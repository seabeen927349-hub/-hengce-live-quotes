#!/usr/bin/env python3
"""Frozen daily Q017 producer; independent of E2 runtime authority."""
from __future__ import annotations
import argparse,csv,hashlib,json,math,re,subprocess,sys
from collections import defaultdict
from datetime import date,datetime
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo
from hengce_unified_contracts import ZERO_AUTHORITY,atomic
import hengce_twse_calendar as twse_calendar

TZ=ZoneInfo('Asia/Taipei'); ROOT=Path(__file__).resolve().parents[1]
DEFAULT_ELECTRONICS=ROOT/'hengce/q017_radar/data/twse_electronics_history_2026.csv'
DEFAULT_SOX=ROOT/'hengce/q017_radar/data/sox_2026.csv'; DEFAULT_OUTPUT=ROOT/'hengce/q017_canonical/latest.json'
BETA_MAX=60; BETA_MIN=30; K=25; TURN_MIN=20_000_000; TURN_FINITE_MIN=10; RESID_MAX=.04; MIN_MEMBERS=150
CONTRACT={'universe':'TWSE_LISTED_ELECTRONICS_PIT_DAILY','beta_history_max':60,'beta_history_min':30,
 'signal_day_excluded_from_beta':True,'k':25,'score':'beta60*(1+25*max(-residual1,0))','top_n':1,
 'avg_turnover20_min':20_000_000,'residual1_max':.04,'electronics_m1_max_exclusive':0.0,
 'electronics_m5_max':-.02,'sox_1d_max':0.0,'sox_5d_max':-.03,'dxy_used':False,
 'entry':'NEXT_TWSE_OPEN','exit':'FIXED_20_SESSIONS','roundtrip_cost':.008,'overlap_allowed':False}
EVIDENCE={'frozen_validation_commit':'f5abef555d9174e3919a9dca52e9bfb07351e02e',
 'frozen_validation_path':'research/e2_profit_max/E2_PROFIT_MAX_CANDIDATE_B_FINAL_VALIDATION_20261019.json',
 'frozen_validation_blob':'4b583972f662cbf040b0705f5c5e51806c708e03','implementation_evidence_path':'scripts/hengce_e2_live.py',
 'implementation_evidence_blob':'5dd05969ace4175ffcbecd8f381404f17ab873dd','authority_note':'E2_RESEARCH_EVIDENCE_ONLY_NOT_Q017_RUNTIME_AUTHORITY'}

def finite(x):
    if isinstance(x,bool) or x is None:return None
    try:v=float(str(x).replace(',','').strip())
    except (ValueError,TypeError,OverflowError):return None
    return v if math.isfinite(v) else None

def day(x):
    try:return date.fromisoformat(str(x or '')[:10]).isoformat()
    except ValueError as e:raise ValueError('INVALID_DATE:'+str(x)) from e

