#!/usr/bin/env python3
"""Offline zero-authority evaluator. Never imports a producer or repairs state."""
import argparse
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Taipei')
ZERO = dict(health_only=True, signal_authority=False, ranking_authority=False,
            capital_authority_twd=0, broker_order_execution=False)
ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / 'config/hengce_health_v1.json'
PATHS = {'q017': 'hengce/q017_radar/observation_latest.json',
         'e2_morning': 'hengce/e2_live/morning_latest.json',
         'eod': 'eod/{date}/status.json', 'display': 'hengce/dual_engine/latest.json'}
EXTRA_PATHS = ('hengce/q017_radar/latest.json', 'hengce/e2_live/state_latest.json')
WORKFLOW_KEYS = {'id','name','file','crons_utc','taipei_interpretation','start_grace_minutes',
                 'max_runtime_minutes','missing_state','expected_artifacts','artifact_authority'}
RULE_KEYS = {'id','kind','path','date_field','timestamp_field','due_taipei','grace_minutes',
             'on_time_start','on_time_end','recovery_deadline','late_state','semantic_pass',
             'semantic_pending','source_authority'}
PASS_FIELDS = {'q017': {'schema_version','module','binding_status','authority'},
               'e2_morning': {'module','binding_status','capital_authority_twd','broker_order_execution'},
               'eod': {'price_status','institutional_status','margin_status','mother_status',
                       'downstream_ready','three_leg_complete','formal_complete_day'},
               'display': {'architecture','rankings_separate','mixed_ranking_forbidden','legacy_v3_display_authority'}}
PASS_VALUES = {
    'q017': dict(schema_version=5,module='Q017_0901_OBSERVATION_LOCK',binding_status='PASS',authority='CAUSAL_MARKET_OBSERVATION_ONLY'),
    'e2_morning': dict(module='E2_PROFIT_MAX_MORNING_BRIDGE',binding_status='PASS',capital_authority_twd=0,broker_order_execution=False),
    'eod': dict(price_status='COMPLETE',institutional_status='COMPLETE',margin_status='COMPLETE',mother_status='COMPLETE',downstream_ready=True,three_leg_complete=True,formal_complete_day=True),
    'display': dict(architecture='DUAL_ENGINE',rankings_separate=True,mixed_ranking_forbidden=True,legacy_v3_display_authority=False)}
WORKFLOW_FILES = dict(q017_primary='hengce-q017-primary-observer.yml',q017_backup='hengce-q017-backup-observer.yml',
    daily='hengce-daily-command-center.yml',e2_backup='hengce-e2-morning-backup.yml',
    q017_recovery='hengce-q017-recovery.yml',macro='hengce-q017-macro-cache.yml',
    e2_postclose='hengce-e2-profit-max-live.yml',display='hengce-dual-engine-display-refresh.yml')


def stamp(value):
    d = datetime.fromisoformat(value)
    if d.tzinfo is None:
        raise ValueError('NAIVE_TIMESTAMP')
    return d.astimezone(TZ)


def at(now, clock):
    h, m = map(int, clock.split(':'))
    return now.replace(hour=h, minute=m, second=0, microsecond=0)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def result(state, *reasons, **metadata):
    return dict(state=state, reason_codes=list(reasons), **metadata)


def worst(states):
    states = list(states)
    for state in ('FAIL_CLOSED', 'DEGRADED', 'PENDING_DATA', 'PASS'):
        if state in states:
            return state
    return 'NOT_DUE'


@lru_cache(maxsize=256)
def cron_field(expression, maximum):
    values = set()
    for part in expression.split(','):
        term, _, step = part.partition('/')
        stride = int(step or 1)
        if stride < 1:
            raise ValueError('INVALID_CRON_STEP')
        if term == '*':
            lo, hi = 0, maximum
        elif '-' in term:
            lo, hi = map(int, term.split('-'))
        else:
            lo = hi = int(term)
        if not 0 <= lo <= hi <= maximum:
            raise ValueError('INVALID_CRON_RANGE')
        values.update(range(lo, hi + 1, stride))
    return values


