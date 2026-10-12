#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, re, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

TAIPEI = timezone(timedelta(hours=8))
UNIVERSE_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
MIS_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
FUGLE_BASE = "https://api.fugle.tw/marketdata/v1.0/stock/intraday/quote/"
DEFAULT_PRIORITY = [
    "3042","2344","2357","2451","3006","2351","2368","3413","3013","3016",
    "3189","3037","4566","3550","4968","6409","6271","8031","8103","4961",
    "6415","3605","6191","1477","3041"
]
BATCH_SIZE = 40
MIS_WORKERS = 6
FUGLE_WORKERS = 6
FULL_COVERAGE = 0.98
FULL_FRESH = 0.90
QUOTE_FRESH_SECONDS = 420
TRADE_FRESH_SECONDS = 420


def now_tw() -> datetime:
    return datetime.now(TAIPEI)


def get_json(url: str, headers: dict[str,str] | None = None, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers=headers or {"User-Agent":"HENGCE-FULL-MARKET-SHADOW/1.2","Accept":"application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def fnum(x):
    if x in (None,"","-","--"):
        return None
    try:
        return float(str(x).replace(",",""))
    except Exception:
        return None


def fint(x):
    v=fnum(x)
    return int(v) if v is not None else None


def sha_obj(obj: Any) -> str:
    b=json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(b).hexdigest()


def load_universe() -> list[dict[str,str]]:
    data=get_json(UNIVERSE_URL)
    if not isinstance(data,list) or not data:
        raise RuntimeError("UNIVERSE_ENDPOINT_EMPTY")
    out=[]; seen=set()
    for row in data:
        code=str(row.get("Code") or row.get("證券代號") or "").strip()
        name=str(row.get("Name") or row.get("證券名稱") or "").strip()
        if not re.fullmatch(r"[1-9]\d{3}",code):
            continue
        if code in seen:
            raise RuntimeError(f"UNIVERSE_DUPLICATE:{code}")
        seen.add(code); out.append({"ticker":code,"name":name})
    if len(out) < 900:
        raise RuntimeError(f"UNIVERSE_TOO_SMALL:{len(out)}")
    return sorted(out,key=lambda x:x["ticker"])


def chunks(xs,n):
    for i in range(0,len(xs),n):
        yield xs[i:i+n]


def parse_mis_time(row: dict):
    raw=row.get("tlong")
    try:
        if raw not in (None,"","-"):
            ts=float(raw)
            if ts > 1e12: ts/=1000.0
            return datetime.fromtimestamp(ts,TAIPEI)
    except Exception:
        pass
    d=str(row.get("d") or "").strip(); t=str(row.get("t") or "").strip()
    try:
        if len(d)==8 and t:
            return datetime.strptime(d+" "+t,"%Y%m%d %H:%M:%S").replace(tzinfo=TAIPEI)
    except Exception:
        pass
    return None


def fetch_mis_batch(tickers: list[str]) -> dict[str,dict]:
    ex_ch="|".join(f"tse_{t}.tw" for t in tickers)
    url=MIS_URL+"?"+urllib.parse.urlencode({"ex_ch":ex_ch,"json":"1","delay":"0"})
    data=get_json(url,headers={"User-Agent":"Mozilla/5.0 HENGCE/1.2","Accept":"application/json","Referer":"https://mis.twse.com.tw/stock/index.jsp"},timeout=25)
    fetched=now_tw()
    rows=data.get("msgArray") if isinstance(data,dict) else None
    if not isinstance(rows,list):
        raise RuntimeError("MIS_MSGARRAY_MISSING")
    out={}
    for r in rows:
        t=str(r.get("c") or "").strip()
        if t not in tickers: continue
        tt=parse_mis_time(r)
        trade_age=max(0,int((fetched-tt).total_seconds())) if tt else None
        out[t]={
            "ticker":t,"name":str(r.get("n") or "").strip(),"last_price":fnum(r.get("z")),
            "reference_close":fnum(r.get("y")),"open":fnum(r.get("o")),"high":fnum(r.get("h")),"low":fnum(r.get("l")),
            "volume_lots":fint(r.get("v")),"best_bid":fnum(str(r.get("b") or "").split("_")[0]),
            "best_ask":fnum(str(r.get("a") or "").split("_")[0]),"trade_time":tt.isoformat() if tt else None,
            "trade_freshness_seconds":trade_age,"fetched_at_taipei":fetched.isoformat(),
            "source":"TWSE_MIS","fetch_ok":True,"error":None
        }
    return out


def fugle_overlay(symbol: str, api_key: str) -> dict | None:
    try:
        row=get_json(FUGLE_BASE+symbol,headers={"X-API-KEY":api_key,"Accept":"application/json","User-Agent":"HENGCE-FULL-MARKET-SHADOW/1.2"},timeout=15)
        fetched=now_tw()
        if str(row.get("symbol"))!=symbol: return None
        lt=row.get("lastTrade") or {}; total=row.get("total") or {}
        price=fnum(lt.get("price")); ref=fnum(row.get("previousClose")); tt=None
        raw=lt.get("time")
        try:
            if raw is not None:
                ts=float(raw)
                if ts>1e14: ts/=1_000_000
                elif ts>1e11: ts/=1000
                tt=datetime.fromtimestamp(ts,TAIPEI)
        except Exception: tt=None
        trade_age=max(0,int((fetched-tt).total_seconds())) if tt else None
        return {"ticker":symbol,"name":row.get("name"),"last_price":price,"reference_close":ref,"open":fnum(row.get("openPrice")),"high":fnum(row.get("highPrice")),"low":fnum(row.get("lowPrice")),"volume_lots":fint(total.get("tradeVolume")),"best_bid":fnum(((row.get("bids") or [{}])[0] or {}).get("price")),"best_ask":fnum(((row.get("asks") or [{}])[0] or {}).get("price")),"trade_time":tt.isoformat() if tt else None,"trade_freshness_seconds":trade_age,"fetched_at_taipei":fetched.isoformat(),"source":"FUGLE","fetch_ok":True,"error":None}
    except Exception:
        return None


def load_priority(path: str | None) -> list[str]:
    if path and Path(path).exists():
        try:
            obj=json.loads(Path(path).read_text(encoding="utf-8"))
            vals=obj.get("tickers") if isinstance(obj,dict) else obj
            if isinstance(vals,list):
                return [str(x) for x in vals if re.fullmatch(r"[1-9]\d{3}",str(x))]
        except Exception:
            pass
    return DEFAULT_PRIORITY[:]


def parse_iso_dt(x):
    try:
        return datetime.fromisoformat(str(x))
    except Exception:
        return None


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out",required=True); ap.add_argument("--priority-file"); args=ap.parse_args()
    started=now_tw(); universe=load_universe(); uhash=sha_obj(universe); tickers=[x["ticker"] for x in universe]; names={x["ticker"]:x["name"] for x in universe}
    records={}; batch_failures=[]; batches=list(chunks(tickers,BATCH_SIZE))

    with ThreadPoolExecutor(max_workers=MIS_WORKERS) as ex:
        futs={ex.submit(fetch_mis_batch,b): b for b in batches}
        for fut in as_completed(futs):
            batch=futs[fut]
            try:
                records.update(fut.result())
            except Exception as e:
                batch_failures.append({"tickers":batch,"error":f"{type(e).__name__}:{e}"})

    priority=[t for t in load_priority(args.priority_file) if t in names]
    api_key=os.environ.get("FUGLE_API_KEY","").strip(); fugle_success=0
    if api_key and priority:
        with ThreadPoolExecutor(max_workers=FUGLE_WORKERS) as ex:
            futs={ex.submit(fugle_overlay,t,api_key): t for t in priority}
            for fut in as_completed(futs):
                t=futs[fut]
                try:
                    q=fut.result()
                except Exception:
                    q=None
                if q:
                    records[t]=q; fugle_success+=1

    finished=now_tw(); normalized=[]
    for t in tickers:
        q=records.get(t) or {"ticker":t,"name":names[t],"last_price":None,"reference_close":None,"open":None,"high":None,"low":None,"volume_lots":None,"best_bid":None,"best_ask":None,"trade_time":None,"trade_freshness_seconds":None,"fetched_at_taipei":None,"source":"NONE","fetch_ok":False,"error":"MISSING_PROVIDER_RESULT"}
        if not q.get("name"): q["name"]=names[t]
        q["tier"]="TIER_1_EARLY" if t in priority else "TIER_3_MARKET"
        fetched_at=parse_iso_dt(q.get("fetched_at_taipei"))
        quote_age=max(0,int((finished-fetched_at).total_seconds())) if fetched_at else None
        q["quote_freshness_seconds"]=quote_age
        q["quote_fresh"]=bool(q.get("fetch_ok") and quote_age is not None and quote_age<=QUOTE_FRESH_SECONDS)
        trade_age=q.get("trade_freshness_seconds")
        q["trade_fresh"]=bool(q.get("fetch_ok") and trade_age is not None and trade_age<=TRADE_FRESH_SECONDS)
        # Backward compatibility: legacy `fresh` now explicitly means transport/quote freshness.
        q["fresh"]=q["quote_fresh"]
        q["freshness_seconds"]=quote_age
        normalized.append(q)

    provider_covered=[q for q in normalized if q.get("fetch_ok")]
    price_covered=[q for q in normalized if q.get("last_price") is not None]
    quote_fresh=[q for q in provider_covered if q.get("quote_fresh")]
    trade_fresh=[q for q in provider_covered if q.get("trade_fresh")]
    coverage=len(provider_covered)/len(normalized) if normalized else 0
    price_coverage=len(price_covered)/len(normalized) if normalized else 0
    quote_fresh_ratio=len(quote_fresh)/len(provider_covered) if provider_covered else 0
    trade_fresh_ratio=len(trade_fresh)/len(provider_covered) if provider_covered else 0
    full=coverage>=FULL_COVERAGE and quote_fresh_ratio>=FULL_FRESH
    payload={
        "schema_version":2,"service":"HENGCE_FULL_MARKET_ROLLING_SHADOW","authority":"SHADOW_CONTEXT_ONLY_NO_CAPITAL_AUTHORITY",
        "snapshot_id":finished.strftime("%Y%m%dT%H%M%S%z"),"generated_at_taipei":finished.isoformat(),"started_at_taipei":started.isoformat(),
        "collector_version":"1.2_DUAL_FRESHNESS","universe_source":UNIVERSE_URL,"universe_count":len(normalized),"universe_sha256":uhash,
        "requested_count":len(normalized),"provider_covered_count":len(provider_covered),"price_covered_count":len(price_covered),
        "fresh_count":len(quote_fresh),"quote_fresh_count":len(quote_fresh),"trade_fresh_count":len(trade_fresh),
        "coverage_ratio":coverage,"price_coverage_ratio":price_coverage,
        "fresh_ratio_of_covered":quote_fresh_ratio,"quote_fresh_ratio_of_covered":quote_fresh_ratio,"trade_fresh_ratio_of_covered":trade_fresh_ratio,
        "freshness_semantics":{"gate_basis":"QUOTE_TRANSPORT_FRESHNESS","quote_fresh_seconds":QUOTE_FRESH_SECONDS,"trade_fresh_seconds":TRADE_FRESH_SECONDS,"legacy_fresh_alias":"quote_fresh"},
        "full_market_gate":{"coverage_required":FULL_COVERAGE,"fresh_ratio_required":FULL_FRESH,"freshness_basis":"QUOTE_TRANSPORT_FRESHNESS","pass":full},
        "status":"SHADOW_FULL_MARKET_READY" if full else ("SHADOW_PARTIAL_MARKET" if coverage>=0.90 else "SHADOW_INSUFFICIENT"),
        "provider_mix":{"TWSE_MIS":sum(q.get("source")=="TWSE_MIS" for q in normalized),"FUGLE":sum(q.get("source")=="FUGLE" for q in normalized),"NONE":sum(q.get("source")=="NONE" for q in normalized)},
        "priority_tickers":priority,"fugle_priority_success":fugle_success,"batch_failures":batch_failures,"quotes":normalized
    }
    payload["payload_sha256"]=sha_obj({k:v for k,v in payload.items() if k!="payload_sha256"})
    p=Path(args.out); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:payload[k] for k in ["snapshot_id","collector_version","universe_count","coverage_ratio","price_coverage_ratio","quote_fresh_ratio_of_covered","trade_fresh_ratio_of_covered","status","provider_mix","payload_sha256"]},ensure_ascii=False,indent=2))
    if coverage < 0.90: raise SystemExit(2)

if __name__=="__main__": main()
