#!/usr/bin/env python3
"""Offline quote-only multi-venue equity membership tests: synthetic rows."""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from hengce_finmind_single_name_membership import current_equity_membership

ASOF=date(2026,11,4)

def fixture():
    rows=[
        {"stock_id":str(i), "type":"twse", "date":"2026-11-02",
         "industry_category":"electronics", "stock_name":"S"}
        for i in range(1000,2000)
    ]
    rows += [
        {"stock_id":str(i), "type":"tpex", "date":"2026-11-02",
         "industry_category":"electronics", "stock_name":"S"}
        for i in range(3000,3800)
    ]
    rows += [
        {"stock_id":"3420", "type":"twse", "date":"2026-09-01",
         "industry_category":"electronics", "stock_name":"OLD"},
        {"stock_id":"3420", "type":"tpex", "date":"2026-11-03",
         "industry_category":"electronics", "stock_name":"CURRENT"},
        {"stock_id":"3420", "type":"twse", "date":"2026-11-05",
         "industry_category":"electronics", "stock_name":"FUTURE"},
        {"stock_id":"7888", "type":"emerging", "date":"2026-11-01",
         "industry_category":"technology", "stock_name":"S"},
        {"stock_id":"9929", "type":"twse", "date":"2026-11-02",
         "industry_category":"TDR", "stock_name":"TEST-DR"},
        {"stock_id":"9991", "type":"twse", "date":"2026-11-02",
         "industry_category":"ETF", "stock_name":"ETF"},
    ]
    return rows

class MembershipTests(unittest.TestCase):
    def test_market_transfers_and_all_venues(self):
        membership,counts=current_equity_membership(fixture(),ASOF)
        self.assertEqual(membership["3420"],"tpex")
        self.assertEqual(membership["7888"],"emerging")
        self.assertEqual(counts["twse"],1000)
        self.assertEqual(counts["tpex"],800)
        self.assertEqual(counts["emerging"],1)
        self.assertNotIn("9929",membership)
        self.assertNotIn("9991",membership)

    def test_fail_closed_unverified_coverage(self):
        with self.assertRaisesRegex(RuntimeError,"MEMBERSHIP_COVERAGE_UNVERIFIED"):
            current_equity_membership([
                {"stock_id":"3420","type":"tpex","date":"2026-11-03",
                 "industry_category":"electronics", "stock_name":"X"}
            ],ASOF)

    def test_no_future_data_or_unsupported_types(self):
        rows=fixture()
        rows.append({"stock_id":"7788","type":"tpex","date":"2026-11-05","industry_category":"electronics","stock_name":"FUTURE"})
        rows.append({"stock_id":"7789","type":"warrant","date":"2026-11-04","industry_category":"electronics","stock_name":"W"})
        m,_=current_equity_membership(rows,ASOF)
        self.assertNotIn("7788",m)
        self.assertNotIn("7789",m)

if __name__=="__main__":
    unittest.main()
