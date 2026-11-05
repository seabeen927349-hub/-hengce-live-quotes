"""Regression guard: the single-stock research standard never restores a model or bypasses mother authority."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
class TestSingleStockAnalysisPolicy(unittest.TestCase):
    def test_default_pointer(self):
        p=json.loads((ROOT/"hengce/HENGCE_SINGLE_STOCK_ANALYSIS_DEFAULT_LATEST.json").read_text())
        self.assertTrue(p["automatic_research_when_user_asks"])
        self.assertFalse(p["scheduled_job_created"])
        self.assertFalse(p["trading_authority"])
        self.assertEqual(0,p["active_selection_strategy_count"])
        self.assertTrue((ROOT/p["contract"]).exists())
        self.assertTrue((ROOT/p["readme"]).exists())
    def test_contract_boundaries(self):
        c=json.loads((ROOT/"governance/HENGCE_SINGLE_STOCK_FINMIND_ANALYSIS_CONTRACT_v1_20261105.json").read_text())
        self.assertGreaterEqual(c["lookback_default_years"],10)
        self.assertFalse(c["second_mother_permission"])
        self.assertFalse(c["parallel_collector_permission"])
        self.assertFalse(c["canonical_promotion_permission"])
        self.assertFalse(c["retired_model_reactivation_forbidden"] is False)
        self.assertEqual(0,c["active_selection_strategy_count"])
        self.assertIn("NO_CANONICAL_COVERAGE",c["canonical_market_boundary"]["tpex"])
        self.assertIn("UNADJUSTED_STOCK_PRICE",c["historical_total_return_rule"])
    def test_old_scan_once_remains_disabled(self):
        c=json.loads((ROOT/"hengce/HENGCE_SCAN_ONCE_CONTRACT_LATEST.json").read_text())
        self.assertEqual(0,c["active_strategy_count"])
        self.assertFalse(c["cross_chat_restore_required"])

if __name__=="__main__":
    unittest.main()
