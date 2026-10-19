#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def replace_once(rel, old, new):
    p=ROOT/rel
    s=p.read_text(encoding='utf-8')
    if new in s:
        print('ALREADY_PATCHED',rel);return
    if old not in s:
        raise RuntimeError(f'PATCH_ANCHOR_MISSING:{rel}')
    p.write_text(s.replace(old,new,1),encoding='utf-8')
    print('PATCHED',rel)

v5='scripts/hengce_q017_observation_lock_v5.py'

replace_once(v5,
"""    if not _close(_f(ds.get('provider_coverage')),1.0) or not _close(_f(ds.get('provider_coverage_required')),1.0):return False,'OBS_PROVIDER_COVERAGE_NOT_100PCT'\n    if ds.get('critical_set_complete') is not True or ds.get('critical_missing') not in ([],None):return False,'OBS_CRITICAL_SET_INCOMPLETE'\n""",
"""    if not _close(_f(ds.get('provider_coverage')),1.0) or not _close(_f(ds.get('provider_coverage_required')),1.0):return False,'OBS_PROVIDER_COVERAGE_NOT_100PCT'\n    qrc=int(ds.get('eligible_quote_row_count') or -1);qcov=_f(ds.get('eligible_quote_row_coverage'));opened=int(ds.get('opened_by_decision_count') if ds.get('opened_by_decision_count') is not None else -1);ocov=_f(ds.get('opened_coverage'))\n    if qrc!=n or not _close(qcov,1.0):return False,'OBS_QUOTE_ROW_COVERAGE_NOT_100PCT'\n    if opened<0 or opened>n:return False,'OBS_OPENED_COUNT_INVALID'\n    if not _close(ocov,opened/n if n else 0.0):return False,'OBS_OPENED_COVERAGE_MISMATCH'\n    if int(ds.get('quote_present_but_no_open_count') if ds.get('quote_present_but_no_open_count') is not None else -1)!=n-opened:return False,'OBS_NOT_OPENED_COUNT_MISMATCH'\n    if ds.get('coverage_semantics')!='QUOTE_ROW_COVERAGE_IS_DATA_COMPLETENESS;OPENED_COVERAGE_IS_CAUSAL_MARKET_STATE':return False,'OBS_COVERAGE_SEMANTICS_DRIFT'\n    if ds.get('critical_set_complete') is not True or ds.get('critical_missing') not in ([],None):return False,'OBS_CRITICAL_SET_INCOMPLETE'\n""")

replace_once(v5,
"""'eligible_beta_count':ds['eligible_beta_count'],'provider_returned_count':ds['provider_returned_count'],'provider_coverage':ds['provider_coverage'],'provider_coverage_required':1.0,'opened_by_decision_count':opened,""",
"""'eligible_beta_count':ds['eligible_beta_count'],'provider_returned_count':ds['provider_returned_count'],'provider_coverage':ds['provider_coverage'],'provider_coverage_required':1.0,'eligible_quote_row_count':ds['eligible_quote_row_count'],'eligible_quote_row_coverage':ds['eligible_quote_row_coverage'],'opened_by_decision_count':opened,'opened_coverage':opened/ds['eligible_beta_count'] if ds['eligible_beta_count'] else 0.0,'quote_present_but_no_open_count':ds['eligible_beta_count']-opened,'coverage_semantics':ds['coverage_semantics'],""")

replace_once(v5,
"""    rec,fail,s,e,cov=accepted\n    models=[{'ticker':t,'name':names.get(t,''),'beta':betas[t],'previous_close':prev[t]} for t in eligible]\n""",
"""    rec,fail,s,e,cov=accepted\n    opened_rows=sum((q or {}).get('open') is not None for q in rec.values())\n    models=[{'ticker':t,'name':names.get(t,''),'beta':betas[t],'previous_close':prev[t]} for t in eligible]\n""")

replace_once(v5,
"""'data_status':{'eligible_beta_count':len(eligible),'provider_returned_count':len(rec),'provider_coverage':cov,'provider_coverage_required':1.0,'critical_set_rule':'top 50 positive Beta60 plus previous locked Top3','critical_set_count':len(crit),'critical_set_complete':True,'critical_missing':[],'batch_failures':fail[:20]},""",
"""'data_status':{'eligible_beta_count':len(eligible),'provider_returned_count':len(rec),'provider_coverage':cov,'provider_coverage_required':1.0,'eligible_quote_row_count':len(rec),'eligible_quote_row_coverage':len(rec)/len(eligible) if eligible else 0.0,'opened_by_decision_count':opened_rows,'opened_coverage':opened_rows/len(eligible) if eligible else 0.0,'quote_present_but_no_open_count':len(eligible)-opened_rows,'coverage_semantics':'QUOTE_ROW_COVERAGE_IS_DATA_COMPLETENESS;OPENED_COVERAGE_IS_CAUSAL_MARKET_STATE','critical_set_rule':'top 50 positive Beta60 plus previous locked Top3','critical_set_count':len(crit),'critical_set_complete':True,'critical_missing':[],'batch_failures':fail[:20]},""")

