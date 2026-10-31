#!/usr/bin/env python3
"""Build HENGCE IF-07 electronic-report metadata index only.

NO accounting values. NO price data. NO forward returns.
Purpose: index official upload timestamps and exact correction-gate status for the
frozen acquisition ticker superset, and determine count-only current/prior pairs.
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
OUT=ROOT/'generated/IF07_METADATA_INDEX_2022_2026.json'
OUT.parent.mkdir(parents=True,exist_ok=True)

UA='Mozilla/5.0 HENGCE-IF07-metadata-index/0.1'
URL='https://doc.twse.com.tw/server-java/t57sb01'
QMAP={'一':1,'二':2,'三':3,'四':4}
RE_PERIOD=re.compile(r'(?P<roc>\d+)\s*年\s*第(?P<q>[一二三四])季')
RE_UPLOAD=re.compile(r'(?P<roc>\d{2,3})/(?P<m>\d{2})/(?P<d>\d{2})\s+(?P<h>\d{2}):(?P<mi>\d{2}):(?P<s>\d{2})')
_tls=threading.local()


def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def sha(b:bytes): return hashlib.sha256(b).hexdigest()

def session():
    if not hasattr(_tls,'s'):
        s=requests.Session(); s.headers.update({'User-Agent':UA,'Accept-Language':'zh-TW,zh;q=0.9'})
        _tls.s=s
    return _tls.s

def parse_upload(s:str):
    m=RE_UPLOAD.fullmatch(s.strip())
    if not m: return None
    return dt.datetime(int(m['roc'])+1911,int(m['m']),int(m['d']),int(m['h']),int(m['mi']),int(m['s']))

def fetch_ticker(ticker:str)->dict[str,Any]:
    p={'step':'1','colorchg':'1','co_id':ticker,'year':'','seamon':'','mtype':'A'}
    last_err=None
    for attempt in range(3):
        try:
            r=session().get(URL,params=p,timeout=45)
            r.encoding='big5'
            soup=BeautifulSoup(r.text,'lxml')
            rows=[]
            for tr in soup.find_all('tr'):
                cells=[' '.join(td.stripped_strings) for td in tr.find_all(['td','th'])]
                if not cells or ticker not in cells: continue
                if len(cells)<11: continue
                if cells[5] != 'IFRSs合併財報': continue
                pm=RE_PERIOD.search(cells[1])
                if not pm: continue
                fy=int(pm['roc'])+1911; q=QMAP[pm['q']]
                if fy<2022 or fy>2026: continue
                up=parse_upload(cells[9])
                rows.append({
                    'ticker':ticker,'fiscal_year':fy,'quarter':q,
                    'period_text':cells[1],'report_type':cells[5],'file_name':cells[7],
                    'file_size_text':cells[8],'upload_text':cells[9],
                    'upload_ts_taipei':up.isoformat() if up else None,
                    'correction_field':cells[10],
                    'correction_exact_none':cells[10]=='無',
                })
            return {'ticker':ticker,'http_status':r.status_code,'bytes':len(r.content),'sha256':sha(r.content),'rows':rows,'error':None}
        except Exception as e:
            last_err=f'{type(e).__name__}: {e}'
            time.sleep(1.0*(attempt+1))
    return {'ticker':ticker,'http_status':None,'bytes':None,'sha256':None,'rows':[],'error':last_err}

def resolve_signal_date(upload_iso:str|None,sessions:list[dt.date]):
    if not upload_iso: return None,'UNPARSEABLE_UPLOAD_TS'
    x=dt.datetime.fromisoformat(upload_iso)
    d=x.date(); close=dt.time(13,30,0)
    sess=set(sessions)
    if d in sess and x.time()<close:
        return d.isoformat(),None
    for sd in sessions:
        if sd>d:
            return sd.isoformat(),None
    return None,'TRADING_SESSION_COVERAGE_BLOCKED'

def main():
    tickers=json.loads(UNION.read_text(encoding='utf-8'))['ticker_union']
    sobj=json.loads(SESS.read_text(encoding='utf-8'))
    sessions=[]
    for y in range(2022,2027):
        sessions.extend(dt.date.fromisoformat(x) for x in sobj['years'][str(y)]['dates'])
    sessions=sorted(set(sessions))

    results=[]
    with cf.ThreadPoolExecutor(max_workers=5) as ex:
        futs={ex.submit(fetch_ticker,t):t for t in tickers}
        for i,f in enumerate(cf.as_completed(futs),1):
            results.append(f.result())
            if i%50==0: print(f'metadata {i}/{len(tickers)}',flush=True)
    results.sort(key=lambda x:x['ticker'])

    rows=[]
    errors=[]
    for rr in results:
        if rr['error']: errors.append({'ticker':rr['ticker'],'error':rr['error']})
        rows.extend(rr['rows'])
    rows.sort(key=lambda r:(r['ticker'],r['fiscal_year'],r['quarter'],r['upload_ts_taipei'] or ''))

    # Detect duplicates before any judgment.
    bykey=defaultdict(list)
    for r in rows: bykey[(r['ticker'],r['fiscal_year'],r['quarter'])].append(r)
    dup_keys={f'{t}:{y}Q{q}':v for (t,y,q),v in bykey.items() if len(v)!=1}

    # Unique exact-none report map only.
    usable={}
    for k,v in bykey.items():
        if len(v)==1 and v[0]['correction_exact_none'] and v[0]['upload_ts_taipei']:
            usable[k]=v[0]

    current_pairs=[]
    for (t,y,q),cur in sorted(usable.items()):
        if y<2023 or y>2026: continue
        prev=usable.get((t,y-1,q))
        if not prev: continue
        signal_date,signal_err=resolve_signal_date(cur['upload_ts_taipei'],sessions)
        # Formal validation cutoff applies to signal_date, but membership will be checked later.
        if signal_date and signal_date>'2026-10-31':
            signal_date=None; signal_err='AFTER_RESEARCH_CUTOFF'
        current_pairs.append({
            'ticker':t,'fiscal_year':y,'quarter':q,
            'current_file':cur['file_name'],'current_upload_ts_taipei':cur['upload_ts_taipei'],
            'prior_file':prev['file_name'],'prior_upload_ts_taipei':prev['upload_ts_taipei'],
            'signal_date':signal_date,'signal_date_error':signal_err,
            'pit_electronics_membership_checked':False,
        })

    c_yearq=Counter(f"{r['fiscal_year']}Q{r['quarter']}" for r in rows)
    c_exact=Counter(f"{r['fiscal_year']}Q{r['quarter']}" for r in rows if r['correction_exact_none'])
    c_pairs=Counter(f"{r['fiscal_year']}Q{r['quarter']}" for r in current_pairs)
    c_signal=Counter(f"{r['fiscal_year']}Q{r['quarter']}" for r in current_pairs if r['signal_date'])
    corr_values=Counter(r['correction_field'] for r in rows)

    obj={
        'system':'HENGCE','artifact':'IF07_METADATA_INDEX_2022_2026','generated_at_utc':now(),
        'contains_accounting_values':False,'contains_price_or_forward_return_data':False,
        'acquisition_ticker_count':len(tickers),'ticker_fetch_error_count':len(errors),'ticker_fetch_errors':errors,
        'report_row_count':len(rows),'report_rows_by_year_quarter':dict(sorted(c_yearq.items())),
        'correction_exact_none_count':sum(r['correction_exact_none'] for r in rows),
        'correction_exact_none_by_year_quarter':dict(sorted(c_exact.items())),
        'correction_field_value_counts':dict(corr_values),
        'duplicate_or_ambiguous_company_quarter_count':len(dup_keys),'duplicate_or_ambiguous_keys':dup_keys,
        'current_prior_exact_none_pair_count':len(current_pairs),'pair_count_by_year_quarter':dict(sorted(c_pairs.items())),
        'signal_date_resolved_pair_count':sum(bool(r['signal_date']) for r in current_pairs),
        'signal_date_resolved_by_year_quarter':dict(sorted(c_signal.items())),
        'signal_date_coverage_blocked_count':sum(r['signal_date_error']=='TRADING_SESSION_COVERAGE_BLOCKED' for r in current_pairs),
        'metadata_rows':rows,
        'current_prior_pairs':current_pairs,
        'boundary':'No PIT electronics membership and no accounting-value extraction has been performed yet. No returns are attached.',
    }
    OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:obj[k] for k in ['acquisition_ticker_count','ticker_fetch_error_count','report_row_count','correction_exact_none_count','current_prior_exact_none_pair_count','signal_date_resolved_pair_count','signal_date_coverage_blocked_count']},ensure_ascii=False))
if __name__=='__main__': main()
