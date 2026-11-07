#!/usr/bin/env python3
"""HENGCE FinMind marketwide historical TDCC feasibility probe (no licensed raw export).

Checks whether the existing FINMIND_TOKEN supports marketwide
TaiwanStockHoldingSharesPer access without data_id. Emits only aggregate counts.
"""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.finmindtrade.com/api/v4/data"
OUT = Path("/tmp/hengce-finmind-market-probe/marketwide_manifest.json")
WINDOWS = [("2018-01-01","2018-01-15"),("2024-01-01","2024-01-15")]

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    token=os.environ.get("FINMIND_TOKEN","").strip()
    result={"schema":"HENGCE_TDCC_FINMIND_MARKETWIDE_PROBE_V1",
            "research_only":True,"no_raw_data_persisted":True,"no_canonical_mutation":True,
            "observed_at_utc":datetime.now(timezone.utc).isoformat(),"probes":[]}
    if not token:
        result["status"]="BLOCKED_TOKEN_MISSING"
        OUT.write_text(json.dumps(result,indent=2)+"\n")
        return 2
    for start,end in WINDOWS:
        params=urllib.parse.urlencode({"dataset":"TaiwanStockHoldingSharesPer","start_date":start,"end_date":end})
        req=urllib.request.Request(API+"?"+params,headers={"Authorization":"Bearer "+token,"User-Agent":"HENGCE-FinMind-marketwide-research/1.0"})
        try:
            with urllib.request.urlopen(req,timeout=120) as response:
                payload=json.load(response)
            state=payload.get("status")
            rows=payload.get("data")
            if state!=200 or not isinstance(rows,list):
                result["probes"].append({"window":[start,end],"status":"BLOCKED","api_status":state,
                      "nonsecret_message":str(payload.get("msg") or payload.get("message") or "")[:180]})
                break
            dates=set();codes=set();levels=set();adjustments=0;bad=0
            for row in rows:
                if not isinstance(row,dict) or not all(k in row for k in ("date","stock_id","HoldingSharesLevel","people","percent","unit")):
                    bad+=1;continue
                dates.add(str(row["date"]));codes.add(str(row["stock_id"]))
                lev=str(row["HoldingSharesLevel"]);levels.add(lev)
                if "差異數調整" in lev:adjustments+=1
            result["probes"].append({"window":[start,end],"status":"PASS" if rows and not bad else "BAD_ROWS",
                "rows":len(rows),"snapshot_count":len(dates),"first_snapshot":min(dates) if dates else None,
                "last_snapshot":max(dates) if dates else None,
                "unique_security_codes":len(codes),"level_count":len(levels),
                "accounting_adjustment_rows":adjustments,"bad_schema_rows":bad})
            print("MARKETWIDE_PROBE",start,len(rows),"rows",len(codes),"tickers",flush=True)
            if not rows or bad:break
        except urllib.error.HTTPError as ex:
            result["probes"].append({"window":[start,end],"status":"BLOCKED_HTTP","code":ex.code})
            break
        except Exception as ex:
            result["probes"].append({"window":[start,end],"status":"BLOCKED_EXCEPTION","type":type(ex).__name__})
            break
    result["status"]="PASS" if len(result["probes"])==len(WINDOWS) and all(p["status"]=="PASS" for p in result["probes"]) else "BLOCKED"
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("HENGCE_FINMIND_MARKETWIDE_STATUS",result["status"],flush=True)
    return 0 if result["status"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
