#!/usr/bin/env python3
from __future__ import annotations

import copy

import hengce_twse_calendar as calendar


def main():
    manifest, path, lineage_sha = calendar.load_manifest()
    assert path.name == calendar.MANIFEST_NAME
    assert len(lineage_sha) == 64
    assert manifest["authority"] == calendar.EFFECTIVE_AUTHORITY
    assert calendar.manifest_fingerprint(manifest) == calendar.EXPECTED_EFFECTIVE_CALENDAR_FINGERPRINT_SHA256

    # 2026-10-23 was an extraordinary typhoon closure, not an annual holiday.
    assert calendar.is_trading_day("2026-10-22", manifest) is True
    assert calendar.is_trading_day("2026-10-23", manifest) is False
    assert calendar.is_trading_day("2026-10-24", manifest) is False
    assert calendar.is_trading_day("2026-10-25", manifest) is False
    assert calendar.is_trading_day("2026-10-26", manifest) is False
    assert calendar.is_trading_day("2026-10-27", manifest) is True
    assert calendar.next_trading_day("2026-10-22", manifest) == "2026-10-27"
    calendar.validate_next_session("2026-10-22", "2026-10-27", manifest)

    try:
        calendar.validate_next_session("2026-10-23", "2026-10-27", manifest)
    except ValueError as exc:
        assert "SIGNAL_DATE_NOT_TWSE_TRADING_DAY" in str(exc)
    else:
        raise AssertionError("typhoon closure acquired signal-session authority")

    try:
        calendar.validate_next_session("2026-10-22", "2026-10-23", manifest)
    except ValueError as exc:
        assert "TRADE_DATE_NOT_TWSE_TRADING_DAY" in str(exc)
    else:
        raise AssertionError("typhoon closure acquired trade-session authority")

    assert calendar.is_trading_day("2026-02-11", manifest) is True
    assert calendar.is_trading_day("2026-02-12", manifest) is False
    assert calendar.next_trading_day("2026-02-11", manifest) == "2026-02-23"
    calendar.validate_next_session("2026-02-11", "2026-02-23", manifest)

    tampered = copy.deepcopy(manifest)
    tampered["closed_dates"].remove("2026-10-23")
    try:
        calendar.validate_manifest(tampered)
    except ValueError as exc:
        assert "CLASSIFICATION_MISMATCH" in str(exc)
    else:
        raise AssertionError("tampered effective closure classification was accepted")

    tampered = copy.deepcopy(manifest)
    tampered["extraordinary_closures"][0]["date"] = "2026-10-22"
    try:
        calendar.validate_manifest(tampered)
    except ValueError as exc:
        assert "CLOSURE_MISMATCH" in str(exc)
    else:
        raise AssertionError("tampered extraordinary closure evidence was accepted")

    print("TWSE_EFFECTIVE_CALENDAR_TEST_PASS")


if __name__ == "__main__":
    main()
