#!/usr/bin/env python3
"""Synthetic/offline evidence-gate regression. Never accesses FinMind or GitHub."""
import copy
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('gate', Path(__file__).with_name('finmind_monitor_gate_v1.py'))
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

DATE='2026-11-04'
TS='2026-11-04T10:31:04+08:00'
SRC='2026-11-04 10:30:59.000000'
SHA=gate.SHA
m={'constituent_count':8,'current_market_date_count':6,'return_observed_count':6,
   'advance_count':3,'decline_count':2,'flat_count':1,'equal_weight_change_rate':0.1}
base={'metric_contract_sha256':SHA,'feature_detector_input_authority':False,
      'formal_metric_authority':False,'source_binding_promotion_authority':False,
      'raw_finmind_rows_persisted':False,'per_security_rows_persisted':False,
      'trading_authority':False,'one_day_change_rate_may_substitute_locked_ew_return':False}
c={**base,'schema':'HENGCE_ESCAPE_FINMIND_TWSE_COMMON_AGGREGATE_SHADOW_V3',
   'market_date':DATE,'generated_at_taipei':TS,'latest_source_timestamp':SRC,
   'active_required_count':8,'finmind_metric_observation_count':6,'metric_unknown_count':2,
   'formal_escape_state_creation':False,'market':m,'industry':{'24':{'constituent_count':8}}}
c['payload_sha256']=gate.digest(c)
s={**base,'schema':'HENGCE_ESCAPE_FINMIND_TWSE_COMMON_SHADOW_STATUS_V3',
   'generated_at_taipei':TS,'latest_source_timestamp':SRC,'active_required_count':8,
   'active_covered_count':8,'finmind_metric_observation_count':6,'metric_unknown_count':2,
   'formal_escape_authority':False,'formal_eod_authority':False,'trading_authority':False,
   'state':'SHADOW_CONTEXT_READY_NO_FORMAL_AUTHORITY','healthy_transport':True,
   'active_universe_transport_full_coverage':True,'unexpected_missing_count':0,
   'context_payload_sha256':c['payload_sha256']}
a={**base,'schema':'HENGCE_ESCAPE_INTRADAY_MONITOR_V1',
   'market_date':DATE,'generated_at_taipei':TS,'latest_source_timestamp':SRC,
   'active_required_count':8,'active_covered_count':8,
   'finmind_metric_observation_count':6,'metric_unknown_count':2,
   'formal_escape_authority':False,'formal_eod_authority':False,'trading_authority':False,
   'formal_escape_level':None,'monitor_state':'LIVE_CONTEXT_READY',
   'active_universe_transport_full_coverage':True,'market':m,'industry':c['industry'],
   'selection_authority':False,'model_authority':False,
   'quality':{'per_security_rows_persisted':False,'raw_finmind_rows_persisted':False}}
a['payload_sha256']=gate.digest(a)
assert gate.verify(c,s,a,DATE)['status']=='PASS_INTRADAY_MONITOR_ONLY'

def rejects(label, func, date=DATE):
    cc, ss, aa = copy.deepcopy((c,s,a))
    func(cc, ss, aa)
    try:gate.verify(cc, ss, aa, date)
    except ValueError: print('PASS reject:',label);return
    raise AssertionError('FAIL_OPEN:'+label)

rejects('bad requested date',lambda cc,ss,aa:None,'2026-11-05')
rejects('wrong monitor date',lambda cc,ss,aa:aa.update(market_date='2026-11-03'))
rejects('tampered context',lambda cc,ss,aa:cc['market'].update(advance_count=5))
rejects('mismatched unknown rows',lambda cc,ss,aa:ss.update(metric_unknown_count=1))
rejects('fake Escape authority',lambda cc,ss,aa:aa.update(formal_escape_authority=True))
rejects('fake Escape level',lambda cc,ss,aa:aa.update(formal_escape_level='L6_PRICE_DAMAGE'))
rejects('unexpected absent ticker',lambda cc,ss,aa:ss.update(unexpected_missing_count=1))
rejects('source digest mismatch',lambda cc,ss,aa:ss.update(context_payload_sha256='0'*64))
print('PASS all synthetic tests: monitor only, formal Escape remains unverified')
