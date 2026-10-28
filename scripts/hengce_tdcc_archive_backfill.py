#!/usr/bin/env python3
"""Collect every currently downloadable full-market TDCC 1-5 historical snapshot.

Authority policy:
- Official live TDCC vessel remains the only PRIMARY source.
- Historical GitHub mirrors are stored under BACKFILL_CANDIDATE and never silently
  promoted into canonical mother.
- Raw bytes are preserved losslessly as .csv.gz; sha256 refers to uncompressed bytes.
- Big400 = grades 12-15. Big1000 = grade 15.
- Point-in-time semantics are preserved; a snapshot date is weekly evidence, not daily data.
"""
from __future__ import annotations

import csv, gzip, hashlib, io, json, os, re, tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

TZ=ZoneInfo('Asia/Taipei')
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'ownership'/'tdcc'/'backfill_candidate'/'wirelessr'
API='https://api.github.com/repos/wirelessr/tdcc-opendata-archive/contents/snapshots'
RAW='https://raw.githubusercontent.com/wirelessr/tdcc-opendata-archive/main/snapshots'
EXPECTED=['資料日期','證券代號','持股分級','人數','股數','占集保庫存數比例%']
SUMMARY_COLS=['SnapshotDate','Ticker','Big400Holders','Big400Shares','Big400Pct','Big1000Holders','Big1000Shares','Big1000Pct','TotalHolders','TotalShares','AdjustmentShares','MirrorSource','RawSHA256']

def sha(b): return hashlib.sha256(b).hexdigest()
def now(): return datetime.now(TZ).replace(microsecond=0).isoformat()
def atomic(path:Path,b:bytes):
 path.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix=path.name+'.',dir=path.parent);os.close(fd)
 try: Path(tmp).write_bytes(b);os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
def jwrite(path,obj): atomic(path,(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode())
def txt(raw):
 for enc in ('utf-8-sig','utf-8','cp950','big5'):
  try:
   s=raw.decode(enc)
   if all(x in s.splitlines()[0] for x in EXPECTED[:3]): return s,enc
  except UnicodeDecodeError: pass
 raise RuntimeError('ENCODING_OR_HEADER_UNRECOGNIZED')
def nint(x):
 s=str(x or '').replace(',','').strip();return 0 if s in ('','-','--') else int(float(s))
def nfloat(x):
 s=str(x or '').replace(',','').replace('%','').strip();return 0.0 if s in ('','-','--') else float(s)
def list_json(url):
 r=requests.get(url,timeout=45,headers={'Accept':'application/vnd.github+json','User-Agent':'HENGCE-TDCC-BACKFILL/1.0'});r.raise_for_status();return r.json()
def discover():
 years=[]
 for x in list_json(API):
  if x.get('type')=='dir' and re.fullmatch(r'20\d{2}',x.get('name','')): years.append(x['name'])
 files=[]
 for y in sorted(years):
  for x in list_json(f'{API}/{y}'):
   if x.get('type')=='file' and re.fullmatch(r'\d{4}-\d{2}-\d{2}\.csv',x.get('name','')):
    files.append((y,x['name']))
 return files

def parse(raw,expected_date):
 s,enc=txt(raw);rd=csv.DictReader(io.StringIO(s));heads=[str(x or '').replace('\ufeff','').strip() for x in (rd.fieldnames or [])]
 miss=[x for x in EXPECTED if x not in heads]
 if miss: raise RuntimeError('MISSING_COLUMNS:'+','.join(miss))
 rows=[]
 for z in rd:
  r={str(k or '').replace('\ufeff','').strip():v for k,v in z.items()}
  ds=str(r.get('資料日期','')).strip();t=str(r.get('證券代號','')).strip();g=str(r.get('持股分級','')).strip()
  if not(ds and t and g):continue
  if ds!=expected_date: raise RuntimeError(f'DATE_MISMATCH:{ds}!={expected_date}')
  rows.append((t,int(g),nint(r.get('人數')),nint(r.get('股數')),nfloat(r.get('占集保庫存數比例%'))))
 if len(rows)<10000:raise RuntimeError(f'ROWS_TOO_SMALL:{len(rows)}')
 gm={}
 for t,g,h,sh,p in rows:
  if re.fullmatch(r'[1-9]\d{3}',t):gm.setdefault(t,{})[g]=(h,sh,p)
 if len(gm)<900:raise RuntimeError(f'TICKERS_TOO_SMALL:{len(gm)}')
 out=[]
 for t,m in sorted(gm.items()):
  if 15 not in m or 17 not in m:continue
  big=[m[g] for g in (12,13,14,15) if g in m]
  if not big:continue
  out.append({'SnapshotDate':expected_date,'Ticker':t,'Big400Holders':sum(x[0] for x in big),'Big400Shares':sum(x[1] for x in big),'Big400Pct':round(sum(x[2] for x in big),6),'Big1000Holders':m[15][0],'Big1000Shares':m[15][1],'Big1000Pct':round(m[15][2],6),'TotalHolders':m[17][0],'TotalShares':m[17][1],'AdjustmentShares':m.get(16,(0,0,0))[1]})
 if len(out)<900:raise RuntimeError(f'SUMMARY_TOO_SMALL:{len(out)}')
 return rows,out,enc

def csvbytes(rows,rawsha,src):
 s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=SUMMARY_COLS,lineterminator='\n');w.writeheader()
 for r in rows:
  z=dict(r);z['MirrorSource']=src;z['RawSHA256']=rawsha;w.writerow(z)
 return s.getvalue().encode()
