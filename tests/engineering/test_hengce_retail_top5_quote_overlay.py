"""Fail-closed regression checks for V2.2 quote overlay; mock sources only."""
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TARGET = Path(__file__).resolve().parents[2] / "scripts" / "hengce_retail_top5_quote_overlay.py"
spec = importlib.util.spec_from_file_location("v22_quote_overlay", TARGET)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
TW = ZoneInfo("Asia/Taipei")


def put(root, file, data):
    p = root / file
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")


def selection():
    return {
        "version": "hengce_selection_v2_2",
        "mode": "research_selection",
        "authority": "NO_TRADING_AUTHORITY",
        "official_source_verified": False,
        "verification_scope": "BUNDLED_REFERENCE_ONLY",
        "decision": "2026-11-06",
        "selected_count": 2,
        "candidates": [
            {"rank": 1, "ticker": "2412", "reference_close": 160},
            {"rank": 2, "ticker": "3042", "reference_close": 136},
        ],
    }


class QuoteOverlayTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.now = datetime(2026, 11, 10, 15, 50, tzinfo=TW)
        self.status = {
            "schema_version": 3,
            "authority": "INTRADAY_QUOTE_TRANSPORT_ONLY_NO_MODEL_RANKING_AUTHORITY",
            "snapshot_id": "20261110-A",
            "generated_at_taipei": "2026-11-10T15:45:00+08:00",
            "cache_expires_at_taipei": "2026-11-10T15:55:00+08:00",
            "requested_count": 1,
            "market_phase": "closed",
            "broker_order_execution": False,
        }
        self.q = {
            "snapshot_id": "20261110-A", "symbol": "2412", "price": 159.5,
            "previous_close": 159, "volume": 18000, "fetch_ok": True,
            "is_trial": False, "is_halted": False, "stale_at_publish": False,
            "quote_date": "2026-11-10",
            "fetched_at_taipei": "2026-11-10T15:45:00+08:00",
            "last_trade_time": "2026-11-10T13:30:00+08:00",
            "change_percent": 0.31,
        }
        put(self.root, "legacy_live/status.json", self.status)
        put(self.root, "legacy_live/active.json", {
            **self.status, "data": [self.q]})
        put(self.root, "escape_live/finmind_twse_common_status.json", {
            "generated_at_taipei": "2026-11-10T15:45:00+08:00",
            "per_security_rows_persisted": False, "formal_eod_authority": False,
            "active_covered_count": 1088, "current_market_date_count": 1082})

    def test_valid_quote_is_observation_not_signal(self):
        x = m.overlay(self.root, selection(), self.now)
        self.assertEqual(x["top5_rows"], 2)
        self.assertEqual(x["current_session_quotes"], 1)
        self.assertEqual(x["quotes"][0]["quote_status"], "CURRENT_SESSION_SNAPSHOT")
        self.assertEqual(x["quotes"][0]["last_executed_price_reference"], 159.5)
        self.assertEqual(x["quotes"][1]["quote_status"], "NO_EXISTING_TICKER_QUOTE")
        self.assertEqual(x["uncovered_or_stale_tickers"], ["3042"])
        self.assertEqual([z["ticker"] for z in x["quotes"]], ["2412", "3042"])
        self.assertFalse(x["ranking_changed"])
        self.assertFalse(x["buy_signal"])
        self.assertFalse(x["sell_signal"])
        self.assertFalse(x["broker_execution"])
        self.assertEqual(x["authorized_lots"], 0)
        self.assertEqual(x["finmind_aggregate"]["status"], "SAME_DAY_AGGREGATE_ONLY")
        self.assertFalse(x["finmind_aggregate"]["per_ticker_quotes"])

    def test_stale_quote_not_current(self):
        x = m.overlay(self.root, selection(), datetime(2026,11,10,16,30,tzinfo=TW))
        self.assertEqual(x["current_session_quotes"], 0)
        self.assertEqual(x["quotes"][0]["quote_status"], "EXPIRED_SESSION_SNAPSHOT")

    def test_trial_price_not_executed(self):
        q = {**self.q, "is_trial": True}
        put(self.root, "legacy_live/active.json", {**self.status, "data": [q]})
        x = m.overlay(self.root, selection(), self.now)
        self.assertEqual(x["quotes"][0]["quote_status"], "TRIAL_NOT_EXECUTED")
        self.assertIsNone(x["quotes"][0]["last_executed_price_reference"])
        self.assertFalse(x["quotes"][0]["session_quote_is_current"])

    def test_halted_not_tradable(self):
        q = {**self.q, "is_halted": True}
        put(self.root, "legacy_live/active.json", {**self.status, "data": [q]})
        x = m.overlay(self.root, selection(), self.now)
        self.assertEqual(x["quotes"][0]["quote_status"], "HALTED_REVIEW")
        self.assertIsNone(x["quotes"][0]["last_executed_price_reference"])

    def test_duplicate_candidates_fail_closed(self):
        s = selection()
        s["candidates"][1]["ticker"] = "2412"
        with self.assertRaises(m.EvidenceBlocked):
            m.overlay(self.root, s, self.now)

    def test_snapshot_mismatch_rejected(self):
        put(self.root, "legacy_live/active.json", {**self.status, "snapshot_id":"OTHER", "data":[self.q]})
        x = m.overlay(self.root, selection(), self.now)
        self.assertEqual(x["current_session_quotes"], 0)
        self.assertEqual(x["source_receipts"][1]["status"], "SNAPSHOT_MISMATCH")

    def test_do_not_promote_to_eod_or_repo_write(self):
        x = m.overlay(self.root, selection(), self.now)
        self.assertTrue(all(row["official_eod_close"] is None for row in x["quotes"]))
        self.assertFalse(x["formal_eod_replaced"])
        with self.assertRaises(m.EvidenceBlocked):
            m.write_output(self.root, self.root / "eod/20261110/output.json", x)

    def test_frozen_single_name_preferred_when_valid(self):
        put(self.root, "legacy_live/frozen_single_name_status.json", {
            "authority": "QUOTE_TRANSPORT_ONLY_NO_RANKING_SIGNAL_CAPITAL_AUTHORITY",
            "snapshot_id": "20261110-B",
            "generated_at_taipei": "2026-11-10T15:48:00+08:00",
            "cache_expires_at_taipei": "2026-11-10T15:58:00+08:00",
            "requested_count": 1,
            "symbols": ["3042"],
            "market_phase": "closed",
        })
        put(self.root, "legacy_live/quotes/3042.json", {
            **self.q, "snapshot_id": "20261110-B", "symbol": "3042",
            "price": 141.5, "fetched_at_taipei": "2026-11-10T15:48:00+08:00"})
        x = m.overlay(self.root, selection(), self.now)
        self.assertEqual(x["current_session_quotes"], 2)
        self.assertEqual(x["quotes"][1]["source"], "FROZEN_SINGLE_NAME")
        self.assertEqual(x["quotes"][1]["last_executed_price_reference"], 141.5)

    def test_unauthorized_receipt_refused(self):
        x = selection()
        x["authority"] = "OFFICIAL_LIVE"
        with self.assertRaises(m.EvidenceBlocked):
            m.overlay(self.root, x, self.now)


    def test_refresh_uncovered_through_existing_fugle_fetcher(self):
        calls = []
        def mocked_fetch(symbol, key, telemetry):
            calls.append((symbol, key))
            return ({
                "symbol": symbol, "date": "2026-11-10",
                "lastTrade": {"price": 141.5, "time": int(self.now.timestamp() * 1_000_000)},
                "total": {"tradeVolume": 9054}, "previousClose": 135,
                "isTrial": False, "tradingHalt": {"isHalted": False},
            }, {"attempts": 1}, None)
        result = m.overlay(self.root, selection(), self.now)
        result = m.refresh_uncovered_from_fugle(
            self.root, result, "fake-key",
            fetcher=mocked_fetch, pause=lambda _: None, clock=lambda: self.now)
        self.assertEqual(calls, [("3042", "fake-key")])
        self.assertEqual(result["current_session_quotes"], 2)
        self.assertEqual(result["quotes"][1]["last_executed_price_reference"], 141.5)
        self.assertEqual(result["quotes"][1]["source"], "FUGLE_EXISTING_TRANSPORT_ON_DEMAND")
        self.assertTrue(result["on_demand_existing_fugle"]["used_existing_fetch_function"])
        self.assertFalse(result["on_demand_existing_fugle"]["new_market_data_endpoint"])
        self.assertFalse(result["broker_execution"])
        self.assertFalse(result["buy_signal"])

    def test_trial_only_direct_refresh_rejected(self):
        def mocked_fetch(symbol, key, telemetry):
            return ({
                "symbol": symbol, "date": "2026-11-10",
                "lastTrade": {},
                "lastPrice": 150,
                "total": {"tradeVolume": 100},
                "isTrial": True,
            }, {"attempts": 1}, None)
        result = m.overlay(self.root, selection(), self.now)
        result = m.refresh_uncovered_from_fugle(
            self.root, result, "fake-key",
            fetcher=mocked_fetch, clock=lambda: self.now)
        self.assertEqual(result["quotes"][1]["quote_status"], "TRIAL_NOT_EXECUTED")
        self.assertIsNone(result["quotes"][1]["last_executed_price_reference"])
        self.assertEqual(result["current_session_quotes"], 1)

    def test_historical_asof_refetch_forbidden(self):
        result = m.overlay(self.root, selection(), self.now)
        later = datetime(2026, 11, 10, 16, 45, tzinfo=TW)
        with self.assertRaisesRegex(m.EvidenceBlocked, "HISTORICAL_REPLAY"):
            m.refresh_uncovered_from_fugle(
                self.root, result, "fake-key", fetcher=lambda *_:None,
                clock=lambda: later)


if __name__ == "__main__":
    unittest.main()
