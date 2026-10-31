#!/usr/bin/env python3
"""Probe official MOPS direct iXBRL response headers as possible filing-time evidence.

NO prices. NO returns. NO alpha calculations.
"""
from __future__ import annotations
import datetime as dt, hashlib, json, time
from email.utils import parsedate_to_datetime
from pathlib import Path
import requests

OUT=Path('research/selection_core_rebuild/generated/IF07_DIRECT_IXBRL_HEADER_TIMESTAMP_PROBE.json')
OUT.parent.mkdir(parents=True,exist_ok=True)
BASE='https://mopsov.twse.com.tw/server-java/FileDownLoad'
SAMPLES=[
 ('2330',2023,1,'2023-05-12T13:51:34+08:00'),
 ('2454',2024,2,'2024-08-13T17:27:52+08:00'),
 ('3037',2025,3,'2025-10-30T18:45:28+08:00'),
 ('2303',2026,2,'2026-07-29T17:18:33+08:00'),
]

def sha(b): return hashlib.sha256(b).hexdigest()

def parse_http_date(x):
 if not x: return None
 try: return parsedate_to_datetime(x).astimezone(dt.timezone(dt.timedelta(hours=8))).isoformat()
 except Exception: return None

def main():
 s=requests.Session(); s.headers.update({'User-Agent':'Mozilla/5.0 HENGCE-IF07-header-ts-probe/0.1','Referer':'https://mopsov.twse.com.tw/mops/web/t203sb01'})
 rows=[]
 for i,(ticker,year,q,verified) in enumerate(SAMPLES):
  p={'functionName':'t164sb01','step':'9','co_id':ticker,'year':year,'season':q,'report_id':'C'}
  try:
   r=s.get(BASE,params=p,timeout=120,allow_redirects=True)
   b=r.content
   hdr={k:v for k,v in r.headers.items() if k.lower() in {'date','last-modified','etag','content-disposition','content-type','content-length','expires','cache-control'}}
   lm=parse_http_date(r.headers.get('Last-Modified'))
   ver=dt.datetime.fromisoformat(verified)
   lm_dt=dt.datetime.fromisoformat(lm) if lm else None
   row={'ticker':ticker,'year':year,'quarter':q,'verified_upload_ts':verified,'http_status':r.status_code,'final_url':r.url,'bytes':len(b),'sha256':sha(b),'headers':hdr,'last_modified_taipei':lm,'delta_seconds_last_modified_vs_verified':(lm_dt-ver).total_seconds() if lm_dt else None,'is_ixbrl':b'<ix:nonFraction' in b or b'<ix:nonfraction' in b.lower()}
  except Exception as e:
   row={'ticker':ticker,'year':year,'quarter':q,'verified_upload_ts':verified,'error':f'{type(e).__name__}: {e}'}
  rows.append(row)
  if i<len(SAMPLES)-1: time.sleep(3)
 exact=all(r.get('delta_seconds_last_modified_vs_verified')==0 for r in rows)
 obj={'system':'HENGCE','artifact':'IF07_DIRECT_IXBRL_HEADER_TIMESTAMP_PROBE','generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'contains_price_or_forward_return_data':False,'samples':rows,'all_last_modified_exact_upload_match':exact,'verdict':'EXACT_PASS_AS_UPLOAD_TIMESTAMP_AUTHORITY' if exact else 'FAIL_OR_INCONCLUSIVE_AS_UPLOAD_TIMESTAMP_AUTHORITY'}
 OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'verdict':obj['verdict'],'rows':[{k:r.get(k) for k in ['ticker','year','quarter','verified_upload_ts','last_modified_taipei','delta_seconds_last_modified_vs_verified','http_status','error']} for r in rows]},ensure_ascii=False))

if __name__=='__main__': main()
