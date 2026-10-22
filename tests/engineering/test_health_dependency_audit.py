"""Synthetic negative mutations and actual repository boundary audit, offline."""
import json
from pathlib import Path
import unittest

from health_dependency_audit import ROOT, INFRASTRUCTURE, audit, repository_sources


class HealthDependencyAuditTests(unittest.TestCase):
    def test_actual_inventoried_producers_and_all_future_source_roots(self):
        inventory = json.loads((ROOT / 'docs/engineering/writer-topology.json').read_text())
        workflows = {w['workflow'] for w in inventory['writers']}
        errors, checked = audit(repository_sources(), workflows)
        self.assertEqual(errors, [])
        self.assertTrue(workflows <= set(checked))
        for p in ('scripts/hengce_e2_live.py', 'scripts/hengce_daily_command_center.py',
                  'scripts/hengce_q017_observer_supervisor_v2.py',
                  'scripts/hengce_q017_recovery_compute_v5.py'):
            self.assertIn(p, checked)

    def test_injected_existing_producer_read_is_rejected(self):
        sources = repository_sources()
        p = 'scripts/hengce_e2_live.py'
        sources[p] += '\nhealth_input = Path("hengce/health/latest.json").read_text()\n'
        errors, _ = audit(sources)
        self.assertTrue(any(e.startswith(p + ': HEALTH_') for e in errors))

    def test_future_producer_reads_writes_stages_and_dependency_declarations_rejected(self):
        cases = {
            'scripts/future_producer.py': 'INPUTS = ["hengce/health/latest.json"]',
            'scripts/future_writer.py': 'Path("hengce/health/latest.json").write_text("bad")',
            '.github/workflows/future-producer.yml': 'run: git add hengce/health/',
            'config/future_producer.json': '{"read_dependencies":["hengce/health/**"]}',
            'scripts/future_producer.sh': 'cat hengce/health/latest.json',
            'scripts/future_producer.js': 'readFileSync("hengce/health/latest.json")',
        }
        for p, text in cases.items():
            with self.subTest(path=p):
                self.assertTrue(audit({p: text})[0])

    def test_import_alias_dynamic_import_and_split_paths_rejected(self):
        for text in ('import hengce_system_health as h',
                     'from hengce_health_collect_runs import collect',
                     'importlib.import_module("hengce_system_" + "health")',
                     'p = ROOT / "hengce" / "health" / "latest.json"',
                     'p = os.path.join("hengce", "hea" + "lth", "latest.json")'):
            with self.subTest(source=text):
                self.assertTrue(audit({'scripts/future.py': text})[0])

    def test_imported_test_helper_loses_its_exemption(self):
        for source in ('from tests.helpers import hidden',
                       'importlib.import_module("tests.helpers.hidden")'):
            sources = {'scripts/producer.py': source,
                       'tests/helpers/hidden.py': 'INPUT = "hengce/health/latest.json"'}
            self.assertTrue(any(e.startswith('tests/helpers/hidden.py:') for e in audit(sources)[0]))

    def test_producer_workflow_cannot_hide_dependency_in_test_command(self):
        p = '.github/workflows/producer.yml'
        sources = {p: 'run: python scripts/test_hidden.py\n# hengce_publish.py',
                   'scripts/test_hidden.py': 'INPUT = "hengce/health/latest.json"'}
        self.assertTrue(any(e.startswith('scripts/test_hidden.py:') for e in audit(sources)[0]))

    def test_exact_infrastructure_and_uninvoked_health_tests_allowed(self):
        sources = {p: 'hengce/health/latest.json' for p in INFRASTRUCTURE}
        sources.update({'tests/test_health.py': 'import hengce_system_health',
                        'docs/engineering/health.md': 'hengce/health/**',
                        'config/producer_status.json': '{"health":{"ready":true}}',
                        'scripts/producer.py': 'import json'})
        self.assertEqual(audit(sources)[0], [])
        self.assertTrue(audit({'scripts/health_helper.py': 'INPUT = "hengce/health/latest.json"'})[0])

    def test_missing_inventoried_workflow_and_invalid_source_fail_closed(self):
        self.assertTrue(audit({}, {'.github/workflows/missing.yml'})[0])
        self.assertTrue(audit({'scripts/future.py': 'invalid python !'})[0])

    def test_ci_guard_is_unfiltered_and_both_test_workflows_run_it(self):
        import yaml
        writer = yaml.load((ROOT / '.github/workflows/hengce-writer-race-tests.yml').read_text(), Loader=yaml.BaseLoader)
        self.assertFalse((writer['on'].get('pull_request') or {}).get('paths'))
        for filename in ('hengce-writer-race-tests.yml', 'hengce-system-health.yml'):
            text = (ROOT / '.github/workflows' / filename).read_text()
            self.assertIn('python -B tests/engineering/test_health_dependency_audit.py', text)


if __name__ == '__main__':
    unittest.main(verbosity=2)
