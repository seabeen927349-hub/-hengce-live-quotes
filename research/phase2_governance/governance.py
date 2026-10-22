"""Research governance checks only. No model, data, search or execution imports."""
from datetime import datetime
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys

from jsonschema import Draft202012Validator, FormatChecker

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
BASE='42f4d4edd4b327c693290416d54d1e7622733969'
AUTHORIZATION_BASE='f10463b07a25d647c0ce6762be2661005eebfeef'
AUTHORIZATION_ID='HENGCE-P2-AUTH-20261023-001'
RECEIPT_SHA256='a4ca71b122c6f1887b2fc8172546301473750250a0eb7981d7afad3b6310edec'
POLICY_SHA256='3792626bc777991a67991f5c97b06371a9f8de33984e99adad78c6b4c4b4477a'
P2A_OPERATIONS=('BASELINE_REPLAY','COST_STRESS','LEAVE_BEST_TRADES_OUT','LEAVE_ONE_YEAR_OUT',
 'REGIME_CHARACTERIZATION','PARAMETER_PERTURBATION_ROBUSTNESS')
ZERO=dict(capital_authority_twd=0,broker_order_execution=False,PROMOTE_TO_PRODUCTION='FORBIDDEN')
APPROVALS={'phase2_research_scope','chronological_walk_forward','purge_embargo',
 'trial_budget_multiple_testing','cost_baseline_stress','minimum_observations_trades',
 'drawdown_tail_cost_turnover_gates','prospective_holdout_custody_access'}


class Blocked(ValueError):pass


def need(ok,reason):
    if not ok:raise Blocked(reason)


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()


def sha(data):return hashlib.sha256(data).hexdigest()


def parse(data):
    def pairs(rows):
        result={}
        for k,v in rows:
            need(k not in result,'DUPLICATE_JSON_KEY');result[k]=v
        return result
    return json.loads(data,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(Blocked('NONFINITE_JSON')))


def metadata(path):return parse(Path(path).read_bytes())


def zero(value):
    need(all(type(value.get(k)) is type(v) and value[k]==v for k,v in ZERO.items()),'RESEARCH_AUTHORITY_FORBIDDEN')


def validate_authorization_receipt(raw=None):
    if raw is None:raw=(HERE/'authorization-event-20261023.json').read_bytes()
    need(sha(raw)==RECEIPT_SHA256,'ORIGINAL_HUMAN_AUTHORIZATION_RECEIPT_CHANGED')
    receipt=parse(raw);zero(receipt)
    need(receipt['authorization_id']==AUTHORIZATION_ID and receipt['authorized_engine']=='E2' and
         receipt['authorized_stage']=='E2_P2A_BASELINE_DESTRUCTION_ONLY' and
         receipt['authorized_operations']==list(P2A_OPERATIONS),'SCOPED_RECEIPT_MISMATCH')
    return receipt


def validate_policy(policy):
    zero(policy)
    validate_authorization_receipt()
    # Exact reviewed contract, including all pending/null values and unknown-key
    # rejection. A JSON toggle or edited receipt cannot self-grant more scope.
    need(sha(canonical(policy))==POLICY_SHA256,'POLICY_TAMPERING_OR_UNREVIEWED_SPECIFICATION')
    need(policy.get('phase2_authorized') is True and policy.get('phase2_research_authorized') is True and
         policy.get('authorization_id')==AUTHORIZATION_ID and
         policy.get('status')=='AUTHORIZED_E2_P2A_DIAGNOSTICS_ONLY','PHASE2_NOT_SCOPED_AUTHORIZED')
    need(policy.get('gates')=={**{f'B{i:02d}':'PARTIAL' for i in range(1,10)},
         'B10':'SCOPED_AUTHORIZED_E2_P2A_ONLY'},'GATES_CANNOT_GRANT_BROAD_AUTHORITY')
    scope={'E2':'P2A_BASELINE_DESTRUCTION_ONLY','Q017':'PROSPECTIVE_CHARACTERIZATION_ONLY',
           'M1':'RESEARCH_SHADOW_ONLY_NO_OPTIMIZATION'}
    need(policy.get('engine_scope')==scope,'ENGINE_SCOPE_FORBIDDEN')
    approvals=policy.get('human_approvals',{})
    need(set(approvals)==APPROVALS,'UNKNOWN_APPROVAL_CONTRACT')
    for key in ('minimum_observations_trades','drawdown_tail_cost_turnover_gates','prospective_holdout_custody_access'):
        value=approvals[key]
        need(value['status']=='PENDING_HUMAN_APPROVAL' and value['approved_value'] is None and
             value['authorization_id'] is None,'ACCEPTANCE_AND_CUSTODY_APPROVAL_NOT_GRANTED')
    exposure=policy.get('historical_exposure',{})
    need(exposure==dict(years=[2023,2024,2025,2026],status='EXPOSED_DEVELOPMENT_VALIDATION_ELIGIBLE_ONLY',
         pristine_holdout=False,usable_only_with_proven_lineage=True),'EXPOSED_HISTORY_IS_NOT_PRISTINE')
    need(policy.get('prospective_holdout')==dict(state='UNALLOCATED',allocation_authorized=False,
         access_authorized=False,candidate_freeze_id=None),'HOLDOUT_ALLOCATION_OR_ACCESS_FORBIDDEN')
    cost=policy.get('existing_e2_baseline',{})
    need(cost==dict(roundtrip_cost=0.008,meaning='EXISTING_AGGREGATE_ROUNDTRIP_ASSUMPTION',component_costs=None,
         double_count_forbidden=True,max_slots=1,overlap='FORBIDDEN',entry='NEXT_TWSE_OPEN',exit='FIXED20'),
         'FROZEN_E2_AGGREGATE_COST_OR_EXECUTION_CHANGED')
    need(policy.get('actual_user_trades_are_model_evidence') is False,'USER_TRADES_ARE_NOT_MODEL_EVIDENCE')
    return policy


