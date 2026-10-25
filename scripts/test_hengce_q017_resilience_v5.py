#!/usr/bin/env python3
from __future__ import annotations

import json, tempfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import hengce_q017_observation_lock_v5 as v5
import hengce_q017_recovery_compute_v5 as recovery


def fixture():
    trade='2026-10-20';members=['1111','2222','3333']
    o={
      'schema_version':5,'system':'HENGCE','module':'Q017_0901_OBSERVATION_LOCK','trade_date':trade,
      'generated_at_taipei':'2026-10-20T09:01:20+08:00','binding_status':'PASS','authority':'CAUSAL_MARKET_OBSERVATION_ONLY',
      'observation_lock':{'cutoff_label':'09:01','capture_window_taipei':'09:01:00-09:01:59.999999','capture_started_at_taipei':'2026-10-20T09:01:05+08:00','capture_finished_at_taipei':'2026-10-20T09:01:20+08:00','window_valid':True,'immutable':True,'attempt_count':1,'accepted_attempt':1,'computation_may_occur_later':True,'no_late_market_backfill':True},
      'universe_lock':{'scope':v5.UNIVERSE_SCOPE,'source':v5.UNIVERSE_SOURCE,'membership_date':'2026-10-19','member_count':3,'universe_sha256':v5.universe_hash(members),'members':members,'full_market_quote_transport_is_not_ranking_universe':True},
      'eligible_models':[{'ticker':'1111','name':'E1','beta':1.0,'previous_close':100.0},{'ticker':'2222','name':'E2','beta':1.2,'previous_close':100.0},{'ticker':'3333','name':'E3','beta':0.8,'previous_close':100.0}],
      'quotes':{
        '1111':{'ticker':'1111','name':'E1','open':97.0,'reference_close':100.0,'fetched_at_taipei':'2026-10-20T09:01:10+08:00'},
        '2222':{'ticker':'2222','name':'E2','open':98.0,'reference_close':100.0,'fetched_at_taipei':'2026-10-20T09:01:11+08:00'},
        '3333':{'ticker':'3333','name':'E3','open':99.0,'reference_close':100.0,'fetched_at_taipei':'2026-10-20T09:01:12+08:00'}},
      'previous_locked_top3':[],'market_inputs':{'sox':{'sox_1d':-0.01,'sox_5d':-0.04},'dxy':{'latest_session':'2026-10-19','five_sessions_back':'2026-10-12','dxy_5d':-0.004}},
      'premarket_gate':{'status':'PASS'},'premarket_coherence':{'status':'PASS'},'dxy_status':{'status':'PASS','symbol':'DX-Y.NYB','dxy_5d':-0.004},
      'data_status':{'eligible_beta_count':3,'provider_returned_count':3,'provider_coverage':1.0,'provider_coverage_required':1.0,'eligible_quote_row_count':3,'eligible_quote_row_coverage':1.0,'opened_by_decision_count':3,'opened_coverage':1.0,'quote_present_but_no_open_count':0,'coverage_semantics':'QUOTE_ROW_COVERAGE_IS_DATA_COMPLETENESS;OPENED_COVERAGE_IS_CAUSAL_MARKET_STATE','critical_set_rule':'test','critical_set_count':3,'critical_set_complete':True,'critical_missing':[],'batch_failures':[]},
      'policy':'ONLY_0901_OBSERVATION_IS_CAUSAL;COMPUTATION_TIME_MAY_BE_LATER'}
    o['observation_snapshot_sha256']=v5.csha({k:v for k,v in o.items() if k!='observation_snapshot_sha256'})
    return o


def rehash(o):
    o['observation_snapshot_sha256']=v5.csha({k:v for k,v in o.items() if k!='observation_snapshot_sha256'});return o


def main():
    o=fixture();assert v5.validate_observation(o)[0]

    with tempfile.TemporaryDirectory() as td, patch.object(v5, 'OBS_LATEST', Path(td)/'observation_latest.json'):
        root=Path(td);canonical=root/'canonical.json';backup=root/'backup.json'
        backup.write_text(json.dumps(o,ensure_ascii=False),encoding='utf-8')
        promoted,source=recovery.promote_if_needed(date(2026,10,20),canonical,backup)
        assert source=='BACKUP_PROMOTED_TO_CANONICAL'
        assert promoted['observation_snapshot_sha256']==o['observation_snapshot_sha256']
        d=v5.build_decision_from_observation(promoted,datetime.fromisoformat('2026-10-20T09:03:30+08:00'))
        assert d['decision_lock']['authority_semantics']=='OBSERVATION_TIME_LOCK'
        assert d['decision_lock']['calculation_may_occur_after_cutoff'] is True
        assert all(x['ticker'] in set(o['universe_lock']['members']) for x in d['top3'])
        _,source2=recovery.promote_if_needed(date(2026,10,20),canonical,backup);assert source2=='CANONICAL_ALREADY_PRESENT'

    with tempfile.TemporaryDirectory() as td, patch.object(v5, 'OBS_LATEST', Path(td)/'observation_latest.json'):
        root=Path(td)
        try:recovery.promote_if_needed(date(2026,10,20),root/'canonical.json',root/'backup.json')
        except RuntimeError as e:assert 'NO_CANONICAL_OR_BACKUP_0901_OBSERVATION' in str(e)
        else:raise AssertionError('missing observation did not fail closed')

    bad=json.loads(json.dumps(o));bad['eligible_models'].append({'ticker':'2603','name':'NON_ELECTRONICS','beta':9.9,'previous_close':100.0});bad['quotes']['2603']={'ticker':'2603','name':'NON_ELECTRONICS','open':50.0,'reference_close':100.0,'fetched_at_taipei':'2026-10-20T09:01:13+08:00'};bad['data_status']['eligible_beta_count']=4;bad['data_status']['provider_returned_count']=4;rehash(bad)
    ok,reason=v5.validate_observation(bad);assert not ok and reason=='ELIGIBLE_OUTSIDE_ELECTRONICS_UNIVERSE'

    extra=json.loads(json.dumps(o));extra['quotes']['2603']={'ticker':'2603','open':50.0,'reference_close':100.0,'fetched_at_taipei':'2026-10-20T09:01:13+08:00'};rehash(extra)
    ok,reason=v5.validate_observation(extra);assert not ok and reason=='OBS_QUOTES_NOT_100PCT_ELIGIBLE'

    late=json.loads(json.dumps(o));late['quotes']['1111']['fetched_at_taipei']='2026-10-20T09:02:00+08:00';rehash(late)
    ok,reason=v5.validate_observation(late);assert not ok and reason=='OBS_QUOTE_NOT_0901'

    print(json.dumps({'resilience_test':'PASS','checks':['primary_dead_backup_0901_promoted','09:03_compute_from_09:01_evidence_valid','no_observation_fail_closed','non_electronics_high_score_injection_rejected','full_market_extra_cannot_expand_q017','09:02_quote_cannot_backfill_09:01']},ensure_ascii=False))

if __name__=='__main__':main()
