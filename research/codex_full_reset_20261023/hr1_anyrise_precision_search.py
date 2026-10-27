#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import json
import math
import statistics
from pathlib import Path

# Reuse the frozen point-in-time TWSE electronics feature/data stack.
# Suppress the imported module's historical report printout; no parameters are changed.
with contextlib.redirect_stdout(io.StringIO()):
    import research.codex_full_reset_20261023.ranking_v13_weak_regime_profiles as v13

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research/codex_full_reset_20261023/HR1_ANYRISE_PRECISION_RESULT_20261025.json"
EVENTS = ROOT / "research/codex_full_reset_20261023/hr1_anyrise_champion_events.jsonl"

TRAIN_START, TRAIN_END = "2024-01-01", "2025-12-31"
HOLDOUT_START, HOLDOUT_END = "2026-01-01", "2026-10-22"
MIN_TRAIN_TRADES = 30
MIN_HIGH_COVERAGE_TRAIN_TRADES = 80
COST_DIAGNOSTIC = 0.012

# Finite, predeclared family. No learned weights and no post-hoc new feature construction.
SCORE_FAMILIES = {
    "V6_COMPOSITE": (0.20, 0.25, 0.30, 0.05, 0.20),
    "EQUAL_5F": (0.20, 0.20, 0.20, 0.20, 0.20),
    "MOM_LOWVOL": (0.00, 0.50, 0.00, 0.00, 0.50),
    "TREND_BLEND": (0.00, 0.40, 0.60, 0.00, 0.00),
    "RESID_REV_ONLY": (1.00, 0.00, 0.00, 0.00, 0.00),
    "MOM20_ONLY": (0.00, 1.00, 0.00, 0.00, 0.00),
    "SKIP5_60_ONLY": (0.00, 0.00, 1.00, 0.00, 0.00),
    "LOWVOL_ONLY": (0.00, 0.00, 0.00, 0.00, 1.00),
}
MAX_HOLDS = (1, 3, 5, 10, 20, 40, 60, 90, 120, 180)
SCORE_MINS = (0.75, 0.85, 0.90, 0.95)
GAP_MINS = (0.00, 0.02, 0.05)
BREADTH_GATES = (
    "ALL",
    "STRONG_GE_050",
    "VERY_STRONG_GE_060",
    "EXTREME_STRONG_GE_070",
    "WEAK_LT_050",
    "VERY_WEAK_LT_040",
)

DATES = v13.dates
DI = {d: i for i, d in enumerate(DATES)}


def breadth_ok(name: str, b: float) -> bool:
    if name == "ALL":
        return True
    if name == "STRONG_GE_050":
        return b >= 0.50
    if name == "VERY_STRONG_GE_060":
        return b >= 0.60
    if name == "EXTREME_STRONG_GE_070":
        return b >= 0.70
    if name == "WEAK_LT_050":
        return b < 0.50
    if name == "VERY_WEAK_LT_040":
        return b < 0.40
    raise KeyError(name)


def wilson_lower(wins: int, n: int, z: float = 1.959963984540054) -> float | None:
    if n <= 0:
        return None
    p = wins / n
    den = 1.0 + z * z / n
    center = p + z * z / (2.0 * n)
    adj = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))
    return (center - adj) / den


def product(xs):
    n = 1.0
    for x in xs:
        n *= 1.0 + x
    return n - 1.0


# Precompute each fixed ranker's top-1 name, score and top1-top2 separation on every signal date.
SIGNALS: dict[str, dict[str, dict]] = {k: {} for k in SCORE_FAMILIES}
for d, F in v13.features.items():
    if d not in v13.breadth:
        continue
    for family, w in SCORE_FAMILIES.items():
        arr = []
        for t, vals in F.items():
            s = sum(w[k] * vals[k] for k in range(5))
            arr.append((s, t))
        arr.sort(key=lambda z: (-z[0], z[1]))
        if len(arr) < 2:
            continue
        SIGNALS[family][d] = {
            "ticker": arr[0][1],
            "score": arr[0][0],
            "gap": arr[0][0] - arr[1][0],
            "breadth20": v13.breadth[d],
        }


def path_outcome(signal_i: int, ticker: str, max_hold: int, end: str):
    """Enter next trading-day open. Earliest exit is one trading day later at close.
    Win = first close strictly above entry open. If never positive, force exit at max_hold close.
    This deliberately optimizes gross direction only; costs are reported separately.
    """
    ei = signal_i + 1
    xi = ei + max_hold
    if ei >= len(DATES) or xi >= len(DATES):
        return None
    if DATES[ei] > end or DATES[xi] > end:
        return None
    er = v13.by[DATES[ei]].get(ticker)
    if er is None or er.o is None or er.o <= 0:
        return None
    entry = er.o
    for j in range(ei + 1, xi + 1):
        r = v13.by[DATES[j]].get(ticker)
        if r is None or r.c is None or r.c <= 0 or r.bad:
            return None
        ret = r.c / entry - 1.0
        if ret > 0.0:
            return {
                "win": True,
                "entry_index": ei,
                "exit_index": j,
                "entry_date": DATES[ei],
                "exit_date": DATES[j],
                "entry_open": entry,
                "exit_close": r.c,
                "gross_return": ret,
                "hold_trading_days": j - ei,
            }
    r = v13.by[DATES[xi]].get(ticker)
    if r is None or r.c is None or r.c <= 0 or r.bad:
        return None
    ret = r.c / entry - 1.0
    return {
        "win": ret > 0.0,
        "entry_index": ei,
        "exit_index": xi,
        "entry_date": DATES[ei],
        "exit_date": DATES[xi],
        "entry_open": entry,
        "exit_close": r.c,
        "gross_return": ret,
        "hold_trading_days": max_hold,
    }