def occurrences(now, crons):
    start = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    slots = set()
    for cron in crons:
        minute, hour, dom, month, dow = cron.split()
        if dom != '*' or month != '*':
            raise ValueError('UNSUPPORTED_CALENDAR_CRON')
        mins, hours, weekdays = cron_field(minute, 59), cron_field(hour, 23), cron_field(dow, 6)
        for offset in range(1440):
            d = start + timedelta(minutes=offset)
            if d.minute in mins and d.hour in hours and (d.weekday() + 1) % 7 in weekdays:
                slots.add(d.astimezone(TZ))
    return sorted(slots)


def zero_valid(obj):
    return all(k in obj and type(obj[k]) is type(v) and obj[k] == v for k,v in ZERO.items())


def validate_policy(p):
    if set(p) != {'schema_version','authoritative_base','calendar','workflows','artifacts',*ZERO} or p['schema_version'] != 1 or not zero_valid(p):
        raise ValueError('UNKNOWN_OR_UNSAFE_CONTRACT')
    if set(p['calendar']) != {'authoritative_exchange_calendar','weekend_not_due','limitation'} or p['calendar']['authoritative_exchange_calendar'] is not False or p['calendar']['weekend_not_due'] is not True:
        raise ValueError('CALENDAR_AUTHORITY_FORBIDDEN')
    if len(p['artifacts']) != 4 or {x['id'] for x in p['artifacts']} != set(PATHS):
        raise ValueError('UNKNOWN_ARTIFACT_KIND')
    for r in p['artifacts']:
        kind = r['id']
        if set(r) != RULE_KEYS or r['kind'] != kind or r['path'] != PATHS[kind] or set(r['semantic_pass']) != PASS_FIELDS[kind]:
            raise ValueError('UNKNOWN_CONTRACT_FIELD_OR_PATH')
        if any(type(r['semantic_pass'][k]) is not type(v) or r['semantic_pass'][k] != v for k,v in PASS_VALUES[kind].items()):
            raise ValueError('UNKNOWN_SOURCE_SEMANTICS')
        expected_dates = {'q017':'trade_date','e2_morning':'trade_date','eod':'target_date','display':None}
        if r['date_field'] != expected_dates[kind] or r['timestamp_field'] != ('updated_at_taipei' if kind == 'eod' else 'generated_at_taipei'):
            raise ValueError('UNKNOWN_CONTRACT_TIMESTAMP_OR_DATE')
        if set(r['semantic_pending']) != ({'price_status','institutional_status','margin_status','mother_status'} if kind == 'eod' else set()):
            raise ValueError('UNKNOWN_PENDING_CONTRACT')
        if any(v != ['PENDING'] for v in r['semantic_pending'].values()):
            raise ValueError('UNKNOWN_PENDING_SEMANTICS')
        for key in ('due_taipei','on_time_start','on_time_end','recovery_deadline'):
            if r[key] is not None:
                at(datetime(2026,1,1,tzinfo=TZ), r[key])
        if type(r['grace_minutes']) is not int or r['grace_minutes'] < 0 or r['late_state'] not in ('DEGRADED','FAIL_CLOSED'):
            raise ValueError('INVALID_HEALTH_WINDOW')
        if kind == 'e2_morning' and (any(r[k] is None for k in ('on_time_start','on_time_end','recovery_deadline')) or not r['on_time_start'] <= r['on_time_end'] <= r['recovery_deadline']):
            raise ValueError('INVALID_E2_RECOVERY_WINDOW')
    ids = set()
    for w in p['workflows']:
        if set(w) != WORKFLOW_KEYS or w['id'] in ids or w['file'] != WORKFLOW_FILES.get(w['id']):
            raise ValueError('UNKNOWN_WORKFLOW_CONTRACT')
        ids.add(w['id'])
        if w['missing_state'] not in ('DEGRADED','FAIL_CLOSED') or any(x not in PATHS for x in w['expected_artifacts']):
            raise ValueError('UNSAFE_WORKFLOW_POLICY')
        for k in ('start_grace_minutes','max_runtime_minutes'):
            if type(w[k]) is not int or w[k] < 1:
                raise ValueError('INVALID_WORKFLOW_GRACE')
        occurrences(datetime(2026,10,22,tzinfo=TZ), tuple(w['crons_utc']))
    if ids != {'q017_primary','q017_backup','daily','e2_backup','q017_recovery','macro','e2_postclose','display'}:
        raise ValueError('UNKNOWN_WORKFLOW_LANE')


