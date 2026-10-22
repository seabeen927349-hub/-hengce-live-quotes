#!/usr/bin/env python3
"""Actual HENGCE E2 Phase-2 P2-A robustness diagnostics.

Research only. Uses the already-exposed Round-2 payload and frozen Candidate B.
Does not create/accept a challenger, open holdout, regenerate historical signals,
or grant capital/broker/production authority.
"""
from __future__ import annotations

import base64
import binascii
import gzip
import hashlib
import importlib.util
import json
import math
import struct
import sys
import zlib
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


def _gzip_raw_offset(blob: bytes) -> int:
    if len(blob) < 18 or blob[:2] != b"\x1f\x8b" or blob[2] != 8:
        raise RuntimeError("ROUND2_GZIP_HEADER_INVALID")
    flg = blob[3]
    pos = 10
    if flg & 4:
        if pos + 2 > len(blob):
            raise RuntimeError("ROUND2_GZIP_FEXTRA_TRUNCATED")
        xlen = struct.unpack("<H", blob[pos:pos+2])[0]
        pos += 2 + xlen
    for bit in (8, 16):
        if flg & bit:
            end = blob.find(b"\x00", pos)
            if end < 0:
                raise RuntimeError("ROUND2_GZIP_HEADER_STRING_TRUNCATED")
            pos = end + 1
    if flg & 2:
        pos += 2
    if pos >= len(blob) - 8:
        raise RuntimeError("ROUND2_GZIP_HEADER_OVERRUN")
    return pos


def load_payload_with_integrity_recovery():
    """Load exact existing shock chunks.

    Normal gzip path is preferred. If only the stored gzip trailer CRC/ISIZE is
    invalid, recover the deflate stream without trusting that trailer, then force
    schema/core/pre-gate/row-count/prefilter checks and an exact frozen baseline
    replay before any diagnostic result is accepted.
    """
    chunks = sorted(r2.INPUT.glob("r2shock_*.txt"))
    if len(chunks) != 3:
        raise RuntimeError(f"ROUND2_INPUT_CHUNK_COUNT:{len(chunks)}")
    b64_text = "".join(p.read_text(encoding="utf-8").strip() for p in chunks)
    compressed = base64.b64decode(b64_text, validate=True)
    recovery = {
        "chunk_count": len(chunks),
        "base64_sha256": hashlib.sha256(b64_text.encode()).hexdigest(),
        "compressed_sha256": hashlib.sha256(compressed).hexdigest(),
        "gzip_crc_status": "VALID",
    }
    try:
        raw = gzip.decompress(compressed)
    except gzip.BadGzipFile as exc:
        if "CRC check failed" not in str(exc) and "Incorrect length" not in str(exc):
            raise
        start = _gzip_raw_offset(compressed)
        objz = zlib.decompressobj(-zlib.MAX_WBITS)
        raw = objz.decompress(compressed[start:]) + objz.flush()
        if not objz.eof or len(objz.unused_data) < 8:
            raise RuntimeError("ROUND2_RAW_DEFLATE_RECOVERY_INCOMPLETE")
        trailer = objz.unused_data[:8]
        stored_crc, stored_isize = struct.unpack("<II", trailer)
        actual_crc = binascii.crc32(raw) & 0xffffffff
        actual_isize = len(raw) & 0xffffffff
        recovery.update({
            "gzip_crc_status": "TRAILER_MISMATCH_RECOVERED_SEMANTIC_VALIDATION_REQUIRED",
            "stored_crc32": f"{stored_crc:08x}",
            "actual_crc32": f"{actual_crc:08x}",
            "stored_isize": stored_isize,
            "actual_isize": actual_isize,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        })
    obj = json.loads(raw)
    if obj.get("schema") != 1 or obj.get("core") != "rev1_no_teacher_K25_Top1":
        raise RuntimeError("ROUND2_INPUT_CORE_MISMATCH")
    if obj.get("pre_gate") != "TW_SHOCK_m1_lt_0_m5_lte_-0.02":
        raise RuntimeError("ROUND2_INPUT_GATE_MISMATCH")
    cols = obj["c"]
    rows = [dict(zip(cols, x)) for x in obj["r"]]
    if len(rows) != 152:
        raise RuntimeError(f"ROUND2_INPUT_ROW_COUNT:{len(rows)}")
    for row in rows:
        row["signal_date"] = r2.d(row["signal_date"])
        row["ticker"] = str(row["ticker"]).zfill(4)
        row["tw_m1"] = r2.f(row["tw_m1"])
        row["tw_m5"] = r2.f(row["tw_m5"])
        if not (row["tw_m1"] is not None and row["tw_m1"] < 0 and
                row["tw_m5"] is not None and row["tw_m5"] <= -0.02):
            raise RuntimeError("ROUND2_PREFILTER_DRIFT")
        for ex in r2.EXITS:
            row[f"{ex}_exit_date"] = r2.d(row.get(f"{ex}_exit_date"))
            row[f"{ex}_net_ret"] = r2.f(row.get(f"{ex}_net_ret"))
    recovery["schema"] = obj["schema"]
    recovery["core"] = obj["core"]
    recovery["pre_gate"] = obj["pre_gate"]
    recovery["row_count"] = len(rows)
    return rows, recovery


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
    raw_rows, payload_integrity = load_payload_with_integrity_recovery()
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
        kept = [e for e in events if e["signal_date"].year != y]
        leave_year[str(y)] = path_metrics(kept)

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
        "evidence_class": "DIAGNOSTIC_COMPUTATION_EVIDENCE_NOT_CANDIDATE_ACCEPTANCE",
        "payload_integrity": payload_integrity,
        "source": {
            "payload_chunks": "research/e2_profit_max/round2/input_shock/r2shock_01..03.txt",
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
