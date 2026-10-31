#!/usr/bin/env python3
"""HENGCE IF-07 Discovery electronic-report metadata index V0.2.

Fixes invalid V0.1 blank-year coverage by querying explicit ticker × ROC year for
2022-2024 only. NO accounting values, NO prices, NO returns.
Discovery inclusion is by resolved SIGNAL DATE <= 2024-12-31, not fiscal year.
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import re
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

ROOT=Path('research/selection_core_rebuild')
UNION=ROOT/'IF07_ELECTRONICS_ACQUISITION_TICKER_UNION_2022_2026.json'
SESS=ROOT/'IF07_CANONICAL_TRADING_SESSIONS_2022_2026.json'
OUT=ROOT/'generated/IF07_DISCOVERY_METADATA_INDEX_V0_2.json'
OUT.parent.mkdir(parents=True,exist_ok=True)
URL='https://doc.twse.com.tw/server-java/t57sb01'
UA='Mozilla/5.0 HENGCE-IF07-discovery-metadata-v0.2'
YEARS=[2022,2023,2024]
QMAP={'一':1,'二':2,'三':3,'四':4}
RE_PERIOD=re.compile(r'(?P<roc>\d+)\s*年\s*第(?P<q>[一二三四])季')
RE_UPLOAD=re.compile(r'(?P<roc>\d{2,3})/(?P<m>\d{2})/(?P<d>\d{2})\s+(?P<h>\d{2}):(?P<mi>\d{2}):(?P<s>\d{2})')
_tls=threading.local()


def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def sha(b:bytes): return hashlib.sha256(b).hexdigest()

def sess():
 if not hasattr(_tls,'s'):
  s=requests.Session(); s.headers.update({'User-Agent':UA,'Accept-Language':'zh-TW,zh;q=0.9'}); _tls.s=s
 return _tls.s

def parse_upload(x:str):
 m=RE_UPLOAD.fullmatch(x.strip())
 if not m: return None
 return dt.datetime(int(m['roc'])+1911,int(m['m']),int(m['d']),int(m['h']),int(m['mi']),int(m['s']))

def fetch_one(ticker:str,year:int)->dict[str,Any]:
 roc=year-1911
 p={'step':'1','colorchg':'1','co_id':ticker,'year':str(roc),'seamon':'','mtype':'A'}
 last=None
 for attempt in range(4):
  try:
   r=sess().get(URL,params=p,timeout=45); r.encoding='big5'; text=r.text
   soup=BeautifulSoup(text,'lxml'); rows=[]
   for tr in soup.find_all('tr'):
    cells=[' '.join(td.stripped_strings) for td in tr.find_all(['td','th'])]
    if not cells or ticker not in cells or len(cells)<11: continue
    if cells[5] != 'IFRSs合併財報': continue
    pm=RE_PERIOD.search(cells[1])
    if not pm: continue
    fy=int(pm['roc'])+1911; q=QMAP[pm['q']]
    if fy!=year: continue
    up=parse_upload(cells[9])
    rows.append({'ticker':ticker,'fiscal_year':fy,'quarter':q,'period_text':cells[1],'report_type':cells[5],'file_name':cells[7],'file_size_text':cells[8],'upload_text':cells[9],'upload_ts_taipei':up.isoformat() if up else None,'correction_field':cells[10],'correction_exact_none':cells[10]=='無'})
   low=text.lower()
   blocked=any(s in low for s in ['access denied','this page can not be accessed','this page cannot be accessed','for security reasons'])
   return {'ticker':ticker,'year':year,'roc_year':roc,'http_status':r.status_code,'bytes':len(r.content),'sha256':sha(r.content),'security_blocked':blocked,'rows':rows,'error':None,'body_text_prefix':' '.join(soup.stripped_strings)[:240]}
  except Exception as e:
   last=f'{type(e).__name__}: {e}'; time.sleep(1.5*(attempt+1))
 return {'ticker':ticker,'year':year,'roc_year':roc,'http_status':None,'bytes':None,'sha256':None,'security_blocked':False,'rows':[],'error':last}

def resolve(upload_iso:str|None,sessions:list[dt.date]):
 if not upload_iso: return None,'UNPARSEABLE_UPLOAD_TS'
 x=dt.datetime.fromisoformat(upload_iso); d=x.date(); ss=set(sessions)
 if d in ss and x.time()<dt.time(13,30): return d.isoformat(),None
 for sd in sessions:
  if sd>d: return sd.isoformat(),None
 return None,'TRADING_SESSION_COVERAGE_BLOCKED'

def main():
 tickers=json.loads(UNION.read_text(encoding='utf-8'))['ticker_union']
 sobj=json.loads(SESS.read_text(encoding='utf-8')); sessions=[]
 for y in range(2022,2026): sessions.extend(dt.date.fromisoformat(x) for x in sobj['years'][str(y)]['dates'])
 sessions=sorted(set(sessions))
 tasks=[(t,y) for t in tickers for y in YEARS]
 results=[]
 with cf.ThreadPoolExecutor(max_workers=3) as ex:
  futs={ex.submit(fetch_one,*task):task for task in tasks}
  for i,f in enumerate(cf.as_completed(futs),1):
   results.append(f.result())
   if i%100==0: print(f'explicit-year metadata {i}/{len(tasks)}',flush=True)
 # Retry transport/security failures separately and slowly; zero rows are not automatically errors.
 bad=[r for r in results if r.get('error') or r.get('security_blocked') or r.get('http_status')!=200]
 good={(r['ticker'],r['year']):r for r in results if (r['ticker'],r['year']) not in {(b['ticker'],b['year']) for b in bad}}
 for round_no in range(3):
  if not bad: break
  print(f'retry round {round_no+1} tasks={len(bad)}',flush=True); time.sleep(5)
  nxt=[]
  for old in bad:
   r=fetch_one(old['ticker'],old['year'])
   if r.get('error') or r.get('security_blocked') or r.get('http_status')!=200: nxt.append(r)
   else: good[(r['ticker'],r['year'])]=r
  bad=nxt
 results=list(good.values())+bad; results.sort(key=lambda r:(r['ticker'],r['year']))
 rows=[]
 for r in results: rows.extend(r['rows'])
 rows.sort(key=lambda r:(r['ticker'],r['fiscal_year'],r['quarter'],r['upload_ts_taipei'] or ''))
 bykey=defaultdict(list)
 for r in rows: bykey[(r['ticker'],r['fiscal_year'],r['quarter'])].append(r)
 dup={f'{t}:{y}Q{q}':v for (t,y,q),v in bykey.items() if len(v)!=1}
 usable={k:v[0] for k,v in bykey.items() if len(v)==1 and v[0]['correction_exact_none'] and v[0]['upload_ts_taipei']}
 pairs=[]; outside=[]
 for (t,y,q),cur in sorted(usable.items()):
  if y not in (2023,2024): continue
  prev=usable.get((t,y-1,q))
  if not prev: continue
  sd,err=resolve(cur['upload_ts_taipei'],sessions)
  row={'ticker':t,'fiscal_year':y,'quarter':q,'current_file':cur['file_name'],'current_upload_ts_taipei':cur['upload_ts_taipei'],'prior_file':prev['file_name'],'prior_upload_ts_taipei':prev['upload_ts_taipei'],'signal_date':sd,'signal_date_error':err,'pit_electronics_membership_checked':False}
  if sd and '2023-01-01'<=sd<='2024-12-31': pairs.append(row)
  else: outside.append(row)
 query_errors=[{'ticker':r['ticker'],'year':r['year'],'error':r.get('error'),'status':r.get('http_status'),'security_blocked':r.get('security_blocked')} for r in results if r.get('error') or r.get('security_blocked') or r.get('http_status')!=200]
 qrows=Counter(f"{r['fiscal_year']}Q{r['quarter']}" for r in rows)
 qexact=Counter(f"{r['fiscal_year']}Q{r['quarter']}" for r in rows if r['correction_exact_none'])
 qpairs=Counter(f"{r['fiscal_year']}Q{r['quarter']}" for r in pairs)
 ticker_year_rows=Counter((r['ticker'],r['fiscal_year']) for r in rows)
 obj={'system':'HENGCE','artifact':'IF07_DISCOVERY_METADATA_INDEX_V0_2','generated_at_utc':now(),'contains_accounting_values':False,'contains_price_or_forward_return_data':False,'query_mode':'EXPLICIT_TICKER_X_FISCAL_YEAR_2022_2024','acquisition_ticker_count':len(tickers),'query_task_count':len(tasks),'query_error_count':len(query_errors),'query_errors':query_errors,'report_row_count':len(rows),'report_rows_by_year_quarter':dict(sorted(qrows.items())),'correction_exact_none_count':sum(r['correction_exact_none'] for r in rows),'correction_exact_none_by_year_quarter':dict(sorted(qexact.items())),'correction_field_value_counts':dict(Counter(r['correction_field'] for r in rows)),'duplicate_or_ambiguous_company_quarter_count':len(dup),'duplicate_or_ambiguous_keys':dup,'ticker_year_with_rows_count':len(ticker_year_rows),'discovery_current_prior_exact_none_pair_count':len(pairs),'discovery_pair_count_by_fiscal_year_quarter':dict(sorted(qpairs.items())),'outside_discovery_signal_date_pair_count':len(outside),'outside_discovery_pairs':outside,'metadata_rows':rows,'discovery_pairs':pairs,'boundary':'No accounting values, PIT electronics membership, prices or returns attached.'}
 OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:obj[k] for k in ['query_task_count','query_error_count','report_row_count','correction_exact_none_count','duplicate_or_ambiguous_company_quarter_count','ticker_year_with_rows_count','discovery_current_prior_exact_none_pair_count','outside_discovery_signal_date_pair_count']},ensure_ascii=False)); print('pairs_by_yq',dict(sorted(qpairs.items())))
if __name__=='__main__': main()