def scheduler(now, manifest, policy):
    try:
        required = {'schema_version','collected_at_utc','coverage_start_utc','coverage_end_utc','complete','errors','runs',*ZERO}
        if set(manifest) != required or manifest['schema_version'] != 1 or not zero_valid(manifest):
            raise ValueError('RUN_MANIFEST_INVALID')
        midnight = now.replace(hour=0,minute=0,second=0,microsecond=0)
        if manifest['complete'] is not True or manifest['errors']:
            raise ValueError('RUN_COLLECTION_INCOMPLETE')
        if stamp(manifest['coverage_start_utc']) > midnight or stamp(manifest['coverage_end_utc']) < now - timedelta(minutes=2):
            raise ValueError('RUN_COVERAGE_INCOMPLETE')
        age = (now - stamp(manifest['collected_at_utc'])).total_seconds()
        if not 0 <= age <= 900:
            raise ValueError('RUN_MANIFEST_STALE_OR_FUTURE')
        run_keys = {'id','workflow_file','event','head_branch','created_at','run_started_at','status','conclusion'}
        for run in manifest['runs']:
            if set(run) != run_keys or stamp(run['created_at']) > now:
                raise ValueError('RUN_RECORD_INVALID')
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        return result('DEGRADED','SCHEDULER_METADATA_UNAVAILABLE', detail=str(exc), workflows={})
    workflows = {}
    for w in policy['workflows']:
        expected = occurrences(now, tuple(w['crons_utc']))
        slots = []
        for i, due in enumerate(expected):
            if due > now:
                continue
            end = expected[i+1] if i+1 < len(expected) else due.replace(hour=23,minute=59,second=59,microsecond=999999)
            runs = [r for r in manifest['runs'] if r['workflow_file'] == w['file'] and r['event'] == 'schedule' and r['head_branch'] == 'main' and due <= stamp(r['created_at']) < end]
            grace = due + timedelta(minutes=w['start_grace_minutes'])
            metadata = dict(expected_at_taipei=due.isoformat(), run_ids=[r['id'] for r in runs])
            if not runs:
                slots.append(result(w['missing_state'] if now > grace else 'NOT_DUE',
                    'MISSING_SCHEDULED_RUN' if now > grace else 'WITHIN_START_GRACE', **metadata))
                continue
            r = sorted(runs, key=lambda x: stamp(x['created_at']))[0]
            reasons, state = [], 'PASS'
            metadata.update(status=r['status'],conclusion=r['conclusion'],created_at=r['created_at'],run_started_at=r['run_started_at'])
            if len(runs) > 1:
                state = 'DEGRADED'; reasons.append('AMBIGUOUS_SCHEDULE_SLOT')
            if r['status'] in ('queued','waiting','requested','pending') or not r['run_started_at']:
                state = w['missing_state'] if now > grace else 'NOT_DUE'
                reasons.append('NOT_STARTED_AFTER_GRACE' if now > grace else 'QUEUED_WITHIN_GRACE')
            else:
                try:
                    started = stamp(r['run_started_at'])
                    if started < stamp(r['created_at']) or started > now:
                        raise ValueError('INVALID_START')
                    if started > grace:
                        state = worst([state,'DEGRADED']); reasons.append('LATE_RUN')
                    if r['status'] != 'completed' and now > started + timedelta(minutes=w['max_runtime_minutes']):
                        state = w['missing_state']; reasons.append('RUN_OVERDUE')
                except (ValueError,TypeError):
                    state='DEGRADED'; reasons.append('RUN_START_UNPROVEN')
            if r['status'] == 'completed' and r['conclusion'] != 'success':
                state=w['missing_state']; reasons.append('WORKFLOW_FAILED')
            if not reasons:
                reasons.append('SCHEDULED_RUN_ON_TIME')
            slots.append(result(state,*reasons,**metadata))
        workflows[w['id']] = result(worst(s['state'] for s in slots),
            'EVENT_DRIVEN_NOT_SCHEDULED' if not expected else 'SCHEDULE_SLOTS_EVALUATED', file=w['file'],slots=slots)
    return result(worst(w['state'] for w in workflows.values()),'SCHEDULE_LIVENESS_EVALUATED',workflows=workflows)


