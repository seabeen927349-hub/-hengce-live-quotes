"""Verify every inventoried main publisher and preserve capture/schedule contracts."""
import ast
import json
from pathlib import Path
import unittest

import yaml
import writer_topology as topology

ROOT = Path(__file__).resolve().parents[2]


class WriterWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = json.loads(topology.OUT.read_text())

    def test_inventory_is_exactly_reproducible_from_authoritative_base(self):
        self.assertEqual(self.inventory, topology.build())
        self.assertEqual(len(self.inventory['writers']), 29)
        for writer in self.inventory['writers']:
            for publication in writer['publications']:
                self.assertTrue(publication['writable_path_prefixes_or_globs'])

    def test_every_main_publisher_is_guarded_with_durable_reports(self):
        for writer in self.inventory['writers']:
            current = yaml.load((ROOT / writer['workflow']).read_text(), Loader=yaml.BaseLoader)
            steps = current['jobs'][writer['job']]['steps']
            for publication in writer['publications']:
                step = next(s for s in steps if s.get('name') == publication['step'])
                with self.subTest(workflow=writer['workflow'], step=publication['step']):
                    self.assertIn('python scripts/hengce_publish.py', step['run'])
                    self.assertIn('--profile ' + publication['dependency_profile'], step['run'])
                    for unsafe in ('git push', 'git pull', 'git rebase', 'git reset'):
                        self.assertNotIn(unsafe, step['run'])
            upload = next(s for s in steps if s.get('name') == 'Preserve publication arbitration receipts and captured evidence')
            self.assertEqual(upload['if'], 'always()')
            self.assertEqual(upload['with']['path'], '${{ runner.temp }}/hengce-publication')

    def test_schedules_groups_permissions_and_job_configuration_unchanged(self):
        for writer in self.inventory['writers']:
            before = yaml.load(topology.show(writer['workflow']), Loader=yaml.BaseLoader)
            after = yaml.load((ROOT / writer['workflow']).read_text(), Loader=yaml.BaseLoader)
            with self.subTest(workflow=writer['workflow']):
                for key in ('on', 'concurrency', 'permissions'):
                    self.assertEqual(before.get(key), after.get(key))
                for job in before['jobs']:
                    self.assertEqual({k:v for k,v in before['jobs'][job].items() if k != 'steps'},
                                     {k:v for k,v in after['jobs'][job].items() if k != 'steps'})

    def test_model_compute_and_validation_steps_unchanged(self):
        for writer in self.inventory['writers']:
            before = yaml.load(topology.show(writer['workflow']), Loader=yaml.BaseLoader)
            after = yaml.load((ROOT / writer['workflow']).read_text(), Loader=yaml.BaseLoader)
            publications = {p['step'] for p in writer['publications']}
            actual_steps=[s for s in after['jobs'][writer['job']]['steps']
                          if s.get('name') != 'Recovery admission from clean current remote']
            # Cleanup task: the display now imports the existing schema-5 guard.
            # Permit this exact import-only installation, on this workflow only;
            # preserve every original capture/compute/validation/publication step.
            if writer['workflow'] == '.github/workflows/hengce-dual-engine-display-refresh.yml':
                dependency = {'name': 'Install existing schema-5 import dependencies',
                              'run': 'python -m pip install requests==2.32.5 openpyxl==3.1.5'}
                self.assertEqual([s for s in actual_steps if s.get('name') == dependency['name']], [dependency])
                actual_steps.remove(dependency)
            for index, step in enumerate(before['jobs'][writer['job']]['steps']):
                if step.get('name') in publications:
                    continue
                expected = dict(step)
                run = expected.get('run', '')
                if 'git pull --rebase origin main' in run and step.get('name', '').startswith('Verify '):
                    expected['run'] = run.replace('git pull --rebase origin main', '# Verify the exact accepted proposal; no post-computation pull/rebase.')
                actual = dict(actual_steps[index])
                run=actual.get('run','')
                if run.startswith('python scripts/hengce_recovery_transaction.py fence'):
                    first,_,rest=run.partition('\n')
                    self.assertRegex(first,r'^python scripts/hengce_recovery_transaction.py fence(?: --scope [a-z0-9-]+)?$')
                    actual['run']=rest
                    if not expected.get('run','').endswith('\n'):actual['run']=rest.rstrip('\n')
                self.assertEqual(expected, actual, (writer['workflow'], step.get('name')))

    def test_no_unguarded_main_push_or_blind_rebase_remains(self):
        safe_precompute_syncs = {
            ('hengce-q017-primary-observer.yml', 'Sync latest persisted morning inputs before observer starts'),
            ('hengce-q017-backup-observer.yml', 'Sync latest persisted morning inputs before observer starts'),
            ('hengce-q017-macro-cache.yml', 'Sync latest repository state before refresh')}
        for path in (ROOT / '.github/workflows').glob('*.yml'):
            text = path.read_text()
            self.assertNotIn('git push origin HEAD:main', text, path)
            config = yaml.load(text, Loader=yaml.BaseLoader)
            for job in config['jobs'].values():
                for step in job.get('steps', []):
                    run = step.get('run', '')
                    if 'git pull --rebase' in run:
                        self.assertIn((path.name, step.get('name')), safe_precompute_syncs)
                        self.assertNotIn('git commit', run)
                        self.assertNotIn('hengce_publish.py', run)
                    self.assertNotIn('git rebase ', run, path)

    def test_q017_observers_have_independent_capture_lanes(self):
        groups = []
        for lane in ('primary', 'backup'):
            path = ROOT / f'.github/workflows/hengce-q017-{lane}-observer.yml'
            config = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
            groups.append(config['concurrency']['group'])
            job = config['jobs'][lane + '-observer']
            self.assertNotIn('concurrency', job)
            steps = job['steps']
            capture = next(i for i,s in enumerate(steps) if s.get('id') == lane + '_observe')
            publish = next(i for i,s in enumerate(steps) if 'hengce_publish.py' in s.get('run', ''))
            self.assertLess(capture, publish)
            run=steps[capture]['run']
            if run.startswith('python scripts/hengce_recovery_transaction.py fence'):
                self.assertEqual(run.splitlines()[0],f'python scripts/hengce_recovery_transaction.py fence --scope q017-{lane}')
                run='\n'.join(run.splitlines()[1:])
            self.assertEqual(run, f'python scripts/hengce_q017_observer_supervisor_v2.py --mode observe --lane {lane}')
        self.assertNotEqual(*groups)

    def test_publisher_imports_only_infrastructure_modules(self):
        source = ast.parse((ROOT / 'scripts/hengce_publish.py').read_text())
        modules = set()
        for node in ast.walk(source):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.add(node.module.split('.')[0])
        self.assertEqual(modules, {'argparse', 'fnmatch', 'json', 'os', 'pathlib', 'subprocess', 'tempfile', 'time', 'uuid','hengce_recovery_transaction'})
        helper=ast.parse((ROOT/'scripts/hengce_recovery_transaction.py').read_text())
        allowed={'argparse','collections','csv','datetime','fnmatch','hashlib','io','json','os','pathlib','re','subprocess','tempfile','uuid','zoneinfo','hengce_publish'}
        for node in ast.walk(helper):
            if isinstance(node,ast.Import):self.assertTrue({a.name.split('.')[0] for a in node.names}<=allowed)
            if isinstance(node,ast.ImportFrom):self.assertIn(node.module.split('.')[0],allowed)

    def test_capture_profiles_protect_macros_code_and_unknown_inputs(self):
        import hengce_publish as publisher
        for profile in ('q017-primary-capture', 'q017-backup-capture'):
            contract = publisher.PROFILES[profile]
            self.assertTrue(publisher.matches('hengce/e2_live/morning_latest.json', contract['unrelated']))
            for path in ('hengce/q017_radar/data/macro_cache/latest.json',
                         'hengce/q017_radar/data/twse_electronics_history_2026.csv',
                         'hengce/q017_radar/decision/previous_0901.json',
                         'scripts/hengce_q017_observation_lock_v5.py',
                         'eod/20261021/status.json', 'future_unknown_input.json'):
                self.assertFalse(publisher.matches(path, contract['unrelated']), (profile, path))

    def test_every_inventoried_publication_excludes_health_only_outputs(self):
        import hengce_publish as publisher
        exits = []
        for writer in self.inventory['writers']:
            for publication in writer['publications']:
                profile = publication['dependency_profile']
                contract = publisher.PROFILES[profile]
                with self.subTest(workflow=writer['workflow'], step=publication['step']):
                    for path in ('hengce/health/latest.json', 'hengce/health/history/synthetic.json'):
                        self.assertTrue(publisher.matches(path, contract['unrelated']))
                    self.assertEqual(publication['authoritative_read_dependency_set']['excluded_patterns'],
                                     list(contract['unrelated']))
                exits.append(publication)
        self.assertEqual(len(exits), 31)
        self.assertEqual(publisher.PROFILES['conservative-all']['unrelated'], ('hengce/health/**',))
        for path in ('hengce/health_inputs.json', 'config/hengce_health_v1.json',
                     'scripts/hengce_system_health.py', 'new_authoritative_input.json'):
            self.assertFalse(publisher.matches(path, publisher.PROFILES['conservative-all']['unrelated']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
