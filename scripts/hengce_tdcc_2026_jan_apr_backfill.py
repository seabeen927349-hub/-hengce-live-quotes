#!/usr/bin/env python3
"""HENGCE 2026 TDCC Jan-Apr historical weekly backfill.

Blood-vessel rules:
- TWSE official MI_INDEX is the date-specific listed-stock universe.
- TDCC official historical qryStock is the only ownership source.
- Reuse the already-verified HENGCE TDCC ordinal parser.
- Preserve TWSE universe raw JSON, TDCC raw HTML ZIP, response hashes.
- Fail closed; never forward-fill, reconstruct, or use technical fallback.
"""
from __future__ import annotations
import argparse, csv, hashlib, io, json, re, threading, time, zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
import hengce_tdcc_monster_pit_backfill_runner as verified_runner

m = verified_runner.m
TZ = ZoneInfo("Asia/Taipei")
ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "ownership" / "tdcc" / "backfill_candidate" / "twse_2026_jan_apr"
TWSE_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
ALLOWED_DATES = {
    "20260102","20260109","20260116","20260123","20260130",
    "20260206","20260213","20260226",
    "20260306","20260313","20260320","20260327",
    "20260402","20260410","20260417","20260424",
}
COLS = [
    "ReferenceDate","Ticker","Name","RetrievedAtTaipei",
    "Big400Holders","Big400Shares","Big400Pct",
    "Big1000Holders","Big1000Shares","Big1000Pct",
    "TotalHolders","TotalShares","ResponseSHA256","Source","PITAuthority"
]
_TLS = threading.local()

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def now_tw() -> str:
    return datetime.now(TZ).replace(microsecond=0).isoformat()

def fetch_twse_universe(ref: str):
    r=requests.get(TWSE_URL, params={"date":ref,"type":"ALLBUT0999","response":"json"},
                   timeout=60, headers={"User-Agent":"Mozilla/5.0 HENGCE-TWSE-UNIVERSE/1.0"})
    r.raise_for_status()
    raw=r.content
    obj=r.json()
    if obj.get("stat") not in (None,"OK"):
        raise RuntimeError(f"TWSE_UNIVERSE_STAT:{obj.get('stat')}")
    found={}
    for t in obj.get("tables",[]):
        fields=[str(x).strip() for x in t.get("fields",[])]
        if "證券代號" not in fields or "證券名稱" not in fields:
            continue
        ci=fields.index("證券代號"); ni=fields.index("證券名稱")
        for row in t.get("data",[]):
            if len(row)<=max(ci,ni): continue
            ticker=str(row[ci]).strip()
            name=str(row[ni]).strip()
            if re.fullmatch(r"[1-9]\d{3}",ticker):
                found[ticker]=name
    rows=[{"Ticker":k,"Name":found[k]} for k in sorted(found)]
    if len(rows)<900:
        raise RuntimeError(f"TWSE_UNIVERSE_TOO_SMALL:{ref}:{len(rows)}")
    return raw, rows

def write_csv(path: Path, rows: list[dict], cols: list[str]):
    s=io.StringIO(newline="")
    w=csv.DictWriter(s,fieldnames=cols,lineterminator="\n")
    w.writeheader()
    for r in rows: w.writerow({c:r.get(c,"") for c in cols})
    path.write_text(s.getvalue(),encoding="utf-8")

def worker_session():
    s=getattr(_TLS,"session",None)
    if s is None:
        s=requests.Session()
        s.headers.update({
            "User-Agent":"Mozilla/5.0 HENGCE-TDCC-2026-BACKFILL/1.1",
            "Referer":m.ENDPOINT,
            "Accept-Language":"zh-TW,zh;q=0.9,en;q=0.5",
        })
        _TLS.session=s
    return s

