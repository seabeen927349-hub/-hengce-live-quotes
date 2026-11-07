#!/usr/bin/env python3
"""Compare FinMind 2025 historical shareholding tiers against official frozen TDCC.

Research-only, NO promotion. Do not silently conflate the accounting-adjustment
row, total row, and 15 valid shareholder holding ranges.
"""
from __future__ import annotations
import csv
import gzip
import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path("/tmp/hengce-finmind-tdcc-probe/finmind_2330_2025-11-01_2025-12-01.csv.gz")
OFFICIAL=ROOT/"ownership/tdcc/backfill_candidate/full_market_2025_tail/20251107/tdcc_ownership_4d.csv"
OUT=Path("/tmp/hengce-finmind-crosscheck/receipt.json")
DATE="20251107"
TICKER="2330"

def normalized_lower_bound(level:str):
    clean=re.sub(r"[,，\s股]", "",level).replace("～","-").replace("~","-")
    if "差異數調整" in clean or "合計" in clean or "總計" in clean or clean.lower()=="total":
        return None
    english_top=re.match(r"^morethan(\d+)$",clean.lower())
    if english_top:
        return int(english_top.group(1))
    m=re.match(r"^(\d+)(?:-|以上|及以上|\+)",clean)
    if not m:
        return None
    return int(m.group(1))

def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    report={"status":"BLOCKED","source":"FinMind historical 2330 TDCC holding tiers",
            "reference_date":DATE,"ticker":TICKER,
            "official":"HENGCE frozen TDCC 2025 tail 20251107",
            "observed_at_utc":datetime.now(timezone.utc).isoformat(),
            "research_only":True, "no_model_or_trading_authority":True}
    try:
        with gzip.open(SOURCE,"rt",encoding="utf-8",newline="") as fd:
            rows=[r for r in csv.DictReader(fd) if r["date"].replace("-","")==DATE and r["stock_id"]==TICKER]
        with OFFICIAL.open(encoding="utf-8",newline="") as fd:
            official=[r for r in csv.DictReader(fd) if r["SnapshotDate"]==DATE and r["Ticker"]==TICKER]
        if len(official)!=1 or not rows:
            raise ValueError("NO_OVERLAPPING_OFFICIAL_FINMIND_DATE")
        high=[];super_high=[];other=[]
        for r in rows:
            low=normalized_lower_bound(r["HoldingSharesLevel"])
            if low is None:
                other.append({"level":r["HoldingSharesLevel"],"unit":int(r["unit"])})
                continue
            if low>=400001:
                high.append(r)
            if low>=1000001:
                super_high.append(r)
        if len(high)!=4 or len(super_high)!=1:
            raise ValueError(f"UNKNOWN_LEVEL_SCHEMA high={len(high)} super={len(super_high)} levels={sorted(r['HoldingSharesLevel'] for r in rows)}")
        def totals(v):
            return {"pct":round(sum(float(x["percent"]) for x in v),6),
                    "shares":sum(int(x["unit"]) for x in v),
                    "holders":sum(int(x["people"]) for x in v)}
        fm400=totals(high); fm1000=totals(super_high); tdcc=official[0]
        rec={"FinMind":{"Big400":fm400,"Big1000":fm1000},
             "TDCC":{"Big400":{"pct":float(tdcc["Big400Pct"]),"shares":int(tdcc["Big400Shares"]),"holders":int(tdcc["Big400Holders"])},
                    "Big1000":{"pct":float(tdcc["Big1000Pct"]),"shares":int(tdcc["Big1000Shares"]),"holders":int(tdcc["Big1000Holders"])}},
             "non_tier_rows":other}
        report.update(rec)
        report["comparison"]={}
        ok=True
        for k,v in [("Big400",fm400),("Big1000",fm1000)]:
            src=rec["TDCC"][k]
            deltas={"pct":round(v["pct"]-src["pct"],6),
                    "shares":v["shares"]-src["shares"],"holders":v["holders"]-src["holders"]}
            report["comparison"][k]=deltas
            if abs(deltas["pct"])>0.1 or deltas["shares"]!=0 or deltas["holders"]!=0:
                ok=False
        report["status"]="PASS_EXACT_OR_WITHIN_ROUNDING" if ok else "MISMATCH_RESEARCH_BLOCKED"
    except Exception as ex:
        report["error"]=f"{type(ex).__name__}:{ex}"
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("HENGCE_FINMIND_TDCC_OFFICIAL_CROSSCHECK",report["status"],flush=True)
    if "error" in report:
        print("HENGCE_FINMIND_CROSSCHECK_ERROR",report["error"],flush=True)
    if "comparison" in report:
        print("HENGCE_FINMIND_TDCC_DELTAS",json.dumps(report["comparison"],ensure_ascii=False),flush=True)
    return 0 if report["status"]=="PASS_EXACT_OR_WITHIN_ROUNDING" else 2

if __name__=="__main__":
    raise SystemExit(main())