def source_metadata(obj, rule, now):
    generated = obj.get(rule['timestamp_field'])
    date = obj.get(rule['date_field']) if rule['date_field'] else None
    try:
        age = (now - stamp(generated)).total_seconds()
    except (TypeError,ValueError):
        age = None
    return dict(source_date=date,source_timestamp=generated,source_age_seconds=age)


def observation_valid(obj, canonical, now):
    if obj != canonical:
        return False, 'Q017_CANONICAL_BINDING_MISSING_OR_DIFFERENT'
    try:
        if obj['schema_version'] != 5 or obj['module'] != 'Q017_0901_OBSERVATION_LOCK' or obj['binding_status'] != 'PASS':
            return False,'Q017_SCHEMA_OR_BINDING_INVALID'
        if obj['observation_snapshot_sha256'] != digest({k:v for k,v in obj.items() if k != 'observation_snapshot_sha256'}):
            return False,'Q017_OBSERVATION_HASH_INVALID'
        lock = obj['observation_lock']
        if lock['immutable'] is not True or lock['window_valid'] is not True or lock['cutoff_label'] != '09:01':
            return False,'Q017_OBSERVATION_LOCK_INVALID'
        times = [stamp(lock[k]) for k in ('capture_started_at_taipei','capture_finished_at_taipei')]
        times += [stamp(q['fetched_at_taipei']) for q in obj['quotes'].values()]
        times += [stamp(obj['generated_at_taipei'])]
        if not obj['quotes'] or any(t.date() != now.date() or (t.hour,t.minute) != (9,1) or t > now for t in times) or times[0] > times[1]:
            return False,'Q017_CAPTURE_LATE_OR_OUT_OF_WINDOW'
        u = obj['universe_lock']; members = u['members']
        if u['scope'] != 'TWSE_LISTED_ELECTRONICS_ONLY' or u['source'] != 'TWSE_MI_INDEX_TYPE_13_ELECTRONICS_HISTORY' or any(not re.fullmatch(r'[1-9]\d{3}',str(m)) for m in members) or len(members) != len(set(members)) or u['member_count'] != len(members) or u['universe_sha256'] != digest(sorted(str(m) for m in members)):
            return False,'Q017_UNIVERSE_HASH_INVALID'
        if datetime.strptime(u['membership_date'],'%Y-%m-%d').date() >= now.date():
            return False,'Q017_MEMBERSHIP_NOT_CAUSAL'
        eligible = {str(x['ticker']) for x in obj['eligible_models']}
        if not eligible or len(eligible) != len(obj['eligible_models']) or eligible != set(obj['quotes']) or not eligible <= set(members):
            return False,'Q017_QUOTE_POPULATION_INVALID'
        for model in obj['eligible_models']:
            if any(not math.isfinite(float(model[k])) or float(model[k]) <= 0 for k in ('beta','previous_close')):
                return False,'Q017_ELIGIBLE_MODEL_INVALID'
        n=len(eligible); ds=obj['data_status']; opened=ds['opened_by_decision_count']
        if any(ds[k] != n for k in ('eligible_beta_count','provider_returned_count','eligible_quote_row_count')) or any(ds[k] != 1.0 for k in ('provider_coverage','provider_coverage_required','eligible_quote_row_coverage')):
            return False,'Q017_COVERAGE_INVALID'
        if type(opened) is not int or not 0 <= opened <= n or not math.isclose(ds['opened_coverage'],opened/n,rel_tol=1e-10) or ds['quote_present_but_no_open_count'] != n-opened or ds['critical_set_complete'] is not True or ds['critical_missing']:
            return False,'Q017_COVERAGE_OR_CRITICAL_SET_INVALID'
        if any(str(q.get('ticker',t)) != str(t) for t,q in obj['quotes'].items()):
            return False,'Q017_QUOTE_TICKER_INVALID'
        mi=obj['market_inputs']
        if any(not math.isfinite(float(v)) for v in (mi['sox']['sox_1d'],mi['sox']['sox_5d'],mi['dxy']['dxy_5d'])):
            return False,'Q017_MARKET_INPUT_INVALID'
        return True,'Q017_VALID_IMMUTABLE_0901_CAPTURE'
    except (KeyError,TypeError,ValueError,AttributeError,OverflowError):
        return False,'Q017_OBSERVATION_INVALID'


