#!/usr/bin/env python3
"""HENGCE governed Nasdaq SOX + Cboe VIX premarket EOD producer.

Read original published vendor data. Fail closed on unavailable/misaligned/
stale US sessions. Not related to retired Q017, stock selection, or trading.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

TAIPEI=ZoneInfo("Asia/Taipei")
NEW_YORK=ZoneInfo("America/New_York")
SOX_URL="https://indexes.nasdaq.com/Index/ExportHistory/SOX"
VIX_URL="https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
MODEL="HENGCE_SOX_VIX_TAIEX_OPEN_GAP_OLS_TRAIN_20181109_20241231_V1"
COEFFICIENTS=(0.041642424724208524,0.15095610356018835,-0.0036574564504370257)
CUTS=(-0.19055541322518293,0.0000503213262588,0.12993431163319522,0.32424484685128574)
LABELS=("強烈偏空","偏空","中性","偏多","強烈偏多")

def require(ok,why):
    if not ok:
        raise ValueError(why)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(obj):
    return sha(json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode("utf-8"))

def num(x):
    if isinstance(x,bool):
        return None
    try:
        z=float(str(x).replace(",","").strip())
        return z if math.isfinite(z) and z>0 else None
    except (TypeError,ValueError):
        return None

def day(x):
    if isinstance(x,dt.datetime): return x.date()
    if isinstance(x,dt.date): return x
    t=str(x).strip()
    for fmt in ("%m/%d/%Y","%Y-%m-%d","%m/%d/%Y %H:%M:%S","%m/%d/%y"):
        try: return dt.datetime.strptime(t,fmt).date()
        except ValueError: pass
    return None

def nasdaq_rows(raw):
    from openpyxl import load_workbook
    require(raw.startswith(b"PK"),"NASDAQ_NOT_XLSX")
    w=load_workbook(io.BytesIO(raw),data_only=True,read_only=True)
    out={}
    try:
        for sheet in w.worksheets:
            for row in sheet.iter_rows(values_only=True):
                if not row or len(row)<2: continue
                d=day(row[0]); p=num(row[1])
                if d and p and dt.date(2010,1,1)<=d<=dt.date(2100,1,1):
                    if d in out and abs(out[d]-p)>1e-8: raise ValueError("NASDAQ_DUPLICATE_CONFLICT")
                    out[d]=p
            if len(out)>=2: break
    finally:
        w.close()
    require(len(out)>=2,"NASDAQ_INSUFFICIENT_INDEX_ROWS")
    return out

def cboe_rows(raw):
    t=raw.decode("utf-8-sig")
    r=csv.DictReader(io.StringIO(t))
    require(r.fieldnames and "DATE" in r.fieldnames and "CLOSE" in r.fieldnames,"CBOE_CSV_SCHEMA_INVALID")
    out={}
    for row in r:
        d=day(row.get("DATE"));p=num(row.get("CLOSE"))
        if d and p:
            if d in out and abs(out[d]-p)>1e-8: raise ValueError("CBOE_DUPLICATE_CONFLICT")
            out[d]=p
    require(len(out)>=2,"CBOE_VIX_HISTORY_EMPTY")
    return out

def fetch(url,timeout=28):
    req=urllib.request.Request(url,headers={
        "Accept":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv,*/*",
        "User-Agent":"Mozilla/5.0 HENGCE-MACRO-EOD-V1"
    })
    last=None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req,timeout=timeout) as res:
                final=res.geturl()
                require(final.startswith("https://") and
                        (final.split("/")[2] in ("indexes.nasdaq.com","cdn.cboe.com","cdn-api.cboe.com")),"UNTRUSTED_VENDOR_REDIRECT_HOST:"+final.split("/")[2][:120])
                data=res.read(5_000_001)
                require(len(data)>100 and len(data)<=5_000_000,"VENDOR_RESPONSE_SIZE_INVALID")
                return data
        except (OSError,ValueError,urllib.error.HTTPError) as e:
            last=e
            if attempt<2:time.sleep(1+attempt)
    raise RuntimeError("VENDOR_FETCH_FAILURE:"+type(last).__name__+":"+str(last)[:280]) from last

def build(asof,tw_previous,sox,vix,sox_raw,vix_raw,url):
    """Build only with known pre-open Taipei time and common completed US EOD."""
    now=asof.astimezone(TAIPEI)
    target=now.date()
    require(target.weekday()<5 and now.hour<9,"NOT_TAIWAN_PREOPEN_WEEKDAY")
    prev=dt.date.fromisoformat(tw_previous)
    require(prev<target and (target-prev).days<=7,"STALE_PREVIOUS_TW_SESSION")
    # Each official publisher can expose newer rows at different times.
    # Select the latest *common* completed weekday, never mixing sessions.
    # A common session older than the expected US EOD remains BLOCKED.
    us_s=max((d for d in sox if d<target and d.weekday()<5),default=None)
    us_v=max((d for d in vix if d<target and d.weekday()<5),default=None)
    common=sorted(d for d in set(sox)&set(vix)
                  if d<target and d.weekday()<5)
    latest=common[-1] if common else None
    details=(" sox="+str(us_s)+" vix="+str(us_v)+
             " common="+str(latest))
    require(latest is not None,"LATEST_US_SOURCE_SESSION_MISMATCH"+details)
    # This strict gate deliberately rejects a vendor that has not published
    # yesterday's US EOD. No stale prior-day fallback and no synthetic row.
    expected=target-dt.timedelta(days=3 if target.weekday()==0 else 1)
    if us_s!=us_v and latest<expected:
        raise ValueError("LATEST_US_SOURCE_SESSION_MISMATCH"+
                         details+" expected="+str(expected))
    require(latest>=expected,"LATEST_EXPECTED_US_EOD_NOT_VERIFIED"+
            details+" expected="+str(expected))
    require((target-latest).days<=4,"STALE_OR_NONTRADING_US_SESSION")
    require(len(common)>=2,"NO_TWO_ALIGNED_US_EOD_SESSIONS")
    prior=common[-2]
    require((latest-prior).days<=5,"PREVIOUS_US_SESSION_TOO_OLD")
    sa,sb=sox[latest],sox[prior];va,vb=vix[latest],vix[prior]
    logsox=100*math.log(sa/sb); logvix=100*math.log(va/vb)
    gap=COEFFICIENTS[0]+COEFFICIENTS[1]*logsox+COEFFICIENTS[2]*logvix
    grade=1+sum(gap>=x for x in CUTS)
    source_info={
      "sox":{"publisher":"Nasdaq","symbol":"SOX","url":url,
             "raw_sha256":sha(sox_raw),"raw_bytes":len(sox_raw),
             "latest_us_session":latest.isoformat(),"prior_us_session":prior.isoformat(),
             "latest_close":sa,"prior_close":sb},
      "vix":{"publisher":"Cboe","symbol":"VIX","url":VIX_URL,
             "raw_sha256":sha(vix_raw),"raw_bytes":len(vix_raw),
             "latest_us_session":latest.isoformat(),"prior_us_session":prior.isoformat(),
             "latest_close":va,"prior_close":vb}
    }
    packet={
      "version":"HENGCE-PREMARKET-V1","model":MODEL,
      "status":"PASS_VERIFIED_VENDOR_EOD",
      "target_tw_date":target.isoformat(),
      "reference_prev_tw_date":prev.isoformat(),
      "latest_us_session":latest.isoformat(),"base_us_session":prior.isoformat(),
      "generated_at_taipei":now.isoformat(),
      "sources":source_info,
      "direction_forecast":{
         "grade":grade,"label":LABELS[grade-1],
         "expected_taiex_open_gap_log_pct":round(gap,8),
         "sox_log_return_pct":round(logsox,8),
         "vix_log_return_pct":round(logvix,8),
         "sox_simple_return_pct":round(100*(sa/sb-1),8),
         "vix_simple_return_pct":round(100*(va/vb-1),8)},
      "risk_forecast":{"vix_level":va,
        "vix_risk_band":"HIGH" if va>=30 else "ELEVATED" if va>=20 else "NORMAL"},
      "provenance_policy":{
        "vendor_eod_not_intraday":True,
        "asof_preopen_only":True,
        "source_raw_hashes_recorded":True,
        "vendor_rows_same_completed_session":True,
        "third_party_history_not_a_signed_data_feed":True,
        "market_interpretation_not_trading_authority":True,
        "source_influence":"EXPLICIT_USER_AUTHORIZED_GOVERNED_SHADOW_ONLY"},
      "authority":"OVERSEAS_PREMARKET_RESEARCH_SHADOW_ONLY_NOT_CANONICAL_STOCK_FLOW",
      "trading_authority":False,
      "capital_authority":False
    }
    packet["packet_sha256"]=canonical(packet)
    return packet

def vendor_url(target):
    start=(target-dt.timedelta(days=25)).isoformat()+"T00:00:00.000"
    end=(target+dt.timedelta(days=1)).isoformat()+"T00:00:00.000"
    return SOX_URL+"?startDate="+start+"&endDate="+end+"&timeOfDay=EOD"

def last_completed_us_weekday(asof):
    """Latest possible completed US stock close in NY wall clock.

    This is a weekday clock gate for *source observations*, not a certified
    US exchange holiday calendar and NOT an official-publisher freshness
    guarantee. The two vendors' actual sessions and publication lags always
    remain separate.
    """
    local=asof.astimezone(NEW_YORK)
    close=dt.datetime.combine(local.date(),dt.time(16,0),NEW_YORK)
    candidate=local.date() if local>=close else local.date()-dt.timedelta(days=1)
    while candidate.weekday()>=5:
        candidate-=dt.timedelta(days=1)
    return candidate


def source_observation(asof,tw_previous,sox,vix,sox_raw,vix_raw,url,*,
                       late_source_only=False,continuous_source_only=False):
    """Independent official index observations; NEVER a composite model receipt.

    The US EOD session date is in America/New_York market time, not the
    Taipei capture date. Keep each publisher's actual latest session visible.
    """
    now=asof.astimezone(TAIPEI)
    target=now.date()
    require(not(late_source_only and continuous_source_only),"SOURCE_OBSERVATION_MODE_CONFLICT")
    if continuous_source_only:
        # Pure source observations have no Taipei weekday/hour gate. The
        # underlying US session MUST have completed by US/Eastern 16:00.
        previous_date=None
        expected=last_completed_us_weekday(asof)
    else:
        if late_source_only:
            require(target.weekday()<5 and now.hour>=9,"NOT_POSTOPEN_TAIWAN_WEEKDAY")
        else:
            require(target.weekday()<5 and now.hour<9,"NOT_TAIWAN_PREOPEN_WEEKDAY")
        prev=dt.date.fromisoformat(tw_previous)
        if late_source_only:
            previous_date=(prev.isoformat() if prev<target and (target-prev).days<=7 else None)
        else:
            require(prev<target and (target-prev).days<=7,"STALE_PREVIOUS_TW_SESSION")
            previous_date=prev.isoformat()
        expected=target-dt.timedelta(days=3 if target.weekday()==0 else 1)

    def leg(symbol,publisher,url,rows,raw):
        valid=sorted(d for d in rows if d.weekday()<5 and
                     d<=(expected if continuous_source_only else target-dt.timedelta(days=1)))
        latest=valid[-1] if valid else None
        prior=valid[-2] if len(valid)>=2 else None
        return {"symbol":symbol,"publisher":publisher,"url":url,
                "raw_sha256":sha(raw),"raw_bytes":len(raw),
                "latest_us_session":latest.isoformat() if latest else None,
                "prior_us_session":prior.isoformat() if prior else None,
                "latest_close":rows[latest] if latest else None,
                "prior_close":rows[prior] if prior else None,
                "source_status":"EXPECTED_US_EOD_PRESENT" if latest==expected
                                 else "EXPECTED_US_EOD_NOT_YET_PUBLISHED"}

    a=leg("SOX","Nasdaq",url,sox,sox_raw)
    b=leg("VIX","Cboe",VIX_URL,vix,vix_raw)
    common=sorted(d for d in set(sox)&set(vix)
                  if d<target and d.weekday()<5)
    aligned=(a["source_status"]=="EXPECTED_US_EOD_PRESENT" and
             b["source_status"]=="EXPECTED_US_EOD_PRESENT" and
             len(common)>=2 and common[-1]==expected)
    result={"schema":"HENGCE_OVERSEAS_SOURCE_OBSERVATION_V1",
            "status":"OFFICIAL_SOURCES_OBSERVED_NO_MODEL_AUTHORITY",
            "target_tw_date":target.isoformat(),
            "reference_prev_tw_date":previous_date,
            "observed_at_taipei":now.isoformat(),
            "observation_window":("ANYTIME_SOURCE_ONLY" if continuous_source_only
                                  else "POST_OPEN_SOURCE_ONLY" if late_source_only
                                  else "PREOPEN_SOURCE_ONLY"),
            "expected_us_session_basis":("US_EASTERN_1600_WEEKDAY_CLOCK_ONLY"
                                        if continuous_source_only else
                                        "TAIPEI_PREMARKET_PREVIOUS_WEEKDAY"),
            "expected_us_session":expected.isoformat(),
            "sources":{"sox":a,"vix":b},
            "composite_readiness":("ANYTIME_SOURCE_ONLY_NO_PREOPEN_FORECAST"
                    if continuous_source_only else
                    "POST_OPEN_SOURCE_ONLY_NO_PREOPEN_FORECAST" if late_source_only else
                    "BOTH_SOURCES_READY_FOR_SEPARATE_FORMAL_VALIDATION"
                    if aligned else "BLOCKED_PENDING_ALIGNED_US_EOD"),
            "composite_forecast_emitted":False,
            "trading_authority":False,"capital_authority":False}
    result["source_observation_sha256"]=canonical(result)
    return result


def produce(asof,previous,observations_out=None):
    url=vendor_url(asof.astimezone(TAIPEI).date())
    # Reuse ONLY the two existing official publisher downloads. Publish the
    # individual observation separately even when their EOD dates differ;
    # the existing composite model must continue failing closed.
    for attempt in range(3):
        sr=fetch(url)
        vr=fetch(VIX_URL)
        current=dt.datetime.now(TAIPEI)
        s=nasdaq_rows(sr);v=cboe_rows(vr)
        if observations_out is not None:
            observation=source_observation(current,previous,s,v,sr,vr,url)
            observations_out.parent.mkdir(parents=True,exist_ok=True)
            observations_out.write_text(
                json.dumps(observation,indent=2,sort_keys=True,ensure_ascii=False)+"\n",
                encoding="utf-8")
        try:
            return build(current,previous,s,v,sr,vr,url)
        except ValueError as error:
            if not str(error).startswith(("LATEST_US_SOURCE_SESSION_MISMATCH",
                                          "LATEST_EXPECTED_US_EOD_NOT_VERIFIED")) or attempt==2:
                raise
            print(json.dumps({"status":"RETRY_SOURCE_SESSION","attempt":attempt+1,
                              "reason":str(error)},ensure_ascii=False),file=sys.stderr)
            time.sleep(10*(attempt+1))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",required=True,choices=("run","probe","late-source","observe"))
    p.add_argument("--context",type=Path,default=Path("escape_live/finmind_twse_common_context.json"))
    p.add_argument("--out",type=Path)
    p.add_argument("--observations-out",type=Path)
    args=p.parse_args()
    if args.mode=="probe":
        url=vendor_url(dt.datetime.now(TAIPEI).date())
        sr=fetch(url);vr=fetch(VIX_URL)
        s=nasdaq_rows(sr);v=cboe_rows(vr)
        z={"status":"SOURCE_PROBE_ONLY","sox_dates":[str(x) for x in sorted(s)[-3:]],
           "sox_latest_values":[s[x] for x in sorted(s)[-3:]],
           "vix_dates":[str(x) for x in sorted(v)[-3:]],
           "vix_latest_values":[v[x] for x in sorted(v)[-3:]],
           "sha256":{"sox":sha(sr),"vix":sha(vr)}}
        print(json.dumps(z,ensure_ascii=False))
        return 0
    if args.mode=="observe":
        require(args.observations_out is not None,"SOURCE_OBSERVATION_OUTPUT_REQUIRED")
        now=dt.datetime.now(TAIPEI)
        url=vendor_url(now.date())
        sr=fetch(url);vr=fetch(VIX_URL)
        observation=source_observation(now,None,nasdaq_rows(sr),cboe_rows(vr),
                       sr,vr,url,continuous_source_only=True)
        args.observations_out.parent.mkdir(parents=True,exist_ok=True)
        args.observations_out.write_text(json.dumps(observation,indent=2,
                       sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
        print(json.dumps({"status":observation["status"],
          "window":observation["observation_window"],
          "expected_us_session":observation["expected_us_session"],
          "composite_forecast_emitted":False,
          "sox_session":observation["sources"]["sox"]["latest_us_session"],
          "vix_session":observation["sources"]["vix"]["latest_us_session"]},ensure_ascii=False))
        return 0
    if args.mode=="late-source":
        require(args.observations_out is not None,"SOURCE_OBSERVATION_OUTPUT_REQUIRED")
        now=dt.datetime.now(TAIPEI)
        require(now.weekday()<5 and now.hour>=9,"NOT_POSTOPEN_TAIWAN_WEEKDAY")
        url=vendor_url(now.date())
        sr=fetch(url);vr=fetch(VIX_URL)
        context=json.loads(args.context.read_text(encoding="utf-8"))
        observation=source_observation(now,context["market_date"],nasdaq_rows(sr),
                 cboe_rows(vr),sr,vr,url,late_source_only=True)
        args.observations_out.parent.mkdir(parents=True,exist_ok=True)
        args.observations_out.write_text(json.dumps(observation,indent=2,
             sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
        print(json.dumps({"status":observation["status"],"window":observation["observation_window"],
                          "composite_forecast_emitted":False,
                          "sox_session":observation["sources"]["sox"]["latest_us_session"],
                          "vix_session":observation["sources"]["vix"]["latest_us_session"]},ensure_ascii=False))
        return 0
    require(args.out is not None,"OUTPUT_PATH_REQUIRED")
    context=json.loads(args.context.read_text(encoding="utf-8"))
    asof=dt.datetime.now(TAIPEI)
    packet=produce(asof,context["market_date"],args.observations_out)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(packet,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":packet["status"],"target":packet["target_tw_date"],
      "us_date":packet["latest_us_session"],"label":packet["direction_forecast"]["label"],
      "gap":packet["direction_forecast"]["expected_taiex_open_gap_log_pct"],
      "packet_sha256":packet["packet_sha256"]},ensure_ascii=False))
    return 0

if __name__=="__main__":
    try:sys.exit(main())
    except Exception as exc:
        print(json.dumps({"status":"BLOCKED","error":type(exc).__name__,"reason":str(exc)},ensure_ascii=False),file=sys.stderr)
        sys.exit(2)
