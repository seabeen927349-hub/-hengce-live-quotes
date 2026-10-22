#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, math, re, time
from datetime import datetime
from pathlib import Path

import hengce_q017_decision_lock_v4 as v4
from hengce_recovery_transaction import current_request

core=v4.core; TZ=v4.TZ; ROOT=v4.ROOT; RADAR=v4.RADAR; HISTORY=v4.HISTORY; LATEST=v4.LATEST; SIGNAL_LEDGER=v4.SIGNAL_LEDGER
OBS_DIR=RADAR/'observations'; OBS_LATEST=RADAR/'observation_latest.json'; DECISION_DIR=RADAR/'decision'; DECISION_LATEST=RADAR/'decision_latest.json'
OBS_DIR.mkdir(parents=True,exist_ok=True); DECISION_DIR.mkdir(parents=True,exist_ok=True)
SCHEMA=5
UNIVERSE_SCOPE='TWSE_LISTED_ELECTRONICS_ONLY'
UNIVERSE_SOURCE='TWSE_MI_INDEX_TYPE_13_ELECTRONICS_HISTORY'


def csha(o):
    return hashlib.sha256(json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def _dt(x):
    try:
        d=datetime.fromisoformat(str(x)); return d if d.tzinfo else None
    except Exception:return None

def _f(x):
    try:return float(x)
    except Exception:return None

def _close(a,b,tol=1e-10):
    return a is not None and b is not None and math.isfinite(a) and math.isfinite(b) and abs(a-b)<=tol*max(1.0,abs(a),abs(b))
def obs_path(today):return OBS_DIR/f'{today.strftime("%Y%m%d")}_0901_observation.json'
def decision_path(today):return DECISION_DIR/f'{today.strftime("%Y%m%d")}_0901.json'
def universe_hash(members):return csha(sorted(str(x) for x in members))
def write_once(path,obj,hash_field):
    text=json.dumps(obj,ensure_ascii=False,indent=2)+'\n'
    try:path.open('x',encoding='utf-8').write(text);return obj,True
    except FileExistsError:
        old=json.loads(path.read_text(encoding='utf-8'))
        if old.get(hash_field)!=obj.get(hash_field):raise RuntimeError(f'IMMUTABLE_CONFLICT:{path}')
        return old,False

def _in_0901(ts,trade):
    d=_dt(ts)
    if not d:return False
    z=d.astimezone(TZ)
    return z.date().isoformat()==trade and z.hour==9 and z.minute==1

def validate_observation(o):
    if int(o.get('schema_version') or 0)!=SCHEMA:return False,'OBS_SCHEMA_NOT_V5'
    if o.get('module')!='Q017_0901_OBSERVATION_LOCK':return False,'OBS_MODULE_INVALID'
    trade=str(o.get('trade_date') or '')
    if len(trade)!=10:return False,'OBS_TRADE_DATE_MISSING'
    lock=o.get('observation_lock') or {}
    if lock.get('cutoff_label')!='09:01' or lock.get('window_valid') is not True or lock.get('immutable') is not True:return False,'OBS_PROVENANCE_FLAGS_INVALID'
    if not _in_0901(lock.get('capture_started_at_taipei'),trade) or not _in_0901(lock.get('capture_finished_at_taipei'),trade):return False,'OBS_CAPTURE_NOT_0901'
    ul=o.get('universe_lock') or {}; members=[str(x) for x in ul.get('members') or []]
    if ul.get('scope')!=UNIVERSE_SCOPE:return False,'UNIVERSE_SCOPE_DRIFT'
    if ul.get('source')!=UNIVERSE_SOURCE:return False,'UNIVERSE_SOURCE_DRIFT'
    if len(members)!=len(set(members)) or any(not re.fullmatch(r'[1-9]\d{3}',x) for x in members):return False,'UNIVERSE_MEMBERS_INVALID'
    if int(ul.get('member_count') or -1)!=len(members) or ul.get('universe_sha256')!=universe_hash(members):return False,'UNIVERSE_HASH_OR_COUNT_INVALID'
    try:
        md=datetime.strptime(str(ul.get('membership_date')),'%Y-%m-%d').date();td=datetime.strptime(trade,'%Y-%m-%d').date()
    except Exception:return False,'UNIVERSE_MEMBERSHIP_DATE_INVALID'
    if md>=td:return False,'UNIVERSE_MEMBERSHIP_NOT_CAUSAL'
    models=o.get('eligible_models') or []
    tickers=[str(x.get('ticker') or '') for x in models]
    if len(tickers)!=len(set(tickers)) or not tickers:return False,'ELIGIBLE_MODELS_INVALID'
    outside=[t for t in tickers if t not in set(members)]
    if outside:return False,'ELIGIBLE_OUTSIDE_ELECTRONICS_UNIVERSE'
    for x in models:
        if _f(x.get('beta')) is None or _f(x.get('beta'))<=0 or _f(x.get('previous_close')) in (None,0):return False,'ELIGIBLE_MODEL_NUMERIC_INVALID'
    quotes=o.get('quotes') or {}; qkeys=sorted(str(x) for x in quotes.keys())
    if sorted(tickers)!=qkeys:return False,'OBS_QUOTES_NOT_100PCT_ELIGIBLE'
    for t,q in quotes.items():
        if str(q.get('ticker') or t)!=str(t):return False,'OBS_QUOTE_TICKER_MISMATCH'
        if not _in_0901(q.get('fetched_at_taipei'),trade):return False,'OBS_QUOTE_NOT_0901'
    ds=o.get('data_status') or {};n=len(tickers)
    if int(ds.get('eligible_beta_count') or 0)!=n or int(ds.get('provider_returned_count') or 0)!=n:return False,'OBS_PROVIDER_COUNT_NOT_100PCT'
    if not _close(_f(ds.get('provider_coverage')),1.0) or not _close(_f(ds.get('provider_coverage_required')),1.0):return False,'OBS_PROVIDER_COVERAGE_NOT_100PCT'
    qrc=int(ds.get('eligible_quote_row_count') or -1);qcov=_f(ds.get('eligible_quote_row_coverage'));opened=int(ds.get('opened_by_decision_count') if ds.get('opened_by_decision_count') is not None else -1);ocov=_f(ds.get('opened_coverage'))
    if qrc!=n or not _close(qcov,1.0):return False,'OBS_QUOTE_ROW_COVERAGE_NOT_100PCT'
    if opened<0 or opened>n:return False,'OBS_OPENED_COUNT_INVALID'
    if not _close(ocov,opened/n if n else 0.0):return False,'OBS_OPENED_COVERAGE_MISMATCH'
    if int(ds.get('quote_present_but_no_open_count') if ds.get('quote_present_but_no_open_count') is not None else -1)!=n-opened:return False,'OBS_NOT_OPENED_COUNT_MISMATCH'
    if ds.get('coverage_semantics')!='QUOTE_ROW_COVERAGE_IS_DATA_COMPLETENESS;OPENED_COVERAGE_IS_CAUSAL_MARKET_STATE':return False,'OBS_COVERAGE_SEMANTICS_DRIFT'
    if ds.get('critical_set_complete') is not True or ds.get('critical_missing') not in ([],None):return False,'OBS_CRITICAL_SET_INCOMPLETE'
    mi=o.get('market_inputs') or {};sf=mi.get('sox') or {};dx=mi.get('dxy') or {}
    if None in (_f(sf.get('sox_1d')),_f(sf.get('sox_5d')),_f(dx.get('dxy_5d'))):return False,'OBS_MARKET_INPUTS_MISSING'
    h=o.get('observation_snapshot_sha256');exp=csha({k:v for k,v in o.items() if k!='observation_snapshot_sha256'})
    if not h or h!=exp:return False,'OBS_HASH_INVALID'
    return True,'VALID_0901_OBSERVATION_ELECTRONICS_LOCKED'

def build_decision_from_observation(o,computed_at=None):
    ok,reason=validate_observation(o)
    if not ok:raise RuntimeError(reason)
    computed_at=computed_at or core.now_tw();trade=o['trade_date'];mi=o['market_inputs'];sf=mi['sox'];dxy=mi['dxy']
    go,checks=v4.evaluate_market_gate(sf,dxy);state=v4.market_state_from_checks(checks)
    models={str(x['ticker']):x for x in o['eligible_models']};quotes=o['quotes'];cand=[];opened=0
    for t,m in models.items():
        q=quotes[t];op=_f(q.get('open'));pc=_f(q.get('reference_close')) or _f(m.get('previous_close'))
        if op is None or pc in (None,0):continue
        opened+=1;b=_f(m['beta']);gap=op/pc-1;exp=b*_f(sf['sox_1d']);res=gap-exp
        if res>0.04:continue
        score=b*(1+25*max(-res,0));cand.append({'ticker':t,'name':q.get('name') or m.get('name',''),'beta':b,'open':op,'previous_close':pc,'gap':gap,'expected_gap':exp,'residual':res,'score':score,'qualified':go,'decision_observed_at_taipei':q.get('fetched_at_taipei')})
    cand.sort(key=lambda x:x['score'],reverse=True);top=cand[:3]
    prev=o.get('previous_locked_top3') or [];cur=[x['ticker'] for x in top]
    for x in top:x['new']=x['ticker'] not in prev
    lock=o['observation_lock'];ds=o['data_status'];ul=o['universe_lock']
    out={'schema_version':SCHEMA,'system':'HENGCE','module':'Q017_SOX_ELECTRONICS_DECISION_LOCK','trade_date':trade,'generated_at_taipei':computed_at.isoformat(),'binding_status':'PASS','market_state':state,'authority':'FORMAL_Q017_DECISION_INPUT_NOT_BROKER_ORDER','observation_source_file':str(obs_path(datetime.strptime(trade,'%Y-%m-%d').date()).relative_to(ROOT)),'observation_snapshot_sha256':o['observation_snapshot_sha256'],'universe_lock':ul,'decision_lock':{'cutoff_label':'09:01','capture_window_taipei':'09:01:00-09:01:59.999999','capture_started_at_taipei':lock['capture_started_at_taipei'],'capture_finished_at_taipei':lock['capture_finished_at_taipei'],'window_valid':True,'immutable':True,'rerank_after_lock':False,'attempt_count':lock['attempt_count'],'accepted_attempt':lock['accepted_attempt'],'authority_semantics':'OBSERVATION_TIME_LOCK','calculation_may_occur_after_cutoff':True,'calculation_time_is_not_market_observation_time':True},'data_status':{'premarket_gate':o.get('premarket_gate'),'premarket_coherence':o.get('premarket_coherence'),'dxy':o.get('dxy_status'),'tw_history_latest_date':ul['membership_date'],'eligible_beta_count':ds['eligible_beta_count'],'provider_returned_count':ds['provider_returned_count'],'provider_coverage':ds['provider_coverage'],'provider_coverage_required':1.0,'eligible_quote_row_count':ds['eligible_quote_row_count'],'eligible_quote_row_coverage':ds['eligible_quote_row_coverage'],'opened_by_decision_count':opened,'opened_coverage':opened/ds['eligible_beta_count'] if ds['eligible_beta_count'] else 0.0,'quote_present_but_no_open_count':ds['eligible_beta_count']-opened,'coverage_semantics':ds['coverage_semantics'],'critical_set_rule':ds['critical_set_rule'],'critical_set_count':ds['critical_set_count'],'critical_set_complete':True,'critical_missing':[],'observation_snapshot_sha256':o['observation_snapshot_sha256']},'market_gate':{'gate_go':go,'checks':checks,'sox_1d':sf['sox_1d'],'sox_5d':sf['sox_5d'],'dxy_5d':dxy['dxy_5d'],'source_lock':'Q017_LOCK_20261018.json'},'sox':sf,'dxy':{'session':dxy.get('latest_session'),'five_sessions_back':dxy.get('five_sessions_back'),'dxy_5d':dxy['dxy_5d']},'rules':{'universe_scope':UNIVERSE_SCOPE,'universe_source':UNIVERSE_SOURCE,'sox_1d_max':0.0,'sox_5d_max':-0.03,'dxy_5d_min':-0.005,'residual_max':0.04,'score':'beta*(1+25*max(-residual,0))','top_n':3,'research_hold_days':10,'authority':'Q017_LOCK_20261018.json'},'top3':top,'new':[x['ticker'] for x in top if x.get('new')],'dropped':[t for t in prev if t not in cur],'note':'Schema-v5 separates 09:01 immutable market observation from later deterministic computation. Ranking universe is hard-locked to TWSE listed electronics only.'}
    out['decision_snapshot_sha256']=csha({k:v for k,v in out.items() if k!='decision_snapshot_sha256'})
    return out

def collect_observation(today=None):
    today=today or core.now_tw().date();p=obs_path(today)
    if p.exists():
        old=json.loads(p.read_text(encoding='utf-8'));ok,reason=validate_observation(old)
        if not ok:raise RuntimeError(f'EXISTING_OBSERVATION_INVALID:{reason}')
        core.atomic_json(OBS_LATEST,old);return old
    gate,sox_status,dxy_status,seed,sf,betas,prev,names,hist_date,universe,coh=v4.prepare_model(today)
    members=sorted(str(t) for t in universe)
    if not members:raise RuntimeError('ELECTRONICS_UNIVERSE_EMPTY')
    eligible=[t for t in members if betas.get(t) is not None and betas.get(t)>0 and prev.get(t)]
    if not eligible:raise RuntimeError('NO_ELIGIBLE_ELECTRONICS_BETA_UNIVERSE')
    _,end=v4.wait_for_decision_minute(today);prev_top=v4.previous_top3(v4.decision_path(today));crit=v4.critical_set(eligible,betas,prev_top);attempts=[];accepted=None;n=0
    while core.now_tw()<=end:
        n+=1;rec,fail,wins,s,e=v4.capture_provider_attempt(eligible);ok,iw,cov,miss=v4.attempt_valid(today,eligible,rec,wins,s,e,end,crit)
        row_times=all(_in_0901((q or {}).get('fetched_at_taipei'),today.isoformat()) for q in rec.values())
        ok=ok and row_times
        attempts.append({'attempt':n,'started_at_taipei':s.isoformat(),'finished_at_taipei':e.isoformat(),'window_valid':iw and row_times,'provider_returned_count':len(rec),'eligible_beta_count':len(eligible),'provider_coverage':cov,'critical_missing':miss,'batch_failure_count':len(fail)})
        if ok:accepted=(rec,fail,s,e,cov);break
        if e>=end:break
        time.sleep(min(v4.RETRY_SLEEP_SECONDS,max(0,(end-core.now_tw()).total_seconds())))
    if accepted is None:
        v4.fail_closed(today,attempts,'NO_VALID_0901_OBSERVATION_100PCT_ELECTRONICS_COVERAGE');raise RuntimeError('Q017_OBSERVATION_MISSING_FAIL_CLOSED')
    rec,fail,s,e,cov=accepted
    opened_rows=sum((q or {}).get('open') is not None for q in rec.values())
    models=[{'ticker':t,'name':names.get(t,''),'beta':betas[t],'previous_close':prev[t]} for t in eligible]
    ul={'scope':UNIVERSE_SCOPE,'source':UNIVERSE_SOURCE,'membership_date':hist_date,'member_count':len(members),'universe_sha256':universe_hash(members),'members':members,'full_market_quote_transport_is_not_ranking_universe':True}
    out={'schema_version':SCHEMA,'system':'HENGCE','module':'Q017_0901_OBSERVATION_LOCK','trade_date':today.isoformat(),'generated_at_taipei':e.isoformat(),'binding_status':'PASS','authority':'CAUSAL_MARKET_OBSERVATION_ONLY','observation_lock':{'cutoff_label':'09:01','capture_window_taipei':'09:01:00-09:01:59.999999','capture_started_at_taipei':s.isoformat(),'capture_finished_at_taipei':e.isoformat(),'window_valid':True,'immutable':True,'attempt_count':n,'accepted_attempt':n,'computation_may_occur_later':True,'no_late_market_backfill':True},'universe_lock':ul,'eligible_models':models,'quotes':{str(k):v for k,v in rec.items()},'previous_locked_top3':prev_top,'market_inputs':{'sox':sf,'dxy':{'latest_session':dxy_status.get('latest_session'),'five_sessions_back':dxy_status.get('five_sessions_back'),'dxy_5d':dxy_status.get('dxy_5d')}},'premarket_gate':gate,'premarket_coherence':coh,'dxy_status':dxy_status,'data_status':{'eligible_beta_count':len(eligible),'provider_returned_count':len(rec),'provider_coverage':cov,'provider_coverage_required':1.0,'eligible_quote_row_count':len(rec),'eligible_quote_row_coverage':len(rec)/len(eligible) if eligible else 0.0,'opened_by_decision_count':opened_rows,'opened_coverage':opened_rows/len(eligible) if eligible else 0.0,'quote_present_but_no_open_count':len(eligible)-opened_rows,'coverage_semantics':'QUOTE_ROW_COVERAGE_IS_DATA_COMPLETENESS;OPENED_COVERAGE_IS_CAUSAL_MARKET_STATE','critical_set_rule':'top 50 positive Beta60 plus previous locked Top3','critical_set_count':len(crit),'critical_set_complete':True,'critical_missing':[],'batch_failures':fail[:20]},'policy':'ONLY_0901_OBSERVATION_IS_CAUSAL;COMPUTATION_TIME_MAY_BE_LATER'}
    out['observation_snapshot_sha256']=csha({k:v for k,v in out.items() if k!='observation_snapshot_sha256'})
    ok,reason=validate_observation(out)
    if not ok:raise RuntimeError(f'OBSERVATION_SELF_VALIDATION_FAIL:{reason}')
    stored,created=write_once(p,out,'observation_snapshot_sha256');core.atomic_json(OBS_LATEST,stored)
    if created:core.atomic_json(HISTORY/f'{e.strftime("%Y%m%dT%H%M%S")}_OBSERVATION_LOCK_V5.json',stored)
    return stored

def compute_decision(today=None):
    today=today or core.now_tw().date();op=obs_path(today)
    current_request('q017-recovery','compute',today.isoformat(),core.now_tw())
    if not op.exists():raise RuntimeError('NO_IMMUTABLE_0901_OBSERVATION')
    p=decision_path(today)
    if p.exists():
        stored=json.loads(p.read_text(encoding='utf-8'))
        validate_decision(stored,today)
        return stored  # Existing validated immutable decision wins; no rerank or projection repair.
    obs=json.loads(op.read_text(encoding='utf-8'));out=build_decision_from_observation(obs);p=decision_path(today);stored,created=write_once(p,out,'decision_snapshot_sha256');core.atomic_json(DECISION_LATEST,stored);core.atomic_json(LATEST,stored)
    if created:
        core.atomic_json(HISTORY/f'{core.now_tw().strftime("%Y%m%dT%H%M%S")}_DECISION_FROM_OBSERVATION_V5.json',stored)
        with SIGNAL_LEDGER.open('a',encoding='utf-8') as f:f.write(json.dumps({'time':stored['generated_at_taipei'],'date':stored['trade_date'],'event':'Q017_DECISION_FROM_0901_OBSERVATION_V5','top3':[x['ticker'] for x in stored['top3']],'observation_snapshot_sha256':stored['observation_snapshot_sha256'],'decision_snapshot_sha256':stored['decision_snapshot_sha256']},ensure_ascii=False)+'\n')
    return stored

def validate_decision(d,today):
    if int(d.get('schema_version') or 0)!=SCHEMA or d.get('trade_date')!=today.isoformat() or d.get('binding_status')!='PASS':raise RuntimeError('DECISION_V5_HEADER_INVALID')
    if d.get('decision_snapshot_sha256')!=csha({k:v for k,v in d.items() if k!='decision_snapshot_sha256'}):raise RuntimeError('DECISION_V5_HASH_INVALID')
    op=obs_path(today)
    if not op.exists():raise RuntimeError('DECISION_OBSERVATION_FILE_MISSING')
    o=json.loads(op.read_text(encoding='utf-8'));ok,reason=validate_observation(o)
    if not ok:raise RuntimeError(reason)
    if d.get('observation_snapshot_sha256')!=o.get('observation_snapshot_sha256'):raise RuntimeError('DECISION_OBSERVATION_HASH_MISMATCH')
    members=set((d.get('universe_lock') or {}).get('members') or [])
    if any(str(x.get('ticker')) not in members for x in d.get('top3') or []):raise RuntimeError('DECISION_TOP3_OUTSIDE_ELECTRONICS_UNIVERSE')

def monitor(today=None):
    today=today or core.now_tw().date();p=decision_path(today)
    if not p.exists():
        x={'schema_version':SCHEMA,'system':'HENGCE','module':'Q017_SOX_ELECTRONICS_RADAR_LOCKED','trade_date':today.isoformat(),'generated_at_taipei':core.now_tw().isoformat(),'binding_status':'DATA_PENDING','market_state':'DATA_PENDING','authority':'NO_FORMAL_SIGNAL','formal_buy_count':0,'top3':[],'monitor':{'status':'NO_DECISION_FROM_0901_OBSERVATION','rerank_performed':False,'ranking_frozen':True}};core.atomic_json(LATEST,x);raise RuntimeError('NO_FORMAL_Q017_DECISION')
    d=json.loads(p.read_text(encoding='utf-8'));validate_decision(d,today);x=dict(d);x['module']='Q017_SOX_ELECTRONICS_RADAR_LOCKED';x['generated_at_taipei']=core.now_tw().isoformat();x['monitor']={'status':'PASS','rerank_performed':False,'ranking_frozen':True,'marks':v4.current_marks(d.get('top3',[]))};core.atomic_json(LATEST,x);return x

def self_test():
    trade='2026-10-20';obs={'schema_version':5,'module':'Q017_0901_OBSERVATION_LOCK','trade_date':trade,'observation_lock':{'cutoff_label':'09:01','window_valid':True,'immutable':True,'capture_started_at_taipei':'2026-10-20T09:01:05+08:00','capture_finished_at_taipei':'2026-10-20T09:01:20+08:00','attempt_count':1,'accepted_attempt':1},'universe_lock':{'scope':UNIVERSE_SCOPE,'source':UNIVERSE_SOURCE,'membership_date':'2026-10-19','member_count':2,'members':['1111','2222'],'universe_sha256':universe_hash(['1111','2222'])},'eligible_models':[{'ticker':'1111','beta':1.0,'previous_close':100.0,'name':'A'},{'ticker':'2222','beta':1.2,'previous_close':100.0,'name':'B'}],'quotes':{'1111':{'ticker':'1111','open':98.0,'reference_close':100.0,'fetched_at_taipei':'2026-10-20T09:01:10+08:00'},'2222':{'ticker':'2222','open':99.0,'reference_close':100.0,'fetched_at_taipei':'2026-10-20T09:01:11+08:00'}},'market_inputs':{'sox':{'sox_1d':-0.01,'sox_5d':-0.04},'dxy':{'dxy_5d':-0.004}},'data_status':{'eligible_beta_count':2,'provider_returned_count':2,'provider_coverage':1.0,'provider_coverage_required':1.0,'eligible_quote_row_count':2,'eligible_quote_row_coverage':1.0,'opened_by_decision_count':2,'opened_coverage':1.0,'quote_present_but_no_open_count':0,'coverage_semantics':'QUOTE_ROW_COVERAGE_IS_DATA_COMPLETENESS;OPENED_COVERAGE_IS_CAUSAL_MARKET_STATE','critical_set_complete':True,'critical_missing':[],'critical_set_count':2,'critical_set_rule':'test'},'previous_locked_top3':[],'premarket_gate':{},'premarket_coherence':{},'dxy_status':{'status':'PASS','symbol':'DX-Y.NYB','dxy_5d':-0.004}}
    obs['observation_snapshot_sha256']=csha({k:v for k,v in obs.items() if k!='observation_snapshot_sha256'});assert validate_observation(obs)[0]
    d=build_decision_from_observation(obs,datetime.fromisoformat('2026-10-20T09:03:30+08:00'));assert d['generated_at_taipei'].startswith('2026-10-20T09:03:30');assert all(x['ticker'] in {'1111','2222'} for x in d['top3'])
    not_open=json.loads(json.dumps(obs));not_open['quotes']['2222']['open']=None;not_open['data_status']['opened_by_decision_count']=1;not_open['data_status']['opened_coverage']=0.5;not_open['data_status']['quote_present_but_no_open_count']=1;not_open['observation_snapshot_sha256']=csha({k:v for k,v in not_open.items() if k!='observation_snapshot_sha256'});assert validate_observation(not_open)[0];nd=build_decision_from_observation(not_open,datetime.fromisoformat('2026-10-20T09:03:30+08:00'));assert all(x['ticker']!='2222' for x in nd['top3'])
    bad=json.loads(json.dumps(obs));bad['eligible_models'].append({'ticker':'2603','beta':3.0,'previous_close':100.0});bad['quotes']['2603']={'ticker':'2603','open':90.0,'reference_close':100.0,'fetched_at_taipei':'2026-10-20T09:01:12+08:00'};bad['data_status']['eligible_beta_count']=3;bad['data_status']['provider_returned_count']=3;bad['observation_snapshot_sha256']=csha({k:v for k,v in bad.items() if k!='observation_snapshot_sha256'});assert validate_observation(bad)[1]=='ELIGIBLE_OUTSIDE_ELECTRONICS_UNIVERSE'
    late=json.loads(json.dumps(obs));late['quotes']['1111']['fetched_at_taipei']='2026-10-20T09:02:00+08:00';late['observation_snapshot_sha256']=csha({k:v for k,v in late.items() if k!='observation_snapshot_sha256'});assert validate_observation(late)[1]=='OBS_QUOTE_NOT_0901'
    print(json.dumps({'self_test':'PASS','schema':5,'observation_time_lock':True,'compute_after_0901_allowed':True,'electronics_universe_hard_lock':True,'non_electronics_injection_rejected':True}))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['observe','compute','monitor','self-test'],required=True);ap.add_argument('--date');a=ap.parse_args();target=datetime.strptime(a.date,'%Y-%m-%d').date() if a.date else None
    if a.mode=='self-test':self_test();return 0
    try:r=collect_observation(target) if a.mode=='observe' else compute_decision(target) if a.mode=='compute' else monitor(target);print(json.dumps(r,ensure_ascii=False,indent=2));return 0
    except Exception as e:
        fail={'schema_version':SCHEMA,'system':'HENGCE','module':'Q017_OBSERVATION_TIME_PIPELINE','mode':a.mode,'generated_at_taipei':core.now_tw().isoformat(),'status':'DATA_PENDING','authority':'NO_FORMAL_SIGNAL','formal_buy_count':0,'error':repr(e),'policy':'Q017_NEW_ENTRY_FAIL_CLOSED_ONLY;E2_AND_EXISTING_POSITION_MANAGEMENT_MUST_CONTINUE'};core.atomic_json(LATEST,fail);print(json.dumps(fail,ensure_ascii=False,indent=2));return 2
if __name__=='__main__':raise SystemExit(main())
