#!/usr/bin/env python3
"""Official TX night session: near-month, TAIFEX session date, OHLC and PIT."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from hengce_taifex_tx_night_v1 import parse, canonical, URL, SCHEMA

TZ = ZoneInfo("Asia/Taipei")
AM = dt.datetime(2026,11,19,5,30,tzinfo=TZ)


def row(day="20261119", month="202612", session="盤後", product="TX",
        last="28333", open_="28300", high="28360", low="28250",
        volume="10000"):
    return {
        "Date": day, "Contract": product, "ContractMonth(Week)":month,
        "TradingSession":session, "Open":open_, "High":high,
        "Low":low, "Last":last, "Volume":volume,
    }


def raw(rows):
    return json.dumps(rows,ensure_ascii=False).encode("utf-8")


class TXNightTests(unittest.TestCase):
    def test_official_completed_next_session_front_month(self):
        actual = parse(raw([row(month="202612"),row(month="202701",last="28000",
                               high="28100",low="27900",open_="28020")]), AM)
        self.assertEqual(actual["schema"], SCHEMA)
        self.assertEqual(actual["status"], "OFFICIAL_TX_NIGHT_ASOF_TW_SESSION")
        self.assertEqual(actual["session_date"], "2026-11-19")
        self.assertEqual(actual["contract_month"], "202612")
        self.assertEqual(actual["night_last"], 28333)
        self.assertEqual(actual["trading_session"], "盤後")
        self.assertEqual(actual["source_url"], URL)
        self.assertFalse(actual["night_last_is_cash_close"])
        self.assertFalse(actual["trading_authority"])
        self.assertEqual(actual["receipt_sha256"], canonical(
          {k:v for k,v in actual.items() if k!="receipt_sha256"}))

    def test_before_0515_not_released_as_complete(self):
        with self.assertRaisesRegex(ValueError,"NO_COMPLETED_TX_ROW"):
            parse(raw([row()]),AM.replace(hour=5,minute=4))
        with self.assertRaisesRegex(ValueError,"NO_COMPLETED_TX_ROW"):
            parse(raw([row()]),AM.replace(hour=4,minute=58))

    def test_never_mix_daytime_session(self):
        p = parse(raw([row(),row(session="一般",last="32000",
                                  high="32000",low="31999",open_="32000")]),AM)
        self.assertEqual(p["night_last"],28333)
        with self.assertRaisesRegex(ValueError,"NO_COMPLETED_TX_ROW"):
            parse(raw([row(session="一般")]),AM)

    def test_expired_current_month_disallowed(self):
        # 2026-11-18 was November's 3rd Wednesday expiry.
        p=parse(raw([row(month="202611"),row(month="202612")]),AM)
        self.assertEqual(p["contract_month"],"202612")

    def test_date_and_session_mismatch_blocked(self):
        with self.assertRaisesRegex(ValueError,"TX_NIGHT_FUTURE_SESSION"):
            parse(raw([row(day="20261120")]),AM)
        with self.assertRaisesRegex(ValueError,"TX_NIGHT_OHLC_CONFLICT"):
            parse(raw([row(last="29000")]),AM)
        with self.assertRaisesRegex(ValueError,"TX_NIGHT_NO_COMPLETED_TX_ROW"):
            parse(raw([row(product="MTX")]),AM)

    def test_not_treat_stale_as_current(self):
        p=parse(raw([row(day="20261118")]),AM)
        self.assertEqual(p["status"],"OFFICIAL_TX_NIGHT_HISTORICAL_NOT_CURRENT")

    def test_integrity_and_publisher_isolation(self):
        with self.assertRaisesRegex(ValueError,"TX_NIGHT_UNTRUSTED_REDIRECT|TX_NIGHT_SOURCE_NOT_TAIFEX"):
            parse(raw([row()]),AM,source_url="https://example.org/api")
        with self.assertRaisesRegex(ValueError,"TX_NIGHT_VOLUME_NOT_INTEGER"):
            parse(raw([row(volume="100.5")]),AM)
        with self.assertRaisesRegex(ValueError,"TX_NIGHT_DUPLICATE_CONFLICT"):
            parse(raw([row(),row(last="28330")]),AM)
        with self.assertRaisesRegex(ValueError,"TX_NIGHT_ASOF_TIMEZONE_REQUIRED"):
            parse(raw([row()]),AM.replace(tzinfo=None))

    def test_publisher_exact_lease(self):
        import hengce_publish
        p=hengce_publish.PROFILES["taifex-tx-night"]
        for f in ("environment/taifex_tx_night/latest.json",
                  "environment/taifex_tx_night/history/20261119_sha.json"):
            self.assertTrue(hengce_publish.matches(f,p["writes"]))
        for f in ("eod/20261118/status.json","ownership/tdcc/latest.json",
                  "overseas_premarket/latest.json"):
            self.assertFalse(hengce_publish.matches(f,p["writes"]))


if __name__ == "__main__":
    unittest.main()
