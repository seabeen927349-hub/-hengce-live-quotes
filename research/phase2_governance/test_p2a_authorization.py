"""Permission checks with synthetic requests only; no diagnostic/model execution."""
import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from research.phase2_governance import governance as g
from research.phase2_governance import freeze

AUTH_ID='HENGCE-P2-AUTH-20261023-001'
AUTH_BASE='f10463b07a25d647c0ce6762be2661005eebfeef'
RECEIPT_COMMIT='71ef7d3dbc83715c6bff23ac809c4e21dee48a3b'
OPS=('BASELINE_REPLAY','COST_STRESS','LEAVE_BEST_TRADES_OUT','LEAVE_ONE_YEAR_OUT',
     'REGIME_CHARACTERIZATION','PARAMETER_PERTURBATION_ROBUSTNESS')


class ScopedAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.policy=g.metadata(g.HERE/'phase2-policy.json')
        network=patch.object(socket.socket,'connect',side_effect=AssertionError('OFFLINE_GATE_ONLY'))
        network.start();self.addCleanup(network.stop)

    def gate(self,engine='E2',stage='P2A_BASELINE_DESTRUCTION',operation='BASELINE_REPLAY',**flags):
        return g.require_phase2_run(self.policy,engine=engine,stage=stage,operation=operation,**flags)

    def test_e2_p2a_six_diagnostics_allowed_without_execution(self):
        for operation in OPS:
            with self.subTest(operation=operation):
                extra={'cost_multiplier':1.0} if operation=='COST_STRESS' else {}
                out=self.gate(operation=operation,**extra)
                self.assertEqual(out['status'],'SCOPED_GATE_ALLOWED_NO_EXECUTION')
                self.assertEqual(out['authorization_id'],AUTH_ID)
                self.assertFalse(out['candidate_acceptance_authorized']);self.assertFalse(out['holdout_access_authorized'])
                for k,v in g.ZERO.items():self.assertEqual(out[k],v)

    def test_q017_denied_even_for_characterization_through_e2_gate(self):
        with self.assertRaises(ValueError):self.gate(engine='Q017',operation='REGIME_CHARACTERIZATION')

    def test_m1_optimization_denied(self):
        with self.assertRaises(ValueError):self.gate(engine='M1')

    def test_p2b_p2c_unknown_or_unscoped_routes_denied(self):
        for stage in ('P2-B','P2-C','P2B','P2C','P2B_OPTIMIZATION','',None):
            with self.assertRaises(ValueError):self.gate(stage=stage)
        with self.assertRaises(ValueError):g.require_phase2_run(self.policy)

    def test_holdout_candidate_acceptance_and_creation_denied(self):
        with self.assertRaises(ValueError):g.require_holdout_access(self.policy)
        for flag in ('holdout_access','candidate_acceptance','candidate_creation'):
            with self.assertRaises(ValueError):self.gate(**{flag:True})

    def test_capital_broker_promotion_and_hidden_authority_denied(self):
        for flags in ({'capital_authority_twd':1},{'capital_authority_twd':False},{'broker_order_execution':True},
                      {'PROMOTE_TO_PRODUCTION':'ALLOWED'},{'capital_authority':1}):
            with self.assertRaises(ValueError):self.gate(**flags)

    def test_optimizer_feature_mining_historical_regeneration_denied(self):
        for operation in ('GRID_SEARCH','RANDOM_SEARCH','BAYESIAN_SEARCH','OPTIMIZER','FEATURE_MINING','HISTORICAL_SIGNAL_REGENERATION'):
            with self.assertRaises(ValueError):self.gate(operation=operation)
        for flag in ('automated_search','unrestricted_feature_mining','historical_signal_regeneration','optimizer'):
            with self.assertRaises(ValueError):self.gate(**{flag:True})

    def test_pending_acceptance_values_do_not_veto_p2a_or_become_approved(self):
        self.gate()
        for key in ('minimum_observations_trades','drawdown_tail_cost_turnover_gates','prospective_holdout_custody_access'):
            row=self.policy['human_approvals'][key]
            self.assertEqual(row['status'],'PENDING_HUMAN_APPROVAL');self.assertIsNone(row['approved_value'])
        pending=self.policy['pending_p2b_folds']
        self.assertIsNone(pending['fold_dates']);self.assertIsNone(pending['step_sessions'])

    def test_approved_chronology_overlap_budget_and_counting_rules(self):
        approvals=self.policy['human_approvals']
        chrono=approvals['chronological_walk_forward']['approved_value']
        self.assertTrue(chrono['chronological_only']);self.assertFalse(chrono['random_split'])
        self.assertEqual(chrono['method'],'PRE_REGISTERED_EXPANDING_WALK_FORWARD')
        overlap=approvals['purge_embargo']['approved_value']
        self.assertGreaterEqual(overlap['purge_min_twse_sessions'],20);self.assertGreaterEqual(overlap['embargo_min_twse_sessions'],20)
        budget=approvals['trial_budget_multiple_testing']['approved_value']
        self.assertEqual(budget['initial_family_max_challenger_variants'],24);self.assertTrue(budget['failed_rejected_aborted_count'])

    def test_cost_stress_uses_single_aggregate_without_components(self):
        for multiplier,cost in ((1.0,.008),(1.5,.012),(2.0,.016)):
            out=self.gate(operation='COST_STRESS',cost_multiplier=multiplier)
            self.assertAlmostEqual(out['aggregate_roundtrip_cost'],cost)
        for value in (True,0,1.1,3,float('nan')):
            with self.assertRaises(ValueError):self.gate(operation='COST_STRESS',cost_multiplier=value)
        with self.assertRaises(ValueError):self.gate(operation='COST_STRESS',component_costs={'fee':.001})

    def test_policy_tampering_and_unknown_fields_fail_closed(self):
        mutations=[{'phase2_authorized':False},{'authorization_id':'SELF_APPROVAL'},
          {'candidate_acceptance_authorized':True},{'holdout_access_authorized':True},
          {'capital_authority_twd':1},{'broker_order_execution':True},{'PROMOTE_TO_PRODUCTION':'ALLOWED'},
          {'unknown_permission':True},{'authorized_operations':[*OPS,'GRID_SEARCH']}]
        for fields in mutations:
            modified=copy.deepcopy(self.policy);modified.update(fields)
            with self.assertRaises(ValueError):g.require_phase2_run(modified,engine='E2',stage='P2A_BASELINE_DESTRUCTION',operation='BASELINE_REPLAY')
        for key in ('minimum_observations_trades','drawdown_tail_cost_turnover_gates'):
            modified=copy.deepcopy(self.policy);modified['human_approvals'][key]['approved_value']=1
            with self.assertRaises(ValueError):g.validate_policy(modified)

    def test_original_authorization_receipt_unchanged_and_tampering_rejected(self):
        path='research/phase2_governance/authorization-event-20261023.json'
        trusted=subprocess.check_output(['git','-C',str(g.ROOT),'show',RECEIPT_COMMIT+':'+path])
        self.assertEqual((g.ROOT/path).read_bytes(),trusted)
        changed=g.parse(trusted);changed['automated_search_authorized']=True
        with self.assertRaises(ValueError):g.validate_authorization_receipt(g.canonical(changed))

    def test_budget_overlap_and_chronology_tampering_fail_closed(self):
        cases=[('purge_embargo','purge_min_twse_sessions',19),('purge_embargo','embargo_min_twse_sessions',19),
          ('trial_budget_multiple_testing','initial_family_max_challenger_variants',25),
          ('trial_budget_multiple_testing','failed_rejected_aborted_count',False),
          ('chronological_walk_forward','random_split',True),('chronological_walk_forward','fold_dates',['self-approved'])]
        for group,key,value in cases:
            changed=copy.deepcopy(self.policy);changed['human_approvals'][group]['approved_value'][key]=value
            with self.subTest(group=group,key=key),self.assertRaises(ValueError):g.validate_policy(changed)

    def test_authorization_pr_has_zero_experiments_and_untouched_production(self):
        base=os.environ.get('HENGCE_GOVERNANCE_BASE',AUTH_BASE)
        report=freeze.verify(base)
        trusted=g.parse(freeze.git('show',base+':research/phase2_governance/phase2-policy.json'))
        if trusted.get('authorization_id')!=AUTH_ID:
            self.assertEqual((g.HERE/'ledger/experiments.jsonl').read_bytes(),b'')
            self.assertEqual(report['ledger_record_count'],0)
        changed=subprocess.check_output(['git','-C',str(g.ROOT),'diff','--name-only',AUTH_BASE]).decode().splitlines()
        freeze.check_paths(changed)
        self.assertEqual(g.metadata(g.HERE/'holdout-state.json')['state'],'UNALLOCATED')

    def test_after_merged_authorization_ledger_prefix_not_permanently_forced_empty(self):
        from research.phase2_governance.test_governance import record
        future='e'*40;original=freeze.git;run=subprocess.run;read=Path.read_bytes
        ledger=g.HERE/'ledger/experiments.jsonl';synthetic=g.canonical(record('FUTURE_SYNTHETIC_AUDIT'))+b'\n'
        original_ledger=ledger.read_bytes()
        def fake(*args):
            if args==('merge-base',future,'HEAD'):return (AUTH_BASE+'\n').encode()
            if args==('show',future+':'+freeze.LEDGER):return b''
            if args==('show',future+':research/phase2_governance/phase2-policy.json'):return g.canonical(self.policy)
            return original(*args)
        def subprocess_call(args,*a,**kw):
            if args[-3:]==['cat-file','-e',future+':'+freeze.LEDGER]:return subprocess.CompletedProcess(args,0)
            return run(args,*a,**kw)
        with patch.object(freeze,'git',side_effect=fake),patch.object(freeze.subprocess,'run',side_effect=subprocess_call), \
             patch.object(Path,'read_bytes',lambda p:synthetic if p==ledger else read(p)):
            self.assertEqual(freeze.verify(future)['ledger_record_count'],1)
        self.assertEqual(ledger.read_bytes(),original_ledger)

    def test_cli_checks_route_without_append_or_custody_side_effect(self):
        ledger=(g.HERE/'ledger/experiments.jsonl').read_bytes()
        args=[sys.executable,'-B',str(g.HERE/'ledger_store.py'),'check-run','--engine','E2',
              '--stage','P2A_BASELINE_DESTRUCTION','--operation','BASELINE_REPLAY']
        run=subprocess.run(args,capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        self.assertEqual(json.loads(run.stdout)['status'],'SCOPED_GATE_ALLOWED_NO_EXECUTION')
        self.assertEqual((g.HERE/'ledger/experiments.jsonl').read_bytes(),ledger)


if __name__=='__main__':unittest.main(verbosity=2)
