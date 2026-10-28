#!/usr/bin/env python3
"""Collect downloadable legacy TDCC distribution CSV resources from NCHC CKAN mirrors.
Research backfill only. Never creates canonical authority.
"""
from __future__ import annotations
import csv,gzip,hashlib,io,json,os,re,tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
TZ=ZoneInfo('Asia/Taipei')
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'ownership'/'tdcc'/'backfill_candidate'/'nchc'
PACKAGES=[
 ('https://scidm.nchc.org.tw/api/3/action/package_show','64395e85-c0b3-4aaa-8df7-442e5ca0343a'),
 ('https://scidm.nchc.org.tw/api/3/action/package_show','ba3fdd24-d3c8-401b-ae8f-07f03ef6c379'),
]
EXPECTED=['資料日期','證券代號','持股分級','人數','股數','占集保庫存數比例%']
COLS=['SnapshotDate','Ticker','Big400Holders','Big400Shares','Big400Pct','Big1000Holders','Big1000Shares','Big1000Pct','TotalHolders','TotalShares','AdjustmentShares','Source','RawSHA256']
def now():return datetime.now(TZ).replace(microsecond=0).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
def atomic(p,b):
 p.parent.mkdir(parents=True,exist_ok=True);fd,t=tempfile.mkstemp(prefix=p.name+'.',dir=p.parent);os.close(fd)
 try:Path(t).write_bytes(b);os.replace(t,p)
 finally:
  if os.path.exists(t):os.unlink(t)
def jwrite(p,o):atomic(p,(json.dumps(o,ensure_ascii=False,indent=2)+'\n').encode())
def decode(raw):
 for enc in ('utf-8-sig','utf-8','cp950','big5'):
  try:
   s=raw.decode(enc)
   h=(s.splitlines() or [''])[0]
   if '資料日期' in h and '證券代號' in h and '持股分級' in h:return s,enc
  except UnicodeDecodeError:pass
 raise RuntimeError('NOT_TDCC_CSV')
def ni(x):
 s=str(x or '').replace(',','').strip();return 0 if s in ('','-','--') else int(float(s))
def nf(x):
 s=str(x or '').replace(',','').replace('%','').strip();return 0.0 if s in ('','-','--') else float(s)
def parse(raw):
 s,enc=decode(raw);rd=csv.DictReader(io.StringIO(s));heads=[str(x or '').replace('\ufeff','').strip() for x in (rd.fieldnames or [])]
 miss=[x for x in EXPECTED if x not in heads]
 if miss:raise RuntimeError('MISSING:'+','.join(miss))
 rows=[]
 for z in rd:
  r={str(k or '').replace('\ufeff','').strip():v for k,v in z.items()};ds=str(r.get('資料日期','')).strip();t=str(r.get('證券代號','')).strip();g=str(r.get('持股分級','')).strip()
  if not(ds and t and g):continue
  if not re.fullmatch(r'\d{8}',ds):continue
  rows.append((ds,t,int(g),ni(r.get('人數')),ni(r.get('股數')),nf(r.get('占集保庫存數比例%'))))
 if len(rows)<1000:raise RuntimeError(f'ROWS_TOO_SMALL:{len(rows)}')
 dates=sorted({x[0] for x in rows})
 if len(dates)!=1:raise RuntimeError('MULTI_DATE:'+','.join(dates[:10]))
 d=dates[0];gm={}
 for _,t,g,h,sh,p in rows:
  if re.fullmatch(r'[1-9]\d{3}',t):gm.setdefault(t,{})[g]=(h,sh,p)
 if len(gm)<500:raise RuntimeError(f'TICKERS_TOO_SMALL:{len(gm)}')
 out=[]
 for t,m in sorted(gm.items()):
  if 15 not in m or 17 not in m:continue
  b=[m[g] for g in (12,13,14,15) if g in m]
  if not b:continue
  out.append({'SnapshotDate':d,'Ticker':t,'Big400Holders':sum(x[0] for x in b),'Big400Shares':sum(x[1] for x in b),'Big400Pct':round(sum(x[2] for x in b),6),'Big1000Holders':m[15][0],'Big1000Shares':m[15][1],'Big1000Pct':round(m[15][2],6),'TotalHolders':m[17][0],'TotalShares':m[17][1],'AdjustmentShares':m.get(16,(0,0,0))[1]})
 return d,out,enc,len(rows)
def csvo(rows,src,rh):
 s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=COLS,lineterminator='\n');w.writeheader()
 for x in rows:
  z=dict(x);z['Source']=src;z['RawSHA256']=rh;w.writerow(z)
 return s.getvalue().encode()
def main():
 found=[];failed=[];seen=set()
 for api,pkg in PACKAGES:
  try:
   q=requests.get(api,params={'id':pkg},timeout=45,headers={'User-Agent':'HENGCE-TDCC-NCHC/1.0'});q.raise_for_status();obj=q.json();resources=(obj.get('result') or {}).get('resources') or []
  except Exception as e:
   failed.append({'package':pkg,'error':f'PACKAGE:{type(e).__name__}:{e}'});continue
  for r in resources:
   rid=str(r.get('id') or 'unknown');url=r.get('url') or r.get('cache_url')
   if not url:continue
   fmt=str(r.get('format') or '').lower();mt=str(r.get('mimetype') or '').lower()
   if 'csv' not in fmt and 'csv' not in mt and not str(url).lower().endswith('.csv'):continue
   try:
    x=requests.get(url,timeout=60,headers={'User-Agent':'HENGCE-TDCC-NCHC/1.0'},allow_redirects=True);x.raise_for_status();raw=x.content;rh=sha(raw)
    if rh in seen:continue
    d,summary,enc,n=parse(raw);seen.add(rh);dest=OUT/d;src=f'{api}?id={pkg} :: {url}'
    atomic(dest/f'{rid}_raw.csv.gz',gzip.compress(raw,compresslevel=9,mtime=0));sb=csvo(summary,src,rh);atomic(dest/f'{rid}_ownership_4d.csv',sb)
    rec={'system':'HENGCE','artifact':'TDCC_LEGACY_NCHC_BACKFILL_CANDIDATE','status':'COMPLETE','snapshot_date':d,'downloaded_at_taipei':now(),'package_id':pkg,'resource_id':rid,'resource_name':r.get('name'),'resource_url':url,'raw_sha256':rh,'raw_rows':n,'summary_rows':len(summary),'source_encoding':enc,'authority':'RESEARCH_BACKFILL_ONLY_NO_CANONICAL_AUTHORITY'}
    jwrite(dest/f'{rid}_receipt.json',rec);found.append(rec);print('OK',d,rid,len(summary))
   except Exception as e:
    failed.append({'package':pkg,'resource_id':rid,'url':url,'error':f'{type(e).__name__}:{e}'});print('FAIL',rid,e)
 jwrite(OUT/'MANIFEST.json',{'system':'HENGCE','artifact':'TDCC_NCHC_BACKFILL_MANIFEST','generated_at_taipei':now(),'status':'PASS' if found else 'NO_VALID_RESOURCE','valid_resources':len(found),'failed_resources':len(failed),'first_snapshot':min([x['snapshot_date'] for x in found],default=None),'last_snapshot':max([x['snapshot_date'] for x in found],default=None),'resources':found,'failures':failed,'authority':'RESEARCH_BACKFILL_ONLY'})
 return 0
if __name__=='__main__':raise SystemExit(main())
