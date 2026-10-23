#!/usr/bin/env python3
from __future__ import annotations

import copy

import hengce_twse_calendar as calendar


def main():
    manifest, path, raw_sha = calendar.load_manifest()
    assert path.name == calendar.MANIFEST_NAME
    assert len(raw_sha) == 64
    assert calendar.manifest_fingerprint(manifest) == calendar.EXPECTED_CALENDAR_FINGERPRINT_SHA256

    assert calendar.is_trading_day("2026-10-23", manifest) is True
    assert calendar.is_trading_day("2026-10-24", manifest) is False
    assert calendar.is_trading_day("2026-10-25", manifest) is False
    assert calendar.is_trading_day("2026-10-26", manifest) is False
    assert calendar.is_trading_day("2026-10-27", manifest) is True
    assert calendar.next_trading_day("2026-10-23", manifest) == "2026-10-27"
    calendar.validate_next_session("2026-10-23", "2026-10-27", manifest)

    assert calendar.is_trading_day("2026-02-11", manifest) is True
    assert calendar.is_trading_day("2026-02-12", manifest) is False
    assert calendar.next_trading_day("2026-02-11", manifest) == "2026-02-23"
    calendar.validate_next_session("2026-02-11", "2026-02-23", manifest)

    try:
        calendar.validate_next_session("2026-10-23", "2026-10-26", manifest)
    except ValueError as exc:
        assert "TRADE_DATE_NOT_TWSE_TRADING_DAY" in str(exc)
    else:
        raise AssertionError("official closure acquired trade-session authority")

    tampered = copy.deepcopy(manifest)
    tampered["closed_dates"].remove("2026-10-26")
    try:
        calendar.validate_manifest(tampered)
    except ValueError as exc:
        assert "CLASSIFICATION_MISMATCH" in str(exc)
    else:
        raise AssertionError("tampered calendar classification was accepted")

    tampered = copy.deepcopy(manifest)
    tampered["source_records"][0]["date"] = "2026-01-02"
    try:
        calendar.validate_manifest(tampered)
    except ValueError as exc:
        assert "SOURCE_RECORDS_HASH_MISMATCH" in str(exc)
    else:
        raise AssertionError("tampered official records were accepted")

    print("TWSE_OFFICIAL_CALENDAR_TEST_PASS")


if __name__ == "__main__":
    main()
