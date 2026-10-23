#!/usr/bin/env python3
"""HENGCE Candidate C finite research screen.

Research-only, zero capital authority. Candidate B / canonical Q017 stay frozen.
This screen reuses the already-committed Round-2 causal event payload and searches
only 4 SOX gate variants x 10 existing exit policies = 40 combinations.

Selection uses 2023-2025 only. 2026 is reported once after selection and is
explicitly non-pristine because that period was already observed in earlier work.
No DXY, no signal-formula tuning, no K/TopN tuning, no threshold tuning.
"""
from __future__ import annotations

import base64
import csv
import gzip
import json
import math
from datetime import date, datetime
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[3]
R2 = ROOT / "research" / "e2_profit_max" / "round2"
MACRO = ROOT / "research" / "e2_profit_max" / "macro"
INPUT = R2 / "input_shock"
OUT = ROOT / "research" / "e2_profit_max" / "candidate_c"

TRAIN_START = date(2023, 1, 1)
TRAIN_END = date(2025, 12, 31)
VAL_START = date(2026, 1, 1)
VAL_END = date(2026, 10, 16)

BASELINE_GATE = "TW_SOX1_SOX5"
BASELINE_EXIT = "fixed20"
GATES = {
    "TW_ONLY": (),
    "TW_SOX1": ("sox1",),
    "TW_SOX5": ("sox5",),
    "TW_SOX1_SOX5": ("sox1", "sox5"),
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
    if x in (None, ""):
        return None
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def load_payload():
    chunks = sorted(INPUT.glob("r2shock_*.txt"))
    if len(chunks) != 3:
        raise RuntimeError(f"CANDIDATE_C_INPUT_CHUNK_COUNT:{len(chunks)}")
    raw = gzip.decompress(base64.b64decode("".join(p.read_text().strip() for p in chunks)))
    obj = json.loads(raw)
    if obj.get("schema") != 1:
        raise RuntimeError("CANDIDATE_C_SCHEMA_MISMATCH")
    if obj.get("core") != "rev1_no_teacher_K25_Top1":
        raise RuntimeError("CANDIDATE_C_CORE_MISMATCH")
    if obj.get("pre_gate") != "TW_SHOCK_m1_lt_0_m5_lte_-0.02":
        raise RuntimeError("CANDIDATE_C_LOCAL_GATE_MISMATCH")
    cols = obj.get("c")
    packed = obj.get("r")
    if not isinstance(cols, list) or not isinstance(packed, list):
        raise RuntimeError("CANDIDATE_C_PAYLOAD_SHAPE")
    rows = [dict(zip(cols, r)) for r in packed]
    if len(rows) != 152:
        raise RuntimeError(f"CANDIDATE_C_INPUT_ROW_COUNT:{len(rows)}")
    for r in rows:
        r["signal_date"] = d(r.get("signal_date"))
        r["ticker"] = str(r.get("ticker", "")).zfill(4)
        r["tw_m1"] = f(r.get("tw_m1"))
        r["tw_m5"] = f(r.get("tw_m5"))
        if not r["signal_date"] or len(r["ticker"]) != 4:
            raise RuntimeError("CANDIDATE_C_BAD_IDENTITY")
        if not (r["tw_m1"] is not None and r["tw_m1"] < 0 and
                r["tw_m5"] is not None and r["tw_m5"] <= -0.02):
            raise RuntimeError("CANDIDATE_C_PREFILTER_DRIFT")
        for ex in EXITS:
            r[f"{ex}_exit_date"] = d(r.get(f"{ex}_exit_date"))
            r[f"{ex}_net_ret"] = f(r.get(f"{ex}_net_ret"))
    return rows


def load_sox():
    path = MACRO / "sox_daily_202212_202610.csv"
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            ds = d(r.get("date"))
            if ds:
                rows.append({"date": ds, "ret1": f(r.get("ret1")), "ret5": f(r.get("ret5"))})
    rows.sort(key=lambda x: x["date"])
    if len(rows) < 900:
        raise RuntimeError("CANDIDATE_C_SOX_TOO_SHORT")
    if any(rows[i]["date"] >= rows[i + 1]["date"] for i in range(len(rows) - 1)):
        raise RuntimeError("CANDIDATE_C_SOX_DATE_ORDER")
    return rows


def attach_sox(rows):
    sox = load_sox()
    for r in rows:
        prior = None
        for m in sox:
            if m["date"] >= r["signal_date"]:
                break
            prior = m
        if not prior:
            raise RuntimeError("CANDIDATE_C_SOX_PRIOR_MISSING")
        if not prior["date"] < r["signal_date"]:
            raise RuntimeError("CANDIDATE_C_SOX_FUTURE_LEAK")
        r["sox_session"] = prior["date"]
        r["sox1"] = prior["ret1"]
        r["sox5"] = prior["ret5"]
    return rows


def gate_ok(r, gate):
    checks = {
        "sox1": r.get("sox1") is not None and r["sox1"] <= 0.0,
        "sox5": r.get("sox5") is not None and r["sox5"] <= -0.03,
    }
    return all(checks[x] for x in GATES[gate])


def max_drawdown(nav_path):
    peak, mdd = 1.0, 0.0
    for n in nav_path:
        peak = max(peak, n)
        mdd = min(mdd, n / peak - 1.0)
    return mdd


def metrics(rets, nav_path):
    wins = sum(x > 0 for x in rets)
    gross_win = sum(x for x in rets if x > 0)
    gross_loss = -sum(x for x in rets if x < 0)
    return {
        "nav": nav_path[-1] if nav_path else 1.0,
        "return": (nav_path[-1] - 1.0) if nav_path else 0.0,
        "trades": len(rets),
        "wins": wins,
        "win_rate": wins / len(rets) if rets else None,
        "mean_trade": mean(rets) if rets else None,
        "median_trade": median(rets) if rets else None,
        "max_drawdown": max_drawdown(nav_path),
        "worst_trade": min(rets) if rets else None,
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else None,
    }


def simulate(rows, gate, exit_name, start, end):
    eligible = []
    for r in rows:
        sd = r["signal_date"]
        if not (start <= sd <= end) or not gate_ok(r, gate):
            continue
        ed = r.get(f"{exit_name}_exit_date")
        rr = r.get(f"{exit_name}_net_ret")
        if ed is None or rr is None or ed > end:
            continue
        eligible.append((sd, r["ticker"], ed, rr, r))
    eligible.sort(key=lambda x: (x[0], x[1]))
    nav = 1.0
    nav_path, trades = [], []
    blocked_exit = None
    for sd, ticker, ed, rr, r in eligible:
        if blocked_exit is not None and sd <= blocked_exit:
            continue
        nav *= 1.0 + rr
        nav_path.append(nav)
        blocked_exit = ed
        trades.append({
            "signal_date": sd.isoformat(),
            "ticker": ticker,
            "exit_date": ed.isoformat(),
            "net_ret": rr,
            "sox_session": r["sox_session"].isoformat(),
            "sox1": r["sox1"],
            "sox5": r["sox5"],
        })
    out = metrics([x["net_ret"] for x in trades], nav_path)
    out["events"] = trades
    return out


def yearly(rows, gate, exit_name):
    return {str(y): simulate(rows, gate, exit_name, date(y, 1, 1), date(y, 12, 31)) for y in (2023, 2024, 2025)}


def strictly_better(candidate, baseline):
    """Predeclared Candidate C gate: improve profit AND win rate; do not worsen MDD."""
    cw, bw = candidate["win_rate"], baseline["win_rate"]
    return bool(
        candidate["trades"] >= baseline["trades"]
        and cw is not None and bw is not None and cw > bw
        and candidate["nav"] > baseline["nav"]
        and candidate["max_drawdown"] >= baseline["max_drawdown"]
    )


def main():
    rows = attach_sox(load_payload())
    baseline = simulate(rows, BASELINE_GATE, BASELINE_EXIT, TRAIN_START, TRAIN_END)
    baseline_years = yearly(rows, BASELINE_GATE, BASELINE_EXIT)
    grid = []
    for gate in GATES:
        for ex in EXITS:
            train = simulate(rows, gate, ex, TRAIN_START, TRAIN_END)
            yy = yearly(rows, gate, ex)
            annual_robust = all(yy[str(y)]["trades"] >= 4 and yy[str(y)]["nav"] > 1.0 for y in (2023, 2024, 2025))
            dominates = strictly_better(train, baseline)
            grid.append({
                "gate": gate,
                "exit": ex,
                "train": {k: v for k, v in train.items() if k != "events"},
                "annual": {y: {k: v for k, v in m.items() if k != "events"} for y, m in yy.items()},
                "annual_robust": annual_robust,
                "strictly_dominates_same_mother_baseline": dominates,
                "worst_year_nav": min(yy[str(y)]["nav"] for y in (2023, 2024, 2025)),
            })
    if len(grid) != 40:
        raise RuntimeError(f"CANDIDATE_C_GRID_COUNT:{len(grid)}")

    eligible = [x for x in grid if x["annual_robust"] and x["strictly_dominates_same_mother_baseline"]]
    eligible.sort(key=lambda x: (
        x["worst_year_nav"],
        x["train"]["win_rate"],
        x["train"]["nav"],
        x["train"]["max_drawdown"],
        -EXITS.index(x["exit"]),
    ), reverse=True)
    winner = eligible[0] if eligible else None

    validation = None
    if winner:
        cand_val = simulate(rows, winner["gate"], winner["exit"], VAL_START, VAL_END)
        base_val = simulate(rows, BASELINE_GATE, BASELINE_EXIT, VAL_START, VAL_END)
        validation = {
            "candidate": cand_val,
            "same_mother_baseline": base_val,
            "candidate_strictly_dominates_baseline": strictly_better(cand_val, base_val),
            "label": "LOCKED_REPORT_ONLY_NON_PRISTINE_2026_ALREADY_OBSERVED",
        }

    result = {
        "schema_version": 1,
        "system": "HENGCE",
        "engine": "E2_PROFIT_MAX_CANDIDATE_C",
        "status": "DISCOVERY_DOMINATING_CANDIDATE_FOUND" if winner else "DISCOVERY_NO_DOMINATING_CANDIDATE",
        "authority": "RESEARCH_ONLY_ZERO_CAPITAL_AUTHORITY",
        "capital_authority_twd": 0,
        "production_mutation": False,
        "q017_mutated": False,
        "candidate_b_mutated": False,
        "search_space": {
            "count": 40,
            "gates": list(GATES),
            "exits": EXITS,
            "dxy": "EXCLUDED",
            "signal_core": "FROZEN_rev1_no_teacher_K25_Top1",
            "local_gate": "FROZEN_tw_m1<0_and_tw_m5<=-0.02",
            "sox_thresholds": "FROZEN_sox1<=0_and_sox5<=-0.03_when_used",
            "threshold_optimization": False,
            "signal_formula_optimization": False,
            "topn_optimization": False,
            "roundtrip_cost": 0.008,
            "overlap": "FORBIDDEN",
        },
        "selection_period": "2023-01-01..2025-12-31",
        "selection_rule": {
            "annual_robust": "each 2023/2024/2025 has >=4 completed trades and NAV>1",
            "strict_dominance": "same-mother train trades>=baseline AND NAV>baseline AND win_rate>baseline AND max_drawdown>=baseline",
            "tie_break": "max worst-year NAV, then win rate, NAV, drawdown; deterministic exit order",
        },
        "same_mother_baseline": {
            "gate": BASELINE_GATE,
            "exit": BASELINE_EXIT,
            "train": {k: v for k, v in baseline.items() if k != "events"},
            "annual": {y: {k: v for k, v in m.items() if k != "events"} for y, m in baseline_years.items()},
        },
        "eligible_count": len(eligible),
        "winner": winner,
        "validation_period": "2026-01-01..2026-10-16",
        "validation": validation,
        "research_limitations": [
            "Round-2 discovery mother is reused; this is not a pristine new discovery dataset.",
            "2026 was observed in prior research; validation is locked reporting only, not pristine OOS.",
            "Any winner must be replayed once on exact official PIT membership before further review.",
            "No tuning is permitted after exact PIT replay failure; a failure kills Candidate C v1.",
            "Future untouched forward evidence is required before any promotion discussion.",
        ],
        "promotion": "FORBIDDEN_BY_THIS_ARTIFACT",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "candidate_c_result.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "eligible_count": len(eligible),
        "baseline": result["same_mother_baseline"]["train"],
        "winner": winner,
        "validation": validation,
    }, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
