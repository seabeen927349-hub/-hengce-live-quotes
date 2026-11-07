#!/usr/bin/env python3
"""HENGCE research-only FinMind TDCC weekly Big400/Big1000 panel 2018–2025.

Input: eight verified annual FinMind research artifact archives.
Original vendor snapshots are retained independently (not committed to public Git).
Only standard 15 holder-size tiers count. Accounting adjustments / total excluded.
No date-forward-fill, no historical publish-timestamp invention, no trade authority.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,re,collections
from pathlib import Path
from datetime import datetime,timezone

FIELDS=("SnapshotDate","Ticker","Big400Pct","Big1000Pct",
        "Big400Shares","Big1000Shares","Big400Holders","Big1000Holders",
        "TierSchema","Provenance")
PAT=re.compile(r"^[1-9]\d{3}$")
EXPECTED_YEARS=tuple(range(2018,2026))
KNOWN_SOURCE="FINMIND_HISTORICAL_TDCC_RETROSPECTIVE_UNVALIDATED_PUBLICATION_TIME"

def h(data):return hashlib.sha256(data).hexdigest()

def lower_bound(value):
    s=re.sub(r"[,，\s股]","",str(value)).replace("～","-").replace("~","-").lower()
    if "差異數調整" in s or "合計" in s or "總計" in s or s=="total":return None
    m=re.match(r"^morethan(\d+)$",s)
    if m:return int(m.group(1))
    m=re.match(r"^(\d+)(?:-|以上|及以上|\+)",s)
    return int(m.group(1)) if m else None

def compile_one_snapshot(rows,expected_date):
    byticker=collections.defaultdict(list)
    bad_records=0
    for r in rows:
        if r.get("date")!=expected_date:raise ValueError("CROSS_DATE_SOURCE_RESPONSE")
        ticker=str(r.get("stock_id","")).strip()
        if PAT.fullmatch(ticker):byticker[ticker].append(r)
    out=[];failed=[]
    for ticker,rec in byticker.items():
        high=[];top=[];numeric_bad=False;levels=[]
        for r in rec:
            name=str(r.get("HoldingSharesLevel",""))
            lb=lower_bound(name)
            if lb is None:continue
            try:
                pct=float(r["percent"]);shares=int(r["unit"]);holders=int(r["people"])
            except (ValueError,TypeError,KeyError):
                numeric_bad=True;continue
            if not(0<=pct<=100 and shares>=0 and holders>=0):
                numeric_bad=True;continue
            levels.append(name)
            if lb>=400001:high.append((pct,shares,holders))
            if lb>=1000001:top.append((pct,shares,holders))
        good=not numeric_bad and len(high)==4 and len(top)==1
        if good:
            p400=round(sum(x[0] for x in high),6)
            p1000=round(sum(x[0] for x in top),6)
            v400=sum(x[1] for x in high)
            v1000=sum(x[1] for x in top)
            n400=sum(x[2] for x in high)
            n1000=sum(x[2] for x in top)
            if p400>100.01 or p1000>p400+.01 or v1000>v400 or n400<0:good=False
        if good:
            out.append((expected_date.replace("-",""),ticker,
                        f"{p400:.6f}",f"{p1000:.6f}",v400,v1000,n400,n1000,
                        "VALID_4_HIGH_1_TOP",KNOWN_SOURCE))
        else:
            out.append((expected_date.replace("-",""),ticker,
                        "","","","","","","MISSING_OR_INVALID_TIER",KNOWN_SOURCE))
            failed.append(ticker)
    return out,failed

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--input-root",required=True)
    ap.add_argument("--out",required=True)
    a=ap.parse_args()
    root=Path(a.input_root);dest=Path(a.out);dest.mkdir(parents=True,exist_ok=True)
    receipt={
        "system":"HENGCE","schema":"HENGCE_FINMIND_TDCC_RESEARCH_BIG400_BIG1000_2018_2025",
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "status":"PENDING",
        "research_only":True,"production_mutated":False,"model_or_trade_authority":False,
        "source_years":list(EXPECTED_YEARS),
        "source":"TaiwanStockHoldingSharesPer / FINMIND_TOKEN",
        "source_first_observed_not_equivalent_to_historical_pit_published":True,
        "no_daily_forward_fill":True,"no_vendor_source_rewriting":True,
        "ordinary_stock_identity_pit_validated":False,
        "source_originals":"separate verified annual private Library archives",
        "years":{},
    }
    dst=dest/"HENGCE_TDCC_BIG400_BIG1000_RESEARCH_2018_2025.csv.gz"
    try:
        total_rows=valid=bad=raw_total=0
        with gzip.open(dst,"wt",encoding="utf-8",newline="",compresslevel=6) as f:
            writer=csv.writer(f,lineterminator="\n")
            writer.writerow(FIELDS)
            for year in EXPECTED_YEARS:
                folder=root/str(year)
                mf=folder/"manifest.json"
                if not mf.exists():raise RuntimeError(f"MISSING_YEAR_MANIFEST_{year}")
                m=json.loads(mf.read_text(encoding="utf-8"))
                if m.get("status")!="PASS" or int(m.get("year"))!=year:
                    raise RuntimeError(f"UNVERIFIED_SOURCE_YEAR_{year}")
                srcs=m.get("snapshots",[])
                if len(srcs)<40 or len(srcs)!=m.get("snapshots_completed"):
                    raise RuntimeError(f"YEAR_NOT_ALL_WEEKS_{year}_{len(srcs)}")
                dates=[x["reference_date"] for x in srcs]
                if dates!=sorted(set(dates)) or any(not d.startswith(str(year)+"-") for d in dates):
                    raise RuntimeError(f"YEAR_DATE_DUPLICATE_OR_BAD_{year}")
                yr_count=yr_valid=yr_bad=yr_raw=0
                missing_samples=[]
                for snap in srcs:
                    path=folder/snap["file"]
                    blob=path.read_bytes()
                    if h(blob)!=snap["gzip_sha256"]:
                        raise RuntimeError(f"SOURCE_SHA_MISMATCH_{year}_{snap['reference_date']}")
                    raw=gzip.decompress(blob)
                    if h(raw)!=snap["normalized_json_sha256"]:
                        raise RuntimeError(f"SOURCE_JSON_SHA_MISMATCH_{year}_{snap['reference_date']}")
                    rows=json.loads(raw)
                    if not isinstance(rows,list) or len(rows)!=snap["tier_rows"]:
                        raise RuntimeError(f"SOURCE_ROWS_MISMATCH_{year}_{snap['reference_date']}")
                    compiled,invalid=compile_one_snapshot(rows,snap["reference_date"])
                    writer.writerows(compiled)
                    n=len(compiled)
                    yr_count+=n
                    yr_bad+=len(invalid)
                    yr_valid+=n-len(invalid)
                    yr_raw+=len(rows)
                    missing_samples.extend([{"date":snap["reference_date"],"ticker":t} for t in invalid[:max(0,10-len(missing_samples))]])
                receipt["years"][str(year)]={
                    "source_weekly_snapshots":len(srcs),
                    "source_tier_rows":yr_raw,
                    "four_digit_stock_week_rows":yr_count,
                    "derived_400_1000_valid_stock_weeks":yr_valid,
                    "invalid_or_missing_tiers":yr_bad,
                    "invalid_examples":missing_samples[:10],
                }
                total_rows+=yr_count
                valid+=yr_valid
                bad+=yr_bad
                raw_total+=yr_raw
                print("HENGCE_TDCC_PANEL_YEAR",year,"weeks",len(srcs),"stockweeks",yr_count,
                    "tier_valid",yr_valid,"tier_invalid",yr_bad,flush=True)
        receipt["status"]="PASS" if valid>200000 and bad/total_rows<.05 else "INSUFFICIENT_QUALITY_FAIL_CLOSED"
        receipt["total_4digit_stock_week_rows"]=total_rows
        receipt["total_valid_derived_rows"]=valid
        receipt["total_invalid_rows"]=bad
        receipt["total_raw_vendor_tier_rows"]=raw_total
        receipt["output_file"]=dst.name
        receipt["output_file_sha256"]=h(dst.read_bytes())
    except Exception as e:
        receipt["status"]="BLOCKED_FAIL_CLOSED"
        receipt["blocker"]=f"{type(e).__name__}:{str(e)[:200]}"
    finally:
        (dest/"HENGCE_TDCC_RESEARCH_PANEL_AUDIT.json").write_text(
            json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("HENGCE_TDCC_PANEL_STATUS",receipt["status"],
              "derived",receipt.get("total_valid_derived_rows",0),flush=True)
    return 0 if receipt["status"]=="PASS" else 2

if __name__=="__main__":raise SystemExit(main())
