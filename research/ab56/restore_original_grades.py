#!/usr/bin/env python3
"""Read archived official TDCC raw HTML for the AB56 study; research branch only."""
import csv, datetime as dt, hashlib, io, json, os, re, sys, time, zipfile
from pathlib import Path
import pandas as pd
import requests

BRANCH="research/ab56-grade-recovery-20261117"
WEEKS={
"20251212":("1303 1802 2308 2360 3711","22134e535fafcb3b7489d8a00cdd162be400a01a"),
"20251219":("1303 1802 2308 2330 2360 2449 3711 8046","0acce34e9368c9fccd69390d059c01ca64882774"),
"20251226":("1303 1802 2308 2330 2360 2383 2449 2454 3711 8046","46d10163c21816ce8a4e7b5b3876af9ffeedd3e5"),
"20260102":("2330 2383 2449 2454 3044 6271 8046 8210","14efbb7a157793fe31c953a0acc10d3c827a5027"),
"20260109":("2383 2454 3044 6271 8210","1a3862e31931235afd75a69757042ac4861b1012"),
"20260116":("3044 6271 8210","039d04de1f438d8fca002831d7ff54029e29974b"),
"20260206":("2059 2603 6213","81f5b4de694e98ee2508a9460d6655385f59808d"),
"20260213":("2059 2603 6213","a7f41ab631c6e117168a5c58d27ac5f5c6152853"),
"20260226":("2059 2603 6213","73f1f8501e716e2a4a59d9bf05e197af7a523923"),
"20260306":("1303 8046","f48b8f89860319edcd4216ba3fbdaade54a406aa"),
"20260313":("1303 8046","b3000526d4335437445d013157d1aee00cda387d"),
"20260320":("1303 2049 2301 2317 2327 2345 2382 8046 8210","cc25a131d6de80d05a5992cedb31d69da74e46bd"),
"20260327":("2049 2301 2317 2327 2345 2360 2382 2408 2882 8210","82a37c8a7982d78bbda8126addb2b76e190cd1cf"),
"20260402":("2049 2301 2303 2317 2327 2345 2360 2382 2408 2882 8210","b6fc52b5bd1ecad827b2316da44f3b43877d4c42"),
"20260410":("2303 2327 2360 2408 2882","d40e8527205db5bb06c63c161714a99069705819"),
"20260417":("2303 2327","0f7c8e4cb8db11c1c01b9b7d9a7ae31304bac2e1"),
"20260424":("2344","7c06b76d30a6e81623b11ad99d23f10b16565286")
}
BASE="https://raw.githubusercontent.com/seabeen927349-hub/-hengce-live-quotes/main/ownership/tdcc/backfill_candidate"
OUT=Path(__file__).resolve().parent/"artifacts"
OUT.mkdir(parents=True,exist_ok=True)

def parse_num(x):
    s=str(x).replace(",","").replace(" ","").strip()
    if re.fullmatch(r"\d+(?:\.0)?",s):return int(float(s))
    raise ValueError("Noninteger shares "+repr(x))

def decode(b):
    for enc in ("utf-8-sig","utf-8","cp950","big5"):
        try:return b.decode(enc)
        except UnicodeDecodeError:pass
    raise ValueError("HTML encoding")

def flatten(c):
    if isinstance(c,tuple):return " ".join(str(z).strip() for z in c if str(z).strip() and str(z)!="nan")
    return str(c).strip()

def parse_grades(raw):
    frames=pd.read_html(io.StringIO(decode(raw)))
    for frame in frames:
        frame=frame.copy();frame.columns=[flatten(x) for x in frame.columns]
        cs=list(frame.columns)
        ordinal=next((x for x in cs if x.strip()=="序"),None)
        shares=next((x for x in cs if ("股數" in x or "單位數" in x) and not ("比例" in x or "分級" in x)),None)
        category=next((x for x in cs if ("持股" in x or "分級" in x) and x!=shares),None)
        if not (ordinal and shares and category):continue
        grades={};total=None
        for _,r in frame.iterrows():
            token=str(r[ordinal]).strip(); cat=str(r[category]).strip()
            label=cat.replace(" ","").replace("\u3000","")
            if "合計" in label or "總計" in label or "合計" in token or "總計" in token:
                if total is not None:raise ValueError("duplicate total row")
                total=parse_num(r[shares])
                continue
            m=re.fullmatch(r"(\d{1,2})(?:\.0)?",token)
            if m:
                g=int(m.group(1))
                if not 1<=g<=15:continue # grade16 adjustment can be signed; never include
                if g in grades:raise ValueError("duplicate grade "+str(g))
                grades[g]=parse_num(r[shares])
        if total is None:total=grades.get(17)
        if not set(range(1,16)).issubset(grades) or not total:continue
        if not 0<=sum(grades[g] for g in (1,2,3))<=total:raise ValueError("invalid small share count")
        return grades,total
    raise ValueError("Official 15-grade + total table not matched")

def gitsha(b):
    return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()

def get(session,url):
    for i in range(4):
        try:
            r=session.get(url,timeout=(30,180));r.raise_for_status()
            return r.content
        except Exception:
            if i==3:raise
            time.sleep((i+1)*3)

