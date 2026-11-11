#!/usr/bin/env python3
"""V2.2-D historical source reader. Never turn historical TDCC nowcast into a live signal.

V2.2-D daily is DIFFERENT from weekly V2.2: price gates + as-of weekly TDCC
nowcast >=.50; rank by 20d median TURNOVER, not by falling-holder probability.
Real daily rollout needs newly frozen source snapshots and a verified model
artifact; there is no trained model / current PIT receipt in this repository.
"""
import json
import math
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo("Asia/Taipei")
FROZEN="research/retail_top5/v22d_historical_20261105.json"
LIVE="research/retail_top5/v22d_daily_latest.json"
PREFERENCE="hengce/HENGCE_SELECTION_MODEL_CHOICE_LATEST.json"
PKG_HASH="245ce7f046a37dd3b4d5eb69221c235f35ce9c69a9f350b37a4cb4f839b4417f"
INPUT_HASH="37a96a72ecb492d7d444d87dd3c6d2cfef5b6a1f994d7ab5f31554fc3e854c8d"
PRICE_MOTHER="b3275f8d58779fbec864a05066414d27e80cef8a68a76a08051f93808f1f8c93"
TDCC_MOTHER="71083d73a791b6bf25770139c65e8d29012a44e31c39f66479806bf5a562bc88"


def _read(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, UnicodeError):
        return None


def _finite(v):
    return type(v) in (int,float) and math.isfinite(v)


def selected_v22d(root):
    c=_read(Path(root)/PREFERENCE)
    if not isinstance(c,dict):
        return False
    if any(c.get(k) is not False for k in
           ("formal_selection_authority","buy_sell_signal_authority","broker_execution")):
        return False
    return (
        c.get("schema")=="HENGCE_SELECTION_MODEL_CHOICE_V1"
        and c.get("model_package")=="HENGCE_SELECTION_MODEL_V2_2_D_DAILY_TOP5"
        and c.get("model_id")=="v22d_daily_nowcast_liquidity_top5_v1"
        and c.get("choice_status")=="PREFERRED_DAILY_RESEARCH_PENDING_PROSPECTIVE"
        and c.get("mode")=="RESEARCH_PREFERENCE_ONLY"
        and type(c.get("capital_authority_twd")) is int
        and c.get("capital_authority_twd")==0
        and type(c.get("authorized_lots")) is int
        and c.get("authorized_lots")==0
        and c.get("no_new_data_vessels") is True
        and c.get("source_package_sha256")==PKG_HASH
        and c.get("source_forecast_data_sha256")==INPUT_HASH
    )


