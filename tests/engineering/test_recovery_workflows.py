"""Pin admission/fence integration without changing schedules or model code."""
import ast
import json
from pathlib import Path
import subprocess
import sys
import unittest
import yaml
import recovery_topology as topology

ROOT=topology.ROOT
sys.path.insert(0,str(ROOT/'scripts'))
import hengce_recovery_transaction as r


def original(path):return topology.show(path).decode()


class RecoveryWorkflowTests(unittest.TestCase):
    def test_exact_base_reinventory_is_reproducible_and_has_all_eleven_lanes(self):
        stored=json.loads(topology.OUT.read_text());self.assertEqual(stored,topology.build())
        self.assertEqual(len(stored['lanes']),11)
        self.assertEqual(stored['source_commit'],topology.BASE)
        for row in stored['lanes']:
            for key in ('write_set','immutable_subset','authoritative_read_dependencies','legal_date_window','existing_validators',
                        'required_closure','retry_idempotence','manual_semantics'):
                self.assertTrue(row[key],(row['lane'],key))

    def test_all_operational_publishers_have_precommit_closure_and_existing_publisher(self):
        rows=json.loads(topology.OUT.read_text())['lanes'];workflows={x['workflow'] for x in rows if x['lane']!='health'}
        for path in workflows:
            config=yaml.load((ROOT/path).read_text(),Loader=yaml.BaseLoader)
            for job in config['jobs'].values():
                steps=job['steps'];admission=[i for i,s in enumerate(steps) if s.get('name')=='Recovery admission from clean current remote']
                self.assertEqual(len(admission),1,path)
                a=steps[admission[0]];self.assertIn('HENGCE_REQUEST_DATE',a['env']);self.assertIn(' prepare --lane ',a['run'])
                for i,s in enumerate(steps):
                    run=s.get('run','')
                    if 'hengce_publish.py' in run:
                        self.assertLess(admission[0],i,path)
                        self.assertIn('--transaction-lane ',run)
                        self.assertLess(run.index('recovery_transaction.py stage'),run.index('git commit'),path)
                        self.assertLess(run.index('git commit'),run.index('hengce_publish.py'),path)
                        for forbidden in ('git push','git pull','git rebase'):self.assertNotIn(forbidden,run)

    def test_triggers_schedules_capture_groups_and_job_configuration_exact_base_unchanged(self):
        rows=json.loads(topology.OUT.read_text())['lanes']
        for path in {x['workflow'] for x in rows}:
            before=yaml.load(original(path),Loader=yaml.BaseLoader);after=yaml.load((ROOT/path).read_text(),Loader=yaml.BaseLoader)
            for k in ('on','concurrency','permissions'):self.assertEqual(before.get(k),after.get(k),path)
            for key in before['jobs']:
                self.assertEqual({k:v for k,v in before['jobs'][key].items() if k!='steps'},
                                 {k:v for k,v in after['jobs'][key].items() if k!='steps'},path)
        p=yaml.load((ROOT/'.github/workflows/hengce-q017-primary-observer.yml').read_text(),Loader=yaml.BaseLoader)
        b=yaml.load((ROOT/'.github/workflows/hengce-q017-backup-observer.yml').read_text(),Loader=yaml.BaseLoader)
        self.assertNotEqual(p['concurrency']['group'],b['concurrency']['group'])

    def test_all_post_publication_computation_is_fenced_even_always_steps(self):
        for row in json.loads(topology.OUT.read_text())['lanes']:
            if row['lane']=='health':continue
            path=row['workflow'];config=yaml.load((ROOT/path).read_text(),Loader=yaml.BaseLoader)
            for job in config['jobs'].values():
                published=False
                for step in job['steps']:
                    run=step.get('run','')
                    if 'hengce_publish.py' in run:published=True;continue
                    if published and any(token in run for token in ('--mode compute','--mode morning','--mode monitor','--mode check-and-repair','python scripts/hengce_dual_engine_display.py')):
                        self.assertTrue(run.startswith('python scripts/hengce_recovery_transaction.py fence'),(path,step.get('name')))

    def test_model_functions_and_e2_engine_exactly_unchanged(self):
        def functions(text):return {x.name:ast.dump(x,include_attributes=False) for x in ast.parse(text).body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))}
        path='scripts/hengce_q017_observation_lock_v5.py';a=functions(original(path));b=functions((ROOT/path).read_text())
        self.assertEqual(set(a),set(b))
        for name in a.keys()-{'compute_decision'}:self.assertEqual(a[name],b[name],name)
        for path in ('scripts/hengce_e2_live.py','scripts/hengce_daily_command_center_core_legacy.py',
                     'scripts/hengce_eod_incremental_ingest.py','scripts/hengce_q017_10d_review.py','scripts/hengce_q017_10d_review_extension.py'):
            self.assertEqual(original(path),(ROOT/path).read_text(),path)

    def test_data_integrity_minimums_and_columns_unchanged(self):
        parsed=ast.parse(original('scripts/hengce_eod_incremental_ingest.py'))
        values={t.id:ast.literal_eval(n.value) for n in parsed.body if isinstance(n,ast.Assign)
                for t in n.targets if isinstance(t,ast.Name) and t.id in ('MIN','COLS')}
        self.assertEqual(r.EOD_MIN,values['MIN']);self.assertEqual(r.EOD_COLUMNS,values['COLS'])

    def test_no_second_publisher_or_health_recovery_dispatch(self):
        tree=ast.parse((ROOT/'scripts/hengce_recovery_transaction.py').read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Constant) and isinstance(node.value,str):
                self.assertNotEqual(node.value,'push')
        health=yaml.load((ROOT/'.github/workflows/hengce-system-health.yml').read_text(),Loader=yaml.BaseLoader)
        live='\n'.join(s.get('run','') for s in health['jobs']['current-health']['steps'])
        self.assertNotIn('recovery_transaction.py',live)
        for dispatch in ('workflow_dispatch','gh workflow run','dispatches'):
            self.assertNotIn(dispatch,live)
        self.assertEqual(r.ZERO,dict(signal_authority=False,ranking_authority=False,capital_authority_twd=0,broker_order_execution=False))

    def test_eod_closure_precedes_downstream_readiness(self):
        cfg=yaml.load((ROOT/'.github/workflows/hengce-daily-command-center.yml').read_text(),Loader=yaml.BaseLoader)
        steps=next(iter(cfg['jobs'].values()))['steps']
        names=[s.get('name') for s in steps]
        guard=names.index('Resolve post-close mother-gated readiness')
        self.assertLess(names.index('Run post-close official ingest and history append'),guard)
        self.assertTrue(steps[guard]['run'].startswith('python scripts/hengce_recovery_transaction.py fence --scope eod-ready\n'))


if __name__=='__main__':unittest.main(verbosity=2)