def simulate(params: dict, start: str, end: str, include_events: bool = False):
    family = params["score_family"]
    max_hold = params["max_hold"]
    score_min = params["score_min"]
    gap_min = params["gap_min"]
    breadth_gate = params["breadth_gate"]
    events = []
    next_free_signal_i = -1
    invalid = 0
    eligible_signals = 0

    for i, d in enumerate(DATES):
        if d < start or d > end or i < next_free_signal_i:
            continue
        s = SIGNALS[family].get(d)
        if s is None:
            continue
        if s["score"] < score_min or s["gap"] < gap_min or not breadth_ok(breadth_gate, s["breadth20"]):
            continue
        eligible_signals += 1
        o = path_outcome(i, s["ticker"], max_hold, end)
        if o is None:
            invalid += 1
            continue
        e = {
            "signal_date": d,
            "ticker": s["ticker"],
            "score": s["score"],
            "gap": s["gap"],
            "breadth20": s["breadth20"],
            **o,
        }
        events.append(e)
        # At an exit close, that same date's close can generate the next signal for next-day entry.
        next_free_signal_i = o["exit_index"]

    wins = sum(1 for e in events if e["win"])
    n = len(events)
    returns = [e["gross_return"] for e in events]
    holds = [e["hold_trading_days"] for e in events]
    cost_wins = sum(1 for x in returns if x > COST_DIAGNOSTIC)
    metrics = {
        "trades": n,
        "wins": wins,
        "losses": n - wins,
        "win_rate": wins / n if n else None,
        "wilson95_lower": wilson_lower(wins, n),
        "eligible_signals": eligible_signals,
        "invalid_paths": invalid,
        "mean_gross_return": statistics.mean(returns) if returns else None,
        "median_gross_return": statistics.median(returns) if returns else None,
        "worst_gross_return": min(returns) if returns else None,
        "best_gross_return": max(returns) if returns else None,
        "compounded_gross_return": product(returns) if returns else None,
        "after_1p2pct_cost_positive_rate": cost_wins / n if n else None,
        "mean_hold_trading_days": statistics.mean(holds) if holds else None,
        "median_hold_trading_days": statistics.median(holds) if holds else None,
        "max_observed_hold_trading_days": max(holds) if holds else None,
    }
    if include_events:
        metrics["events"] = events
    return metrics


def candidate_key(x: dict):
    m = x["train"]
    # User objective: maximize directional win rate. Sample strength is only the tie-breaker.
    return (
        m["win_rate"],
        m["wilson95_lower"],
        m["trades"],
        -m["mean_hold_trading_days"],
        -x["params"]["max_hold"],
    )


candidates = []
for family in SCORE_FAMILIES:
    for hold in MAX_HOLDS:
        for score_min in SCORE_MINS:
            for gap_min in GAP_MINS:
                for bg in BREADTH_GATES:
                    params = {
                        "score_family": family,
                        "max_hold": hold,
                        "score_min": score_min,
                        "gap_min": gap_min,
                        "breadth_gate": bg,
                        "exit_rule": "first close > next-day entry open; otherwise max-hold close",
                    }
                    train = simulate(params, TRAIN_START, TRAIN_END)
                    if train["trades"] < MIN_TRAIN_TRADES:
                        continue
                    candidates.append({"params": params, "train": train})

if not candidates:
    raise RuntimeError("No HR1 candidate met the minimum training trade count")

candidates.sort(key=candidate_key, reverse=True)
champion = candidates[0]
champion_holdout = simulate(champion["params"], HOLDOUT_START, HOLDOUT_END, include_events=True)
champion["holdout_2026"] = {k: v for k, v in champion_holdout.items() if k != "events"}

high_cov_pool = [x for x in candidates if x["train"]["trades"] >= MIN_HIGH_COVERAGE_TRAIN_TRADES]
high_cov = sorted(high_cov_pool, key=candidate_key, reverse=True)[0] if high_cov_pool else None
if high_cov is not None:
    h = simulate(high_cov["params"], HOLDOUT_START, HOLDOUT_END)
    high_cov = {**high_cov, "holdout_2026": h}

# Locked champion event ledger across train+holdout for auditability.
all_champ_events = []
for label, s, e in (("TRAIN", TRAIN_START, TRAIN_END), ("HOLDOUT_2026", HOLDOUT_START, HOLDOUT_END)):
    mm = simulate(champion["params"], s, e, include_events=True)
    for ev in mm["events"]:
        ev["split"] = label
        all_champ_events.append(ev)