def source_safety(kind, obj):
    unsafe = []
    for x in (obj, obj.get('e2', {}) if kind == 'display' else {}):
        if not isinstance(x,dict):
            unsafe.append('SOURCE_STRUCTURE_INVALID'); continue
        if 'capital_authority_twd' in x and (type(x['capital_authority_twd']) is not int or x['capital_authority_twd'] != 0):
            unsafe.append('SOURCE_CAPITAL_AUTHORITY_NONZERO')
        if x.get('broker_order_execution',False) is not False:
            unsafe.append('SOURCE_BROKER_EXECUTION_ENABLED')
    if kind == 'e2_morning' and (type(obj.get('capital_authority_twd')) is not int or obj.get('capital_authority_twd') != 0 or obj.get('broker_order_execution') is not False):
        unsafe.append('E2_ZERO_AUTHORITY_FIELDS_INVALID')
    if kind == 'display':
        if any(obj.get(k) is not v for k,v in {'rankings_separate':True,'mixed_ranking_forbidden':True,'legacy_v3_display_authority':False}.items()):
            unsafe.append('DISPLAY_AUTHORITY_ISOLATION_INVALID')
        q = obj.get('q017',{}); e = obj.get('e2',{})
        if not isinstance(q,dict) or not isinstance(e,dict) or type(e.get('capital_authority_twd')) is not int or e.get('capital_authority_twd') != 0 or e.get('broker_order_execution') is not False:
            unsafe.append('DISPLAY_ZERO_AUTHORITY_FIELDS_INVALID')
        elif q.get('status') == 'CASH' and q.get('formal_buy_count',0) != 0:
            unsafe.append('DISPLAY_CASH_BUY_COUNT_CONTRADICTION')
    if kind == 'eod' and obj.get('model_authority_created',False) is not False:
        unsafe.append('EOD_UNEXPECTED_MODEL_AUTHORITY')
    return result('FAIL_CLOSED' if unsafe else 'PASS',*(unsafe or ['SOURCE_AUTHORITY_BOUNDARIES_SAFE']))


