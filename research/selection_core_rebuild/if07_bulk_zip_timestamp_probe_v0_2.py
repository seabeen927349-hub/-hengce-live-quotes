#!/usr/bin/env python3
"""HENGCE IF-07 bulk ZIP timestamp probe V0.2.

Engineering-only hardening: validate ZIP magic, back off/retry MOPS transient/rate-limit
responses, and record failure body prefixes. NO price data. NO returns.
"""
from __future__ import annotations
import datetime as dt, hashlib, io, json, time, zipfile
from pathlib import Path
import requests

OUT=Path('research/selection_core_rebuild/generated/IF07_BULK_ZIP_TIMESTAMP_PROBE_V0_2.json')
OUT.parent.mkdir(parents=True,exist_ok=True)
BASE='https://mopsov.twse.com.tw/server-java/FileDownLoad'
SAMPLES=[
 {'ticker':'2330','year':2023,'quarter':1,'verified_upload':'2023-05-12T13:51:34'},
 {'ticker':'2454','year':2024,'quarter':2,'verified_upload':'2024-08-13T17:27:52'},
 {'ticker':'3037','year':2025,'quarter':3,'verified_upload':'2025-10-30T18:45:28'},
 {'ticker':'2303','year':2026,'quarter':2,'verified_upload':'2026-07-29T17:18:33'},
]

def sha(b:bytes): return hashlib.sha256(b).hexdigest()

def get_zip(s,year,q):
 fn=f'tifrs-{year}Q{q}.zip'; p={'step':'9','functionName':'show_file2','fileName':fn,'filePath':f'/ifrs/{year}/'}
 attempts=[]
 for a in range(1,6):
  try:
   r=s.get(BASE,params=p,headers={'Referer':'https://mopsov.twse.com.tw/mops/web/t203sb02'},timeout=300)
   b=r.content
   rec={'attempt':a,'status':r.status_code,'bytes':len(b),'content_type':r.headers.get('content-type'),'content_disposition':r.headers.get('content-disposition'),'zip_magic':b[:2]==b'PK','sha256':sha(b)}
   if not rec['zip_magic']:
    rec['body_prefix']=b[:500].decode('utf-8','replace')
   attempts.append(rec)
   if r.status_code==200 and b[:2]==b'PK': return b,attempts
  except Exception as e:
   attempts.append({'attempt':a,'error':f'{type(e).__name__}: {e}'})
  time.sleep(12*a)
 raise RuntimeError(json.dumps({'year':year,'quarter':q,'attempts':attempts},ensure_ascii=False))

def main():
 s=requests.Session(); s.headers.update({'User-Agent':'Mozilla/5.0 HENGCE-IF07-zip-ts-probe-v0.2','Accept-Language':'zh-TW,zh;q=0.9'})
 out=[]; cache={}
 for idx,x in enumerate(SAMPLES):
  key=(x['year'],x['quarter'])
  try:
   b,attempts=get_zip(s,*key)
   z=zipfile.ZipFile(io.BytesIO(b)); cache[key]={'zip':z,'bytes':len(b),'sha256':sha(b),'attempts':attempts}
   target=f"tifrs-fr1-m1-ci-cr-{x['ticker']}-{x['year']}Q{x['quarter']}.html"
   hits=[zi for zi in z.infolist() if Path(zi.filename).name.lower()==target.lower()]
   row={**x,'bulk_zip_bytes':len(b),'bulk_zip_sha256':sha(b),'download_attempts':attempts,'target_member':target,'hit_count':len(hits)}
   if len(hits)==1:
    zi=hits[0]; member_ts=dt.datetime(*zi.date_time); verified=dt.datetime.fromisoformat(x['verified_upload']); delta=(member_ts-verified).total_seconds()
    row.update({'member_filename':zi.filename,'zip_member_timestamp':member_ts.isoformat(),'zip_member_timestamp_raw':list(zi.date_time),'member_file_size':zi.file_size,'member_crc':zi.CRC,'delta_seconds_vs_verified_upload':delta,'exact_match':delta==0,'within_one_second':abs(delta)<=1,'same_minute':member_ts.replace(second=0)==verified.replace(second=0)})
   out.append(row)
  except Exception as e:
   out.append({**x,'error':f'{type(e).__name__}: {e}'})
  if idx < len(SAMPLES)-1: time.sleep(20)
 exact=all(r.get('exact_match') for r in out)
 within1=all(r.get('within_one_second') for r in out)
 obj={'system':'HENGCE','artifact':'IF07_BULK_ZIP_TIMESTAMP_PROBE_V0_2','generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'contains_price_or_forward_return_data':False,'samples':out,'all_exact_match':exact,'all_within_one_second':within1,'verdict':'EXACT_PASS' if exact else ('WITHIN_ONE_SECOND_ONLY' if within1 else 'FAIL_AS_UPLOAD_TIMESTAMP_AUTHORITY')}
 OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'verdict':obj['verdict'],'rows':[{k:r.get(k) for k in ['ticker','year','quarter','verified_upload','zip_member_timestamp','delta_seconds_vs_verified_upload','exact_match','within_one_second','error']} for r in out]},ensure_ascii=False))
if __name__=='__main__': main()
