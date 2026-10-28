#!/usr/bin/env python3
"""HENGCE research-only derived holder-history collector from norway.twsthr.info.

This is NOT TDCC raw authority. It is a derived historical backfill candidate.
Default pacing is one request per second. Do not increase concurrency.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,re,time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'ownership'/'tdcc'
OUT=BASE/'backfill_candidate'/'twsthr_derived'
URL='https://norway.twsthr.info/StockHolders.aspx?stock={}'
UA='Mozilla/5.0 (HENGCE research; polite derived-history collector)'
DATE_RE=re.compile(r'^20[12][0-9][01][0-9][0-3][0-9]$')
RECORD_LEN=15
TZ=ZoneInfo('Asia/Taipei')
COLS=['SnapshotDate','Ticker','TotalLots','TotalHolders','AvgLotsPerHolder','Big400Lots','Big400Pct','Big400Holders','Holders400_600','Holders600_800','Holders800_1000','HoldersOver1000','Big1000Pct','ClosePrice','Source']

def pi(s):
 s=str(s).replace(',','').strip()
 try:return int(float(s))
 except:return None
def pf(s):
 s=str(s).replace(',','').strip()
 try:return float(s)
 except:return None

def parse(html,ticker):
 soup=BeautifulSoup(html,'html.parser');tables=sorted(soup.find_all('table'),key=lambda t:len(t.find_all('tr')),reverse=True)
 if len(tables)<3:return []
 cells=[c.get_text(strip=True) for r in tables[2].find_all('tr') for c in r.find_all(['td','th'])]
 rows=[];seen=set();i=0
 while i<len(cells):
  if DATE_RE.match(cells[i]):
   b=cells[i:i+RECORD_LEN]
   if len(b)==RECORD_LEN and b[0] not in seen:
    seen.add(b[0]);rows.append({'SnapshotDate':b[0],'Ticker':ticker,'TotalLots':pi(b[1]),'TotalHolders':pi(b[2]),'AvgLotsPerHolder':pf(b[3]),'Big400Lots':pi(b[4]),'Big400Pct':pf(b[5]),'Big400Holders':pi(b[6]),'Holders400_600':pi(b[7]),'Holders600_800':pi(b[8]),'Holders800_1000':pi(b[9]),'HoldersOver1000':pi(b[10]),'Big1000Pct':pf(b[11]),'ClosePrice':pf(b[12]),'Source':URL.format(ticker)})
   i+=RECORD_LEN
  else:i+=1
 return rows

def fetch(ticker):
 r=requests.get(URL.format(ticker),headers={'User-Agent':UA},timeout=30);r.raise_for_status();return parse(r.text,ticker)
def universe():
 p=BASE/'latest.json'
 # Prefer latest official summary pointed by repo state; current vessel is 20261022.
 p=BASE/'20261022'/'tdcc_ownership_4d.csv'
 ids=[]
 with p.open(encoding='utf-8-sig',newline='') as f:
  for r in csv.DictReader(f):
   t=str(r.get('Ticker','')).strip()
   if re.fullmatch(r'[1-9]\d{3}',t):ids.append(t)
 return sorted(set(ids))
def write_csv(path,rows):
 import io
 s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=COLS,lineterminator='\n');w.writeheader();w.writerows(rows);raw=s.getvalue().encode();path.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0));return hashlib.sha256(raw).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--symbols',default='');ap.add_argument('--sleep',type=float,default=1.0);ap.add_argument('--chunk-size',type=int,default=200);args=ap.parse_args()
 ids=[x.strip() for x in args.symbols.split(',') if x.strip()] if args.symbols else universe()
 ids=[x for x in ids if re.fullmatch(r'[1-9]\d{3}',x)]
 OUT.mkdir(parents=True,exist_ok=True);summary=[]
 for c0 in range(0,len(ids),args.chunk_size):
  chunk=ids[c0:c0+args.chunk_size];tag=f'{c0:04d}_{c0+len(chunk)-1:04d}';p=OUT/f'chunk_{tag}.csv.gz';rp=OUT/f'chunk_{tag}.receipt.json'
  if p.exists() and rp.exists():continue
  rows=[];errors=[]
  for n,t in enumerate(chunk):
   try:
    rr=fetch(t);rows.extend(rr);print(t,len(rr), flush=True)
   except Exception as e:errors.append({'ticker':t,'error':f'{type(e).__name__}:{e}'});print('ERR',t,e,flush=True)
   if n<len(chunk)-1:time.sleep(max(1.0,args.sleep))
  if not rows: raise SystemExit('NO_ROWS_IN_CHUNK:'+tag)
  h=write_csv(p,rows);dates=sorted({r['SnapshotDate'] for r in rows})
  rec={'system':'HENGCE','artifact':'TWSTHR_DERIVED_HOLDER_BACKFILL_CHUNK','status':'COMPLETE' if not errors else 'PARTIAL','chunk':tag,'requested_symbols':len(chunk),'successful_symbols':len(set(r['Ticker'] for r in rows)),'rows':len(rows),'first_snapshot':dates[0],'last_snapshot':dates[-1],'errors':errors,'sha256_uncompressed_csv':h,'generated_at_taipei':datetime.now(TZ).replace(microsecond=0).isoformat(),'authority':'DERIVED_RESEARCH_BACKFILL_ONLY_NO_TDCC_RAW_AUTHORITY','pacing_seconds':max(1.0,args.sleep)}
  rp.write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n');summary.append(rec)
 print(json.dumps({'chunks_written':len(summary),'requested_symbols':len(ids)},ensure_ascii=False))
if __name__=='__main__':main()