with EVENTS.open("w", encoding="utf-8") as fh:
    for ev in all_champ_events:
        fh.write(json.dumps(ev, ensure_ascii=False) + "\n")

# Prospective/live state reconstruction through the current data-as-of using the locked champion.
def live_state(params: dict):
    family = params["score_family"]
    max_hold = params["max_hold"]
    score_min = params["score_min"]
    gap_min = params["gap_min"]
    breadth_gate = params["breadth_gate"]
    start = HOLDOUT_START
    end = HOLDOUT_END
    next_free_signal_i = -1
    completed = []
    open_trade = None
    for i, d in enumerate(DATES):
        if d < start or d > end or i < next_free_signal_i:
            continue
        s = SIGNALS[family].get(d)
        if s is None or s["score"] < score_min or s["gap"] < gap_min or not breadth_ok(breadth_gate, s["breadth20"]):
            continue
        ei = i + 1
        if ei >= len(DATES) or DATES[ei] > end:
            break
        er = v13.by[DATES[ei]].get(s["ticker"])
        if er is None or er.o is None or er.o <= 0:
            continue
        entry = er.o
        forced_xi = ei + max_hold
        available_xi = min(forced_xi, DI[end])
        bad = False
        exited = False
        for j in range(ei + 1, available_xi + 1):
            r = v13.by[DATES[j]].get(s["ticker"])
            if r is None or r.c is None or r.c <= 0 or r.bad:
                bad = True
                break
            ret = r.c / entry - 1.0
            if ret > 0.0:
                completed.append({"signal_date": d, "ticker": s["ticker"], "entry_date": DATES[ei], "entry_open": entry, "exit_date": DATES[j], "exit_close": r.c, "gross_return": ret, "hold_trading_days": j - ei, "win": True})
                next_free_signal_i = j
                exited = True
                break
        if bad:
            continue
        if exited:
            continue
        if forced_xi <= DI[end]:
            r = v13.by[DATES[forced_xi]].get(s["ticker"])
            if r is None or r.c is None or r.c <= 0 or r.bad:
                continue
            ret = r.c / entry - 1.0
            completed.append({"signal_date": d, "ticker": s["ticker"], "entry_date": DATES[ei], "entry_open": entry, "exit_date": DATES[forced_xi], "exit_close": r.c, "gross_return": ret, "hold_trading_days": max_hold, "win": ret > 0.0})
            next_free_signal_i = forced_xi
            continue
        latest = v13.by[end].get(s["ticker"])
        open_trade = {
            "status": "OPEN",
            "signal_date": d,
            "ticker": s["ticker"],
            "entry_date": DATES[ei],
            "entry_open": entry,
            "data_asof": end,
            "latest_close": latest.c if latest is not None else None,
            "latest_gross_return": (latest.c / entry - 1.0) if latest is not None and latest.c is not None else None,
            "elapsed_trading_days": DI[end] - ei,
            "max_hold": max_hold,
        }
        break
    return {"completed_2026_trades": len(completed), "last_completed_trade": completed[-1] if completed else None, "open_trade": open_trade}

live = live_state(champion["params"])

res = {
    "status": "HR1_ANYRISE_PRECISION_SEARCH_COMPLETE",
    "objective": "maximize gross directional win rate only; any strictly positive close-vs-entry-open return counts as a win",
    "selection_protocol": {
        "training_selection_window": [TRAIN_START, TRAIN_END],
        "locked_evaluation_window": [HOLDOUT_START, HOLDOUT_END],
        "minimum_training_trades": MIN_TRAIN_TRADES,
        "candidate_count_meeting_min_trades": len(candidates),
        "score_families": SCORE_FAMILIES,
        "max_holds": MAX_HOLDS,
        "score_mins": SCORE_MINS,
        "gap_mins": GAP_MINS,
        "breadth_gates": BREADTH_GATES,
        "entry": "next trading-day open after signal",
        "exit": "first subsequent trading-day close strictly above entry open; otherwise forced close at max_hold",
        "non_overlapping_single_capital_schedule": True,
        "cost_not_in_objective": True,
        "cost_diagnostic": COST_DIAGNOSTIC,
    },
    "champion": champion,
    "high_coverage_champion": high_cov,
    "top10_training_candidates": candidates[:10],
    "live_state_through_2026_10_22": live,
    "events_file": str(EVENTS.relative_to(ROOT)),
    "authority": {
        "research_only": True,
        "capital_authority_twd": 0,
        "broker_order_execution": False,
        "production_promotion": False,
        "merge_authorized": False,
    },
    "caveat": "2026 is locked only within this HR1 search, but the broader project has previously exposed 2026 data. This is a historical diagnostic, not untouched future OOS. Maximizing hit rate can hide rare large losses and long capital lock-up; those diagnostics are reported but not optimized.",
}
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("HR1_RESULT=" + json.dumps(res, ensure_ascii=False, separators=(",", ":")))
