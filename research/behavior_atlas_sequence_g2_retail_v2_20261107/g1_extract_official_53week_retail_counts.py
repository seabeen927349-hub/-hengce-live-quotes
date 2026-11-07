#!/usr/bin/env python3
"""G1 raw 15-grade TDCC 'people' extraction from *existing* HENGCE official-source archives.

Read-only source QC. 6 bounded date shards on GH Actions. No behavior discovery,
no price/returns, no individual investor IDs. Never infer a missing grade by a complement.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,io,json,re,sys,time,urllib.error,urllib.request,zipfile
from collections import Counter,defaultdict
from pathlib import Path
from bs4 import BeautifulSoup

BASE="https://raw.githubusercontent.com/seabeen927349-hub/-hengce-live-quotes/main/"
DATE={
 "2025A":["20251031","20251107","20251114","20251121","20251128"],
 "2025B":["20251205","20251212","20251219","20251226"],
 "2026A":["20260102","20260109","20260116","20260123","20260130"],
 "2026B":["20260206","20260213","20260226","20260306","20260313"],
 "2026C":["20260320","20260327","20260402","20260410","20260417","20260424"],
 "2026D":["20260430","20260508","20260515","20260522","20260529","20260605","20260612","20260618","20260626","20260703","20260709","20260717","20260724","20260731","20260807","20260814","20260821","20260828","20260904","20260911","20260918","20260924","20261002","20261008","20261016","20261022","20261030","20261106"]
}
HEADER=["SnapshotDate","Ticker","HolderLe10Lots","Holder10To50Lots","OddLotHolders","HolderLe50Lots","HoldersFull15Sum","HoldersReportedTotal","PeopleTotalMatches","ValidPeople15","InvalidReason","RawSourceKind","RawSourceSHA256"]
def read_url(path):
    last=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(BASE+path,headers={"User-Agent":"HENGCE-TDCC-G1-owner-research"})
            with urllib.request.urlopen(req,timeout=100) as response:
                return response.read()
        except Exception as e:
            last=e
            time.sleep(3*(attempt+1))
    raise RuntimeError(f"SOURCE_FETCH_ERROR {path}: {type(last).__name__} {last}")
def digits(s):
    s=str(s).strip().replace(",","")
    if not re.fullmatch(r"[0-9]+",s):
        raise ValueError("NON_INTEGER_PERSON_COUNT")
    return int(s)
def consolidate(date,ticker,grades,reported_total,kind,sha):
    err=[]
    if len(grades)!=15 or set(grades)!=set(range(1,16)):
        err.append("MISSING_LEVEL_OR_DUPLICATE")
    if any(not isinstance(p,int) or p<0 for p in grades.values()):
        err.append("NEGATIVE_OR_NON_INTEGER")
    total=sum(grades.values()) if not err else None
    if reported_total is None:
        err.append("MISSING_TOTAL")
    elif total is not None and total!=reported_total:
        err.append("TOTAL_PEOPLE_NOT_RECONCILED")
    def group(keys):
        return sum(grades[i] for i in keys) if all(i in grades for i in keys) and not err else ""
    # 1-10 lots: grades 1-3, 10+-50 lots grades 4-8; the people
    # column counts per-security holders/accounts, not unique retail humans.
    return [date,ticker,group([1,2,3]),group([4,5,6,7,8]),group([1]),group(list(range(1,9))),
            total if total is not None else "",reported_total if reported_total is not None else "",
            bool(total==reported_total) if total is not None and reported_total is not None else "",
            int(not err),";".join(err),kind,sha]
def parse_html(b,date,ticker,sha):
    soup=BeautifulSoup(b,"lxml")
    table=next((tab for tab in soup.find_all("table") if
                "持股/單位數分級" in tab.get_text() and "人數" in tab.get_text()),None)
    if table is None:
        return [date,ticker,"","","","","","","",0,"MISSING_GRADE_TABLE","TDCC_OFFICIAL_HIST_HTML",sha]
    grades={};total=None;duplicate=False
    for tr in table.find_all("tr"):
        vals=[x.get_text(" ",strip=True) for x in tr.find_all(["td","th"])]
        if len(vals)<4:continue
        tag=vals[0].replace(",","").strip()
        if tag.isdigit():
            num=int(tag)
            if 1<=num<=15:
                if num in grades:duplicate=True
                try:grades[num]=digits(vals[2])
                except ValueError:grades[num]=-1
            elif re.sub(r'\s+', '', vals[1])=='合計':
                # Official HTML may omit the adjustment row, so total is row 16 or 17.
                try:total=digits(vals[2])
                except ValueError:pass
    row=consolidate(date,ticker,grades,total,"TDCC_OFFICIAL_HIST_HTML",sha)
    if duplicate:
        row[9]=0
        row[10]=(row[10]+";" if row[10] else "")+"DUPLICATE_GRADE"
        for k in [2,3,4,5]:row[k]=""
    return row
def process_html(date):
    part="full_market_2025_tail" if date.startswith("2025") else "full_market_2026_jan_apr"
    path=f"ownership/tdcc/backfill_candidate/{part}/{date}/raw_html.zip"
    raw=read_url(path);sha=hashlib.sha256(raw).hexdigest()
    out=[]
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for name in z.namelist():
            m=re.fullmatch(r"valid/([0-9]{4})\.html",name)
            if m:
                out.append(parse_html(z.read(name),date,m.group(1),sha))
    return out,{"date":date,"source_path":path,"raw_sha256":sha,"source_kind":"TDCC_OFFICIAL_HIST_HTML","seen_tickers":len(out)}
def process_csv(date):
    if date in ("20261030","20261106"):
        path=f"ownership/tdcc/{date}/tdcc_1_5_raw.csv"
    else:
        path=f"ownership/tdcc/backfill_candidate/wirelessr/{date}/tdcc_1_5_raw.csv.gz"
    raw=read_url(path);sha=hashlib.sha256(raw).hexdigest()
    data=gzip.decompress(raw) if path.endswith(".gz") else raw
    csvobj=csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    grades=defaultdict(dict);total={};dup=set()
    for a in csvobj:
        ticker=a.get("證券代號","").strip()
        if not re.fullmatch(r"[0-9]{4}",ticker):continue
        if (a.get("資料日期","").strip()!=date):raise RuntimeError("WRONG_DATE_IN_RAW "+date)
        lvl=int(a.get("持股分級","-1"))
        if 1<=lvl<=15:
            if lvl in grades[ticker]:dup.add(ticker)
            try:grades[ticker][lvl]=digits(a.get("人數",""))
            except ValueError:grades[ticker][lvl]=-1
        elif lvl==17:
            try:total[ticker]=digits(a.get("人數",""))
            except ValueError:pass
    result=[]
    for ticker,g in sorted(grades.items()):
        row=consolidate(date,ticker,g,total.get(ticker),"TDCC_OFFICIAL_CSV",sha)
        if ticker in dup:
            row[9]=0;row[10]=(row[10]+";" if row[10] else "")+"DUPLICATE_GRADE"
            for k in [2,3,4,5]:row[k]=""
        result.append(row)
    return result,{"date":date,"source_path":path,"raw_sha256":sha,"source_kind":"TDCC_OFFICIAL_CSV","seen_tickers":len(result)}
def main():
    p=argparse.ArgumentParser();p.add_argument("--shard",choices=DATE,required=True);p.add_argument("--out",default="/tmp/hengce_tdcc_retail_g1");a=p.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    data=[];weeks=[];seen=set()
    for date in DATE[a.shard]:
        rows,receipt=(process_html(date) if a.shard!="2026D" else process_csv(date))
        if len(rows)<800:raise RuntimeError("CATASTROPHIC_WEEK_COVERAGE "+date+" "+str(len(rows)))
        for row in rows:
            k=(row[0],row[1])
            if k in seen:raise RuntimeError("DUPLICATED_WEEK_TICKER "+str(k))
            seen.add(k)
        good=sum(row[9]==1 for row in rows)
        receipt.update(valid_people_account_stockweeks=good,invalid_stockweeks=len(rows)-good,source_rows=len(rows))
        weeks.append(receipt);data.extend(rows)
        print("G1_RETAIL_WEEK",date,"raw_codes",len(rows),"valid_tier_people",good,"invalid",len(rows)-good,flush=True)
    pth=out/f"TDCC_15GRADE_HEADCOUNTS_{a.shard}.csv.gz"
    with gzip.open(pth,"wt",encoding="utf-8",newline="",compresslevel=6) as f:
        w=csv.writer(f);w.writerow(HEADER);w.writerows(data)
    sha=hashlib.sha256(pth.read_bytes()).hexdigest()
    report={
      "artifact":"HENGCE_G1_RAW_TDCC_ACCOUNT_TIER_COUNT_SHARD",
      "shard":a.shard,"status":"SOURCE_SCOPE_EXTRACTED_WITH_INVALID_QUARANTINE",
      "weeks":weeks,"total_weeks":len(weeks),"stockweek_rows":len(data),
      "tier_people_valid":sum(row[9]==1 for row in data),
      "tier_people_invalid":sum(row[9]!=1 for row in data),
      "nonunique_account_people_warning":True,
      "retail_small_1_to_10_lots":"levels_1_2_3_people_sum",
      "retail_10_to_50_lots":"levels_4_to_8_people_sum",
      "source_data_only":True,"not_joined_to_G1_443341_denominator":True,
      "no_model_no_target_return":True,
      "sha256_gzip_output":sha,
      "out_file":pth.name
    }
    (out/f"TDCC_15GRADE_HEADCOUNTS_{a.shard}_RECEIPT.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("G1_RETAIL_SHARD_DONE",a.shard,"weeks",len(weeks),"rows",len(data),"valid",report["tier_people_valid"],"invalid",report["tier_people_invalid"],"sha",sha,flush=True)
if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("G1_RETAIL_SHARD_FAIL",str(exc),file=sys.stderr)
        raise
