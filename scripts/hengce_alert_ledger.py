#!/usr/bin/env python3
"""Persist deduplicated HENGCE alerts emitted by the live action board.

This module is transport-neutral.  It produces a stable new-alert file plus a
ledger of seen AlertKey values so an external notifier can consume each event
once without granting this layer any trade authority.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from hengce_unified_contracts import atomic, strict_loads


def _existing(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "module": "HENGCE_ALERT_LEDGER", "seen": {}}
    data = strict_loads(path.read_bytes())
    if not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("module") != "HENGCE_ALERT_LEDGER":
        raise ValueError("ALERT_LEDGER_UNSUPPORTED_SCHEMA")
    if not isinstance(data.get("seen"), dict):
        raise ValueError("ALERT_LEDGER_SEEN_NOT_OBJECT")
    return data


def _alert(row: dict[str, Any], trade_date: str | None, generated_at: str | None) -> dict[str, Any]:
    return {
        "Ticker": row.get("Ticker"),
        "AlertKey": row.get("AlertKey"),
        "AlertLevel": row.get("AlertLevel"),
        "StructureExitState": row.get("StructureExitState"),
        "StructureBreakLevel": row.get("StructureBreakLevel"),
        "StructureReactionLow": row.get("StructureReactionLow"),
        "StructureFirstBreakDate": row.get("StructureFirstBreakDate"),
        "StructureReclaimDate": row.get("StructureReclaimDate"),
        "FinalAction": row.get("FinalAction"),
        "trade_date": trade_date,
        "generated_at": generated_at,
    }


def update(action: dict[str, Any], alerts_path: Path, ledger_path: Path, now: datetime | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(action, dict) or not isinstance(action.get("rows"), list):
        raise ValueError("ACTION_BOARD_ROWS_UNAVAILABLE")
    ledger = _existing(ledger_path)
    seen = dict(ledger["seen"])
    generated_at = action.get("generated_at") or (now.isoformat() if now else None)
    trade_date = action.get("trade_date")
    new_alerts: list[dict[str, Any]] = []

    for row in action["rows"]:
        if not isinstance(row, dict) or row.get("AlertRequired") is not True:
            continue
        key = row.get("AlertKey")
        if not isinstance(key, str) or not key:
            raise ValueError("ALERT_REQUIRED_WITHOUT_KEY")
        alert = _alert(row, trade_date, generated_at)
        if key not in seen:
            new_alerts.append(alert)
            seen[key] = {
                "first_seen_at": generated_at,
                "trade_date": trade_date,
                "Ticker": alert["Ticker"],
                "AlertLevel": alert["AlertLevel"],
                "StructureExitState": alert["StructureExitState"],
                "FinalAction": alert["FinalAction"],
            }

    alerts = {
        "schema_version": 1,
        "module": "HENGCE_ALERTS",
        "generated_at": generated_at,
        "trade_date": trade_date,
        "new_alert_count": len(new_alerts),
        "alerts": new_alerts,
        "transport_status": "NOT_CONFIGURED",
        "trade_authority": 0,
    }
    ledger_out = {
        "schema_version": 1,
        "module": "HENGCE_ALERT_LEDGER",
        "updated_at": generated_at,
        "seen_count": len(seen),
        "seen": seen,
        "trade_authority": 0,
    }
    atomic(alerts_path, alerts)
    atomic(ledger_path, ledger_out)
    return alerts, ledger_out
