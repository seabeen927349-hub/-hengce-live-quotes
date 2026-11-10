"""Current retirement/monitoring boundaries, separate from archived engineering tests."""
import json
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"


class CurrentRetirementMonitoringTests(unittest.TestCase):
    def test_retired_q017_cannot_reenter_active_workflows_or_runtime(self):
        lock = json.loads((ROOT / "hengce/HENGCE_Q017_RETIREMENT_LOCK_20261105.json").read_text())
        self.assertEqual(lock["status"], "RETIRED_NO_ACTIVE_STRATEGY")
        self.assertEqual(lock["active_strategy_count"], 0)
        for name in ("selection_authority", "signal_authority", "broker_order_execution"):
            self.assertIs(lock[name], False)
        self.assertEqual(lock["capital_authority_twd"], 0)
        self.assertEqual(list(WORKFLOWS.glob("*q017*.yml")), [])
        self.assertEqual(list((ROOT / "scripts").glob("*q017*.py")), [])

    def test_old_health_scheduler_not_silently_reactivated(self):
        self.assertFalse((WORKFLOWS / "hengce-system-health.yml").exists())
        for workflow in WORKFLOWS.glob("*.yml"):
            source = workflow.read_text(encoding="utf-8")
            with self.subTest(workflow=workflow.name):
                self.assertNotIn("python scripts/hengce_system_health.py", source)
                self.assertNotIn("python scripts/hengce_health_collect_runs.py", source)

    def test_existing_hba_surveillance_remains_schedulable_and_read_only(self):
        path = WORKFLOWS / "hengce-hba-daily-surveillance.yml"
        self.assertTrue(path.is_file())
        config = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        event = config["on"]
        self.assertGreaterEqual(len(event["schedule"]), 1)
        self.assertIn("workflow_dispatch", event)
        self.assertIn("workflow_run", event)
        self.assertIn("HENGCE original EOD ingest", event["workflow_run"]["workflows"])
        steps = config["jobs"]["scan"]["steps"]
        runs = "\n".join(s.get("run", "") for s in steps)
        self.assertIn("test_*.py", runs)
        self.assertIn("hengce_hba_daily_surveillance.py", runs)
        self.assertIn("hengce_hba_decision_report.py", runs)
        self.assertIn("broker_execution", runs)
        contract = json.loads((ROOT / "hengce/HENGCE_SCAN_ONCE_CONTRACT_LATEST.json").read_text())
        self.assertEqual(contract["active_strategy_count"], 0)
        self.assertIs(contract["broker_order_execution"], False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
