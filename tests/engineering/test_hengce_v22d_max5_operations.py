"""V2.2-D/MAX5 account-review safety; mocks only the market data values in tests.

Production code always uses the ORIGINAL HENGCE EOD + mother SHA receipts.
"""
import copy
import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from scripts.hengce_v22d_max5_operations import (
    _calendar, worklist, HOLDING_COLS, JOURNAL_COLS,
)
from scripts.hengce_scan_once_router import report

ROOT=Path(__file__).resolve().parents[2]
NOW=datetime.fromisoformat("2026-11-11T23:55:00+08:00")
AM=datetime.fromisoformat("2026-11-11T08:45:00+08:00")


class SyntheticVerifiedPriceReader:
    """Test fixture only. Not a production quote/data-provider substitute."""
    def __init__(self, prices=None, atr=3):
        self.prices=prices or {}
        self.atr=atr
        self.checked=[]

    def ticker_day(self,day,ticker):
        self.checked.append((day,ticker))
        close=self.prices.get((day.isoformat(),ticker),100.0)
        if close is None:
            raise ValueError("ORIGINAL_SESSION_PRICE_UNAVAILABLE")
        return {"Open":close,"High":close+2,"Low":close-2,"Close":close}

    def atr20(self,day,ticker,calendar):
        return {"atr20":self.atr,"official_close":self.ticker_day(day,ticker)["Close"]}


def holding(ticker="3042",**fields):
    return {
        "ticker":ticker,"entry_date":"2026-11-10",
        "entry_fill":100,"quantity":1000,
        "signal_atr20":3,"risk_floor":94,
        "peak_close":100,"pending_exit":False,
        **fields
    }


