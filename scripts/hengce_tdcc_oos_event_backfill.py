#!/usr/bin/env python3
"""Adapter for frozen historical OOS events onto the existing HENGCE TDCC vessel.

This file does NOT change Monster V1 or TDCC parsing semantics. It reuses
hengce_tdcc_monster_pit_backfill.py's official TDCC endpoint/parser, fixed 51W
calendar, PIT+7 proxy, Big400/Big1000 definitions, raw-response hashing, and
no-forward-fill policy.

Event-level rule for T4 ownership rotation:
- Need >=3 PIT-eligible weekly snapshots to form two ownership intervals.
- If fewer than 3 exist in the existing HENGCE 51W calendar, the event is
  T4_FAIL_CLOSED_INSUFFICIENT_SNAPSHOTS. It is never synthetically filled.
- For eligible events, fetch up to the same 7 snapshots used by the frozen
  Monster targeted backfill.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

import hengce_tdcc_monster_pit_backfill as base

MIN_ROTATION_SNAPSHOTS = 3
MAX_SNAPSHOTS = base.SNAPSHOTS_PER_EVENT


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def csv_text(rows, cols):
    s=io.StringIO(newline='')
    w=csv.DictWriter(s,fieldnames=cols,lineterminator='\n')
    w.writeheader()
    for r in rows:w.writerow({c:r.get(c,'') for c in cols})
    return s.getvalue()


def load_events(path: Path):
    if not path.exists():raise RuntimeError(f'EVENT_FILE_MISSING:{path}')
    d=pd.read_csv(path,dtype={'Ticker':str})
    need={'Date','Ticker'}
    if not need.issubset(d.columns):raise RuntimeError(f'EVENT_FILE_BAD_HEADER:{list(d.columns)}')
    if 'Name' not in d.columns:d['Name']=''
    d=d[['Date','Ticker','Name']].drop_duplicates().copy()
    d['Date']=pd.to_datetime(d['Date'],errors='raise')
    d['Ticker']=d['Ticker'].astype(str)
    return d.sort_values(['Date','Ticker']).reset_index(drop=True)


def plan(events):
    refs=sorted(datetime.strptime(x,'%Y%m%d').date() for x in base.WEEK_DATES)
    required=[]; event_status=[]
    for _,r in events.iterrows():
        ed=r['Date'].date(); cutoff=ed-timedelta(days=base.PIT_LAG_DAYS)
        eligible=[x for x in refs if x<=cutoff]
        selected=eligible[-MAX_SNAPSHOTS:]
        ok=len(selected)>=MIN_ROTATION_SNAPSHOTS
        event_status.append({
            'EventDate':ed.isoformat(),'Ticker':str(r['Ticker']),'Name':str(r['Name']),
            'PITEligibleSnapshotCountIn51W':len(selected),
            'T4Status':'ELIGIBLE' if ok else 'T4_FAIL_CLOSED_INSUFFICIENT_SNAPSHOTS',
        })
        if not ok:continue
        for rd in selected:
            required.append({
                'EventDate':ed.isoformat(),'Ticker':str(r['Ticker']),'Name':str(r['Name']),
                'ReferenceDate':rd.strftime('%Y%m%d'),
                'PITProxyAvailableDate':(rd+timedelta(days=base.PIT_LAG_DAYS)).isoformat(),
            })
    key={(x['EventDate'],x['Ticker'],x['ReferenceDate']) for x in required}
    if len(key)!=len(required):raise RuntimeError('DUPLICATE_EVENT_TICKER_REFERENCE_KEY')
    return required,event_status


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--events',required=True)
    ap.add_argument('--out',required=True)
    a=ap.parse_args()
    event_path=Path(a.events);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    events=load_events(event_path); required,event_status=plan(events)
    retrieved=base.now_tw()

    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    session=requests.Session()
    session.headers.update({
        'User-Agent':'Mozilla/5.0 HENGCE-TDCC-OOS-PIT-BACKFILL/1.0',
        'Referer':base.ENDPOINT,'Accept-Language':'zh-TW,zh;q=0.9,en;q=0.5'})

    rows=[];invalid=[];seen={};written=set(); raw_zip=out/'raw_html.zip'
    with zipfile.ZipFile(raw_zip,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for i,k in enumerate(required,1):
            ticker,ref=k['Ticker'],k['ReferenceDate']; qkey=(ticker,ref)
            print(f'[{i}/{len(required)}] {k["EventDate"]} {ticker} {ref}',flush=True)
            try:
                if qkey in seen:raw,text,sm=seen[qkey]
                else:
                    raw,text,sm=base.fetch_one(session,ticker,ref);seen[qkey]=(raw,text,sm);time.sleep(0.12)
                sha=sha256_bytes(raw); entry=f'{ticker}/{ref}.html'
                if entry not in written:z.writestr(entry,raw);written.add(entry)
                row=dict(k);row.update({
                    'RetrievedAtTaipei':retrieved,
                    'Big400Holders':sm['Big400Holders'],'Big400Shares':sm['Big400Shares'],'Big400Pct':sm['Big400Pct'],
                    'Big1000Holders':sm['Big1000Holders'],'Big1000Shares':sm['Big1000Shares'],'Big1000Pct':sm['Big1000Pct'],
                    'TotalHolders':sm['TotalHolders'],'TotalShares':sm['TotalShares'],
                    'ResponseSHA256':sha,'Source':base.ENDPOINT,'PITAuthority':'HISTORICAL_PIT_PROXY_RESEARCH_ONLY'})
                rows.append(row)
            except Exception as e:
                err=f'{type(e).__name__}:{e}';invalid.append({**k,'error':err});print('INVALID',ticker,ref,err,flush=True)

    summary=out/'tdcc_oos_pit_backfill.csv'
    summary.write_text(csv_text(rows,base.SUMMARY_COLS),encoding='utf-8')
    status_file=out/'event_t4_eligibility.csv'
    status_file.write_text(csv_text(event_status,['EventDate','Ticker','Name','PITEligibleSnapshotCountIn51W','T4Status']),encoding='utf-8')
    eligible_events=sum(x['T4Status']=='ELIGIBLE' for x in event_status)
    fail_events=len(event_status)-eligible_events
    query_status='COMPLETE' if len(rows)==len(required) and not invalid else 'PARTIAL_FAIL_CLOSED'
    manifest={
        'system':'HENGCE','artifact':'TDCC_FROZEN_OOS_TARGETED_HISTORICAL_BACKFILL',
        'status':query_status,'authority':'RESEARCH_BACKFILL_CANDIDATE_NO_LIVE_AUTHORITY',
        'model_authority_created':False,'frozen_model':'MONSTER_BUY_V1','monster_v1_retuned':False,
        'event_file':str(event_path),'event_file_sha256':sha256_bytes(event_path.read_bytes()),
        'event_count':int(len(events)),'eligible_t4_event_count':int(eligible_events),
        'fail_closed_insufficient_snapshot_event_count':int(fail_events),
        'source_owner':'TDCC','source_endpoint':base.ENDPOINT,'retrieved_at_taipei':retrieved,
        'reference_week_source':'existing HENGCE 51W fixed weekly calendar',
        'pit_proxy_rule':f'ReferenceDate + {base.PIT_LAG_DAYS} calendar days <= EventDate',
        'pit_proxy_note':'Retrospective eligibility proxy only; not proof of historical publication timestamp or live authority.',
        'min_snapshots_for_t4_rotation':MIN_ROTATION_SNAPSHOTS,'max_snapshots_per_event':MAX_SNAPSHOTS,
        'required_key_count':len(required),'valid_key_count':len(rows),'invalid_key_count':len(invalid),'invalid':invalid,
        'summary_sha256':sha256_bytes(summary.read_bytes()),'raw_html_zip_sha256':sha256_bytes(raw_zip.read_bytes()),
        'big400_definition':'historical TDCC rows/grades 12+13+14+15 (>=400,001 shares)',
        'big1000_definition':'historical TDCC row/grade 15 (>=1,000,001 shares)',
        'no_forward_fill':True,'technical_fallback':'PROHIBITED',
    }
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:manifest[k] for k in ('status','event_count','eligible_t4_event_count','fail_closed_insufficient_snapshot_event_count','required_key_count','valid_key_count','invalid_key_count')},ensure_ascii=False),flush=True)
    if query_status!='COMPLETE':raise SystemExit(f'FAIL_CLOSED_BACKFILL_INCOMPLETE:{len(rows)}/{len(required)}')

if __name__=='__main__':main()
