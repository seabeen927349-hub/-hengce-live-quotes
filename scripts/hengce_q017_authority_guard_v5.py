#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from datetime import datetime
from pathlib import Path

import hengce_q017_observation_lock_v5 as v5

ROOT=v5.ROOT; RADAR=v5.RADAR; LATEST=v5.LATEST
FORMAL_SCHEMA=5
FORMAL_MODULE='Q017_SOX_ELECTRONICS_DECISION_LOCK'
MONITOR_MODULE='Q017_SOX_ELECTRONICS_RADAR_LOCKED'
FAIL_MODULES={'Q017_OBSERVATION_TIME_PIPELINE','Q017_AUTHORITY_GUARD_FAIL_CLOSED'}


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def atomic(p,o):v5.core.atomic_json(Path(p),o)
def _trade(p):return str(p.get('trade_date') or '')
def _obs_path(trade,radar=None):return (radar or RADAR)/'observations'/f'{trade.replace("-","")}_0901_observation.json'
def _decision_path(trade):return RADAR/'decision'/f'{trade.replace("-","")}_0901.json'

def validate_decision_payload(d,*,radar=None):
    if int(d.get('schema_version') or 0)!=FORMAL_SCHEMA:return False,'FORMAL_SCHEMA_NOT_V5'
    if d.get('module')!=FORMAL_MODULE:return False,'FORMAL_DECISION_MODULE_INVALID'
    trade=_trade(d)
    if len(trade)!=10:return False,'TRADE_DATE_MISSING'
    op=_obs_path(trade,radar)
    if not op.exists():return False,'OBSERVATION_ARTIFACT_MISSING'
    o=read(op);ok,reason=v5.validate_observation(o)
    if not ok:return False,reason
    if d.get('observation_snapshot_sha256')!=o.get('observation_snapshot_sha256'):return False,'DECISION_NOT_BOUND_TO_OBSERVATION_HASH'
    if (d.get('universe_lock') or {}).get('universe_sha256')!=(o.get('universe_lock') or {}).get('universe_sha256'):return False,'DECISION_UNIVERSE_HASH_MISMATCH'
    if (d.get('rules') or {}).get('universe_scope')!=v5.UNIVERSE_SCOPE:return False,'DECISION_UNIVERSE_SCOPE_DRIFT'
    if (d.get('rules') or {}).get('universe_source')!=v5.UNIVERSE_SOURCE:return False,'DECISION_UNIVERSE_SOURCE_DRIFT'
    try:computed_at=datetime.fromisoformat(str(d.get('generated_at_taipei')))
    except Exception:return False,'DECISION_COMPUTE_TIMESTAMP_INVALID'
    expected=v5.build_decision_from_observation(o,computed_at)
    payload_hash=v5.csha({k:v for k,v in d.items() if k!='decision_snapshot_sha256'})
    if payload_hash!=expected['decision_snapshot_sha256']:return False,'DECISION_NOT_DETERMINISTIC_FROM_LOCKED_OBSERVATION'
    if d.get('decision_snapshot_sha256')!=payload_hash:return False,'DECISION_HASH_INVALID'
    members=set((o.get('universe_lock') or {}).get('members') or [])
    if any(str(x.get('ticker')) not in members for x in d.get('top3') or []):return False,'TOP3_OUTSIDE_ELECTRONICS_UNIVERSE'
    return True,'VALID_V5_OBSERVATION_BOUND_ELECTRONICS_Q017'