class MAX5ReadOnlyOperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for file in (
            "hengce/HENGCE_SELECTION_MODEL_CHOICE_LATEST.json",
            "governance/TWSE_TRADING_CALENDAR_2026_v1.json",
            "governance/TWSE_EXTRAORDINARY_CLOSURES_2026_v1.json",
        ):
            dest=self.root/file
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes((ROOT/file).read_bytes())
        self.cal=_calendar(self.root)
        self.vessel=SyntheticVerifiedPriceReader()

    def go(self,when=NOW,holdings=None,journal=None,previous=None,
           selection=None,vessel=None):
        return worklist(when,self.root,holdings=holdings,
                        journal=journal,previous=previous,
                        selection=selection,vessel=vessel or self.vessel,
                        calendar=self.cal)

    @staticmethod
    def filled_sell(ticker="3042",qty=1000):
        return {"ticker":ticker,"trade_date":"2026-11-11",
                "side":"SELL","status":"FILLED","quantity":qty}

    @staticmethod
    def filled_buy(ticker="6446"):
        return {"ticker":ticker,"trade_date":"2026-11-11",
                "side":"BUY","status":"FILLED","quantity":1000}

    def daily_selection(self,tickers=None):
        return {
            "status":"CURRENT_V22D_PIT_TOP5_VERIFIED",
            "model":"V2.2-D",
            "source_kind":"ORIGINAL_V22D_CHECKPOINT_EOD_TDCC_PIT",
            "source_date":"2026-11-11",
            "top5":[{"ticker":s,"rank":i+1}
                    for i,s in enumerate(tickers or ["6446","1476","2412"])],
            "current_selection":True,
            "formal_selection_authority":False,
            "broker_execution":False,"buy_signal":False,"sell_signal":False,
            "authorized_lots":0,
        }

    def test_without_account_its_not_an_empty_portfolio(self):
        x=self.go()
        self.assertEqual(x["status"],"WAITING_ACTUAL_ACCOUNT_SNAPSHOT")
        self.assertEqual(x["account_status"],"ACCOUNT_HOLDINGS_NOT_PROVIDED")
        self.assertEqual(x["position_states"],[])
        self.assertIsNone(x["candidate"])
        self.assertFalse(x["broker_execution"])

    def test_one_position_daily_monitoring_without_current_research_model(self):
        x=self.go(holdings=[holding()])
        self.assertEqual(x["status"],"WAITING_VERIFIED_CURRENT_V22D_DAILY_FORECAST")
        self.assertEqual(x["review_eod_session"],"2026-11-11")
        p=x["position_states"][0]
        self.assertEqual(p["status"],"POSITION_RISK_MONITORED")
        self.assertEqual(p["initial_risk_floor"],94)
        self.assertEqual(p["effective_risk_floor"],94)
        self.assertFalse(p["pending_exit"])
        self.assertEqual(x["position_count"],1)
        self.assertEqual(x["remaining_slots"],4)
        self.assertEqual(x["journal_status"],"ACTUAL_WEEKLY_TRANSACTION_JOURNAL_NOT_PROVIDED")
        self.assertEqual(x["pending_exit_count"],0)
        self.assertIsNone(x["candidate"])

    def test_exit_trigger_latched_even_after_rebound(self):
        self.vessel=SyntheticVerifiedPriceReader({
            ("2026-11-10","3042"):90,
            ("2026-11-11","3042"):120,
        })
        x=self.go(holdings=[holding()])
        p=x["position_states"][0]
        self.assertEqual(p["status"],"EXIT_PENDING_MANUAL_CONFIRMATION")
        self.assertEqual(p["first_trigger_date"],"2026-11-10")
        self.assertTrue(p["pending_exit"])
        self.assertEqual(p["effective_risk_floor"],108)
        self.assertEqual(x["tasks"][0]["action"],"REVIEW_EXIT_NEXT_VALID_OPEN")
        self.assertTrue(x["tasks"][0]["must_verify_broker_fill"])
        self.assertFalse(x["sell_signal"])

    def test_pending_exit_must_be_carried_unless_account_sold(self):
        self.vessel=SyntheticVerifiedPriceReader({
            ("2026-11-10","3042"):90,
            ("2026-11-11","3042"):120,
        })
        past=self.go(datetime.fromisoformat("2026-11-10T23:55:00+08:00"),
                     holdings=[holding()])
        self.assertTrue(past["position_states"][0]["pending_exit"])
        current=holding()
        current["last_reviewed_session"]="2026-11-10"
        current["risk_floor"]=94
        current["peak_close"]=100
        current["pending_exit"]=False
        x=self.go(holdings=[current],previous=past)
        self.assertEqual(x["status"],"PARTIAL_HOLDING_RISK_BLOCKED_NO_NEW_BUY")
        self.assertEqual(x["position_states"][0]["reason"],
                         "PENDING_EXIT_LATCH_CANNOT_BE_CLEARED_WITHOUT_SELL")

    def test_source_missing_on_one_day_cannot_be_silent_hold(self):
        self.vessel=SyntheticVerifiedPriceReader({
            ("2026-11-11","3042"):None,
        })
        x=self.go(holdings=[holding()])
        self.assertEqual(x["status"],"PARTIAL_HOLDING_RISK_BLOCKED_NO_NEW_BUY")
        self.assertEqual(x["position_states"][0]["status"],"BLOCKED_POSITION_EVIDENCE")
        self.assertFalse(x["position_states"][0]["no_sell_conclusion_allowed"])
        self.assertEqual(x["tasks"],[])

    def test_no_injected_current_ranking_from_caller(self):
        fake=self.daily_selection()
        x=self.go(holdings=[],journal=[],selection=fake)
        self.assertEqual(x["status"],"WAITING_VERIFIED_CURRENT_V22D_DAILY_FORECAST")
        self.assertFalse(x["source_receipt_matches_repo_reader"])
        self.assertIsNone(x["candidate"])

    def test_candidate_when_test_fixture_authenticates_and_account_is_free(self):
        # We override the canonical *source reader* only in a synthetic unit
        # test. Production observation() rejects any unverified live receipt.
        fake=self.daily_selection()
        with patch("scripts.hengce_v22d_max5_operations.observation",
                   return_value=copy.deepcopy(fake)):
            x=self.go(holdings=[],journal=[],selection=fake)
        self.assertEqual(x["status"],"ONE_RESEARCH_NEXT_OPEN_ENTRY_SLOT_AVAILABLE")
        self.assertEqual(x["candidate"]["ticker"],"6446")
        self.assertEqual(x["candidate"]["planned_next_session"],"2026-11-12")
        self.assertEqual(x["candidate"]["signal_atr20"],3)
        self.assertEqual(x["candidate"]["initial_risk_floor_after_fill_formula"],
                         "ACTUAL_FILL_MINUS_2ATR20")
        self.assertFalse(x["candidate"]["requires_manual_account_and_execution_confirmation"] is False)
        self.assertFalse(x["buy_signal"])

    def test_only_one_new_buy_each_week_with_verified_current_mock(self):
        fake=self.daily_selection()
        with patch("scripts.hengce_v22d_max5_operations.observation",
                   return_value=copy.deepcopy(fake)):
            x=self.go(holdings=[],journal=[self.filled_buy()],selection=fake)
        self.assertEqual(x["status"],"WEEKLY_NEW_ENTRY_LIMIT_REACHED")
        self.assertEqual(x["weekly_buy_usage"]["filled_buy"],1)
        self.assertIsNone(x["candidate"])

    def test_existing_full_portfolio_cannot_reuse_pending_exit_slot(self):
        fake=self.daily_selection()
        held=[holding(str(k)) for k in range(3000,3005)]
        with patch("scripts.hengce_v22d_max5_operations.observation",
                   return_value=copy.deepcopy(fake)):
            x=self.go(holdings=held,journal=[],selection=fake)
        self.assertEqual(x["status"],"MAX5_FULL_INCLUDING_PENDING_EXITS")
        self.assertEqual(x["remaining_slots"],0)
        self.assertIsNone(x["candidate"])

    def test_six_positions_fail_before_price_reader(self):
        held=[holding(str(k)) for k in range(3000,3006)]
        x=self.go(holdings=held)
        self.assertEqual(x["status"],"BLOCKED_MAX5_OR_INVALID_HOLDINGS")
        self.assertEqual(self.vessel.checked,[])

    def test_previously_held_stock_cannot_disappear_without_sell_entry(self):
        past=self.go(holdings=[holding()])
        x=self.go(holdings=[],journal=[],previous=past)
        self.assertEqual(x["status"],
                         "BLOCKED_ACCOUNT_POSITION_DISAPPEARED_WITHOUT_SELL_RECEIPT")
        self.assertEqual(x["missing_prior_positions"],["3042"])

    def test_manual_sale_reconciles_but_is_not_broker_proof(self):
        past=self.go(datetime.fromisoformat("2026-11-10T23:55:00+08:00"),
                     holdings=[holding()])
        x=self.go(holdings=[],journal=[self.filled_sell()],previous=past)
        self.assertEqual(x["status"],"WAITING_VERIFIED_CURRENT_V22D_DAILY_FORECAST")
        self.assertEqual(x["position_count"],0)
        self.assertEqual(x["reported_closed_positions"][0]["closing_status"],
                         "USER_DECLARED_FILLED_NOT_BROKER_VERIFIED")

    def test_pre_23_uses_yesterday_eod_not_todays_future_eod(self):
        self.vessel=SyntheticVerifiedPriceReader({
            ("2026-11-10","3042"):100,
            ("2026-11-11","3042"):90,
        })
        x=self.go(AM,holdings=[holding()])
        self.assertEqual(x["review_eod_session"],"2026-11-10")
        self.assertEqual(x["position_states"][0]["status"],"POSITION_RISK_MONITORED")
        self.assertNotIn((date(2026,11,11),"3042"),self.vessel.checked)

    def test_incomplete_actual_account_entry_at_pre_23_not_assumed_complete(self):
        h=holding(entry_date="2026-11-11")
        x=self.go(AM,holdings=[h])
        self.assertEqual(x["position_states"][0]["status"],"BLOCKED_POSITION_EVIDENCE")
        self.assertEqual(x["status"],"PARTIAL_HOLDING_RISK_BLOCKED_NO_NEW_BUY")

    def test_report_integration_does_not_change_formal_no_order_contract(self):
        x=report(NOW,self.root,holdings=[holding()],journal=[])
        self.assertEqual(x["status"],"NO_ACTIVE_SELECTION_STRATEGY")
        self.assertEqual(x["rows"],[])
        self.assertFalse(x["buy_signal"])
        self.assertFalse(x["broker_order_execution"])
        self.assertIn("v22d_max5_daily_account_worklist",x["reporting"])
        self.assertFalse(x["reporting"]["v22d_max5_daily_account_worklist"]["broker_execution"])

    def test_repeat_same_evidence_and_account_is_deterministic(self):
        self.assertEqual(self.go(holdings=[holding()],journal=[]),
                         self.go(holdings=[holding()],journal=[]))


if __name__=="__main__":
    unittest.main()
