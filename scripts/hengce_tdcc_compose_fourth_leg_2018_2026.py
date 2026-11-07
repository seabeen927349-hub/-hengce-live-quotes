#!/usr/bin/env python3
"""HENGCE: compose historical TDCC/FinMind with OFFICIAL weekly ownership (fourth-leg).

This creates a SEPARATE weekly point-in-time-snapshot sidecar linked to the existing
daily three-leg mother, NOT a daily forward-fill nor a trading-approved fourth signal.

Immutable source precedence:
  official current TDCC > official stock/date 2025/2026 > official archived
  continuation > historical retrospective FinMind.
Historical first-observation / publication time is NEVER inferred.
Includes all 4-digit security candidates; a PIT ordinary-stock universe mask must
be applied separately at strategy-research time.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,io,json,re
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path

FOUR=re.compile(r'^[1-9]\d{3}$')
DATE=re.compile(r'^20\d{6}$')
COLS=[
    'SnapshotDate','Ticker','Big400Pct','Big1000Pct','Big400Holders',
    'Big400Shares','Big1000Holders','Big1000Shares',
    'TotalHolders','TotalShares','SourceTier','SourceKind',
    'SourcePath','RawSHA256','TierStatus','PITReleaseStatus','ConflictFlag',
]
RAW_EXPECTED_HIST_STOCKWEEKS=858654
RAW_EXPECTED_HIST_VALID=858236
RAW_EXPECTED_HIST_MISSING=418
HISTORICAL_PIT='RETROSPECTIVE_PUBLISH_DATE_NOT_VERIFIED'
OFFICIAL_PIT='FIRST_OBSERVED_CANNOT_ASSUME_ON_REFERENCE_DATE'
PROVENANCE=[
    ['FINMIND_VENDOR_HISTORICAL',10],
    ['TDCC_OFFICIAL_HISTORICAL_2025_TAIL',80],
    ['TDCC_OFFICIAL_HISTORICAL_2026_JAN_APR',90],
    ['TDCC_VERIFIED_CONTINUATION_2026',70],
    ['TDCC_OFFICIAL_CURRENT',100],
]
RANK=dict(PROVENANCE)
HOME=Path(__file__).resolve().parents[1]

def sha(blob:bytes)->str:return hashlib.sha256(blob).hexdigest()

def enforce_checksum(path:Path,expect:str,role:str)->None:
    if not path.exists():raise RuntimeError(f'MISSING_{role}_{path}')
    actual=sha(path.read_bytes())
    if actual!=expect:raise RuntimeError(f'SHA_MISMATCH_{role}: {actual} != {expect}')

def normal_date(ds)->str:
    s=str(ds or '').strip().replace('-','')
    if not DATE.fullmatch(s):raise ValueError('INVALID_SNAPSHOT_DATE:'+s[:40])
    return s

def num_int(s):
    s=str(s if s is not None else '').replace(',','').strip()
    if not s:return None
    return int(float(s))

def num_float(s):
    s=str(s if s is not None else '').replace(',','').strip()
    if not s:return None
    return float(s)

def get_obj(path):
    return json.loads(path.read_text(encoding='utf-8'))

def open_rows(path):
    if path.suffix=='.gz':
        with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:
            yield from csv.DictReader(f)
    else:
        with path.open(encoding='utf-8-sig',newline='') as f:
            yield from csv.DictReader(f)

def normalized(row,kind,source_path):
    date=normal_date(row['SnapshotDate'])
    ticker=str(row['Ticker']).strip()
    if not FOUR.fullmatch(ticker):return None
    old=row.get('TierSchema') or row.get('TierStatus') or ''
    values={}
    for name in ('Big400Pct','Big1000Pct'):
        values[name]=num_float(row.get(name))
    for name in ('Big400Holders','Big400Shares','Big1000Holders','Big1000Shares','TotalHolders','TotalShares'):
        values[name]=num_int(row.get(name))
    required=('Big400Pct','Big1000Pct','Big400Holders','Big400Shares','Big1000Holders','Big1000Shares')
    valid=all(values[x] is not None for x in required)
    if old.startswith('MISSING_OR_INVALID'):valid=False
    if valid:
        a,b=values['Big400Pct'],values['Big1000Pct']
        if not (0<=b<=a<=100.01 and values['Big400Holders']>=values['Big1000Holders']>=0
            and values['Big400Shares']>=values['Big1000Shares']>=0):
            raise RuntimeError(f'INVALID_OWNERSHIP_METRICS_{date}_{ticker}_{kind}')
    for f in required:
        if not valid:values[f]=None
    status='VALID' if valid else 'SOURCE_TIER_INVALID_NULL'
    source_sha=row.get('RawSHA256') or row.get('raw_sha256') or ''
    pit=HISTORICAL_PIT if kind=='FINMIND_VENDOR_HISTORICAL' else OFFICIAL_PIT
    return {**{'SnapshotDate':date,'Ticker':ticker},**values,
        'SourceTier':row.get('SourceTier') or kind,
        'SourceKind':kind,'SourcePath':source_path,'RawSHA256':source_sha,
        'TierStatus':status,'PITReleaseStatus':pit,'ConflictFlag':''}

def signature(r):
    return tuple(r.get(k) for k in ('Big400Pct','Big1000Pct','Big400Holders','Big400Shares','Big1000Holders','Big1000Shares'))

def sig_mismatch(a,b):
    sa,sb=signature(a),signature(b)
    for i,(u,v) in enumerate(zip(sa,sb)):
        if u is None or v is None:continue
        tol=.1 if i<2 else 0
        if abs(u-v)>tol:return True
    return False

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--historical-dir',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--mother-library-path',default='/HENGCE_CANONICAL/RESEARCH/HIST_FULL_MARKET_MOTHER_2018_2026_20261107/HENGCE_FULL_MARKET_MOTHER_RESEARCH_2018_2026.csv.gz')
    ap.add_argument('--mother-sha256',default='b3275f8d58779fbec864a05066414d27e80cef8a68a76a08051f93808f1f8c93')
    args=ap.parse_args()
    hist=Path(args.historical_dir);out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    receipts={
        'system':'HENGCE','artifact':'HENGCE_FOURTH_LEG_2018_2026_WEEKLY_RESEARCH_MOTHER',
        'schema':'HENGCE_FOUR_LEG_WEEKLY_V1',
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'status':'BLOCKED','daily_mother_mutated':False,
        'mother_library_path':args.mother_library_path,'mother_sha256_expected':args.mother_sha256,
        'daily_mother_qa_rows':2111682,
        'linked_as':'WEEKLY_SIDECAR_DATE_TICKER_NO_DAILY_FORWARD_FILL',
        'source_priority':[k for k,p in sorted(PROVENANCE,key=lambda x:-x[1])],
        'historical_publication_time_confirmed':False,
        'ordinary_stock_pit_mask_confirmed':False,
        'historical_data_promoted_to_trading_authority':False,
        'weekly_new_data_source':'OWNERSHIP_TDCC_OFFICIAL_PROVENANCE_CANONICAL_VESSEL',
        'weekly_new_data_repo_path':'ownership/tdcc/{SnapshotDate}/tdcc_ownership_4d.csv',
        'notes':['The 2018-2025 FinMind history is retrospective and not an authoritative publication-time sequence.',
                 '2026 official current sources carry first-observed metadata in separate receipts.',
                 'Four-digit codes can include non-common-stock securities; historical PIT ordinary-stock mask remains required.',
                 'No weekly values are daily-filled; missing 418 historical tier records remain NULL unless higher-priority source provides an independent observation.'],
        'source_counts':{},'year_counts':{},'conflicts':[]
    }
    selected={};src_counts=Counter();overlaps=Counter();conflict_examples=[]
    try:
        panel=hist/'HENGCE_TDCC_BIG400_BIG1000_RESEARCH_2018_2025.csv.gz'
        qa=hist/'HENGCE_TDCC_RESEARCH_PANEL_AUDIT.json'
        audit=get_obj(qa)
        if audit.get('status')!='PASS' or audit.get('total_4digit_stock_week_rows')!=RAW_EXPECTED_HIST_STOCKWEEKS:
            raise RuntimeError('HIST_RESEARCH_QA_NOT_MATCHED')
        if audit.get('total_valid_derived_rows')!=RAW_EXPECTED_HIST_VALID or audit.get('total_invalid_rows')!=RAW_EXPECTED_HIST_MISSING:
            raise RuntimeError('HIST_VALID_MISSING_QA_NOT_MATCHED')
        enforce_checksum(panel,audit['output_file_sha256'],'HIST_PANEL')
        loaded=Counter()
        def ingest(path,kind,min_date=None,max_date=None,manifest=None,sha_field=None):
            if manifest and sha_field:
                man=get_obj(manifest)
                if man.get('status')!='COMPLETE':raise RuntimeError(f'SOURCE_MANIFEST_NOT_COMPLETE_{kind}')
                enforce_checksum(path,man[sha_field],kind)
            n=0
            for line in open_rows(path):
                r=normalized(line,kind,str(path.relative_to(HOME)) if path.is_relative_to(HOME) else path.name)
                if r is None:continue
                d=r['SnapshotDate']
                if min_date and d<min_date:continue
                if max_date and d>max_date:continue
                n+=1
                key=(d,r['Ticker'])
                old=selected.get(key)
                if old is not None:
                    overlaps[(old['SourceKind'],kind)]+=1
                    if sig_mismatch(old,r):
                        if len(conflict_examples)<300:
                            conflict_examples.append({'date':d,'ticker':r['Ticker'],'low_source':old['SourceKind'],'candidate':kind})
                    if RANK[kind]>RANK[old['SourceKind']] or (RANK[kind]==RANK[old['SourceKind']] and r['TierStatus']=='VALID' and old['TierStatus']!='VALID'):
                        r['ConflictFlag']='SOURCE_VALUE_CONFLICT' if sig_mismatch(old,r) else ''
                        selected[key]=r
                else:selected[key]=r
            loaded[kind]+=n
            if n<1000:raise RuntimeError(f'UNEXPECTED_LOW_SOURCE_ROWS_{kind}:{n}')
            print('HENGCE_FOURTH_LEG_SOURCE',kind,'rows',n,flush=True)
        ingest(panel,'FINMIND_VENDOR_HISTORICAL',min_date='20180101',max_date='20251030')
        if loaded['FINMIND_VENDOR_HISTORICAL']!=RAW_EXPECTED_HIST_STOCKWEEKS:
            raise RuntimeError('FINMIND_HIST_KEY_COVERAGE_NOT_EXPECTED')
        tail=HOME/'ownership/tdcc/backfill_candidate/full_market_2025_tail'
        ingest(tail/'tdcc_2025_tail_full_market_backfill.csv',
               'TDCC_OFFICIAL_HISTORICAL_2025_TAIL',min_date='20251031',max_date='20251231',
               manifest=tail/'manifest.json',sha_field='summary_sha256')
        jan=HOME/'ownership/tdcc/backfill_candidate/full_market_2026_jan_apr'
        ingest(jan/'tdcc_2026_jan_apr_full_market_backfill.csv',
               'TDCC_OFFICIAL_HISTORICAL_2026_JAN_APR',min_date='20260101',max_date='20260424',
               manifest=jan/'manifest.json',sha_field='summary_sha256')
        cont=HOME/'ownership/tdcc/consolidated_candidate'
        mcont=get_obj(cont/'MANIFEST.json')
        enforce_checksum(cont/'tdcc_fourth_leg_best_available.csv.gz',mcont['output_sha256_gzip'],'CONTINUATION_2026')
        ingest(cont/'tdcc_fourth_leg_best_available.csv.gz','TDCC_VERIFIED_CONTINUATION_2026',
               min_date='20260430',max_date='20261022')
        for ds in ['20261022','20261030','20261106']:
            p=HOME/f'ownership/tdcc/{ds}/tdcc_ownership_4d.csv'
            m=HOME/f'ownership/tdcc/{ds}/receipt.json'
            if not p.exists() or not m.exists():
                # 20261022 exists in canonical library but may not have official
                # standalone file in repository: only skip this optional overlap.
                if ds=='20261022':continue
                raise RuntimeError(f'MISSING_OFFICIAL_LIVE_RECEIPT_{ds}')
            x=get_obj(m)
            if x.get('status')!='COMPLETE' or x.get('snapshot_date')!=ds:
                raise RuntimeError('UNVERIFIED_OFFICIAL_CURRENT_'+ds)
            enforce_checksum(p,x['summary_sha256'],'TDCC_OFFICIAL_CURRENT_'+ds)
            ingest(p,'TDCC_OFFICIAL_CURRENT',min_date=ds,max_date=ds)
        dates=sorted({d for d,t in selected})
        if dates[0]>'20180131' or dates[-1]<'20261106':
            raise RuntimeError(f'DATE_RANGE_NOT_COMPLETE_{dates[0]}_{dates[-1]}')
        if len(dates)<450:raise RuntimeError(f'SNAPSHOT_COUNT_LOW_{len(dates)}')
        result=out/'HENGCE_TDCC_FOURTH_LEG_WEEKLY_2018_2026.csv.gz'
        invalid=0
        by_year=defaultdict(lambda:Counter())
        with gzip.open(result,'wt',encoding='utf-8',newline='',compresslevel=6) as f:
            w=csv.DictWriter(f,fieldnames=COLS,lineterminator='\n')
            w.writeheader()
            for key in sorted(selected):
                r=selected[key]
                w.writerow({x:r.get(x) for x in COLS})
                year=r['SnapshotDate'][:4]
                by_year[year]['rows']+=1
                if r['TierStatus']!='VALID':
                    invalid+=1;by_year[year]['invalid']+=1
                else:by_year[year]['valid']+=1
        expected_invalid=RAW_EXPECTED_HIST_MISSING
        if invalid>expected_invalid+100:
            raise RuntimeError(f'FOURTH_LEG_INVALID_EXCEEDS_EXPECTED_{invalid}')
        receipts.update(status='PASS_RESEARCH_FOURTH_LEG_INTEGRATED',total_rows=len(selected),
            valid_rows=len(selected)-invalid,invalid_or_null_rows=invalid,
            snapshot_count=len(dates),first_snapshot=dates[0],last_snapshot=dates[-1],
            source_counts=dict(loaded),source_selection_counts=dict(Counter(x['SourceKind'] for x in selected.values())),
            year_counts={y:dict(q) for y,q in sorted(by_year.items())},
            overlap_counts={str(k):v for k,v in overlaps.items()},conflict_count=len(conflict_examples),
            conflicts=conflict_examples[:100],output_file=result.name,output_sha256=sha(result.read_bytes()))
        if conflict_examples:
            receipts['status']='PASS_WITH_SOURCE_CONFLICTS_QUARANTINED'
        # A stable pointer contract for HENGCE three-leg mother + fourth-leg sidecar.
        pointer={
            'schema':'HENGCE_FOUR_LEG_MOTHER_BINDING_V1',
            'status':receipts['status'],
            'three_leg_daily_mother':{'library_path':args.mother_library_path,'sha256':args.mother_sha256,
                                     'rows':2111682,'date_range':['2018-01-02','2026-11-06']},
            'fourth_leg_weekly':{'file':result.name,'sha256':receipts['output_sha256'],
                                 'rows':len(selected),'snapshots':len(dates),
                                 'date_range':[dates[0],dates[-1]],
                                 'join_key':['SnapshotDate','Ticker'],
                                 'join_mode':'explicit_weekly_asof_release_gated_only'},
            'weekly_official_vessel':{'repo':'seabeen927349-hub/-hengce-live-quotes',
                                      'workflow':'.github/workflows/hengce-tdcc-ownership-daily.yml',
                                      'source':'https://opendata.tdcc.com.tw/getOD.ashx?id=1-5',
                                      'future_weekly_updates_not_automatically_backdated':True},
            'retrospective_history_requires_publication_lag_sensitivity':True,
            'daily_ffill_disabled':True,'ordinary_stock_pit_filter_required':True,
            'trading_authority':False}
        (out/'HENGCE_FOUR_LEG_MOTHER_BINDING.json').write_text(
            json.dumps(pointer,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('HENGCE_FOUR_LEG_FINAL',receipts['status'],len(selected),'weeks',len(dates),'nulls',invalid,flush=True)
    except Exception as e:
        receipts['status']='BLOCKED_FAIL_CLOSED'
        receipts['error_type']=type(e).__name__
        receipts['blocker']=str(e)[:500]
        print('HENGCE_FOUR_LEG_ERROR',receipts['blocker'],flush=True)
    finally:
        (out/'HENGCE_FOURTH_LEG_INTEGRATION_AUDIT.json').write_text(
            json.dumps(receipts,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return 0 if receipts['status'].startswith('PASS') else 2

if __name__=='__main__':raise SystemExit(main())
