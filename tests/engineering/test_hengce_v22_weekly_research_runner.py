"""Proof: V2.2 reuses existing original EOD/TDCC, never a parallel data vessel."""
import json
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts"))
import hengce_v22_weekly_research_runner as runner
from hengce_retail_top5_vessel_bridge import DataBlocked

NOW_1106=datetime.fromisoformat("2026-11-10T22:38:00+08:00")
MODEL=ROOT/"original_v22_model"


class V22WeeklyResearchTests(unittest.TestCase):
    def test_real_original_eod_mother_and_g1_21day_3snapshot(self):
        daily,weekly,rec=runner.inputs(ROOT,date(2026,11,6),asof=NOW_1106)
        self.assertEqual(len(daily),22865)
        self.assertEqual(len(weekly),3248)
        self.assertEqual(len(rec["price_days"]),21)
        self.assertEqual(len(rec["price_mother_recovered_days"]),8)
        self.assertEqual([p["snapshot_date"] for p in rec["tdcc_snapshots"]],
                         ["20261008","20261016","20261022"])
        self.assertEqual(rec["source_mode"],"HENGCE_ORIGINAL_EOD_PLUS_EXISTING_RESEARCH_MOTHER_AND_TDCC")
        self.assertTrue(rec["historical_asof_proof_missing"])
        self.assertEqual(rec["tdcc_g1_457_week_mother_sha256"],runner.CHIP_PARENT_SHA)
        self.assertEqual(rec["eod_research_mother_sha256"],runner.EOD_PARENT_SHA)

    def test_actual_original_v22_rank_on_canonical_21day_input(self):
        if not MODEL.is_dir():
            self.skipTest("CI checks out pinned immutable original V2.2 separately")
        r=runner.calculate(ROOT,MODEL,date(2026,11,6),now=NOW_1106)
        self.assertEqual(r["qualified_count"],7)
        self.assertEqual([x["ticker"] for x in r["top5"]],
                         ["6446","2412","1476","2610","2254"])
        self.assertEqual(r["decision_date"],"2026-11-06")
        self.assertEqual(r["original_screen_commit"],runner.MODEL_COMMIT)
        self.assertTrue(r["historical_asof_proof_missing"])
        self.assertEqual(r["mode"],"RESEARCH_TOP5_ONLY_NO_ORDER")
        self.assertFalse(r["broker_execution"])
        self.assertFalse(r["buy_signal"])
        self.assertFalse(r["selection_authority"])
        self.assertEqual(r["authorized_lots"],0)
        self.assertTrue(all(v["authorized_lots"]==0 for v in r["all_qualified"]))

    def test_original_tdcc_receipt_mismatch_uses_later_real_proof_not_fabricated_date(self):
        rows,proof=runner._parse_canonical_compat(ROOT,"20261030",decision=date(2026,11,13))
        self.assertGreaterEqual(len(rows),900)
        self.assertEqual(proof["snapshot_date"],"20261030")
        self.assertEqual(proof["source_type"],
                         "CANONICAL_TDCC_FIRST_OBSERVED_RECONCILED_RESEARCH_ONLY")
        self.assertEqual(proof["observed_at_taipei"],
                         "2026-11-01T15:41:59.900722+08:00")
        self.assertEqual(proof["receipt_observed_at_taipei"],
                         "2026-10-31T23:57:43+08:00")
        self.assertEqual(proof["raw_sha256"],runner.RECONCILED_TDCC_SHA)

    def test_1030_not_known_on_1030_and_not_eligible_before_lag14(self):
        with self.assertRaisesRegex(DataBlocked,"TDCC_NOT_KNOWN_AT_DECISION|TDCC_RECEIPT_PROOF_TIME_MISMATCH"):
            runner._parse_canonical_compat(ROOT,"20261030",decision=date(2026,10,30))

    def test_next_friday_cannot_generate_if_price_receipt_is_invalid(self):
        # Replay a deliberately rejected ORIGINAL EOD receipt. Never assume
        # that 11/11 is still absent: the existing original vessel advances.
        future=datetime.fromisoformat("2026-11-13T20:00:00+08:00")
        def broken_original_receipt(root,d):
            if d==date(2026,11,11):
                raise DataBlocked("SYNTHETIC_ORIGINAL_PRICE_RECEIPT_MISMATCH_TEST")
            return runner.read_eod_price(root,d)
        with self.assertRaisesRegex(DataBlocked,
                                    "ORIGINAL_EOD_INVALID_NO_SAFE_RESEARCH_FALLBACK:2026-11-11"):
            runner.inputs(ROOT,date(2026,11,13),asof=future,
                          price_reader=broken_original_receipt)

    def test_non_friday_and_before_close_rejected(self):
        with self.assertRaisesRegex(DataBlocked,"V22_RESEARCH_DECISION_NOT_2026_FRIDAY"):
            runner.inputs(ROOT,date(2026,11,10),asof=NOW_1106)
        with self.assertRaisesRegex(DataBlocked,"DECISION_EOD_NOT_YET_PUBLISHED"):
            runner.inputs(ROOT,date(2026,11,13),asof=NOW_1106)

    def test_no_broker_or_canonical_write_and_offrepo_output(self):
        fake={
          "schema":"HENGCE_V22_WEEKLY_RESEARCH_SCREEN_V1",
          "all_qualified":[{"rank":1,"ticker":"6446","reference_close":1270.0,
                            "r20_pct":8.0,"r5_pct":4.0,"retail_2week_pct":-2.0,
                            "median_20d_turnover_twd":300000000,"chip_date":"2026-10-22",
                            "authorized_lots":0}],
          "broker_execution":False,"authorized_lots":0,"top5":[]
        }
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"research_report"
            runner.save(ROOT,p,fake)
            self.assertTrue((p/"v22_weekly_research.json").is_file())
            self.assertTrue((p/"v22_all_qualified.csv").is_file())
            self.assertFalse((p/"orders.csv").exists())
        with self.assertRaisesRegex(DataBlocked,"OUTPUT_MUST_BE_OUTSIDE_HENGCE_REPOSITORY"):
            runner.save(ROOT,ROOT/"eod"/"bad",fake)


if __name__=="__main__":
    unittest.main()
