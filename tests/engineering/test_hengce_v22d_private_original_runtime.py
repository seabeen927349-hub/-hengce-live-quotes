"""Safeguard V2.2-D original-checkpoint private replay and scan routing."""
import copy
import datetime as dt
import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path

from scripts.hengce_v22d_private_original_inference import (
    MODEL_HASH, REG_HASH, PRICE_HASH, TDCC_HASH,
    KNOWN_20261111_CANONICAL_HASH, FEATURES)
from scripts.hengce_v22d_private_replay_reader import read_private_replay
from scripts.hengce_scan_once_router import report

NOW = dt.datetime.fromisoformat("2026-11-12T09:50:00+08:00")
ROOT = Path(__file__).resolve().parents[2]


def signed(obj):
    x = copy.deepcopy(obj)
    x.pop("receipt_sha256", None)
    x["receipt_sha256"] = hashlib.sha256(
        json.dumps(x, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode("utf-8")).hexdigest()
    return x


def fixture():
    # Synthetic test-only attribution; the actual private checkpoint is
    # verified separately against source SHA and its real model predictions.
    score = 0.5752304792404175
    raw = math.log(score/(1-score))
    audit = {
        "method": "LIGHTGBM_TREE_SHAP_RAW_LOG_ODDS",
        "model_target": "CURRENT_WEEK_LE10_HOLDERS_VS_TWO_WEEKS_PRIOR_DECREASE_GE_1PCT",
        "baseline_raw_log_odds": 0.0,
        "feature_inputs": {feature: 0.0 for feature in FEATURES},
        "feature_contributions_raw_log_odds":
            {feature: (raw if feature=="ret20" else 0.0) for feature in FEATURES},
        "raw_log_odds": raw,
        "sum_reconstructed_raw_log_odds": raw,
        "sigmoid_reconstructed_score": score,
        "score_is_calibrated_probability": False,
        "score_is_expected_stock_return": False,
    }
    return signed({
        "schema": "HENGCE_V22D_PRIVATE_ORIGINAL_CHECKPOINT_REPLAY_V1",
        "system": "HENGCE", "model_id": "v22d_daily_nowcast_liquidity_top5_v1",
        "status": "RESEARCH_REPLAY_NOT_PIT_CERTIFIED",
        "decision_date": "2026-11-11",
        "generated_at_taipei": "2026-11-12T09:40:00+08:00",
        "fixed_cohort_count": 781, "feature_coverage": 737,
        "qualified_count": 1,
        "score_formula": "SIGMOID(BASE_LOG_ODDS_PLUS_16_FEATURE_CONTRIBUTIONS)",
        "score_feature_order": list(FEATURES),
        "target_event": "CURRENT_WEEK_LE10_HOLDERS_VS_TWO_WEEKS_PRIOR_DECREASE_GE_1PCT",
        "score_cutoff": 0.50,
        "score_explanations_are_causal_effects": False,
        "last_assumed_tdcc_snapshot": "2026-10-22",
        "source_sha256": {
            "original_prices": PRICE_HASH, "original_tdcc": TDCC_HASH,
            "original_2026_canonical": KNOWN_20261111_CANONICAL_HASH,
            "classifier": MODEL_HASH, "regressor": REG_HASH},
        "historical_tdcc_first_observed_pit_certified": False,
        "prediction_is_real_daily_retail_count": False,
        "score_is_calibrated_probability": False,
        "current_selection": False, "retrospective_only": True,
        "trading_authority": False, "formal_selection_authority": False,
        "buy_signal": False, "sell_signal": False, "broker_execution": False,
        "capital_authority_twd": 0, "authorized_lots": 0,
        "top5": [{"rank": 1, "ticker": "1802",
                  "daily_decline_score": 0.5752304792404175,
                  "return_20d": 0.20787394, "return_5d": 0.14992499,
                  "median_20d_turnover_twd": 8860158976.0,
                  "last_assumed_available_tdcc_date": "2026-10-22",
                  "last_known_le10_holder_count": 191579.0,
                  "estimated_week_end_le10_holder_count": 190423.8,
                  "last_verified_close": 76.7,
                  "score_explanation": audit}]
    })


class V22DPrivateOriginalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "private_replay.json"

    def put(self, payload):
        self.path.write_text(json.dumps(payload, ensure_ascii=False),
                             encoding="utf-8")
        return read_private_replay(self.path, NOW)

    def test_importable_without_private_weights_or_vessel_downloads(self):
        self.assertEqual(len(FEATURES), 16)
        self.assertEqual(len({*FEATURES}), 16)
        self.assertEqual(len(MODEL_HASH), 64)
        self.assertEqual(len(REG_HASH), 64)
        self.assertEqual(len(PRICE_HASH), 64)
        self.assertEqual(len(TDCC_HASH), 64)
        self.assertEqual(read_private_replay(now=NOW)["status"],
                         "PRIVATE_ORIGINAL_MODEL_REPLAY_NOT_ATTACHED")

    def test_private_replay_is_only_research_not_formal_live(self):
        x = self.put(fixture())
        self.assertEqual(x["status"],
                         "PRIVATE_V22D_ORIGINAL_REPLAY_VERIFIED_RESEARCH_ONLY")
        self.assertEqual([y["ticker"] for y in x["top5"]], ["1802"])
        self.assertEqual(x["model_coverage"], 737)
        self.assertEqual(x["score_audit"],
                         "ALL_TOP5_16_FEATURE_CONTRIBUTIONS_RECONSTRUCTED")
        self.assertFalse(x["buy_signal"])
        self.assertFalse(x["current_selection"])
        self.assertFalse(x["formal_selection_authority"])
        self.assertFalse(x["broker_execution"])

    def test_tamper_rejected_by_receipt_sha(self):
        p = fixture()
        p["top5"][0]["ticker"] = "3042"
        self.assertEqual(self.put(p)["status"], "PRIVATE_REPLAY_RECEIPT_REJECTED")

    def test_resigned_fake_score_or_missing_feature_rejected(self):
        p = fixture()
        p["top5"][0]["daily_decline_score"] = 0.9
        self.assertEqual(self.put(signed(p))["status"],
                         "PRIVATE_REPLAY_SCORE_AUDIT_REJECTED")
        p = fixture()
        p["top5"][0]["score_explanation"]["feature_contributions_raw_log_odds"]["ret20"] += 0.15
        self.assertEqual(self.put(signed(p))["status"],
                         "PRIVATE_REPLAY_SCORE_AUDIT_REJECTED")
        p = fixture()
        p["top5"][0]["score_explanation"]["feature_inputs"].pop("netfrac")
        self.assertEqual(self.put(signed(p))["status"],
                         "PRIVATE_REPLAY_SCORE_AUDIT_REJECTED")
        p = fixture()
        p["score_feature_order"] = list(reversed(FEATURES))
        self.assertEqual(self.put(signed(p))["status"],
                         "PRIVATE_REPLAY_RECEIPT_REJECTED")

    def test_all_authority_and_source_substitutions_rejected(self):
        for field, bad in [
            ("fixed_cohort_count", 787), ("broker_execution", True),
            ("buy_signal", True), ("formal_selection_authority", True),
            ("current_selection", True), ("retrospective_only", False),
            ("historical_tdcc_first_observed_pit_certified", True),
            ("decision_date", "2026-11-13"),
            ("generated_at_taipei", "2026-11-13T10:00:00+08:00"),
        ]:
            with self.subTest(field=field):
                p = fixture()
                p[field] = bad
                self.assertEqual(self.put(signed(p))["status"],
                                 "PRIVATE_REPLAY_RECEIPT_REJECTED")
        p = fixture()
        p["source_sha256"]["classifier"] = "0" * 64
        self.assertEqual(self.put(signed(p))["status"], "PRIVATE_REPLAY_RECEIPT_REJECTED")

    def test_missing_private_model_never_falls_back_to_v22(self):
        bad = {"schema": "HENGCE_V22D_PRIVATE_ORIGINAL_CHECKPOINT_REPLAY_V1",
               "status": "CURRENT_V22D_PIT_TOP5_VERIFIED",
               "top5": [{"ticker": "3042", "rank": 1}]}
        self.assertNotEqual(self.put(bad)["status"],
                            "PRIVATE_V22D_ORIGINAL_REPLAY_VERIFIED_RESEARCH_ONLY")

    def test_original_router_retirement_lock_unmodified(self):
        self.put(fixture())
        out = report(NOW, ROOT, v22d_private_report=str(self.path))
        replay = out["reporting"]["v22d_private_original_model_replay"]
        self.assertEqual(replay["status"],
                         "PRIVATE_V22D_ORIGINAL_REPLAY_VERIFIED_RESEARCH_ONLY")
        self.assertEqual(out["status"], "NO_ACTIVE_SELECTION_STRATEGY")
        self.assertEqual(out["rows"], [])
        self.assertFalse(out["buy_signal"])
        self.assertFalse(out["broker_order_execution"])
        self.assertEqual(out["reporting"]["v22d_primary_research_top5"]["current_selection"],
                         False)


if __name__ == "__main__":
    unittest.main()