def read_official_summary(date):
 p=ROOT/'ownership'/'tdcc'/date/'tdcc_ownership_4d.csv'
 if not p.exists():return None
 with p.open(encoding='utf-8-sig',newline='') as f:
  d={}
  for r in csv.DictReader(f):
   d[str(r['Ticker'])]=(int(float(r['Big400Holders'])),int(float(r['Big400Shares'])),round(float(r['Big400Pct']),6),int(float(r['Big1000Holders'])),int(float(r['Big1000Shares'])),round(float(r['Big1000Pct']),6),int(float(r['TotalHolders'])),int(float(r['TotalShares'])))
 return d
def norm_candidate(rows):
 return {str(r['Ticker']):(int(r['Big400Holders']),int(r['Big400Shares']),round(float(r['Big400Pct']),6),int(r['Big1000Holders']),int(r['Big1000Shares']),round(float(r['Big1000Pct']),6),int(r['TotalHolders']),int(r['TotalShares'])) for r in rows}

def main():
 files=discover();manifest=[];fail=[]
 for y,name in files:
  d=name[:-4].replace('-','');src=f'{RAW}/{y}/{name}';dest=OUT/d;gz=dest/'tdcc_1_5_raw.csv.gz';sm=dest/'tdcc_ownership_4d.csv';rec=dest/'receipt.json'
  try:
   r=requests.get(src,timeout=60,headers={'User-Agent':'HENGCE-TDCC-BACKFILL/1.0'});r.raise_for_status();raw=r.content;rh=sha(raw)
   _,summary,enc=parse(raw,d)
   sb=csvbytes(summary,rh,src);sh=sha(sb)
   verification='ARCHIVE_ONLY_BACKFILL_CANDIDATE'
   off=read_official_summary(d)
   if off is not None:
    verification='VERIFIED_AGAINST_OFFICIAL_SUMMARY' if off==norm_candidate(summary) else 'OFFICIAL_SUMMARY_MISMATCH_FAIL_CLOSED'
    if verification.endswith('FAIL_CLOSED'):raise RuntimeError(verification)
   dest.mkdir(parents=True,exist_ok=True)
   atomic(gz,gzip.compress(raw,compresslevel=9,mtime=0));atomic(sm,sb)
   receipt={'system':'HENGCE','artifact':'TDCC_HISTORICAL_BACKFILL_CANDIDATE','status':'COMPLETE','snapshot_date':d,'downloaded_at_taipei':now(),'source_kind':'PUBLIC_GITHUB_MIRROR_OF_TDCC_1_5','mirror_repo':'wirelessr/tdcc-opendata-archive','mirror_url':src,'raw_uncompressed_sha256':rh,'summary_sha256':sh,'summary_rows':len(summary),'source_encoding':enc,'verification':verification,'authority':'RESEARCH_BACKFILL_ONLY_NO_CANONICAL_AUTHORITY','big400_definition':'grades 12+13+14+15','big1000_definition':'grade 15','point_in_time':'WEEKLY_SNAPSHOT_DO_NOT_FORWARD_OR_BACKFILL_AS_DAILY'}
   jwrite(rec,receipt);manifest.append(receipt)
   print('OK',d,len(summary),verification)
  except Exception as e:
   fail.append({'snapshot':d,'source':src,'error':f'{type(e).__name__}:{e}'});print('FAIL',d,e)
 manifest_obj={'system':'HENGCE','artifact':'TDCC_BACKFILL_CANDIDATE_MANIFEST','generated_at_taipei':now(),'status':'PASS' if not fail else 'PARTIAL','downloaded_snapshots':len(manifest),'failed_snapshots':len(fail),'first_snapshot':min([x['snapshot_date'] for x in manifest],default=None),'last_snapshot':max([x['snapshot_date'] for x in manifest],default=None),'years':sorted({x['snapshot_date'][:4] for x in manifest}),'authority':'RESEARCH_BACKFILL_ONLY','official_primary_source_unchanged':True,'snapshots':manifest,'failures':fail}
 jwrite(OUT/'MANIFEST.json',manifest_obj)
 if fail:raise SystemExit(2)
 return 0
if __name__=='__main__':raise SystemExit(main())
