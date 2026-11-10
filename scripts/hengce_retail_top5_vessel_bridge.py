#!/usr/bin/env python3
"""READ-ONLY original-vessel -> V2.2 input schema lineage and capability bridge.

This is DATA PREPARATION, not a selector. No FinMind/Fugle row is promoted to
canonical EOD/TDCC, and no official V2.2 bundled SHA pin is bypassed. Files
remain isolated under an explicit output directory, never in original vessels.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TW = ZoneInfo('Asia/Taipei')
TICKER = re.compile(r'[1-9][0-9]{3}\Z')
DAILY_FIELDS = ['Date','Ticker','Close','Volume','Turnover']
CHIP_FIELDS = ['SnapshotDate','Ticker','HolderLe10Lots','RetailPeopleValid']

class DataBlocked(Exception): pass

def js(path):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError) as e: raise DataBlocked(f'UNREADABLE_JSON:{path}:{type(e).__name__}') from e

def sha(data):return hashlib.sha256(data).hexdigest()

def eod_digest(files):
    h=hashlib.sha256()
    for p in sorted(files):
        h.update(p.name.encode());h.update(b'\0');h.update(p.read_bytes());h.update(b'\0')
    return h.hexdigest()

def parse_number(s, *, integral=False, optional=False):
    t=str(s if s is not None else '').strip().replace(',','')
    if t in ('','--','-') and optional:return None
    try:v=float(t)
    except ValueError:raise DataBlocked('NON_NUMERIC_OBSERVATION')
    if not math.isfinite(v) or v<0 or (integral and not v.is_integer()):raise DataBlocked('INVALID_NUMERIC_OBSERVATION')
    return int(v) if integral else v

def read_eod_price(root, d):
    p=root/'eod'/d.strftime('%Y%m%d')
    st=js(p/'status.json')
    if st.get('target_date')!=d.isoformat() or st.get('price_status')!='COMPLETE' or st.get('price_date')!=d.isoformat():
        raise DataBlocked('EOD_DATE_OR_PRICE_NOT_VERIFIED')
    if st.get('downstream_ready') is not True or st.get('mother_status')!='COMPLETE' or st.get('second_mother') is not False:
        raise DataBlocked('EOD_ORIGINAL_MOTHER_NOT_READY')
    receipt=js(p/'receipts'/'price.json')
    if receipt.get('status')!='COMPLETE' or receipt.get('leg')!='price' or receipt.get('target_date')!=d.isoformat():
        raise DataBlocked('EOD_PRICE_RECEIPT_INVALID')
    files=sorted(p.glob('price_[1-9].csv'))
    if not files or sorted(f.name for f in files)!=sorted(receipt.get('files') or []):
        raise DataBlocked('EOD_PRICE_SHARD_SET_MISMATCH')
    digest=eod_digest(files)
    if digest!=receipt.get('sha256') or digest!=st.get('price_sha256'):
        raise DataBlocked('EOD_PRICE_SHA_MISMATCH')
    rows=[];seen=set()
    for f in files:
        with f.open(encoding='utf-8-sig',newline='') as inp:
            reader=csv.DictReader(inp)
            if not set(['Date','Ticker','Close','VolumeShares','TurnoverTWD']).issubset(reader.fieldnames or []):
                raise DataBlocked('EOD_PRICE_COLUMNS_MISSING')
            for r in reader:
                ticker=str(r['Ticker']).strip()
                if r['Date']!=d.isoformat() or not TICKER.fullmatch(ticker) or ticker in seen:
                    raise DataBlocked('EOD_PRICE_ROW_KEY_INVALID')
                seen.add(ticker)
                volume=parse_number(r['VolumeShares'],integral=True)
                turnover=parse_number(r['TurnoverTWD'])
                close=parse_number(r['Close'],optional=True)
                if close==0:raise DataBlocked('EOD_PRICE_ZERO_CLOSE')
                rows.append([d.isoformat(),ticker,'' if close is None else format(close,'.12g'),volume,format(turnover,'.12g')])
    if len(rows)!=receipt.get('rows') or len(rows)<900:raise DataBlocked('EOD_PRICE_COVERAGE_INSUFFICIENT')
    return rows, {'date':d.isoformat(),'rows':len(rows),'sha256':digest,'directory':f'eod/{d:%Y%m%d}'}

def tdcc(raw_path, receipt_path, *, cutoff:date, asof_datetime:datetime):
    receipt=js(receipt_path)
    ds=receipt.get('snapshot_date')
    try: snap=date.fromisoformat(f'{ds[:4]}-{ds[4:6]}-{ds[6:8]}')
    except (ValueError,TypeError):raise DataBlocked('TDCC_BAD_SNAPSHOT_DATE')
    obs=datetime.fromisoformat(receipt.get('observed_at_taipei',''))
    if obs.tzinfo is None or obs.astimezone(TW)>asof_datetime or snap>cutoff:
        raise DataBlocked('TDCC_NOT_KNOWN_AT_DECISION')
    if receipt.get('status')!='COMPLETE' or receipt.get('source_owner')!='TDCC' or receipt.get('model_authority_created') is not False:
        raise DataBlocked('TDCC_RECEIPT_INVALID')
    raw=raw_path.read_bytes()
    rawsha=sha(raw)
    if rawsha!=receipt.get('source_sha256'):raise DataBlocked('TDCC_RAW_SHA_MISMATCH')
    root=raw_path.parents[1]
    proof_path=root/'provenance'/'first_observed'/(rawsha+'.json')
    if not proof_path.exists():raise DataBlocked('TDCC_FIRST_OBSERVED_PROOF_ABSENT')
    proof=js(proof_path)
    if (proof.get('payload_sha256')!=rawsha or
        proof.get('snapshot_reference_date')!=snap.isoformat() or
        proof.get('provenance_source_authority')!='CANONICAL_VESSEL_RESPONSE_ONLY' or
        proof.get('official_published_at') is not None or
        proof.get('ownership_and_provenance_share_exact_response_bytes') is not True):
        raise DataBlocked('TDCC_FIRST_OBSERVED_PROOF_INVALID')
    seen_at=datetime.fromisoformat(proof.get('first_observed_at_taipei') or proof.get('response_received_at_taipei',''))
    if seen_at.tzinfo is None or seen_at.astimezone(TW)>asof_datetime:
        raise DataBlocked('TDCC_FIRST_OBSERVED_AFTER_DECISION')
    if seen_at.astimezone(TW) != obs.astimezone(TW):
        raise DataBlocked('TDCC_RECEIPT_PROOF_TIME_MISMATCH')
    import io
    try: txt=raw.decode('utf-8-sig')
    except UnicodeError:raise DataBlocked('TDCC_ENCODING_INVALID')
    reader=csv.DictReader(io.StringIO(txt))
    required={'資料日期','證券代號','持股分級','人數','股數'}
    if not required.issubset(reader.fieldnames or []):raise DataBlocked('TDCC_COLUMNS_INVALID')
    holders={}; seen=set()
    for r in reader:
        t=str(r['證券代號']).strip()
        if not TICKER.fullmatch(t):continue
        if str(r['資料日期']).strip()!=ds:raise DataBlocked('TDCC_ROW_DATE_MISMATCH')
        grade=parse_number(r['持股分級'],integral=True)
        if grade not in (1,2,3):continue
        key=(t,grade)
        if key in seen:raise DataBlocked('TDCC_DUPLICATE_GRADE')
        seen.add(key)
        n=parse_number(r['人數'],integral=True)
        s=parse_number(r['股數'],integral=True)
        holders.setdefault(t,{})[grade]=(n,s)
    result=[]
    for ticker,grades in holders.items():
        if set(grades)=={1,2,3}:
            n=sum(grades[g][0] for g in (1,2,3))
            result.append([ds,ticker,n,'true'])
    if len(result)<900:raise DataBlocked('TDCC_RETAIL_COVERAGE_INSUFFICIENT')
    return result, {'snapshot_date':ds,'observed_at_taipei':obs.astimezone(TW).isoformat(),
                   'raw_sha256':rawsha,'first_observed_proof':str(proof_path),'valid_tickers':len(result),'source':str(raw_path)}

def aux_status(root, latest):
    data={'fugle':{'status':'UNAVAILABLE_OR_STALE','role':'QUOTE_ONLY_NOT_EOD'},
          'finmind':{'status':'UNAVAILABLE_OR_STALE','role':'AGGREGATE_CONTEXT_ONLY_NOT_PER_TICKER_EOD'}}
    p=root/'live'/'status.json'
    if p.exists():
        try:
            x=js(p); expires=datetime.fromisoformat(x['cache_expires_at_taipei']);now=datetime.now(TW)
            fresh=expires.tzinfo is not None and expires>=now and x.get('transport_role')=='QUOTE_TRANSPORT_ONLY_NO_RANKING_SIGNAL_CAPITAL_AUTHORITY'
            data['fugle']={'status':'FRESH_QUOTE_CONTEXT_ONLY' if fresh else 'UNAVAILABLE_OR_STALE',
                           'snapshot_id':x.get('snapshot_id'),'expires_at':x.get('cache_expires_at_taipei'),
                           'role':'QUOTE_ONLY_NOT_EOD','may_replace_close':False}
        except (DataBlocked,ValueError,KeyError,TypeError):pass
    p=root/'eod'/latest.strftime('%Y%m%d')/'market_state_finmind_context.json'
    if p.exists():
        try:
            x=js(p); st=js(p.parent/'status.json')
            valid=(x.get('target_date')==latest.isoformat() and
                   st.get('market_state_finmind_context_status')=='ATTACHED_RESEARCH_SHADOW' and
                   st.get('market_state_finmind_context_sha256')==sha(p.read_bytes()) and
                   x.get('selection_effect')=='NONE' and x.get('raw_vendor_snapshot_persisted') is False)
            data['finmind']={'status':'VERIFIED_AGGREGATE_CONTEXT_ONLY' if valid else 'UNAVAILABLE_OR_STALE',
                             'role':'AGGREGATE_CONTEXT_ONLY_NOT_PER_TICKER_EOD',
                             'may_replace_close':False,'may_replace_tdcc':False,'snapshot_date':latest.isoformat()}
        except (DataBlocked,KeyError,ValueError):pass
    return data

def audit(root, decision):
    record={'schema':'HENGCE_RETAIL_TOP5_ORIGINAL_VESSEL_INPUT_BRIDGE_V1',
            'decision':decision.isoformat(),'status':'BLOCKED','research_data_only':True,
            'formal_selection_authority':False,'capital_authority_twd':0,'broker_execution':False,
            'q017':'RETIRED_UNCHANGED','eod_source':'EXISTING_HENGCE_EOD_ONLY',
            'tdcc_source':'EXISTING_HENGCE_TDCC_ONLY',
            'v22_original_bundled_sha_unmodified':True,
            'downstream_selection_mode':'NOT_AUTHORIZED_OR_CONNECTED','blockers':[], 'sources':{}}
    if decision.weekday()!=4: record['blockers'].append('DECISION_NOT_FRIDAY')
    if decision>datetime.now(TW).date():record['blockers'].append('DECISION_IN_FUTURE')
    folders=sorted((root/'eod').glob('[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]')) if (root/'eod').exists() else []
    dates=[]
    for p in folders:
        try:d=date.fromisoformat(p.name[:4]+'-'+p.name[4:6]+'-'+p.name[6:])
        except ValueError:continue
        if d<=decision:dates.append(d)
    record['available_eod_folder_count']=len(dates)
    chosen=dates[-25:]
    daily=[]; dpro=[]
    for d in chosen:
        try:
            rows,proof=read_eod_price(root,d);daily.extend(rows);dpro.append(proof)
        except (DataBlocked,OSError,csv.Error) as e:
            record['blockers'].append('EOD_INVALID:'+d.isoformat()+':'+str(e))
    if len(dpro)<21:record['blockers'].append(f'INSUFFICIENT_VERIFIED_EOD_DAYS:{len(dpro)}<21')
    if not dates or dates[-1]!=decision:record['blockers'].append('DECISION_DAY_EOD_ABSENT')
    if chosen and len(dpro)!=len(chosen):record['blockers'].append('SOME_EOD_DAYS_INVALID')
    record['verified_eod_day_count']=len(dpro)
    record['sources']['eod']=dpro
    cutoff=decision-timedelta(days=14)
    start=datetime.combine(decision,datetime.max.time(),tzinfo=TW)
    selected=[]
    croot=root/'ownership'/'tdcc'
    if croot.exists():
        for p in sorted(croot.glob('[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]')):
            try:snap=date.fromisoformat(p.name[:4]+'-'+p.name[4:6]+'-'+p.name[6:])
            except ValueError:continue
            if snap<=cutoff:selected.append(p)
    selected=selected[-3:]
    weekly=[]; wpro=[]
    for p in selected:
        try:
            rows,proof=tdcc(p/'tdcc_1_5_raw.csv',p/'receipt.json',cutoff=cutoff,asof_datetime=start)
            weekly.extend(rows);wpro.append(proof)
        except (DataBlocked,OSError,csv.Error,UnicodeError) as e:record['blockers'].append('TDCC_INVALID:'+p.name+':'+str(e))
    if len(wpro)!=3:record['blockers'].append(f'INSUFFICIENT_VERIFIED_TDCC_WEEKS:{len(wpro)}<3')
    for a,b in zip(wpro,wpro[1:]):
        if not 5<=(date.fromisoformat(b['snapshot_date'][:4]+'-'+b['snapshot_date'][4:6]+'-'+b['snapshot_date'][6:])-date.fromisoformat(a['snapshot_date'][:4]+'-'+a['snapshot_date'][4:6]+'-'+a['snapshot_date'][6:])).days<=10:
            record['blockers'].append('TDCC_NONCONSECUTIVE_SNAPSHOTS')
    if wpro and (cutoff-date.fromisoformat(wpro[-1]['snapshot_date'][:4]+'-'+wpro[-1]['snapshot_date'][4:6]+'-'+wpro[-1]['snapshot_date'][6:])).days>7:
        record['blockers'].append('TDCC_LAST_SNAPSHOT_STALE')
    record['verified_tdcc_week_count']=len(wpro)
    record['sources']['tdcc']=wpro
    record['auxiliary']=aux_status(root,decision)
    if not record['blockers']:
        record['status']='SOURCE_DATA_PREPARED_RESEARCH_ONLY'
    return record,daily,weekly

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--repo-root',type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument('--decision',required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    try:
        d=date.fromisoformat(a.decision)
        if a.output.exists():raise DataBlocked('OUTPUT_PATH_ALREADY_EXISTS')
        report,day,week=audit(a.repo_root,d)
        a.output.mkdir(parents=True,exist_ok=False)
        (a.output/'bridge_status.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if report['status']=='SOURCE_DATA_PREPARED_RESEARCH_ONLY':
            for name,header,rows in [('daily.csv',DAILY_FIELDS,day),('weekly.csv',CHIP_FIELDS,week)]:
                with (a.output/name).open('x',encoding='utf-8-sig',newline='') as f:
                    w=csv.writer(f);w.writerow(header);w.writerows(rows)
        print(json.dumps({'status':report['status'],'decision':a.decision,
                          'eod_days':report['verified_eod_day_count'],
                          'tdcc_weeks':report['verified_tdcc_week_count'],
                          'blockers':report['blockers'],'auxiliary':report['auxiliary']},ensure_ascii=False))
        return 0 if report['status']=='SOURCE_DATA_PREPARED_RESEARCH_ONLY' else 2
    except (DataBlocked,ValueError) as e:
        ap.exit(2,f'INPUT_BRIDGE_REJECTED:{e}\n')
if __name__=='__main__':raise SystemExit(main())