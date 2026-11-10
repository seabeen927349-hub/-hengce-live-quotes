import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hengce_scan_once_router as scan

NOW = datetime.fromisoformat("2026-11-10T21:29:00+08:00")
OBS = "research/retail_top5/v22_research_latest.json"
PREF = "hengce/HENGCE_SELECTION_MODEL_CHOICE_LATEST.json"


class ReadonlyOriginalV22ResearchScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in (OBS, PREF):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT/name).read_bytes())

    def candidate(self):
        return scan.research_top5_observation(NOW, self.root)

    def mutate(self, fn):
        p = self.root / OBS
        d = json.loads(p.read_text(encoding="utf-8"))
        fn(d)
        p.write_text(json.dumps(d, ensure_ascii=False) + "\n", encoding="utf-8")

    def test_original_v22_research_top5_visible_on_scan_route(self):
        report = self.candidate()
        self.assertEqual(report["status"], "HISTORICAL_RESEARCH_TOP5_VERIFIED")
        self.assertEqual(report["source_date"], "2026-11-06")
        self.assertEqual(report["age_calendar_days"], 4)
        self.assertEqual([x["ticker"] for x in report["top5"]],
                         ["6446", "2412", "1476", "2610", "2254"])
        self.assertEqual(report["qualified_count"],7)
        self.assertFalse(report["formal_selection_authority"])
        self.assertFalse(report["broker_execution"])
        self.assertFalse(report["buy_signal"])
        self.assertFalse(report["current_selection"])
        self.assertTrue(report["not_current_recommendations"])

    def test_formal_router_still_returns_no_active_selection(self):
        result = scan.report(NOW, self.root)
        self.assertEqual(result["status"],"NO_ACTIVE_SELECTION_STRATEGY")
        self.assertEqual(result["rows"],[])
        self.assertEqual(result["reporting"]["top10"],[])
        self.assertEqual(result["reporting"]["action_card"]["status"],"NO_BUY")
        self.assertFalse(result["broker_order_execution"])
        self.assertEqual(result["reporting"]["v22_research_top5"]["status"],
                         "HISTORICAL_RESEARCH_TOP5_VERIFIED")

    def test_bad_model_preference_fails_closed(self):
        p = self.root/PREF
        x = json.loads(p.read_text())
        x["choice_status"]="ACTIVE_TRADING"
        p.write_text(json.dumps(x))
        self.assertEqual(self.candidate()["status"],"V22_PREFERENCE_UNVERIFIED")

    def test_research_receipt_cannot_promote_itself(self):
        for field, value in (
            ("official_pit_certified",True),("model_literature_gate","PASSED"),
            ("formal_selection_authority",True),("buy_signal",True),
            ("broker_execution",True),("authorized_lots",1),
            ("capital_authority_twd",100000),("decision_is_current",True),
        ):
            with self.subTest(field=field):
                data=(ROOT/OBS).read_bytes()
                (self.root/OBS).write_bytes(data)
                self.mutate(lambda d:d.update({field:value}))
                self.assertEqual(self.candidate()["status"],"RESEARCH_RECEIPT_NOT_VERIFIED")

    def test_source_artifact_or_original_model_commit_cannot_be_substituted(self):
        for field,value in (
            ("source_artifact_id",999),
            ("source_parent_tdcc_sha256","bad"),
            ("original_v22_screen_pinned_commit","not-original"),
        ):
            with self.subTest(field=field):
                (self.root/OBS).write_bytes((ROOT/OBS).read_bytes())
                self.mutate(lambda d:d.update({field:value}))
                self.assertEqual(self.candidate()["status"],"RESEARCH_RECEIPT_NOT_VERIFIED")

    def test_wrong_order_and_invalid_thresholds_are_rejected(self):
        self.mutate(lambda d:d["top5"][0].update({"r20_pct":3.0}))
        self.assertEqual(self.candidate()["status"],"RESEARCH_METRICS_INVALID")
        (self.root/OBS).write_bytes((ROOT/OBS).read_bytes())
        self.mutate(lambda d:d["top5"][0].update({"rank":5}))
        self.assertEqual(self.candidate()["status"],"RESEARCH_RANKING_INVALID")
        (self.root/OBS).write_bytes((ROOT/OBS).read_bytes())
        self.mutate(lambda d:d["top5"][0].update({"median_20d_turnover_twd":10000000}))
        self.assertEqual(self.candidate()["status"],"RESEARCH_RANKING_ORDER_INVALID")

    def test_future_date_rejected_and_old_day_always_historical(self):
        future = datetime.fromisoformat("2026-11-05T21:00:00+08:00")
        self.assertEqual(scan.research_top5_observation(future,self.root)["status"],
                         "RESEARCH_RECEIPT_NOT_VERIFIED")
        much_later = datetime.fromisoformat("2026-12-10T21:00:00+08:00")
        x=scan.research_top5_observation(much_later,self.root)
        self.assertEqual(x["source_date"], "2026-11-06")
        self.assertTrue(x["retrospective_only"])
        self.assertFalse(x["current_selection"])

    def test_missing_or_malformed_receipt_does_not_affect_formal_router(self):
        (self.root/OBS).unlink()
        self.assertEqual(self.candidate()["status"],"RESEARCH_RECEIPT_UNREADABLE")
        result=scan.report(NOW,self.root)
        self.assertEqual(result["status"],"NO_ACTIVE_SELECTION_STRATEGY")
        self.assertFalse(result["buy_signal"])
        self.assertEqual(result["reporting"]["v22_research_top5"]["top5"],[])


if __name__=="__main__":
    unittest.main()
