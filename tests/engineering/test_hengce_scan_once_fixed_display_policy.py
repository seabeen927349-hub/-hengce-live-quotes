"""Cross-conversation read-only HENGCE report UI lock; no trading authority."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
PUBLIC=ROOT/"hengce/HENGCE_SCAN_ONCE_CONTRACT_LATEST.json"
GOV=ROOT/"governance/HENGCE_SCAN_ONCE_CONSISTENCY_LOCK_v1_0_20261111.json"
SOURCE_SHA="357585f2ccd37c97adeded6c363a1914c6d67f54"
SECTIONS=[
    "PROTOCOL_AND_DATA_DATE","SINGLE_ORIGINAL_V22D_MODEL",
    "A_B_POSTSCORE_STATUS","A_STRONG_DECLINE_LABEL",
    "ENVIRONMENT_AND_DATA_VESSELS","MISSING_OR_BLOCKED",
    "SOURCE_AND_EXECUTION_AUTHORITY"]
VISIBLE=[
    "ORIGINAL_V22D","A_B_POSTSCORE","A_STRONG_DECLINE_LABEL",
    "ORIGINAL_EOD_THREE_LEGS","HISTORICAL_MOTHER","TDCC_PIT",
    "SOX_VIX_US_SESSION_AND_TW_TARGET",
    "FUGLE_TIMESTAMPED_SINGLE_NAME_OBSERVATION",
    "FINMIND_TIMESTAMPED_INTRADAY","RMS_RESEARCH_STATUS",
    "LEGACY_HEALTH_DATE_ONLY","MISSING_DATA_AND_NO_ORDER_AUTHORITY",
    "GITHUB_PROVENANCE"]
HIDDEN=["S5","Escape"]


class FixedScanDisplayPolicyTests(unittest.TestCase):
    def test_single_readout_pointer_and_private_sha_are_locked(self):
        p=json.loads(PUBLIC.read_text(encoding="utf-8"))
        x=p["fixed_scan_once_v1"]
        self.assertEqual(p["trigger"],"衡策掃一次")
        self.assertEqual(x["canonical_contract_git_blob_sha"],SOURCE_SHA)
        self.assertEqual(x["display_policy_id"],"HENGCE_SCAN_ONCE_FIXED_VISIBLE_REPORT_20261117")
        self.assertEqual(x["private_repository"],"seabeen927349-hub/twse--backfill-test")
        self.assertEqual(x["canonical_contract"],"hengce/private_v22d_autoscan/HENGCE_FIXED_SCAN_CONTRACT_V1.json")
        self.assertEqual(x["readout_json"],"hengce/private_v22d_autoscan/reports/scan_once_fixed_latest.json")
        self.assertTrue(x["cross_chat_read_required"])
        self.assertEqual(p["combined_display_mode"]["id"],"HENGCE_SCAN_ONCE_V22D_B_COMBINED_DISPLAY_20261120_V1")
        self.assertTrue(p["combined_display_mode"]["display_separate_historical_b_recalc"])
        self.assertTrue(p["combined_display_mode"]["display_independent_signed_b_paper"])
        self.assertTrue(x["cross_chat_display_must_match_private_main"])
        self.assertTrue(x["verified_report_is_the_only_user_visible_report"])
        self.assertEqual(x["hidden_modules"],HIDDEN)
        self.assertEqual(x["visible_modules"],VISIBLE)
        self.assertEqual(x["display_order"],SECTIONS)
        self.assertTrue(x["never_render_hidden_modules_even_if_unverified"])
        self.assertEqual(x["fugle_live_quotes"],"TIMESTAMPED_OBSERVATION_NOT_ORIGINAL_MODEL")
        self.assertTrue(x["no_change_without_explicit_user_authorization"])
        self.assertTrue(x["maintain_no_trading_authority"])
        self.assertEqual(p["active_strategy_count"],0)
        self.assertFalse(p["broker_order_execution"])

    def test_governance_override_prevents_legacy_sections_from_reappearing(self):
        p=json.loads(PUBLIC.read_text(encoding="utf-8"))
        g=json.loads(GOV.read_text(encoding="utf-8"))
        x=g["fixed_visible_scan_once_override"]
        self.assertEqual(x["status"],"ACTIVE_USER_APPROVED_DISPLAY_LOCK")
        self.assertEqual(x["private_contract_git_blob_sha"],SOURCE_SHA)
        self.assertEqual(x["policy_id"],p["fixed_scan_once_v1"]["display_policy_id"])
        self.assertEqual(x["no_hidden_module_display"],HIDDEN)
        self.assertEqual(x["show_user_display_modules_in_order"],VISIBLE)
        self.assertEqual(x["seven_sections_in_order"],SECTIONS)
        self.assertTrue(x["cross_chat_restore_required"])
        self.assertTrue(x["preserve_upstream_module_logic"])
        self.assertTrue(x["not_a_strategy_or_authority_change"])
        self.assertNotIn("S5_Escape_RMS_and_macro_evidence",g["reporting_order"])
        self.assertIn("SOX_VIX_FINMIND_RMS_and_macro_evidence",g["reporting_order"])
        self.assertEqual(g["capital_authority_twd"],0)
        self.assertFalse(g["broker_execution"])


if __name__=="__main__":
    unittest.main()
