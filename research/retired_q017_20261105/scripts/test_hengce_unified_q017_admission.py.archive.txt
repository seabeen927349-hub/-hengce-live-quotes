#!/usr/bin/env python3
from __future__ import annotations

import copy
from datetime import date, datetime, timedelta

import hengce_q017_canonical_producer as producer
import hengce_unified_candidate_adapter as adapter
import hengce_unified_q017_admission as admission


def artifact():
    start = date(2026, 1, 1)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(36)]
    market = [-0.006 if i >= 31 else (0.003 if i % 2 == 0 else -0.002) for i in range(36)]
    rows = []
    prices = {"1111": 100.0, "2222": 100.0, "3333": 100.0}
    for i, ds in enumerate(dates):
        for ticker, beta in (("1111", .5), ("2222", 1.0), ("3333", 1.5)):
            r1 = market[i] * beta - (0.03 if i == 35 and ticker == "3333" else 0.0)
            prices[ticker] *= 1 + r1
            rows.append({"date": ds, "ticker": ticker, "name": ticker,
                         "close": prices[ticker], "turnover": 30_000_000.0})
    signal = date.fromisoformat(dates[-1])
    sox = []
    p = 100.0
    for i in range(20):
        ds = (signal - timedelta(days=20-i)).isoformat()
        p *= 1 + (-.008 if i >= 12 else .002)
        sox.append({"date": ds, "close": p})
    trade = (signal + timedelta(days=1)).isoformat()
    calendar, _, calendar_sha = producer.twse_calendar.load_manifest()
    return producer.build_artifact(
        rows, sox, trade_date=trade, signal_date=signal.isoformat(),
        generated_at=datetime.fromisoformat(trade + "T08:30:00+08:00"),
        code_commit=admission.VERIFIED_PRODUCER_COMMIT,
        input_hashes={"electronics_history": "2" * 64, "sox_history": "3" * 64,
                      "twse_calendar_manifest": calendar_sha},
        calendar_manifest=calendar, calendar_raw_sha=calendar_sha,
        min_daily_members=3,
    )


def main():
    q = artifact()
    admitted = admission.admit(adapter, q)
    assert admitted is q
    assert admission.VERIFIED_PRODUCER_COMMIT in adapter.VERIFIED_Q017_PRODUCERS
    legacy = {"run_id": "ADMISSION_TEST", "trade_date": q["trade_date"],
              "rows": [{"Ticker": "2330", "AlphaScore": .9, "FormalEntryTrigger": False}]}
    out = adapter.build(legacy, admitted)
    assert out["q017_contract_status"] == "PASS"
    assert out["source_provenance_counts"]["Q017"] == 1

    wrong = copy.deepcopy(q)
    wrong["producer"]["code_commit"] = "f" * 40
    assert admission.admit(adapter, wrong).get("input_error") == "Q017_PRODUCER_COMMIT_NOT_VERIFIED"

    stale = copy.deepcopy(q)
    stale["signal_date"] = stale["trade_date"]
    assert admission.admit(adapter, stale).get("input_error") == "Q017_SIGNAL_DATE_NOT_PRIOR"

    weekend = copy.deepcopy(q)
    weekend["trade_date"] = (date.fromisoformat(weekend["signal_date"]) + timedelta(days=2)).isoformat()
    weekend["candidates"][0]["entry_trade_date"] = weekend["trade_date"]
    assert "Q017_TRADE_DATE_NOT_TWSE_TRADING_DAY" in admission.admit(adapter, weekend).get("input_error", "")

    calendar_tamper = copy.deepcopy(q)
    calendar_tamper["session_calendar"]["manifest_sha256"] = "f" * 64
    assert admission.admit(adapter, calendar_tamper).get("input_error") == "Q017_SESSION_CALENDAR_LINEAGE_MISMATCH"

    # The extraordinary 2026-10-23 typhoon closure must not be signal or entry authority.
    typhoon_signal = copy.deepcopy(q)
    typhoon_signal["signal_date"] = "2026-10-23"
    typhoon_signal["trade_date"] = "2026-10-27"
    typhoon_signal["candidates"][0]["signal_date"] = typhoon_signal["signal_date"]
    typhoon_signal["candidates"][0]["entry_trade_date"] = typhoon_signal["trade_date"]
    assert "Q017_SIGNAL_DATE_NOT_TWSE_TRADING_DAY" in admission.admit(adapter, typhoon_signal).get("input_error", "")

    post_typhoon = copy.deepcopy(q)
    post_typhoon["signal_date"] = "2026-10-22"
    post_typhoon["trade_date"] = "2026-10-27"
    post_typhoon["candidates"][0]["signal_date"] = post_typhoon["signal_date"]
    post_typhoon["candidates"][0]["entry_trade_date"] = post_typhoon["trade_date"]
    assert admission.admit(adapter, post_typhoon) is post_typhoon

    typhoon_trade = copy.deepcopy(post_typhoon)
    typhoon_trade["trade_date"] = "2026-10-23"
    typhoon_trade["candidates"][0]["entry_trade_date"] = typhoon_trade["trade_date"]
    assert "Q017_TRADE_DATE_NOT_TWSE_TRADING_DAY" in admission.admit(adapter, typhoon_trade).get("input_error", "")

    holiday_bad = copy.deepcopy(post_typhoon)
    holiday_bad["trade_date"] = "2026-10-26"
    holiday_bad["candidates"][0]["entry_trade_date"] = holiday_bad["trade_date"]
    assert "Q017_TRADE_DATE_NOT_TWSE_TRADING_DAY" in admission.admit(adapter, holiday_bad).get("input_error", "")

    bad_obs = copy.deepcopy(q)
    bad_obs["candidates"][0]["beta_observations"] = 29
    assert admission.admit(adapter, bad_obs).get("input_error") == "Q017_BETA_OBSERVATIONS_OUT_OF_RANGE"

    geometry = copy.deepcopy(q)
    geometry["candidates"][0]["BreakoutLower"] = 100
    assert admission.admit(adapter, geometry).get("input_error") == "Q017_CANDIDATE_CANNOT_CARRY_GEOMETRY_AUTHORITY"

    print("Q017_REVIEWED_PRODUCER_ADMISSION_TEST_PASS")


if __name__ == "__main__":
    main()
