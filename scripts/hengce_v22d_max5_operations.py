#!/usr/bin/env python3
"""HENGCE V2.2-D + MAX5: reproducible no-order daily position & price worklist.

This workflow consumes only HENGCE's existing canonical original EOD receipts,
the primary V2.2-D research reader, and EXPLICIT account-supplied positions and
trade journal. No new market-data vessel, model, or broker connection is created.
An absent account/forecast/ATR cannot silently become an empty 'no buy/no sell'.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import date, datetime, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from scripts.hengce_v22_max5_atr_price_plan import (
        OriginalPriceVessel, PriceEvidenceBlocked, _calendar,
        advance_atr_floor,
    )
    from scripts.hengce_twse_calendar import is_trading_day, next_trading_day
    from scripts.hengce_v22d_daily_reader import observation, selected_v22d
except ModuleNotFoundError:
    from hengce_v22_max5_atr_price_plan import (
        OriginalPriceVessel, PriceEvidenceBlocked, _calendar,
        advance_atr_floor,
    )
    from hengce_twse_calendar import is_trading_day, next_trading_day
    from hengce_v22d_daily_reader import observation, selected_v22d

TW = ZoneInfo("Asia/Taipei")
HOLDING_COLS = ("ticker", "entry_date", "entry_fill", "quantity",
                "signal_atr20", "peak_close", "risk_floor", "pending_exit",
                "last_reviewed_session")
JOURNAL_COLS = ("ticker", "trade_date", "side", "status", "quantity")


class OperationsBlocked(ValueError):
    pass


def _positive(v, name):
    try:
        x=float(v)
    except (TypeError, ValueError) as e:
        raise OperationsBlocked("INVALID_" + name) from e
    if not math.isfinite(x) or x <= 0:
        raise OperationsBlocked("INVALID_" + name)
    return x


def _bool(v):
    if v in (True, "true", "TRUE", "1", 1):
        return True
    if v in (False, "false", "FALSE", "0", 0, "", None):
        return False
    raise OperationsBlocked("INVALID_PENDING_EXIT_FLAG")


def _calendar_days(cal, first: date, last: date):
    if last < first:
        return []
    if first.year != 2026 or last.year != 2026:
        raise OperationsBlocked("2026_PINNED_CALENDAR_COVERAGE_ONLY")
    days=[]
    for offset in range((last-first).days+1):
        d=first+timedelta(days=offset)
        if is_trading_day(d, cal):
            days.append(d)
    return days


def _journal_checks(journal, holdings, today):
    if journal is None:
        return "ACTUAL_WEEKLY_TRANSACTION_JOURNAL_NOT_PROVIDED", None
    if not isinstance(journal,list):
        return "INVALID_JOURNAL", None
    week_start=today-timedelta(days=today.weekday())
    used=0
    pending=0
    identifiers=set()
    for row in journal:
        if not isinstance(row,dict):
            return "INVALID_JOURNAL", None
        ticker=str(row.get("ticker","")).strip()
        if len(ticker)!=4 or not ticker.isdigit() or ticker.startswith("0"):
            return "INVALID_JOURNAL_TICKER", None
        try:
            dt=date.fromisoformat(str(row.get("trade_date","")))
            shares=_positive(row.get("quantity"),"JOURNAL_QUANTITY")
        except (ValueError,OperationsBlocked):
            return "INVALID_JOURNAL_TRADE", None
        if dt>today or (row.get("side") not in ("BUY","SELL")
                        or row.get("status") not in ("FILLED","PENDING","CANCELED")):
            return "INVALID_JOURNAL_TRADE", None
        ident=(ticker,dt.isoformat(),row["side"],row["status"],shares)
        if ident in identifiers:
            return "JOURNAL_DUPLICATE_ENTRY", None
        identifiers.add(ident)
        if dt>=week_start and row["side"]=="BUY":
            if row["status"]=="FILLED":
                used+=1
            elif row["status"]=="PENDING":
                pending+=1
    if used>1 or used+pending>1:
        return "MAX_ONE_WEEKLY_BUY_VIOLATED", {"filled_buy":used,"pending_buy":pending}
    return "USER_SUPPLIED_UNVERIFIED", {"filled_buy":used,"pending_buy":pending}


def _previous_lookup(previous):
    if previous is None:
        return {}, "NO_PRIOR_WORKLIST_SNAPSHOT"
    if (not isinstance(previous,dict)
        or previous.get("schema")!="HENGCE_V22D_MAX5_OPERATIONAL_WORKLIST_V1"
        or previous.get("broker_execution") is not False
        or not isinstance(previous.get("position_states"),list)):
        raise OperationsBlocked("PRIOR_WORKLIST_SCHEMA_INVALID")
    lookup={}
    for x in previous["position_states"]:
        code=x.get("ticker") if isinstance(x,dict) else None
        if not isinstance(code,str) or code in lookup:
            raise OperationsBlocked("PRIOR_WORKLIST_DUPLICATE_OR_INVALID")
        lookup[code]=x
    return lookup,"USER_SUPPLIED_PRIOR_WORKLIST_NOT_BROKER_RECEIPT"


def _review_holding(h, asof_day, cal, vessel, previous):
    ticker=str(h.get("ticker","")).strip()
    item={
        "ticker":ticker,"status":"BLOCKED_POSITION_EVIDENCE",
        "action":"NO_AUTOMATIC_ACTION","research_only":True,
        "broker_fill_confirmed":False,
    }
    try:
        if len(ticker)!=4 or not ticker.isdigit() or ticker.startswith("0"):
            raise OperationsBlocked("INVALID_TICKER")
        entry=date.fromisoformat(str(h.get("entry_date","")))
        if entry>asof_day or entry.year!=2026 or not is_trading_day(entry,cal):
            raise OperationsBlocked("ENTRY_SESSION_NOT_VERIFIED")
        fill=_positive(h.get("entry_fill"),"ENTRY_FILL")
        qty=_positive(h.get("quantity"),"QUANTITY")
        if not qty.is_integer():
            raise OperationsBlocked("QUANTITY_MUST_BE_WHOLE_SHARES")
        signal_atr=_positive(h.get("signal_atr20"),"ENTRY_SIGNAL_ATR20")
        initial=fill-2*signal_atr
        if initial<=0:
            raise OperationsBlocked("INITIAL_ATR_RISK_FLOOR_NONPOSITIVE")
        prev=previous.get(ticker) or {}
        if prev and prev.get("status") not in (
            "POSITION_RISK_MONITORED","EXIT_PENDING_MANUAL_CONFIRMATION",
            "BLOCKED_POSITION_EVIDENCE"):
            raise OperationsBlocked("PRIOR_POSITION_STATE_UNVERIFIED")
        if prev and (prev.get("entry_date")!=entry.isoformat()
                     or float(prev.get("entry_fill",0))!=fill
                     or float(prev.get("quantity",0))!=qty):
            raise OperationsBlocked("POSITION_CHANGED_WITHOUT_RECONCILED_EXECUTION")
        checkpoint=str(h.get("last_reviewed_session") or "")
        start=date.fromisoformat(checkpoint)+timedelta(days=1) if checkpoint else entry
        if checkpoint:
            prevday=date.fromisoformat(checkpoint)
            if prevday<entry or prevday>asof_day or not is_trading_day(prevday,cal):
                raise OperationsBlocked("CARRIED_REVIEW_DATE_INVALID")
            if not prev or prev.get("last_verified_eod_date")!=checkpoint:
                raise OperationsBlocked("CARRIED_STATE_NOT_BOUND_TO_PRIOR_WORKLIST")
        if prev:
            if h.get("risk_floor") not in ("",None) and float(h["risk_floor"])<float(prev.get("effective_risk_floor",0)):
                raise OperationsBlocked("CARRIED_FLOOR_ROLLBACK")
            if h.get("peak_close") not in ("",None) and float(h["peak_close"])<float(prev.get("peak_close",0)):
                raise OperationsBlocked("CARRIED_PEAK_ROLLBACK")
        carried_floor=_positive(h.get("risk_floor") or initial,"RISK_FLOOR")
        carried_peak=_positive(h.get("peak_close") or fill,"PEAK_CLOSE")
        floor=max(initial,carried_floor,float(prev.get("effective_risk_floor",0)) if prev else 0)
        peak=max(fill,carried_peak,float(prev.get("peak_close",0)) if prev else 0)
        latched=_bool(h.get("pending_exit"))
        if prev and prev.get("pending_exit") is True and not latched:
            raise OperationsBlocked("PENDING_EXIT_LATCH_CANNOT_BE_CLEARED_WITHOUT_SELL")
        if prev and prev.get("pending_exit") is True:
            latched=True
        initial_state=(floor,peak,latched)
        last_verified=checkpoint or None
        last_close=None
        trigger_date=prev.get("first_trigger_date") if prev else None
        days=_calendar_days(cal,start,asof_day)
        # ALL official sessions must have verified OHLC/ATR. Failure cannot
        # advance the previous checkpoint, or claim 'no sell' after a gap.
        for d in days:
            observed=vessel.ticker_day(d,ticker)
            atr=vessel.atr20(d,ticker,cal)["atr20"]
            close=_positive(observed["Close"],"OFFICIAL_CLOSE")
            updated=advance_atr_floor(fill,initial,floor,peak,close,atr,latched)
            floor=updated["effective_risk_floor"]
            peak=updated["peak_close"]
            if updated["exit_signal_new_today"] and trigger_date is None:
                trigger_date=d.isoformat()
            latched=updated["exit_triggered"]
            last_verified=d.isoformat()
            last_close=close
        if not checkpoint and not days:
            raise OperationsBlocked("NO_OFFICIAL_SESSION_SINCE_ENTRY")
        item.update(status=("EXIT_PENDING_MANUAL_CONFIRMATION" if latched
                            else "POSITION_RISK_MONITORED"),
                    action=("REVIEW_NEXT_TRADEABLE_OPEN_EXIT" if latched
                            else "HOLD_AND_MONITOR"),
                    entry_date=entry.isoformat(),entry_fill=fill,quantity=int(qty),
                    entry_signal_atr20=signal_atr,
                    initial_risk_floor=round(initial,6),
                    effective_risk_floor=round(floor,6),
                    peak_close=round(peak,6),
                    pending_exit=latched,first_trigger_date=trigger_date,
                    last_verified_eod_date=last_verified,
                    latest_verified_close=last_close,
                    new_eod_sessions_reviewed=len(days),
                    exit_price_known_in_advance=False,
                    risk_floor_not_guaranteed_fill=True,
                    statement="ACCOUNT_SUPPLIED_INPUT_WITH_ORIGINAL_EOD_VERIFIED")
    except (ValueError,KeyError,TypeError,PriceEvidenceBlocked,OperationsBlocked) as e:
        item["reason"]=str(e)
        item["prior_checkpoint_retained"]=bool(previous.get(ticker))
        item["no_sell_conclusion_allowed"]=False
    return item


def worklist(asof=None, root=None, holdings=None, journal=None, previous=None,
             selection=None, vessel=None, calendar=None):
    asof=asof or datetime.now(TW)
    asof=(asof if asof.tzinfo else asof.replace(tzinfo=TW)).astimezone(TW)
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    result={
        "schema":"HENGCE_V22D_MAX5_OPERATIONAL_WORKLIST_V1",
        "mode":"RESEARCH_ONLY_MANUAL_ACCOUNT_NO_ORDERS",
        "as_of_taipei":asof.isoformat(),"decision_date":asof.date().isoformat(),
        "status":"NOT_READY_INPUT_EVIDENCE",
        "source_selection":"V2.2-D_DAILY_PREFERRED",
        "max_positions":5,"max_new_entries_per_week":1,
        "position_states":[],"tasks":[],"candidate":None,
        "research_only":True,"current_buy_recommendation":False,
        "buy_signal":False,"sell_signal":False,
        "formal_selection_authority":False,"broker_execution":False,
        "capital_authority_twd":0,"authorized_lots":0,
        "original_vessels_read_only":True,"risk_floor_is_not_guaranteed_fill":True,
    }
    if not selected_v22d(root):
        result["status"]="BLOCKED_PRIMARY_V22D_PREFERENCE_UNVERIFIED"
        return result
    try:
        cal=calendar if calendar is not None else _calendar(root)
        if asof.year!=2026:
            raise OperationsBlocked("TWSE_CALENDAR_YEAR_NOT_SUPPORTED")
        instrument=vessel if vessel is not None else OriginalPriceVessel(root)
        prev,prior_status=_previous_lookup(previous)
        result["previous_worklist_status"]=prior_status
    except (PriceEvidenceBlocked,OperationsBlocked,ValueError,TypeError) as e:
        result["status"]="BLOCKED_OPERATIONAL_SOURCES"
        result["reason"]=str(e)
        return result
    if holdings is None:
        result["account_status"]="ACCOUNT_HOLDINGS_NOT_PROVIDED"
        result["status"]="WAITING_ACTUAL_ACCOUNT_SNAPSHOT"
        return result
    if not isinstance(holdings,list) or len(holdings)>5 or any(not isinstance(x,dict) for x in holdings):
        result["status"]="BLOCKED_MAX5_OR_INVALID_HOLDINGS"
        return result
    # Never inspect a current-day EOD before the existing 23:00 Taipei
    # original-vessel schedule. Weekend/holiday reviews use last official day.
    # This is a conservative time guard; real receipt availability is checked
    # by OriginalPriceVessel and its unmodified SHA/mother proofs.
    review_day=asof.date()
    if review_day.year!=2026:
        result["status"]="BLOCKED_CALENDAR_COVERAGE"
        return result
    if (not is_trading_day(review_day,cal)
        or asof.time() < time(23,0)):
        probe=review_day-timedelta(days=1)
        for _ in range(15):
            if probe.year==2026 and is_trading_day(probe,cal):
                review_day=probe
                break
            probe-=timedelta(days=1)
        else:
            result["status"]="BLOCKED_NO_PRIOR_OFFICIAL_SESSION"
            return result
    result["review_eod_session"]=review_day.isoformat()
    result["new_intraday_quote_claimed"]=False
    codes=[str(h.get("ticker","")).strip() for h in holdings]
    if len(codes)!=len(set(codes)):
        result["status"]="BLOCKED_DUPLICATE_ACCOUNT_HOLDINGS"
        return result
    if any(code not in codes for code in prev):
        result["status"]="BLOCKED_ACCOUNT_POSITION_DISAPPEARED_WITHOUT_SELL_RECEIPT"
        result["missing_prior_positions"]=sorted(set(prev)-set(codes))
        return result
    result["account_status"]="USER_SUPPLIED_NOT_BROKER_VERIFIED"
    result["position_count"]=len(holdings)
    result["remaining_slots"]=5-len(holdings)
    for holding in holdings:
        p=_review_holding(holding,review_day,cal,instrument,prev)
        result["position_states"].append(p)
        if p["status"]=="EXIT_PENDING_MANUAL_CONFIRMATION":
            result["tasks"].append({
                "priority":1,"ticker":p["ticker"],
                "action":"REVIEW_EXIT_NEXT_VALID_OPEN",
                "trigger_date":p["first_trigger_date"],
                "risk_floor":p["effective_risk_floor"],
                "price_known":False,
                "must_verify_broker_fill":True})
    # Account execution journal remains untrusted manually provided; no bank or
    # broker connector is being used and historical order logs aren't invented.
    journal_status,week=_journal_checks(journal,holdings,asof.date())
    result["journal_status"]=journal_status
    result["weekly_buy_usage"]=week
    daily=selection if selection is not None else observation(asof,root)
    result["v22d_selection_status"]=daily.get("status") if isinstance(daily,dict) else "INVALID"
    possible=(isinstance(daily,dict)
              and daily.get("status")=="CURRENT_V22D_PIT_TOP5_VERIFIED"
              and daily.get("source_date")==review_day.isoformat()
              and daily.get("current_selection") is True
              and daily.get("formal_selection_authority") is False
              and daily.get("broker_execution") is False
              and daily.get("buy_signal") is False
              and daily.get("sell_signal") is False
              and daily.get("authorized_lots")==0
              and daily.get("source_kind")=="ORIGINAL_V22D_CHECKPOINT_EOD_TDCC_PIT")
    if any(p["status"]=="BLOCKED_POSITION_EVIDENCE" for p in result["position_states"]):
        result["status"]="PARTIAL_HOLDING_RISK_BLOCKED_NO_NEW_BUY"
    elif not possible:
        result["status"]="WAITING_VERIFIED_CURRENT_V22D_DAILY_FORECAST"
    elif journal_status!="USER_SUPPLIED_UNVERIFIED":
        result["status"]="WAITING_VALID_WEEKLY_ACCOUNT_JOURNAL"
    elif week["filled_buy"]+week["pending_buy"]>=1:
        result["status"]="WEEKLY_NEW_ENTRY_LIMIT_REACHED"
    elif len(holdings)>=5:
        result["status"]="MAX5_FULL_INCLUDING_PENDING_EXITS"
    elif len(result["tasks"])>0:
        result["status"]="EXIT_REVIEW_PRIORITY_NO_NEW_BUY"
    else:
        # A verified current daily Top5 can arrive after official EOD. Its
        # entry is NEXT session open, not today's close or tomorrow's guessed price.
        try:
            target=next_trading_day(review_day,cal)
            proposals=daily.get("top5")
            if not isinstance(proposals,list) or len(proposals)>5:
                raise OperationsBlocked("V22D_TOP5_SCHEMA_INVALID")
            used=set(codes)
            for row in proposals:
                ticker=str(row.get("ticker","")).strip() if isinstance(row,dict) else ""
                if len(ticker)!=4 or not ticker.isdigit() or ticker.startswith("0"):
                    raise OperationsBlocked("V22D_TOP5_TICKER_INVALID")
                if ticker in used:
                    continue
                info=instrument.atr20(review_day,ticker,cal)
                result["candidate"]={
                    "ticker":ticker,"signal_date":review_day.isoformat(),
                    "planned_next_session":target,
                    "signal_day_official_close":info["official_close"],
                    "signal_atr20":info["atr20"],
                    "buy_price":"UNKNOWN_UNTIL_NEXT_OPEN_OR_ACTUAL_BROKER_FILL",
                    "initial_risk_floor_after_fill_formula":"ACTUAL_FILL_MINUS_2ATR20",
                    "fixed_take_profit":None,
                    "requires_manual_account_and_execution_confirmation":True,
                }
                result["status"]="ONE_RESEARCH_NEXT_OPEN_ENTRY_SLOT_AVAILABLE"
                break
            if result["candidate"] is None:
                result["status"]="NO_UNHELD_PRICE_VERIFIED_V22D_CANDIDATE"
        except (ValueError,TypeError,PriceEvidenceBlocked,OperationsBlocked) as e:
            result["status"]="BLOCKED_ATR_OR_TRADING_CALENDAR_FOR_ENTRY"
            result["reason"]=str(e)
    result["reviewed_position_count"]=sum(
        p["status"]!="BLOCKED_POSITION_EVIDENCE" for p in result["position_states"])
    result["pending_exit_count"]=sum(
        p["status"]=="EXIT_PENDING_MANUAL_CONFIRMATION" for p in result["position_states"])
    result["source_holders_are_actual_daily_count"]=False
    return result


def _load_csv(path, required):
    with Path(path).open(encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames or not set(required).issubset(reader.fieldnames):
            raise OperationsBlocked("ACCOUNT_CSV_REQUIRED_FIELDS:" + ",".join(required))
        return list(reader)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--asof",help="Asia/Taipei ISO time")
    p.add_argument("--holdings",help="actual manual holdings CSV; required for portfolio check")
    p.add_argument("--journal",help="actual manual trade journal CSV; required before new buy")
    p.add_argument("--previous-state",help="previous confirmed worklist JSON")
    p.add_argument("--output",help="output derived worklist JSON OUTSIDE repository")
    args=p.parse_args()
    try:
        now=datetime.fromisoformat(args.asof) if args.asof else datetime.now(TW)
        holdings=_load_csv(args.holdings,HOLDING_COLS[:4]) if args.holdings else None
        journal=_load_csv(args.journal,JOURNAL_COLS) if args.journal else None
        previous=json.loads(Path(args.previous_state).read_text(encoding="utf8")) if args.previous_state else None
        payload=worklist(now,holdings=holdings,journal=journal,previous=previous)
        message=json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
        if args.output:
            path=Path(args.output).resolve()
            repo=Path(__file__).resolve().parents[1]
            if path.is_relative_to(repo):
                raise OperationsBlocked("OUTPUT_MUST_BE_OUTSIDE_REPOSITORY")
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(message,encoding="utf8")
        else:
            print(message,end="")
    except (OSError,ValueError,OperationsBlocked) as e:
        print(json.dumps({"status":"BLOCKED","reason":str(e),"broker_execution":False},ensure_ascii=False))
        return 2
    return 0


if __name__=="__main__":
    raise SystemExit(main())
