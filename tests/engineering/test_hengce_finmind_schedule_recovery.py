"""Offline guard regression: never add a second FinMind blood vessel."""
import sys
import unittest
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts"))
from hengce_finmind_trigger_gate import assess,UPSTREAM

TW=ZoneInfo("Asia/Taipei")
NOW=datetime(2026,11,9,11,25,tzinfo=TW)
REPO="seabeen927349-hub/-hengce-live-quotes"


def event_payload(now=NOW):
    return {"workflow_run":{
        "name":UPSTREAM,"conclusion":"success","head_branch":"main",
        "head_repository":{"full_name":REPO},
        "event":"schedule","updated_at":(now-timedelta(minutes=4)).isoformat()
    }}


class ScheduleRecoveryTests(unittest.TestCase):
    def test_backup_from_existing_schedule(self):
        self.assertEqual(assess("workflow_run",NOW,REPO,event_payload(),"refs/heads/main"),
                         (True,"INDEPENDENT_SCHEDULE_HEARTBEAT"))

    def test_upstream_wrong_repo_or_branch_blocked(self):
        for field,value in (("head_branch","feature"),("head_repository",{"full_name":"other/repo"})):
            with self.subTest(field=field):
                p=event_payload()
                p["workflow_run"][field]=value
                self.assertFalse(assess("workflow_run",NOW,REPO,p,"refs/heads/main")[0])

    def test_upstream_push_does_not_generate_backup(self):
        p=event_payload()
        p["workflow_run"]["event"]="push"
        self.assertFalse(assess("workflow_run",NOW,REPO,p,"refs/heads/main")[0])

    def test_upstream_failed_or_wrong_workflow_does_not_trigger(self):
        for k,v in (("conclusion","failure"),("name","unrelated workflow")):
            p=event_payload()
            p["workflow_run"][k]=v
            self.assertFalse(assess("workflow_run",NOW,REPO,p,"refs/heads/main")[0])

    def test_untrusted_or_malformed_event_rejected(self):
        self.assertFalse(assess("workflow_run",NOW,REPO,{}, "refs/heads/main")[0])
        self.assertFalse(assess("repository_dispatch",NOW,REPO,None,"refs/heads/main")[0])

    def test_stale_or_future_backup_blocked(self):
        for minutes in (45,-5):
            p=event_payload()
            p["workflow_run"]["updated_at"]=(NOW-timedelta(minutes=minutes)).isoformat()
            self.assertFalse(assess("workflow_run",NOW,REPO,p,"refs/heads/main")[0])

    def test_schedule_must_be_trading_session(self):
        self.assertTrue(assess("schedule",NOW,REPO,None,"refs/heads/main")[0])
        self.assertFalse(assess("schedule",NOW.replace(hour=15),REPO,None,"refs/heads/main")[0])
        sunday=datetime(2026,11,8,11,25,tzinfo=TW)
        self.assertFalse(assess("schedule",sunday,REPO,None,"refs/heads/main")[0])

    def test_pr_is_offline_only_and_manual_is_main_only(self):
        self.assertEqual(assess("pull_request",NOW,REPO,None,"refs/pull/52/merge"),(True,"PR_OFFLINE_ONLY"))
        self.assertFalse(assess("workflow_dispatch",NOW,REPO,None,"refs/heads/feature")[0])
        self.assertTrue(assess("workflow_dispatch",NOW,REPO,None,"refs/heads/main")[0])

    def test_existing_hba_and_official_source_scheduled_wake_same_finmind_vessel(self):
        for name in ("HENGCE Governed SOX VIX Premarket EOD",
                     "HENGCE HBA Daily Surveillance Research Sidecar"):
            with self.subTest(name=name):
                p=event_payload()
                p["workflow_run"]["name"]=name
                self.assertEqual(assess("workflow_run",NOW,REPO,p,"refs/heads/main"),
                                 (True,"INDEPENDENT_SCHEDULE_HEARTBEAT"))
                p["workflow_run"]["event"]="pull_request"
                self.assertFalse(assess("workflow_run",NOW,REPO,p,"refs/heads/main")[0])
        y=(ROOT/".github/workflows/hengce-escape-twse-full-market-finmind-shadow.yml").read_text()
        self.assertIn("HENGCE Governed SOX VIX Premarket EOD",y)
        self.assertIn("HENGCE HBA Daily Surveillance Research Sidecar",y)

    def test_same_monitor_workflow_and_existing_source(self):
        y=(ROOT/".github/workflows/hengce-escape-twse-full-market-finmind-shadow.yml").read_text(encoding="utf-8")
        source=(ROOT/".github/workflows/hengce-frozen-single-name-live-quotes.yml").read_text(encoding="utf-8")
        self.assertIn("name: "+UPSTREAM,source)
        self.assertIn("  workflow_run:",y)
        self.assertIn("HENGCE Frozen Single-Name Live Quotes",y)
        self.assertIn('cron: "3-58/5 1-4 * * 1-5"',y)
        self.assertIn('cron: "3-33/5 5 * * 1-5"',y)
        self.assertIn("python scripts/hengce_finmind_trigger_gate.py",y)
        self.assertIn("needs: trigger-gate",y)
        self.assertIn("if: needs.trigger-gate.outputs.allowed == 'true'",y)
        self.assertEqual(y.count("python scripts/hengce_escape_finmind_twse_common_shadow.py"),1)
        self.assertIn("python scripts/hengce_finmind_intraday_freshness_gate.py",y)
        self.assertIn("python scripts/hengce_publish.py",y)
        self.assertNotIn("git pull --rebase",y)
        # The source must be current main for any live run, but pull
        # requests still test their own head. This prevents old push event
        # SHA checkout from failing exact lease when HBA advanced main.
        self.assertIn("github.event.pull_request.head.sha || 'main'",y)
        self.assertIn("Checkout current authoritative main for governed publication",y)

if __name__=="__main__":
    unittest.main()
