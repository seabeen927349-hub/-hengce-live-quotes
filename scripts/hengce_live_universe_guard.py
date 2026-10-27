#!/usr/bin/env python3
import argparse, hashlib, json
from datetime import date, datetime
from pathlib import Path

U=Path('hengce/live_universe.json'); C=Path('hengce/HENGCE_LIVE_UNIVERSE_COVERAGE_CONTRACT_v1_0_20261020.json')
LATEST=Path('latest.json'); ACTIVE=Path('live/active.json'); STATUS=Path('live/status.json')
ROLE='TRANSPORT_COVERAGE_OBSERVVABILITY_ONLY_NO_RANKING_SIGNAL_CAPITAL_AUTHORITY'.replace('OBSERVV','OBSERV')
LINEAGE='LINEAGE_ONLY_NOT_AUTHORITY'; HEALTH='TRANSPORT_AND_DATA_FRESHNESS_ONLY'

def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def dump(p,o): Path(p).parent.mkdir(parents=True,exist_ok=True); Path(p).write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def csha(o): return hashlib.sha256(json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def pdate(v):
    try:return date.fromisoformat(str(v))
    except:return None
def current(payload):
    raw=payload.get('generated_at_taipei') or payload.get('generated_at')
    try:return datetime.fromisoformat(str(raw).replace('Z','+00:00')).date()
    except:return pdate(str(raw)[:10]) if raw else None
def contract(c):
    if c.get('module')!='HENGCE_LIVE_UNIVERSE_COVERAGE' or c.get('role')!=ROLE: raise SystemExit('UNIVERSE_CONTRACT_IDENTITY_MISMATCH')
    for k in ('ranking','signal','capital','broker_execution'):
        if (c.get('authority') or {}).get(k) is not False: raise SystemExit('UNIVERSE_CONTRACT_AUTHORITY_MUST_BE_FALSE:'+k)
    r=c.get('refresh_policy') or {}
    for k in ('auto_rebuild_from_live_prices','auto_rebuild_from_full_market_shadow','auto_rebuild_from_legacy_v3_label'):
        if r.get(k) is not False: raise SystemExit('UNIVERSE_AUTO_REBUILD_MUST_BE_FALSE:'+k)
    if r.get('authoritative_handoff_required_for_symbol_changes') is not True: raise SystemExit('UNIVERSE_AUTHORITATIVE_HANDOFF_REQUIRED')
    x=c.get('compatibility') or {}
    if x.get('legacy_fully_healthy_scope')!=HEALTH or x.get('overall_observability_must_include_universe_coverage') is not True: raise SystemExit('UNIVERSE_COMPATIBILITY_MISMATCH')
def syms(u):
    s=[str(x).strip() for x in u.get('symbols',[])]
    if not s or len(s)!=len(set(s)) or int(u.get('requested_count',-1))!=len(s): raise SystemExit('LIVE_UNIVERSE_SYMBOL_SET_INVALID')
    return s
def handoff(u,s):
    h=u.get('membership_handoff')
    if h is None:return None
    a=u.get('authority') or {}; exact={'membership':True,'ranking':False,'signal':False,'capital':False,'broker_execution':False}
    if u.get('policy')!='AUTHORITATIVE_HANDOFF_SYMBOL_SET_HARD_BIND' or u.get('symbol_order_semantics')!='SET_ONLY_NOT_RANKING' or a!=exact: raise SystemExit('UNIVERSE_HANDOFF_POLICY_OR_AUTHORITY_MISMATCH')
    if h.get('validated') is not True or h.get('automatic_rebuild') is not False: raise SystemExit('UNIVERSE_HANDOFF_VALIDATION_LOCK_MISMATCH')
    for k in ('ranking_authority','signal_authority','capital_authority','broker_order_execution'):
        if h.get(k) is not False: raise SystemExit('UNIVERSE_HANDOFF_FALSE_LOCK_VIOLATION:'+k)
    if h.get('lineage_semantics')!=LINEAGE or u.get('source_run_id')!=h.get('handoff_id') or u.get('target_date') is None: raise SystemExit('UNIVERSE_HANDOFF_BINDING_MISMATCH')
    m=csha({'trade_date':u.get('target_date'),'symbols':sorted(s)})
    if h.get('membership_sha256')!=m: raise SystemExit('UNIVERSE_HANDOFF_MEMBERSHIP_SHA_MISMATCH')
    for k in ('handoff_sha256','binding_sha256','source_artifact_sha256'):
        v=str(h.get(k) or '')
        if len(v)!=64 or any(x not in '0123456789abcdef' for x in v.lower()): raise SystemExit('UNIVERSE_HANDOFF_SHA_INVALID:'+k)
    return h
def inputs():
    if not U.exists() or not C.exists(): raise SystemExit('LIVE_UNIVERSE_OR_CONTRACT_MISSING_FAIL_CLOSED')
    u=load(U); c=load(C); contract(c); s=syms(u); h=handoff(u,s); return u,c,s,h
def classify(target,now):
    t=pdate(target); n=now if isinstance(now,date) else pdate(now)
    if t is None or n is None:return {'universe_coverage_status':'FAIL_CLOSED_INVALID_SOURCE_DATE','universe_source_age_calendar_days':None,'universe_source_matches_current_trade_date':False,'universe_refresh_required':True}
    age=(n-t).days; status='PASS' if age==0 else ('SOURCE_AGE_REVIEW_REQUIRED' if age>0 else 'FAIL_CLOSED_INVALID_SOURCE_DATE')
    return {'universe_coverage_status':status,'universe_source_age_calendar_days':age,'universe_source_matches_current_trade_date':age==0,'universe_refresh_required':age!=0}
def overall(p,status):
    if status=='FAIL_CLOSED_INVALID_SOURCE_DATE':return 'FAIL_CLOSED_INVALID_UNIVERSE_SOURCE_DATE'
    if str(p.get('transport_health_status','PASS')).upper()!='PASS' or str(p.get('data_freshness_status','PASS')).upper()!='PASS' or p.get('trial_guard_status') not in (None,'PASS'):return 'DEGRADED_LIVE_PIPELINE'
    return 'REVIEW_REQUIRED_UNIVERSE_SOURCE_AGE' if status=='SOURCE_AGE_REVIEW_REQUIRED' else 'PASS'
def fields(p,u,c,s,h):
    d=current(p); st=classify(u.get('target_date'),d); status=st['universe_coverage_status']; authoritative=h is not None
    st.update({'universe_guard_role':ROLE,'universe_coverage_contract_version':c.get('contract_version'),'universe_coverage_contract_sha256':sha(C),'universe_guard_source_file_sha256':sha(U),'universe_source_target_date':u.get('target_date'),'universe_guard_current_trade_date':d.isoformat() if d else None,'universe_coverage_symbol_count':len(s),'universe_source_run_id_lineage_only':True,'universe_source_action_board_version_lineage_only':True,'universe_source_run_id_semantics':LINEAGE,'universe_coverage_ranking_authority':False,'universe_coverage_signal_authority':False,'universe_coverage_capital_authority':False,'universe_coverage_broker_order_execution':False,'universe_auto_rebuilt':False,'universe_authoritative_refresh_provided_to_guard':authoritative,'universe_refresh_mode':'AUTHORITATIVE_HANDOFF_ONLY_NO_AUTO_DERIVATION','universe_existing_bound_coverage_retained':not authoritative,'fully_healthy_scope':HEALTH,'overall_observability_status':overall(p,status),'universe_authoritative_handoff_id':h.get('handoff_id') if h else None,'universe_authoritative_handoff_binding_sha256':h.get('binding_sha256') if h else None})
    st['universe_observability_status']='PASS' if status=='PASS' else ('REVIEW_REQUIRED_UNIVERSE_SOURCE_AGE' if status=='SOURCE_AGE_REVIEW_REQUIRED' else 'FAIL_CLOSED_INVALID_UNIVERSE_SOURCE_DATE')
    return st
def apply():
    u,c,s,h=inputs()
    if not LATEST.exists(): raise SystemExit('LATEST_MISSING')
    p=load(LATEST)
    if p.get('universe_source_run_id')!=u.get('source_run_id') or p.get('universe_version')!=u.get('version') or int(p.get('requested_count',-1))!=len(s): raise SystemExit('LIVE_UNIVERSE_BINDING_MISMATCH')
    f=fields(p,u,c,s,h); p.update(f); dump(LATEST,p); dump(ACTIVE,p); q={k:v for k,v in p.items() if k!='data'}; q['healthy']=int(p.get('success_count',0))>0; dump(STATUS,q)
    print('HENGCE LIVE UNIVERSE GUARD',f['universe_coverage_status'],'target',f['universe_source_target_date'],'current',f['universe_guard_current_trade_date'],'age_days',f['universe_source_age_calendar_days'],'symbols',len(s),'overall',f['overall_observability_status'],'authoritative_handoff',bool(h))
def validate():
    u,c,s,h=inputs(); p=load(LATEST); e=fields(p,u,c,s,h)
    for k,v in e.items():
        if p.get(k)!=v: raise SystemExit('UNIVERSE_GUARD_FIELD_MISMATCH:'+k)
    if p.get('universe_source_run_id')!=u.get('source_run_id') or p.get('universe_target_date')!=u.get('target_date') or p.get('universe_version')!=u.get('version') or int(p.get('requested_count',-1))!=len(s): raise SystemExit('UNIVERSE_BINDING_MISMATCH')
    for k in ('universe_coverage_ranking_authority','universe_coverage_signal_authority','universe_coverage_capital_authority','universe_coverage_broker_order_execution','universe_auto_rebuilt'):
        if p.get(k) is not False: raise SystemExit('UNIVERSE_GUARD_FALSE_LOCK_VIOLATION:'+k)
    if p.get('universe_coverage_status')=='FAIL_CLOSED_INVALID_SOURCE_DATE': raise SystemExit('UNIVERSE_INVALID_SOURCE_DATE_FAIL_CLOSED')
    print('HENGCE LIVE UNIVERSE GUARD VERIFIED',p.get('universe_coverage_status'),'age_days',p.get('universe_source_age_calendar_days'),'symbols',len(s),'authoritative_handoff',bool(h))
def self_test():
    _,c,_,_=inputs(); contract(c)
    assert classify('2026-10-20',date(2026,10,20))['universe_coverage_status']=='PASS'
    assert classify('2026-10-15',date(2026,10,20))['universe_coverage_status']=='SOURCE_AGE_REVIEW_REQUIRED'
    assert classify('2026-10-21',date(2026,10,20))['universe_coverage_status']=='FAIL_CLOSED_INVALID_SOURCE_DATE'
    fake={'target_date':'2026-10-20','source_run_id':'H1','policy':'AUTHORITATIVE_HANDOFF_SYMBOL_SET_HARD_BIND','requested_count':2,'symbols':['2454','2330'],'symbol_order_semantics':'SET_ONLY_NOT_RANKING','authority':{'membership':True,'ranking':False,'signal':False,'capital':False,'broker_execution':False},'membership_handoff':{'validated':True,'automatic_rebuild':False,'handoff_id':'H1','membership_sha256':csha({'trade_date':'2026-10-20','symbols':['2330','2454']}),'handoff_sha256':'a'*64,'binding_sha256':'b'*64,'source_artifact_sha256':'c'*64,'lineage_semantics':LINEAGE,'ranking_authority':False,'signal_authority':False,'capital_authority':False,'broker_order_execution':False}}
    assert handoff(fake,fake['symbols']) is not None
    legacy=dict(fake); legacy.pop('membership_handoff'); legacy['policy']='DAILY_ACTION_BOARD_ROWS_HARD_BIND'; legacy.pop('authority'); legacy.pop('symbol_order_semantics'); assert handoff(legacy,legacy['symbols']) is None
    print(json.dumps({'self_test':'PASS','older_source_is_review_required_not_auto_rebuilt':True,'future_or_missing_source_date_fail_closed':True,'valid_authoritative_handoff_recognized':True,'legacy_universe_not_misclassified_as_handoff':True,'ranking_authority':False,'signal_authority':False,'capital_authority':False,'broker_order_execution':False},ensure_ascii=False))
def main():
    p=argparse.ArgumentParser(); p.add_argument('--mode',choices=('apply','validate','self-test'),default='apply'); a=p.parse_args(); {'apply':apply,'validate':validate,'self-test':self_test}[a.mode]()
if __name__=='__main__': main()
