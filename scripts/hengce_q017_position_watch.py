#!/usr/bin/env python3
"""Validate and merge an exit-only Q017 held-position watch into unified HENGCE.

This input is deliberately separate from today's Q017 candidate file.  A
watch row can authorize monitoring/exit of an already-held position, but can
never create entry geometry or entry authority.
"""
from __future__ import annotations

import copy
import re
from typing import Any

from hengce_unified_contracts import ticker as _ticker

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate(watch: Any) -> list[dict[str, Any]]:
    if not isinstance(watch, dict):
        raise ValueError("Q017_POSITION_WATCH_NOT_OBJECT")
    if watch.get("schema_version") != 1 or watch.get("module") != "HENGCE_Q017_POSITION_WATCH":
        raise ValueError("Q017_POSITION_WATCH_UNSUPPORTED_SCHEMA")
    rows = watch.get("positions")
    if not isinstance(rows, list):
        raise ValueError("Q017_POSITION_WATCH_POSITIONS_NOT_LIST")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for original in rows:
        if not isinstance(original, dict):
            raise ValueError("Q017_POSITION_WATCH_ROW_NOT_OBJECT")
        ticker = _ticker(original)
        if not ticker or ticker in seen:
            raise ValueError("Q017_POSITION_WATCH_INVALID_OR_DUPLICATE_TICKER")
        seen.add(ticker)
        if original.get("PositionHeld") is not True:
            raise ValueError("Q017_POSITION_WATCH_REQUIRES_HELD_TRUE")
        entry_date = str(original.get("PositionEntryDate") or "")
        if not DATE_RE.fullmatch(entry_date):
            raise ValueError("Q017_POSITION_WATCH_ENTRY_DATE_REQUIRED")
        provenance = str(original.get("SourceProvenance") or "Q017").upper()
        if provenance not in {"Q017", "BOTH"}:
            raise ValueError("Q017_POSITION_WATCH_BAD_PROVENANCE")
        out.append({
            "Ticker": ticker,
            "PositionHeld": True,
            "PositionEntryDate": entry_date,
            "SourceProvenance": provenance,
            "PositionWatchEvidence": copy.deepcopy(original),
        })
    return out


def merge(unified: dict[str, Any], watch: Any | None) -> dict[str, Any]:
    if watch is None:
        out = copy.deepcopy(unified)
        out["q017_position_watch_status"] = "NOT_PROVIDED"
        out["q017_position_watch_count"] = 0
        return out
    positions = validate(watch)
    out = copy.deepcopy(unified)
    rows = out.get("rows")
    if not isinstance(rows, list):
        raise ValueError("UNIFIED_ROWS_NOT_LIST")
    by_ticker = {_ticker(r): r for r in rows if isinstance(r, dict) and _ticker(r)}

    for position in positions:
        ticker = position["Ticker"]
        existing = by_ticker.get(ticker)
        if existing is not None:
            existing["PositionHeld"] = True
            existing["PositionEntryDate"] = position["PositionEntryDate"]
            existing["PositionWatchEvidence"] = position["PositionWatchEvidence"]
            # A Q017-held legacy candidate becomes BOTH, never Q017-only entry authority.
            if existing.get("SourceProvenance") == "LEGACY":
                existing["SourceProvenance"] = "BOTH"
        else:
            row = {
                "Ticker": ticker,
                "PositionHeld": True,
                "PositionEntryDate": position["PositionEntryDate"],
                "PositionWatchEvidence": position["PositionWatchEvidence"],
                "SourceProvenance": "Q017",
                "FormalEntryTrigger": False,
                "FormalCandidate": False,
                "GeometryStatus": "UNAVAILABLE",
                "LegacyEvidence": None,
                "Q017Evidence": None,
                "LegacyScore": None,
                "Q017Score": None,
                "Q017Rank": None,
                "Q017Beta60": None,
                "Q017Residual1": None,
            }
            rows.append(row)
            by_ticker[ticker] = row

    counts = {"LEGACY": 0, "Q017": 0, "BOTH": 0}
    for row in rows:
        provenance = row.get("SourceProvenance") if isinstance(row, dict) else None
        if provenance in counts:
            counts[provenance] += 1
    out["source_provenance_counts"] = counts
    out["q017_position_watch_status"] = "PASS"
    out["q017_position_watch_count"] = len(positions)
    out["q017_position_watch_tickers"] = [p["Ticker"] for p in positions]
    return out
