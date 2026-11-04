#!/usr/bin/env python3
"""Offline tests: synthetic snapshots only; zero provider network requests."""
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from hengce_finmind_single_name_bridge import lookup, public_status, HENGCE_LIVE_TTL_SECONDS

NOW = datetime(2026, 11, 4, 9, 13, tzinfo=ZoneInfo("Asia/Taipei"))
ALLOWED = {"3042", "2330", "2408"}

def make(ticker="3042", timestamp=NOW, price=154.5):
    return {"stock_id":ticker, "date":timestamp.isoformat(), "close":price,
        "open":149.0, "high":155.0, "low":148.0,
        "average_price":151.2, "total_volume":500, "total_amount":200000}

class Tests(unittest.TestCase):
    def test_one_snapshot_multiple_names_no_refetch(self):
        snapshot={s:make(ticker=s) for s in ALLOWED}
        for ticker in ("3042","2330","2408"):
            quote,state=lookup(snapshot,ticker,NOW,ALLOWED)
            self.assertEqual(state,"READY_IN_RUNNER_MEMORY_ONLY")
            self.assertEqual(quote.price,154.5)
            self.assertNotIn("154.5",repr(quote))
        status=public_status(snapshot,["3042","2330"],NOW,ALLOWED)
        self.assertNotIn("154.5",str(status))
        self.assertTrue(status["single_fetch_reused"])
        self.assertFalse(status["paid_quote_values_in_public_repo"])
        self.assertFalse(status["trading_authority_created"])

    def test_fail_closed_invalid_universe_or_missing(self):
        snapshot={"3042":make()}
        for code,expected in [("not-a-ticker","INVALID_TICKER"),("9999","OUTSIDE_GOVERNED_TWSE_UNIVERSE"),("2330","NOT_IN_SNAPSHOT")]:
            self.assertEqual(lookup(snapshot,code,NOW,ALLOWED)[1],expected)

    def test_fail_closed_stale_previous_day(self):
        for seconds,expected in [(481,"STALE_GT_480_SECONDS"),(86400,"NOT_CURRENT_MARKET_DATE")]:
            q,s=lookup({"3042":make(timestamp=NOW-timedelta(seconds=seconds))},"3042",NOW,ALLOWED)
            self.assertIsNone(q)
            self.assertEqual(s,expected)

    def test_fail_closed_bad_price_and_clock(self):
        self.assertEqual(lookup({"3042":make(price=None)},"3042",NOW,ALLOWED)[1],"LAST_PRICE_UNAVAILABLE")
        self.assertEqual(lookup({"3042":make(timestamp=NOW+timedelta(minutes=4))},"3042",NOW,ALLOWED)[1],"FUTURE_TIMESTAMP")
        self.assertEqual(lookup({"3042":make()},"3042",NOW.replace(tzinfo=None),ALLOWED)[1],"NOW_MISSING_TIMEZONE")

    def test_ttl(self):
        self.assertEqual(HENGCE_LIVE_TTL_SECONDS,480)

if __name__=="__main__":
    unittest.main()
