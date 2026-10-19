#!/usr/bin/env python3
"""HENGCE E2_PROFIT_MAX finite Round-2 search.

Frozen before this run:
- signal core: rev1 residual / no teacher / K=25 / Top1
- universe: TWSE-listed electronics research mother
- local shock gate: electronics median 1d < 0 and electronics 5d <= -2%
- macro thresholds: copied from Q017, never optimized here
- costs: already embedded in each exit return (0.8% round trip)

This script searches exactly 8 environment gates x 10 exit policies = 80.
It does not add factors, retune K, add stop-loss/take-profit, or modify Q017.
"""
from __future__ import annotations

import base64
import csv
import gzip
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[3]
R2 = ROOT / "research" / "e2_profit_max" / "round2"
MACRO = ROOT / "research" / "e2_profit_max" / "macro"
INPUT = R2 / "input_shock"

TRAIN_END = date(2025, 12, 31)
VAL_START = date(2026, 1, 1)
VAL_END = date(2026, 10, 16)

GATES = {
    "TW_ONLY": (),
    "TW_SOX1": ("sox1",),
    "TW_SOX5": ("sox5",),
    "TW_DXY5": ("dxy5",),
    "TW_SOX1_SOX5": ("sox1", "sox5"),
    "TW_SOX1_DXY5": ("sox1", "dxy5"),
    "TW_SOX5_DXY5": ("sox5", "dxy5"),
    "TW_FULL_Q017_MACRO": ("sox1", "sox5", "dxy5"),
}
EXITS = [
    "fixed1", "fixed3", "fixed5", "fixed10", "fixed20", "fixed40", "fixed60",
    "resid_normalized", "tw_recovery", "tw_shock_cleared",
]


def d(s):
    if s in (None, "", "nan"):
        return None
    return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()


def f(x):
    if x is None or x == "":
        return None
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except Exception:
        return None


def load_payload():
    chunks = sorted(INPUT.glob("r2shock_*.txt"))
    if len(chunks) != 3:
        raise RuntimeError(f"ROUND2_INPUT_CHUNK_COUNT:{len(chunks)}")
    b64 = "".join(p.read_text(encoding="utf-8").strip() for p in chunks)
    raw = gzip.decompress(base64.b64decode(b64))
    obj = json.loads(raw)
    if obj.get("schema") != 1 or obj.get("core") != "rev1_no_teacher_K25_Top1":
        raise RuntimeError("ROUND2_INPUT_CORE_MISMATCH")
    if obj.get("pre_gate") != "TW_SHOCK_m1_lt_0_m5_lte_-0.02":
        raise RuntimeError("ROUND2_INPUT_GATE_MISMATCH")
    cols = obj["c"]
    rows = [dict(zip(cols, r)) for r in obj["r"]]
    if len(rows) != 152:
        raise RuntimeError(f"ROUND2_INPUT_ROW_COUNT:{len(rows)}")
    for r in rows:
        r["signal_date"] = d(r["signal_date"])
        r["ticker"] = str(r["ticker"]).zfill(4)
        r["tw_m1"] = f(r["tw_m1"])
        r["tw_m5"] = f(r["tw_m5"])
        if not (r["tw_m1"] is not None and r["tw_m1"] < 0 and r["tw_m5"] is not None and r["tw_m5"] <= -0.02):
            raise RuntimeError("ROUND2_PREFILTER_DRIFT")
        for e in EXITS:
            r[f"{e}_exit_date"] = d(r.get(f"{e}_exit_date"))
            r[f"{e}_net_ret"] = f(r.get(f"{e}_net_ret"))
    return rows


def load_macro(path: Path):
    out = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            ds = d(r.get("date"))
            if not ds:
                continue
            out.append({"date": ds, "ret1": f(r.get("ret1")), "ret5": f(r.get("ret5"))})
    return sorted(out, key=lambda x: x["date"])


def prior_macro(series, signal_date):
    # Dataset is small; explicit scan makes the causal condition obvious.
    z = None
    for r in series:
        if r["date"] >= signal_date:
            break
        z = r
    return z


