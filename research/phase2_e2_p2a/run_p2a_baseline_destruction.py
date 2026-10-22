#!/usr/bin/env python3
"""Actual HENGCE E2 Phase-2 P2-A robustness diagnostics.

Research only. Uses already-exposed Round-2 data and frozen Candidate B.
Does not create/accept a challenger, open holdout, regenerate historical signals,
or grant capital/broker/production authority.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import importlib.util
import json
import math
import sys
from datetime import date
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "research" / "phase2_e2_p2a" / "p2a_result.json"

from research.phase2_governance import governance as gov

POLICY = gov.metadata(ROOT / "research/phase2_governance/phase2-policy.json")
STAGE = "P2A_BASELINE_DESTRUCTION"


def permit(op: str, cost_multiplier=None):
    return gov.require_phase2_run(POLICY, engine="E2", stage=STAGE,
                                  operation=op, cost_multiplier=cost_multiplier)


R2_PATH = ROOT / "research/e2_profit_max/round2/run_round2_finite.py"
spec = importlib.util.spec_from_file_location("hengce_round2", R2_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("ROUND2_MODULE_LOAD_FAILED")
r2 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = r2
spec.loader.exec_module(r2)

BASELINE_COST = 0.008
BASELINE_GATE = "TW_SOX1_SOX5"
BASELINE_EXIT = "fixed20"
TRAIN_START = date(2023, 1, 1)
TRAIN_END = date(2025, 12, 31)
VAL_START = date(2026, 1, 1)
VAL_END = date(2026, 10, 16)


def decode_chunk_set(directory: Path, pattern: str, expected_chunks: int):
    chunks = sorted(directory.glob(pattern))
    if len(chunks) != expected_chunks:
        raise RuntimeError(f"ROUND2_CHUNK_COUNT:{pattern}:{len(chunks)}")
    b64_text = "".join(p.read_text(encoding="utf-8").strip() for p in chunks)
    compressed = base64.b64decode(b64_text, validate=True)
    raw = gzip.decompress(compressed)
    obj = json.loads(raw)
    return obj, {
        "path": str(directory.relative_to(ROOT)) + "/" + pattern,
        "chunk_count": len(chunks),
        "base64_sha256": hashlib.sha256(b64_text.encode()).hexdigest(),
        "compressed_sha256": hashlib.sha256(compressed).hexdigest(),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }


def normalize_rows(obj):
    if obj.get("schema") != 1 or obj.get("core") != "rev1_no_teacher_K25_Top1":
        raise RuntimeError("ROUND2_INPUT_CORE_MISMATCH")
    cols = obj.get("c")
    source_rows = obj.get("r")
    if not isinstance(cols, list) or not isinstance(source_rows, list):
        raise RuntimeError("ROUND2_INPUT_ROWS_MISSING")
    rows = [dict(zip(cols, x)) for x in source_rows]
    for row in rows:
        row["signal_date"] = r2.d(row["signal_date"])
        row["ticker"] = str(row["ticker"]).zfill(4)
        row["tw_m1"] = r2.f(row.get("tw_m1"))
        row["tw_m5"] = r2.f(row.get("tw_m5"))
        for ex in r2.EXITS:
            row[f"{ex}_exit_date"] = r2.d(row.get(f"{ex}_exit_date"))
            row[f"{ex}_net_ret"] = r2.f(row.get(f"{ex}_net_ret"))
    return rows


def load_round2_shock_rows():
    """Use stored shock payload if valid; otherwise rebuild from stored mother rows.

    The shock archive currently present on main is corrupted. Rebuilding from the
    already-exposed Round-2 mother payload is allowed because it only reapplies the
    frozen local gate to stored candidate rows; it does not regenerate a signal,
    score, rank, universe, or historical market observation.
    """
    shock_dir = ROOT / "research/e2_profit_max/round2/input_shock"
    mother_dir = ROOT / "research/e2_profit_max/round2/input"
    integrity = {"shock_archive_status": "UNKNOWN"}
    try:
        obj, meta = decode_chunk_set(shock_dir, "r2shock_*.txt", 3)
        rows = normalize_rows(obj)
        if obj.get("pre_gate") != "TW_SHOCK_m1_lt_0_m5_lte_-0.02" or len(rows) != 152:
            raise RuntimeError("ROUND2_SHOCK_ARCHIVE_SEMANTIC_MISMATCH")
        integrity.update(meta)
        integrity["shock_archive_status"] = "VALID_DIRECT"
    except Exception as exc:
        integrity["shock_archive_status"] = "CORRUPT_FAIL_CLOSED_REBUILT_FROM_STORED_MOTHER"
        integrity["shock_archive_error"] = f"{type(exc).__name__}:{exc}"
        obj, meta = decode_chunk_set(mother_dir, "r2seg_*.txt", 8)
        mother = normalize_rows(obj)
        rows = [x for x in mother if x["tw_m1"] is not None and x["tw_m1"] < 0 and
                x["tw_m5"] is not None and x["tw_m5"] <= -0.02]
        integrity["mother"] = meta
        integrity["mother_schema"] = obj.get("schema")
        integrity["mother_core"] = obj.get("core")
        integrity["mother_row_count"] = len(mother)
        integrity["reapplied_frozen_local_gate"] = "tw_m1<0 and tw_m5<=-0.02"
        integrity["historical_signal_regeneration"] = False
    if len(rows) != 152:
        raise RuntimeError(f"ROUND2_REBUILT_SHOCK_ROW_COUNT:{len(rows)}")
    if any(not (x["tw_m1"] < 0 and x["tw_m5"] <= -0.02) for x in rows):
        raise RuntimeError("ROUND2_PREFILTER_DRIFT")
    integrity["shock_row_count"] = len(rows)
    return rows, integrity


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
    src = row_lookup.get((e["signal_date"], e["ticker"]), {})
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
    raw_rows, payload_integrity = load_round2_shock_rows()
    rows = r2.attach_macro(raw_rows)
    row_lookup = {(x["signal_date"], x["ticker"]): x for x in rows}

    baseline = r2.simulate(rows, BASELINE_GATE, BASELINE_EXIT, TRAIN_START, TRAIN_END)
    if baseline["trades"] != 13 or not math.isclose(baseline["nav"], 1.530103542875737, rel_tol=0, abs_tol=1e-12):
        raise RuntimeError(f"FROZEN_BASELINE_REPLAY_MISMATCH:{baseline['trades']}:{baseline['nav']}")
    payload_integrity["frozen_baseline_replay"] = "EXACT_MATCH_13_TRADES_NAV_1.530103542875737"
    events = baseline["events"]

    cost_stress = {}
    for mult in (1.0, 1.5, 2.0):
        permit("COST_STRESS", mult)
        target = BASELINE_COST * mult
        cost_stress[str(mult)] = {
            "aggregate_roundtrip_cost": target,
            **path_metrics(events, extra_cost=target - BASELINE_COST),
        }

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
        leave_year[str(y)] = path_metrics([e for e in events if e["signal_date"].year != y])

    permit("REGIME_CHARACTERIZATION")
    sox5_median = median([float(e["sox5"]) for e in events if e.get("sox5") is not None])
    regime = {
        "by_signal_year": group_metrics(events, lambda e: e["signal_date"].year),
        "sox5_descriptive_median": sox5_median,
        "sox5_descriptive_median_split": group_metrics(
            events,
            lambda e: "MORE_NEGATIVE" if float(e["sox5"]) <= sox5_median else "LESS_NEGATIVE",
        ),
        "warning": "DESCRIPTIVE_ONLY_NOT_A_SELECTION_GATE",
    }

    permit("PARAMETER_PERTURBATION_ROBUSTNESS")
    perturbation = {
        "status": "NOT_RUN_FAIL_CLOSED",
        "reason": "STORED_ROUND2_ROWS_ARE_ALREADY_K25_TOP1_AND_LACK_PRESELECTION_CROSS_SECTION; HISTORICAL_SIGNAL_REGENERATION_FORBIDDEN",
    }

    validation_2026 = r2.simulate(rows, BASELINE_GATE, BASELINE_EXIT, VAL_START, VAL_END)
    result = {
        "schema_version": 1,
        "system": "HENGCE",
        "engine": "E2_PROFIT_MAX",
        "phase": "P2A_BASELINE_DESTRUCTION",
        "authorization_id": gov.AUTHORIZATION_ID,
        "status": "COMPLETED_WITH_PARAMETER_PERTURBATION_BLOCKED_BY_DATA_BOUNDARY",
        "evidence_class": "DIAGNOSTIC_COMPUTATION_EVIDENCE_NOT_CANDIDATE_ACCEPTANCE",
        "payload_integrity": payload_integrity,
        "source": {
            "preferred_shock_payload": "research/e2_profit_max/round2/input_shock/r2shock_01..03.txt",
            "fallback_mother_payload": "research/e2_profit_max/round2/input/r2seg_01..08.txt",
            "loader_reference": "research/e2_profit_max/round2/run_round2_finite.py",
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
        "diagnostic_variant_count": 11,
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
