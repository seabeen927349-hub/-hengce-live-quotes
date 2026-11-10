#!/usr/bin/env python3
"""HENGCE research-only whole-lot display from an upstream frozen PIT ranking.

Does not compute the ranking, select a stock, read a broker, send orders, restore
Q017, modify S5/Escape/RMS, or create any formal trading authority.
"""
import argparse
import json
import math
from pathlib import Path
from datetime import date

SCHEMA = "HENGCE_RETAIL_WHOLELOT_SHADOW_BOARD_V1"
RANK_SCHEMA = "HENGCE_VERIFIED_FROZEN_RETAIL_RANKING_V1"
AUTHORITY = "RESEARCH_ONLY_NO_SELECTION_NO_TRADING"
FEE = 0.0025
LOT_SHARES = 1000

def numeric(v):
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (ValueError, TypeError, OverflowError):
        return None

def block(asof, reason):
    return {"schema":SCHEMA,"asof":asof,"status":"DATA_BLOCKED","reason":reason,
            "authority":AUTHORITY,"research_top10":[],"position_reviews":[],
            "formal_selection":False,"broker_order_execution":False,
            "capital_authority_twd":0}

def evaluate(ranking, account, contract, asof):
    try:
        date.fromisoformat(asof)
    except (TypeError, ValueError):
        return block(asof,"INVALID_ASOF")
    if not isinstance(contract,dict) or (
        contract.get("status") != "NO_ACTIVE_SELECTION_STRATEGY" or
        contract.get("active_strategy_count") != 0 or
        contract.get("broker_order_execution") is not False or
        contract.get("capital_authority_twd") != 0
    ):
        return block(asof,"FORMAL_RETIREMENT_CONTRACT_NOT_VERIFIED")
    if not isinstance(ranking,dict) or ranking.get("schema") != RANK_SCHEMA:
        return block(asof,"NO_FROZEN_PIT_RANKING")
    if not (ranking.get("signal_asof")==asof
            and ranking.get("authority")=="RESEARCH_ONLY"
            and ranking.get("pit_verified") is True
            and ranking.get("frozen_source") is True
            and isinstance(ranking.get("source_sha256"),str)
            and len(ranking["source_sha256"])==64
            and all(c in "0123456789abcdef" for c in ranking["source_sha256"])):
        return block(asof,"PIT_OR_SOURCE_NOT_VERIFIED")
    rows=ranking.get("ranked_candidates")
    if not isinstance(rows,list) or not 0<=len(rows)<=10:
        return block(asof,"INVALID_RANK_LIST")
    if any(not isinstance(r,dict) for r in rows):
        return block(asof,"INVALID_RANK_ROW")
    if [r.get("rank") for r in rows] != list(range(1,len(rows)+1)):
        return block(asof,"NON_FROZEN_RANK_ORDER")
    tickers=[r.get("ticker") for r in rows]
    if (len(set(tickers))!=len(tickers) or
        any(not isinstance(t,str) or len(t)!=4 or not t.isdigit() for t in tickers) or
        any(r.get("ranking_basis")!="FROZEN_20D_MEDIAN_TURNOVER_DESC" for r in rows)):
        return block(asof,"INVALID_OR_UNVERIFIED_RANKS")
    if not isinstance(account,dict) or account.get("scope")!="INDEPENDENT_RESEARCH_ACCOUNT":
        return block(asof,"RESEARCH_ACCOUNT_MISSING")
    equity=numeric(account.get("equity_twd"))
    cash=numeric(account.get("free_cash_twd"))
    held=account.get("held_tickers")
    if (equity is None or equity<=0 or cash is None or not 0<=cash<=equity or
        not isinstance(held,list) or len(held)>4 or
        any(not isinstance(t,str) for t in held) or len(set(held))!=len(held)):
        return block(asof,"ACCOUNT_OR_HOLDINGS_INVALID")
    preview_cash=cash
    slots=4-len(held)
    ranked=[]
    for r in rows:
        ticker=r["ticker"]
        price=numeric(r.get("reference_close_twd"))
        correct_date=r.get("reference_close_date")==asof
        one_lot=math.ceil(LOT_SHARES*price*(1+FEE)) if price and price>0 else None
        block_reasons=[]
        if ticker in held: block_reasons.append("ALREADY_HELD")
        if slots<=0: block_reasons.append("FOUR_POSITION_LIMIT")
        if not one_lot or not correct_date: block_reasons.append("VERIFIED_EOD_PRICE_MISSING")
        if r.get("qualified_signal_verified") is not True: block_reasons.append("SIGNAL_NOT_VERIFIED")
        if r.get("tdcc_available_at_decision") is not True: block_reasons.append("TDCC_PIT_NOT_VERIFIED")
        if r.get("stock_tradable_verified") is not True: block_reasons.append("EXCHANGE_TRADABILITY_NOT_VERIFIED")
        for key in ("rms","s5","escape","investor_access"):
            if r.get(key)!="PASS": block_reasons.append(key.upper()+"_NOT_PASS")
        budget=max(0,min(.30*equity,preview_cash-.10*equity))
        lots=math.floor(budget/one_lot) if one_lot else 0
        if lots<1: block_reasons.append("ONE_LOT_NOT_AFFORDABLE")
        if block_reasons:
            lots=0
        else:
            slots-=1
            preview_cash-=lots*one_lot
        ranked.append({
            "rank":r["rank"],"ticker":ticker,"name":r.get("name"),
            "reference_close_twd":price,"reference_close_date":r.get("reference_close_date"),
            "one_lot_estimated_cost_twd":one_lot,"lots_simulated":lots,
            "total_estimated_cost_twd":int(lots*one_lot) if one_lot else 0,
            "display":"BLOCKED" if block_reasons else "RESEARCH_CAPACITY_ONLY",
            "reasons":block_reasons,"formal_can_buy":False})
    positions=account.get("actual_positions_for_review") or []
    if not isinstance(positions,list):
        return block(asof,"POSITION_REVIEW_INVALID")
    reviewed=[]
    for p in positions:
        if not isinstance(p,dict) or not isinstance(p.get("ticker"),str):
            return block(asof,"POSITION_REVIEW_INVALID")
        # Avoid interpreting the brokerage transaction as a position held today.
        needs=[k for k in ("entry_cost_twd","latest_close_twd","max_close_since_entry_twd",
                           "ma30_twd","below_ma30_three_days","return_5d_pct",
                           "shares_confirmed_asof","close_asof") if p.get(k) is None]
        if p.get("close_asof")!=asof: needs.append("CURRENT_EOD")
        if p.get("shares_confirmed_asof")!=asof: needs.append("CURRENT_POSITION")
        triggers=[]
        if not needs:
            vals=[numeric(p[k]) for k in ("entry_cost_twd","latest_close_twd",
                         "max_close_since_entry_twd","ma30_twd","return_5d_pct")]
            cost,close,peak,ma,ret=vals
            if (any(x is None for x in vals) or
                any(x<=0 for x in (cost,close,peak,ma)) or
                not isinstance(p["below_ma30_three_days"],bool)):
                needs.append("INVALID_POSITION_DATA")
            else:
                if close<=.92*cost:triggers.append("CLOSE_BELOW_COST_BY_8PCT")
                if close<=.85*peak:triggers.append("CLOSE_BELOW_PEAK_BY_15PCT")
                if p["below_ma30_three_days"] and ret<0:
                    triggers.append("MA30_THREE_CLOSES_AND_NEGATIVE_5D")
        reviewed.append({
            "ticker":p["ticker"],
            "status":"DATA_BLOCKED" if needs else
                     ("HUMAN_EXIT_REVIEW" if triggers else "NO_RESEARCH_EXIT_TRIGGER"),
            "missing":needs,"trigger_reasons":triggers,"formal_can_sell":False})
    return {
        "schema":SCHEMA,"status":"RESEARCH_DISPLAY_READY","asof":asof,"authority":AUTHORITY,
        "source_sha256":ranking["source_sha256"],"research_top10":ranked,
        "position_reviews":reviewed,
        "preview_cash_remaining_twd":round(preview_cash,2),
        "note":"Prices are as-of-close estimates, NOT next-session executable prices.",
        "formal_selection":False,"broker_order_execution":False,
        "capital_authority_twd":0}

def read_json(path):
    try:return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError,ValueError,TypeError):return None

def main():
    p=argparse.ArgumentParser()
    for key in ("asof","ranking","account","contract"):
        p.add_argument("--"+key,required=True)
    p.add_argument("--out")
    x=p.parse_args()
    obj=evaluate(read_json(x.ranking),read_json(x.account),read_json(x.contract),x.asof)
    s=json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
    if x.out:
        path=Path(x.out)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(s,encoding="utf-8")
    print(s,end="")
if __name__=="__main__":
    main()
