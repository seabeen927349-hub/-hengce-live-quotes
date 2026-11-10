"""Use original V2.2 computation and the scan-once production read path."""
import copy
import json
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts"))
import hengce_v22_weekly_research_runner as runner
import hengce_scan_once_router as scan

MODEL=ROOT/"original_v22_model"
NOW=datetime.fromisoformat("2026-11-10T22:38:00+08:00")
LATEST="research/retail_top5/v22_weekly_latest.json"
PREF="hengce/HENGCE_SELECTION_MODEL_CHOICE_LATEST.json"


class LivePathV22WeeklyResearchReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEL.is_dir():
            raise unittest.SkipTest("Pinned original V2.2 checkout is only available in full CI")
        cls.valid=runner.calculate(ROOT,MODEL,date(2026,11,6),now=NOW)

    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        for p in (LATEST,PREF):
            (self.root/p).parent.mkdir(parents=True,exist_ok=True)
        (self.root/PREF).write_bytes((ROOT/PREF).read_bytes())
        self.write(self.valid)

    def write(self,x):
        (self.root/LATEST).write_text(json.dumps(x,ensure_ascii=False)+"\n",encoding="utf-8")

    def read(self):
        return scan.research_top5_observation(NOW,self.root)

    def test_real_original_selector_produces_visible_research_top5(self):
        a=self.read()
        self.assertEqual(a["status"],"WEEKLY_RESEARCH_TOP5_READY")
        self.assertEqual(a["source_date"],"2026-11-06")
        self.assertEqual(a["qualified_count"],7)
        self.assertEqual([z["ticker"] for z in a["top5"]],
                         ["6446","2412","1476","2610","2254"])
        self.assertTrue(a["historical_asof_proof_missing"])
        self.assertFalse(a["broker_execution"])
        self.assertFalse(a["buy_signal"])
        self.assertFalse(a["formal_selection_authority"])
        self.assertEqual(a["authorized_lots"],0)

    def test_formal_scan_remains_no_selection_or_order(self):
        r=scan.report(NOW,self.root)
        self.assertEqual(r["status"],"NO_ACTIVE_SELECTION_STRATEGY")
        self.assertEqual(r["rows"],[])
        self.assertEqual(r["reporting"]["action_card"]["status"],"NO_BUY")
        self.assertEqual(r["reporting"]["top10"],[])
        self.assertFalse(r["broker_order_execution"])
        self.assertEqual(r["reporting"]["v22_research_top5"]["status"],
                         "WEEKLY_RESEARCH_TOP5_READY")

    def test_forged_trade_permission_or_model_digest_rejected(self):
        for field,value in [
            ("broker_execution",True),("buy_signal",True),
            ("selection_authority",True),("authorized_lots",1),
            ("original_screen_commit","other"),
            ("formal_strategy_promoted",True),
        ]:
            with self.subTest(field=field):
                d=copy.deepcopy(self.valid)
                d[field]=value
                self.write(d)
                self.assertEqual(self.read()["status"],"WEEKLY_RESEARCH_RECEIPT_UNVERIFIED")

    def test_corrupted_weekly_snapshot_or_unverified_rows_rejected(self):
        for mutation in [
            lambda x:x["source_lineage"].update({"source_cutoff":"2026-11-06"}),
            lambda x:x["source_lineage"]["tdcc_snapshots"][-1].update({"snapshot_date":"20261106"}),
            lambda x:x["top5"][0].update({"rank":2}),
            lambda x:x["all_qualified"][0].update({"retail_2week_pct":4.0}),
            lambda x:x["source_lineage"].update({"eod_research_mother_sha256":"tampered"}),
        ]:
            x=copy.deepcopy(self.valid)
            mutation(x)
            self.write(x)
            self.assertEqual(self.read()["status"],"WEEKLY_RESEARCH_RECEIPT_UNVERIFIED")

    def test_new_weekly_invalid_receipt_does_not_hide_error_with_old_historical(self):
        (self.root/"research/retail_top5/v22_research_latest.json").write_bytes(
            (ROOT/"research/retail_top5/v22_research_latest.json").read_bytes())
        d=copy.deepcopy(self.valid)
        d["broker_execution"]=True
        self.write(d)
        x=self.read()
        self.assertEqual(x["status"],"WEEKLY_RESEARCH_RECEIPT_UNVERIFIED")
        self.assertEqual(x["top5"],[])
        (self.root/LATEST).unlink()
        older=self.read()
        self.assertEqual(older["status"],"HISTORICAL_RESEARCH_TOP5_VERIFIED")
        self.assertEqual(older["source_date"],"2026-11-06")

    def test_future_weekly_date_is_rejected(self):
        early=datetime.fromisoformat("2026-11-05T22:38:00+08:00")
        result=scan.research_top5_observation(early,self.root)
        self.assertEqual(result["status"],"WEEKLY_RESEARCH_RECEIPT_UNVERIFIED")


if __name__=="__main__":
    unittest.main()