def attach_macro(rows):
    sox = load_macro(MACRO / "sox_daily_202212_202610.csv")
    dxy = load_macro(MACRO / "dxy_exact_DX-Y.NYB_202212_202610.csv")
    if len(sox) < 900 or len(dxy) < 900:
        raise RuntimeError("ROUND2_MACRO_TOO_SHORT")
    for r in rows:
        s = prior_macro(sox, r["signal_date"])
        x = prior_macro(dxy, r["signal_date"])
        r["sox_session"] = s["date"] if s else None
        r["sox1"] = s["ret1"] if s else None
        r["sox5"] = s["ret5"] if s else None
        r["dxy_session"] = x["date"] if x else None
        r["dxy5"] = x["ret5"] if x else None
        if s and not s["date"] < r["signal_date"]:
            raise RuntimeError("SOX_FUTURE_LEAK")
        if x and not x["date"] < r["signal_date"]:
            raise RuntimeError("DXY_FUTURE_LEAK")
    return rows


def gate_ok(r, gate):
    req = GATES[gate]
    checks = {
        "sox1": r.get("sox1") is not None and r["sox1"] <= 0.0,
        "sox5": r.get("sox5") is not None and r["sox5"] <= -0.03,
        "dxy5": r.get("dxy5") is not None and r["dxy5"] >= -0.005,
    }
    return all(checks[k] for k in req)


def max_drawdown(nav_path):
    peak = 1.0
    mdd = 0.0
    for n in nav_path:
        peak = max(peak, n)
        mdd = min(mdd, n / peak - 1.0)
    return mdd


def simulate(rows, gate, exit_name, start, end):
    eligible = []
    for r in rows:
        sd = r["signal_date"]
        if not (start <= sd <= end) or not gate_ok(r, gate):
            continue
        ed = r.get(f"{exit_name}_exit_date")
        rr = r.get(f"{exit_name}_net_ret")
        # No boundary backfill and no forced close for an open-ended dynamic exit.
        if ed is None or rr is None or ed > end:
            continue
        eligible.append((sd, r["ticker"], ed, rr, r))
    eligible.sort(key=lambda x: (x[0], x[1]))

    nav = 1.0
    nav_path = []
    blocked_exit = None
    trades = []
    for sd, ticker, ed, rr, r in eligible:
        # Preserve Round-1 non-overlap semantics: next signal date must be strictly
        # after the prior exit date.
        if blocked_exit is not None and sd <= blocked_exit:
            continue
        nav *= (1.0 + rr)
        nav_path.append(nav)
        blocked_exit = ed
        trades.append({
            "signal_date": sd,
            "ticker": ticker,
            "exit_date": ed,
            "net_ret": rr,
            "holding_calendar_days_from_signal": (ed - sd).days,
            "sox_session": r.get("sox_session"),
            "sox1": r.get("sox1"),
            "sox5": r.get("sox5"),
            "dxy_session": r.get("dxy_session"),
            "dxy5": r.get("dxy5"),
        })
    rets = [t["net_ret"] for t in trades]
    return {
        "nav": nav,
        "return": nav - 1.0,
        "trades": len(trades),
        "wins": sum(x > 0 for x in rets),
        "win_rate": (sum(x > 0 for x in rets) / len(rets)) if rets else None,
        "mean_trade": mean(rets) if rets else None,
        "median_trade": median(rets) if rets else None,
        "max_drawdown": max_drawdown(nav_path),
        "avg_holding_calendar_days_from_signal": mean([t["holding_calendar_days_from_signal"] for t in trades]) if trades else None,
        "max_holding_calendar_days_from_signal": max([t["holding_calendar_days_from_signal"] for t in trades]) if trades else None,
        "events": trades,
    }


def yearly_train(rows, gate, exit_name):
    out = {}
    for y in (2023, 2024, 2025):
        out[str(y)] = simulate(rows, gate, exit_name, date(y, 1, 1), date(y, 12, 31))
    return out


