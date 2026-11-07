#!/usr/bin/env python3
"""HENGCE FinMind TDCC history: bounded shard, never production, never Git-push raw paid data.

FinMind data are held only in temporary GitHub Actions artifacts (1-day retention)
and moved by the authorized researcher to private HENGCE Library.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,os,re,sys,time
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from hengce_finmind_tdcc_historical_backfill import fetch,validate,write_verified,FinMindAccessError,sha256

PARENT=ROOT/'ownership/tdcc/consolidated_candidate/tdcc_fourth_leg_best_available.csv.gz'
PARENT_SHA='d10a3576e09f42041135dae3884f59c73e555c05ce23e524131feee94f1e8b8f'
UNION_SHA='70229d9b1bcef321deaad73b96fcb65c84227e30d173cd0b20a7e7e524a52936'
RESEARCH_BRANCH='research/tdcc-finmind-historical-backfill-20261107'

def load_universe():
    if sha256(PARENT.read_bytes())!=PARENT_SHA: raise RuntimeError('PARENT_SHA_MISMATCH')
    with gzip.open(PARENT,'rt',encoding='utf-8',newline='') as f:
        codes=sorted({str(r.get('Ticker','')).strip() for r in csv.DictReader(f)})
    if len(codes)!=3091 or any(re.fullmatch(r'[1-9]\\d{3}',s) is None for s in codes):
        raise RuntimeError('CANDIDATE_UNIVERSE_INVALID')
    if sha256(('Ticker\\n'+'\\n'.join(codes)+'\\n').encode())!=UNION_SHA:
        raise RuntimeError('CANDIDATE_UNION_SHA_MISMATCH')
    return codes

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--offset',type=int,required=True)
    ap.add_argument('--count',type=int,default=75)
    ap.add_argument('--start',default='2018-01-01')
    ap.add_argument('--end',default='2025-10-30')
    ap.add_argument('--out',required=True)
    a=ap.parse_args()
    if not (0<=a.offset<3091 and 1<=a.count<=100):
        raise SystemExit('INVALID_CHUNK')
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    receipt={
      'artifact':'HENGCE_FINMIND_TDCC_HISTORY_SHARD_V1',
      'status':'PENDING','offset':a.offset,'requested_count':a.count,
      'start':a.start,'end':a.end,'source':'FinMind TaiwanStockHoldingSharesPer',
      'source_scope':'BACKER_AUTHENTICATED_HISTORICAL_PER_STOCK',
      'first_observed_at_utc':datetime.now(timezone.utc).isoformat(),
      'source_publication_timestamp_verified':False,
      'official_tdcc_original_source':False,
      'no_canonical_mutation':True,'research_only':True,'trading_authority':False,
      'no_imputation':True,'raw_data_not_committed_to_public_repository':True,
      'records':[]
    }
    try:
        token=os.environ.get('FINMIND_TOKEN','').strip()
        if not token:raise FinMindAccessError('FINMIND_TOKEN_MISSING')
        codes=load_universe()
        selected=codes[a.offset:a.offset+a.count]
        receipt['selected_tickers']=selected
        # First verify paid historical data on a known long-listed stock.
        sentinel,_=fetch(token,'2330','2018-01-01','2018-03-31')
        if len(sentinel)<100:raise FinMindAccessError('HISTORICAL_LICENSE_SENTINEL_FAILED')
        total=0; valid=0; empty=0
        for i,symbol in enumerate(selected):
            data,transport=fetch(token,symbol,a.start,a.end)
            stats=validate(data,symbol,a.start,a.end)
            if data:
                basename=f'finmind_{symbol}_{a.start}_{a.end}.csv.gz'
                dgst=write_verified(symbol,data,out/basename)
                record={'ticker':symbol,'status':'PASS','name':basename,'sha256':dgst,
                        'rows':stats['rows'],'snapshots':stats['snapshots'],
                        'first':stats['first_snapshot'],'last':stats['last_snapshot'],
                        'adjustment_rows':stats['accounting_adjustment_rows'],
                        'raw_json_sha256':transport['raw_json_sha256']}
                total+=len(data);valid+=1
            else:
                record={'ticker':symbol,'status':'NO_DATA_RETURNED','rows':0,'snapshots':0,
                        'raw_json_sha256':transport['raw_json_sha256']}
                empty+=1
            receipt['records'].append(record)
            if i==0 or (i+1)%10==0 or i+1==len(selected):
                print('HENGCE_FINMIND_SHARD_PROGRESS',i+1,'/',len(selected),'valid',valid,'no_data',empty,flush=True)
            time.sleep(.8)
        if valid==0:raise RuntimeError('NO_VALID_STOCK_IN_SHARD')
        receipt.update(status='PASS_RESEARCH_CANDIDATE',selected_count=len(selected),
            valid_stocks=valid,no_data_stocks=empty,total_tier_rows=total,
            completed_at_utc=datetime.now(timezone.utc).isoformat())
    except Exception as e:
        receipt.update(status='BLOCKED_FAIL_CLOSED',error_type=type(e).__name__,
            blocker=str(e).splitlines()[0][:180])
    finally:
        (out/'manifest.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\\n',encoding='utf-8')
        print('HENGCE_FINMIND_SHARD_RESULT',receipt['status'],
              'valid',receipt.get('valid_stocks'),'rows',receipt.get('total_tier_rows'),flush=True)
    return 0 if receipt['status']=='PASS_RESEARCH_CANDIDATE' else 2

if __name__=='__main__':raise SystemExit(main())
