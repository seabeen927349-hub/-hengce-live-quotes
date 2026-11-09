"""Fail-closed governance regression for HENGCE capital-cycle interpretation.

The original 5D/TDCC surveillance remains operational, but it cannot authorize
sowing, fertilizing, harvesting, withdrawal or capital-rotation stage claims.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from hengce_hba_daily_surveillance import scan
from hengce_hba_context_bridge_v1 import build

CONTRACT = ROOT / "governance/HENGCE_LONGITUDINAL_CAPITAL_CYCLE_HARD_GATE_v1_20261109.json"
RULE = ROOT / "governance/HENGCE_LONGITUDINAL_CAPITAL_CYCLE_HARD_GATE_v1_20261109.md"
CONSTITUTION = ROOT / "governance/HENGCE_RESEARCH_LITERATURE_FIRST_CONSTITUTION_v1.md"
UNVERIFIED = "HISTORICAL_CYCLE_UNVERIFIED"


class LongitudinalCapitalCycleGateTests(unittest.TestCase):
    def test_global_governance_is_active_and_preserves_prior_gates(self):
        cfg = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(cfg["status"], "ACTIVE_FAIL_CLOSED_HISTORICAL_PHASE_CLAIMS")
        self.assertEqual(cfg["unknown_historical_phase_state"], UNVERIFIED)
        self.assertFalse(cfg["short_window_surveillance"]["can_assert_historical_sowing_fertilizing_harvesting_or_rotation"])
        self.assertFalse(cfg["gross_turnover_summary"]["sufficient_to_assign_historical_cycle_stage"])
        self.assertTrue(cfg["governance"]["literature_first_constitution_still_required"])
        self.assertFalse(cfg["governance"]["grants_selection_or_trade_authority"])
        rule = RULE.read_text(encoding="utf-8")
        self.assertIn("不得先指定每輪", rule)
        self.assertIn("失敗", rule)
        self.assertIn("反證", rule)
        self.assertIn("短期雷達", rule)
        self.assertIn(CONTRACT.name, CONSTITUTION.read_text(encoding="utf-8"))

    def test_prior_eight_stock_phase_claims_marked_invalid(self):
        cfg = json.loads(CONTRACT.read_text(encoding="utf-8"))
        legacy = cfg["invalidated_short_window_phase_claims"]
        self.assertEqual(set(legacy["ticker_set"]),
                         {"2330","2454","2317","2408","6239","6446","3653","2412"})
        self.assertEqual(legacy["prior_interpretations"],
                         "PROVISIONAL_INVALID_AS_HISTORICAL_PHASE_CLAIM")
        self.assertTrue(legacy["original_raw_evidence_retained"])

    def test_daily_scan_cannot_promote_short_window_to_longitudinal_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = scan(Path(tmp), "2026-11-09")
        self.assertEqual(r["capital_cycle_claim_gate"]["status"], UNVERIFIED)
        self.assertFalse(r["capital_cycle_claim_gate"]["historical_phase_claim_authorized"])
        self.assertEqual(r["capital_cycle_claim_gate"]["stage_scope"], "SHORT_WINDOW_SURVEILLANCE_ONLY")
        self.assertEqual(r["data_gate"], "BLOCKED")

    def test_context_bridge_even_with_historical_candidate_is_unverified(self):
        original = {
            "target_tw_date":"2026-11-09","latest_verified_eod":"2026-11-06",
            "data_gate":"EOD_VALID_MACRO_UNKNOWN",
            "candidates":[{"ticker":"2330","stage":"行情確認（待人工評估）"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            result = build(Path(tmp), original)
        self.assertEqual(result["capital_cycle_claim_gate"]["status"], UNVERIFIED)
        self.assertFalse(result["capital_cycle_claim_gate"]["historical_phase_claim_authorized"])
        self.assertEqual(result["candidates"][0]["historical_cycle_stage"], UNVERIFIED)
        self.assertFalse(result["candidates"][0]["historical_phase_claim_authorized"])
        self.assertEqual(result["candidates"][0]["original_stage_scope"], "SHORT_WINDOW_SURVEILLANCE_ONLY")

if __name__ == "__main__":
    unittest.main()
