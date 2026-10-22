#!/usr/bin/env python3
"""Actual HENGCE E2 Phase-2 P2-A robustness diagnostics.

Research only. Uses the already-exposed Round-2 payload and frozen Candidate B.
Does not create/accept a challenger, open holdout, regenerate historical signals,
or grant capital/broker/production authority.
"""
from __future__ import annotations

import importlib.util
import json
import math
from datetime import date
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research" / "phase2_e2_p2a" / "p2a_result.json"

# Load governance gate first.
from research.phase2_governance import governance as gov

POLICY = gov.metadata(ROOT / "research/phase2_governance/phase2-policy.json")
STAGE = "P2A_BASELINE_DESTRUCTION"

def permit(op: str, cost_multiplier=None):
    return gov.require_phase2_run(POLICY, engine="E2", stage=STAGE,
                                  operation=op, cost_multiplier=cost_multiplier)

# Reuse the historical finite-search loader/simulator byte-for-byte rather than
# reimplementing signal reconstruction.
R2_PATH = ROOT / "research/e2_profit_max/round2/run_round2_finite.py"
spec = importlib.util.spec_from_file_location("hengce_round2", R2_PATH)
r2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r2)

BASELINE_COST = 0.008
BASELINE_GATE = "TW_SOX1_SOX5"  # SOX1 + SOX5; DXY excluded in frozen Candidate B.
BASELINE_EXIT = "fixed20"
TRAIN_START = date(2023, 1, 1)
TRAIN_END = date(2025, 12, 31)
VAL_START = date(2026, 1, 1)
VAL_END = date(2026, 10, 16)


def path_metrics(events, extra_cost=0.0):
    nav = 1.0
    peak = 1.0
    mdd = 0.0
    adjusted = []
    for e in sorted(events, key=lambda x: (x["signal_date"], x["ticker"])):
        rr = float(e["net_ret"]) - extra_cost
        if rr <= -1.0:
            raise RuntimeError("INVALID_ADJUSTED_RETURN")
        nav *= 1.0 + rr
        peak = max(peak, nav)
        mdd = min(mdd, nav / peak - 1.0)
        adjusted.append(rr)
    return {
        "nav": nav,
        "return": nav - 1.0,
        "trades": len(adjusted),
        "wins": sum(x > 0 for x in adjusted),
        "win_rate": sum(x > 0 for x in adjusted) / len(adjusted) if adjusted else None,
        "mean_trade": mean(adjusted) if adjusted else None,
        "median_trade": median(adjusted) if adjusted else None,
        "max_drawdown": mdd,
    }


def clean_event(e, row_lookup):
    z = dict(e)
    key = (e["signal_date"], e["ticker"])
    src = row_lookup.get(key, {})
    z["tw_m1"] = src.get("tw_m1")
    z["tw_m5"] = src.get("tw_m5")
    for k in ("signal_date", "exit_date", "sox_session", "dxy_session"):
        if z.get(k) is not None:
            z[k] = z[k].isoformat()
    return z


def group_metrics(events, keyfunc):
    groups = {}
    for e in events:
        groups.setdefault(str(keyfunc(e)), []).append(e)
    return {k: path_metrics(v) for k, v in sorted(groups.items())}


