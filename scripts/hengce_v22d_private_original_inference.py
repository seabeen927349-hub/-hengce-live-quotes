#!/usr/bin/env python3
"""Read-only V2.2-D original-checkpoint daily research replay.

Sources: existing SHA-pinned historical price mother, G1 TDCC cohort and
2026 canonical mother supplied locally from private HENGCE Library.
No downloader, no training, no synthetic daily TDCC headcount, no orders.
The original model checkpoint is NEVER committed to this repository.
Historical TDCC first-publication dates are not fully PIT-certified, so even
a same-day run cannot promote this report to a formal selector.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import zipfile
from pathlib import Path
from zoneinfo import ZoneInfo

MODEL_HASH = "db47b6f2276150610972d50a8f2b1a9d816eb89fc415d41db5c81b12c1c94a97"
REG_HASH = "8e6931fa9b4ca4324db3b24feb47312bbcbdb9030388e00ab5e8f2e36b014c06"
PRICE_HASH = "b3275f8d58779fbec864a05066414d27e80cef8a68a76a08051f93808f1f8c93"
TDCC_HASH = "71083d73a791b6bf25770139c65e8d29012a44e31c39f66479806bf5a562bc88"
KNOWN_20261111_CANONICAL_HASH = "67cc7454094a884c4769d0fa5172bdfba175fc7b95182714a40ced3c42d28d5f"
FEATURES = [
    "weekday", "known_lag", "log_known", "last_known_delta",
    "prior_known_delta", "ret1", "ret5", "ret10", "ret20",
    "turnratio5_20", "margin10", "intradayrange", "logturn20",
    "thiswk_turnratio", "thiswkret", "netfrac",
]
PRICE_COLS = [
    "Date", "Ticker", "Open", "High", "Low", "Close", "Volume",
    "Turnover", "Margin_MarginBalance", "TotalNet",
]


def eligible_full_market_ticker(ticker):
    """TWSE research candidate identifier: include ordinary 99xx shares.
    
    The original EOD price universe supplies actual membership; this only
    excludes obvious nonstock/TDR codes before the verified EOD intersection.
    Do not mistake first digit 9 for a security type.
    """
    return (isinstance(ticker, str) and len(ticker) == 4
            and ticker.isdecimal() and ticker[0] != "0"
            and not ticker.startswith("91"))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_hash(path, wanted):
    found = digest(path)
    if found != wanted:
        raise ValueError("ORIGINAL_VESSEL_SHA_MISMATCH " + str(path.name) +
                         " actual=" + found)
    return found


def infer(base, tdcc, recent, checkpoint, decision_day,
          recent_sha256=KNOWN_20261111_CANONICAL_HASH,
          universe_mode="FIXED_781", tdcc_sha256=None):
    """FIXED_781 is immutable legacy; ALL_TWSE_10LOT_RESEARCH is a distinct sidecar."""
    """Reproduce original features/LightGBM; never infer a live trading signal."""
    import numpy as np
    import pandas as pd
    import lightgbm as lgb

    decision = dt.date.fromisoformat(decision_day)
    if universe_mode not in ("FIXED_781", "ALL_TWSE_10LOT_RESEARCH"):
        raise ValueError("UNKNOWN_V22D_RESEARCH_UNIVERSE_MODE")
    if decision.weekday() > 3 and not (
            universe_mode == "ALL_TWSE_10LOT_RESEARCH" and decision.weekday() == 4):
        raise ValueError("V22D_ONLY_MONDAY_THROUGH_THURSDAY")
    if decision > dt.datetime.now(ZoneInfo("Asia/Taipei")).date():
        raise ValueError("FUTURE_DECISION_DATE_FORBIDDEN")
    # The all-TWSE sidecar only needs the SHA-verified last 100-calendar-day
    # original canonical mother; no duplicate nine-year historical collector.
    # Legacy FIXED_781 retains ALL its original pinned input requirements.
    if universe_mode == "ALL_TWSE_10LOT_RESEARCH":
        # The G1 original 457-week panel is SHA-pinned separately; the PRIVATE
        # 2026 rolling research derivative has a distinct byte hash. Never
        # disable integrity checks or falsely claim that hashes are equal.
        if (not isinstance(tdcc_sha256, str) or len(tdcc_sha256) != 64):
            raise ValueError("PRIVATE_DERIVED_TDCC_SHA_REQUIRED")
        sources = ((tdcc, tdcc_sha256), (recent, recent_sha256))
    else:
        if tdcc_sha256 is not None:
            raise ValueError("LEGACY_ORIGINAL_TDCC_SHA_OVERRIDE_FORBIDDEN")
        sources = ((base, PRICE_HASH), (tdcc, TDCC_HASH), (recent, recent_sha256))
    for path, wanted in sources:
        check_hash(path, wanted)
    if decision > dt.date(2026, 11, 11) and recent_sha256 == KNOWN_20261111_CANONICAL_HASH:
        raise ValueError("NEWER_CANONICAL_SHA_REQUIRED_FOR_LATER_DECISION")

    with zipfile.ZipFile(checkpoint) as archive:
        def load(name, expected):
            raw = archive.read(name)
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("ORIGINAL_V22D_MODEL_CHECKPOINT_SHA_MISMATCH")
            return lgb.Booster(model_str=raw.decode("utf-8"))
        classifier = load("V22D_original_2019_2022_classifier.txt", MODEL_HASH)
        regressor = load("V22D_original_2019_2022_regressor.txt", REG_HASH)
    # Never let model feature order drift when the source code is refactored.
    if classifier.feature_name() != FEATURES or regressor.feature_name() != FEATURES:
        raise ValueError("ORIGINAL_CHECKPOINT_FEATURE_ORDER_MISMATCH")

    cols = ["SnapshotDate", "Ticker", "HolderLe10Lots",
            "RetailPeopleValid", "Big400Pct", "TierStatus"]
    w = pd.read_csv(tdcc, usecols=cols,
                    dtype={"Ticker": str, "SnapshotDate": str}, low_memory=False)
    w["SnapshotDate"] = pd.to_datetime(w.SnapshotDate, format="%Y%m%d", errors="coerce")
    if universe_mode == "FIXED_781":
        # Original checkpoint replay contract is preserved byte-for-byte in its
        # universe selection. Never silently change historical 781 comparators.
        first = (w[(w.SnapshotDate.dt.year == 2018) & w.TierStatus.eq("VALID")]
                 .sort_values(["Ticker", "SnapshotDate"])
                 .groupby("Ticker").first())
        cohort = set(first[first.Big400Pct >= 50].index)
        if len(cohort) != 781:
            raise ValueError("FIXED_2018_781_COHORT_MISMATCH")
    else:
        # Existing G1 weekly TDCC mother already covers historical TWSE issues
        # outside the original 781. This is a NEW RESEARCH UNIVERSE, not a
        # retrained model. Require actual valid <=10-lot holder observations
        # no later than the original 14-day information cutoff.
        cutoff = pd.Timestamp(decision - dt.timedelta(days=14))
        mask = (w.TierStatus.eq("VALID") &
                w.RetailPeopleValid.astype(str).str.lower().isin(["true", "1"]) &
                w.SnapshotDate.le(cutoff) &
                w.Ticker.map(eligible_full_market_ticker))
        cohort = set(w.loc[mask, "Ticker"].unique())
        if len(cohort) < 900:
            raise ValueError("FULL_TWSE_TDCC_COVERAGE_INSUFFICIENT")
    w = w[w.Ticker.isin(cohort)].copy()
    w["N"] = pd.to_numeric(w.HolderLe10Lots, errors="coerce").where(
        w.RetailPeopleValid.astype(str).str.lower().isin(["true", "1"]))
    w = (w.sort_values(["Ticker", "SnapshotDate"])
         .drop_duplicates(["Ticker", "SnapshotDate"]).reset_index(drop=True))
    g = w.groupby("Ticker", sort=False)
    for i in (1, 2):
        w["Nlag" + str(i)] = g.N.shift(i)
    w = (w[["Ticker", "SnapshotDate", "N", "Nlag1", "Nlag2"]]
         .rename(columns={"SnapshotDate": "known_date", "N": "known0",
                          "Nlag1": "known1", "Nlag2": "known2"})
         .sort_values(["known_date", "Ticker"]))

    now = pd.Timestamp(decision)
    start = now - pd.Timedelta(days=100)
    def price_chunks(path, after=None):
        for ch in pd.read_csv(
                path, usecols=PRICE_COLS, dtype={"Ticker": str},
                parse_dates=["Date"], low_memory=False,
                na_values=["--", "---", "-"], chunksize=75000):
            keep = (ch.Date >= start) & (ch.Date <= now) & ch.Ticker.isin(cohort)
            if after is not None:
                keep &= ch.Date > after
            part = ch.loc[keep]
            if len(part):
                yield part
    if universe_mode == "ALL_TWSE_10LOT_RESEARCH":
        parts = list(price_chunks(recent))
    else:
        parts = list(price_chunks(base))
        parts.extend(price_chunks(recent, after=pd.Timestamp("2026-11-06")))
    if not parts:
        raise ValueError("NO_PRICE_HISTORY_FROM_EXISTING_VESSELS")
    p = (pd.concat(parts, ignore_index=True)
         .sort_values(["Ticker", "Date"])
         .drop_duplicates(["Ticker", "Date"])
         .reset_index(drop=True))
    if p.Date.max().date() != decision:
        raise ValueError("DECISION_EOD_NOT_IN_ORIGINAL_MOTHER")
    for col in PRICE_COLS[2:]:
        p[col] = pd.to_numeric(p[col], errors="coerce").astype("float32")
    p["wfriday"] = p.Date.dt.to_period("W-FRI").dt.end_time.dt.normalize()
    p["weekday"] = p.Date.dt.weekday.astype("int8")
    g = p.groupby("Ticker", sort=False)
    for k in (1, 5, 10, 20):
        p["ret" + str(k)] = (p.Close / g.Close.shift(k) - 1).clip(-.90, 3).astype("float32")
    for k in (5, 20):
        p["volmean" + str(k)] = g.Volume.transform(
            lambda s: s.rolling(k, min_periods=k).mean()).astype("float32")
        p["turnmed" + str(k)] = g.Turnover.transform(
            lambda s: s.rolling(k, min_periods=k).median()).astype("float32")
    p["turnratio5_20"] = (p.volmean5 / p.volmean20.replace(0, np.nan)).clip(0, 50).astype("float32")
    p["margin10"] = (p.Margin_MarginBalance / g.Margin_MarginBalance.shift(10) - 1).replace(
        [np.inf, -np.inf], np.nan).clip(-1, 3).astype("float32")
    p["intradayrange"] = (p.High / p.Low.replace(0, np.nan) - 1).clip(0, 1).astype("float32")
    p["logturn20"] = np.log1p(p.turnmed20.clip(lower=0)).astype("float32")
    gw = p.groupby(["Ticker", "wfriday"], sort=False)
    p["week_days"] = (gw.cumcount() + 1).astype("int8")
    p["thiswk_turnavg"] = (p.Turnover.fillna(0).groupby(
        [p.Ticker, p.wfriday], sort=False).cumsum() / p.week_days).astype("float32")
    p["thiswk_turnratio"] = (p.thiswk_turnavg / p.turnmed20.replace(0, np.nan)).clip(0, 50).astype("float32")
    lastwk = gw.Close.last().rename("weekclose").reset_index().sort_values(["Ticker", "wfriday"])
    lastwk["prev_week_close"] = lastwk.groupby("Ticker").weekclose.shift(1)
    p = p.merge(lastwk[["Ticker", "wfriday", "prev_week_close"]],
                on=["Ticker", "wfriday"], how="left", validate="many_to_one")
    p["thiswkret"] = (p.Close / p.prev_week_close - 1).clip(-.9, 3).astype("float32")
    p["thiswknet"] = p.TotalNet.fillna(0).groupby(
        [p.Ticker, p.wfriday], sort=False).cumsum()
    p["thiswkvol"] = p.Volume.fillna(0).groupby(
        [p.Ticker, p.wfriday], sort=False).cumsum()
    p["netfrac"] = (p.thiswknet / p.thiswkvol.replace(0, np.nan)).clip(-10, 10).astype("float32")
    p["valid_close"] = p.Close.where(p.Volume.gt(0))
    logclose = np.log(p.valid_close.where(p.valid_close.gt(0)))
    p["volatility20"] = logclose.groupby(p.Ticker).diff().groupby(
        p.Ticker).transform(lambda s: s.rolling(20, min_periods=20).std()).astype("float32")
    d = p[p.Date.eq(now)].copy()
    d["cutoff"] = d.Date - pd.Timedelta(days=14)
    d = d.sort_values(["cutoff", "Ticker"])
    d = pd.merge_asof(d, w, left_on="cutoff", right_on="known_date",
                      by="Ticker", direction="backward", allow_exact_matches=True)
    d["last_age"] = (d.cutoff - d.known_date).dt.days
    d["known_lag"] = ((d.wfriday - d.known_date).dt.days / 7).round().astype("float32")
    d["log_known"] = np.log1p(d.known0).astype("float32")
    d["last_known_delta"] = (d.known0 / d.known1 - 1).clip(-.5, .5).astype("float32")
    d["prior_known_delta"] = (d.known1 / d.known2 - 1).clip(-.5, .5).astype("float32")
    d = d[d.known0.gt(0) & d.known1.gt(0) & d.known2.gt(0) &
          d.last_age.between(0, 7) & d.known_lag.between(1, 5)].copy()
    if universe_mode == "ALL_TWSE_10LOT_RESEARCH":
        # Full-market research reports only currently priced/tradable issues
        # as scorable; 1538 on 2026-11-13 had no valid price. Retain its
        # source row in the original mother, but not the selection universe.
        d = d[d.valid_close.gt(0)].copy()
    for col in FEATURES:
        d[col] = d[col].replace([np.inf, -np.inf], np.nan)
    d["score"] = classifier.predict(d[FEATURES]).astype("float32")
    d["estimated_weekend_holders"] = (
        d.known0 * np.exp(np.clip(regressor.predict(d[FEATURES]), -.7, .7))
    ).clip(lower=0).astype("float32")
    d["eligible"] = (d.ret20.ge(.05) & d.ret5.ge(0) &
                     d.turnmed20.ge(1e7) & d.volatility20.gt(0) &
                     d.valid_close.gt(0) & d.score.ge(.50))
    eligible = d[d.eligible].sort_values(
        ["turnmed20", "Ticker"], ascending=[False, True])
    leading = eligible.head(5).copy()
    # LightGBM TreeSHAP: base + all 16 contributions = raw log odds;
    # sigmoid(raw log odds) = classifier probability-shaped score.
    # These are attribution terms, NOT causal effects or percentage points.
    if len(leading):
        matrix = leading[FEATURES]
        attribution = classifier.predict(matrix, pred_contrib=True)
        raw = classifier.predict(matrix, raw_score=True)
        if attribution.shape != (len(leading), len(FEATURES) + 1):
            raise ValueError("V22D_SCORE_CONTRIBUTION_DIMENSION_MISMATCH")
    else:
        attribution = np.empty((0, len(FEATURES) + 1))
        raw = np.empty((0,))
    full_rank = []
    all_scored = []
    if universe_mode == "ALL_TWSE_10LOT_RESEARCH":
        # Needed for previous-qualifier exit audit. A missing ticker is
        # UNKNOWN, never an inferred score failure. No separate market rank.
        for _, z in d.iterrows():
            price_gate = (pd.notna(z["ret20"]) and z["ret20"] >= .05
                          and pd.notna(z["ret5"]) and z["ret5"] >= 0
                          and pd.notna(z["turnmed20"]) and z["turnmed20"] >= 1e7
                          and pd.notna(z["volatility20"]) and z["volatility20"] > 0
                          and pd.notna(z["valid_close"]) and z["valid_close"] > 0)
            all_scored.append({
                "ticker": str(z["Ticker"]),
                "score": float(z["score"]),
                "close": float(z["Close"]),
                "ret20": (float(z["ret20"]) if pd.notna(z["ret20"]) else None),
                "ret5": (float(z["ret5"]) if pd.notna(z["ret5"]) else None),
                "turnover20_median": (float(z["turnmed20"]) if pd.notna(z["turnmed20"]) else None),
                "volatility20": (float(z["volatility20"]) if pd.notna(z["volatility20"]) else None),
                "price_gate": bool(price_gate),
                "model_gate": bool(z["eligible"]),
            })
        if (len(all_scored) != len(d) or
                sum(item["model_gate"] for item in all_scored) != len(eligible)):
            raise ValueError("FULLMARKET_SCORE_AUDIT_DISAGREES_WITH_QUALIFIED")

        # Publish every qualifying ticker for a single ranked report, not a
        # second top5. No post-decision TDCC is ever a model feature here.
        for rank, (_, rr) in enumerate(eligible.iterrows(), 1):
            full_rank.append({
                "rank": rank, "ticker": str(rr["Ticker"]),
                "close": float(rr["Close"]), "score": float(rr["score"]),
                "ret20": float(rr["ret20"]), "ret5": float(rr["ret5"]),
                "turnover20_median": float(rr["turnmed20"]),
                "known_date": rr["known_date"].strftime("%Y-%m-%d"),
                "last_known_le10_holder_count": float(rr["known0"]),
                "estimated_week_end_le10_holder_count":
                    float(rr["estimated_weekend_holders"]),
            })
    rows = leading[["Ticker", "score", "ret20", "ret5", "turnmed20",
                    "known_date", "known0", "estimated_weekend_holders", "Close"]].copy()
    rows["known_date"] = rows.known_date.dt.strftime("%Y-%m-%d")
    top = []
    for idx, (rank, row) in enumerate(enumerate(rows.to_dict("records"), 1)):
        contributions = {key: float(attribution[idx, j])
                         for j, key in enumerate(FEATURES)}
        input_values = {key: (None if not math.isfinite(float(leading.iloc[idx][key]))
                              else float(leading.iloc[idx][key]))
                        for key in FEATURES}
        z = float(raw[idx])
        baseline = float(attribution[idx, -1])
        checked_sum = baseline + sum(contributions.values())
        # Numerically stable logistic; scores still not calibrated probabilities.
        reconstructed = (1.0 / (1.0 + math.exp(-z)) if z >= 0
                         else math.exp(z) / (1.0 + math.exp(z)))
        if (not math.isclose(checked_sum, z, rel_tol=0, abs_tol=1e-6)
                or not math.isclose(reconstructed, float(row["score"]),
                                    rel_tol=0, abs_tol=1e-6)):
            raise ValueError("V22D_SCORE_RECONSTRUCTION_MISMATCH")
        top.append({"rank": rank, "ticker": row["Ticker"],
                    "daily_decline_score": float(row["score"]),
                    "return_20d": float(row["ret20"]), "return_5d": float(row["ret5"]),
                    "median_20d_turnover_twd": float(row["turnmed20"]),
                    "last_assumed_available_tdcc_date": row["known_date"],
                    "last_known_le10_holder_count": float(row["known0"]),
                    "estimated_week_end_le10_holder_count": float(row["estimated_weekend_holders"]),
                    "last_verified_close": float(row["Close"]),
                    "score_explanation": {
                        "method": "LIGHTGBM_TREE_SHAP_RAW_LOG_ODDS",
                        "model_target": "CURRENT_WEEK_LE10_HOLDERS_VS_TWO_WEEKS_PRIOR_DECREASE_GE_1PCT",
                        "baseline_raw_log_odds": baseline,
                        "feature_inputs": input_values,
                        "feature_contributions_raw_log_odds": contributions,
                        "raw_log_odds": z,
                        "sum_reconstructed_raw_log_odds": checked_sum,
                        "sigmoid_reconstructed_score": reconstructed,
                        "score_is_calibrated_probability": False,
                        "score_is_expected_stock_return": False,
                    }})
    generated = dt.datetime.now(ZoneInfo("Asia/Taipei"))
    result = {
        "schema": "HENGCE_V22D_PRIVATE_ORIGINAL_CHECKPOINT_REPLAY_V1",
        "system": "HENGCE", "model_id": "v22d_daily_nowcast_liquidity_top5_v1",
        "status": "RESEARCH_REPLAY_NOT_PIT_CERTIFIED",
        "decision_date": decision.isoformat(), "generated_at_taipei": generated.isoformat(),
        "fixed_cohort_count": 781 if universe_mode == "FIXED_781" else None,
        "universe_mode": universe_mode,
        "research_universe_count": len(cohort),
        "friday_shadow_only": decision.weekday() == 4,
        "feature_coverage": len(d),
        "qualified_count": len(eligible), "top5": top,
        **({"all_qualified": full_rank,
            "all_scored_for_exit_audit": all_scored,
            "price_gate_count": sum(z["price_gate"] for z in all_scored)}
           if universe_mode == "ALL_TWSE_10LOT_RESEARCH" else {}),
        "score_formula": "SIGMOID(BASE_LOG_ODDS_PLUS_16_FEATURE_CONTRIBUTIONS)",
        "score_feature_order": list(FEATURES),
        "target_event": "CURRENT_WEEK_LE10_HOLDERS_VS_TWO_WEEKS_PRIOR_DECREASE_GE_1PCT",
        "score_cutoff": 0.50,
        "score_explanations_are_causal_effects": False,
        "last_assumed_tdcc_snapshot": d.known_date.max().strftime("%Y-%m-%d") if len(d) else None,
        "source_sha256": {"original_prices": (
            PRICE_HASH if universe_mode == "FIXED_781" else None),
            "original_tdcc": (TDCC_HASH if universe_mode == "FIXED_781"
                              else tdcc_sha256),
                          "original_2026_canonical": recent_sha256, "classifier": MODEL_HASH,
                          "regressor": REG_HASH},
        "historical_tdcc_first_observed_pit_certified": False,
        "current_selection": False, "retrospective_only": True,
        "prediction_is_real_daily_retail_count": False,
        "score_is_calibrated_probability": False, "trading_authority": False,
        "formal_selection_authority": False, "buy_signal": False, "sell_signal": False,
        "broker_execution": False, "capital_authority_twd": 0,
        "authorized_lots": 0,
    }
    result["receipt_sha256"] = hashlib.sha256(
        json.dumps(result, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode("utf-8")).hexdigest()
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-price-mother", type=Path, required=True)
    p.add_argument("--original-tdcc-mother", type=Path, required=True)
    p.add_argument("--original-2026-canonical", type=Path, required=True)
    p.add_argument("--private-original-model", type=Path, required=True)
    p.add_argument("--decision-date", required=True)
    p.add_argument("--tdcc-sha256",
                   help="Required fullmarket SHA-verified PRIVATE G1 rolling cache digest")
    p.add_argument("--universe-mode", choices=["FIXED_781", "ALL_TWSE_10LOT_RESEARCH"],
                   default="FIXED_781")
    p.add_argument("--canonical-sha256", default=KNOWN_20261111_CANONICAL_HASH)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    result = infer(args.original_price_mother, args.original_tdcc_mother,
                   args.original_2026_canonical, args.private_original_model,
                   args.decision_date, args.canonical_sha256,
                   universe_mode=args.universe_mode, tdcc_sha256=args.tdcc_sha256)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                          indent=2, allow_nan=False)
                        + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"],
                      "date": result["decision_date"],
                      "qualified": result["qualified_count"],
                      "top5": [r["ticker"] for r in result["top5"]]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
