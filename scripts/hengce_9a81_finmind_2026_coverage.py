#!/usr/bin/env python3
"""Independent 9A81 FinMind coverage-only audit; no licensed rows are persisted."""
import datetime as dt
import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

BASE="https://api.finmindtrade.com/api/v4"
FIRST="2026-01-01"
LAST="2026-11-20"
BRANCH="9A81"
OUTPUT=pathlib.Path("research/9a81_finmind_2026_coverage_summary.json")

def query(route,params,token,retries=3):
    url=BASE+"/"+route+"?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={"Authorization":"Bearer "+token,
           "Accept":"application/json","User-Agent":"HENGCE-Research-9A81-Daily-Only/1.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req,timeout=90) as response:
                raw=response.read(50000000)
            payload=json.loads(raw.decode("utf-8-sig"))
            if not isinstance(payload,dict) or not isinstance(payload.get("data"),list):
                raise ValueError("MISSING_LIST_DATA_OR_DENIED")
            if str(payload.get("status","200")) not in ("200","0"):
                raise ValueError("NON_SUCCESS_STATUS")
            return payload["data"]
        except Exception:
            if attempt==retries-1:
                raise
            time.sleep(2**attempt)

def main():
    token=os.environ.get("FINMIND_TOKEN","").strip()
    if not token:
        raise SystemExit("ORIGINAL_REPO_FINMIND_TOKEN_NOT_AVAILABLE")
    rows=query("data",{"dataset":"TaiwanStockTradingDate","start_date":FIRST,"end_date":LAST},token)
    days=sorted({str(r.get("date",""))[:10] for r in rows if isinstance(r,dict)
                and FIRST<=str(r.get("date",""))[:10]<=LAST})
    if not days or days[0]>"2026-01-09" or days[-1]<"2026-11-19":
        raise SystemExit("TRADING_CALENDAR_ABSENT_OR_IMPLAUSIBLE")
    all_results=[]
    for i,day in enumerate(days,1):
        rec={"date":day}
        try:
            data=query("taiwan_stock_trading_daily_report",
                       {"securities_trader_id":BRANCH,"date":day},token)
            invalid=sum(1 for row in data if not isinstance(row,dict) or
                        str(row.get("securities_trader_id","")).upper()!=BRANCH or
                        str(row.get("date",""))[:10]!=day or not str(row.get("stock_id","")).strip() or
                        any(k not in row for k in ("buy","sell","price")))
            rec.update({"status":"OK" if data and invalid==0 else "INVALID_OR_EMPTY",
                        "price_rows":len(data),"distinct_stocks":len({str(x.get("stock_id")) for x in data if isinstance(x,dict)}),
                        "invalid_rows":invalid})
        except Exception as exc:
            rec.update({"status":"ERROR","error_type":type(exc).__name__})
        all_results.append(rec)
        if i%20==0:
            print("AUDIT_PROGRESS",i,"/",len(days),flush=True)
    failures=[x for x in all_results if x["status"]!="OK"]
    totals={
        "schema":"HENGCE_9A81_2026_SANITIZED_DAILY_COVERAGE_V1",
        "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "branch":BRANCH,
        "first_requested_date":FIRST,"last_requested_date":LAST,
        "calendar_trading_days":len(days),"successful_trading_days":len(days)-len(failures),
        "failed_or_empty_days":len(failures),
        "price_level_rows_total":sum(x.get("price_rows",0) for x in all_results),
        "coverage_complete":len(failures)==0,
        "exceptions":failures,
        "daily_summary":all_results,
        "raw_licensed_trades_stored":False,
        "trade_details_in_public_repository":False,
        "source":"FinMind TaiwanStockTradingDailyReport for 9A81, TaiwanStockTradingDate",
        "scope_note":"Only metadata of each trading day's response; no stock-level buy/sell or prices persisted.",
        "other_repo_private_ledger_complete":False,
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(totals,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("AUDIT_RESULT",json.dumps({k:v for k,v in totals.items() if k not in ("daily_summary","exceptions")},ensure_ascii=False))
    if failures:
        raise SystemExit("COVERAGE_INCOMPLETE: "+str(len(failures))+" days; see sanitized receipt")
if __name__=="__main__":
    main()
