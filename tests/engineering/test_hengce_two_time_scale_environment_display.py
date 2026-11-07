#!/usr/bin/env python3
"""HENGCE dual-horizon display: no inferred capital or fabricated daily signal."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from hengce_two_time_scale_environment_display import (
    build_display, TODAY_LABELS, CAPITAL_LABELS, UNKNOWN
)

TARGET = "2026-11-09"
REFERENCE = "2026-11-06"

def verified(g):
    return {"status":"VERIFIED_GOVERNED_OVERSEAS_SOX_VIX",
            "vendor_price_integrity":True,
            "source_receipt_sha256":"b"*64,
            "grade":g,"expected_gap_log_pct":0.05}

def formal(state):
    return {"schema":"HENGCE_CANONICAL_CAPITAL_ENVIRONMENT_DISPLAY_V1",
            "status":"PASS","source_authority":"HENGCE_CANONICAL_EOD_VERIFIED",
            "canonical_integrity":"PASS","formal_daily_close_ready":True,
            "source_trade_date":REFERENCE,"long_term_capital_state":state,
            "trading_authority":False,"evidence_windows_trading_days":[20,60,120],
            "supporting_flow_evidence":["TEST_SYNTHETIC_PIT_VALIDATED"],
            "canonical_receipt_sha256":"a"*64}

class DualHorizonDisplay(unittest.TestCase):
    def test_both_axes_always_visible(self):
        x=build_display({},TARGET,REFERENCE)
        self.assertEqual(x["today_market_environment"]["label"],UNKNOWN)
        self.assertEqual(x["long_term_capital_environment"]["label"],UNKNOWN)
        self.assertEqual(len(x["today_market_environment"]["allowed_labels"]),5)
        self.assertEqual(len(x["long_term_capital_environment"]["allowed_labels"]),5)
    def test_all_five_daily_labels(self):
        for grade,label in TODAY_LABELS.items():
            with self.subTest(grade=grade):
                x=build_display(verified(grade),TARGET,REFERENCE)
                self.assertEqual(x["today_market_environment"]["label"],label)
                self.assertEqual(x["long_term_capital_environment"]["label"],UNKNOWN)
                self.assertIsNone(x["long_term_capital_environment"].get("formal_state"))
    def test_unknown_is_not_neutral(self):
        x=build_display({},TARGET,REFERENCE)
        self.assertEqual(x["today_market_environment"]["label"],UNKNOWN)
        self.assertNotEqual(x["today_market_environment"]["label"],TODAY_LABELS[3])
        self.assertFalse(x["decision_policy"]["missing_input_is_neutral"])
    def test_unverified_overseas_schema_never_promotes(self):
        s={"status":"PIT_SCHEMA_VERIFIED_UPSTREAM","grade":5,
           "expected_gap_log_pct":0.70}
        x=build_display(s,TARGET,REFERENCE)
        self.assertEqual(x["today_market_environment"]["label"],UNKNOWN)
        self.assertEqual(x["today_market_environment"]["status"],"OVERSEAS_PACKET_SCHEMA_ONLY_NOT_SOURCE_VERIFIED")
    def test_bad_vendor_confirmation_cannot_promote(self):
        p=verified(5);p["vendor_price_integrity"]=False
        self.assertEqual(build_display(p,TARGET,REFERENCE)["today_market_environment"]["label"],UNKNOWN)
        p=verified(5);p["source_receipt_sha256"]="not-a-sha"
        self.assertEqual(build_display(p,TARGET,REFERENCE)["today_market_environment"]["label"],UNKNOWN)
    def test_all_four_capital_labels_accept_only_declared_formal_receipt(self):
        for code,label in CAPITAL_LABELS.items():
            with self.subTest(state=code):
                x=build_display({},TARGET,REFERENCE,formal(code))
                self.assertEqual(x["long_term_capital_environment"]["label"],label)
                self.assertEqual(x["today_market_environment"]["label"],UNKNOWN)
    def test_reject_tampered_or_stale_capital(self):
        p=formal("WITHDRAWAL_CONFIRMED");p["source_trade_date"]="2026-11-05"
        x=build_display({},TARGET,REFERENCE,p)
        self.assertEqual(x["long_term_capital_environment"]["label"],UNKNOWN)
        self.assertEqual(x["long_term_capital_environment"]["status"],"REJECTED_UNVERIFIED_CAPITAL_RECEIPT")
        p=formal("WITHDRAWAL_CONFIRMED");p["canonical_integrity"]="PENDING"
        self.assertEqual(build_display({},TARGET,REFERENCE,p)["long_term_capital_environment"]["label"],UNKNOWN)
        p=formal("WITHDRAWAL_CONFIRMED");p["evidence_windows_trading_days"]=[20,60]
        self.assertEqual(build_display({},TARGET,REFERENCE,p)["long_term_capital_environment"]["label"],UNKNOWN)
    def test_conflict_does_not_override_either_axis(self):
        x=build_display(verified(5),TARGET,REFERENCE,formal("WITHDRAWAL_CONFIRMED"))
        self.assertEqual(x["today_market_environment"]["label"],"強烈偏多")
        self.assertEqual(x["long_term_capital_environment"]["label"],"資金撤退")
        self.assertTrue(x["decision_policy"]["independent_axes"])
        self.assertEqual(x["decision_policy"]["trading_authority"],"NONE")

if __name__=="__main__":
    unittest.main()