def main():
    rows = attach_macro(load_payload())
    grid = []
    for gate in GATES:
        for ex in EXITS:
            all_train = simulate(rows, gate, ex, date(2023, 1, 1), TRAIN_END)
            yy = yearly_train(rows, gate, ex)
            robust = all(yy[str(y)]["trades"] >= 4 and yy[str(y)]["nav"] > 1.0 for y in (2023, 2024, 2025))
            grid.append({
                "gate": gate,
                "exit": ex,
                "train_nav": all_train["nav"],
                "train_return": all_train["return"],
                "train_trades": all_train["trades"],
                "train_win_rate": all_train["win_rate"],
                "train_max_drawdown": all_train["max_drawdown"],
                "train_avg_hold_calendar_days": all_train["avg_holding_calendar_days_from_signal"],
                "train_max_hold_calendar_days": all_train["max_holding_calendar_days_from_signal"],
                "robust_annual_positive": robust,
                **{f"{y}_nav": yy[str(y)]["nav"] for y in (2023, 2024, 2025)},
                **{f"{y}_trades": yy[str(y)]["trades"] for y in (2023, 2024, 2025)},
            })
    if len(grid) != 80:
        raise RuntimeError(f"ROUND2_GRID_COUNT:{len(grid)}")

    robust = [x for x in grid if x["robust_annual_positive"]]
    status = "PASS_TRAIN_ROBUST_FOUND" if robust else "FAIL_ROUND2_NO_ROBUST"
    winner = None
    validation = None
    if robust:
        winner = sorted(robust, key=lambda x: (x["train_nav"], x["train_max_drawdown"]), reverse=True)[0]
        validation = simulate(rows, winner["gate"], winner["exit"], VAL_START, VAL_END)
        validation["status"] = "PASS" if validation["nav"] > 1.0 and validation["trades"] >= 4 else "FAIL"
        validation["label"] = "LOCKED_2026_VALIDATION_NOT_PRISTINE_OOS_BECAUSE_2026_WAS_OBSERVED_IN_ROUND1"

    R2.mkdir(parents=True, exist_ok=True)
    grid_sorted = sorted(grid, key=lambda x: (x["robust_annual_positive"], x["train_nav"], x["train_max_drawdown"]), reverse=True)
    with (R2 / "train_grid_80.csv").open("w", encoding="utf-8", newline="") as fh:
        cols = list(grid_sorted[0].keys())
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader(); w.writerows(grid_sorted)

    if winner and validation:
        with (R2 / "winner_validation_events.csv").open("w", encoding="utf-8", newline="") as fh:
            cols = list(validation["events"][0].keys()) if validation["events"] else ["signal_date","ticker","exit_date","net_ret"]
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for e in validation["events"]:
                z = {**e}
                for k in ("signal_date","exit_date","sox_session","dxy_session"):
                    if z.get(k): z[k] = z[k].isoformat()
                w.writerow(z)

    def clean_event(e):
        z = dict(e)
        for k in ("signal_date","exit_date","sox_session","dxy_session"):
            if z.get(k): z[k] = z[k].isoformat()
        return z
    if validation:
        validation_json = {k:v for k,v in validation.items() if k != "events"}
        validation_json["events"] = [clean_event(e) for e in validation["events"]]
    else:
        validation_json = None

    result = {
        "schema_version": 1,
        "system": "HENGCE",
        "engine": "E2_PROFIT_MAX",
        "round": 2,
        "status": status,
        "authority": "RESEARCH_ONLY_ZERO_CAPITAL_AUTHORITY",
        "capital_authority_twd": 0,
        "search_space": {
            "count": 80,
            "frozen_signal_core": "rev1_no_teacher_K25_Top1",
            "local_gate_fixed": "tw_m1<0 and tw_m5<=-0.02",
            "macro_thresholds_not_optimized": {"sox1_max":0.0,"sox5_max":-0.03,"dxy5_min":-0.005},
            "gates": list(GATES.keys()),
            "exits": EXITS,
            "dynamic_exit_has_no_hard_max": True,
            "roundtrip_cost_embedded": 0.008,
            "new_feature_engineering_forbidden_in_this_round": True,
        },
        "macro_causality": "latest completed US session with session_date < Taiwan signal date",
        "train_period": "2023-01-01..2025-12-31",
        "robust_rule": "each 2023/2024/2025 >=4 completed trades and annual NAV > 1",
        "robust_count": len(robust),
        "winner": winner,
        "validation_period": "2026-01-01..2026-10-16",
        "validation": validation_json,
        "historical_membership_warning": "2023-2025 discovery mother still uses electronics proxy-union; exact daily PIT membership revalidation is required before promotion.",
        "validation_exposure_warning": "2026 was already observed in Round1, so Round2 2026 is locked validation rather than pristine untouched OOS.",
        "promotion_rule": "No rescue tuning. Exact 2023-2025 PIT revalidate frozen winner once; if it fails, kill candidate. Then require forward evidence before capital authority.",
        "legacy_e2": "REVOKED_ZERO_AUTHORITY",
        "q017_mutated": False,
    }
    (R2 / "round2_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": status,
        "robust_count": len(robust),
        "winner": winner,
        "validation": {k:v for k,v in (validation or {}).items() if k != "events"},
    }, ensure_ascii=False, indent=2, default=str))
    return 0 if robust else 2


if __name__ == "__main__":
    raise SystemExit(main())