def validate_historical(d, now):
    if not isinstance(d,dict):
        return False
    if not (
        d.get("schema")=="HENGCE_V22D_HISTORICAL_DAILY_TOP5_SOURCE_EXTRACT_V1"
        and d.get("system")=="HENGCE"
        and d.get("model_id")=="v22d_daily_nowcast_liquidity_top5_v1"
        and d.get("archive_date")=="2026-11-05"
        and d.get("decision_date")=="2026-11-05"
        and d.get("source_package_sha256")==PKG_HASH
        and d.get("source_forecast_data_sha256")==INPUT_HASH
        and d.get("source_original_price_mother_sha256")==PRICE_MOTHER
        and d.get("source_original_tdcc_mother_sha256")==TDCC_MOTHER
        and d.get("historical_research_only") is True
        and d.get("point_in_time_publication_timestamps_audited") is False
        and d.get("model_calibration_certified") is False
        and d.get("not_current_recommendations") is True
        and d.get("was_actual_2026_11_11_selection") is False
        and d.get("observations_for_decision_date")==737
        and d.get("qualified_count")==7
        and d.get("score_threshold")==.50
        and d.get("source_information_lag_min_calendar_days")==14
        and d.get("ranking")=="MEDIAN_20D_TURNOVER_DESC_TICKER_ASC"
        and d.get("formal_selection_authority") is False
        and d.get("buy_signal") is False
        and d.get("sell_signal") is False
        and d.get("broker_execution") is False
        and type(d.get("authorized_lots")) is int
        and d.get("authorized_lots")==0
        and type(d.get("capital_authority_twd")) is int
        and d.get("capital_authority_twd")==0
        and date.fromisoformat(d["decision_date"]) <= now.date()
    ):
        return False
    allq=d.get("all_qualified")
    top=d.get("top5")
    if not isinstance(allq,list) or len(allq)!=7 or not isinstance(top,list) or top!=allq[:5]:
        return False
    prev=None
    seen=set()
    for ix,row in enumerate(allq,1):
        if not isinstance(row,dict):
            return False
        code=row.get("ticker")
        if (not isinstance(code,str) or not code.isdigit() or len(code)!=4
            or code.startswith("0") or code in seen or row.get("rank")!=ix
            or row.get("research_only") is not True or row.get("authorized_lots")!=0
            or row.get("last_assumed_available_tdcc_date")!="2026-10-22"):
            return False
        seen.add(code)
        if any(not _finite(row.get(key)) for key in (
                "daily_decline_score", "return_20d", "return_5d",
                "median_20d_turnover_twd", "last_known_le10_holder_count",
                "estimated_week_end_le10_holder_count")):
            return False
        if not (.50<=row["daily_decline_score"]<=1
                and row["return_20d"]>=.05 and row["return_5d"]>=0
                and row["median_20d_turnover_twd"]>=1e7
                and row["last_known_le10_holder_count"]>0
                and row["estimated_week_end_le10_holder_count"]>0):
            return False
        turnover=row["median_20d_turnover_twd"]
        if prev is not None and turnover>prev:
            return False
        prev=turnover
    return [z["ticker"] for z in top]==["1216","2618","1476","9904","2610"]


def observation(now=None,root=None):
    now=now or datetime.now(TZ)
    now=(now if now.tzinfo else now.replace(tzinfo=TZ)).astimezone(TZ)
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    base={
        "schema":"HENGCE_V22D_DAILY_PRIMARY_RESEARCH_READER_V1",
        "model":"V2.2-D",
        "model_id":"v22d_daily_nowcast_liquidity_top5_v1",
        "status":"V22D_PREFERENCE_UNVERIFIED",
        "source_date":None,
        "source_kind":None,
        "top5":[],
        "qualified_count":0,
        "research_only":True,
        "retrospective_only":True,
        "current_selection":False,
        "not_current_recommendations":True,
        "score_is_calibrated_probability":False,
        "buy_signal":False,"sell_signal":False,
        "formal_selection_authority":False,
        "broker_execution":False,"authorized_lots":0,"capital_authority_twd":0,
        "baseline_v22_is_not_current_primary":True
    }
    if not selected_v22d(root):
        return base
    # Never show old history as a CURRENT selection. Source models required for
    # actual 2026-11-11 daily forecast are absent; presence of a new JSON alone
    # is not enough to certify a model ran at time of decision.
    if (root/LIVE).exists():
        base["status"]="V22D_CURRENT_FORECAST_NEEDS_VERIFIED_MODEL_AND_PIT_INPUTS"
        base["reason"]="Uncertified daily receipt may not replace original trained model evidence"
        return base
    d=_read(root/FROZEN)
    if not validate_historical(d,now):
        base["status"]="V22D_HISTORICAL_SOURCE_UNVERIFIED"
        return base
    base.update(status="HISTORICAL_V22D_TOP5_VERIFIED",
                source_date=d["decision_date"],
                source_kind="V22D_PINNED_20261105_HISTORICAL_UNVERIFIED_PIT",
                archive_sha256=d["source_package_sha256"],
                source_forecast_sha256=d["source_forecast_data_sha256"],
                age_calendar_days=(now.date()-date.fromisoformat(d["decision_date"])).days,
                top5=[dict(z) for z in d["top5"]],
                qualified_count=d["qualified_count"],
                retrospectively_selected_top5=True,
                latest_daily_model_ready=False,
                why_not_current=[
                    "Historical daily forecasts stop on 2026-11-05",
                    "No deployed original V2.2-D trained model checkpoint or new immutable daily PIT forecast receipt",
                    "Cannot treat weekly TDCC later-publication as same-day observed holder counts",
                ])
    return base