def validate(p):
    m=p.get('module')
    if m in FAIL_MODULES:
        if int(p.get('schema_version') or 0)<5:return False,'FAIL_CLOSED_SCHEMA_TOO_OLD'
        if p.get('authority')!='NO_FORMAL_SIGNAL' or int(p.get('formal_buy_count') or 0)!=0:return False,'FAIL_CLOSED_AUTHORITY_INVALID'
        if p.get('top3') not in ([],None):return False,'FAIL_CLOSED_TOP3_NOT_EMPTY'
        return True,'VALID_V5_FAIL_CLOSED'
    if m==FORMAL_MODULE:
        return validate_decision_payload(p)
    if m==MONITOR_MODULE:
        trade=_trade(p);dp=_decision_path(trade)
        if not dp.exists():return False,'LOCKED_DECISION_MISSING'
        d=read(dp);ok,reason=validate_decision_payload(d)
        if not ok:return False,reason
        if p.get('decision_snapshot_sha256')!=d.get('decision_snapshot_sha256'):return False,'MONITOR_DECISION_HASH_MISMATCH'
        if [str(x.get('ticker')) for x in p.get('top3') or []]!=[str(x.get('ticker')) for x in d.get('top3') or []]:return False,'MONITOR_TOP3_CHANGED'
        # monitor() changes only these projection fields. Every decision field,
        # including exact scores and universe members, remains immutable.
        projection={'module','generated_at_taipei','monitor'}
        if {k:v for k,v in p.items() if k not in projection}!={k:v for k,v in d.items() if k not in projection}:return False,'MONITOR_DECISION_FIELDS_CHANGED'
        mon=p.get('monitor') or {}
        if mon.get('rerank_performed') is not False or mon.get('ranking_frozen') is not True:return False,'MONITOR_RERANK_POLICY_INVALID'
        return True,'VALID_V5_LOCKED_MONITOR'
    return False,f'UNAUTHORIZED_Q017_MODULE:{m}'

def quarantine(r,reason):
    return {'schema_version':5,'system':'HENGCE','module':'Q017_AUTHORITY_GUARD_FAIL_CLOSED','generated_at_taipei':v5.core.now_tw().isoformat(),'trade_date':_trade(r) or v5.core.now_tw().date().isoformat(),'binding_status':'DATA_PENDING','market_state':'DATA_PENDING','authority':'NO_FORMAL_SIGNAL','formal_buy_count':0,'top3':[],'reason':reason,'rejected_artifact':{'module':r.get('module'),'schema_version':r.get('schema_version'),'decision_snapshot_sha256':r.get('decision_snapshot_sha256'),'observation_snapshot_sha256':r.get('observation_snapshot_sha256')},'policy':'ONLY_SCHEMA5_DECISIONS_DETERMINISTICALLY_DERIVED_FROM_IMMUTABLE_0901_OBSERVATION_AND_TWSE_ELECTRONICS_UNIVERSE_HAVE_Q017_AUTHORITY'}
def check():
    if not LATEST.exists():print(json.dumps({'status':'PASS','latest':'ABSENT','authority':'NO_FORMAL_SIGNAL'}));return 0
    p=read(LATEST);ok,reason=validate(p)
    if ok:print(json.dumps({'status':'PASS','reason':reason,'module':p.get('module')},ensure_ascii=False));return 0
    q=quarantine(p,reason);atomic(LATEST,q);print(json.dumps({'status':'REPAIRED_FAIL_CLOSED','reason':reason,'formal_buy_count':0},ensure_ascii=False));return 0
def self_test():
    bad={'schema_version':4,'module':FORMAL_MODULE,'trade_date':'2026-10-20'};assert validate(bad)[1]=='FORMAL_SCHEMA_NOT_V5'
    fc={'schema_version':5,'module':'Q017_AUTHORITY_GUARD_FAIL_CLOSED','authority':'NO_FORMAL_SIGNAL','formal_buy_count':0,'top3':[]};assert validate(fc)[0]
    print(json.dumps({'self_test':'PASS','schema':5,'observation_hash_binding':True,'deterministic_recompute_from_observation':True,'electronics_universe_hard_lock':True}))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['check-and-repair','self-test'],required=True);a=ap.parse_args();return self_test() if a.mode=='self-test' else check()
if __name__=='__main__':raise SystemExit(main())
