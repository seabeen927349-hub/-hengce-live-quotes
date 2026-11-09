#!/usr/bin/env python3
"""HENGCE FinMind whole-market intraday receipt gate.

Check ONLY existing FinMind aggregate-shadows, not paid per-stock raw rows.
Never upgrade market-state, detector, EOD, selection or trading authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")
EXPECTED_METRIC_SHA = "1d93c171b0b06d49eef19e0bf63e3b086fc366052d6bbc45516928c672f47281"


class Rejected(RuntimeError):
    pass


def payload_hash(obj: dict) -> str:
    obj = dict(obj)
    obj.pop("payload_sha256", None)
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def stamp(value) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise Rejected("MISSING_SOURCE_TIMESTAMP")
    try:
        d = datetime.fromisoformat(value.strip().replace(" ", "T"))
    except ValueError as exc:
        raise Rejected("INVALID_SOURCE_TIMESTAMP") from exc
    if d.tzinfo is None:
        d = d.replace(tzinfo=TAIPEI)
    return d.astimezone(TAIPEI)


def validate(context: dict, status: dict, monitor: dict, now: datetime | None = None) -> dict:
    now = (now or datetime.now(TAIPEI)).astimezone(TAIPEI)
    day = now.date().isoformat()
    for key, obj in (("context", context), ("status", status), ("monitor", monitor)):
        if not isinstance(obj, dict):
            raise Rejected("INVALID_" + key.upper())
    if status.get("state") != "SHADOW_CONTEXT_READY_NO_FORMAL_AUTHORITY":
        raise Rejected("SHADOW_NOT_READY")
    if monitor.get("monitor_state") != "LIVE_CONTEXT_READY":
        raise Rejected("MONITOR_NOT_READY")
    if context.get("market_date") != day or monitor.get("market_date") != day:
        raise Rejected("NOT_CURRENT_TW_MARKET_DAY")
    if status.get("source") != "FinMind" or monitor.get("source") != "FinMind taiwan_stock_tick_snapshot":
        raise Rejected("SOURCE_NOT_FINMIND_VESSEL")
    if any(obj.get("metric_contract_sha256") != EXPECTED_METRIC_SHA for obj in (context, status, monitor)):
        raise Rejected("FROZEN_METRIC_CONTRACT_MISMATCH")
    if status.get("context_payload_sha256") != context.get("payload_sha256"):
        raise Rejected("CONTEXT_DIGEST_MISMATCH")
    if context.get("payload_sha256") != payload_hash(context):
        raise Rejected("CONTEXT_PAYLOAD_TAMPERED")
    if monitor.get("payload_sha256") != payload_hash(monitor):
        raise Rejected("MONITOR_PAYLOAD_TAMPERED")
    if any(obj.get("formal_eod_authority") is not False for obj in (status, monitor)):
        raise Rejected("EOD_AUTHORITY_FORBIDDEN")
    if any(obj.get("trading_authority") is not False for obj in (status, monitor)):
        raise Rejected("TRADING_AUTHORITY_FORBIDDEN")
    if monitor.get("formal_escape_authority") is not False:
        raise Rejected("ESCAPE_AUTHORITY_FORBIDDEN")
    if monitor.get("feature_detector_input_authority") is not False:
        raise Rejected("FEATURE_DETECTOR_AUTHORITY_FORBIDDEN")
    if monitor.get("canonical_eod_legs_replaced") is not False:
        raise Rejected("REPLACED_CANONICAL_FORBIDDEN")
    if status.get("active_universe_transport_full_coverage") is not True or monitor.get("active_universe_transport_full_coverage") is not True:
        raise Rejected("FULL_UNIVERSE_TRANSPORT_MISSING")
    count = status.get("active_required_count")
    covered = status.get("active_covered_count")
    valid = status.get("finmind_metric_observation_count")
    unknown = status.get("metric_unknown_count")
    if not (type(count) is int and count >= 900 and
            type(covered) is int and covered == count and
            type(valid) is int and type(unknown) is int and
            valid + unknown == count and valid / count >= 0.98):
        raise Rejected("FINMIND_METRIC_COVERAGE_LOW")
    if any(monitor.get(k) != status.get(k) for k in (
        "active_required_count", "active_covered_count", "finmind_metric_observation_count", "metric_unknown_count"
    )):
        raise Rejected("MONITOR_STATUS_COUNT_MISMATCH")
    if context.get("market", {}).get("return_observed_count") != valid:
        raise Rejected("MARKET_BREADTH_COUNT_MISMATCH")

    generated = stamp(status.get("generated_at_taipei"))
    if stamp(monitor.get("generated_at_taipei")) != generated or stamp(context.get("generated_at_taipei")) != generated:
        raise Rejected("GENERATED_TIMES_DISAGREE")
    age_generated = (now - generated).total_seconds() / 60
    if age_generated < -2 or age_generated > 12:
        raise Rejected("COLLECTOR_OUTPUT_NOT_FRESH")
    source = stamp(status.get("latest_source_timestamp"))
    if stamp(monitor.get("latest_source_timestamp")) != source or stamp(context.get("latest_source_timestamp")) != source:
        raise Rejected("LATEST_SOURCE_TIMES_DISAGREE")
    if source.date().isoformat() != day:
        raise Rejected("STALE_FINMIND_SOURCE_DATE")
    source_age = (now - source).total_seconds() / 60
    if source_age < -2:
        raise Rejected("SOURCE_TIMESTAMP_IN_FUTURE")

    # During continuous TWSE trading, the latest market observation must not be stale.
    # Outside the session the same-day close context is allowed, but never presented
    # as live trading or formal EOD.
    minutes = now.hour * 60 + now.minute
    during_session = 9 * 60 + 10 <= minutes <= 13 * 60 + 35
    if during_session and source_age > 25:
        raise Rejected("INTRADAY_SOURCE_OLDER_THAN_25_MINUTES")
    return {
        "state": "PASS_FINMIND_SHADOW_FRESHNESS",
        "market_date": day,
        "collector_generated_at": generated.isoformat(),
        "latest_source_timestamp": source.isoformat(),
        "source_age_minutes": round(source_age, 2),
        "active_required_count": count,
        "valid_metric_count": valid,
        "unknown_metric_count": unknown,
        "intraday_recency_gate_applied": during_session,
        "authority": "RESEARCH_SHADOW_ONLY_NO_EOD_ESCAPE_SELECTION_OR_TRADING",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--context", required=True, type=Path)
    p.add_argument("--status", required=True, type=Path)
    p.add_argument("--monitor", required=True, type=Path)
    args = p.parse_args()
    context = json.loads(args.context.read_text(encoding="utf-8"))
    status = json.loads(args.status.read_text(encoding="utf-8"))
    monitor = json.loads(args.monitor.read_text(encoding="utf-8"))
    try:
        result = validate(context, status, monitor)
    except Rejected as exc:
        print(json.dumps({"state": "FAIL_CLOSED", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
