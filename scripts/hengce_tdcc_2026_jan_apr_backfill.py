#!/usr/bin/env python3
"""HENGCE full-market TDCC historical weekly backfill for 2026 Jan-Apr.

Governance:
- Candidate universe is the frozen 3,091 four-digit ticker union already observed
  in the validated HENGCE TDCC historical mother.
- Ownership source is ONLY the official TDCC historical stock/date endpoint.
- A fresh SYNCHRONIZER_TOKEN is obtained for EVERY query; token reuse is forbidden
  because the HENGCE probe proved reuse creates false NO_DATA responses.
- Explicit TDCC '查無此資料' resolves that candidate as absent for that snapshot.
- Network/HTTP/parser/grade errors are invalid and fail the whole snapshot closed.
- Raw HTML and SHA-256 are preserved for both valid and explicit-NO_DATA queries.
- No ownership forward-fill, reconstruction, alternate source, or technical fallback.
"""
from __future__ import annotations
import argparse, csv, hashlib, io, json, threading, time, zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
import hengce_tdcc_monster_pit_backfill_runner as verified_runner

m = verified_runner.m
TZ = ZoneInfo("Asia/Taipei")
ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "ownership" / "tdcc" / "backfill_candidate" / "full_market_2026_jan_apr"
CANDIDATE_FILE = ROOT / "research" / "tdcc" / "tdcc_historical_candidate_universe_3091_20261029.csv"
CANDIDATE_SHA256 = "70229d9b1bcef321deaad73b96fcb65c84227e30d173cd0b20a7e7e524a52936"
CANDIDATE_SOURCE_SHA256_GZIP = "d10a3576e09f42041135dae3884f59c73e555c05ce23e524131feee94f1e8b8f"
ALLOWED_DATES = {
    "20260102","20260109","20260116","20260123","20260130",
    "20260206","20260213","20260226",
    "20260306","20260313","20260320","20260327",
    "20260402","20260410","20260417","20260424",
}
COLS = [
    "SnapshotDate","Ticker","Big400Pct","Big1000Pct",
    "Big400Holders","Big400Shares","Big1000Holders","Big1000Shares",
    "TotalHolders","TotalShares","SourceTier","SourcePath","RawSHA256","ConflictFlag"
]
NO_DATA_COLS = ["SnapshotDate","Ticker","RawSHA256","SourcePath","Resolution"]
_TLS = threading.local()

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def now_tw() -> str:
    return datetime.now(TZ).replace(microsecond=0).isoformat()

def write_csv(path: Path, rows: list[dict], cols: list[str]):
    s=io.StringIO(newline="")
    w=csv.DictWriter(s,fieldnames=cols,lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c:r.get(c,"") for c in cols})
    path.write_text(s.getvalue(),encoding="utf-8")

def load_candidates() -> list[str]:
    if not CANDIDATE_FILE.exists():
        raise RuntimeError(f"CANDIDATE_FILE_MISSING:{CANDIDATE_FILE}")
    raw=CANDIDATE_FILE.read_bytes()
    if sha256_bytes(raw)!=CANDIDATE_SHA256:
        raise RuntimeError(f"CANDIDATE_SHA_MISMATCH:{sha256_bytes(raw)}")
    rows=list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    tickers=[str(r.get("Ticker","")).strip() for r in rows]
    if len(tickers)!=3091 or len(set(tickers))!=3091:
        raise RuntimeError(f"CANDIDATE_COUNT_CHANGED:{len(tickers)}:{len(set(tickers))}")
    if any(len(t)!=4 or not t.isdigit() for t in tickers):
        raise RuntimeError("CANDIDATE_BAD_TICKER_FORMAT")
    return sorted(tickers)

def worker_session() -> requests.Session:
    s=getattr(_TLS,"session",None)
    if s is None:
        s=requests.Session()
        s.headers.update({
            "User-Agent":"Mozilla/5.0 HENGCE-TDCC-2026-FULL-MARKET-BACKFILL/1.0",
            "Referer":m.ENDPOINT,
            "Accept-Language":"zh-TW,zh;q=0.9,en;q=0.5",
        })
        _TLS.session=s
    return s

def fetch_classified(ref: str, ticker: str):
    session=worker_session()
    last_err=None
    for attempt in range(1,4):
        try:
            token=m.get_token(session)  # FRESH token for every attempt/query; NEVER reuse.
            data={
                "SYNCHRONIZER_TOKEN":token,
                "SYNCHRONIZER_URI":"/portal/zh/smWeb/qryStock",
                "method":"submit",
                "firDate":ref,
                "scaDate":ref,
                "sqlMethod":"StockNo",
                "stockNo":ticker,
                "stockName":"",
            }
            r=session.post(m.ENDPOINT,data=data,timeout=60,verify=False)
            r.raise_for_status()
            raw=r.content
            raw_sha=sha256_bytes(raw)
            if "查無此資料" in r.text:
                return "NO_DATA",{
                    "SnapshotDate":ref,"Ticker":ticker,"RawSHA256":raw_sha,
                    "SourcePath":m.ENDPOINT,
                    "Resolution":"TDCC_EXPLICIT_NO_DATA_NOT_PRESENT_FOR_REFERENCE_DATE",
                },raw
            table=m.find_data_table(r.text)[0]
            sm=m.summarize_table(table)
            row={
                "SnapshotDate":ref,"Ticker":ticker,
                "Big400Pct":sm["Big400Pct"],"Big1000Pct":sm["Big1000Pct"],
                "Big400Holders":sm["Big400Holders"],"Big400Shares":sm["Big400Shares"],
                "Big1000Holders":sm["Big1000Holders"],"Big1000Shares":sm["Big1000Shares"],
                "TotalHolders":sm["TotalHolders"],"TotalShares":sm["TotalShares"],
                "SourceTier":"TDCC_HISTORICAL_OFFICIAL_QUERY",
                "SourcePath":m.ENDPOINT,
                "RawSHA256":raw_sha,"ConflictFlag":"",
            }
            return "VALID",row,raw
        except Exception as e:
            last_err=e
            if attempt<3:
                time.sleep(1.2*attempt)
    return "INVALID",{
        "SnapshotDate":ref,"Ticker":ticker,
        "error":f"{type(last_err).__name__}:{last_err}",
    },None

