#!/usr/bin/env python3
"""Test vendor field scope and archived-vs-current T86 hold-gates."""
import copy
import json
import unittest
from pathlib import Path
from reconcile import reconcile

FIXTURE = json.loads((Path(__file__).parent / "SNAPSHOT_EXCERPTS.json").read_text())

class TestReconcile(unittest.TestCase):
    def test_three_stock_eod_price_pass(self):
        o = reconcile(copy.deepcopy(FIXTURE))
        self.assertEqual(o["stock_count"], 3)
        self.assertTrue(o["all_finmind_twse_eod_price_equal"])

    def test_all_three_fugle_close_agree(self):
        o = reconcile(copy.deepcopy(FIXTURE))
        self.assertTrue(all(x["price"]["fugle_close_matches_twse"] for x in o["results"]))

    def test_fugle_volume_not_eod(self):
        o = reconcile(copy.deepcopy(FIXTURE))
        self.assertTrue(all(x["price"]["scope_mismatch_observed"] for x in o["results"]))
        self.assertTrue(all(x["price"]["fugle_quote_volume_not_authorized_as_eod"] for x in o["results"]))

    def test_archived_2330_t86_holds(self):
        o = reconcile(copy.deepcopy(FIXTURE))
        row = next(x for x in o["results"] if x["ticker"] == "2330")
        self.assertEqual(row["institutional"]["delta_current_twse_minus_archived"]["total_net"], "6510")
        self.assertTrue(row["institutional"]["finmind_matches_current_twse"])
        self.assertFalse(row["institutional"]["may_overwrite_archived_evidence"])
        self.assertTrue(o["canonical_reconciliation_required"])

    def test_archived_2454_t86_holds(self):
        o = reconcile(copy.deepcopy(FIXTURE))
        row = next(x for x in o["results"] if x["ticker"] == "2454")
        self.assertEqual(row["institutional"]["delta_current_twse_minus_archived"]["total_net"], "-3000")

    def test_new_vendor_price_difference_fails(self):
        sample = copy.deepcopy(FIXTURE)
        sample["stocks"][0]["finmind_eod"]["close"] = 2261
        self.assertFalse(reconcile(sample)["all_finmind_twse_eod_price_equal"])

    def test_cross_date_quote_must_fail(self):
        sample = copy.deepcopy(FIXTURE)
        sample["stocks"][0]["fugle_quote"]["date"] = "2026-11-03"
        with self.assertRaisesRegex(ValueError, "SOURCE_DATE_MISMATCH"):
            reconcile(sample)

    def test_never_formal(self):
        o = reconcile(copy.deepcopy(FIXTURE))
        self.assertFalse(o["feature_detector_input_authority"])
        self.assertFalse(o["formal_escape_state_authority"])
        self.assertFalse(o["selection_authority"])
        self.assertEqual(o["trading_authority"], "NONE")

if __name__ == "__main__":
    unittest.main()