replace_once(v5,
"""'data_status':{'eligible_beta_count':2,'provider_returned_count':2,'provider_coverage':1.0,'provider_coverage_required':1.0,'critical_set_complete':True,'critical_missing':[],'critical_set_count':2,'critical_set_rule':'test'},""",
"""'data_status':{'eligible_beta_count':2,'provider_returned_count':2,'provider_coverage':1.0,'provider_coverage_required':1.0,'eligible_quote_row_count':2,'eligible_quote_row_coverage':1.0,'opened_by_decision_count':2,'opened_coverage':1.0,'quote_present_but_no_open_count':0,'coverage_semantics':'QUOTE_ROW_COVERAGE_IS_DATA_COMPLETENESS;OPENED_COVERAGE_IS_CAUSAL_MARKET_STATE','critical_set_complete':True,'critical_missing':[],'critical_set_count':2,'critical_set_rule':'test'},""")

replace_once(v5,
"""    d=build_decision_from_observation(obs,datetime.fromisoformat('2026-10-20T09:03:30+08:00'));assert d['generated_at_taipei'].startswith('2026-10-20T09:03:30');assert all(x['ticker'] in {'1111','2222'} for x in d['top3'])\n    bad=json.loads(json.dumps(obs));bad['eligible_models'].append({'ticker':'2603','beta':3.0,'previous_close':100.0});""",
"""    d=build_decision_from_observation(obs,datetime.fromisoformat('2026-10-20T09:03:30+08:00'));assert d['generated_at_taipei'].startswith('2026-10-20T09:03:30');assert all(x['ticker'] in {'1111','2222'} for x in d['top3'])\n    not_open=json.loads(json.dumps(obs));not_open['quotes']['2222']['open']=None;not_open['data_status']['opened_by_decision_count']=1;not_open['data_status']['opened_coverage']=0.5;not_open['data_status']['quote_present_but_no_open_count']=1;not_open['observation_snapshot_sha256']=csha({k:v for k,v in not_open.items() if k!='observation_snapshot_sha256'});assert validate_observation(not_open)[0];nd=build_decision_from_observation(not_open,datetime.fromisoformat('2026-10-20T09:03:30+08:00'));assert all(x['ticker']!='2222' for x in nd['top3'])\n    bad=json.loads(json.dumps(obs));bad['eligible_models'].append({'ticker':'2603','beta':3.0,'previous_close':100.0});""")

# Resilience fixture must carry explicit coverage semantics too.
replace_once('scripts/test_hengce_q017_resilience_v5.py',
"""'data_status':{'eligible_beta_count':3,'provider_returned_count':3,'provider_coverage':1.0,'provider_coverage_required':1.0,'critical_set_rule':'test','critical_set_count':3,'critical_set_complete':True,'critical_missing':[],'batch_failures':[]},""",
"""'data_status':{'eligible_beta_count':3,'provider_returned_count':3,'provider_coverage':1.0,'provider_coverage_required':1.0,'eligible_quote_row_count':3,'eligible_quote_row_coverage':1.0,'opened_by_decision_count':3,'opened_coverage':1.0,'quote_present_but_no_open_count':0,'coverage_semantics':'QUOTE_ROW_COVERAGE_IS_DATA_COMPLETENESS;OPENED_COVERAGE_IS_CAUSAL_MARKET_STATE','critical_set_rule':'test','critical_set_count':3,'critical_set_complete':True,'critical_missing':[],'batch_failures':[]},""")

# Backup receipt exposes both semantics explicitly.
replace_once('scripts/hengce_q017_backup_observer_v5.py',
"""        'provider_coverage':(out.get('data_status') or {}).get('provider_coverage'),\n        'policy':'May be promoted only if canonical 09:01 observation is absent and this artifact passes schema-v5 validation.'\n""",
"""        'provider_coverage':(out.get('data_status') or {}).get('provider_coverage'),\n        'eligible_quote_row_coverage':(out.get('data_status') or {}).get('eligible_quote_row_coverage'),\n        'opened_coverage':(out.get('data_status') or {}).get('opened_coverage'),\n        'quote_present_but_no_open_count':(out.get('data_status') or {}).get('quote_present_but_no_open_count'),\n        'coverage_semantics':(out.get('data_status') or {}).get('coverage_semantics'),\n        'policy':'May be promoted only if canonical 09:01 observation is absent and this artifact passes schema-v5 validation.'\n""")

print('PASS Q017_COVERAGE_SEMANTICS_REPAIR_APPLIED')
