#!/usr/bin/env python3
"""HENGCE FinMind full-market TDCC historical weekly YEAR collection.

Only read paid FinMind data using existing FINMIND_TOKEN secret.
Licensed raw data remain in short-lived Actions artifact and are moved
into the user's private Library; never git-commit or publish raw data.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from hengce_finmind_tdcc_historical_backfill import fetch,validate,sha256

API='https://api.finmindtrade.com/api/v4/data'
SOURCE='TaiwanStockHoldingSharesPer'
FIELDS=('date','stock_id','HoldingSharesLevel','people','percent','unit')

def get_full_market(token, refdate):
    p=urllib.parse.urlencode({'dataset':SOURCE,'start_date':refdate})
    req=urllib.request.Request(API+'?'+p,headers={
        'Authorization':'Bearer '+token,
        'Accept':'application/json',
        'User-Agent':'HENGCE-FinMind-TDCC-Historical-Year-Research/1.0'
    })
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req,timeout=180) as response:
                raw=response.read()
            break
        except urllib.error.HTTPError as e:
            if e.code in (429,500,502,503,504) and attempt<3:
                time.sleep(10*(attempt+1));continue
            raise RuntimeError('FINMIND_HTTP_'+str(e.code)) from None
        except Exception as e:
            if attempt<3:
                time.sleep(4*(attempt+1));continue
            raise RuntimeError('FINMIND_NETWORK_'+type(e).__name__) from None
    obj=json.loads(raw)
    if not isinstance(obj,dict) or obj.get('status')!=200 or not isinstance(obj.get('data'),list):
        raise RuntimeError('FINMIND_STATUS_OR_SCHEMA_BLOCKED_'+str(obj.get('status') if isinstance(obj,dict) else 'INVALID'))
    rows=obj['data']
    if not rows:
        raise RuntimeError('NO_FULL_MARKET_DATA_FOR_VERIFIED_DATE_'+refdate)
    keys=set()
    tickers=set()
    metadata_anomalies=[]
    for row in rows:
        if not isinstance(row,dict) or any(k not in row for k in FIELDS):
            raise RuntimeError('MISSING_REQUIRED_FIELD_'+refdate)
        d=str(row['date']);s=str(row['stock_id']);lvl=str(row['HoldingSharesLevel'])
        if d!=refdate:
            raise RuntimeError('SOURCE_DATE_MISMATCH_'+refdate+'_'+d)
        key=(d,s,lvl)
        if key in keys:
            raise RuntimeError('DUPLICATE_DATE_SECURITY_LEVEL_'+refdate)
        keys.add(key);tickers.add(s)
        try:
            p=float(row['percent']);person=int(row['people']);unit=int(row['unit'])
        except (ValueError,TypeError):
            raise RuntimeError('BAD_NUMERIC_'+refdate)
        reconciliation='差異數調整' in lvl
        summary_row=lvl.strip().lower() in ('total','合計','總計')
        # TDCC holding tiers must have valid unsigned counts and proportions.
        # Vendor-provided total rows may report 101% or other accounting artifacts.
        # These are NOT holding tiers, are preserved verbatim, and are audited
        # separately; never feed them into Big400 / Big1000 aggregations.
        if person<0 or (not (reconciliation or summary_row) and (p<0 or p>100 or unit<0)):
            raise RuntimeError('BAD_PERCENT_PEOPLE_UNIT_'+refdate)
        if summary_row and (p<0 or p>100 or unit<0):
            metadata_anomalies.append({'date':refdate,'ticker':s,'level':lvl,'percent':p,'unit_negative':unit<0})
    if len(tickers)<1000:
        raise RuntimeError('IMPLAUSIBLE_STOCK_UNIVERSE_'+refdate)
    return rows,{'raw_sha256':sha256(raw),'source_bytes':len(raw),
                 'tier_rows':len(rows),'security_count':len(tickers),'non_tier_summary_anomalies':metadata_anomalies[:100],'non_tier_summary_anomaly_count':len(metadata_anomalies)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--year',type=int,required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--limit',type=int,default=0,help='0=all weekly dates; positive=pilot number')
    a=ap.parse_args()
    if not 2018<=a.year<=2025 or a.limit<0:raise SystemExit('INVALID_YEAR_OR_LIMIT')
    end=f'{a.year}-12-31' if a.year<2025 else '2025-10-30'
    start=f'{a.year}-01-01'
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    receipt={'schema':'HENGCE_TDCC_FINMIND_FULL_MARKET_YEAR_V1',
             'year':a.year,'period':[start,end],
             'source':SOURCE,'source_authority':'VENDOR_FINMIND_DERIVED_TDCC_NOT_OFFICIAL_FIRST_OBSERVED',
             'source_time_query_semantics':'one valid weekly start_date, no end_date or stock_id',
             'created_at_utc':datetime.now(timezone.utc).isoformat(),
             'data_license':'licensed vendor content not distributed in public Git',
             'no_canonical_mutation':True,'research_only':True,
             'no_trading_authority':True,'no_lookahead_proven':False,
             'status':'PENDING','snapshots':[]}
    try:
        token=os.getenv('FINMIND_TOKEN','').strip()
        if not token:raise RuntimeError('FINMIND_TOKEN_MISSING')
        sentinel,metadata=fetch(token,'2330',start,end)
        dates=sorted({str(r['date']) for r in sentinel})
        if not dates or min(dates)<start or max(dates)>end or len(dates)<35:
            raise RuntimeError('SENTINEL_CALENDAR_NOT_COVERED')
        receipt['sentinel_stock']='2330'
        receipt['verified_weekly_calendar_count']=len(dates)
        receipt['calendar']=dates
        target=dates[:a.limit] if a.limit else dates
        receipt['attempted_snapshots']=len(target)
        for index,ds in enumerate(target):
            rows,meta=get_full_market(token,ds)
            raw=json.dumps(rows,ensure_ascii=False,separators=(',',':'),sort_keys=True).encode('utf-8')
            compressed=gzip.compress(raw,compresslevel=6,mtime=0)
            name=f'{ds}.json.gz'
            (out/name).write_bytes(compressed)
            receipt['snapshots'].append(dict(reference_date=ds,file=name,
                gzip_sha256=sha256(compressed),normalized_json_sha256=sha256(raw),
                first_observed_utc=datetime.now(timezone.utc).isoformat(),**meta))
            if index%5==0 or index+1==len(target):
                print('HENGCE_TDCC_FINMIND_YEAR',a.year,'progress',index+1,'/',len(target),
                      'stocks',meta['security_count'],'tier_rows',meta['tier_rows'],flush=True)
            time.sleep(1.25)
        receipt.update(status='PASS',snapshots_completed=len(receipt['snapshots']),
            total_tier_rows=sum(x['tier_rows'] for x in receipt['snapshots']),
            finished_at_utc=datetime.now(timezone.utc).isoformat())
    except Exception as e:
        receipt['status']='BLOCKED_FAIL_CLOSED'
        receipt['error_type']=type(e).__name__
        receipt['error']=str(e).splitlines()[0][:160]
        print('HENGCE_FINMIND_YEAR_ERROR',receipt['error'],flush=True)
    finally:
        (out/'manifest.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('HENGCE_FINMIND_YEAR_STATUS',a.year,receipt['status'],
              'completed',len(receipt['snapshots']),'of',receipt.get('attempted_snapshots'),flush=True)
    return 0 if receipt['status']=='PASS' else 2

if __name__=='__main__':raise SystemExit(main())
