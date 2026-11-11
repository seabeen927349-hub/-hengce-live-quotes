import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import hengce_retail_top5_readiness as mod


class FridayReadinessTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "repo"
        self.root.mkdir()
        (self.root / "hengce").mkdir()
        (self.root / "governance").mkdir()
        (self.root / mod.MODEL_CHOICE).write_text(json.dumps({
            "model_package": "HENGCE_SELECTION_MODEL_V2_2_TOP5",
            "choice_status": "PREFERRED_PENDING_PROMOTION",
            "formal_selection_authority": False,
            "buy_sell_signal_authority": False,
            "capital_authority_twd": 0,
            "broker_execution": False
        }), encoding="utf-8")
        (self.root / mod.STRATEGY_AUTHORITY).write_text(json.dumps({
            "active_strategy_count": 0, "selection_authority": False,
            "broker_order_execution": False
        }), encoding="utf-8")
        self.decision = date(2026, 11, 6)
        self.sessions = []
        d = self.decision
        from datetime import timedelta
        while len(self.sessions) < 21:
            if d.weekday() < 5:
                self.sessions.append(d.isoformat())
            d -= timedelta(days=1)
        self.sessions.reverse()
        self.receipt = {
            "schema": "HENGCE_RETAIL_TOP5_ORIGINAL_VESSEL_INPUT_BRIDGE_V1",
            "status": "SOURCE_DATA_PREPARED_RESEARCH_ONLY",
            "verified_eod_day_count": 21, "verified_tdcc_week_count": 3,
            "blockers": [],
            "sources": {"eod": [{"date": d, "sha256": "test-only"} for d in self.sessions],
                        "tdcc": [{"snapshot_date": z} for z in
                                 ["20261008", "20261015", "20261022"]]},
            "auxiliary": {"fugle": {"status": "QUOTE_CONTEXT_ONLY"}}
        }
        self.calendar_patch = patch.object(mod, "load_manifest",
            return_value=({"test_calendar": True}, Path("mock"), "test-lineage"))
        self.trading_patch = patch.object(mod, "is_trading_day",
                                        side_effect=lambda day, _: day.weekday() < 5)
        self.calendar_patch.start()
        self.trading_patch.start()
        self.addCleanup(self.calendar_patch.stop)
        self.addCleanup(self.trading_patch.stop)

    def inspect(self, root, decision):
        self.assertEqual(root, self.root)
        self.assertEqual(decision, self.decision)
        daily = [[self.decision.isoformat(), "3042", 100, 1000, 1000000]]
        weekly = [["20261022", "3042", 2000, "true"]]
        return self.receipt, daily, weekly

    def check(self, inspector=None):
        return mod.market_readiness(self.root, self.decision, today=date(2026,11,10),
                                    inspector=inspector or self.inspect)

    def test_latest_friday_calculated_in_taipei_dates(self):
        self.assertEqual(mod.latest_friday(date(2026,11,10)), self.decision)
        self.assertEqual(mod.latest_friday(self.decision), self.decision)

    def test_complete_21_sessions_and_three_tdcc_only_prepare_data(self):
        status, daily, weekly = self.check()
        self.assertEqual(status["source_status"], "SOURCE_DATA_PREPARED_RESEARCH_ONLY")
        self.assertEqual(status["selection_status"], "NOT_RUN_UNMERGED_MODEL_AND_NO_PROMOTION")
        self.assertFalse(status["selection_attempted"])
        self.assertEqual(status["top5"], [])
        self.assertEqual(status["authorized_lots"], 0)
        self.assertFalse(status["broker_execution"])
        self.assertEqual(status["calendar_lineage"], "test-lineage")
        self.assertEqual(len(daily), 1)
        self.assertEqual(len(weekly), 1)

    def test_v22d_primary_still_allows_original_weekly_benchmark_readiness(self):
        pref=json.loads((self.root/mod.MODEL_CHOICE).read_text(encoding="utf-8"))
        pref.update({
            "model_package":"HENGCE_SELECTION_MODEL_V2_2_D_DAILY_TOP5",
            "choice_status":"PREFERRED_DAILY_RESEARCH_PENDING_PROSPECTIVE",
            "model_id":"v22d_daily_nowcast_liquidity_top5_v1",
            "original_v22_weekly_status":"RETAINED_READ_ONLY_BENCHMARK_NOT_CURRENT_PRIMARY"
        })
        (self.root/mod.MODEL_CHOICE).write_text(json.dumps(pref),encoding="utf-8")
        state, daily, weekly=self.check()
        self.assertEqual(state["source_status"],"SOURCE_DATA_PREPARED_RESEARCH_ONLY")
        self.assertEqual(state["top5"],[])
        self.assertEqual(len(daily),1)
        self.assertEqual(len(weekly),1)

    def test_one_missing_trading_day_blocks_even_if_source_claims_ready(self):
        self.receipt["sources"]["eod"] = self.receipt["sources"]["eod"][1:]
        status, daily, weekly = self.check()
        self.assertEqual(status["source_status"], "BLOCKED")
        self.assertIn("OFFICIAL_EOD_SESSION_CONTINUITY_INCOMPLETE", status["blockers"])
        self.assertEqual(status["missing_eod_sessions"], [self.sessions[0]])
        self.assertEqual(daily, [])
        self.assertEqual(weekly, [])

    def test_tdcc_source_failure_is_not_downgraded(self):
        self.receipt["status"] = "BLOCKED"
        self.receipt["blockers"] = ["INSUFFICIENT_VERIFIED_TDCC_WEEKS:1<3"]
        status, daily, weekly = self.check()
        self.assertIn("INSUFFICIENT_VERIFIED_TDCC_WEEKS:1<3", status["blockers"])
        self.assertIn("CANONICAL_INPUT_RECEIPT_NOT_READY", status["blockers"])
        self.assertEqual((daily, weekly), ([], []))

    def test_invalid_choice_stops_before_data_reads(self):
        (self.root / mod.MODEL_CHOICE).unlink()
        def forbidden(*_):
            self.fail("Data inspector should not run with invalid choice")
        status, _, _ = self.check(inspector=forbidden)
        self.assertEqual(status["source_status"], "BLOCKED_BEFORE_SOURCE_AUDIT")
        self.assertIn("V22_USER_MODEL_CHOICE_UNVERIFIED", status["blockers"])

    def test_formal_authority_drift_fails_closed(self):
        (self.root / mod.STRATEGY_AUTHORITY).write_text(json.dumps({
            "active_strategy_count": 1,
            "selection_authority": True, "broker_order_execution": False
        }), encoding="utf-8")
        status, _, _ = self.check()
        self.assertIn("EXISTING_STRATEGY_AUTHORITY_BOUNDARY_UNVERIFIED", status["blockers"])

    def test_non_friday_or_future_date_fail_closed(self):
        for d, problem in [(date(2026, 11, 9), "DECISION_NOT_FRIDAY"),
                           (date(2026, 11, 13), "DECISION_IN_FUTURE")]:
            state, a, b = mod.market_readiness(self.root, d, today=date(2026,11,10),
                inspector=lambda *_: self.fail("Unexpected source read"))
            self.assertIn(problem, state["blockers"])
            self.assertEqual(a, [])
            self.assertEqual(b, [])

    def test_calendar_failure_blocks(self):
        with patch.object(mod, "load_manifest", side_effect=ValueError("hash mismatch")):
            state, _, _ = self.check()
        self.assertIn("OFFICIAL_TRADING_CALENDAR_UNVERIFIED", state["blockers"])

    def test_write_checkpoint_is_external_and_no_selector_files(self):
        state, daily, weekly = self.check()
        out = self.root.parent / "prepared"
        mod.write_checkpoint(self.root, out, state, daily, weekly)
        data = json.loads((out / "readiness.json").read_text(encoding="utf-8"))
        self.assertFalse(data["formal_selection_authority"])
        self.assertFalse((out / "selection.json").exists())
        with (out / "verified_daily_input.csv").open(encoding="utf-8-sig") as f:
            self.assertEqual(next(csv.DictReader(f))["Ticker"], "3042")
        self.assertTrue((out / "verified_tdcc_input.csv").exists())

    def test_blocked_status_writes_no_selection_or_partial_csv(self):
        self.receipt["status"] = "BLOCKED"
        self.receipt["blockers"] = ["INSUFFICIENT_VERIFIED_EOD_DAYS:18<21"]
        state, daily, weekly = self.check()
        out = self.root.parent / "blocked"
        mod.write_checkpoint(self.root, out, state, daily, weekly)
        self.assertTrue((out / "readiness.json").exists())
        self.assertFalse((out / "verified_daily_input.csv").exists())
        self.assertFalse((out / "selection.json").exists())

    def test_never_mutates_original_repo(self):
        state, daily, weekly = self.check()
        with self.assertRaisesRegex(mod.DataBlocked, "OUTPUT_MUST_BE_OUTSIDE_HENGCE_REPOSITORY"):
            mod.write_checkpoint(self.root, self.root / "eod" / "new", state, daily, weekly)


if __name__ == "__main__":
    unittest.main()
