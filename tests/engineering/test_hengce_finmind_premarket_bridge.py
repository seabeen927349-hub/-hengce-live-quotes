#!/usr/bin/env python3
"""Governed FinMind to premarket bridge regression tests."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from hengce_finmind_premarket_bridge import build, METRIC_SHA

class FinMindBridgeTests(unittest.TestCase):
    def setUp(self):
        m={"constituent_count":1088,"return_observed_count":1085,"advance_count":105,
           "decline_count":953,"flat_count":27,"net_breadth":-848,
           "equal_weight_change_rate":-3.01176037,"total_amount":1006890618220}
        c={"market_date":"2026-11-06","metric_contract_sha256":METRIC_SHA,
           "monitoring_universe":"ALL_TWSE_LISTED_COMMON_STOCKS",
           "trading_authority":False,"generated_at_taipei":"2026-11-06T20:45:43+08:00"}
        self.ctx={**c,"market":m,"formal_escape_state_creation":False,
                  "current_market_date_ratio":0.99724265}
        self.stat={**c,"formal_escape_authority":False,
                   "state":"SHADOW_CONTEXT_READY_NO_FORMAL_AUTHORITY",
                   "active_universe_transport_full_coverage":True,
                   "unexpected_missing_count":0,"raw_finmind_rows_persisted":False,
                   "per_security_rows_persisted":False,"stale_rows_neutralized_as_zero":False,
                   "active_required_count":1088,"finmind_metric_observation_count":1085,
                   "metric_unknown_count":3,"current_market_date_ratio":0.99724265,
                   "latest_source_timestamp":"2026-11-06 14:30:00"}
        self.monitor={**c,"market":m,"formal_escape_authority":False,
                      "monitor_state":"LIVE_CONTEXT_READY","feature_detector_input_authority":False,
                      "active_required_count":1088,"finmind_metric_observation_count":1085}
    def preopen(self, p=None):
        return build(self.ctx,self.stat,self.monitor,"PREOPEN_PREVIOUS_SESSION",
                     "2026-11-09","2026-11-06","2026-11-09T08:40:00+08:00",p)
    def test_preopen_prior_day_not_fake_live(self):
        a=self.preopen()
        self.assertEqual(a["finmind"]["source_market_date"],"2026-11-06")
        self.assertEqual(a["finmind"]["data_role"],"PREVIOUS_COMPLETED_TW_SESSION")
        self.assertEqual(a["observed_breadth"]["advancers"],105)
        self.assertEqual(a["premarket_forecast"]["status"],"NO_VERIFIED_OVERSEAS_PACKET")
    def test_coverage_fail_closed(self):
        self.stat["current_market_date_ratio"]=0.95
        with self.assertRaises(ValueError):self.preopen()
    def test_missingness_fail_closed(self):
        self.stat["metric_unknown_count"]=0
        with self.assertRaises(ValueError):self.preopen()
    def test_authority_cannot_be_promoted(self):
        self.ctx["formal_escape_state_creation"]=True
        with self.assertRaises(ValueError):self.preopen()
    def test_dates_cannot_mismatch(self):
        self.stat["market_date"]="2026-11-05"
        with self.assertRaises(ValueError):self.preopen()
    def test_preopen_packet_with_overseas_inputs(self):
        p={"version":"HENGCE-PREMARKET-V1","target_tw_date":"2026-11-09",
           "reference_prev_tw_date":"2026-11-06","latest_us_session":"2026-11-06",
           "base_us_session":"2026-11-05",
           "direction_forecast":{"grade":5,"expected_taiex_open_gap_log_pct":0.7},
           "risk_forecast":{"grade":"elevated"}}
        self.assertEqual(self.preopen(p)["premarket_forecast"]["grade"],5)
        p["reference_prev_tw_date"]="2026-11-05"
        with self.assertRaises(ValueError):self.preopen(p)
    def test_intraday_source_freshness(self):
        for obj in (self.ctx,self.stat,self.monitor):
            obj["market_date"]="2026-11-09"
            obj["generated_at_taipei"]="2026-11-09T09:10:00+08:00"
        self.stat["latest_source_timestamp"]="2026-11-09 09:08:00"
        args=(self.ctx,self.stat,self.monitor,"INTRADAY_CURRENT_SESSION",
              "2026-11-09","2026-11-09","2026-11-09T09:15:00+08:00")
        self.assertEqual(build(*args)["finmind"]["data_role"],"CURRENT_INTRADAY_OBSERVATION")
        self.stat["latest_source_timestamp"]="2026-11-09 08:40:00"
        with self.assertRaises(ValueError):build(*args)
    def test_inputs_immutable(self):
        old=copy.deepcopy([self.ctx,self.stat,self.monitor])
        self.preopen()
        self.assertEqual([self.ctx,self.stat,self.monitor],old)

if __name__=="__main__":
    unittest.main()