def evaluate(now, artifacts, manifest, policy, main_sha):
    if not isinstance(now,str) and now.tzinfo is None:
        raise ValueError('NAIVE_EVALUATION_TIME')
    now = stamp(now) if isinstance(now,str) else now.astimezone(TZ)
    output = dict(schema_version=1,system='HENGCE',module='HENGCE_SYSTEM_HEALTH',
        generated_at_taipei=now.isoformat(),evaluated_trade_date=now.date().isoformat(),
        authoritative_main_sha=main_sha,**ZERO)
    output['calendar']=dict(confidence='CONTRACT_UNVERIFIED',authoritative_exchange_calendar=False,
        market_data_expected='UNVERIFIED_EXCHANGE_SESSION',limitation='No authoritative exchange calendar is supplied.')
    try:
        validate_policy(policy)
        output['health_policy_sha256']=digest(policy)
    except (ValueError,TypeError,KeyError,AttributeError) as exc:
        output.update(state='FAIL_CLOSED',reason_codes=['HEALTH_CONTRACT_INVALID'],detail=str(exc))
        for name in ('scheduler_liveness','artifact_freshness','data_readiness','authority_safety'):
            output[name] = result('FAIL_CLOSED','HEALTH_CONTRACT_INVALID')
        return output
    output['calendar'] = dict(confidence='WEEKDAY_CRON_ONLY_NOT_EXCHANGE_CALENDAR',
        workflow_schedule_expected='BY_UTC_CRON',market_data_expected='UNVERIFIED_EXCHANGE_SESSION',
        **policy['calendar'])
    output['scheduler_liveness'] = scheduler(now,manifest,policy)
    fresh, ready, safety = {}, {}, {}
    today = now.date().isoformat(); compact = now.strftime('%Y%m%d')
    for rule in policy['artifacts']:
        kind = rule['id']; path = rule['path'].format(date=compact)
        obj = artifacts.get(path)
        due = now.weekday() < 5 and now >= at(now,rule['due_taipei']) + timedelta(minutes=rule['grace_minutes'])
        if not isinstance(obj,dict):
            fresh[kind] = result('FAIL_CLOSED' if due else 'NOT_DUE','ARTIFACT_MISSING' if due else 'ARTIFACT_NOT_DUE',path=path)
            ready[kind] = result('PENDING_DATA' if due else 'NOT_DUE','SOURCE_UNAVAILABLE')
            safety[kind] = result('NOT_DUE','NO_SOURCE_TO_INSPECT')
            continue
        safety[kind] = source_safety(kind,obj)
        metadata = dict(path=path,**source_metadata(obj,rule,now))
        date = metadata['source_date']; age = metadata['source_age_seconds']
        if not due:
            fresh[kind]=result('NOT_DUE','ARTIFACT_NOT_DUE',**metadata)
            ready[kind]=result('NOT_DUE','DATA_NOT_DUE')
            continue
        if rule['date_field'] and date != today:
            fresh[kind]=result('FAIL_CLOSED' if kind == 'q017' else 'DEGRADED','STALE_SOURCE_DATE',**metadata)
            ready[kind]=result('PENDING_DATA','CURRENT_SOURCE_UNAVAILABLE')
            continue
        if age is None or age < 0:
            fresh[kind]=result('FAIL_CLOSED' if kind == 'q017' else 'DEGRADED','SOURCE_TIMESTAMP_INVALID',**metadata)
            ready[kind]=result('PENDING_DATA','SOURCE_TIME_UNPROVEN')
            continue
        semantic = all(type(obj.get(k)) is type(v) and obj.get(k) == v for k,v in rule['semantic_pass'].items())
        if kind == 'q017':
            canonical = artifacts.get(f'hengce/q017_radar/observations/{compact}_0901_observation.json')
            valid, reason = observation_valid(obj,canonical,now)
            if not semantic:
                valid,reason=False,'Q017_SEMANTIC_CONTRACT_INVALID'
            fresh[kind]=result('PASS' if valid and semantic else 'FAIL_CLOSED',reason,publication_first_seen='NOT_PROVEN_BY_GENERATION_TIME',**metadata)
            ready[kind]=result('PASS' if valid else 'PENDING_DATA',reason)
        elif kind == 'e2_morning':
            generated = stamp(obj[rule['timestamp_field']])
            if not semantic:
                state, reason='FAIL_CLOSED','E2_BINDING_OR_MODULE_INVALID'
            elif generated < at(now,rule['on_time_start']):
                state, reason='DEGRADED','EARLY_BIND'
            elif generated <= at(now,rule['on_time_end']):
                state, reason='PASS','ON_TIME'
            elif generated <= at(now,rule['recovery_deadline']):
                state, reason='DEGRADED','RECOVERY_WINDOW'
            else:
                state, reason=rule['late_state'],'LATE_RECOVERY'
            fresh[kind]=result(state,reason,**metadata)
            ready[kind]=result('PASS' if semantic else 'PENDING_DATA','E2_BOUND' if semantic else 'E2_NOT_BOUND')
        elif kind == 'eod':
            statuses={k:obj.get(k+'_status') for k in ('price','institutional','margin','mother')}
            unknown=[k for k,v in statuses.items() if v not in ('COMPLETE','PENDING','PARTIAL','ERROR',None)]
            state='PASS' if semantic else ('FAIL_CLOSED' if unknown or 'ERROR' in statuses.values() else 'PENDING_DATA')
            reasons=['EOD_READY' if semantic else 'SOURCE_STATUS_UNKNOWN' if unknown else 'SOURCE_ERROR' if state=='FAIL_CLOSED' else 'SOURCE_PENDING']
            slots=output['scheduler_liveness'].get('workflows',{}).get('daily',{}).get('slots',[])
            if state=='PENDING_DATA' and any(stamp(s['expected_at_taipei']).hour==17 and s['run_ids'] for s in slots):
                reasons.append('FINAL_RETRY_SOURCE_PENDING')
            completed_updates=[stamp(s['expected_at_taipei']) for s in slots if s.get('status')=='completed' and stamp(s['expected_at_taipei']).hour >= 15 and stamp(s['expected_at_taipei'])+timedelta(minutes=rule['grace_minutes'])<=now]
            expected_update=max(completed_updates) if completed_updates else at(now,rule['due_taipei'])
            time_current=stamp(obj[rule['timestamp_field']]) >= expected_update
            fresh[kind]=result('PASS' if time_current else 'DEGRADED','EOD_STATUS_CURRENT' if time_current else 'EOD_STATUS_STALE_FOR_COMPLETED_RETRY',expected_update_after=expected_update.isoformat(),**metadata)
            ready[kind]=result(state,*reasons,legs=statuses,downstream_ready=obj.get('downstream_ready'),mother_status=obj.get('mother_status'))
        else:
            q=artifacts.get(EXTRA_PATHS[0]); e=artifacts.get(EXTRA_PATHS[1])
            q=q if isinstance(q,dict) else {}; e=e if isinstance(e,dict) else {}
            view_q=obj.get('q017',{}); view_e=obj.get('e2',{})
            qdate=q.get('trade_date'); edate=e.get('signal_asof')
            priors=[v.get('target_date') for p,v in artifacts.items() if p.startswith('eod/') and isinstance(v,dict) and v.get('formal_complete_day') is True and isinstance(v.get('target_date'),str) and v['target_date'] < today]
            minimum=max(priors) if priors else today
            try:
                source_times_current=all(stamp(x['generated_at_taipei']) <= stamp(obj[rule['timestamp_field']]) for x in (q,e))
            except (KeyError,TypeError,ValueError):
                source_times_current=False
            coherent=(semantic and isinstance(view_q,dict) and isinstance(view_e,dict)
                and qdate==today and view_q.get('trade_date')==qdate
                and isinstance(edate,str) and minimum <= edate <= today
                and view_e.get('signal_asof')==edate and e.get('binding_status')=='PASS'
                and q.get('binding_status')=='PASS' and source_times_current
                and (q.get('market_state') is None or q['market_state']==view_q.get('status'))
                and (e.get('engine_status') is None or e['engine_status']==view_e.get('status'))
                and fresh.get('q017',{}).get('state')=='PASS'
                and stamp(obj[rule['timestamp_field']]).date()==now.date())
            fresh[kind]=result('PASS' if coherent else 'DEGRADED','DISPLAY_SOURCES_CURRENT' if coherent else 'DISPLAY_STALE_OR_INCOHERENT_SOURCE',
                q017_source_date=qdate,e2_source_date=edate,q017_source_timestamp=q.get('generated_at_taipei'),
                e2_source_timestamp=e.get('generated_at_taipei'),minimum_evidenced_source_date=minimum,**metadata)
            ready[kind]=result('PASS' if coherent else 'PENDING_DATA','DISPLAY_SOURCE_READINESS_ONLY')
            safety[kind]['canonical_e2_safety']=source_safety('e2_morning',e)
            if safety[kind]['canonical_e2_safety']['state']=='FAIL_CLOSED':
                safety[kind]['state']='FAIL_CLOSED'; safety[kind]['reason_codes'].append('CANONICAL_E2_AUTHORITY_UNSAFE')
    for name,path in (('canonical_e2',EXTRA_PATHS[1]),('canonical_q017',EXTRA_PATHS[0])):
        if isinstance(artifacts.get(path),dict):
            safety[name]=source_safety('e2_morning' if name=='canonical_e2' else 'q017',artifacts[path])
    for name,lanes in [('artifact_freshness',fresh),('data_readiness',ready),('authority_safety',safety)]:
        output[name]=result(worst(v['state'] for v in lanes.values()),'LANES_EVALUATED',lanes=lanes)
    states=[output[k]['state'] for k in ('scheduler_liveness','artifact_freshness','data_readiness','authority_safety')]
    output['state']='NOT_DUE' if states[:3]==['NOT_DUE']*3 and states[3] in ('PASS','NOT_DUE') else worst(states)
    return output


