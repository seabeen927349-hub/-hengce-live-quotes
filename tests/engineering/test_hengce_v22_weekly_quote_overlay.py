"""Real existing EOD/TDCC V2.2 weekly research -> existing Fugle quote overlay."""
import copy
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"scripts"))
import hengce_v22_weekly_research_runner as runner

spec=importlib.util.spec_from_file_location("quote_overlay",ROOT/"scripts/hengce_retail_top5_quote_overlay.py")
q=importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)
MODEL=ROOT/"original_v22_model"
TW=ZoneInfo("Asia/Taipei")


class WeeklyQuoteOverlayExistingVessels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEL.is_dir():
            raise unittest.SkipTest("Pinned immutable original V2.2 must be checked out in integration CI")
        cls.report=runner.calculate(
            ROOT,MODEL,date(2026,11,6),
            now=datetime.fromisoformat("2026-11-10T15:48:00+08:00"))
        assert cls.report["qualified_count"]==7

    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        for file in ("hengce/HENGCE_SELECTION_MODEL_CHOICE_LATEST.json",
                     "scripts/hengce_scan_once_router.py"):
            (self.root/file).parent.mkdir(parents=True,exist_ok=True)
            shutil.copy(ROOT/file,self.root/file)
        self.output=self.root/"research/retail_top5/v22_weekly_latest.json"
        self.output.parent.mkdir(parents=True,exist_ok=True)
        self.write(self.report)
        self.now=datetime(2026,11,10,15,50,tzinfo=TW)
        status={
            "schema_version":3,"authority":"INTRADAY_QUOTE_TRANSPORT_ONLY_NO_MODEL_RANKING_AUTHORITY",
            "snapshot_id":"quote-20261110","generated_at_taipei":"2026-11-10T15:45:00+08:00",
            "cache_expires_at_taipei":"2026-11-10T15:55:00+08:00",
            "requested_count":1,"market_phase":"closed","broker_order_execution":False,
        }
        (self.root/"legacy_live").mkdir(parents=True,exist_ok=True)
        (self.root/"legacy_live/status.json").write_text(json.dumps(status))
        (self.root/"legacy_live/active.json").write_text(json.dumps({
            **status,"data":[{
                "snapshot_id":status["snapshot_id"],"symbol":"6446","price":1300.0,
                "previous_close":1280.0,"volume":4000,"fetch_ok":True,"is_trial":False,
                "is_halted":False,"stale_at_publish":False,"quote_date":"2026-11-10",
                "fetched_at_taipei":"2026-11-10T15:45:00+08:00",
                "last_trade_time":"2026-11-10T13:30:00+08:00",
                "change_percent":1.5625
            }]
        }))

    def write(self,value):
        self.output.write_text(json.dumps(value,ensure_ascii=False)+"\n",encoding="utf-8")

    def test_actual_weekly_top5_can_observe_existing_quote(self):
        result=q.overlay(self.root,self.report,self.now)
        self.assertEqual(result["selection_scope"],"HENGCE_EXISTING_EOD_TDCC_WEEKLY_RESEARCH_ONLY")
        self.assertEqual(result["top5_rows"],5)
        self.assertEqual([x["ticker"] for x in result["quotes"]],
                         ["6446","2412","1476","2610","2254"])
        self.assertEqual(result["quotes"][0]["last_executed_price_reference"],1300.0)
        self.assertEqual(result["quotes"][0]["ranking_source"],"V2.2_ORIGINAL_HENGCE_FRIDAY_RESEARCH")
        self.assertEqual(result["quotes"][0]["quote_status"],"CURRENT_SESSION_SNAPSHOT")
        self.assertEqual(result["current_session_quotes"],1)
        self.assertFalse(result["formal_eod_replaced"])
        self.assertFalse(result["ranking_changed"])
        self.assertFalse(result["broker_execution"])
        self.assertEqual(result["authorized_lots"],0)

    def test_uncommitted_or_mutated_weekly_report_is_not_quoteable(self):
        altered=copy.deepcopy(self.report)
        altered["top5"][0]["ticker"]="3042"
        with self.assertRaisesRegex(q.EvidenceBlocked,"NOT_COMMITTED_OR_MISMATCHED"):
            q.overlay(self.root,altered,self.now)
        self.output.unlink()
        with self.assertRaisesRegex(q.EvidenceBlocked,"NOT_COMMITTED_OR_MISMATCHED"):
            q.overlay(self.root,self.report,self.now)

    def test_broker_authority_and_source_digest_fail_closed(self):
        for modify in [
            lambda r:r.update({"broker_execution":True}),
            lambda r:r.update({"authorized_lots":1}),
            lambda r:r["source_lineage"].update({"eod_research_mother_sha256":"tampered"}),
        ]:
            r=copy.deepcopy(self.report)
            modify(r);self.write(r)
            with self.subTest(change=r.get("broker_execution"),source=r.get("source_lineage",{}).get("eod_research_mother_sha256")):
                with self.assertRaisesRegex(q.EvidenceBlocked,"SELECTION_NOT_VERIFIED"):
                    q.overlay(self.root,r,self.now)

    def test_real_existing_fugle_fetch_used_for_missing_top5(self):
        seen=[]
        def original_fetch(ticker,key,telemetry):
            seen.append(ticker)
            return ({
              "symbol":ticker,"date":"2026-11-10",
              "lastTrade":{"price":210.0,"time":"2026-11-10T13:30:00+08:00"},
              "previousClose":200.0,"total":{"tradeVolume":9000},
              "isTrial":False,"tradingHalt":{"isHalted":False}
            },{"attempts":1},None)
        result=q.overlay(self.root,self.report,self.now)
        result=q.refresh_uncovered_from_fugle(self.root,result,"test-key",
                      fetcher=original_fetch,clock=lambda:self.now,pause=lambda _:None)
        self.assertEqual(seen,["2412","1476","2610","2254"])
        self.assertEqual(result["current_session_quotes"],5)
        self.assertEqual(result["quotes"][-1]["source"],"FUGLE_EXISTING_TRANSPORT_ON_DEMAND")
        self.assertEqual(result["quotes"][-1]["last_executed_price_reference"],210.0)
        self.assertFalse(result["ranking_changed"])
        self.assertFalse(result["broker_execution"])

    def test_source_is_stale_if_session_date_is_not_today(self):
        past=datetime.fromisoformat("2026-11-11T15:50:00+08:00")
        result=q.overlay(self.root,self.report,past)
        self.assertEqual(result["current_session_quotes"],0)
        self.assertEqual(result["quotes"][0]["quote_status"],"PRIOR_SESSION_ONLY")
        self.assertFalse(result["quotes"][0]["session_quote_is_current"])

    def test_expired_or_malformed_existing_quotes_never_claim_current(self):
        now=datetime.fromisoformat("2026-11-10T16:50:00+08:00")
        result=q.overlay(self.root,self.report,now)
        self.assertEqual(result["current_session_quotes"],0)
        self.assertEqual(result["quotes"][0]["quote_status"],"EXPIRED_SESSION_SNAPSHOT")


if __name__=="__main__":
    unittest.main()
