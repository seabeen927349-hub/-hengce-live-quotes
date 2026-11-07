#!/usr/bin/env python3
"""HENGCE Behavior Atlas: fail-closed stage-gate protocol validator.

This validates procedural permissions only. It cannot certify the truth
of empirical findings or literature full-text reading.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

BASE=Path(__file__).resolve().parent
STATE=BASE/'STAGE_GATE_STATE.json'
VALID={'NOT_STARTED','BLOCKED','PASS','FAIL_STOP'}
STAGES=[f'G{i}' for i in range(8)]
EXPECTED_DAILY_SHA='b3275f8d58779fbec864a05066414d27e80cef8a68a76a08051f93808f1f8c93'
EXPECTED_WEEKLY_SHA='e78b967042bd0d9058c0eded1b7c2b80ae03cb9c0c7fbc1ca660844d0126f7a3'

def require(cond, message):
    if not cond:
        raise RuntimeError('STAGE_GATE_VIOLATION: '+message)

def check():
    require((BASE/'PROTOCOL_LOCK_V1.md').exists(),'PROTOCOL_MISSING')
    obj=json.loads(STATE.read_text(encoding='utf-8'))
    rows=obj.get('stages',[])
    require(len(rows)==8,'STAGE_COUNT_NOT_EIGHT')
    require([x.get('id') for x in rows]==STAGES,'GATE_ORDER_OR_IDS_CHANGED')
    require(all(x.get('status') in VALID for x in rows),'UNKNOWN_STAGE_STATUS')
    require(obj.get('data_source_hashes',{}).get('daily_three_leg_mother_sha256')==EXPECTED_DAILY_SHA,'DAILY_MOTHER_SHA_CHANGED')
    require(obj.get('data_source_hashes',{}).get('weekly_tdcc_fourth_leg_sha256')==EXPECTED_WEEKLY_SHA,'TDCC_MOTHER_SHA_CHANGED')
    budget=obj.get('work_cap',{})
    require(budget.get('total_major_discovery_experiments')==6,'DISCOVERY_BUDGET_CHANGED')
    require(budget.get('method_families')==3,'DISCOVERY_FAMILIES_CHANGED')
    require(budget.get('implementation_variants_each')==2,'DISCOVERY_VARIANTS_CHANGED')
    require(budget.get('post_validation_retunes')==0,'POST_VALIDATION_TUNING_NOT_ZERO')
    require(budget.get('literature_supplementary_rounds')==2,'LITERATURE_ATTEMPT_CAP_CHANGED')
    require(budget.get('data_fix_attempts_per_gap')==2,'DATA_REPAIR_CAP_CHANGED')
    cfg=obj.get('execution_controls',{})
    require(cfg.get('automatic_restart_on_no_result') is False,'AUTOMATIC_RESTART_BANNED')
    require(cfg.get('failed_literature_gate_is_terminal_for_proposal') is True,'ENDLESS_LITERATURE_REVIEW_BANNED')
    require(cfg.get('formal_terminal_outcome_required') is True,'NO_RESULT_CLOSURE_REQUIRED')
    require(cfg.get('bugfix_rounds_per_stage')==1,'BUGFIX_BUDGET_CHANGED')
    require(cfg.get('post_validation_parameter_revisions')==0,'NO_RETUNING_VIOLATION')
    require(rows[0].get('rounds_completed',0)<=2,'LITERATURE_ROUNDS_EXCEEDED')
    require(rows[3].get('major_experiments_run',0)<=6,'EXPERIMENTS_EXCEEDED')
    for step in rows:
        require(isinstance(step.get('deliverables'),list) and len(step['deliverables'])>0,'MISSING_DELIVERABLES_'+step['id'])
        require(step.get('pass_rule') and step.get('stop_rule'),'MISSING_PASS_STOP_RULE_'+step['id'])
        for parent in step.get('blocking_gates',[]):
            require(parent in STAGES,'BAD_PARENT_'+step['id'])
            if step['status']=='PASS':
                require(rows[STAGES.index(parent)]['status']=='PASS','PASS_WITH_BLOCKED_PREREQUISITE_'+step['id'])
        if step['status']=='FAIL_STOP':
            for next_step in rows[STAGES.index(step['id'])+1:]:
                require(next_step['status'] not in ('PASS',),'CHILD_PASS_AFTER_TERMINAL_PARENT')
    literature=BASE/'LITERATURE_GATE.json'
    if rows[0]['status']=='PASS':
        require(literature.exists(),'LITERATURE_GATE_MISSING')
        lg=json.loads(literature.read_text(encoding='utf-8'))
        require(lg.get('literature_status')=='PASS' and lg.get('literature_review_complete') is True,
                'LITERATURE_GATE_NOT_PASSED')
        require(obj.get('topic_literature_gate')=='PASS','TOPIC_LITERATURE_AUTHORITY_NOT_SET')
    else:
        require(rows[2]['status'] not in ('PASS',),'PREREGISTRATION_WITHOUT_LITERATURE_PASS')
        require(all(r['status']!='PASS' for r in rows[3:]),'EMPIRICAL_PHASE_WITHOUT_LITERATURE_PASS')
    if rows[1]['status']=='PASS':
        require((BASE/'03_FOUR_LEG_CAPABILITY_AUDIT.json').exists(),'G1_AUDIT_MISSING')
    if rows[2]['status']=='PASS':
        require((BASE/'05_PREREGISTRATION_LOCK.md').exists(),'PREREG_NOT_FROZEN')
        require(rows[2].get('prereg_sha256'),'PREREG_SHA_NOT_REGISTERED')
    if rows[3]['status']=='PASS':
        require(rows[3].get('major_experiments_run',0)>0,'G3_PASS_WITH_ZERO_EXP')
    print('HENGCE_BEHAVIOR_ATLAS_STAGE_GATE_VALID:', obj['current_focus'],
          'literature='+obj['topic_literature_gate'],
          'experiments='+str(rows[3].get('major_experiments_run',0))+'/6')
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(check())
    except Exception as exc:
        print('HENGCE_BEHAVIOR_ATLAS_BLOCKED:',str(exc),file=sys.stderr)
        raise SystemExit(2)
