#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, shutil, tempfile
from datetime import date
from copy import deepcopy
from pathlib import Path

CONTRACT=Path('hengce/HENGCE_LIVE_UNIVERSE_AUTHORITATIVE_HANDOFF_CONTRACT_v1_0_20261020.json')
UNIVERSE=Path('hengce/live_universe.json'); RECEIPTS=Path('receipts')
HANDOFF='LIVE_UNIVERSE_AUTHORITATIVE_HANDOFF'; SOURCE='LIVE_UNIVERSE_MEMBERSHIP_SOURCE'
SOURCE_TYPE='EXPLICIT_AUTHORIZED_MEMBERSHIP_SOURCE'; LINEAGE='LINEAGE_ONLY_NOT_AUTHORITY'
AUTH_ID='HENGCE_LIVE_UNIVERSE_MEMBERSHIP_AUTHORITY_V1'; AUTH_ROLE='LIVE_UNIVERSE_MEMBERSHIP_UPDATE_ONLY'
ROLE='LIVE_UNIVERSE_MEMBERSHIP_UPDATE_ONLY_NO_RANKING_SIGNAL_CAPITAL_AUTHORITY'
SYM=re.compile(r'^[1-9]\d{3}$'); DATE=re.compile(r'^\d{4}-\d{2}-\d{2}$')

def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def dump(p,o):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True); t=p.with_suffix(p.suffix+'.tmp')
    t.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); t.replace(p)