def fetch_security(ref: str, ticker: str, name: str, retrieved: str):
    try:
        raw, text, sm=m.fetch_one(worker_session(),ticker,ref)
        row={
            "ReferenceDate":ref,"Ticker":ticker,"Name":name,
            "RetrievedAtTaipei":retrieved,
            "Big400Holders":sm["Big400Holders"],"Big400Shares":sm["Big400Shares"],
            "Big400Pct":sm["Big400Pct"],"Big1000Holders":sm["Big1000Holders"],
            "Big1000Shares":sm["Big1000Shares"],"Big1000Pct":sm["Big1000Pct"],
            "TotalHolders":sm["TotalHolders"],"TotalShares":sm["TotalShares"],
            "ResponseSHA256":sha256_bytes(raw),"Source":m.ENDPOINT,
            "PITAuthority":"HISTORICAL_PIT_PROXY_RESEARCH_ONLY",
        }
        time.sleep(0.05)
        return True,row,raw
    except Exception as e:
        return False,{"ReferenceDate":ref,"Ticker":ticker,"Name":name,
                      "error":f"{type(e).__name__}:{e}"},None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--date",required=True)
    ap.add_argument("--workers",type=int,default=4)
    args=ap.parse_args()
    ref=args.date.replace("-","")
    if ref not in ALLOWED_DATES:
        raise SystemExit(f"DATE_NOT_IN_FROZEN_2026_GAP_SET:{ref}")
    if not 1 <= args.workers <= 8:
        raise SystemExit(f"WORKERS_OUT_OF_RANGE:{args.workers}")
    out=OUT_ROOT/ref
    out.mkdir(parents=True,exist_ok=True)
    retrieved=now_tw()

    universe_raw, universe=fetch_twse_universe(ref)
    (out/"twse_universe_raw.json").write_bytes(universe_raw)
    write_csv(out/"twse_universe.csv",universe,["Ticker","Name"])

    rows=[]; invalid=[]; completed=0
    zpath=out/"raw_html.zip"
    with zipfile.ZipFile(zpath,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        with ThreadPoolExecutor(max_workers=args.workers,thread_name_prefix=f"tdcc-{ref}") as ex:
            futures={ex.submit(fetch_security,ref,r["Ticker"],r["Name"],retrieved):(r["Ticker"],r["Name"]) for r in universe}
            for fut in as_completed(futures):
                ticker,name=futures[fut]
                try:
                    ok,payload,raw=fut.result()
                except Exception as e:
                    ok=False; raw=None
                    payload={"ReferenceDate":ref,"Ticker":ticker,"Name":name,
                             "error":f"FUTURE_{type(e).__name__}:{e}"}
                completed+=1
                if ok:
                    rows.append(payload)
                    z.writestr(f"{ticker}.html",raw)
                else:
                    invalid.append(payload)
                if completed==1 or completed%100==0 or completed==len(universe):
                    print(f"[{ref}] {completed}/{len(universe)} valid={len(rows)} invalid={len(invalid)}",flush=True)

    rows.sort(key=lambda x:x["Ticker"])
    invalid.sort(key=lambda x:x["Ticker"])
    cpath=out/"tdcc_ownership_4d.csv"
    write_csv(cpath,rows,COLS)
    (out/"invalid.json").write_text(json.dumps(invalid,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    status="COMPLETE" if len(rows)==len(universe) and not invalid else "PARTIAL_FAIL_CLOSED"
    manifest={
        "system":"HENGCE","artifact":"TDCC_2026_JAN_APR_WEEKLY_BACKFILL_DATE",
        "status":status,"reference_date":ref,
        "universe_source":"TWSE official MI_INDEX through HENGCE source family",
        "universe_rows":len(universe),
        "universe_sha256":sha256_bytes((out/"twse_universe.csv").read_bytes()),
        "universe_raw_sha256":sha256_bytes(universe_raw),
        "valid_rows":len(rows),"invalid_rows":len(invalid),
        "retrieved_at_taipei":retrieved,"query_workers":args.workers,
        "source":"TDCC official historical qryStock endpoint",
        "parser":"existing verified HENGCE ordinal parser",
        "summary_sha256":sha256_bytes(cpath.read_bytes()),
        "raw_html_zip_sha256":sha256_bytes(zpath.read_bytes()),
        "raw_html_zip_bytes":zpath.stat().st_size,
        "authority":"RESEARCH_BACKFILL_CANDIDATE_NO_CANONICAL_AUTHORITY",
        "pit_authority":"HISTORICAL_PIT_PROXY_RESEARCH_ONLY",
        "no_forward_fill":True,"no_reconstruction":True,
        "technical_fallback":"PROHIBITED",
    }
    (out/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(manifest,ensure_ascii=False))
    if status!="COMPLETE":
        raise SystemExit(2)

if __name__=="__main__":
    main()