def load_artifacts(root, now):
    paths=[p.format(date=now.strftime('%Y%m%d')) for p in PATHS.values()]+list(EXTRA_PATHS)
    paths.append(f'hengce/q017_radar/observations/{now.strftime("%Y%m%d")}_0901_observation.json')
    paths += [str(p.relative_to(root)) for p in (root/'eod').glob('????????/status.json')]
    objects={}
    for path in set(paths):
        try:
            objects[path]=json.loads((root/path).read_text(encoding='utf-8'))
        except (OSError,ValueError):
            objects[path]=None
    return objects


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--policy',type=Path,default=POLICY)
    parser.add_argument('--runs',type=Path,required=True)
    parser.add_argument('--now')
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args(); now=stamp(args.now) if args.now else datetime.now(TZ)
    try: manifest=json.loads(args.runs.read_text())
    except (OSError,ValueError): manifest={}
    try: policy=json.loads(args.policy.read_text())
    except (OSError,ValueError): policy={}
    sha=subprocess.check_output(['git','-C',str(args.root),'rev-parse','HEAD'],text=True).strip()
    health=evaluate(now,load_artifacts(args.root,now),manifest,policy,sha)
    text=json.dumps(health,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if args.write:
        out=args.root/'hengce/health/latest.json'; out.parent.mkdir(parents=True,exist_ok=True)
        if not out.resolve().is_relative_to(args.root.resolve()/'hengce/health'):
            raise ValueError('UNSAFE_HEALTH_OUTPUT_PATH')
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=out.parent,delete=False) as f:
            f.write(text); temporary=Path(f.name)
        temporary.replace(out)
    print(text)
    # Reporting bad health is a successful observation, not a repair/producer run.


if __name__=='__main__':
    main()