def fsha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def csha(o): return hashlib.sha256(json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def auth(): return {'authority_id':AUTH_ID,'role':AUTH_ROLE,'membership':True,'ranking':False,'signal':False,'capital':False,'broker_execution':False}
def auth_of(o): return {k:o.get(k) for k in auth()}
def symbols(v):
    if not isinstance(v,list) or not v: raise SystemExit('SYMBOLS_MISSING_OR_EMPTY')
    out=[]; seen=set()
    for x in v:
        s=str(x).strip()
        if not SYM.fullmatch(s): raise SystemExit('BAD_SYMBOL:'+s)
        if s in seen: raise SystemExit('DUPLICATE_SYMBOL:'+s)
        seen.add(s); out.append(s)
    return sorted(out)
def membership_sha(d,ss): return csha({'trade_date':d,'symbols':sorted(ss)})
def safe(root,rel,prefix=None):
    r=Path(rel)
    if r.is_absolute() or '..' in r.parts: raise SystemExit('UNSAFE_REPO_PATH:'+str(rel))
    if prefix and not (r==prefix or prefix in r.parents): raise SystemExit('SOURCE_PATH_PREFIX_VIOLATION:'+str(rel))
    return root/r
def binding(h,ss):
    s=h.get('source') or {}
    return {'schema_version':h.get('schema_version'),'system':h.get('system'),'artifact':h.get('artifact'),'handoff_id':h.get('handoff_id'),'trade_date':h.get('trade_date'),'authority':auth_of(h.get('authority') or {}),'source':{'artifact_type':s.get('artifact_type'),'artifact_id':s.get('artifact_id'),'artifact_path':s.get('artifact_path'),'artifact_sha256':s.get('artifact_sha256'),'lineage_semantics':s.get('lineage_semantics'),'historical_lineage':s.get('historical_lineage') or []},'requested_count':h.get('requested_count'),'symbols':sorted(ss),'membership_sha256':h.get('membership_sha256')}
def leak(o,path='root'):
    false={'ranking_authority','signal_authority','capital_authority','broker_order_execution','trade_authority','rank_authority'}
    if isinstance(o,dict):
        for k,v in o.items():
            p=path+'.'+str(k)
            if (k in false and v is not False) or (k in {'ranking','signal','capital','broker_execution'} and isinstance(v,bool) and v is not False): raise SystemExit('AUTHORITY_LEAKAGE:'+p)
            leak(v,p)
    elif isinstance(o,list):
        for i,v in enumerate(o): leak(v,f'{path}[{i}]')
def contract_ok(c):
    if c.get('system')!='HENGCE' or c.get('module')!='HENGCE_LIVE_UNIVERSE_AUTHORITATIVE_HANDOFF' or c.get('role')!=ROLE: raise SystemExit('HANDOFF_CONTRACT_IDENTITY_MISMATCH')
    if (c.get('required_authority') or {})!=auth(): raise SystemExit('HANDOFF_CONTRACT_REQUIRED_AUTHORITY_MISMATCH')
    sp=c.get('source_policy') or {}; cp=c.get('consumer_policy') or {}; ss=c.get('source_artifact_schema') or {}
    if sp.get('required_artifact_type')!=SOURCE_TYPE or sp.get('required_lineage_semantics')!=LINEAGE: raise SystemExit('HANDOFF_CONTRACT_SOURCE_POLICY_MISMATCH')
    if ss.get('path_prefix')!='handoff/authorized_sources/' or ss.get('artifact')!=SOURCE: raise SystemExit('HANDOFF_CONTRACT_SOURCE_SCHEMA_MISMATCH')
    locks={'automatic_rebuild':False,'scheduled_apply':False,'manual_workflow_only':True,'reject_stale_handoff':True,'reject_wrong_count':True,'reject_duplicate_symbols':True,'reject_unknown_authority':True,'reject_shadow_or_v3_as_authority':True,'no_live_price_derivation':True,'no_full_market_shadow_derivation':True,'no_command_center_topn_derivation':True,'no_q017_or_e2_authority_change':True}
    for k,v in locks.items():
        if cp.get(k) is not v: raise SystemExit('HANDOFF_CONTRACT_CONSUMER_POLICY_MISMATCH:'+k)
def validate(root,hrel,expected):
    c=load(root/CONTRACT); contract_ok(c)
    hp=safe(root,hrel)
    if not hp.is_file(): raise SystemExit('HANDOFF_MISSING_FAIL_CLOSED')
    h=load(hp); leak(h)
    if h.get('schema_version')!=1 or h.get('system')!='HENGCE' or h.get('artifact')!=HANDOFF: raise SystemExit('HANDOFF_SCHEMA_IDENTITY_MISMATCH')
    if not DATE.fullmatch(expected or ''): raise SystemExit('EXPECTED_TRADE_DATE_INVALID')
    try: date.fromisoformat(expected)
    except ValueError: raise SystemExit('EXPECTED_TRADE_DATE_INVALID')
    if h.get('trade_date')!=expected: raise SystemExit('STALE_OR_WRONG_TRADE_DATE_HANDOFF')
    if auth_of(h.get('authority') or {})!=auth(): raise SystemExit('HANDOFF_UNKNOWN_OR_INVALID_AUTHORITY')
    ss=symbols(h.get('symbols'))
    if int(h.get('requested_count',-1))!=len(ss): raise SystemExit('HANDOFF_REQUESTED_COUNT_MISMATCH')
    m=membership_sha(expected,ss)
    if h.get('membership_sha256')!=m: raise SystemExit('HANDOFF_MEMBERSHIP_SHA256_MISMATCH')
    s=h.get('source') or {}
    if s.get('artifact_type')!=SOURCE_TYPE or s.get('lineage_semantics')!=LINEAGE: raise SystemExit('HANDOFF_SOURCE_POLICY_MISMATCH')
    candidates='|'.join(str(x or '') for x in [h.get('handoff_id'),(h.get('authority') or {}).get('authority_id'),(h.get('authority') or {}).get('role'),s.get('artifact_type'),s.get('artifact_id')]).upper()
    for marker in (c.get('source_policy') or {}).get('forbidden_authority_markers',[]):
        if str(marker).upper() in candidates: raise SystemExit('FORBIDDEN_AUTHORITY_MARKER:'+str(marker).upper())
    sp=safe(root,s.get('artifact_path') or '',Path('handoff/authorized_sources'))
    if not sp.is_file(): raise SystemExit('SOURCE_ARTIFACT_MISSING')
    actual=fsha(sp)
    if s.get('artifact_sha256')!=actual: raise SystemExit('SOURCE_ARTIFACT_SHA256_MISMATCH')
    src=load(sp); leak(src)
    if src.get('schema_version')!=1 or src.get('system')!='HENGCE' or src.get('artifact')!=SOURCE: raise SystemExit('SOURCE_ARTIFACT_SCHEMA_IDENTITY_MISMATCH')
    if src.get('source_id')!=s.get('artifact_id') or src.get('trade_date')!=expected or auth_of(src.get('authority') or {})!=auth(): raise SystemExit('SOURCE_ARTIFACT_BINDING_MISMATCH')
    sss=symbols(src.get('symbols'))
    if sss!=ss or int(src.get('requested_count',-1))!=len(ss): raise SystemExit('SOURCE_ARTIFACT_MEMBERSHIP_MISMATCH')
    b=csha(binding(h,ss))
    if h.get('binding_sha256')!=b: raise SystemExit('HANDOFF_BINDING_SHA256_MISMATCH')
    return {'contract_sha256':fsha(root/CONTRACT),'handoff':h,'handoff_path':hp,'handoff_sha256':fsha(hp),'source_path':sp,'source_sha256':actual,'symbols':ss,'membership_sha256':m,'binding_sha256':b}
def build(v):
    h=v['handoff']; s=h['source']; ss=v['symbols']; hid=h['handoff_id']; d=h['trade_date']
    return {'schema_version':2,'system':'HENGCE','artifact':'LIVE_UNIVERSE','target_date':d,'source_run_id':hid,'source_action_board_version':'AUTHORITATIVE_MEMBERSHIP_HANDOFF:'+str(s['artifact_id']),'policy':'AUTHORITATIVE_HANDOFF_SYMBOL_SET_HARD_BIND','requested_count':len(ss),'symbols':ss,'symbol_order_semantics':'SET_ONLY_NOT_RANKING','version':'HENGCE_LIVE_UNIVERSE_AUTH_HANDOFF_'+d.replace('-','_')+'_'+v['binding_sha256'][:12],'authority':{'membership':True,'ranking':False,'signal':False,'capital':False,'broker_execution':False},'membership_handoff':{'validated':True,'handoff_id':hid,'handoff_sha256':v['handoff_sha256'],'binding_sha256':v['binding_sha256'],'membership_sha256':v['membership_sha256'],'source_artifact_id':s['artifact_id'],'source_artifact_path':s['artifact_path'],'source_artifact_sha256':v['source_sha256'],'lineage_semantics':LINEAGE,'automatic_rebuild':False,'ranking_authority':False,'signal_authority':False,'capital_authority':False,'broker_order_execution':False}}
def apply(root,hrel,expected):
    v=validate(root,hrel,expected); up=root/UNIVERSE; old=fsha(up) if up.exists() else None
    u=build(v); dump(up,u); new=fsha(up)
    r={'schema_version':1,'system':'HENGCE','receipt':'LIVE_UNIVERSE_AUTHORITATIVE_HANDOFF_APPLY','trade_date':expected,'status':'PASS_VALIDATED_NOT_RANKING_AUTHORITY','handoff_id':v['handoff']['handoff_id'],'handoff_sha256':v['handoff_sha256'],'contract_sha256':v['contract_sha256'],'source_artifact_sha256':v['source_sha256'],'membership_sha256':v['membership_sha256'],'binding_sha256':v['binding_sha256'],'old_universe_sha256':old,'new_universe_sha256':new,'requested_count':len(v['symbols']),'authority':{'membership':True,'ranking':False,'signal':False,'capital':False,'broker_execution':False},'automatic_rebuild':False,'q017_e2_isolation_must_be_revalidated_by_workflow':True}
    rp=root/RECEIPTS/f"HENGCE_LIVE_UNIVERSE_AUTHORITATIVE_HANDOFF_APPLY_{expected.replace('-','')}_{v['binding_sha256'][:12]}.json"; dump(rp,r)
    return {'status':'PASS','universe_sha256':new,'receipt_path':str(rp.relative_to(root)),'requested_count':len(v['symbols']),'trade_date':expected,'handoff_id':v['handoff']['handoff_id']}
def test_files(root,t,trade='2026-10-20',ss=None):
    ss=ss or ['3026','2330','2454']; src={'schema_version':1,'system':'HENGCE','artifact':SOURCE,'source_id':'MANUAL_MEMBERSHIP_SOURCE_001','trade_date':trade,'authority':auth(),'requested_count':len(ss),'symbols':ss}
    sp=t/'handoff/authorized_sources/source.json'; dump(sp,src); n=symbols(ss)
    h={'schema_version':1,'system':'HENGCE','artifact':HANDOFF,'handoff_id':'HENGCE_LIVE_UNIVERSE_HANDOFF_TEST_001','trade_date':trade,'authority':auth(),'source':{'artifact_type':SOURCE_TYPE,'artifact_id':src['source_id'],'artifact_path':str(sp.relative_to(t)),'artifact_sha256':fsha(sp),'lineage_semantics':LINEAGE,'historical_lineage':['LEGACY_V3_REFERENCE_ALLOWED_ONLY_AS_HISTORY']},'requested_count':len(n),'symbols':ss,'membership_sha256':membership_sha(trade,n)}
    h['binding_sha256']=csha(binding(h,n)); hp=t/'handoff/live_universe_authoritative_handoff.json'; dump(hp,h); return hp,h
def fail(fn,text):
    try: fn()
    except SystemExit as e:
        assert text in str(e),(text,str(e)); return
    raise AssertionError('expected '+text)
def self_test(root):
    contract_ok(load(root/CONTRACT))
    with tempfile.TemporaryDirectory() as td:
        t=Path(td); (t/'hengce').mkdir(); shutil.copy2(root/CONTRACT,t/CONTRACT); dump(t/UNIVERSE,{'requested_count':2,'symbols':['2330','2454']})
        hp,h=test_files(root,t); assert validate(t,hp.relative_to(t),'2026-10-20')['symbols']==['2330','2454','3026']
        fail(lambda:validate(t,hp.relative_to(t),'2026-10-21'),'STALE_OR_WRONG_TRADE_DATE_HANDOFF')
        bad=deepcopy(h); bad['requested_count']=9; bad['binding_sha256']=csha(binding(bad,symbols(bad['symbols']))); dump(hp,bad); fail(lambda:validate(t,hp.relative_to(t),'2026-10-20'),'HANDOFF_REQUESTED_COUNT_MISMATCH')
        bad=deepcopy(h); bad['symbols']=['3026','3026','2454']; dump(hp,bad); fail(lambda:validate(t,hp.relative_to(t),'2026-10-20'),'DUPLICATE_SYMBOL')
        bad=deepcopy(h); bad['authority']['authority_id']='UNKNOWN'; dump(hp,bad); fail(lambda:validate(t,hp.relative_to(t),'2026-10-20'),'HANDOFF_UNKNOWN_OR_INVALID_AUTHORITY')
        for marker in ['HENGCE_V3_SCAN_AS_AUTHORITY','FULL_MARKET_SHADOW_20261020']:
            bad=deepcopy(h); bad['source']['artifact_id']=marker; bad['binding_sha256']=csha(binding(bad,symbols(bad['symbols']))); dump(hp,bad); fail(lambda:validate(t,hp.relative_to(t),'2026-10-20'),'FORBIDDEN_AUTHORITY_MARKER')
        before=(t/UNIVERSE).read_bytes(); fail(lambda:apply(t,Path('handoff/missing.json'),'2026-10-20'),'HANDOFF_MISSING_FAIL_CLOSED'); assert (t/UNIVERSE).read_bytes()==before
        hp,_=test_files(root,t); out=apply(t,hp.relative_to(t),'2026-10-20'); u=load(t/UNIVERSE); assert out['requested_count']==3 and u['membership_handoff']['validated'] is True and u['authority']['capital'] is False
    print(json.dumps({'self_test':'PASS','valid_handoff_accepted':True,'stale_wrong_count_duplicate_unknown_authority_rejected':True,'v3_shadow_as_authority_rejected':True,'missing_handoff_preserves_existing_universe':True,'manual_only':True,'q017_e2_authority_changed':False},ensure_ascii=False))
def main():
    p=argparse.ArgumentParser(); p.add_argument('--mode',choices=('self-test','validate','apply'),default='self-test'); p.add_argument('--root',default='.'); p.add_argument('--handoff',default='handoff/live_universe_authoritative_handoff.json'); p.add_argument('--expected-trade-date'); a=p.parse_args(); root=Path(a.root).resolve()
    if a.mode=='self-test': self_test(root); return 0
    if not a.expected_trade_date: raise SystemExit('EXPECTED_TRADE_DATE_REQUIRED_YYYY_MM_DD')
    if a.mode=='validate':
        v=validate(root,Path(a.handoff),a.expected_trade_date); print(json.dumps({'status':'PASS','handoff_id':v['handoff']['handoff_id'],'trade_date':a.expected_trade_date,'requested_count':len(v['symbols']),'membership_sha256':v['membership_sha256'],'binding_sha256':v['binding_sha256'],'ranking_authority':False,'signal_authority':False,'capital_authority':False,'broker_order_execution':False},ensure_ascii=False,indent=2)); return 0
    print(json.dumps(apply(root,Path(a.handoff),a.expected_trade_date),ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
