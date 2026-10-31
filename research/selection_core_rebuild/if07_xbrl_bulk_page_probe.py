#!/usr/bin/env python3
"""Inspect official MOPS XBRL bulk-download page protocol.
NO price data. NO returns. Engineering capability only.
"""
from __future__ import annotations
import datetime as dt, hashlib, json, re
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

OUT=Path('research/selection_core_rebuild/generated/IF07_XBRL_BULK_PAGE_PROBE.json')
OUT.parent.mkdir(parents=True,exist_ok=True)
URL='https://mopsov.twse.com.tw/mops/web/t203sb02'

def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def sh(b): return hashlib.sha256(b).hexdigest()

def main():
 s=requests.Session(); s.headers.update({'User-Agent':'Mozilla/5.0 HENGCE-IF07-bulk-probe/0.1','Accept-Language':'zh-TW,zh;q=0.9'})
 r=s.get(URL,timeout=45); r.encoding='utf-8'; text=r.text
 soup=BeautifulSoup(text,'lxml')
 forms=[]
 for f in soup.find_all('form'):
  forms.append({'action':f.get('action'),'method':f.get('method'),'id':f.get('id'),'name':f.get('name')})
 inputs=[]
 for x in soup.find_all(['input','button','a','img']):
  d={k:x.get(k) for k in ['tag','type','name','value','id','src','href','onclick','onmousedown','class','alt','title'] if x.get(k) is not None}
  d['tag']=x.name
  surrounding=' '.join(x.parent.stripped_strings)[:300] if x.parent else ''
  if any(k in (surrounding+' '+str(d)) for k in ['112','Q1','下載','download','fish','魚','203sb02','step']):
   d['surrounding_text']=surrounding
   inputs.append(d)
 scripts=[]
 inline=[]
 for sc in soup.find_all('script'):
  if sc.get('src'):
   scripts.append(urljoin(r.url,sc.get('src')))
  else:
   t=sc.get_text('\n')
   if any(k in t for k in ['203sb02','download','Download','FileDownLoad','Q1','season','year','ajax']): inline.append(t[:20000])
 # Fetch same-origin scripts and find likely protocol snippets.
 script_hits=[]
 for u in scripts:
  try:
   rr=s.get(u,timeout=30)
   st=rr.text
   lines=[ln.strip() for ln in st.splitlines() if any(k in ln for k in ['t203sb02','FileDownLoad','download','Download','season','year'])]
   if lines: script_hits.append({'url':u,'http_status':rr.status_code,'sha256':sh(rr.content),'hits':lines[:100]})
  except Exception as e:
   script_hits.append({'url':u,'error':type(e).__name__+': '+str(e)})
 obj={'system':'HENGCE','artifact':'IF07_XBRL_BULK_PAGE_PROBE','generated_at_utc':now(),'contains_price_or_forward_return_data':False,
      'page':{'url':r.url,'status':r.status_code,'bytes':len(r.content),'sha256':sh(r.content),'title':soup.title.get_text(strip=True) if soup.title else None},
      'forms':forms,'candidate_controls':inputs[:300],'script_urls':scripts,'inline_script_hits':inline,'external_script_hits':script_hits,
      'raw_keyword_context':[]}
 for m in re.finditer(r'.{0,250}(?:112|Q1|下載|FileDownLoad|t203sb02).{0,500}',text,re.S):
  obj['raw_keyword_context'].append(re.sub(r'\s+',' ',m.group(0))[:1000])
  if len(obj['raw_keyword_context'])>=80: break
 OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'status':r.status_code,'forms':len(forms),'controls':len(inputs),'scripts':len(scripts),'script_hits':len(script_hits),'contexts':len(obj['raw_keyword_context'])},ensure_ascii=False))
if __name__=='__main__': main()
