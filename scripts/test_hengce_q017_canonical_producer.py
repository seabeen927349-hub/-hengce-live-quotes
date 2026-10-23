#!/usr/bin/env python3
from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import hengce_q017_canonical_producer as q


def synthetic():
    start = date(2026, 1, 1)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(36)]
    market = [-0.006 if i >= 31 else (0.003 if i % 2 == 0 else -0.002) for i in range(36)]
    tickers = [("1111", 0.5), ("2222", 1.0), ("3333", 1.5)]
    prices = {ticker: 100.0 for ticker, _ in tickers}
    rows = []
    for i, ds in enumerate(dates):
        for ticker, beta in tickers:
            r1 = market[i] * beta
            if i == len(dates) - 1 and ticker == "3333":
                r1 -= 0.03
            prices[ticker] *= 1.0 + r1
            rows.append({"date": ds, "ticker": ticker, "name": ticker,
                         "close": prices[ticker], "turnover": 30_000_000.0})
    signal = date.fromisoformat(dates[-1])
    sox_prices = 100.0
    sox = []
    sox_start = signal - timedelta(days=20)
    for i in range(20):
        ds = (sox_start + timedelta(days=i)).isoformat()
        sox_prices *= 1 + (-0.008 if i >= 12 else 0.002)
        sox.append({"date": ds, "close": sox_prices})
    return dates, rows, sox


def build(rows, sox, trade, signal=None):
    calendar, _, calendar_sha = q.twse_calendar.load_manifest()
    return q.build_artifact(
        rows, sox, trade_date=trade, signal_date=signal or rows[-1]["date"],
        generated_at=datetime.fromisoformat(trade + "T08:30:00+08:00"),
        code_commit="1" * 40,
        input_hashes={"electronics_history": "2" * 64, "sox_history": "3" * 64,
                      "twse_calendar_manifest": calendar_sha},
        calendar_manifest=calendar, calendar_raw_sha=calendar_sha,
        min_daily_members=3,
    )


def main():
    dates, rows, sox = synthetic()
    trade = (date.fromisoformat(dates[-1]) + timedelta(days=1)).isoformat()
    artifact = build(rows, sox, trade)
    assert artifact["binding_status"] == "PASS" and artifact["market_state"] == "GO"
    assert artifact["signal_date"] == dates[-1]
    assert artifact["session_calendar"]["authority"] == q.twse_calendar.EFFECTIVE_AUTHORITY
    assert artifact["session_calendar"]["fingerprint_sha256"] == q.twse_calendar.EXPECTED_EFFECTIVE_CALENDAR_FINGERPRINT_SHA256
    assert artifact["producer"]["input_hashes"]["twse_calendar_manifest"] == artifact["session_calendar"]["manifest_sha256"]
    assert artifact["macro_gate"]["dxy_used"] is False
    assert artifact["canonical_q017_contract"]["top_n"] == 1
    assert artifact["canonical_q017_contract"]["signal_day_excluded_from_beta"] is True
    assert len(artifact["candidates"]) == 1
    c = artifact["candidates"][0]
    assert c["ticker"] == "3333" and c["q017_rank"] == 1 and c["qualified"] is True
    assert c["beta_observations"] == 34
    assert math.isclose(c["residual1"], -0.03, rel_tol=0, abs_tol=1e-10), c
    assert math.isclose(c["q017_score"], c["beta60"] * (1 + 25 * 0.03), rel_tol=1e-12)
    assert c["filter_evidence"]["avg_turnover20"] == 30_000_000.0
    assert c["filter_evidence"]["electronics_m1"] < 0
    assert c["filter_evidence"]["electronics_m5"] <= -0.02
    assert c["filter_evidence"]["sox_1d"] <= 0
    assert c["filter_evidence"]["sox_5d"] <= -0.03

    baseline_beta = c["beta60"]
    changed = [dict(r) for r in rows]
    for r in changed:
        if r["date"] == dates[-1] and r["ticker"] == "3333":
            r["close"] *= 0.98
    _, ranked, _ = q.prepare_features(changed, dates[-1], min_daily_members=3)
    top = next(x for x in ranked if x["ticker"] == "3333")
    assert math.isclose(top["beta60"], baseline_beta, rel_tol=1e-12, abs_tol=1e-12)

    bad_sox = [dict(x) for x in sox]
    bad_sox[-1]["close"] = bad_sox[-2]["close"] * 1.10
    cash = build(rows, bad_sox, trade)
    assert cash["market_state"] == "CASH" and cash["candidates"] == []

    same_day = [dict(r) for r in rows]
    for ticker in ("1111", "2222", "3333"):
        same_day.append({"date": trade, "ticker": ticker, "name": ticker,
                         "close": 100.0, "turnover": 30_000_000.0})
    try:
        build(same_day, sox, trade, signal=dates[-1])
    except ValueError as exc:
        assert "SIGNAL_DATE_NOT_LATEST_ELECTRONICS_SESSION" in str(exc) or "NONCAUSAL_HISTORY" in str(exc)
    else:
        raise AssertionError("same-day history was accepted")

    try:
        build(rows, sox, trade, signal=dates[-2])
    except ValueError as exc:
        assert "Q017_NOT_NEXT_TWSE_OPEN" in str(exc)
    else:
        raise AssertionError("stale explicit signal date was accepted")

    weekend = (date.fromisoformat(dates[-1]) + timedelta(days=2)).isoformat()
    try:
        build(rows, sox, weekend, signal=dates[-1])
    except ValueError as exc:
        assert "Q017_TRADE_DATE_NOT_TWSE_TRADING_DAY" in str(exc)
    else:
        raise AssertionError("non-trading entry date was accepted")

    calendar, _, calendar_sha = q.twse_calendar.load_manifest()
    try:
        q.build_artifact(rows, sox, trade_date=trade, signal_date=dates[-1],
            generated_at=datetime.fromisoformat(trade + "T08:30:00+08:00"), code_commit="1"*40,
            input_hashes={"electronics_history":"2"*64,"sox_history":"3"*64,"twse_calendar_manifest":"4"*64},
            calendar_manifest=calendar, calendar_raw_sha=calendar_sha, min_daily_members=3)
    except ValueError as exc:
        assert "TWSE_CALENDAR_INPUT_HASH_MISMATCH" in str(exc)
    else:
        raise AssertionError("mismatched calendar lineage was accepted")

    print("CANONICAL_Q017_PRODUCER_TEST_PASS")


if __name__ == "__main__":
    main()
