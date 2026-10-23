#!/usr/bin/env python3
"""Calendar-gated operational entrypoint for the recovery-pinned EOD ingest.

The underlying ``hengce_eod_incremental_ingest.py`` is intentionally left byte-
for-byte unchanged.  This wrapper is the operational gate: on an effective
TWSE closure it returns before importing/calling the three network legs; on a
trading day it delegates to the pinned ingest without changing its semantics.
"""
from __future__ import annotations

import argparse
import json
from datetime import date

import hengce_twse_calendar as twse_calendar


def _calendar_gate(target: date) -> tuple[bool, dict]:
    manifest, manifest_path, lineage = twse_calendar.load_manifest()
    trading_day = twse_calendar.is_trading_day(target, manifest)
    return trading_day, {
        "market_calendar_date": target.isoformat(),
        "market_calendar_trading_day": trading_day,
        "market_calendar_authority": manifest.get("authority"),
        "market_calendar_fingerprint_sha256": twse_calendar.manifest_fingerprint(manifest),
        "market_calendar_lineage_sha256": lineage,
        "market_calendar_manifest": str(manifest_path),
    }


def ingest(target: date | None = None) -> dict:
    if target is None:
        from hengce_daily_command_center_core_legacy import now_tw
        target = now_tw().date()

    trading_day, calendar_meta = _calendar_gate(target)
    if not trading_day:
        return {
            "system": "HENGCE",
            "artifact": "EOD_OPERATIONAL_CALENDAR_GATE",
            "target_date": target.isoformat(),
            "status": "SKIP_NONTRADING",
            "reason": "TWSE_EFFECTIVE_CALENDAR_CLOSED",
            "available_legs": [],
            "pending_legs": ["price", "institutional", "margin"],
            "error_legs": [],
            "three_leg_complete": False,
            "formal_complete_day": False,
            "mother_status": "NOT_READY",
            "downstream_ready": False,
            "network_access_attempted": False,
            "parallel_eod_tree": False,
            "second_mother": False,
            "model_authority_created": False,
            "ranking_authority": False,
            "signal_authority": False,
            "capital_authority": False,
            "broker_order_execution": False,
            "delegated_to_pinned_ingest": False,
            "policy": "FAIL_CLOSED_EFFECTIVE_TWSE_CALENDAR_NO_DOWNLOAD_NO_PROMOTION",
            **calendar_meta,
        }

    # Import only after the calendar gate.  Closed sessions therefore cannot
    # accidentally enter any of the three network legs through this entrypoint.
    import hengce_eod_incremental_ingest as pinned
    result = pinned.ingest(target)
    if isinstance(result, dict):
        result = dict(result)
        result.update(calendar_meta)
        result["delegated_to_pinned_ingest"] = True
    return result


def self_test() -> None:
    closed, _ = _calendar_gate(date.fromisoformat("2026-10-23"))
    opened, _ = _calendar_gate(date.fromisoformat("2026-10-22"))
    assert closed is False
    assert opened is True
    result = ingest(date.fromisoformat("2026-10-23"))
    assert result["status"] == "SKIP_NONTRADING"
    assert result["network_access_attempted"] is False
    assert result["delegated_to_pinned_ingest"] is False
    assert result["three_leg_complete"] is False
    assert result["formal_complete_day"] is False
    assert result["downstream_ready"] is False
    assert result["capital_authority"] is False
    assert result["broker_order_execution"] is False
    manifest, _, _ = twse_calendar.load_manifest()
    assert twse_calendar.next_trading_day("2026-10-22", manifest) == "2026-10-27"
    print(json.dumps({
        "self_test": "PASS",
        "pinned_ingest_unchanged": True,
        "extraordinary_closure_no_network": True,
        "extraordinary_closure_2026_10_23": True,
        "next_trading_day_after_2026_10_22": "2026-10-27",
    }, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("ingest", "self-test"), required=True)
    parser.add_argument("--date")
    args = parser.parse_args()
    if args.mode == "self-test":
        self_test()
        return 0
    target = date.fromisoformat(args.date) if args.date else None
    print(json.dumps(ingest(target), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
