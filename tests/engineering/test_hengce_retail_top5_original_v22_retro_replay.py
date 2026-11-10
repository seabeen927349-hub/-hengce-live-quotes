import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hengce_retail_top5_original_v22_retro_replay as replay

MODEL = ROOT / "original_v22_model"


@unittest.skipUnless(MODEL.is_dir(), "Pinned original V2.2 PR64 checkout required")
class OriginalCodeRetrospectiveReplayTests(unittest.TestCase):
    def test_actual_hengce_g1_tdcc_plus_21day_mother_uses_original_screen(self):
        result = replay.replay(ROOT, MODEL, today=date(2026,11,10))
        self.assertEqual(result["original_unmerged_model_commit"], replay.ORIGINAL_MODEL_COMMIT)
        self.assertEqual(result["model_method"], "ORIGINAL_V22_SCREEN_ELIGIBLE_STOCKS_LAG14")
        self.assertEqual(result["price_original_eod_days"], 13)
        self.assertEqual(result["price_mother_recovered_days"], 8)
        self.assertEqual(result["retail_input_rows"],3248)
        self.assertEqual(result["retail_snapshot_count"],3)
        self.assertGreaterEqual(result["qualified_count"],0)
        self.assertLessEqual(len(result["historical_research_top5"]),5)
        self.assertFalse(result["official_pit_certified"])
        self.assertFalse(result["formal_selection_performed"])
        self.assertFalse(result["broker_execution"])
        self.assertEqual(result["authorized_lots"],0)

    def test_actual_top5_maintains_original_v22_parameters(self):
        x = replay.replay(ROOT,MODEL,today=date(2026,11,10))
        tickers = [r["ticker"] for r in x["historical_research_top5"]]
        self.assertEqual(len(set(tickers)),len(tickers))
        for r in x["historical_research_top5"]:
            self.assertGreaterEqual(r["r20_pct"],5)
            self.assertGreaterEqual(r["r5_pct"],0)
            self.assertLessEqual(r["retail_2week_pct"],-1)
            self.assertGreaterEqual(r["median_20d_turnover_twd"],10_000_000)
            self.assertEqual(r["chip_date"],"2026-10-22")

    def test_replay_does_not_become_select_stocks_prospective(self):
        x=replay.replay(ROOT,MODEL,today=date(2026,11,10))
        self.assertEqual(x["model_literature_gate"],"NOT_PASSED")
        self.assertEqual(x["research_scope"],"POSTFACTO_RESEARCH_BACKFILL_ONLY_NO_CLEAN_PIT")
        self.assertEqual(x["action"],"RESEARCH_ONLY_NO_TRADING_AUTHORITY")
        self.assertNotIn("orders",x)
        self.assertNotIn("selection.json",x)

    def test_wrong_date_denied(self):
        with self.assertRaisesRegex(replay.DataBlocked,"MUST_BE_20261106"):
            replay.replay(ROOT,MODEL,decision=date(2026,11,13),today=date(2026,11,14))

    def test_original_model_commit_must_match(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(replay.DataBlocked,"ORIGINAL_V22_GIT_PROVENANCE_UNAVAILABLE"):
                replay.original_screen_module(Path(d))


if __name__=="__main__":
    unittest.main()
