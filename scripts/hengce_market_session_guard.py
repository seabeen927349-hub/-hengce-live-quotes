#!/usr/bin/env python3
"""Apply the pinned effective TWSE calendar to runtime data-vessel artifacts.

Authority-reducing only: this guard may turn a runtime artifact from READY/PASS
into MARKET_CLOSED, but it never grants ranking, signal, capital, or broker
authority.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import hengce_twse_calendar as twse_calendar

TZ = ZoneInfo("Asia/Taipei")


def _parse_date(value: str | None, payload: dict | None = None) -> str:
    if value:
        return str(value)[:10]
    payload = payload or {}
    for key in ("generated_at_taipei", "fetched_at_taipei", "updated_at_taipei", "target_date"):
        raw = payload.get(key)
        if isinstance(raw, str) and len(raw) >= 10:
            return raw[:10]
    return datetime.now(TZ).date().isoformat()


def session_metadata(target_date: str) -> dict:
    manifest, path, lineage = twse_calendar.load_manifest()
    trading_day = twse_calendar.is_trading_day(target_date, manifest)
    return {
        "market_calendar_trading_day": trading_day,
        "market_calendar_authority": manifest.get("authority"),
        "market_calendar_fingerprint_sha256": twse_calendar.manifest_fingerprint(manifest),
        "market_calendar_lineage_sha256": lineage,
        "market_calendar_manifest": str(path),
        "market_calendar_date": target_date,
    }


def _assert_no_authority_promotion(payload: dict) -> None:
    for key in ("ranking_authority", "signal_authority", "capital_authority", "broker_order_execution"):
        if payload.get(key) is True:
            raise ValueError("MARKET_SESSION_GUARD_REFUSES_AUTHORITY_BEARING_ARTIFACT:" + key)


def guard_live(payload: dict, target_date: str | None = None) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("LIVE_ARTIFACT_NOT_OBJECT")
    _assert_no_authority_promotion(payload)
    target = _parse_date(target_date, payload)
    meta = session_metadata(target)
    payload.update(meta)

    trading_day = meta["market_calendar_trading_day"]
    payload["market_session_data_usable"] = bool(
        trading_day
        and payload.get("market_phase") == "open"
        and payload.get("transport_health_status") == "PASS"
        and payload.get("data_freshness_status") == "PASS"
        and payload.get("fully_healthy") is True
    )
    payload["market_closed_by_calendar"] = not trading_day

    if not trading_day:
        payload["market_phase"] = "closed"
        payload["data_freshness_status"] = "MARKET_CLOSED"
        payload["fully_healthy"] = False
        payload["degraded"] = False
        payload["market_session_data_usable"] = False
        payload["market_closed_reason"] = "TWSE_EFFECTIVE_CALENDAR_CLOSED"
        # Previous-session quotes are expected carry-forward on an official closure.
        # Preserve raw stale/mismatch counters but remove them from outage semantics.
        payload["unexpected_stale_count"] = 0
        for row in payload.get("data") or []:
            if not isinstance(row, dict):
                continue
            row["market_phase"] = "closed"
            row["market_calendar_trading_day"] = False
            row["market_session_data_usable"] = False
            row["market_closed_by_calendar"] = True
            row["unexpected_stale_at_publish"] = False
            row["stale_expected_due_market_closure"] = bool(row.get("stale_at_publish"))
    return payload


def guard_shadow(payload: dict, target_date: str | None = None) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("SHADOW_ARTIFACT_NOT_OBJECT")
    _assert_no_authority_promotion(payload)
    target = _parse_date(target_date, payload)
    meta = session_metadata(target)
    payload.update(meta)
    trading_day = meta["market_calendar_trading_day"]
    payload["market_closed_by_calendar"] = not trading_day

    gate = payload.get("full_market_gate")
    if gate is not None and not isinstance(gate, dict):
        raise ValueError("SHADOW_FULL_MARKET_GATE_NOT_OBJECT")
    if gate is None:
        gate = {}
        payload["full_market_gate"] = gate

    if not trading_day:
        gate["pass"] = False
        gate["calendar_trading_day"] = False
        gate["calendar_reason"] = "TWSE_EFFECTIVE_CALENDAR_CLOSED"
        payload["status"] = "SHADOW_MARKET_CLOSED"
        payload["market_session_data_usable"] = False
        payload["fully_healthy"] = False
    else:
        gate["calendar_trading_day"] = True
        payload["market_session_data_usable"] = bool(gate.get("pass"))
    return payload


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def apply_file(mode: str, path: Path, target_date: str | None = None) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if mode == "live":
        result = guard_live(payload, target_date)
    elif mode == "shadow":
        result = guard_shadow(payload, target_date)
    else:
        raise ValueError("MARKET_SESSION_GUARD_MODE_INVALID:" + mode)
    _atomic_write_json(path, result)
    return result


def self_test() -> None:
    assert session_metadata("2026-10-23")["market_calendar_trading_day"] is False
    assert session_metadata("2026-10-22")["market_calendar_trading_day"] is True
    manifest, _, _ = twse_calendar.load_manifest()
    assert twse_calendar.next_trading_day("2026-10-22", manifest) == "2026-10-27"

    live = {
        "generated_at_taipei": "2026-10-23T10:00:00+08:00",
        "market_phase": "open",
        "transport_health_status": "PASS",
        "data_freshness_status": "DEGRADED",
        "fully_healthy": False,
        "degraded": True,
        "unexpected_stale_count": 1,
        "ranking_authority": False,
        "signal_authority": False,
        "capital_authority": False,
        "broker_order_execution": False,
        "data": [{"stale_at_publish": True, "unexpected_stale_at_publish": True}],
    }
    guarded_live = guard_live(live)
    assert guarded_live["market_phase"] == "closed"
    assert guarded_live["data_freshness_status"] == "MARKET_CLOSED"
    assert guarded_live["market_session_data_usable"] is False
    assert guarded_live["unexpected_stale_count"] == 0
    assert guarded_live["data"][0]["unexpected_stale_at_publish"] is False

    shadow = {
        "generated_at_taipei": "2026-10-23T10:00:00+08:00",
        "status": "SHADOW_FULL_MARKET_READY",
        "full_market_gate": {"pass": True},
        "ranking_authority": False,
        "signal_authority": False,
        "capital_authority": False,
        "broker_order_execution": False,
    }
    guarded_shadow = guard_shadow(shadow)
    assert guarded_shadow["status"] == "SHADOW_MARKET_CLOSED"
    assert guarded_shadow["full_market_gate"]["pass"] is False
    assert guarded_shadow["market_session_data_usable"] is False
    print("PASS hengce_market_session_guard self-test")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("live", "shadow"))
    parser.add_argument("--artifact")
    parser.add_argument("--date")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0
    if not args.mode or not args.artifact:
        parser.error("--mode and --artifact are required unless --self-test is used")
    result = apply_file(args.mode, Path(args.artifact), args.date)
    print(json.dumps({
        "status": result.get("status") or result.get("data_freshness_status"),
        "market_calendar_date": result.get("market_calendar_date"),
        "market_calendar_trading_day": result.get("market_calendar_trading_day"),
        "market_session_data_usable": result.get("market_session_data_usable"),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
