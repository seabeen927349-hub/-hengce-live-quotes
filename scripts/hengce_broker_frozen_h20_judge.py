#!/usr/bin/env python3
"""Frozen HENGCE Broker Structure H20 judge.

This implementation is governed by the already-frozen Broker Structure
preregistration. Do not run it on partial historical Broker factor data.

Primary inference:
- date-level cross-sectional rank OLS (Fama-MacBeth coefficient series)
- BROKER_GROSS_HHI_1D primary coefficient
- Newey-West/HAC lag 20 on the daily coefficient mean
- non-circular moving-block bootstrap, block 20, 10,000 resamples, seed 20261103
- two-sided inference
- early/late sign stability lock

No threshold/top-k/sign flip/state rescue/horizon rescue is implemented here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

PRIMARY_HORIZON = "H20_RETURN"
FEATURE = "BROKER_GROSS_HHI_1D"
CONTROLS = ["MOM20", "REV5_LOG", "LIQ20", "AGG_FLOW5"]
STATE = "HENGCE_STATE_S5"
VALID_STATES = {"DIFFUSE_NORMAL", "SYNCHRONIZED_STRESS"}
HAC_LAG = 20
BOOT_BLOCK = 20
BOOT_DRAWS = 10_000
BOOT_SEED = 20261103
EARLY_END = pd.Timestamp("2022-12-31")
LATE_START = pd.Timestamp("2023-01-01")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rank01(s: pd.Series) -> pd.Series:
    n = int(s.notna().sum())
    if n < 2 or n != len(s):
        raise ValueError("RANK01_REQUIRES_COMPLETE_N_GE_2")
    r = s.rank(method="average", ascending=True)
    return (r - 1.0) / float(n - 1)


def daily_regression(g: pd.DataFrame) -> dict:
    ranked = pd.DataFrame(index=g.index)
    ranked["Y"] = rank01(g[PRIMARY_HORIZON])
    ranked["B"] = rank01(g[FEATURE])
    ranked["M"] = rank01(g["MOM20"])
    ranked["R"] = rank01(g["REV5_LOG"])
    ranked["L"] = rank01(g["LIQ20"])
    ranked["F"] = rank01(g["AGG_FLOW5"])
    y = ranked["Y"].to_numpy(dtype=float)
    X = np.column_stack([
        np.ones(len(ranked), dtype=float),
        ranked[["B", "M", "R", "L", "F"]].to_numpy(dtype=float),
    ])
    rank = int(np.linalg.matrix_rank(X))
    if rank != X.shape[1]:
        raise np.linalg.LinAlgError(f"RANK_DEFICIENT:{rank}/{X.shape[1]}")
    coef, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    return {
        "intercept": float(coef[0]),
        "b_broker": float(coef[1]),
        "b_mom20": float(coef[2]),
        "b_rev5": float(coef[3]),
        "b_liq20": float(coef[4]),
        "b_agg_flow5": float(coef[5]),
        "n": int(len(g)),
    }


def hac_mean_inference(x: np.ndarray, lag: int) -> dict:
    """Intercept-only Newey-West HAC, Bartlett kernel, finite-sample correction.

    gamma_l uses denominator T. Long-run variance uses Bartlett weights.
    The covariance receives the intercept-only finite-sample multiplier T/(T-1).
    The reported t statistic is mean / HAC-SE; two-sided p and 95% CI use a
    Student-t reference with df=T-1. These conventions are frozen here before
    any full historical Broker outcome execution.
    """
    x = np.asarray(x, dtype=float)
    if x.ndim != 1 or len(x) <= lag + 1 or not np.isfinite(x).all():
        raise ValueError("INVALID_HAC_SERIES")
    T = len(x)
    mu = float(x.mean())
    e = x - mu
    gamma0 = float(np.dot(e, e) / T)
    lrv = gamma0
    for l in range(1, lag + 1):
        gamma = float(np.dot(e[l:], e[:-l]) / T)
        weight = 1.0 - l / float(lag + 1)
        lrv += 2.0 * weight * gamma
    lrv *= T / float(T - 1)  # intercept-only finite-sample correction
    if lrv < 0 and abs(lrv) < 1e-15:
        lrv = 0.0
    if lrv <= 0 or not math.isfinite(lrv):
        raise ValueError("NONPOSITIVE_OR_NONFINITE_HAC_LRV")
    se = math.sqrt(lrv / T)
    tstat = mu / se
    df = T - 1
    crit = float(stats.t.ppf(0.975, df=df))
    p = float(2.0 * stats.t.sf(abs(tstat), df=df))
    return {
        "mean": mu,
        "se_hac_lag20": se,
        "t_hac": tstat,
        "df_reference": df,
        "p_two_sided": p,
        "ci95": [mu - crit * se, mu + crit * se],
        "hac_lag": lag,
        "kernel": "BARTLETT",
        "finite_sample_correction": "T_OVER_T_MINUS_1_INTERCEPT_ONLY",
        "reference_distribution": "STUDENT_T_DF_T_MINUS_1",
    }


def moving_block_bootstrap_mean_ci(x: np.ndarray) -> dict:
    x = np.asarray(x, dtype=float)
    T = len(x)
    if T < BOOT_BLOCK or not np.isfinite(x).all():
        raise ValueError("INVALID_BOOTSTRAP_SERIES")
    starts = np.arange(0, T - BOOT_BLOCK + 1, dtype=int)
    blocks_needed = int(math.ceil(T / BOOT_BLOCK))
    rng = np.random.default_rng(BOOT_SEED)
    means = np.empty(BOOT_DRAWS, dtype=float)
    for b in range(BOOT_DRAWS):
        chosen = rng.choice(starts, size=blocks_needed, replace=True)
        sample = np.concatenate([x[s:s + BOOT_BLOCK] for s in chosen])[:T]
        means[b] = float(sample.mean())
    q = np.quantile(means, [0.025, 0.975], method="linear")
    return {
        "block_length": BOOT_BLOCK,
        "draws": BOOT_DRAWS,
        "seed": BOOT_SEED,
        "scheme": "NONCIRCULAR_OVERLAPPING_MOVING_BLOCKS_TRUNCATE_TO_T",
        "ci_method": "PERCENTILE_LINEAR",
        "ci95": [float(q[0]), float(q[1])],
    }


def excludes_zero(ci: list[float]) -> bool:
    return bool(ci[0] > 0 or ci[1] < 0)


def sign(v: float) -> int:
    return 1 if v > 0 else (-1 if v < 0 else 0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", required=True, help="Frozen complete input panel CSV/CSV.GZ")
    ap.add_argument("--output", required=True)
    ap.add_argument("--daily-beta-output")
    a = ap.parse_args()
    panel_path = Path(a.panel)
    out_path = Path(a.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    result = {
        "system": "HENGCE",
        "artifact": "BROKER_GROSS_HHI_1D_FROZEN_H20_JUDGE",
        "authority": "FROZEN_HISTORICAL_RECONSTRUCTION_TEST_ONLY_NO_PRODUCTION_AUTHORITY",
        "status": "FAIL_CLOSED",
        "primary_horizon": "H20",
        "feature": FEATURE,
        "hard_locks": {
            "named_broker_selection": False,
            "sign_flip_rescue": False,
            "lookback_tuning": False,
            "threshold_optimization": False,
            "horizon_rescue": False,
            "state_rescue": False,
            "imputation": False,
        },
        "errors": [],
    }

    try:
        if not panel_path.is_file():
            raise RuntimeError("PANEL_MISSING")
        result["panel_sha256"] = sha256(panel_path)
        df = pd.read_csv(panel_path, dtype={"ticker": str}, low_memory=False)
        required = {"date", "ticker", PRIMARY_HORIZON, FEATURE, STATE, *CONTROLS}
        missing = sorted(required - set(df.columns))
        if missing:
            raise RuntimeError(f"MISSING_COLUMNS:{missing}")
        df["date"] = pd.to_datetime(df["date"], errors="raise")
        if df.duplicated(["date", "ticker"]).any():
            raise RuntimeError("DUPLICATE_DATE_TICKER")

        date_rows = []
        beta_rows = []
        for d, g0 in df.groupby("date", sort=True):
            u100_n = len(g0)
            if u100_n != 100:
                date_rows.append({"date": d, "u100_n": u100_n, "status": "EXCLUDE_U100_NOT_100"})
                continue
            h20_valid = int(pd.to_numeric(g0[PRIMARY_HORIZON], errors="coerce").notna().sum())
            if h20_valid < 95:
                date_rows.append({"date": d, "u100_n": 100, "h20_valid_n": h20_valid, "status": "EXCLUDE_H20_LT95"})
                continue
            g = g0.copy()
            numeric_cols = [PRIMARY_HORIZON, FEATURE, *CONTROLS]
            for c in numeric_cols:
                g[c] = pd.to_numeric(g[c], errors="coerce")
            finite = np.ones(len(g), dtype=bool)
            for c in numeric_cols:
                finite &= np.isfinite(g[c].to_numpy(dtype=float))
            finite &= g[STATE].isin(VALID_STATES).to_numpy()
            g = g.loc[finite].copy()
            complete_n = len(g)
            if complete_n < 95:
                date_rows.append({
                    "date": d, "u100_n": 100, "h20_valid_n": h20_valid,
                    "complete_n": complete_n, "status": "EXCLUDE_COMPLETE_LT95"
                })
                continue
            states = set(g[STATE].dropna().astype(str))
            if len(states) != 1:
                raise RuntimeError(f"NONCOMMON_STATE_WITHIN_DATE:{d.date()}:{sorted(states)}")
            try:
                co = daily_regression(g)
            except np.linalg.LinAlgError as exc:
                date_rows.append({
                    "date": d, "u100_n": 100, "h20_valid_n": h20_valid,
                    "complete_n": complete_n, "status": f"EXCLUDE_{exc}"
                })
                continue
            beta_rows.append({
                "date": d,
                "state": next(iter(states)),
                "raw_broker_hhi_median": float(g[FEATURE].median()),
                "raw_broker_hhi_iqr": float(g[FEATURE].quantile(0.75) - g[FEATURE].quantile(0.25)),
                **co,
            })
            date_rows.append({
                "date": d, "u100_n": 100, "h20_valid_n": h20_valid,
                "complete_n": complete_n, "status": "INCLUDED_PRIMARY"
            })

        betas = pd.DataFrame(beta_rows).sort_values("date").reset_index(drop=True)
        if len(betas) == 0:
            raise RuntimeError("NO_INCLUDED_PRIMARY_DATES")
        b = betas["b_broker"].to_numpy(dtype=float)
        hac = hac_mean_inference(b, HAC_LAG)
        boot = moving_block_bootstrap_mean_ci(b)

        early = betas[betas.date <= EARLY_END]
        late = betas[betas.date >= LATE_START]
        if early.empty or late.empty:
            raise RuntimeError("EARLY_OR_LATE_PERIOD_EMPTY")
        early_mean = float(early.b_broker.mean())
        late_mean = float(late.b_broker.mean())
        full_sign = sign(hac["mean"])
        temporal_sign_stability = bool(full_sign != 0 and sign(early_mean) == full_sign and sign(late_mean) == full_sign)
        hac_pass = excludes_zero(hac["ci95"])
        boot_pass = excludes_zero(boot["ci95"])
        survival = bool(hac_pass and boot_pass and temporal_sign_stability)

        state_diag = {}
        for st, gs in betas.groupby("state", sort=True):
            state_diag[st] = {
                "date_count": int(len(gs)),
                "mean_b_broker": float(gs.b_broker.mean()),
                "median_b_broker": float(gs.b_broker.median()),
                "fraction_b_broker_gt_zero": float((gs.b_broker > 0).mean()),
                "raw_broker_hhi_median_across_date_medians": float(gs.raw_broker_hhi_median.median()),
                "raw_broker_hhi_median_iqr_across_dates": float(gs.raw_broker_hhi_iqr.median()),
                "authority": "SECONDARY_DESCRIPTIVE_ONLY_CANNOT_RESCUE_PRIMARY",
            }
        year_diag = {
            str(int(y)): {"date_count": int(len(g)), "mean_b_broker": float(g.b_broker.mean())}
            for y, g in betas.groupby(betas.date.dt.year, sort=True)
        }
        control_means = {
            c: float(betas[c].mean())
            for c in ["b_mom20", "b_rev5", "b_liq20", "b_agg_flow5"]
        }

        classification = (
            "INCREMENTAL_VALUE_ESTABLISHED_RECONSTRUCTION_ONLY"
            if survival else "NO_STABLE_INCREMENTAL_VALUE_KILL"
        )
        result.update({
            "status": "COMPLETE_FROZEN_H20_JUDGMENT",
            "classification": classification,
            "date_counts": {
                "input_dates": int(df.date.nunique()),
                "included_primary_dates": int(len(betas)),
                "early_included_dates": int(len(early)),
                "late_included_dates": int(len(late)),
            },
            "primary_broker": {
                "hac": hac,
                "moving_block_bootstrap": boot,
                "early_mean_b_broker": early_mean,
                "late_mean_b_broker": late_mean,
                "full_sign": full_sign,
                "early_sign": sign(early_mean),
                "late_sign": sign(late_mean),
                "hac_ci_excludes_zero": hac_pass,
                "bootstrap_ci_excludes_zero": boot_pass,
                "temporal_sign_stability": temporal_sign_stability,
                "all_survival_requirements_pass": survival,
            },
            "control_coefficient_means_descriptive": control_means,
            "state_diagnostics": state_diag,
            "year_diagnostics": year_diag,
            "excluded_date_status_counts": pd.DataFrame(date_rows)["status"].value_counts().to_dict(),
            "governance_consequence": (
                "RECONSTRUCTION_INCREMENTAL_INFORMATION_ONLY; NO SIGNED TRADING RULE, NO TOP-K, NO THRESHOLD, NO NAMED BROKER, NO PRODUCTION/CAPITAL AUTHORITY"
                if survival else
                "KILL BROKER_GROSS_HHI_1D; NO RESCUE BY SIGN/BROKER_SET/LOOKBACK/THRESHOLD/STATE/HORIZON"
            ),
        })

        if a.daily_beta_output:
            p = Path(a.daily_beta_output)
            p.parent.mkdir(parents=True, exist_ok=True)
            betas.to_csv(p, index=False, date_format="%Y-%m-%d", float_format="%.17g")
            result["daily_beta_sha256"] = sha256(p)
    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}:{exc}")
        result["status"] = "FAIL_CLOSED"

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "status": result.get("status"),
        "classification": result.get("classification"),
        "errors": result.get("errors"),
        "panel_sha256": result.get("panel_sha256"),
    }, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "COMPLETE_FROZEN_H20_JUDGMENT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
