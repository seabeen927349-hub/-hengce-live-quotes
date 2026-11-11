"""V2.2-D switch: archived daily Top5 is never today's order or old V2.2."""
import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from scripts.hengce_v22d_daily_reader import observation, selected_v22d
from scripts.hengce_scan_once_router import report, selected_model_preference, research_top5_observation

ROOT=Path(__file__).resolve().parents[2]
PREF="hengce/HENGCE_SELECTION_MODEL_CHOICE_LATEST.json"
V22D="research/retail_top5/v22d_historical_20261105.json"
V22="research/retail_top5/v22_research_latest.json"
LIVE="research/retail_top5/v22d_daily_latest.json"
NOW=datetime.fromisoformat("2026-11-11T22:49:00+08:00")


class V22DPrimarySwitchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for file in (
            PREF, V22D, V22,
            "governance/HENGCE_V22_ATR_MAX5_PRICE_PLAN_RESEARCH_v1_20261111.json",
            "governance/TWSE_TRADING_CALENDAR_2026_v1.json",
            "governance/TWSE_EXTRAORDINARY_CLOSURES_2026_v1.json",
        ):
            target=self.root/file
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((ROOT/file).read_bytes())

    def test_preferred_is_v22d_not_v22(self):
        p=selected_model_preference(self.root)
        self.assertEqual(p["status"],"PREFERRED_DAILY_RESEARCH_MODEL_NOT_LIVE")
        self.assertEqual(p["model_id"],"v22d_daily_nowcast_liquidity_top5_v1")
        self.assertEqual(p["legacy_v22_role"],"BENCHMARK_ONLY_NOT_PRIMARY")
        self.assertFalse(p["broker_execution"])
        self.assertTrue(selected_v22d(self.root))

    def test_independent_archive_daily_top5_and_provenance(self):
        p=observation(NOW,self.root)
        self.assertEqual(p["status"],"HISTORICAL_V22D_TOP5_VERIFIED")
        self.assertEqual(p["source_date"],"2026-11-05")
        self.assertEqual(p["qualified_count"],7)
        self.assertEqual([x["ticker"] for x in p["top5"]],
                         ["1216","2618","1476","9904","2610"])
        self.assertEqual([x["daily_decline_score"] for x in p["top5"][:2]],
                         [.65616614,.701428])
        self.assertFalse(p["score_is_calibrated_probability"])
        self.assertFalse(p["current_selection"])
        self.assertTrue(p["not_current_recommendations"])

    def test_legacy_weekly_is_only_benchmark_and_still_reproducible(self):
        a=research_top5_observation(NOW,self.root)
        self.assertEqual(a["status"],"HISTORICAL_RESEARCH_TOP5_VERIFIED")
        self.assertEqual([x["ticker"] for x in a["top5"]],
                         ["6446","2412","1476","2610","2254"])
        r=report(NOW,self.root)
        self.assertTrue(r["reporting"]["v22_legacy_benchmark_only"])
        self.assertEqual(r["reporting"]["v22d_primary_research_top5"]["status"],
                         "HISTORICAL_V22D_TOP5_VERIFIED")
        self.assertEqual(r["reporting"]["selected_model_preference"]["model_id"],
                         "v22d_daily_nowcast_liquidity_top5_v1")
        self.assertEqual(r["reporting"]["v22d_atr_max5_price_plan"]["status"],
                         "WAITING_CURRENT_VERIFIED_V22D_DAILY_FORECAST")
        self.assertFalse(r["reporting"]["v22d_atr_max5_price_plan"]["broker_execution"])
        self.assertEqual(r["status"],"NO_ACTIVE_SELECTION_STRATEGY")
        self.assertEqual(r["reporting"]["top10"],[])
        self.assertEqual(r["rows"],[])
        self.assertFalse(r["buy_signal"])
        self.assertFalse(r["sell_signal"])
        self.assertFalse(r["broker_order_execution"])

    def test_past_archive_not_available_before_historical_decision(self):
        p=observation(datetime.fromisoformat("2026-11-04T19:30:00+08:00"),self.root)
        self.assertEqual(p["status"],"V22D_HISTORICAL_SOURCE_UNVERIFIED")
        self.assertEqual(p["top5"],[])

    def test_source_score_and_order_tampering_fail_closed(self):
        target=self.root/V22D
        baseline=json.loads(target.read_text(encoding="utf-8"))
        for mutation in (
            lambda d:d["top5"][0].update({"daily_decline_score":.19}),
            lambda d:d["all_qualified"][0].update({"daily_decline_score":.19}),
            lambda d:d.update({"source_package_sha256":"fake"}),
            lambda d:d["all_qualified"][2].update({"rank":1}),
            lambda d:d["all_qualified"][0].update({"last_assumed_available_tdcc_date":"2026-11-06"}),
            lambda d:d["all_qualified"][1].update({"median_20d_turnover_twd":5000000000}),
            lambda d:d.update({"broker_execution":True}),
            lambda d:d.update({"decision_date":"not-a-date"}),
        ):
            d=copy.deepcopy(baseline)
            mutation(d)
            target.write_text(json.dumps(d,ensure_ascii=False),encoding="utf-8")
            self.assertEqual(observation(NOW,self.root)["status"],
                             "V22D_HISTORICAL_SOURCE_UNVERIFIED")
        target.write_text(json.dumps(baseline,ensure_ascii=False),encoding="utf-8")

    def test_fake_live_receipt_is_not_promoted_and_old_v22_not_fallback(self):
        target=self.root/LIVE
        target.write_text(json.dumps({"decision_date":"2026-11-11",
                                      "status":"LIVE","top5":[{"ticker":"1216"}]}))
        x=observation(NOW,self.root)
        self.assertEqual(x["status"],"V22D_CURRENT_FORECAST_NEEDS_VERIFIED_MODEL_AND_PIT_INPUTS")
        self.assertEqual(x["top5"],[])
        self.assertFalse(x["current_selection"])

    def test_preference_forgery_does_not_activate_orders(self):
        target=self.root/PREF
        original=json.loads(target.read_text(encoding="utf-8"))
        for key,value in (
            ("formal_selection_authority",True),
            ("broker_execution",True),
            ("authorized_lots",1),
            ("capital_authority_twd",200000),
            ("source_package_sha256","wrong"),
            ("choice_status","ACTIVE_TRADING")
        ):
            x=copy.deepcopy(original)
            x[key]=value
            target.write_text(json.dumps(x,ensure_ascii=False),encoding="utf-8")
            self.assertEqual(selected_model_preference(self.root)["status"],
                             "PREFERENCE_INVALID_FAIL_CLOSED")
            self.assertEqual(observation(NOW,self.root)["status"],
                             "V22D_PREFERENCE_UNVERIFIED")
        target.write_text(json.dumps(original,ensure_ascii=False),encoding="utf-8")

    def test_deterministic_same_asof(self):
        self.assertEqual(observation(NOW,self.root),observation(NOW,self.root))
        self.assertEqual(report(NOW,self.root),report(NOW,self.root))


if __name__=="__main__":
    unittest.main()