def main():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    ap=argparse.ArgumentParser()
    ap.add_argument("--date",required=True)
    ap.add_argument("--workers",type=int,default=4)
    args=ap.parse_args()
    ref=args.date.replace("-","")
    if ref not in ALLOWED_DATES:
        raise SystemExit(f"DATE_NOT_IN_FROZEN_2026_GAP_SET:{ref}")
    if not 1 <= args.workers <= 8:
        raise SystemExit(f"WORKERS_OUT_OF_RANGE:{args.workers}")
    candidates=load_candidates()
    out=OUT_ROOT/ref
    out.mkdir(parents=True,exist_ok=True)
    retrieved=now_tw()

    valid=[]; no_data=[]; invalid=[]; completed=0
    zpath=out/"raw_html.zip"
    with zipfile.ZipFile(zpath,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        with ThreadPoolExecutor(max_workers=args.workers,thread_name_prefix=f"tdcc-{ref}") as ex:
            futures={ex.submit(fetch_classified,ref,t):t for t in candidates}
            for fut in as_completed(futures):
                ticker=futures[fut]
                try:
                    state,payload,raw=fut.result()
                except Exception as e:
                    state="INVALID"; raw=None
                    payload={"SnapshotDate":ref,"Ticker":ticker,"error":f"FUTURE_{type(e).__name__}:{e}"}
                completed+=1
                if state=="VALID":
                    valid.append(payload)
                    z.writestr(f"valid/{ticker}.html",raw)
                elif state=="NO_DATA":
                    no_data.append(payload)
                    z.writestr(f"no_data/{ticker}.html",raw)
                else:
                    invalid.append(payload)
                if completed==1 or completed%100==0 or completed==len(candidates):
                    print(
                        f"[{ref}] {completed}/{len(candidates)} valid={len(valid)} "
                        f"no_data={len(no_data)} invalid={len(invalid)}",flush=True
                    )

    valid.sort(key=lambda x:x["Ticker"])
    no_data.sort(key=lambda x:x["Ticker"])
    invalid.sort(key=lambda x:x["Ticker"])
    summary_path=out/"tdcc_ownership_4d.csv"
    no_data_path=out/"explicit_no_data.csv"
    invalid_path=out/"invalid.json"
    write_csv(summary_path,valid,COLS)
    write_csv(no_data_path,no_data,NO_DATA_COLS)
    invalid_path.write_text(json.dumps(invalid,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    resolved=len(valid)+len(no_data)
    status="COMPLETE" if resolved==len(candidates) and not invalid else "PARTIAL_FAIL_CLOSED"
    manifest={
        "system":"HENGCE",
        "artifact":"TDCC_2026_JAN_APR_FULL_MARKET_WEEKLY_BACKFILL_DATE",
        "status":status,
        "reference_date":ref,
        "candidate_universe":"HENGCE_TDCC_HISTORICAL_UNION_3091",
        "candidate_rows":len(candidates),
        "candidate_csv_sha256":CANDIDATE_SHA256,
        "candidate_parent_gzip_sha256":CANDIDATE_SOURCE_SHA256_GZIP,
        "valid_rows":len(valid),
        "explicit_no_data_rows":len(no_data),
        "resolved_candidates":resolved,
        "invalid_rows":len(invalid),
        "retrieved_at_taipei":retrieved,
        "query_workers":args.workers,
        "fresh_token_per_query":True,
        "token_reuse":"PROHIBITED_BY_VERIFIED_HENGCE_PROBE_FALSE_NO_DATA_RISK",
        "source":"TDCC official historical qryStock endpoint",
        "parser":"existing verified HENGCE ordinal parser",
        "summary_sha256":sha256_bytes(summary_path.read_bytes()),
        "explicit_no_data_sha256":sha256_bytes(no_data_path.read_bytes()),
        "raw_html_zip_sha256":sha256_bytes(zpath.read_bytes()),
        "raw_html_zip_bytes":zpath.stat().st_size,
        "authority":"RESEARCH_BACKFILL_CANDIDATE_NO_CANONICAL_AUTHORITY",
        "pit_authority":"HISTORICAL_PIT_PROXY_RESEARCH_ONLY",
        "no_forward_fill":True,
        "no_reconstruction":True,
        "technical_fallback":"PROHIBITED",
    }
    (out/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(manifest,ensure_ascii=False))
    if status!="COMPLETE":
        raise SystemExit(2)

if __name__=="__main__":
    main()
