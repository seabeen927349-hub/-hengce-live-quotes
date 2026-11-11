"""Regression for the CURRENT read-only HENGCE health board, never retired Q017."""
import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

PYTHON=Path(__file__).resolve().parents[2]/'scripts/hengce_operational_integrity_v1.py'
spec=importlib.util.spec_from_file_location('hengce_operational_integrity_v1',PYTHON)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
evaluate=module.evaluate
WORKFLOWS=module.WORKFLOWS
TZ=ZoneInfo('Asia/Taipei')


class OperationalIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.now=datetime(2026,11,11,9,40,tzinfo=TZ)
        self.write("hengce/HENGCE_SCAN_ONCE_CONTRACT_LATEST.json",{
            "status":"NO_ACTIVE_SELECTION_STRATEGY",
            "active_strategy_count":0,"broker_order_execution":False,
            "capital_authority_twd":0})
        self.write("governance/HENGCE_ACTIVE_STRATEGY_AUTHORITY_20261105.json",{
            "status":"NO_ACTIVE_SELECTION_STRATEGY",
            "active_strategy_count":0,"broker_order_execution":False,
            "capital_authority_twd":0,"selection_authority":False,
            "q017":"RETIRED_ALL_OPERATIONAL_PATHS"})
        self.write("eod/20261110/status.json",{
            "status":"COMPLETE","formal_complete_day":True,
            "downstream_ready":True,"mother_status":"COMPLETE",
            "price_date":"2026-11-10","institutional_date":"2026-11-10",
            "margin_date":"2026-11-10",
            "price_status":"COMPLETE","institutional_status":"COMPLETE",
            "margin_status":"COMPLETE",
            "price_rows":1091,"institutional_rows":1082,"margin_rows":1062})
        self.write("ownership/tdcc/latest.json",{
            "status":"COMPLETE","snapshot_date":"20261106",
            "summary_rows":2975,"source_sha256":"a"*64,
            "historical_latency_status":"DATA_BLOCKED"})
        orig=self.write("research/hba_surveillance/latest.json",{"status":"EOD_VALID_MACRO_UNKNOWN"})
        integ=self.write("research/hba_surveillance/integrated_latest.json",{"readiness":"RESEARCH_READY"})
        self.write("research/hba_surveillance/decision_latest.json",{
            "status":"RESEARCH_ADVISORY_READY",
            "authority":{"active_selection_strategy_count":0,
                         "formal_selection":False,"broker_execution":False,
                         "capital_twd":0},
            "not_live_quotes":True,"observed_eod_date":"2026-11-10",
            "research_summary":{"market_covered":1082},
            "input_sha256":{"original_hba":module.digest(orig),
                            "integrated_hba":module.digest(integ)}})
        self.write("live/status.json",{
            "transport_health_status":"PASS","broker_order_execution":False,
            "generated_at_taipei":"2026-10-27T13:56:29+08:00",
            "cache_expires_at_taipei":"2026-10-27T14:06:29+08:00"})
    def tearDown(self):
        self.tmp.cleanup()
    def write(self,path,obj):
        p=self.root/path
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(obj,ensure_ascii=False),encoding="utf-8")
        return p
    def check(self,now=None,**kw):
        return evaluate(self.root,now or self.now,**kw)

    def test_research_is_recovered_but_whole_system_is_not_claimed_healthy(self):
        out=self.check()
        self.assertEqual(out["modules"]["governance"]["state"],"PASS")
        self.assertEqual(out["modules"]["eod"]["state"],"PASS")
        self.assertEqual(out["modules"]["tdcc"]["state"],"PASS")
        self.assertEqual(out["modules"]["hba"]["state"],"PASS")
        self.assertEqual(out["modules"]["quote_transport"]["state"],"STALE")
        self.assertEqual(out["modules"]["overseas"]["state"],"UNKNOWN")
        self.assertEqual(out["modules"]["v22_weekly"]["state"],"UNKNOWN")
        self.assertEqual(out["modules"]["s5"]["state"],"UNKNOWN")
        self.assertEqual(out["modules"]["escape"]["state"],"UNKNOWN")
        self.assertEqual(out["modules"]["rms"]["state"],"UNKNOWN")
        self.assertEqual(out["overall"],"DEGRADED")
        self.assertEqual(out["authority"],module.ZERO)
        self.assertTrue(out["no_new_data_collector"])
        self.assertTrue(out["formal_health_not_inferred_from_old_q017"])

    def test_unsafe_order_or_q017_activation_blocks_whole_board(self):
        p=self.root/"governance/HENGCE_ACTIVE_STRATEGY_AUTHORITY_20261105.json"
        a=json.loads(p.read_text());a["broker_order_execution"]=True
        self.write("governance/HENGCE_ACTIVE_STRATEGY_AUTHORITY_20261105.json",a)
        out=self.check()
        self.assertEqual(out["modules"]["governance"]["state"],"FAIL_CLOSED")
        self.assertEqual(out["overall"],"FAIL_CLOSED")

    def test_hba_hash_mismatch_fails_closed(self):
        self.write("research/hba_surveillance/latest.json",{"newer_unverified_research":True})
        out=self.check()
        self.assertEqual(out["modules"]["hba"]["state"],"FAIL_CLOSED")
        self.assertFalse(out["modules"]["hba"]["evidence"]["evidence_hash_match"])

    def test_stale_hba_is_not_same_as_eod(self):
        p=self.root/"research/hba_surveillance/decision_latest.json"
        a=json.loads(p.read_text());a["observed_eod_date"]="2026-11-09"
        self.write("research/hba_surveillance/decision_latest.json",a)
        self.assertEqual(self.check()["modules"]["hba"]["state"],"STALE")

    def test_missing_eod_three_leg_fail_closed(self):
        p=self.root/"eod/20261110/status.json"
        a=json.loads(p.read_text());a["margin_status"]="PENDING"
        self.write("eod/20261110/status.json",a)
        out=self.check()
        self.assertEqual(out["modules"]["eod"]["state"],"FAIL_CLOSED")
        self.assertEqual(out["modules"]["hba"]["state"],"STALE")

    def test_no_historical_v22_promoted_as_weekly_receipt(self):
        self.write("research/retail_top5/v22_research_latest.json",{
            "status":"RETROSPECTIVE_V22_TOP5_READY","decision_date":"2026-11-06"})
        self.assertEqual(self.check()["modules"]["v22_weekly"]["state"],"UNKNOWN")

    def test_readonly_verified_weekly_receipt_remains_nontrading(self):
        self.write("research/retail_top5/v22_weekly_latest.json",{
            "decision_date":"2026-11-06","research_only":True,
            "broker_execution":False,"selection_authority":False,
            "authorized_lots":0,"capital_authority_twd":0,
            "buy_signal":False,"sell_signal":False})
        self.assertEqual(self.check()["modules"]["v22_weekly"]["state"],"PASS")
        p=self.root/"research/retail_top5/v22_weekly_latest.json"
        a=json.loads(p.read_text());a["buy_signal"]=True
        self.write("research/retail_top5/v22_weekly_latest.json",a)
        self.assertEqual(self.check()["modules"]["v22_weekly"]["state"],"FAIL_CLOSED")

    def test_workflow_failure_cannot_be_drowned_by_old_success(self):
        runs={fname:[{
            "id":1,"head_branch":"main","event":"schedule",
            "status":"completed","conclusion":"success",
            "created_at":"2026-11-11T00:30:00Z"}] for fname in WORKFLOWS.values()}
        macro=WORKFLOWS["overseas_workflow"]
        runs[macro].append({
            "id":2,"head_branch":"main","event":"schedule",
            "status":"completed","conclusion":"failure",
            "created_at":"2026-11-11T01:29:00Z"})
        out=self.check(workflow_runs=runs)
        self.assertEqual(out["modules"]["workflows"]["state"],"FAIL_CLOSED")
        self.assertEqual(out["modules"]["workflows"]["evidence"]["overseas_workflow"]["state"],"FAIL_CLOSED")
        self.assertEqual(out["overall"],"FAIL_CLOSED")

    def test_no_git_run_metadata_never_looks_green(self):
        out=self.check(workflow_runs=None,collection_error="UNAVAILABLE")
        self.assertEqual(out["modules"]["workflows"]["state"],"UNKNOWN")

    def test_no_outbound_calls_or_modifications_during_local_audit(self):
        before={str(p):p.read_bytes() for p in self.root.rglob("*.json")}
        self.check()
        after={str(p):p.read_bytes() for p in self.root.rglob("*.json")}
        self.assertEqual(before,after)

    def test_real_current_repository_receipts_and_retirement_authority(self):
        # Main checkout may be modified between tests; derived receipts must
        # still never produce formal selection/order authority in audit output.
        repo=Path(__file__).resolve().parents[2]
        out=evaluate(repo,datetime.now(TZ))
        self.assertEqual(out["authority"],module.ZERO)
        self.assertEqual(out["modules"]["governance"]["state"],"PASS")
        self.assertNotEqual(out["overall"],"PASS")

if __name__ == "__main__":
    unittest.main()
