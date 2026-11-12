"""Research advisory is visible through existing '衡策掃一次' while formal selector stays retired."""
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from hengce_scan_once_router import report

class ReadOnlyRouterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.now=datetime(2026,11,10,12,15,tzinfo=ZoneInfo("Asia/Taipei"))
        (self.root/"hengce").mkdir()
        (self.root/"research/hba_surveillance").mkdir(parents=True)
        (self.root/"hengce/HENGCE_SCAN_ONCE_CONTRACT_LATEST.json").write_text(json.dumps({
            "status":"NO_ACTIVE_SELECTION_STRATEGY",
            "active_strategy_count":0, "broker_order_execution":False}))
        self.sources={}
        for key, name in (("original_hba","latest.json"),
                          ("integrated_hba","integrated_latest.json")):
            p=self.root/"research/hba_surveillance"/name
            p.write_text(json.dumps({"test":key}),encoding="utf-8")
            self.sources[key]=hashlib.sha256(p.read_bytes()).hexdigest()
        self.payload={
            "schema":"HENGCE_HBA_RESEARCH_DECISION_V1_20261110",
            "status":"RESEARCH_ADVISORY_READY",
            "target_tw_date":"2026-11-10",
            "observed_eod_date":"2026-11-09",
            "not_live_quotes":True,
            "historical_alpha_validated":False,
            "authority":{"active_selection_strategy_count":0,
                         "formal_selection":False,"trading":False,
                         "broker_execution":False,"capital_twd":0},
            "input_sha256":self.sources,
            "research_summary":{"market_covered":1082},
            "human_review_examples":[{"ticker":"3703","name":"欣陸",
                  "review_group":"優先人工追蹤","why":"兩方實股",
                  "risks":"回檔警戒","change_of_view":"下一週集保反轉"}]}
        self.write()
    def tearDown(self):self.temp.cleanup()
    def write(self):
        (self.root/"research/hba_surveillance/decision_latest.json").write_text(
            json.dumps(self.payload,ensure_ascii=False),encoding="utf-8")
    def test_existing_router_preserves_formal_retirement(self):
        x=report(self.now,self.root)
        self.assertEqual(x["status"],"NO_ACTIVE_SELECTION_STRATEGY")
        self.assertEqual(x["active_strategy_count"],0)
        self.assertEqual(x["reporting"]["top10"],[])
        self.assertEqual(x["rows"],[])
        self.assertFalse(x["buy_signal"])
        self.assertFalse(x["sell_signal"])
        self.assertFalse(x["broker_order_execution"])
        a=x["reporting"]["research_advisory"]
        self.assertEqual(a["status"],"RESEARCH_ADVISORY_READY")
        self.assertEqual(a["examples"][0]["ticker"],"3703")
        self.assertEqual(a["market_covered"],1082)
    def test_scan_once_includes_hash_checked_environment_but_no_trade_signal(self):
        path=self.root/"research/hba_surveillance/integrated_latest.json"
        data={"target_tw_date":"2026-11-10","observed_eod_date":"2026-11-09",
              "authority":{"trade":False,"formal_escape":False,
                           "new_selection":False,"capital":False},
              "market_environment":{
                "overseas":{"status":"資料不足","label":"資料不足",
                            "official_source_observation":None},
                "finmind_shadow":{"status":"STALE_FINMIND_SHADOW"},
                "full_market_intraday_monitor":{"status":"STALE_PRIOR_SESSION_MONITOR"},
                "s5":{"status":"NOT_PROVIDED"},
                "escape":{"status":"NOT_PROVIDED"},
                "canonical":{"date":"2026-11-09","canonical_eod":"COMPLETE"}}}
        path.write_text(json.dumps(data,ensure_ascii=False))
        self.payload["input_sha256"]["integrated_hba"]=hashlib.sha256(path.read_bytes()).hexdigest()
        self.write()
        report_result=report(self.now,self.root)
        state=report_result["reporting"]["environment_monitoring"]
        self.assertEqual(state["status"],"VERIFIED_HBA_RESEARCH_ENVIRONMENT_ONLY")
        self.assertEqual(state["finmind_shadow"]["status"],"STALE_FINMIND_SHADOW")
        self.assertEqual(state["s5"]["status"],"NOT_PROVIDED")
        self.assertEqual(state["escape"]["status"],"NOT_PROVIDED")
        self.assertFalse(state["formal_escape_authority"])
        self.assertFalse(report_result["buy_signal"])
        path.write_text("{}")
        tampered=report(self.now,self.root)["reporting"]["environment_monitoring"]
        self.assertEqual(tampered["status"],"HBA_SOURCE_NOT_VERIFIED")

    def test_environment_not_recycled_into_next_trading_day(self):
        state=report(datetime(2026,11,11,12,tzinfo=ZoneInfo("Asia/Taipei")),self.root)
        m=state["reporting"]["environment_monitoring"]
        self.assertEqual(m["status"],"HISTORICAL_HBA_ENVIRONMENT_NOT_CURRENT")
        self.assertFalse(m["trading_authority"])

    def test_changed_evidence_blocks_advisory(self):
        (self.root/"research/hba_surveillance/latest.json").write_text("{}")
        x=report(self.now,self.root)
        self.assertEqual(x["reporting"]["research_advisory"]["status"],
                         "RESEARCH_EVIDENCE_HASH_MISMATCH")
        self.assertEqual(x["reporting"]["top10"],[])
    def test_past_receipt_not_called_live(self):
        x=report(datetime(2026,11,19,tzinfo=ZoneInfo("Asia/Taipei")),self.root)
        self.assertEqual(x["reporting"]["research_advisory"]["status"],
                         "STALE_OR_FUTURE_EOD")
    def test_unauthorized_strategy_or_trade_blocks(self):
        self.payload["authority"]["trading"]=True
        self.write()
        a=report(self.now,self.root)["reporting"]["research_advisory"]
        self.assertEqual(a["status"],"UNVERIFIED_RESEARCH_RECEIPT")
    def test_incorrect_retirement_contract_blocks(self):
        p=self.root/"hengce/HENGCE_SCAN_ONCE_CONTRACT_LATEST.json"
        x=json.loads(p.read_text());x["active_strategy_count"]=1;p.write_text(json.dumps(x))
        a=report(self.now,self.root)["reporting"]["research_advisory"]
        self.assertEqual(a["status"],"RETIREMENT_CONTRACT_UNVERIFIED")

if __name__=="__main__":
    unittest.main()
