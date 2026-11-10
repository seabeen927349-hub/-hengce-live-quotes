"""Fail-closed tests for research-only whole-lot board. No brokerage or vendor calls."""
import importlib.util
from pathlib import Path
import unittest

SOURCE=Path(__file__).resolve().parents[2]/"scripts/hengce_retail_wholelot_display.py"
spec=importlib.util.spec_from_file_location("wholelot_shadow_board",SOURCE)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
DATE="2026-11-09"

def contract():
    return {"status":"NO_ACTIVE_SELECTION_STRATEGY","active_strategy_count":0,
            "broker_order_execution":False,"capital_authority_twd":0}

def candidate(ticker,rank,price):
    return {"rank":rank,"ticker":ticker,"name":ticker,
            "reference_close_date":DATE,"reference_close_twd":price,
            "ranking_basis":"FROZEN_20D_MEDIAN_TURNOVER_DESC",
            "qualified_signal_verified":True,
            "tdcc_available_at_decision":True,"stock_tradable_verified":True,
            "rms":"PASS","s5":"PASS","escape":"PASS","investor_access":"PASS"}

def snapshot():
    return {"schema":module.RANK_SCHEMA,"signal_asof":DATE,"authority":"RESEARCH_ONLY",
            "pit_verified":True,"frozen_source":True,"source_sha256":"a"*64,
            "ranked_candidates":[candidate("2254",1,110),candidate("6782",2,274.5)]}

def account():
    return {"scope":"INDEPENDENT_RESEARCH_ACCOUNT","equity_twd":1_000_000,
            "free_cash_twd":1_000_000,"held_tickers":[]}

class BoardTest(unittest.TestCase):
    def test_no_upstream_no_rank(self):
        r=module.evaluate(None,account(),contract(),DATE)
        self.assertEqual(r["status"],"DATA_BLOCKED")
        self.assertEqual(r["research_top10"],[])

    def test_no_authority_even_when_preview_ready(self):
        r=module.evaluate(snapshot(),account(),contract(),DATE)
        self.assertEqual(r["status"],"RESEARCH_DISPLAY_READY")
        self.assertFalse(r["formal_selection"])
        self.assertFalse(r["broker_order_execution"])
        self.assertEqual(r["capital_authority_twd"],0)
        self.assertEqual([x["lots_simulated"] for x in r["research_top10"]],[2,1])
        self.assertEqual([x["one_lot_estimated_cost_twd"] for x in r["research_top10"]],[110275,275187])
        self.assertGreaterEqual(r["preview_cash_remaining_twd"],100000)

    def test_risk_unknown_blocks_not_defaults_to_pass(self):
        s=snapshot();s["ranked_candidates"][0]["rms"]=None
        r=module.evaluate(s,account(),contract(),DATE)
        self.assertEqual(r["research_top10"][0]["lots_simulated"],0)
        self.assertIn("RMS_NOT_PASS",r["research_top10"][0]["reasons"])

    def test_retirement_contract_must_remain_retired(self):
        x=contract();x["active_strategy_count"]=1
        r=module.evaluate(snapshot(),account(),x,DATE)
        self.assertEqual(r["status"],"DATA_BLOCKED")

    def test_ranking_must_be_frozen(self):
        x=snapshot();x["ranked_candidates"][1]["rank"]=3
        r=module.evaluate(x,account(),contract(),DATE)
        self.assertEqual(r["reason"],"NON_FROZEN_RANK_ORDER")

    def test_current_actual_position_required(self):
        x=account()
        x["actual_positions_for_review"]=[{
            "ticker":"3042","entry_cost_twd":100,"latest_close_twd":91,
            "max_close_since_entry_twd":120,"ma30_twd":105,
            "below_ma30_three_days":True,"return_5d_pct":-7,
            "shares_confirmed_asof":DATE,"close_asof":DATE}]
        r=module.evaluate(snapshot(),x,contract(),DATE)
        p=r["position_reviews"][0]
        self.assertEqual(p["status"],"HUMAN_EXIT_REVIEW")
        self.assertEqual(len(p["trigger_reasons"]),3)
        self.assertFalse(p["formal_can_sell"])
        x["actual_positions_for_review"][0]["shares_confirmed_asof"]="2026-10-21"
        r=module.evaluate(snapshot(),x,contract(),DATE)
        self.assertEqual(r["position_reviews"][0]["status"],"DATA_BLOCKED")

    def test_held_position_not_rebought(self):
        x=account();x["held_tickers"]=["2254"]
        r=module.evaluate(snapshot(),x,contract(),DATE)
        self.assertIn("ALREADY_HELD",r["research_top10"][0]["reasons"])

if __name__=="__main__":
    unittest.main()