def main():
    s=requests.Session();s.headers["User-Agent"]="HENGCE-AB56-RAW-ARCHIVE-READONLY/1.0"
    records=[];errors=[];checks=[]
    for i,(date,(strtickers,expected_sha)) in enumerate(WEEKS.items(),1):
        group="full_market_2025_tail" if date.startswith("2025") else "full_market_2026_jan_apr"
        folder=f"{BASE}/{group}/{date}"
        tickers=strtickers.split()
        print(f"BEGIN_WEEK {i}/17 {date} tickers={len(tickers)}",flush=True)
        try:
            raw=get(s,folder+"/raw_html.zip")
            observed=gitsha(raw)
            if observed!=expected_sha:raise ValueError(f"ZIP_SHA1_MISMATCH {observed} expected {expected_sha}")
            summarytext=decode(get(s,folder+"/tdcc_ownership_4d.csv"))
            summary={r["Ticker"]:r for r in csv.DictReader(io.StringIO(summarytext))}
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                for ticker in tickers:
                    try:
                        path=f"valid/{ticker}.html"
                        body=z.read(path)
                        if date=="20251212" and ticker=="2308":
                            frames=pd.read_html(io.StringIO(decode(body)))
                            probe=[]
                            for fi,frame in enumerate(frames[:8]):
                                probe.append({"table":fi,"columns":[str(c) for c in frame.columns],"all_rows":frame.astype(str).values.tolist()})
                            (OUT/"AB56_FAILED_2308_TABLE_DIAGNOSTIC.json").write_text(json.dumps(probe,ensure_ascii=False,indent=2),encoding="utf-8")
                        if date=="20251212" and ticker=="1303":
                            probe=[]
                            frames=pd.read_html(io.StringIO(decode(body)))
                            for fi,frame in enumerate(frames[:8]):
                                probe.append({"table":fi,"columns":[str(c) for c in frame.columns],"first_rows":frame.head(5).astype(str).values.tolist(),"last_rows":frame.tail(3).astype(str).values.tolist()})
                            (OUT/"AB56_HTML_TABLE_DIAGNOSTIC.json").write_text(json.dumps(probe,ensure_ascii=False,indent=2),encoding="utf-8")
                        g,total=parse_grades(body)
                        old=summary.get(ticker)
                        if not old:raise ValueError("No summary row")
                        expected_raw=old["RawSHA256"]
                        if hashlib.sha256(body).hexdigest()!=expected_raw:raise ValueError("HTML_SHA256_MISMATCH")
                        b400=sum(g[k] for k in (12,13,14,15))
                        if b400!=int(float(old["Big400Shares"])):raise ValueError(f"BIG400_MISMATCH {b400}!={old['Big400Shares']}")
                        rec={"SnapshotDate":date,"Ticker":ticker,
                        "Grade1Shares":g[1],"Grade2Shares":g[2],"Grade3Shares":g[3],
                        "Grade17TotalShares":total,"RawSHA256":expected_raw,
                        "SourceZIPGitSHA1":observed,"SourceMember":path,
                        "SourceKind":"TDCC_HISTORICAL_OFFICIAL_HTML_ZIP"}
                        records.append(rec)
                    except Exception as e:
                        errors.append({"date":date,"ticker":ticker,"reason":str(e)})
                        print(f"ERROR_ROW {date} {ticker} {type(e).__name__} {e}",flush=True)
            checks.append({"date":date,"observed_git_blob_sha1":observed,"archive_bytes":len(raw),"verified_stock_count":sum(x["SnapshotDate"]==date for x in records)})
        except Exception as e:
            errors.append({"date":date,"ticker":"ALL","reason":str(e)})
            print(f"ERROR_WEEK {date} {type(e).__name__} {e}",flush=True)
        print(f"END_WEEK {date} total_verified={len(records)} total_errors={len(errors)}",flush=True)
    columns=["SnapshotDate","Ticker","Grade1Shares","Grade2Shares","Grade3Shares","Grade17TotalShares","RawSHA256","SourceZIPGitSHA1","SourceMember","SourceKind"]
    dst=OUT/"HENGCE_AB56_RECOVERED_GRADE1_2_3_17.csv"
    with dst.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(records)
    receipt={"status":"COMPLETE" if len(records)==90 and not errors else "INCOMPLETE",
      "expected_unique_stock_weeks":90,"verified_unique_stock_weeks":len(records),
      "source_archive_weeks":17,"source_check_results":checks,"row_errors":errors,
      "csv_sha256":hashlib.sha256(dst.read_bytes()).hexdigest(),
      "no_production_changes":True,"pit":"retrospective_week_end_plus_14_days_proxy"}
    (OUT/"HENGCE_AB56_RECOVERY_RECEIPT.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("RECOVERY_SUMMARY "+json.dumps({k:v for k,v in receipt.items() if k not in ("source_check_results","row_errors")},ensure_ascii=False),flush=True)
    if errors:print("ERRORS "+json.dumps(errors,ensure_ascii=False),flush=True)
    if len(records)!=90 or errors:sys.exit(2)

if __name__=="__main__":main()
