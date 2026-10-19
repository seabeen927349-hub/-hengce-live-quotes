#!/usr/bin/env python3
from __future__ import annotations
import copy, json, tempfile
from datetime import date, datetime
from pathlib import Path
import hengce_q017_decision_lock_v4 as lock
import hengce_q017_authority_guard_v4 as guard

def expect_invalid(payload,contains):
    ok,reason=guard.validate(payload);assert not ok,(contains,reason);assert contains in reason,(contains,reason)
def install_paths(root):
    lock.ROOT=root;lock.RADAR=root/'hengce/q017_radar';lock.HISTORY=lock.RADAR/'history';lock.LATEST=lock.RADAR/'latest.json';lock.SIGNAL_LEDGER=lock.RADAR/'signal_ledger.jsonl';lock.DECISION_DIR=lock.RADAR/'decision';lock.DECISION_LATEST=lock.RADAR/'decision_latest.json';lock.ATTEMPT_DIR=lock.RADAR/'decision_attempts';lock.ATTEMPT_LATEST=lock.RADAR/'decision_attempt_latest.json'
    for p in [lock.HISTORY,lock.DECISION_DIR,lock.ATTEMPT_DIR]:p.mkdir(parents=True,exist_ok=True)
    guard.ROOT=root;guard.RADAR=lock.RADAR;guard.LATEST=lock.LATEST;guard.DECISION_DIR=lock.DECISION_DIR
def recompute(d):d['decision_snapshot_sha256']=lock.canonical_sha({k:v for k,v in d.items() if k!='decision_snapshot_sha256'});return d
def test_retry_then_pass(root):
    install_paths(root);today=date(2026,10,19);t1=datetime(2026,10,19,9,1,10,tzinfo=lock.TZ);t2=datetime(2026,10,19,9,1,12,tzinfo=lock.TZ);end=datetime(2026,10,19,9,1,59,999999,tzinfo=lock.TZ)
    orig=(lock.prepare_model,lock.wait_for_decision_minute,lock.capture_provider_attempt,lock.core.now_tw,lock.time.sleep);calls={'n':0}
    try:
        lock.core.now_tw=lambda:t1;lock.time.sleep=lambda _:None;lock.wait_for_decision_minute=lambda _:(t1,end)
        lock.prepare_model=lambda _:({'status':'PASS','required':{'latest_eod_date':'20261016','electronics_history_latest':'2026-10-16'}},{'status':'PASS'},{'status':'PASS','symbol':'DX-Y.NYB','latest_session':'2026-10-16','five_sessions_back':'2026-10-09','dxy_5d':-0.004},{'status':'PASS'},{'sox_1d':-0.01,'sox_5d':-0.04},{'1111':1.0,'2222':2.0,'3333':3.0,'4444':4.0},{'1111':100.0,'2222':100.0,'3333':100.0,'4444':100.0},{'1111':'A','2222':'B','3333':'C','4444':'D'},'2026-10-16',['1111','2222','3333','4444'],{'status':'PASS','trade_date':'2026-10-19','electronics_history_latest':'2026-10-16','latest_complete_eod_date':'20261016'})
        def attempt(_eligible):
            calls['n']+=1;assert not lock.decision_path(today).exists(),'failed first attempt poisoned immutable decision file';tt=t1 if calls['n']==1 else t2;ids=['1111','2222'] if calls['n']==1 else ['1111','2222','3333','4444'];rows={x:{'ticker':x,'name':x,'open':99.0-float(i),'reference_close':100.0,'fetched_at_taipei':tt.isoformat()} for i,x in enumerate(ids)};return rows,[],[(tt,tt)],tt,tt
        lock.capture_provider_attempt=attempt;snap=lock.capture_decision(today);assert calls['n']==2 and snap['binding_status']=='PASS' and snap['schema_version']==4;assert snap['data_status']['provider_coverage']==1.0 and snap['decision_lock']['attempt_count']==2;ok,reason=guard.validate(snap);assert ok,reason;return snap
    finally:lock.prepare_model,lock.wait_for_decision_minute,lock.capture_provider_attempt,lock.core.now_tw,lock.time.sleep=orig
def test_adversarial(root,snap):
    p=lock.decision_path(date(2026,10,19))
    def install(d):p.write_text(json.dumps(recompute(d),ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return copy.deepcopy(d)
    d=copy.deepcopy(snap);d['decision_lock']['capture_started_at_taipei']='2026-10-19T09:40:00+08:00';d['decision_lock']['capture_finished_at_taipei']='2026-10-19T09:40:01+08:00';d['decision_lock']['window_valid']=False
    for x in d['top3']:x['decision_observed_at_taipei']='2026-10-19T09:40:01+08:00'
    expect_invalid(install(d),'DECISION_WINDOW_VALID_NOT_TRUE')
    d=copy.deepcopy(snap);d['data_status']['provider_returned_count']=3;d['data_status']['provider_coverage']=0.75;expect_invalid(install(d),'PROVIDER_RETURNED_COUNT_NOT_100PCT')
    d=copy.deepcopy(snap);d['binding_status']='DATA_PENDING';expect_invalid(install(d),'DECISION_BINDING_STATUS_NOT_PASS')
    d=copy.deepcopy(snap);d['trade_date']='2026-10-20';payload=install(d);latest=copy.deepcopy(payload);latest['trade_date']='2026-10-19';latest['decision_snapshot_sha256']=payload['decision_snapshot_sha256'];expect_invalid(latest,'DECISION_TRADE_DATE_MISMATCH')
    d=copy.deepcopy(snap);d['market_state']='BANANA';expect_invalid(install(d),'Q017_MARKET_STATE_INCONSISTENT')
    d=copy.deepcopy(snap);d['top3'][0]['score']+=1.0;expect_invalid(install(d),'TOP3_SCORE_MATH_INVALID')
    d=copy.deepcopy(snap);d['data_status']['eligible_beta_count']=424;d['data_status']['provider_returned_count']=423;d['data_status']['provider_coverage']=423/424;expect_invalid(install(d),'PROVIDER_RETURNED_COUNT_NOT_100PCT')
    p.write_text(json.dumps(snap,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');mon=copy.deepcopy(snap);mon['module']='Q017_SOX_ELECTRONICS_RADAR_LOCKED';mon['monitor']={'status':'PASS','rerank_performed':False,'ranking_frozen':True,'marks':[]};ok,reason=guard.validate(mon);assert ok,reason;mon['top3']=list(reversed(mon['top3']));expect_invalid(mon,'LATEST_TOP3_DIFFERS_FROM_LOCKED_DECISION')
def main():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);snap=test_retry_then_pass(root);test_adversarial(root,snap)
    print(json.dumps({'adversarial_v4':'PASS','checks':['same_minute_retry_without_poison','late_0940_forgery_rejected_even_with_fresh_hash','partial_coverage_rejected','binding_pending_rejected','trade_date_mismatch_rejected','invalid_market_state_rejected','score_math_tamper_rejected','single_missing_provider_row_rejected','monitor_rerank_rejected']},ensure_ascii=False))
if __name__=='__main__':main()