def main():
    permit("BASELINE_REPLAY")
    rows = r2.attach_macro(r2.load_payload())
    row_lookup = {(x["signal_date"], x["ticker"]): x for x in rows}

    baseline = r2.simulate(rows, BASELINE_GATE, BASELINE_EXIT, TRAIN_START, TRAIN_END)
    # Exact frozen Candidate B reproduction is a hard prerequisite.
    if baseline["trades"] != 13 or not math.isclose(baseline["nav"], 1.530103542875737, rel_tol=0, abs_tol=1e-12):
        raise RuntimeError(f"FROZEN_BASELINE_REPLAY_MISMATCH:{baseline['trades']}:{baseline['nav']}")
    events = baseline["events"]

    # Cost stress is exact because Round-2 source explicitly embeds 0.008 in each
    # net return; stress only subtracts the incremental aggregate cost.
    cost_stress = {}
    for mult in (1.0, 1.5, 2.0):
        permit("COST_STRESS", mult)
        target = BASELINE_COST * mult
        cost_stress[str(mult)] = {
            "aggregate_roundtrip_cost": target,
            **path_metrics(events, extra_cost=target - BASELINE_COST),
        }

    # Leave-best-trades-out: remove realized best return(s) with NO BACKFILL of
    # previously blocked overlapping candidates. This deliberately tests reliance
    # on exceptional winners rather than constructing a new strategy.
    permit("LEAVE_BEST_TRADES_OUT")
    ranked = sorted(events, key=lambda e: float(e["net_ret"]), reverse=True)
    leave_best = {}
    for n in (1, 2):
        removed = ranked[:n]
        removed_ids = {(x["signal_date"], x["ticker"]) for x in removed}
        kept = [x for x in events if (x["signal_date"], x["ticker"]) not in removed_ids]
        leave_best[f"drop_top_{n}"] = {
            **path_metrics(kept),
            "removed": [clean_event(x, row_lookup) for x in removed],
            "no_backfill": True,
        }

    permit("LEAVE_ONE_YEAR_OUT")
    leave_year = {}
    for y in (2023, 2024, 2025):
        kept = [e for e in events if e["signal_date"].year != y]
        leave_year[str(y)] = path_metrics(kept)

    permit("REGIME_CHARACTERIZATION")
    sox5_median = median([float(e["sox5"]) for e in events if e.get("sox5") is not None])
    # Descriptive only: median split is reported, never used to select a candidate.
    regime = {
        "by_signal_year": group_metrics(events, lambda e: e["signal_date"].year),
        "sox5_descriptive_median": sox5_median,
        "sox5_descriptive_median_split": group_metrics(
            events,
            lambda e: "MORE_NEGATIVE" if float(e["sox5"]) <= sox5_median else "LESS_NEGATIVE",
        ),
        "warning": "DESCRIPTIVE_ONLY_NOT_A_SELECTION_GATE",
    }

    # The exposed payload is already core=rev1_no_teacher_K25_Top1. It lacks the
    # preselection cross-section required to causally re-rank K/beta alternatives.
    # The authorization explicitly forbids historical signal regeneration, so we
    # fail closed instead of fabricating parameter-perturbation evidence.
    permit("PARAMETER_PERTURBATION_ROBUSTNESS")
    perturbation = {
        "status": "NOT_RUN_FAIL_CLOSED",
        "reason": "FROZEN_ROUND2_PAYLOAD_IS_ALREADY_K25_TOP1_AND_DOES_NOT_CONTAIN_PRESELECTION_CROSS_SECTION; HISTORICAL_SIGNAL_REGENERATION_FORBIDDEN",
    }

    validation_2026 = r2.simulate(rows, BASELINE_GATE, BASELINE_EXIT, VAL_START, VAL_END)

    result = {
        "schema_version": 1,
        "system": "HENGCE",
        "engine": "E2_PROFIT_MAX",
        "phase": "P2A_BASELINE_DESTRUCTION",
        "authorization_id": gov.AUTHORIZATION_ID,
        "status": "COMPLETED_WITH_PARAMETER_PERTURBATION_BLOCKED_BY_DATA_BOUNDARY",
        "source": {
            "payload": "research/e2_profit_max/round2/input_shock/payload.json.gz.b64",
            "loader": "research/e2_profit_max/round2/run_round2_finite.py",
            "baseline_gate": BASELINE_GATE,
            "baseline_exit": BASELINE_EXIT,
            "baseline_cost": BASELINE_COST,
            "historical_signal_regeneration": False,
        },
        "baseline_2023_2025": {k:v for k,v in baseline.items() if k != "events"},
        "baseline_events": [clean_event(e, row_lookup) for e in events],
        "cost_stress": cost_stress,
        "leave_best_trades_out": leave_best,
        "leave_one_year_out": leave_year,
        "regime_characterization": regime,
        "parameter_perturbation": perturbation,
        "exposed_2026_validation_completed_only": {k:v for k,v in validation_2026.items() if k != "events"},
        "diagnostic_variant_count": 1 + 3 + 2 + 3 + 2,
        "candidate_creation_authorized": False,
        "candidate_acceptance_authorized": False,
        "prospective_holdout_access": False,
        "capital_authority_twd": 0,
        "broker_order_execution": False,
        "PROMOTE_TO_PRODUCTION": "FORBIDDEN",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str))


if __name__ == "__main__":
    main()
