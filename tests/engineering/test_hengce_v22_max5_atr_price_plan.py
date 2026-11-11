"""Fail-closed research-only V2.2 original Top5 -> MAX5 ATR20 price worklist."""
import csv
import hashlib
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.hengce_v22_max5_atr_price_plan import (
    OriginalPriceVessel, PriceEvidenceBlocked, _calendar, _sessions_ending,
    advance_atr_floor, build_price_plan, LOCK, BASE_CAL, EXTRA_CAL,
)
from scripts.hengce_scan_once_router import report

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime.fromisoformat("2026-11-06T20:00:00+08:00")


class V22MAX5ATRPriceResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in (LOCK, BASE_CAL, EXTRA_CAL):
            dest = self.root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes((ROOT / rel).read_bytes())
        self.calendar = _calendar(self.root)
        self.tickers = ["3042", "6446"] + [str(n) for n in range(1101, 2001)]
        self.days = _sessions_ending(self.calendar, date(2026, 11, 6), 21)
        self.select = {
            "status": "WEEKLY_RESEARCH_TOP5_READY",
            "source_date": "2026-11-06",
            "source_kind": "HENGCE_ORIGINAL_EOD_TDCC_RESEARCH_ONLY",
            "formal_selection_authority": False,
            "broker_execution": False,
            "buy_signal": False,
            "top5": [{"ticker": "3042", "rank": 1}, {"ticker": "6446", "rank": 2}],
        }

    def put(self, path, obj):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        return p

    def set_day(self, day, *, no_close=None, gap_factor=0):
        code = day.strftime("%Y%m%d")
        folder = self.root / "eod" / code
        folder.mkdir(parents=True, exist_ok=True)
        names = []
        h = hashlib.sha256()
        offset = (day - self.days[0]).days
        for shard in range(9):
            name = f"price_{shard+1}.csv"
            names.append(name)
            chunk = self.tickers[shard*101:(shard+1)*101]
            lines = ["Date,Ticker,Open,High,Low,Close"]
            for ticker in chunk:
                if ticker == no_close:
                    cols = ["--"]*4
                else:
                    base = 100 + offset
                    cols = [base, base+2, base-1, base+1]
                    if ticker == "6446":
                        cols = [v + 20 for v in cols]
                    if ticker == "3042" and gap_factor:
                        cols = [v * gap_factor for v in cols]
                lines.append(",".join([day.isoformat(), ticker] + [str(x) for x in cols]))
            blob = ("\n".join(lines) + "\n").encode("utf-8")
            (folder / name).write_bytes(blob)
            h.update(name.encode("utf-8"))
            h.update(b"\0")
            h.update(blob)
            h.update(b"\0")
        sha = h.hexdigest()
        self.put(f"eod/{code}/status.json", {
            "status": "COMPLETE", "target_date": day.isoformat(),
            "formal_complete_day": True, "three_leg_complete": True,
            "downstream_ready": True, "mother_status": "COMPLETE",
            "mother_receipt_status": "PASS", "second_mother": False,
            "mother_sha256": "m" * 64,
            "price_status": "COMPLETE", "price_date": day.isoformat(),
            "institutional_status": "COMPLETE", "institutional_date": day.isoformat(),
            "margin_status": "COMPLETE", "margin_date": day.isoformat(),
            "price_sha256": sha})
        self.put(f"eod/{code}/receipts/mother.json", {
            "status": "PASS", "target_date": day.isoformat(),
            "three_leg_complete": True, "second_mother": False,
            "integrity_status": "PASS", "mother_sha256": "m" * 64,
            "promoted_leg_sha256": {"price": sha}})
        self.put(f"eod/{code}/receipts/price.json", {
            "status": "COMPLETE", "leg": "price", "target_date": day.isoformat(),
            "sha256": sha, "rows": len(self.tickers), "files": names})

    def populate(self, including_monday=False):
        for day in self.days:
            self.set_day(day)
        if including_monday:
            self.set_day(date(2026, 11, 9))

    def build(self, now=NOW, holdings=None, select=None):
        return build_price_plan(now, self.root,
                                verified_v22=self.select if select is None else select,
                                holdings=holdings)

    def test_historical_or_no_weekly_reader_is_not_live(self):
        self.assertEqual(build_price_plan(NOW, self.root)["status"],
                         "WAITING_EXISTING_VERIFIED_V22_WEEKLY_READER")
        x = self.build(select={"status": "HISTORICAL_RESEARCH_TOP5_VERIFIED"})
        self.assertEqual(x["status"], "WAITING_VERIFIED_WEEKLY_V22_TOP5")
        self.assertEqual(x["candidate_price_plans"], [])

    def test_only_original_21_verified_sessions_can_create_atr(self):
        self.populate()
        x = self.build(holdings=[])
        self.assertEqual(x["status"], "ATR_PRICE_RESEARCH_READY_NO_TRADE_AUTHORITY")
        self.assertEqual(x["candidate_count"], 2)
        self.assertEqual(x["one_research_entry_candidate"], "3042")
        self.assertEqual(x["entry_capacity_status"], "ONE_WEEKLY_RESEARCH_ENTRY_SLOT_AVAILABLE")
        first, second = x["candidate_price_plans"]
        self.assertEqual(first["atr_window_start"], self.days[0].isoformat())
        self.assertEqual(first["atr_window_end"], "2026-11-06")
        self.assertEqual(first["atr_method"], "SMA20_OF_TRUE_RANGE")
        self.assertEqual(first["signal_atr20"], 3)
        self.assertEqual(first["status"], "ATR_READY_WAITING_NEXT_OPEN_AND_ACCOUNT_CAPACITY")
        self.assertTrue(first["within_one_weekly_entry_limit"])
        self.assertFalse(second["within_one_weekly_entry_limit"])
        self.assertFalse(x["next_open_price_known_in_advance"])
        self.assertFalse(x["buy_signal"])
        self.assertFalse(x["sell_signal"])
        self.assertFalse(x["broker_execution"])

    def test_future_monday_open_not_leaked_into_friday(self):
        self.populate(including_monday=True)
        x = self.build()
        self.assertEqual(x["planned_next_session"], "2026-11-09")
        self.assertNotIn("research_observed_next_open", x["candidate_price_plans"][0])
        self.assertEqual(x["entry_capacity_status"], "ACTUAL_ACCOUNT_HOLDINGS_REQUIRED")

    def test_monday_eod_open_is_historical_reference_not_actual_fill(self):
        self.populate(including_monday=True)
        x = self.build(datetime.fromisoformat("2026-11-09T21:00:00+08:00"),
                       holdings=[])
        p = x["candidate_price_plans"][0]
        self.assertEqual(p["research_observed_next_open"], 103)
        self.assertEqual(p["research_initial_floor_from_observed_open"], 97)
        self.assertEqual(p["status"], "OFFICIAL_OPEN_RESEARCH_REFERENCE_NOT_BROKER_FILL")
        self.assertTrue(p["research_buy_fill_not_verified"])

    def test_missing_one_official_day_blocks_price_not_buys(self):
        self.populate()
        (self.root / f"eod/{self.days[4]:%Y%m%d}/status.json").unlink()
        x = self.build(holdings=[])
        self.assertEqual(x["status"], "BLOCKED_MISSING_VERIFIED_ATR_EOD")
        self.assertIn("SOURCE_UNREADABLE", x["candidate_price_plans"][0]["block_reason"])
        self.assertIsNone(x["one_research_entry_candidate"])

    def test_tampered_ohlc_sha_blocks_without_fallback(self):
        self.populate()
        p = self.root / f"eod/{self.days[2]:%Y%m%d}/price_1.csv"
        p.write_bytes(p.read_bytes().replace(b"3042", b"3043", 1))
        x = self.build()
        self.assertEqual(x["status"], "BLOCKED_MISSING_VERIFIED_ATR_EOD")
        self.assertIn("ORIGINAL_EOD_SHARD_HASH_OR_COUNT_MISMATCH",
                      x["candidate_price_plans"][0]["block_reason"])

    def test_official_no_close_row_blocks_only_affected_ticker(self):
        self.populate()
        self.set_day(self.days[5], no_close="3042")
        x = self.build(holdings=[])
        self.assertEqual(x["status"], "PARTIAL_PRICE_EVIDENCE_NO_TRADE_AUTHORITY")
        self.assertEqual(x["candidate_price_plans"][0]["status"], "BLOCKED_ATR_EVIDENCE")
        self.assertEqual(x["one_research_entry_candidate"], "6446")
        self.assertEqual(x["candidate_price_plans"][1]["signal_atr20"], 3)

    def test_risk_floor_trailing_only_raises_and_latches(self):
        # Initial = 100, fill = 110; no trailing stop before +20%
        a = advance_atr_floor(110, 100, 100, 112, 115, 3)
        self.assertFalse(a["trail_active"])
        self.assertEqual(a["effective_risk_floor"], 100)
        b = advance_atr_floor(110, 100, 100, 115, 133, 3)
        self.assertTrue(b["trail_active"])
        self.assertEqual(b["effective_risk_floor"], 121)
        c = advance_atr_floor(110, 100, 121, 133, 130, 5)
        self.assertEqual(c["effective_risk_floor"], 121)
        self.assertFalse(c["exit_triggered"])
        d = advance_atr_floor(110, 100, 121, 133, 118, 5)
        self.assertTrue(d["exit_signal_new_today"])
        e = advance_atr_floor(110, 100, 121, 133, 137, 3, pending_exit=True)
        self.assertTrue(e["exit_triggered"])
        self.assertFalse(e["exit_signal_new_today"])

    def test_actual_account_required_and_max5_rejects_overallocation(self):
        self.populate()
        six = [{"ticker": str(i)} for i in range(1111,1117)]
        x = self.build(holdings=six)
        self.assertEqual(x["status"], "BLOCKED_HOLDING_INPUT")
        self.assertEqual(x["candidate_price_plans"], [])
        x = self.build(holdings=[])
        self.assertEqual(x["one_research_entry_candidate"], "3042")
        self.assertFalse(x["formal_selection_authority"])

    def test_existing_account_holding_is_skipped_in_ranked_weekly_candidate(self):
        self.populate()
        holding = {"ticker": "3042", "entry_date": "2026-11-06",
                   "entry_fill": 110, "quantity": 1000}
        x = self.build(holdings=[holding])
        self.assertEqual(x["one_research_entry_candidate"], "6446")
        self.assertEqual(len(x["existing_position_risk"]), 1)
        self.assertEqual(x["existing_position_risk"][0]["status"], "BLOCKED")

    def test_policy_or_calendar_missing_blocks_no_eod_guessing(self):
        (self.root / BASE_CAL).unlink()
        x = self.build()
        self.assertEqual(x["status"], "BLOCKED_UNVERIFIED_PRICE_POLICY")
        self.assertEqual(x["reason"], "EXISTING_TWSE_CALENDAR_UNVERIFIED")

    def test_actual_scan_route_remains_zero_authority_and_no_data_guess(self):
        result = report(NOW, self.root)
        atr = result["reporting"]["v22_atr_max5_price_plan"]
        self.assertEqual(atr["status"], "WAITING_VERIFIED_WEEKLY_V22_TOP5")
        self.assertFalse(atr["broker_execution"])
        self.assertEqual(result["status"], "NO_ACTIVE_SELECTION_STRATEGY")
        self.assertEqual(result["rows"], [])
        self.assertFalse(result["buy_signal"])
        self.assertFalse(result["sell_signal"])

    def test_same_inputs_are_deterministic(self):
        self.populate()
        self.assertEqual(self.build(holdings=[]), self.build(holdings=[]))


if __name__ == "__main__":
    unittest.main()
