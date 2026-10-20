#!/usr/bin/env python3
import argparse
import hashlib
import json
from datetime import date, datetime
from pathlib import Path

UNIVERSE_PATH = Path("hengce/live_universe.json")
CONTRACT_PATH = Path("hengce/HENGCE_LIVE_UNIVERSE_COVERAGE_CONTRACT_v1_0_20261020.json")
LATEST = Path("latest.json")
ACTIVE = Path("live/active.json")
STATUS = Path("live/status.json")

ROLE = "TRANSPORT_COVERAGE_OBSERVABILITY_ONLY_NO_RANKING_SIGNAL_CAPITAL_AUTHORITY"
LINEAGE = "LINEAGE_ONLY_NOT_AUTHORITY"
HEALTH_SCOPE = "TRANSPORT_AND_DATA_FRESHNESS_ONLY"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_date(value):
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


def generated_trade_date(payload):
    raw = payload.get("generated_at_taipei") or payload.get("generated_at")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
    except Exception:
        return parse_date(str(raw)[:10])


def validate_contract(contract):
    if contract.get("module") != "HENGCE_LIVE_UNIVERSE_COVERAGE":
        raise SystemExit("UNIVERSE_CONTRACT_MODULE_MISMATCH")
    if contract.get("role") != ROLE:
        raise SystemExit("UNIVERSE_CONTRACT_ROLE_MISMATCH")
    for key in ("ranking", "signal", "capital", "broker_execution"):
        if (contract.get("authority") or {}).get(key) is not False:
            raise SystemExit("UNIVERSE_CONTRACT_AUTHORITY_MUST_BE_FALSE:" + key)
    refresh = contract.get("refresh_policy") or {}
    for key in ("auto_rebuild_from_live_prices", "auto_rebuild_from_full_market_shadow", "auto_rebuild_from_legacy_v3_label"):
        if refresh.get(key) is not False:
            raise SystemExit("UNIVERSE_AUTO_REBUILD_MUST_BE_FALSE:" + key)
    if refresh.get("authoritative_handoff_required_for_symbol_changes") is not True:
        raise SystemExit("UNIVERSE_AUTHORITATIVE_HANDOFF_REQUIRED")
    compat = contract.get("compatibility") or {}
    if compat.get("legacy_fully_healthy_scope") != HEALTH_SCOPE:
        raise SystemExit("UNIVERSE_HEALTH_SCOPE_CONTRACT_MISMATCH")
    if compat.get("overall_observability_must_include_universe_coverage") is not True:
        raise SystemExit("UNIVERSE_OVERALL_OBSERVABILITY_CONTRACT_MISSING")


def classify(target_date, current_date):
    target = parse_date(target_date)
    current = parse_date(current_date) if not isinstance(current_date, date) else current_date
    if target is None or current is None:
        return {
            "universe_coverage_status": "FAIL_CLOSED_INVALID_SOURCE_DATE",
            "universe_source_age_calendar_days": None,
            "universe_source_matches_current_trade_date": False,
            "universe_refresh_required": True,
        }
    age = (current - target).days
    if age < 0:
        status = "FAIL_CLOSED_INVALID_SOURCE_DATE"
    elif age == 0:
        status = "PASS"
    else:
        status = "SOURCE_AGE_REVIEW_REQUIRED"
    return {
        "universe_coverage_status": status,
        "universe_source_age_calendar_days": age,
        "universe_source_matches_current_trade_date": age == 0,
        "universe_refresh_required": age != 0,
    }


def load_inputs():
    if not UNIVERSE_PATH.exists():
        raise SystemExit("LIVE_UNIVERSE_MISSING_FAIL_CLOSED")
    if not CONTRACT_PATH.exists():
        raise SystemExit("LIVE_UNIVERSE_CONTRACT_MISSING_FAIL_CLOSED")
    universe = load(UNIVERSE_PATH)
    contract = load(CONTRACT_PATH)
    validate_contract(contract)
    symbols = [str(x).strip() for x in universe.get("symbols", [])]
    if not symbols or len(symbols) != len(set(symbols)):
        raise SystemExit("LIVE_UNIVERSE_SYMBOL_SET_INVALID")
    if int(universe.get("requested_count", len(symbols))) != len(symbols):
        raise SystemExit("LIVE_UNIVERSE_COUNT_MISMATCH")
    return universe, contract, symbols


