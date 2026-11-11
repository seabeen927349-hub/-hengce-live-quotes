"""Prevent repeated 'scan once' reports from reclassifying repaired work as broken."""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.hengce_scan_consistency import consistency_snapshot, LOCK_PATH
from scripts.hengce_scan_once_router import report

ROOT = Path(__file__).resolve().parents[2]
TZ = ZoneInfo("Asia/Taipei")


class ScanConsistencyLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for path in (LOCK_PATH, "governance/TWSE_TRADING_CALENDAR_2026_v1.json"):
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / path).read_bytes())
        self.write("ownership/tdcc/latest.json", {
            "status": "COMPLETE", "snapshot_date": "20261106"})
        self.write("research/hba_surveillance/decision_latest.json", {
            "status": "RESEARCH_ADVISORY_READY",
            "observed_eod_date": "2026-11-10",
            "research_summary": {"market_covered": 1082, "macro": "資料不足"}})
        self.write("research/retail_top5/v22_research_latest.json", {
            "status": "RETROSPECTIVE_V22_TOP5_READY",
            "decision_date": "2026-11-06"})
        self.write("live/status.json", {
            "snapshot_id": "old",
            "cache_expires_at_taipei": "2026-10-27T14:06:29+08:00"})
        self.make_eod("20261110")

    def write(self, path, obj):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, ensure_ascii=False) + "\n", encoding="utf-8")
        return p

    def make_eod(self, day):
        d = f"{day[:4]}-{day[4:6]}-{day[6:8]}"
        mother = {
            "status": "PASS", "target_date": d,
            "three_leg_complete": True, "integrity_status": "PASS",
            "mother_sha256": "a" * 64,
            "promoted_leg_sha256": {
                "price": "p" * 64, "margin": "m" * 64,
                "institutional": "i" * 64}}
        receipt = {
            "status": "COMPLETE", "target_date": d,
            "formal_complete_day": True, "three_leg_complete": True,
            "mother_status": "COMPLETE", "mother_receipt_status": "PASS",
            "mother_sha256": "a" * 64}
        for leg, value in [("price", "p"), ("margin", "m"),
                           ("institutional", "i")]:
            receipt[leg + "_status"] = "COMPLETE"
            receipt[leg + "_date"] = d
            receipt[leg + "_sha256"] = value * 64
        self.write(f"eod/{day}/status.json", receipt)
        self.write(f"eod/{day}/receipts/mother.json", mother)

    def snapshot(self, time_string="2026-11-11T21:48:00+08:00"):
        return consistency_snapshot(datetime.fromisoformat(time_string), self.root)

    def test_baseline_repair_is_distinct_from_current_runtime(self):
        x = self.snapshot()
        self.assertEqual(x["status"], "LOCK_APPLIED")
        repairs = {i["repair_id"]: i for i in x["repair_baselines"]}
        self.assertEqual(repairs["HBA_NO_CLOSE_EOD"]["merged_pr"], 77)
        self.assertEqual(repairs["HBA_NO_CLOSE_EOD"]["baseline"],
                         "RECORDED_VERIFIED_REPAIR")
        self.assertFalse(repairs["HBA_NO_CLOSE_EOD"]["current_execution_verified_by_this_guard"])
        self.assertEqual(repairs["READ_ONLY_HEALTH_AUDITOR"]["merged_pr"], 79)
        self.assertEqual(x["hba"]["market_covered"], 1082)
        self.assertEqual(x["hba"]["state"], "RECORDED_RESEARCH_ADVISORY_READY")
        self.assertEqual(x["tdcc"]["snapshot_date"], "20261106")
        self.assertFalse(x["tdcc"]["daily_retail_count_claimed"])
        self.assertEqual(x["v22"]["state"], "HISTORICAL_RESEARCH_ONLY")
        self.assertEqual(x["v22"]["formal_selector_status"], "NOT_ENABLED")
        self.assertEqual(x["existing_quote_cache"]["state"],
                         "REPOSITORY_CACHE_STALE_OR_UNVERIFIED")
        self.assertTrue(x["existing_quote_cache"]["does_not_imply_all_fugle_quotes_broken"])
        self.assertEqual(x["runtime_modules"]["s5"], "UNKNOWN_NO_CURRENT_RUNTIME_EVIDENCE")
        self.assertTrue(x["not_a_new_full_market_scan"])
        self.assertFalse(x["broker_execution"])

    def test_before_original_eod_schedule_is_not_called_broken(self):
        x = self.snapshot()
        self.assertEqual(x["eod"]["latest_complete_eod_date"], "2026-11-10")
        self.assertEqual(x["eod"]["state"], "AWAITING_SCHEDULE")
        self.assertFalse(x["eod"]["failed_workflow_claim"])

    def test_after_schedule_without_receipt_is_not_auto_failure(self):
        x = self.snapshot("2026-11-11T23:05:00+08:00")
        self.assertEqual(x["eod"]["state"], "AWAITING_PUBLISH_CONFIRMATION")
        self.assertFalse(x["eod"]["failed_workflow_claim"])

    def test_complete_today_requires_original_three_leg_and_mother(self):
        self.make_eod("20261111")
        self.assertEqual(self.snapshot()["eod"]["state"], "RECEIPT_COMPLETE")
        p = self.root / "eod/20261111/status.json"
        x = json.loads(p.read_text())
        x["margin_status"] = "PENDING"
        self.write("eod/20261111/status.json", x)
        self.assertEqual(self.snapshot()["eod"]["state"],
                         "TODAY_RECEIPT_INCOMPLETE_UNVERIFIED")

    def test_missing_yesterday_eod_is_staleness_not_new_broken_repair(self):
        x = self.snapshot("2026-11-12T21:00:00+08:00")
        self.assertEqual(x["eod"]["state"], "SOURCE_STALE_REVIEW_REQUIRED")
        self.assertEqual(x["repair_baselines"][0]["baseline"],
                         "RECORDED_VERIFIED_REPAIR")

    def test_closed_market_not_reported_as_missing_eod_failure(self):
        x = self.snapshot("2026-12-25T21:00:00+08:00")
        self.assertEqual(x["eod"]["state"], "MARKET_CLOSED_NO_NEW_EOD_EXPECTED")
        self.assertEqual(x["eod"]["calendar_source"], "EXISTING_TWSE_CALENDAR")

    def test_missing_lock_fails_closed_without_erasing_data(self):
        (self.root / LOCK_PATH).unlink()
        x = self.snapshot()
        self.assertEqual(x["status"], "POLICY_LOCK_UNVERIFIED")
        self.assertEqual(x["repair_baselines"], [])
        self.assertFalse(x["broker_execution"])

    def test_same_snapshot_same_report_and_existing_router_untouched(self):
        a = self.snapshot()
        self.assertEqual(a, self.snapshot())
        x = report(datetime.fromisoformat("2026-11-11T21:48:00+08:00"), self.root)
        self.assertEqual(x["reporting"]["consistency_evidence"]["eod"]["state"],
                         "AWAITING_SCHEDULE")
        self.assertEqual(x["status"], "NO_ACTIVE_SELECTION_STRATEGY")
        self.assertEqual(x["rows"], [])
        self.assertFalse(x["broker_order_execution"])
        self.assertFalse(x["buy_signal"])
        self.assertFalse(x["sell_signal"])
        self.assertEqual(x["reporting"]["action_card"]["status"], "NO_BUY")


if __name__ == "__main__":
    unittest.main()
