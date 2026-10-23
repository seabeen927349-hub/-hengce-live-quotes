#!/usr/bin/env python3
"""Pinned TWSE trading-calendar validation for causal HENGCE session binding."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date, timedelta
from pathlib import Path

from hengce_unified_contracts import strict_loads

CALENDAR_YEAR = 2026
EXPECTED_SOURCE_RECORDS_SHA256 = "8f9096843c09c877a51df318946e6dc279f36863ec9230b79a8b1a07a1af3cc6"
EXPECTED_CALENDAR_FINGERPRINT_SHA256 = "eb8861a737327a867c6cea8d6d58fa41235dd125cdae1760e0b1441751b26f84"
EXPECTED_ENDPOINT = "https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule"
MANIFEST_NAME = "TWSE_TRADING_CALENDAR_2026_v1.json"


def _canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha(value) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _as_date(value) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError("TWSE_CALENDAR_INVALID_DATE:" + str(value)) from exc


def _root() -> Path:
    return Path(os.environ.get("HENGCE_ROOT", Path(__file__).resolve().parents[1])).resolve()


def default_manifest_path() -> Path:
    explicit = os.environ.get("HENGCE_TWSE_CALENDAR_JSON")
    if explicit is not None:
        path = Path(explicit).resolve()
        if not path.is_file():
            raise ValueError("TWSE_CALENDAR_OVERRIDE_NOT_FOUND")
        return path
    root = _root()
    candidates = [
        root / "hengce/calendar" / MANIFEST_NAME,
        root / "governance" / MANIFEST_NAME,
    ]
    found = [p for p in candidates if p.is_file()]
    if len(found) != 1:
        raise ValueError("TWSE_CALENDAR_NOT_FOUND_OR_AMBIGUOUS")
    return found[0]


def validate_manifest(manifest) -> dict:
    if not isinstance(manifest, dict):
        raise ValueError("TWSE_CALENDAR_NOT_OBJECT")
    if (manifest.get("schema_version") != 1 or manifest.get("market") != "TWSE" or
            manifest.get("calendar_year") != CALENDAR_YEAR or manifest.get("roc_year") != 115 or
            manifest.get("timezone") != "Asia/Taipei" or
            manifest.get("authority") != "TWSE_OFFICIAL_HOLIDAY_SCHEDULE"):
        raise ValueError("TWSE_CALENDAR_SCHEMA_OR_AUTHORITY_MISMATCH")
    if manifest.get("base_rule") != {"weekday_trading_days": [0, 1, 2, 3, 4], "weekend_closed": True}:
        raise ValueError("TWSE_CALENDAR_BASE_RULE_MISMATCH")
    source = manifest.get("source")
    if not isinstance(source, dict) or source.get("endpoint") != EXPECTED_ENDPOINT:
        raise ValueError("TWSE_CALENDAR_SOURCE_MISMATCH")
    records = manifest.get("source_records")
    if not isinstance(records, list) or not records:
        raise ValueError("TWSE_CALENDAR_SOURCE_RECORDS_MISSING")
    if _sha(records) != EXPECTED_SOURCE_RECORDS_SHA256 or source.get("source_records_sha256") != EXPECTED_SOURCE_RECORDS_SHA256:
        raise ValueError("TWSE_CALENDAR_SOURCE_RECORDS_HASH_MISMATCH")

    closed = []
    opened = []
    seen = set()
    for row in records:
        if not isinstance(row, dict) or set(row) != {"name", "date", "weekday", "kind"}:
            raise ValueError("TWSE_CALENDAR_RECORD_SCHEMA_MISMATCH")
        ds = _as_date(row["date"])
        if ds.year != CALENDAR_YEAR or row["date"] in seen:
            raise ValueError("TWSE_CALENDAR_RECORD_DATE_INVALID_OR_DUPLICATE")
        seen.add(row["date"])
        if row["kind"] == "CLOSED":
            closed.append(row["date"])
        elif row["kind"] == "OPEN_MARKER":
            opened.append(row["date"])
        else:
            raise ValueError("TWSE_CALENDAR_RECORD_KIND_INVALID")
    if manifest.get("closed_dates") != closed or manifest.get("explicit_open_dates") != opened:
        raise ValueError("TWSE_CALENDAR_CLASSIFICATION_MISMATCH")

    core = {
        "schema_version": manifest["schema_version"],
        "market": manifest["market"],
        "calendar_year": manifest["calendar_year"],
        "roc_year": manifest["roc_year"],
        "timezone": manifest["timezone"],
        "base_rule": manifest["base_rule"],
        "closed_dates": closed,
        "explicit_open_dates": opened,
        "source": {
            "publisher": source.get("publisher"),
            "endpoint": source.get("endpoint"),
            "source_records_sha256": source.get("source_records_sha256"),
        },
    }
    fingerprint = _sha(core)
    if fingerprint != EXPECTED_CALENDAR_FINGERPRINT_SHA256 or manifest.get("calendar_fingerprint_sha256") != fingerprint:
        raise ValueError("TWSE_CALENDAR_FINGERPRINT_MISMATCH")
    return manifest


def load_manifest(path: Path | str | None = None) -> tuple[dict, Path, str]:
    selected = Path(path).resolve() if path is not None else default_manifest_path()
    raw = selected.read_bytes()
    manifest = validate_manifest(strict_loads(raw))
    return manifest, selected, hashlib.sha256(raw).hexdigest()


def is_trading_day(value, manifest: dict) -> bool:
    manifest = validate_manifest(manifest)
    ds = _as_date(value)
    if ds.year != CALENDAR_YEAR:
        raise ValueError("TWSE_CALENDAR_YEAR_OUT_OF_RANGE")
    iso = ds.isoformat()
    if iso in manifest["explicit_open_dates"]:
        return True
    if iso in manifest["closed_dates"]:
        return False
    return ds.weekday() in manifest["base_rule"]["weekday_trading_days"]


def next_trading_day(value, manifest: dict) -> str:
    current = _as_date(value)
    if current.year != CALENDAR_YEAR:
        raise ValueError("TWSE_CALENDAR_YEAR_OUT_OF_RANGE")
    for offset in range(1, 15):
        candidate = current + timedelta(days=offset)
        if candidate.year != CALENDAR_YEAR:
            raise ValueError("TWSE_CALENDAR_COVERAGE_EXHAUSTED")
        if is_trading_day(candidate, manifest):
            return candidate.isoformat()
    raise ValueError("TWSE_CALENDAR_NEXT_SESSION_UNRESOLVED")


def validate_next_session(signal_date, trade_date, manifest: dict) -> None:
    signal = _as_date(signal_date)
    trade = _as_date(trade_date)
    if not is_trading_day(signal, manifest):
        raise ValueError("Q017_SIGNAL_DATE_NOT_TWSE_TRADING_DAY")
    if not is_trading_day(trade, manifest):
        raise ValueError("Q017_TRADE_DATE_NOT_TWSE_TRADING_DAY")
    expected = next_trading_day(signal, manifest)
    if trade.isoformat() != expected:
        raise ValueError("Q017_NOT_NEXT_TWSE_OPEN:" + expected)


def manifest_fingerprint(manifest: dict) -> str:
    validate_manifest(manifest)
    return EXPECTED_CALENDAR_FINGERPRINT_SHA256