def overall_observability(payload, coverage_status):
    if coverage_status == "FAIL_CLOSED_INVALID_SOURCE_DATE":
        return "FAIL_CLOSED_INVALID_UNIVERSE_SOURCE_DATE"
    if str(payload.get("transport_health_status", "PASS")).upper() != "PASS":
        return "DEGRADED_LIVE_PIPELINE"
    if str(payload.get("data_freshness_status", "PASS")).upper() != "PASS":
        return "DEGRADED_LIVE_PIPELINE"
    trial = payload.get("trial_guard_status")
    if trial not in (None, "PASS"):
        return "DEGRADED_LIVE_PIPELINE"
    if coverage_status == "SOURCE_AGE_REVIEW_REQUIRED":
        return "REVIEW_REQUIRED_UNIVERSE_SOURCE_AGE"
    return "PASS"


def guard_fields(payload, universe, contract, symbols):
    current = generated_trade_date(payload)
    state = classify(universe.get("target_date"), current)
    coverage_status = state["universe_coverage_status"]
    state.update({
        "universe_guard_role": ROLE,
        "universe_coverage_contract_version": contract.get("contract_version"),
        "universe_coverage_contract_sha256": sha256(CONTRACT_PATH),
        "universe_guard_source_file_sha256": sha256(UNIVERSE_PATH),
        "universe_source_target_date": universe.get("target_date"),
        "universe_guard_current_trade_date": current.isoformat() if current else None,
        "universe_coverage_symbol_count": len(symbols),
        "universe_source_run_id_lineage_only": True,
        "universe_source_action_board_version_lineage_only": True,
        "universe_source_run_id_semantics": LINEAGE,
        "universe_coverage_ranking_authority": False,
        "universe_coverage_signal_authority": False,
        "universe_coverage_capital_authority": False,
        "universe_coverage_broker_order_execution": False,
        "universe_auto_rebuilt": False,
        "universe_authoritative_refresh_provided_to_guard": False,
        "universe_refresh_mode": "AUTHORITATIVE_HANDOFF_ONLY_NO_AUTO_DERIVATION",
        "universe_existing_bound_coverage_retained": True,
        "fully_healthy_scope": HEALTH_SCOPE,
        "overall_observability_status": overall_observability(payload, coverage_status),
    })
    if coverage_status == "PASS":
        state["universe_observability_status"] = "PASS"
    elif coverage_status == "SOURCE_AGE_REVIEW_REQUIRED":
        state["universe_observability_status"] = "REVIEW_REQUIRED_UNIVERSE_SOURCE_AGE"
    else:
        state["universe_observability_status"] = "FAIL_CLOSED_INVALID_UNIVERSE_SOURCE_DATE"
    return state


def apply_guard():
    universe, contract, symbols = load_inputs()
    if not LATEST.exists():
        raise SystemExit("LATEST_MISSING")
    payload = load(LATEST)
    if payload.get("universe_source_run_id") != universe.get("source_run_id"):
        raise SystemExit("LIVE_UNIVERSE_SOURCE_RUN_BINDING_MISMATCH")
    if payload.get("universe_version") != universe.get("version"):
        raise SystemExit("LIVE_UNIVERSE_VERSION_BINDING_MISMATCH")
    if int(payload.get("requested_count", -1)) != len(symbols):
        raise SystemExit("LIVE_REQUESTED_COUNT_BINDING_MISMATCH")

    fields = guard_fields(payload, universe, contract, symbols)
    payload.update(fields)
    dump(LATEST, payload)
    dump(ACTIVE, payload)

    status = {key: value for key, value in payload.items() if key != "data"}
    status["healthy"] = int(payload.get("success_count", 0)) > 0
    dump(STATUS, status)

    print(
        "HENGCE LIVE UNIVERSE GUARD",
        fields["universe_coverage_status"],
        "target", fields["universe_source_target_date"],
        "current", fields["universe_guard_current_trade_date"],
        "age_days", fields["universe_source_age_calendar_days"],
        "symbols", len(symbols),
        "overall", fields["overall_observability_status"],
        "auto_rebuilt", False,
    )


