#!/usr/bin/env python3
"""Fail-closed validator for HENGCE Loss Forensics prospective OOS governance.

This validator protects the bounded OOS judgment contract. It does not evaluate
market performance and cannot create production/trading authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RF = ROOT / "research" / "loss_forensics"

PREREG = RF / "LOSS_FORENSICS_PROSPECTIVE_OOS_EVALUATION_PREREGISTRATION_20261101.md"
PROTOCOL = RF / "PROSPECTIVE_ACTUAL_AVAILABILITY_PROTOCOL_20261101.md"
LOCK = RF / "LOSS_FORENSICS_OOS_GOVERNANCE_LOCK_20261101.json"
ARM = RF / "LOSS_FORENSICS_OOS_CANDIDATE_ARM_CARD_20261101.json"
STATE = RF / "CURRENT_STATE_LOSS_FORENSICS_OOS_JUDGE_20261101.json"

EXPECTED = {
    "parent_authority_commit": "42171697203b617dc21fe40e791485516750d28f",
    "protocol_blob_sha1": "4d2c5de6582a70a694dc9337fdcbd21a0e25f51a",
    "prereg_blob_sha1": "a59902e2058a95af6a917fbfdc5fa36f9317a77c",
    "minimum_valid_formal_trading_days": 60,
    "maximum_collection_trading_days_if_event_scarcity": 90,
    "minimum_valid_events": 120,
    "minimum_distinct_event_dates": 24,
    "minimum_distinct_symbols": 30,
    "maximum_single_event_date_share": 0.20,
    "maximum_single_symbol_share": 0.10,
    "minimum_valid_day_integrity_share": 0.80,
    "outcome_horizons_trading_days": [1, 5, 20],
    "chronological_blocks": 4,
    "minimum_blocks_with_expected_sign": 3,
    "confidence_level": 0.95,
}

LEGAL_STATES = {
    "PREARMED_DATA_COLLECTING",
    "COLLECTING",
    "DATA_QUALITY_FAIL",
    "INSUFFICIENT_EVENTS",
    "OOS_INCONCLUSIVE_LOW_EVENT_RATE",
    "OOS_FAIL",
    "OOS_MIXED",
    "OOS_PASS_CANDIDATE",
    "VALIDATED",
}

REJECTED_FAMILIES = {
    "CORE_LOOSENING",
    "BRIDGE/DESTINATION_PRELOAD",
    "PROFESSIONAL_FLOW",
}


def die(msg: str) -> None:
    raise SystemExit("HENGCE_OOS_GOVERNANCE_FAIL_CLOSED: " + msg)


def load_json(path: Path) -> dict:
    if not path.exists():
        die(f"missing required artifact: {path.relative_to(ROOT)}")
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        die(f"invalid JSON {path.name}: {exc!r}")
    if not isinstance(obj, dict):
        die(f"top-level JSON must be object: {path.name}")
    return obj


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def require(cond: bool, msg: str) -> None:
    if not cond:
        die(msg)


def nonnull(x) -> bool:
    return x is not None and x != "" and x != [] and x != {}


def main() -> int:
    for p in (PREREG, PROTOCOL, LOCK, ARM, STATE):
        require(p.exists(), f"required file absent: {p.relative_to(ROOT)}")

    lock = load_json(LOCK)
    arm = load_json(ARM)
    state = load_json(STATE)

    # 1. Bind the two prose authorities by Git blob identity.
    require(git_blob_sha1(PROTOCOL) == EXPECTED["protocol_blob_sha1"], "prospective protocol blob changed")
    require(git_blob_sha1(PREREG) == EXPECTED["prereg_blob_sha1"], "OOS preregistration blob changed")
    chain = lock.get("authority_chain", {})
    require(chain.get("prospective_protocol_blob_sha1") == EXPECTED["protocol_blob_sha1"], "lock protocol hash mismatch")
    require(chain.get("evaluation_preregistration_blob_sha1") == EXPECTED["prereg_blob_sha1"], "lock prereg hash mismatch")
    require(lock.get("parent_authority_commit") == EXPECTED["parent_authority_commit"], "parent authority commit changed")
    require(chain.get("supersedes_pass3_pass4") is False, "Pass 3/4 supersedence forbidden")
    require(chain.get("may_reopen_historical_latency") is False, "historical latency reopen forbidden")
    require(chain.get("may_reconstruct_missing_pass4_interpreter") is False, "Pass 4 approximate reconstruction forbidden")

    # 2. Hard-bind evaluation constants. Changing these requires a new preregistration/cohort.
    c = lock.get("frozen_evaluation_constants", {})
    for key in (
        "minimum_valid_formal_trading_days",
        "maximum_collection_trading_days_if_event_scarcity",
        "minimum_valid_events",
        "minimum_distinct_event_dates",
        "minimum_distinct_symbols",
        "maximum_single_event_date_share",
        "maximum_single_symbol_share",
        "minimum_valid_day_integrity_share",
        "outcome_horizons_trading_days",
        "chronological_blocks",
        "minimum_blocks_with_expected_sign",
        "confidence_level",
    ):
        require(c.get(key) == EXPECTED[key], f"frozen constant changed: {key}")
    require(c.get("optional_stopping_on_performance_forbidden") is True, "optional stopping guard disabled")
    require(c.get("day60_extension_reason_allowed") == "EVENT_DIVERSITY_GATES_ONLY", "extension rule changed")

    # 3. Authority must remain research-only.
    for obj_name, obj in (("lock", lock), ("arm", arm), ("state", state)):
        auth = obj.get("authority") if obj_name != "state" else obj.get("frozen_authority")
        require(isinstance(auth, dict), f"{obj_name} authority missing")
        require(auth.get("production_authority") == "NONE", f"{obj_name} production authority escalated")
        require(auth.get("trading_authority") == "NONE", f"{obj_name} trading authority escalated")
    require(lock.get("authority", {}).get("buy_sell_authority") is False, "BUY/SELL authority forbidden")
    require(lock.get("authority", {}).get("broker_order_execution") is False, "broker execution forbidden")
    require(lock.get("authority", {}).get("capital_authority") is False, "capital authority forbidden")

    # 4. Rejected families remain rejected.
    require(set(lock.get("frozen_rejected_families", [])) == REJECTED_FAMILIES, "rejected family lock changed")

    # 5. State-machine legality and formal clock anti-backdating guard.
    s = state.get("state")
    require(s in LEGAL_STATES, f"illegal state: {s!r}")
    arm_status = arm.get("arm_status")
    formal_started = state.get("formal_oos_clock_started")
    days = state.get("progress", {}).get("valid_formal_trading_days")
    start = state.get("formal_oos_start_date")

    require(state.get("progress", {}).get("target_valid_formal_trading_days") == 60, "state target days drifted")
    require(state.get("progress", {}).get("maximum_collection_trading_days_if_event_scarcity") == 90, "state max days drifted")
    require(state.get("progress", {}).get("minimum_valid_events") == 120, "state event minimum drifted")
    require(state.get("progress", {}).get("minimum_distinct_event_dates") == 24, "state event-date minimum drifted")
    require(state.get("progress", {}).get("minimum_distinct_event_symbols") == 30, "state symbol minimum drifted")

    if arm_status != "ARMED":
        require(formal_started is False, "formal clock started while candidate not ARMED")
        require(days == 0, "formal trading days counted before ARM")
        require(start is None, "formal start date populated before ARM")
        require(s == "PREARMED_DATA_COLLECTING", "non-ARMED candidate must remain PREARMED_DATA_COLLECTING")
        require(state.get("conclusion", {}).get("formal_conclusion") == "NONE", "formal conclusion before ARM forbidden")
    else:
        require(formal_started is True, "ARMED candidate must explicitly start formal clock")
        require(nonnull(start), "ARMED candidate missing formal start date")
        gates = arm.get("arm_gates", {})
        require(gates and all(v is True for v in gates.values()), "ARMED with incomplete ARM gates")
        cd = arm.get("candidate_definition", {})
        for key in (
            "hypothesis",
            "event_definition",
            "eligible_universe_rule",
            "control_construction",
            "primary_endpoint",
            "primary_horizon_trading_days",
            "expected_direction",
            "null_value",
            "minimum_practical_effect",
        ):
            require(nonnull(cd.get(key)), f"ARMED candidate missing {key}")
        require(cd.get("primary_horizon_trading_days") in {1, 5, 20}, "primary horizon must be T+1/T+5/T+20")
        eb = arm.get("executable_binding", {})
        require(eb.get("binding_status") == "BOUND", "ARMED executable is not BOUND")
        require(nonnull(eb.get("extractor_path")), "ARMED extractor path missing")
        require(nonnull(eb.get("extractor_blob_sha1")), "ARMED extractor hash missing")
        require(arm.get("input_provenance_binding", {}).get("actual_availability_contract_frozen") is True, "input provenance not frozen")
        require(arm.get("collector_binding", {}).get("collector_versions_frozen") is True, "collector identity not frozen")

    # 6. Violation counters are one-way safety indicators; any positive semantic/backdating violation blocks promotion.
    integ = state.get("integrity", {})
    for key in (
        "append_only_violation_count",
        "timestamp_provenance_violation_count",
        "universe_integrity_violation_count",
        "forbidden_semantic_rule_change_count",
        "backdating_violation_count",
    ):
        val = integ.get(key)
        require(isinstance(val, int) and val >= 0, f"invalid violation counter: {key}")

    # 7. Bounded extension only for scarcity, never performance.
    cp = state.get("checkpoint", {})
    if cp.get("bounded_extension_active"):
        require(days >= 60, "bounded extension before Day 60 forbidden")
        require(days <= 90, "bounded extension beyond Day 90 forbidden")
        require(cp.get("bounded_extension_reason") == "EVENT_DIVERSITY_GATES_ONLY", "illegal extension reason")

    require(isinstance(days, int) and 0 <= days <= 90, "formal trading day counter outside [0,90]")

    # 8. Terminal judgment guards.
    conclusion = state.get("conclusion", {})
    if s in {"OOS_FAIL", "OOS_MIXED", "OOS_INCONCLUSIVE_LOW_EVENT_RATE"}:
        require(conclusion.get("formal_weight") == 0, f"{s} must have formal weight 0")
    if s == "OOS_PASS_CANDIDATE":
        p = state.get("progress", {})
        require(days >= 60, "PASS_CANDIDATE before 60 valid days")
        require(p.get("valid_event_count", 0) >= 120, "PASS_CANDIDATE below event minimum")
        require(p.get("distinct_event_dates", 0) >= 24, "PASS_CANDIDATE below date diversity")
        require(p.get("distinct_event_symbols", 0) >= 30, "PASS_CANDIDATE below symbol diversity")
        require(integ.get("forbidden_semantic_rule_change_count") == 0, "PASS_CANDIDATE with semantic rule changes")
        require(integ.get("backdating_violation_count") == 0, "PASS_CANDIDATE with backdating violation")
        require(conclusion.get("validated") is False, "first cohort cannot directly VALIDATE")
    if s == "VALIDATED":
        die("v1 first cohort cannot assign VALIDATED; separate confirmation preregistration required")

    # 9. Formal evaluation may execute at most once in this cohort.
    count = cp.get("formal_evaluation_execution_count")
    require(isinstance(count, int) and 0 <= count <= 1, "formal evaluation may execute at most once")
    require(cp.get("formal_evaluation_executed") is (count == 1), "formal evaluation execution flags inconsistent")

    print(json.dumps({
        "system": "HENGCE",
        "validator": "LOSS_FORENSICS_OOS_GOVERNANCE",
        "status": "PASS",
        "state": s,
        "arm_status": arm_status,
        "valid_formal_trading_days": days,
        "production_authority": "NONE",
        "trading_authority": "NONE",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
