#!/usr/bin/env python3
"""Verify one official MOPS quarterly bulk iXBRL ZIP.
NO prices, NO returns.
"""
from __future__ import annotations
import datetime as dt, hashlib, io, json, zipfile
from pathlib import Path
import requests

OUT=Path('research/selection_core_rebuild/generated/IF07_BULK_ZIP_PROBE_2023Q1.json')
OUT.parent.mkdir(parents=True,exist_ok=True)
URL='https://mopsov.twse.com.tw/server-java/FileDownLoad'
PARAMS={'step':'9','functionName':'show_file2','fileName':'tifrs-2023Q1.zip','filePath':'/ifrs/2023/'}

def main():
 s=requests.Session(); s.headers.update({'User-Agent':'Mozilla/5.0 HENGCE-IF07-bulk-zip-probe/0.1','Referer':'https://mopsov.twse.com.tw/mops/web/t203sb02'})
 r=s.get(URL,params=PARAMS,timeout=180)
 b=r.content
 obj={'system':'HENGCE','artifact':'IF07_BULK_ZIP_PROBE_2023Q1','generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'contains_price_or_forward_return_data':False,
      'http_status':r.status_code,'final_url':r.url,'content_type':r.headers.get('content-type'),'content_disposition':r.headers.get('content-disposition'),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'zip_magic':b[:2]==b'PK'}
 if b[:2]==b'PK':
  with zipfile.ZipFile(io.BytesIO(b)) as z:
   names=z.namelist()
   obj['member_count']=len(names)
   obj['first_30_members']=names[:30]
   obj['members_with_2330']=[n for n in names if '2330' in n][:20]
   obj['members_with_2454']=[n for n in names if '2454' in n][:20]
   obj['html_member_count']=sum(n.lower().endswith(('.html','.htm','.xhtml')) for n in names)
   obj['xml_xbrl_member_count']=sum(n.lower().endswith(('.xml','.xbrl')) for n in names)
 OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:obj.get(k) for k in ['http_status','bytes','zip_magic','member_count','html_member_count','xml_xbrl_member_count','members_with_2330']},ensure_ascii=False))
if __name__=='__main__': main()