def require_phase2_run(policy,engine=None,stage=None,operation=None,cost_multiplier=None,**flags):
    """Check scoped permission only. Never execute/append/access any model/data.

    Pending candidate gates do not veto P2-A diagnostics. Actual experiments
    require a merged authorization PR and independently checkpointed ledger.
    """
    validate_policy(policy)
    need(engine=='E2' and stage=='P2A_BASELINE_DESTRUCTION' and
         isinstance(operation,str) and operation in P2A_OPERATIONS,'SCOPED_ROUTE_NOT_AUTHORIZED')
    locked={**ZERO,'candidate_creation':False,'candidate_acceptance':False,'holdout_access':False,
            'historical_signal_regeneration':False,'automated_search':False,'unrestricted_feature_mining':False}
    need(set(flags)<=set(locked),'UNKNOWN_OR_FORBIDDEN_REQUEST_FIELD')
    requested={**locked,**flags};zero(requested)
    need(all(requested[k] is False for k in locked if k not in ZERO),'REQUEST_EXCEEDS_P2A_AUTHORIZATION')
    aggregate=policy['existing_e2_baseline']['roundtrip_cost']
    if operation=='COST_STRESS':
        need(type(cost_multiplier) in (int,float) and cost_multiplier in (1.0,1.5,2.0),
             'ONLY_APPROVED_AGGREGATE_COST_MULTIPLIERS_ALLOWED')
        aggregate*=cost_multiplier
    else:need(cost_multiplier is None,'COST_MULTIPLIER_ONLY_FOR_COST_STRESS')
    return dict(status='SCOPED_GATE_ALLOWED_NO_EXECUTION',authorization_id=AUTHORIZATION_ID,
        phase2_authorized=True,engine=engine,stage=stage,operation=operation,aggregate_roundtrip_cost=aggregate,
        candidate_creation_authorized=False,candidate_acceptance_authorized=False,holdout_access_authorized=False,
        initial_family_trial_budget_max=24,failed_rejected_aborted_count=True,
        requires_merged_authorization_pr=25,requires_proven_lineage=True,
        requires_ledger_and_independent_checkpoint=True,**ZERO)


def require_holdout_access(policy):
    validate_policy(policy)
    raise Blocked('PROSPECTIVE_HOLDOUT_UNALLOCATED_ACCESS_FORBIDDEN')


def schema(name):
    manifest=metadata(HERE/'environment-lock.json')
    path='research/phase1_audit/'+name+'.schema.json';raw=(ROOT/path).read_bytes()
    need(sha(raw)==manifest['frozen_sources_sha256'][path],'FROZEN_SCHEMA_CHANGED')
    spec=parse(raw);Draft202012Validator.check_schema(spec)
    return Draft202012Validator(spec,format_checker=FormatChecker())


def holdout_metadata(value):
    schema('holdout').validate(value)
    stamps=[datetime.fromisoformat(value[k]) for k in ('sealed_at','opened_at','consumed_at') if value[k] is not None]
    need(all(s.tzinfo is not None for s in stamps) and stamps==sorted(stamps),'INVALID_CUSTODY_TIME_ORDER')
    return value


def validate_holdout_transition(before,after):
    """Pure metadata validation; never allocates/opens/releases a real artifact."""
    holdout_metadata(before);holdout_metadata(after)
    order=('UNALLOCATED','SEALED','OPENED','CONSUMED');a=order.index(before['state']);b=order.index(after['state'])
    need(before['holdout_id']==after['holdout_id'],'HOLDOUT_ID_CHANGED')
    need(b==a+1 or before==after,'IRREVERSIBLE_HOLDOUT_TRANSITION')
    if a>=1:
        keys=('custodian','artifact_commitment_sha256','policy_authorization_id','access_policy_sha256','sealed_at')
        need(all(before[k]==after[k] for k in keys),'SEALED_CUSTODY_COMMITMENT_CHANGED')
    if a>=2:
        need(after['open_count']==1 and after['exposed'] is True and before['opened_at']==after['opened_at'],
             'OPENED_IS_PERMANENTLY_EXPOSED_NO_SECOND_OPEN')
    return True


def verify_environment(runtime=True):
    lock=metadata(HERE/'environment-lock.json');zero(lock)
    need(lock['authoritative_base']==BASE and lock['phase2_authorized'] is False,'INVALID_ENVIRONMENT_AUTHORITY')
    need(sha((HERE/'requirements.lock').read_bytes())==lock['requirements_sha256'],'DEPENDENCY_LOCK_CHANGED')
    for path,digest in lock['frozen_sources_sha256'].items():
        need(sha((ROOT/path).read_bytes())==digest,'FROZEN_SOURCE_CHANGED:'+path)
    if runtime:
        need(platform.python_implementation()==lock['python']['implementation'] and platform.python_version()==lock['python']['version'],
             'RESEARCH_PYTHON_LOCK_MISMATCH')
        need(platform.system()==lock['platform']['system'] and platform.machine()==lock['platform']['machine'],'RESEARCH_PLATFORM_LOCK_MISMATCH')
        for dep in lock['dependencies']:
            need(importlib.metadata.version(dep['name'])==dep['version'],'RESEARCH_DEPENDENCY_VERSION_MISMATCH:'+dep['name'])
    return lock
