"""Regression: actual checked-in 2026-11-06 research receipt is visible in scan-once.

Unlike fixture-only tests, validates the real published receipt at its runtime path.
"""
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts"))
import hengce_scan_once_router as scan


class PublishedV22HistoricalReceiptTests(unittest.TestCase):
    def test_real_published_historical_top5_is_visible_but_not_an_order(self):
        now = datetime.fromisoformat("2026-11-10T22:38:00+08:00")
        result=scan.report(now, ROOT)
        research=result["reporting"]["v22_research_top5"]
        self.assertEqual(research["status"],"HISTORICAL_RESEARCH_TOP5_VERIFIED")
        self.assertEqual(research["source_date"],"2026-11-06")
        self.assertEqual(research["qualified_count"],7)
        self.assertEqual([r["ticker"] for r in research["top5"]],
                         ["6446","2412","1476","2610","2254"])
        self.assertEqual(result["status"],"NO_ACTIVE_SELECTION_STRATEGY")
        self.assertEqual(result["rows"],[])
        self.assertEqual(result["reporting"]["top10"],[])
        self.assertEqual(result["reporting"]["action_card"]["status"],"NO_BUY")
        self.assertFalse(result["broker_order_execution"])
        self.assertFalse(research["current_selection"])
        self.assertFalse(research["buy_signal"])
        self.assertFalse(research["broker_execution"])
        self.assertTrue(all(r["authorized_lots"]==0 for r in research["top5"]))


if __name__=="__main__":
    unittest.main()