def validate_latest():
    universe, contract, symbols = load_inputs()
    payload = load(LATEST)
    expected = guard_fields(payload, universe, contract, symbols)

    for key, value in expected.items():
        if payload.get(key) != value:
            raise SystemExit("UNIVERSE_GUARD_FIELD_MISMATCH:" + key + ":" + repr(payload.get(key)) + "!=" + repr(value))

    if payload.get("universe_source_run_id") != universe.get("source_run_id"):
        raise SystemExit("UNIVERSE_SOURCE_RUN_BINDING_MISMATCH")
    if payload.get("universe_target_date") != universe.get("target_date"):
        raise SystemExit("UNIVERSE_TARGET_DATE_BINDING_MISMATCH")
    if payload.get("universe_version") != universe.get("version"):
        raise SystemExit("UNIVERSE_VERSION_BINDING_MISMATCH")
    if int(payload.get("requested_count", -1)) != len(symbols):
        raise SystemExit("UNIVERSE_SYMBOL_COUNT_BINDING_MISMATCH")

    for key in (
        "universe_coverage_ranking_authority",
        "universe_coverage_signal_authority",
        "universe_coverage_capital_authority",
        "universe_coverage_broker_order_execution",
        "universe_auto_rebuilt",
        "universe_authoritative_refresh_provided_to_guard",
    ):
        if payload.get(key) is not False:
            raise SystemExit("UNIVERSE_GUARD_FALSE_LOCK_VIOLATION:" + key)

    if payload.get("universe_source_run_id_lineage_only") is not True:
        raise SystemExit("UNIVERSE_SOURCE_RUN_MUST_BE_LINEAGE_ONLY")
    if payload.get("universe_source_action_board_version_lineage_only") is not True:
        raise SystemExit("UNIVERSE_ACTION_BOARD_VERSION_MUST_BE_LINEAGE_ONLY")
    if payload.get("fully_healthy_scope") != HEALTH_SCOPE:
        raise SystemExit("UNIVERSE_FULLY_HEALTHY_SCOPE_MISSING")

    if payload.get("universe_coverage_status") == "FAIL_CLOSED_INVALID_SOURCE_DATE":
        raise SystemExit("UNIVERSE_INVALID_SOURCE_DATE_FAIL_CLOSED")

    print(
        "HENGCE LIVE UNIVERSE GUARD VERIFIED",
        payload.get("universe_coverage_status"),
        "age_days", payload.get("universe_source_age_calendar_days"),
        "symbols", payload.get("universe_coverage_symbol_count"),
        "refresh_required", payload.get("universe_refresh_required"),
        "overall", payload.get("overall_observability_status"),
    )


def self_test():
    _, contract, _ = load_inputs()
    validate_contract(contract)

    current = classify("2026-10-20", date(2026, 10, 20))
    assert current["universe_coverage_status"] == "PASS"
    assert current["universe_refresh_required"] is False

    older = classify("2026-10-15", date(2026, 10, 20))
    assert older["universe_coverage_status"] == "SOURCE_AGE_REVIEW_REQUIRED"
    assert older["universe_source_age_calendar_days"] == 5
    assert older["universe_refresh_required"] is True

    future = classify("2026-10-21", date(2026, 10, 20))
    assert future["universe_coverage_status"] == "FAIL_CLOSED_INVALID_SOURCE_DATE"

    missing = classify(None, date(2026, 10, 20))
    assert missing["universe_coverage_status"] == "FAIL_CLOSED_INVALID_SOURCE_DATE"

    healthy = {"transport_health_status": "PASS", "data_freshness_status": "PASS", "trial_guard_status": "PASS"}
    assert overall_observability(healthy, "PASS") == "PASS"
    assert overall_observability(healthy, "SOURCE_AGE_REVIEW_REQUIRED") == "REVIEW_REQUIRED_UNIVERSE_SOURCE_AGE"
    degraded = {"transport_health_status": "DEGRADED", "data_freshness_status": "PASS", "trial_guard_status": "PASS"}
    assert overall_observability(degraded, "PASS") == "DEGRADED_LIVE_PIPELINE"

    print(json.dumps({
        "self_test": "PASS",
        "role": ROLE,
        "older_source_is_review_required_not_auto_rebuilt": True,
        "future_or_missing_source_date_fail_closed": True,
        "fully_healthy_scope": HEALTH_SCOPE,
        "overall_observability_includes_universe_coverage": True,
        "ranking_authority": False,
        "signal_authority": False,
        "capital_authority": False,
        "broker_order_execution": False,
    }, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("apply", "validate", "self-test"), default="apply")
    mode = parser.parse_args().mode
    {"apply": apply_guard, "validate": validate_latest, "self-test": self_test}[mode]()


if __name__ == "__main__":
    main()
