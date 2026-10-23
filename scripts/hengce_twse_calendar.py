#!/usr/bin/env python3
"""Pinned TWSE trading-calendar validation for causal HENGCE session binding.

The annual TWSE holiday schedule is the immutable base calendar. Unplanned
market closures (for example a typhoon closure) are a separate, independently
pinned authority layer. Runtime consumers receive an effective calendar that
combines both layers and binds both source files into one lineage digest.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from datetime import date, timedelta
from pathlib import Path

from hengce_unified_contracts import strict_loads

CALENDAR_YEAR = 2026
BASE_AUTHORITY = "TWSE_OFFICIAL_HOLIDAY_SCHEDULE"
EFFECTIVE_AUTHORITY = "TWSE_OFFICIAL_HOLIDAY_SCHEDULE_PLUS_EXTRAORDINARY_CLOSURES"
EXPECTED_SOURCE_RECORDS_SHA256 = "8f9096843c09c877a51df318946e6dc279f36863ec9230b79a8b1a07a1af3cc6"
EXPECTED_BASE_CALENDAR_FINGERPRINT_SHA256 = "eb8861a737327a867c6cea8d6d58fa41235dd125cdae1760e0b1441751b26f84"
# Backward-compatible name for code that intentionally refers to the annual base.
EXPECTED_CALENDAR_FINGERPRINT_SHA256 = EXPECTED_BASE_CALENDAR_FINGERPRINT_SHA256
EXPECTED_EXTRAORDINARY_CLOSURES_SHA256 = "5a09dc8580b5bd08ffac35f48d3809445ac3c322ebeaa713cd33fe2a33384847"
EXPECTED_EXTRAORDINARY_FINGERPRINT_SHA256 = "0c01c796ccae97347539b790de04491f291f4ec0ae20d9e96faecdf817592d1f"
EXPECTED_EFFECTIVE_CALENDAR_FINGERPRINT_SHA256 = "d22bd75b6a9b63a440c494133a438a8266387964e74d3e5ca0ca676dfd4e1b9c"
EXPECTED_ENDPOINT = "https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule"
MANIFEST_NAME = "TWSE_TRADING_CALENDAR_2026_v1.json"
EXTRAORDINARY_MANIFEST_NAME = "TWSE_EXTRAORDINARY_CLOSURES_2026_v1.json"
EXPECTED_TAIPEI_EOC_URL = "https://eoc.gov.taipei/News/Detail/1590?MenuId=51"
EXPECTED_TWSE_SUSPENSION_URL = "https://www.twse.com.tw/zh/clearing/suspended.html"


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


def _select_duplicate_safe(explicit_env: str, name: str, missing: str, mismatch: str) -> Path:
    explicit = os.environ.get(explicit_env)
    if explicit is not None:
        path = Path(explicit).resolve()
        if not path.is_file():
            raise ValueError(missing + "_OVERRIDE_NOT_FOUND")
        return path
    root = _root()
    candidates = [root / "hengce/calendar" / name, root / "governance" / name]
    found = [p for p in candidates if p.is_file()]
    if not found:
        raise ValueError(missing + "_NOT_FOUND")
    if len(found) > 1:
        payloads = [p.read_bytes() for p in found]
        if any(blob != payloads[0] for blob in payloads[1:]):
            raise ValueError(mismatch)
    return found[0]


def default_manifest_path() -> Path:
    return _select_duplicate_safe(
        "HENGCE_TWSE_CALENDAR_JSON", MANIFEST_NAME,
        "TWSE_CALENDAR", "TWSE_CALENDAR_DUPLICATE_MISMATCH")


def default_extraordinary_manifest_path() -> Path:
    return _select_duplicate_safe(
        "HENGCE_TWSE_EXTRAORDINARY_CLOSURES_JSON", EXTRAORDINARY_MANIFEST_NAME,
        "TWSE_EXTRAORDINARY_CLOSURES", "TWSE_EXTRAORDINARY_CLOSURES_DUPLICATE_MISMATCH")


def _validate_base_manifest(manifest) -> dict:
    if not isinstance(manifest, dict):
        raise ValueError("TWSE_CALENDAR_NOT_OBJECT")
    if (manifest.get("schema_version") != 1 or manifest.get("market") != "TWSE" or
            manifest.get("calendar_year") != CALENDAR_YEAR or manifest.get("roc_year") != 115 or
            manifest.get("timezone") != "Asia/Taipei" or manifest.get("authority") != BASE_AUTHORITY):
        raise ValueError("TWSE_CALENDAR_SCHEMA_OR_AUTHORITY_MISMATCH")
    if manifest.get("base_rule") != {"weekday_trading_days": [0, 1, 2, 3, 4], "weekend_closed": True}:
        raise ValueError("TWSE_CALENDAR_BASE_RULE_MISMATCH")
    source = manifest.get("source")
    if not isinstance(source, dict) or source.get("endpoint") != EXPECTED_ENDPOINT:
        raise ValueError("TWSE_CALENDAR_SOURCE_MISMATCH")
    records = manifest.get("source_records")
    if not isinstance(records, list) or not records:
        raise ValueError("TWSE_CALENDAR_SOURCE_RECORDS_MISSING")
    if (_sha(records) != EXPECTED_SOURCE_RECORDS_SHA256 or
            source.get("source_records_sha256") != EXPECTED_SOURCE_RECORDS_SHA256):
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
        "schema_version": manifest["schema_version"], "market": manifest["market"],
        "calendar_year": manifest["calendar_year"], "roc_year": manifest["roc_year"],
        "timezone": manifest["timezone"], "base_rule": manifest["base_rule"],
        "closed_dates": closed, "explicit_open_dates": opened,
        "source": {"publisher": source.get("publisher"), "endpoint": source.get("endpoint"),
                   "source_records_sha256": source.get("source_records_sha256")},
    }
    fingerprint = _sha(core)
    if (fingerprint != EXPECTED_BASE_CALENDAR_FINGERPRINT_SHA256 or
            manifest.get("calendar_fingerprint_sha256") != fingerprint):
        raise ValueError("TWSE_CALENDAR_FINGERPRINT_MISMATCH")
    return manifest


def validate_extraordinary_manifest(manifest) -> dict:
    if not isinstance(manifest, dict):
        raise ValueError("TWSE_EXTRAORDINARY_CLOSURES_NOT_OBJECT")
    expected_keys = {"schema_version", "market", "calendar_year", "timezone", "authority",
                     "closures", "closures_sha256", "extraordinary_closure_fingerprint_sha256"}
    if set(manifest) != expected_keys:
        raise ValueError("TWSE_EXTRAORDINARY_CLOSURES_SCHEMA_MISMATCH")
    if (manifest.get("schema_version") != 1 or manifest.get("market") != "TWSE" or
            manifest.get("calendar_year") != CALENDAR_YEAR or manifest.get("timezone") != "Asia/Taipei" or
            manifest.get("authority") != "TAIPEI_CITY_GOVERNMENT_PLUS_TWSE_NATURAL_DISASTER_RULE"):
        raise ValueError("TWSE_EXTRAORDINARY_CLOSURES_AUTHORITY_MISMATCH")
    closures = manifest.get("closures")
    if not isinstance(closures, list) or not closures:
        raise ValueError("TWSE_EXTRAORDINARY_CLOSURES_MISSING")
    if (_sha(closures) != EXPECTED_EXTRAORDINARY_CLOSURES_SHA256 or
            manifest.get("closures_sha256") != EXPECTED_EXTRAORDINARY_CLOSURES_SHA256):
        raise ValueError("TWSE_EXTRAORDINARY_CLOSURES_HASH_MISMATCH")
    seen = set()
    for row in closures:
        if not isinstance(row, dict) or set(row) != {"date", "kind", "reason", "evidence"}:
            raise ValueError("TWSE_EXTRAORDINARY_CLOSURE_RECORD_SCHEMA_MISMATCH")
        ds = _as_date(row["date"])
        if ds.year != CALENDAR_YEAR or row["date"] in seen or row["kind"] != "CLOSED":
            raise ValueError("TWSE_EXTRAORDINARY_CLOSURE_DATE_OR_KIND_INVALID")
        seen.add(row["date"])
        evidence = row["evidence"]
        if not isinstance(evidence, list) or len(evidence) < 2:
            raise ValueError("TWSE_EXTRAORDINARY_CLOSURE_EVIDENCE_MISSING")
        urls = {item.get("url") for item in evidence if isinstance(item, dict)}
        if EXPECTED_TAIPEI_EOC_URL not in urls or EXPECTED_TWSE_SUSPENSION_URL not in urls:
            raise ValueError("TWSE_EXTRAORDINARY_CLOSURE_EVIDENCE_AUTHORITY_MISMATCH")
    core = {"schema_version": manifest["schema_version"], "market": manifest["market"],
            "calendar_year": manifest["calendar_year"], "timezone": manifest["timezone"],
            "authority": manifest["authority"], "closures": closures}
    fingerprint = _sha(core)
    if (fingerprint != EXPECTED_EXTRAORDINARY_FINGERPRINT_SHA256 or
            manifest.get("extraordinary_closure_fingerprint_sha256") != fingerprint):
        raise ValueError("TWSE_EXTRAORDINARY_CLOSURE_FINGERPRINT_MISMATCH")
    return manifest


def _effective(base: dict, extraordinary: dict) -> dict:
    base = _validate_base_manifest(base)
    extraordinary = validate_extraordinary_manifest(extraordinary)
    result = copy.deepcopy(base)
    result["authority"] = EFFECTIVE_AUTHORITY
    result["base_calendar_fingerprint_sha256"] = EXPECTED_BASE_CALENDAR_FINGERPRINT_SHA256
    result["extraordinary_closure_fingerprint_sha256"] = EXPECTED_EXTRAORDINARY_FINGERPRINT_SHA256
    result["extraordinary_closures"] = copy.deepcopy(extraordinary["closures"])
    result["closed_dates"] = sorted(set(base["closed_dates"]) | {row["date"] for row in extraordinary["closures"]})
    result["calendar_fingerprint_sha256"] = EXPECTED_EFFECTIVE_CALENDAR_FINGERPRINT_SHA256
    return result


def _validate_effective_manifest(manifest) -> dict:
    if not isinstance(manifest, dict) or manifest.get("authority") != EFFECTIVE_AUTHORITY:
        raise ValueError("TWSE_EFFECTIVE_CALENDAR_AUTHORITY_MISMATCH")
    expected = {
        "base_calendar_fingerprint_sha256": EXPECTED_BASE_CALENDAR_FINGERPRINT_SHA256,
        "extraordinary_closure_fingerprint_sha256": EXPECTED_EXTRAORDINARY_FINGERPRINT_SHA256,
        "calendar_fingerprint_sha256": EXPECTED_EFFECTIVE_CALENDAR_FINGERPRINT_SHA256,
    }
    if any(manifest.get(k) != v for k, v in expected.items()):
        raise ValueError("TWSE_EFFECTIVE_CALENDAR_LINEAGE_MISMATCH")
    closures = manifest.get("extraordinary_closures")
    if not isinstance(closures, list) or _sha(closures) != EXPECTED_EXTRAORDINARY_CLOSURES_SHA256:
        raise ValueError("TWSE_EFFECTIVE_CALENDAR_CLOSURE_MISMATCH")
    # Reconstruct the immutable annual layer and verify it independently.
    base = copy.deepcopy(manifest)
    base["authority"] = BASE_AUTHORITY
    base["closed_dates"] = [d for d in base.get("closed_dates", []) if d not in {r["date"] for r in closures}]
    base["calendar_fingerprint_sha256"] = EXPECTED_BASE_CALENDAR_FINGERPRINT_SHA256
    for key in ("base_calendar_fingerprint_sha256", "extraordinary_closure_fingerprint_sha256", "extraordinary_closures"):
        base.pop(key, None)
    _validate_base_manifest(base)
    expected_closed = sorted(set(base["closed_dates"]) | {row["date"] for row in closures})
    if manifest.get("closed_dates") != expected_closed:
        raise ValueError("TWSE_EFFECTIVE_CALENDAR_CLASSIFICATION_MISMATCH")
    effective_core = {
        "base_calendar_fingerprint_sha256": EXPECTED_BASE_CALENDAR_FINGERPRINT_SHA256,
        "extraordinary_closure_fingerprint_sha256": EXPECTED_EXTRAORDINARY_FINGERPRINT_SHA256,
    }
    if _sha(effective_core) != EXPECTED_EFFECTIVE_CALENDAR_FINGERPRINT_SHA256:
        raise ValueError("TWSE_EFFECTIVE_CALENDAR_FINGERPRINT_MISMATCH")
    return manifest


def validate_manifest(manifest) -> dict:
    """Validate either the immutable annual base or the composed effective calendar."""
    if isinstance(manifest, dict) and manifest.get("authority") == EFFECTIVE_AUTHORITY:
        return _validate_effective_manifest(manifest)
    return _validate_base_manifest(manifest)


def load_manifest(path: Path | str | None = None) -> tuple[dict, Path, str]:
    selected = Path(path).resolve() if path is not None else default_manifest_path()
    base_raw = selected.read_bytes()
    base = _validate_base_manifest(strict_loads(base_raw))
    extraordinary_path = default_extraordinary_manifest_path()
    extraordinary_raw = extraordinary_path.read_bytes()
    extraordinary = validate_extraordinary_manifest(strict_loads(extraordinary_raw))
    manifest = _effective(base, extraordinary)
    lineage = hashlib.sha256(base_raw + b"\0" + extraordinary_raw).hexdigest()
    return manifest, selected, lineage


def is_trading_day(value, manifest: dict) -> bool:
    manifest = _validate_effective_manifest(manifest)
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
    _validate_effective_manifest(manifest)
    return EXPECTED_EFFECTIVE_CALENDAR_FINGERPRINT_SHA256
