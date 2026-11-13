"""HENGCE original V2.2D full-TWSE bridge, exact-receipt regression tests."""
import copy
import datetime as dt
import hashlib
import json
import unittest

from scripts.hengce_v22d_fullmarket_receipt_bridge import (
    bridge, BridgeBlocked, CLASSIFIER, REGRESSOR,
)

NOW=dt.datetime.fromisoformat("2026-11-14T07:31:00+08:00")


def signed(d):
    x=copy.deepcopy(d)
    x.pop("receipt_sha256",None)
    x["receipt_sha256"]=hashlib.sha256(json.dumps(
        x,ensure_ascii=False,sort_keys=True,
        separators=(",",":")).encode()).hexdigest()
    return x


def inputs():
    a={"schema":"HENGCE_V22D_PRIVATE_ORIGINAL_CHECKPOINT_REPLAY_V1",
       "status":"RESEARCH_REPLAY_NOT_PIT_CERTIFIED",
       "system":"HENGCE","universe_mode":"ALL_TWSE_10LOT_RESEARCH",
       "decision_date":"2026-11-13","friday_shadow_only":True,
       "qualified_count":2,"feature_coverage":3,"price_gate_count":3,
       "last_assumed_tdcc_snapshot":"2026-10-30",
       "historical_tdcc_first_observed_pit_certified":False,
       "trading_authority":False,"formal_selection_authority":False,
       "buy_signal":False,"sell_signal":False,"broker_execution":False,
       "authorized_lots":0,"capital_authority_twd":0,
       "source_sha256":{"classifier":CLASSIFIER,"regressor":REGRESSOR,
                        "original_2026_canonical":"a"*64},
       "all_qualified":[
           {"rank":1,"ticker":"9933","close":51.6,"score":.74944,
            "ret20":.2126,"ret5":.1621,"turnover20_median":320000000,
            "known_date":"2026-10-30"},
           {"rank":2,"ticker":"1802","close":85.1,"score":.6,
            "ret20":.27,"ret5":.47,"turnover20_median":200000000,
            "known_date":"2026-10-30"}],
       "all_scored_for_exit_audit":[
           {"ticker":"9933","model_gate":True,"score":.74944,
            "ret20":.2126,"ret5":.1621,"turnover20_median":320000000,
            "volatility20":.04,"close":51.6},
           {"ticker":"1802","model_gate":True,"score":.6,
            "ret20":.27,"ret5":.47,"turnover20_median":200000000,
            "volatility20":.06,"close":85.1},
           {"ticker":"3715","model_gate":False,"score":.4554,
            "ret20":.007,"ret5":.43,"turnover20_median":660000000,
            "volatility20":.06,"close":141.5}]
       }
    e={"status":"COMPLETE","target_date":"2026-11-13",
       "mother_sha256":"a"*64,"mother_status":"COMPLETE",
       "three_leg_complete":True,"formal_complete_day":True,
       "downstream_ready":True}
    d={"observed_eod_date":"2026-11-13",
       "two_group_research":{"status":"VERIFIED_TWO_GROUP_RESEARCH",
         "other_definition":"grade 17 total minus grades 1-3 shares",
         "last_tdcc_date":"20261113",
         "first_observed_taipei":"2026-11-14T05:28:55+08:00",
         "market_registry_total":2},
       "two_group_market_registry":[
         {"ticker":"9933","small_holders":1000,"small_holders_delta":-100,
          "small_shares":300000,"other_shares":1200000},
         {"ticker":"1802","small_holders":2000,"small_holders_delta":-10,
          "small_shares":1000000,"other_shares":8000000}
       ]}
    names={"9933":"中鼎","1802":"台玻"}
    previous={"status":"RESEARCH_SCAN_READY","decision_date":"2026-11-12",
              "ranked":[{"ticker":"9933","name":"中鼎"},
                        {"ticker":"3715","name":"定穎投控"}]}
    return signed(a),e,d,names,previous


class BridgeTests(unittest.TestCase):
    def test_verified_99xx_scores_in_one_ranking_and_exit(self):
        a,e,d,n,p=inputs()
        o=bridge(a,e,d,n,p,NOW)
        self.assertEqual(o["qualified_count"],2)
        self.assertEqual(o["all_qualified"][0]["ticker"],"9933")
        self.assertAlmostEqual(o["all_qualified"][0]["retail_holder_week_delta_pct"],
                               -100/1100*100)
        self.assertEqual(o["source_tdcc_model_asof"],"2026-10-30")
        self.assertEqual(o["source_tdcc_research_overlay"],"2026-11-13")
        self.assertFalse(o["broker_order_execution"])
        self.assertEqual([v["ticker"] for v in o["exited"]],["3715"])
        self.assertIn("RET20_BELOW",o["exited"][0]["reason"])
        self.assertIn("SCORE_BELOW_0_50",o["exited"][0]["reason"])

    def test_same_day_rerun_does_not_fabricate_exit(self):
        a,e,d,n,p=inputs()
        p["decision_date"]="2026-11-13"
        self.assertEqual(bridge(a,e,d,n,p,NOW)["exited"],[])

    def test_unscored_previous_stock_is_unknown(self):
        a,e,d,n,p=inputs()
        p["ranked"].append({"ticker":"2254","name":"巨鎧"})
        o=bridge(a,e,d,n,p,NOW)
        self.assertEqual(o["exited"][-1]["reason"],"INPUT_MISSING_CANNOT_VERIFY_EXIT")

    def test_tampering_score_or_rank_rejected(self):
        a,e,d,n,p=inputs()
        a["all_qualified"][0]["score"]=.999
        with self.assertRaisesRegex(BridgeBlocked,"MODEL_RECEIPT_SHA_MISMATCH"):
            bridge(a,e,d,n,p,NOW)
        a,e,d,n,p=inputs()
        a["all_qualified"][0]["ticker"]="9103"
        with self.assertRaisesRegex(BridgeBlocked,"DUPLICATE_OR_INVALID_RANKED_STOCK"):
            bridge(signed(a),e,d,n,p,NOW)

    def test_postdecision_tdcc_timestamp_not_model_feature(self):
        a,e,d,n,p=inputs()
        with self.assertRaisesRegex(BridgeBlocked,"TDCC_NOT_YET_OBSERVED"):
            bridge(a,e,d,n,p,dt.datetime.fromisoformat(
                "2026-11-14T05:00:00+08:00"))
        a,e,d,n,p=inputs()
        d["two_group_research"]["last_tdcc_date"]="20261120"
        with self.assertRaisesRegex(BridgeBlocked,"POST_DECISION_TDCC_NOT_PERMITTED"):
            bridge(a,e,d,n,p,NOW)

    def test_wrong_mother_or_model_sha_blocks(self):
        a,e,d,n,p=inputs()
        e["mother_sha256"]="b"*64
        with self.assertRaisesRegex(BridgeBlocked,"CANONICAL_MOTHER_HASH_MISMATCH"):
            bridge(a,e,d,n,p,NOW)
        a,e,d,n,p=inputs()
        a["source_sha256"]["classifier"]="c"*64
        with self.assertRaisesRegex(BridgeBlocked,"ORIGINAL_CHECKPOINT_NOT_VERIFIED"):
            bridge(signed(a),e,d,n,p,NOW)


if __name__=="__main__":
    unittest.main()
