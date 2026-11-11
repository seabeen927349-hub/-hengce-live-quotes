"""HENGCE V2.2-D checkpoint recovery is evidence, not trading authority."""
import json
import math
import unittest
from pathlib import Path
from datetime import datetime

from scripts.hengce_v22d_daily_reader import observation, selected_v22d
from scripts.hengce_scan_once_router import selected_model_preference

ROOT=Path(__file__).resolve().parents[2]
MANIFEST="research/retail_top5/HENGCE_V22D_ORIGINAL_MODEL_CHECKPOINT_PROVENANCE_20261111.json"
ATR="research/retail_top5/v22d_atr_historical_replay_20261111.json"

class OriginalV22DModelProvenanceTests(unittest.TestCase):
    def test_original_model_sha_and_independent_frozen_replay(self):
        j=json.loads((ROOT/MANIFEST).read_text(encoding="utf8"))
        self.assertEqual(j["model"],"ORIGINAL_V22D_DAILY_MON_THU_LGBM")
        self.assertEqual(j["reproducibility"]["frozen_20261105_predictions_matched"],737)
        self.assertLess(j["reproducibility"]["max_abs_score_difference"],0.0000001)
        self.assertEqual(j["training"]["training_period"],"2019-01-01 through 2022-12-31")
        self.assertEqual(j["training"]["validation_year"],2023)
        self.assertEqual(j["training"]["training_rows"],481862)
        self.assertEqual(len(j["training"]["feature_columns"]),16)
        self.assertEqual(j["original_models_sha256"]["classifier"],
                         "db47b6f2276150610972d50a8f2b1a9d816eb89fc415d41db5c81b12c1c94a97")
        self.assertEqual(j["model_weights_location"]["kind"],"PRIVATE_USER_CHATGPT_LIBRARY")
        self.assertFalse(j["model_weights_location"]["public_github_weights_published"])
        self.assertFalse(j["not_a_daily_live_signal"] is False)
        self.assertFalse(j["broker_execution"])

    def test_model_choice_is_mon_thu_not_fictitious_friday_daily(self):
        j=json.loads((ROOT/"hengce/HENGCE_SELECTION_MODEL_CHOICE_LATEST.json").read_text())
        self.assertEqual(j["selection_method"]["decision"],
                         "MONDAY_THROUGH_THURSDAY_POST_VERIFIED_OFFICIAL_EOD")
        self.assertFalse(j["selection_method"]["friday_daily_nowcast_is_active"])
        self.assertFalse(j["formal_selection_authority"])
        self.assertFalse(j["broker_execution"])
        self.assertTrue(selected_v22d(ROOT))
        self.assertEqual(selected_model_preference(ROOT)["model_id"],
                         "v22d_daily_nowcast_liquidity_top5_v1")

    def test_retro_atr_has_no_fabricated_open_or_sell(self):
        j=json.loads((ROOT/ATR).read_text())
        self.assertEqual(j["historical_primary_v22d_top5"],
                         ["1802","2886","2618","1476","2610"])
        self.assertFalse(j["buy_price_known"])
        self.assertIsNone(j["next_market_buy_price"])
        self.assertFalse(j["replay_published_before_decision"])
        self.assertFalse(j["buy_signal"])
        self.assertFalse(j["sell_signal"])
        self.assertFalse(j["broker_execution"])
        for row in j["rows"]:
            self.assertGreater(row["close"],0)
            self.assertTrue(math.isfinite(row["atr20"]))
            self.assertAlmostEqual(row["atr20"]*2,row["initial_floor_distance_twd"],places=4)
            self.assertIsNone(row["entry_fill_price_twd"])
            self.assertIsNone(row["initial_risk_floor_twd"])

    def test_replaying_decision_same_day_is_still_historical_not_live(self):
        x=observation(datetime.fromisoformat("2026-11-11T23:55:00+08:00"),ROOT)
        self.assertEqual(x["status"],"HISTORICAL_V22D_TOP5_VERIFIED")
        self.assertFalse(x["current_selection"])
        self.assertTrue(x["not_current_recommendations"])

if __name__=="__main__":
    unittest.main()