def raw_hash(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def producer_commit(root=ROOT):
    try:v=subprocess.check_output(['git','-C',str(root),'log','-1','--format=%H','--',str(Path(__file__).resolve().relative_to(root))],text=True,timeout=10).strip()
    except Exception as e:raise ValueError('Q017_PRODUCER_COMMIT_UNRESOLVED') from e
    if not re.fullmatch(r'[0-9a-f]{40}',v):raise ValueError('Q017_PRODUCER_COMMIT_INVALID')
    return v

def load_electronics(path):
    out=[];seen=set()
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        rd=csv.DictReader(f)
        if not rd.fieldnames or not {'date','ticker','close','turnover_ntd'}.issubset(rd.fieldnames):raise ValueError('ELECTRONICS_COLUMNS_MISSING')
        for r in rd:
            ds=day(r.get('date'));t=str(r.get('ticker') or '').strip()
            if not re.fullmatch(r'[1-9]\d{3}',t):continue
            if (ds,t) in seen:raise ValueError('DUPLICATE_ELECTRONICS_DATE_TICKER:'+ds+':'+t)
            seen.add((ds,t));c=finite(r.get('close'));turn=finite(r.get('turnover_ntd'))
            if c is not None and c>0:out.append({'date':ds,'ticker':t,'name':str(r.get('name') or ''),'close':c,'turnover':turn})
    if not out:raise ValueError('ELECTRONICS_HISTORY_EMPTY')
    return sorted(out,key=lambda r:(r['date'],r['ticker']))

def load_sox(path):
    out=[];seen=set()
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        rd=csv.DictReader(f)
        if not rd.fieldnames or not {'date','close'}.issubset(rd.fieldnames):raise ValueError('SOX_COLUMNS_MISSING')
        for r in rd:
            ds=day(r.get('date'));c=finite(r.get('close'))
            if ds in seen:raise ValueError('DUPLICATE_SOX_DATE:'+ds)
            if c is None or c<=0:raise ValueError('INVALID_SOX_CLOSE:'+ds)
            seen.add(ds);out.append({'date':ds,'close':c})
    if len(out)<6:raise ValueError('SOX_HISTORY_INSUFFICIENT')
    return sorted(out,key=lambda r:r['date'])

def prepare_features(rows,signal_date,min_daily_members=MIN_MEMBERS):
    by=defaultdict(list);md=defaultdict(list)
    for x in rows:
        if x['date']<=signal_date:by[x['ticker']].append(dict(x))
    for hist in by.values():
        hist.sort(key=lambda r:r['date']);prev=None;turn=[]
        for r in hist:
            r1=r['close']/prev-1 if prev not in (None,0) else None;turn.append(r['turnover'])
            vals=[v for v in turn[-20:] if v is not None and math.isfinite(v)]
            r['r1']=r1;r['avg_turnover20']=sum(vals)/len(vals) if len(vals)>=TURN_FINITE_MIN else None
            if r1 is not None and math.isfinite(r1):md[r['date']].append(r1)
            prev=r['close']
    members=sum(r['date']==signal_date for r in rows)
    if members<min_daily_members:raise ValueError(f'SIGNAL_UNIVERSE_TOO_SMALL:{members}')
    market={};dates=sorted(md)
    for i,ds in enumerate(dates):
        m1=median(md[ds]);market[ds]={'m1':m1,'m5':None,'return_count':len(md[ds])}
        if i>=4:
            p=1.0
            for d in dates[i-4:i+1]:p*=1+market[d]['m1']
            market[ds]['m5']=p-1
    curm=market.get(signal_date)
    if not curm or curm['m5'] is None:raise ValueError('LOCAL_MARKET_FEATURES_MISSING')
    cand=[]
    for t,hist in by.items():
        hist.sort(key=lambda r:r['date']);idx=next((i for i,r in enumerate(hist) if r['date']==signal_date),None)
        if idx is None:continue
        cur=hist[idx]
        if cur.get('r1') is None or cur.get('avg_turnover20') is None or cur['avg_turnover20']<TURN_MIN:continue
        obs=[(r['r1'],market[r['date']]['m1']) for r in hist[max(0,idx-BETA_MAX):idx] if r.get('r1') is not None and r['date'] in market]
        if len(obs)<BETA_MIN:continue
        n=len(obs);sm=sum(a for a,_ in obs)/n;mm=sum(b for _,b in obs)/n
        cov=sum((a-sm)*(b-mm) for a,b in obs)/n;var=sum((b-mm)**2 for _,b in obs)/n
        if abs(var)<=1e-18:continue
        beta=cov/var
        if not math.isfinite(beta) or beta<=0:continue
        resid=cur['r1']-beta*curm['m1']
        if not math.isfinite(resid) or resid>RESID_MAX:continue
        cand.append({'ticker':t,'name':cur.get('name',''),'beta60':beta,'beta_observations':n,'stock_r1':cur['r1'],
                     'residual1':resid,'q017_score':beta*(1+K*max(-resid,0)),'avg_turnover20':cur['avg_turnover20'],'signal_close':cur['close']})
    cand.sort(key=lambda r:(-r['q017_score'],r['ticker']))
    return curm,cand,{'signal_universe_members':members,'signal_market_return_count':curm['return_count'],'eligible_before_global_gates':len(cand)}

def macro(rows,signal_date):
    z=[r for r in rows if r['date']<signal_date]
    if len(z)<6:raise ValueError('SOX_PRIOR_HISTORY_INSUFFICIENT')
    last=z[-1]
    if (date.fromisoformat(signal_date)-date.fromisoformat(last['date'])).days>7:raise ValueError('SOX_STALE_FOR_SIGNAL:'+last['date'])
    return {'session':last['date'],'sox_1d':last['close']/z[-2]['close']-1,'sox_5d':last['close']/z[-6]['close']-1}

def build_artifact(electronics,sox,*,trade_date,signal_date,generated_at,code_commit,input_hashes,calendar_manifest,calendar_raw_sha,min_daily_members=MIN_MEMBERS):
    trade_date=day(trade_date);signal_date=day(signal_date)
    if generated_at.tzinfo is None:raise ValueError('GENERATED_AT_NAIVE')
    generated_at=generated_at.astimezone(TZ)
    if generated_at.date().isoformat()!=trade_date:raise ValueError('GENERATED_AT_TRADE_DATE_MISMATCH')
    twse_calendar.validate_next_session(signal_date,trade_date,calendar_manifest)
    if not re.fullmatch(r'[0-9a-f]{40}',code_commit):raise ValueError('PRODUCER_COMMIT_INVALID')
    if not input_hashes or any(not re.fullmatch(r'[0-9a-f]{64}',x) for x in input_hashes.values()):raise ValueError('INPUT_HASH_INVALID')
    if input_hashes.get('twse_calendar_manifest')!=calendar_raw_sha:raise ValueError('TWSE_CALENDAR_INPUT_HASH_MISMATCH')
    dates=sorted({r['date'] for r in electronics})
    if not dates:raise ValueError('ELECTRONICS_HISTORY_EMPTY')
    if dates[-1]!=signal_date:raise ValueError('SIGNAL_DATE_NOT_LATEST_ELECTRONICS_SESSION:'+dates[-1])
    if any(x>=trade_date for x in dates):raise ValueError('NONCAUSAL_HISTORY_CONTAINS_TRADE_DATE_OR_LATER')
    loc,ranked,diag=prepare_features(electronics,signal_date,min_daily_members);mac=macro(sox,signal_date)
    lc={'electronics_m1_lt_0':loc['m1']<0,'electronics_m5_lte_minus_2pct':loc['m5']<=-.02}
    mc={'sox_1d_lte_0':mac['sox_1d']<=0,'sox_5d_lte_minus_3pct':mac['sox_5d']<=-.03}
    top=ranked[0] if ranked else None;go=all(lc.values()) and all(mc.values()) and top is not None;state='GO' if go else 'CASH'
    candidates=[]
    if go:
        candidates=[{'ticker':top['ticker'],'name':top['name'],'q017_rank':1,'q017_score':top['q017_score'],'beta60':top['beta60'],
         'beta_observations':top['beta_observations'],'stock_r1':top['stock_r1'],'residual1':top['residual1'],'signal_close':top['signal_close'],
         'qualified':True,'signal_date':signal_date,'entry_trade_date':trade_date,
         'filter_evidence':{'avg_turnover20':top['avg_turnover20'],'electronics_m1':loc['m1'],'electronics_m5':loc['m5'],'sox_1d':mac['sox_1d'],'sox_5d':mac['sox_5d']}}]
    return {'schema_version':1,'system':'HENGCE','module':'HENGCE_CANONICAL_Q017_CANDIDATES',**ZERO_AUTHORITY,
     'generated_at':generated_at.isoformat(),'trade_date':trade_date,'signal_date':signal_date,'binding_status':'PASS','market_state':state,
     'session_calendar':{'market':'TWSE','calendar_year':calendar_manifest['calendar_year'],'authority':calendar_manifest['authority'],
       'fingerprint_sha256':twse_calendar.manifest_fingerprint(calendar_manifest),'manifest_sha256':calendar_raw_sha},
     'canonical_q017_contract':dict(CONTRACT),'producer':{'name':'hengce_q017_canonical_producer','code_commit':code_commit,'input_hashes':dict(sorted(input_hashes.items())),'evidence':dict(EVIDENCE)},
     'local_gate':{'go':all(lc.values()),'checks':lc,'electronics_m1':loc['m1'],'electronics_m5':loc['m5']},
     'macro_gate':{'go':all(mc.values()),'checks':mc,'sox_session':mac['session'],'sox_1d':mac['sox_1d'],'sox_5d':mac['sox_5d'],'dxy_used':False},
     'selection':{'ranked_eligible_count':len(ranked),'top1_ticker':top['ticker'] if top else None,'top1_score':top['q017_score'] if top else None,'gate_go':go},
     'diagnostics':diag,'candidates':candidates}

def fail(trade_date,generated_at,commit,hashes,reason):
    return {'schema_version':1,'system':'HENGCE','module':'HENGCE_CANONICAL_Q017_CANDIDATES',**ZERO_AUTHORITY,
     'generated_at':generated_at.astimezone(TZ).isoformat(),'trade_date':trade_date,'binding_status':'FAIL_CLOSED','market_state':'CASH',
     'canonical_q017_contract':dict(CONTRACT),'producer':{'name':'hengce_q017_canonical_producer','code_commit':commit,'input_hashes':dict(sorted(hashes.items())),'evidence':dict(EVIDENCE)},'candidates':[],'reason':reason}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--trade-date',required=True);ap.add_argument('--signal-date',required=True)
    ap.add_argument('--electronics-history',type=Path,default=DEFAULT_ELECTRONICS);ap.add_argument('--sox-history',type=Path,default=DEFAULT_SOX)
    ap.add_argument('--calendar',type=Path);ap.add_argument('--output',type=Path,default=DEFAULT_OUTPUT);ap.add_argument('--generated-at');a=ap.parse_args()
    now=datetime.fromisoformat(a.generated_at) if a.generated_at else datetime.now(TZ)
    if now.tzinfo is None:print('FAIL_CLOSED: GENERATED_AT_NAIVE',file=sys.stderr);return 2
    hashes={};commit=None
    try:
        td=day(a.trade_date);sd=day(a.signal_date);cal,cal_path,cal_sha=twse_calendar.load_manifest(a.calendar)
        hashes={'electronics_history':raw_hash(a.electronics_history),'sox_history':raw_hash(a.sox_history),'twse_calendar_manifest':cal_sha};commit=producer_commit()
        out=build_artifact(load_electronics(a.electronics_history),load_sox(a.sox_history),trade_date=td,signal_date=sd,generated_at=now,code_commit=commit,input_hashes=hashes,calendar_manifest=cal,calendar_raw_sha=cal_sha)
        atomic(a.output,out);print(json.dumps({'binding_status':'PASS','market_state':out['market_state'],'signal_date':sd,'trade_date':td,'calendar':str(cal_path),'candidate_count':len(out['candidates']),'output':str(a.output)},ensure_ascii=False));return 0
    except Exception as e:
        reason=f'{type(e).__name__}:{e}'
        try:atomic(a.output,fail(day(a.trade_date),now,commit,hashes,reason))
        except Exception:pass
        print('FAIL_CLOSED: '+reason,file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
