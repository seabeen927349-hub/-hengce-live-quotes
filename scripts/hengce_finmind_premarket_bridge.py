#!/usr/bin/env python3
"""HENGCE governed FinMind snapshot -> premarket and intraday shadow.
Consumes EXISTING FinMind aggregate files only; no new vendor request and
no authority to alter EOD, stock selection, Escape, or portfolio decisions.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo
from hengce_two_time_scale_environment_display import build_display
from hengce_overseas_sox_vix_premarket_v1 import MODEL, COEFFICIENTS, CUTS, canonical, SOX_URL, VIX_URL

TZ = ZoneInfo("Asia/Taipei")
METRIC_SHA = "1d93c171b0b06d49eef19e0bf63e3b086fc366052d6bbc45516928c672f47281"
SCOPE = "ALL_TWSE_LISTED_COMMON_STOCKS"

def stamp(value):
    d = dt.datetime.fromisoformat(str(value).replace("Z","+00:00"))
    return d.replace(tzinfo=TZ) if d.tzinfo is None else d.astimezone(TZ)

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

def ensure(condition,message):
    if not condition:
        raise ValueError(message)

def build(context,status,monitor,phase,target,previous,asof,premarket=None):
    """Fail closed on clock, source, coverage or authority mismatch."""
    ensure(phase in ("PREOPEN_PREVIOUS_SESSION","INTRADAY_CURRENT_SESSION"),"bad phase")
    target_day=dt.date.fromisoformat(target)
    source_day=dt.date.fromisoformat(previous)
    now=stamp(asof)
    ensure(now.date()==target_day and target_day.weekday()<5,"invalid target/asof")
    preopen=phase=="PREOPEN_PREVIOUS_SESSION"
    if preopen:
        ensure(source_day<target_day and now.hour<9,"preopen needs prior session and before 09:00")
    else:
        ensure(source_day==target_day and (9,0)<=(now.hour,now.minute)<=(13,45),"not a live TWSE session")
    for label,obj in (("context",context),("status",status),("monitor",monitor)):
        ensure(obj.get("market_date",previous)==previous,f"{label}: date mismatch")
        ensure(obj.get("metric_contract_sha256")==METRIC_SHA,f"{label}: metric hash mismatch")
        ensure(obj.get("monitoring_universe")==SCOPE,f"{label}: universe mismatch")
        ensure((obj.get("formal_escape_state_creation") if label=="context" else obj.get("formal_escape_authority")) is False,f"{label}: Escape authority forbidden")
        ensure(obj.get("trading_authority") is False,f"{label}: trading authority forbidden")
        ensure(stamp(obj["generated_at_taipei"])<=now,f"{label}: future timestamp")
    ensure(status.get("state")=="SHADOW_CONTEXT_READY_NO_FORMAL_AUTHORITY","FinMind not ready")
    ensure(monitor.get("monitor_state")=="LIVE_CONTEXT_READY","intraday monitor not ready")
    ensure(status.get("active_universe_transport_full_coverage") is True,"transport coverage failed")
    ensure(status.get("unexpected_missing_count")==0,"unexpected TWSE missing")
    ensure(status.get("raw_finmind_rows_persisted") is False,"raw records forbidden")
    ensure(status.get("per_security_rows_persisted") is False,"per-security records forbidden")
    ensure(status.get("stale_rows_neutralized_as_zero") is False,"missing-as-zero forbidden")
    ensure(monitor.get("feature_detector_input_authority") is False,"formal feature promotion forbidden")
    n=status.get("active_required_count")
    observed=status.get("finmind_metric_observation_count")
    unknown=status.get("metric_unknown_count")
    ensure(all(type(x)==int for x in (n,observed,unknown)) and n>=900 and observed>0
           and observed+unknown==n,"count integrity failed")
    coverage=status.get("current_market_date_ratio")
    ensure(isinstance(coverage,(int,float)) and math.isfinite(coverage)
           and 0.98<=coverage<=1 and abs(coverage-context.get("current_market_date_ratio",-1))<1e-8,
           "current-session coverage failed")
    ensure(monitor.get("active_required_count")==n and
           monitor.get("finmind_metric_observation_count")==observed,"monitor count mismatch")
    m=context.get("market")
    ensure(isinstance(m,dict) and m==monitor.get("market"),"market aggregate mismatch")
    adv,dec,flat=(m.get(k) for k in ("advance_count","decline_count","flat_count"))
    ensure(all(type(x)==int and x>=0 for x in (adv,dec,flat)) and
           adv+dec+flat==observed and m.get("net_breadth")==adv-dec and
           m.get("return_observed_count")==observed and m.get("constituent_count")==n,
           "market breadth count mismatch")
    latest=stamp(status["latest_source_timestamp"])
    ensure(latest.date()==source_day and latest<=now,"FinMind source date/future mismatch")
    if not preopen:
        ensure((now-latest).total_seconds()<=20*60,"stale intraday FinMind snapshot")
    prediction={"status":"NO_VERIFIED_OVERSEAS_PACKET","grade":None,"expected_gap_log_pct":None}
    if premarket is not None:
        ensure(preopen and premarket.get("version")=="HENGCE-PREMARKET-V1","bad model packet")
        ensure(premarket.get("target_tw_date")==target and
               premarket.get("reference_prev_tw_date")==previous,"model/TW session mismatch")
        latest_us=dt.date.fromisoformat(premarket["latest_us_session"])
        base_us=dt.date.fromisoformat(premarket["base_us_session"])
        ensure(base_us<latest_us<target_day,"invalid US session chronology")
        d=premarket.get("direction_forecast") or {}
        grade,gap=d.get("grade"),d.get("expected_taiex_open_gap_log_pct")
        ensure(type(grade)==int and 1<=grade<=5 and
               isinstance(gap,(int,float)) and math.isfinite(gap),"bad forecast score")
        prediction={"status":"PIT_SCHEMA_VERIFIED_UPSTREAM","grade":grade,
          "expected_gap_log_pct":gap,"vix_risk":premarket.get("risk_forecast"),
          "overseas_source_sessions":{"latest":latest_us.isoformat(),"base":base_us.isoformat()},
          "source_sha256":digest(premarket),
          "source_notice":"SOX/VIX inputs are independent from FinMind; source price freshness not established here."}
        if premarket.get("status")=="PASS_VERIFIED_VENDOR_EOD":
            ensure(premarket.get("model")==MODEL,"overseas model contract mismatch")
            receipt=premarket.get("packet_sha256")
            ensure(type(receipt)==str and len(receipt)==64 and
                   receipt==canonical({k:val for k,val in premarket.items()
                                      if k!="packet_sha256"}),"overseas receipt hash mismatch")
            issued=stamp(premarket["generated_at_taipei"])
            ensure(issued.date()==now.date() and issued<=now,
                   "overseas packet generated outside current preopen PIT")
            ensure((target_day-latest_us).days<=4 and
                   (latest_us-base_us).days<=5,"overseas history stale")
            sources=premarket.get("sources") or {}
            sox=sources.get("sox") or {}
            vix=sources.get("vix") or {}
            ensure(sox.get("publisher")=="Nasdaq" and
                   str(sox.get("url","")).startswith(SOX_URL+"?") and
                   vix.get("publisher")=="Cboe" and
                   vix.get("url")==VIX_URL,"vendor URL contract mismatch")
            for leg in (sox,vix):
                ensure(leg.get("latest_us_session")==latest_us.isoformat()
                       and leg.get("prior_us_session")==base_us.isoformat(),
                       "vendor session mismatch")
                ensure(type(leg.get("raw_sha256"))==str
                       and len(leg["raw_sha256"])==64
                       and leg["raw_sha256"]!="0"*64
                       and isinstance(leg.get("raw_bytes"),int)
                       and leg["raw_bytes"]>100,"vendor raw digest invalid")
                ensure(all(isinstance(leg.get(k),(int,float)) and
                           not isinstance(leg[k],bool) and
                           math.isfinite(leg[k]) and leg[k]>0
                           for k in ("latest_close","prior_close")),
                           "vendor index values invalid")
            logsox=100*math.log(sox["latest_close"]/sox["prior_close"])
            logvix=100*math.log(vix["latest_close"]/vix["prior_close"])
            recalculated=COEFFICIENTS[0]+COEFFICIENTS[1]*logsox+COEFFICIENTS[2]*logvix
            regrade=1+sum(recalculated>=c for c in CUTS)
            ensure(abs(recalculated-gap)<=0.000001 and
                   regrade==grade and
                   d.get("label")==("強烈偏空","偏空","中性","偏多","強烈偏多")[grade-1] and
                   abs(d.get("sox_log_return_pct",1e99)-logsox)<=0.000001 and
                   abs(d.get("vix_log_return_pct",1e99)-logvix)<=0.000001,
                   "overseas model coefficients or grade not reproducible")
            ensure((premarket.get("provenance_policy") or {}).get("source_raw_hashes_recorded")
                   is True and premarket.get("trading_authority") is False,
                   "overseas authority invalid")
            prediction={"status":"VERIFIED_GOVERNED_OVERSEAS_SOX_VIX",
              "vendor_price_integrity":True,
              "source_receipt_sha256":receipt,
              "grade":grade,"expected_gap_log_pct":gap,
              "sox":{"latest_close":sox["latest_close"],
                     "change_pct":d.get("sox_simple_return_pct")},
              "vix":{"latest_close":vix["latest_close"],
                     "change_pct":d.get("vix_simple_return_pct"),
                     "risk_band":(premarket.get("risk_forecast") or {}).get("vix_risk_band")},
              "vix_risk":premarket.get("risk_forecast"),
              "overseas_source_sessions":{"latest":latest_us.isoformat(),"base":base_us.isoformat()},
              "source_url":{"sox":sox["url"],"vix":vix["url"]},
              "source_notice":"Official-vendor EOD captured by governed shadow; not an independently signed data feed or trading signal."}
    return {
      "schema":"HENGCE_FINMIND_PREMARKET_BRIDGE_V1",
      "status":"PASS_READ_ONLY_CONTEXT",
      "target_tw_date":target,"asof_taipei":now.isoformat(),
      "finmind":{
        "existing_transport":"taiwan_stock_tick_snapshot",
        "data_role":"PREVIOUS_COMPLETED_TW_SESSION" if preopen else "CURRENT_INTRADAY_OBSERVATION",
        "source_market_date":previous,"latest_source_taipei":latest.isoformat(),
        "generated_at_taipei":status["generated_at_taipei"],
        "required_count":n,"observed_count":observed,"unknown_count":unknown,
        "current_session_coverage":coverage,"metric_contract_sha256":METRIC_SHA,
        "context_digest":digest(context),"status_digest":digest(status),"monitor_digest":digest(monitor)
      },
      "observed_breadth":{
        "advancers":adv,"decliners":dec,"unchanged":flat,
        "advancer_share_directional":round(adv/(adv+dec),8) if adv+dec else None,
        "equal_weight_change_rate_vendor_units":m.get("equal_weight_change_rate"),
        "vendor_turnover_units":m.get("total_amount"),
        "interpretation":"Historical session observations, NOT future fund flows or formal Escape metrics."
      },
      "premarket_forecast":prediction,
      "two_time_scale_display":build_display(prediction,target,previous),
      "macro_regime":"UNVERIFIED_NO_FRESH_CANONICAL_PACKET",
      "escape_formal_state":"UNVERIFIED_NO_FRESH_CANONICAL_PACKET",
      "governance":{"new_finmind_fetch":False,"new_market_universe":False,
        "canonical_eod_replaced":False,"raw_vendor_rows_persisted":False,
        "formal_buy_sell_created":False,"formal_state_mutated":False,
        "trading_authority":"NONE","equity_flow_is_net_remittance":False}
    }

def main():
    p=argparse.ArgumentParser()
    for field in ("context","status","monitor","out"):
        p.add_argument("--"+field,required=True,type=Path)
    for field in ("phase","target-tw-date","expected-finmind-session","asof-taipei"):
        p.add_argument("--"+field,required=True)
    p.add_argument("--premarket",type=Path)
    a=p.parse_args()
    read=lambda x:json.loads(x.read_text(encoding="utf-8"))
    obj=build(read(a.context),read(a.status),read(a.monitor),
      a.phase,a.target_tw_date,a.expected_finmind_session,a.asof_taipei,
      read(a.premarket) if a.premarket else None)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":obj["status"],"finmind_date":obj["finmind"]["source_market_date"],
      "premarket_status":obj["premarket_forecast"]["status"]},ensure_ascii=False))

if __name__=="__main__":
    main()
