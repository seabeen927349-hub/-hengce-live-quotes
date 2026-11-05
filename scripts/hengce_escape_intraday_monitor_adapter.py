#!/usr/bin/env python3
"""Thin adapter from verified FinMind TWSE-common aggregate shadow to HENGCE live monitor.

This adapter does not change the frozen Escape metric contract and does not
create a formal Escape level. It only exposes the already-derived intraday
price/liquidity/breadth context through a stable monitor payload.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

EXPECTED_METRIC_SHA = "1d93c171b0b06d49eef19e0bf63e3b086fc366052d6bbc45516928c672f47281"


def load(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return obj


def payload_sha(obj: dict[str, Any]) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build(context: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
    for obj, label in ((context, "context"), (status, "status")):
        if obj.get("metric_contract_sha256") != EXPECTED_METRIC_SHA:
            raise RuntimeError(f"{label} metric contract mismatch")
        if obj.get("source_binding_promotion_authority") is not False:
            raise RuntimeError(f"{label} source promotion authority must remain false")
        if obj.get("feature_detector_input_authority") is not False:
            raise RuntimeError(f"{label} feature detector authority must remain false")
        if obj.get("formal_metric_authority") is not False:
            raise RuntimeError(f"{label} formal metric authority must remain false")
        if obj.get("one_day_change_rate_may_substitute_locked_ew_return") is not False:
            raise RuntimeError(f"{label} one-day change rate substitution is forbidden")
        if obj.get("missing_as_zero_forbidden") is not True:
            raise RuntimeError(f"{label} missing-as-zero guard is not locked")
        if obj.get("per_security_rows_persisted") is not False:
            raise RuntimeError(f"{label} per-security persistence is forbidden")

    if status.get("state") != "SHADOW_CONTEXT_READY_NO_FORMAL_AUTHORITY":
        raise RuntimeError(f"shadow status not ready: {status.get('state')}")
    if status.get("active_universe_transport_full_coverage") is not True:
        raise RuntimeError("active universe transport is not fully covered")
    if status.get("unexpected_missing_count") != 0:
        raise RuntimeError("unexpected universe gaps remain")

    market = context.get("market")
    industry = context.get("industry")
    if not isinstance(market, dict) or not isinstance(industry, dict):
        raise RuntimeError("aggregate market/industry context missing")

    monitor = {
        "schema": "HENGCE_ESCAPE_INTRADAY_MONITOR_V1",
        "service": "HENGCE Escape Intraday Monitor",
        "generated_at_taipei": status.get("generated_at_taipei"),
        "market_date": context.get("market_date"),
        "monitor_phase": "INTRADAY_PRICE_LIQUIDITY_OBSERVATION",
        "monitor_state": "LIVE_CONTEXT_READY",
        "source": "FinMind taiwan_stock_tick_snapshot",
        "source_role": "PRIMARY_LIVE_TRANSPORT_FOR_MONITOR_SHADOW",
        "monitoring_universe": status.get("monitoring_universe"),
        "metric_contract_sha256": EXPECTED_METRIC_SHA,
        "active_required_count": status.get("active_required_count"),
        "active_covered_count": status.get("active_covered_count"),
        "active_universe_transport_full_coverage": status.get("active_universe_transport_full_coverage"),
        "session_context_count": status.get("session_context_count"),
        "session_context_ratio": status.get("session_context_ratio"),
        "finmind_metric_observation_count": status.get("finmind_metric_observation_count"),
        "metric_unknown_count": status.get("metric_unknown_count"),
        "metric_unknown_sample": status.get("metric_unknown_sample"),
        "latest_source_timestamp": status.get("latest_source_timestamp"),
        "exempt_missing": status.get("exempt_missing"),
        "market": market,
        "industry": industry,
        "quality": {
            "healthy_transport": status.get("healthy_transport"),
            "unexpected_missing_count": status.get("unexpected_missing_count"),
            "twse_mis_secondary_session_status": status.get("twse_mis_secondary_session_status"),
            "twse_mis_session_verified_count": status.get("twse_mis_session_verified_count"),
            "twse_mis_session_unresolved_count": status.get("twse_mis_session_unresolved_count"),
            "raw_finmind_rows_persisted": status.get("raw_finmind_rows_persisted"),
            "per_security_rows_persisted": status.get("per_security_rows_persisted"),
            "stale_rows_neutralized_as_zero": status.get("stale_rows_neutralized_as_zero"),
        },
        "formal_escape_level": None,
        "formal_escape_state": "UNRESOLVED_INTRADAY_SHADOW",
        "formal_escape_authority": False,
        "formal_eod_authority": False,
        "feature_detector_input_authority": False,
        "selection_authority": False,
        "model_authority": False,
        "trading_authority": False,
        "canonical_eod_legs_replaced": False,
    }
    monitor["payload_sha256"] = payload_sha(monitor)
    return monitor


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--context", type=Path, required=True)
    p.add_argument("--status", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    monitor = build(load(args.context), load(args.status))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(monitor, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "monitor_state": monitor["monitor_state"],
        "market_date": monitor["market_date"],
        "active_required_count": monitor["active_required_count"],
        "finmind_metric_observation_count": monitor["finmind_metric_observation_count"],
        "metric_unknown_count": monitor["metric_unknown_count"],
        "formal_escape_level": monitor["formal_escape_level"],
        "formal_escape_authority": monitor["formal_escape_authority"],
        "payload_sha256": monitor["payload_sha256"],
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
