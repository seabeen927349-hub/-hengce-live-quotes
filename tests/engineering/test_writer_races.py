"""Synthetic local Git remotes only: no market data, provider calls or outcomes."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
PUBLISH = ROOT / 'scripts/hengce_publish.py'
LATEST = 'hengce/e2_live/morning_latest.json'
PRIMARY = 'hengce/q017_radar/observations/synthetic_0901_observation.json'
BACKUP = 'hengce/q017_radar/backup_observations/synthetic_0901_observation.json'


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE).decode().strip()


class WriterRaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='hengce-synthetic-race-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.remote = self.root / 'remote.git'
        subprocess.run(['git', 'init', '--bare', '--initial-branch=main', str(self.remote)], check=True, capture_output=True)
        self.a = self.clone('primary')
        self.commit(self.a, {'README': 'SYNTHETIC ONLY\n', LATEST: '{"synthetic_version":0}\n'})
        git(self.a, 'push', 'origin', 'HEAD:main')
        self.base = git(self.a, 'rev-parse', 'HEAD')
        self.b = self.clone('backup')

    def clone(self, name):
        root = self.root / name
        subprocess.run(['git', 'clone', str(self.remote), str(root)], check=True, capture_output=True)
        git(root, 'config', 'user.name', 'Synthetic Writer')
        git(root, 'config', 'user.email', 'synthetic@example.invalid')
        return root

    def commit(self, root, files):
        for name, content in files.items():
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            if content is None:
                p.unlink()
            else:
                p.write_text(content)
        git(root, 'add', '-A')
        git(root, 'commit', '-m', 'synthetic proposal')

    def publish(self, root):
        report = self.root / ('reports-' + root.name)
        run = subprocess.run([sys.executable, '-B', str(PUBLISH), '--repo', str(root),
                              '--report-dir', str(report)], text=True, capture_output=True, timeout=20)
        reports = sorted(report.glob('*.json')) if report.exists() else []
        self.assertTrue(reports, run.stdout + run.stderr)
        entries = [json.loads(p.read_text()) for p in reports]
        return run.returncode, entries[-1], entries

    def read_remote(self, path):
        return git(self.remote, 'show', 'main:' + path)

    def test_e2_primary_backup_stale_base_fail_closed(self):
        self.commit(self.a, {LATEST: '{"synthetic_version":1}\n'})
        self.commit(self.b, {LATEST: '{"synthetic_version":2}\n'})
        self.assertEqual(self.publish(self.a)[1]['result'], 'PUBLISHED')
        rc, result, _ = self.publish(self.b)
        self.assertEqual(rc, 2)
        self.assertEqual(result['result'], 'CONFLICT_FAIL_CLOSED')
        self.assertEqual(result['initial_base_sha'], self.base)
        self.assertNotEqual(result['remote_sha'], self.base)
        self.assertIn('REMOTE_ADVANCED', result['conflict_reason'])
        self.assertEqual(self.read_remote(LATEST), '{"synthetic_version":1}')

    def test_legacy_blind_rebase_can_publish_mixed_canonical_state(self):
        middle = '\n'.join('unchanged-' + str(i) for i in range(12)) + '\n'
        self.commit(self.a, {LATEST: 'version=0\n' + middle + 'binding=old\n'})
        git(self.a, 'push', 'origin', 'HEAD:main')
        git(self.b, 'fetch', 'origin', 'main')
        git(self.b, 'reset', '--hard', 'origin/main')
        self.commit(self.a, {LATEST: 'version=1\n' + middle + 'binding=old\n'})
        self.commit(self.b, {LATEST: 'version=0\n' + middle + 'binding=stale\n'})
        git(self.a, 'push', 'origin', 'HEAD:main')
        git(self.b, 'pull', '--rebase', 'origin', 'main')
        git(self.b, 'push', 'origin', 'HEAD:main')
        self.assertEqual(self.read_remote(LATEST), 'version=1\n' + middle + 'binding=stale')

    def test_duplicate_identical_publication_is_noop(self):
        for root in (self.a, self.b):
            self.commit(root, {LATEST: '{"synthetic_version":1}\n'})
        self.assertEqual(self.publish(self.a)[0], 0)
        before = git(self.remote, 'rev-parse', 'main')
        self.assertEqual(self.publish(self.b)[1]['result'], 'IDEMPOTENT_NOOP')
        self.assertEqual(git(self.remote, 'rev-parse', 'main'), before)

    def test_append_only_primary_backup_evidence_retained(self):
        self.commit(self.a, {PRIMARY: 'synthetic-primary\n'})
        self.commit(self.b, {BACKUP: 'synthetic-backup\n'})
        self.assertEqual(self.publish(self.a)[0], 0)
        rc, result, attempts = self.publish(self.b)
        self.assertEqual(rc, 0)
        self.assertEqual(result['result'], 'PUBLISHED')
        self.assertIn('RETRY_REVALIDATED', [x['result'] for x in attempts])
        self.assertEqual(self.read_remote(PRIMARY), 'synthetic-primary')
        self.assertEqual(self.read_remote(BACKUP), 'synthetic-backup')

    def test_independent_simultaneous_q017_capture_publication(self):
        # Both captures finish locally before either publisher runs; no capture lock.
        self.commit(self.a, {PRIMARY: 'primary independent capture\n'})
        self.commit(self.b, {BACKUP: 'backup independent capture\n'})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.publish, (self.a, self.b)))
        self.assertTrue(all(x[0] == 0 for x in results), results)
        self.assertEqual(self.read_remote(PRIMARY), 'primary independent capture')
        self.assertEqual(self.read_remote(BACKUP), 'backup independent capture')

    def test_immutable_observation_conflict_not_overwritten(self):
        self.commit(self.a, {PRIMARY: 'first observation\n'})
        self.commit(self.b, {PRIMARY: 'different observation\n'})
        self.assertEqual(self.publish(self.a)[0], 0)
        rc, result, _ = self.publish(self.b)
        self.assertEqual(rc, 2)
        self.assertIn('IMMUTABLE', result['conflict_reason'])
        self.assertEqual(self.read_remote(PRIMARY), 'first observation')

    def test_existing_immutable_file_cannot_be_changed_even_on_fresh_base(self):
        self.commit(self.a, {PRIMARY: 'first observation\n'})
        self.assertEqual(self.publish(self.a)[0], 0)
        fresh = self.clone('fresh')
        self.commit(fresh, {PRIMARY: 'replacement\n'})
        self.assertEqual(self.publish(fresh)[0], 2)
        self.assertEqual(self.read_remote(PRIMARY), 'first observation')

    def test_stale_mutable_different_paths_do_not_auto_merge(self):
        # No textual Git conflict, but the stale backup may depend on newer state.
        self.commit(self.a, {'hengce/e2_live/state_latest.json': 'new state\n'})
        self.commit(self.b, {LATEST: 'stale derived state\n'})
        self.assertEqual(self.publish(self.a)[0], 0)
        self.assertEqual(self.publish(self.b)[0], 2)
        self.assertEqual(self.read_remote(LATEST), '{"synthetic_version":0}')

    def test_append_only_evidence_not_rebased_across_changed_inputs(self):
        self.commit(self.a, {'README': 'changed code/input\n'})
        git(self.a, 'push', 'origin', 'HEAD:main')  # Represents an external human change.
        self.commit(self.b, {BACKUP: 'stale derived evidence\n'})
        self.assertEqual(self.publish(self.b)[0], 2)

    def test_retry_cannot_replace_newer_canonical_artifact(self):
        self.commit(self.a, {LATEST: 'winner\n'})
        self.commit(self.b, {LATEST: 'stale\n'})
        self.assertEqual(self.publish(self.a)[0], 0)
        for _ in range(2):
            self.assertEqual(self.publish(self.b)[0], 2)
        self.assertEqual(self.read_remote(LATEST), 'winner')

    def test_rejected_push_does_not_blindly_retry_mutable_state(self):
        # Advance remote after the helper's fetch but before its lease push.
        self.commit(self.a, {LATEST: 'stale\n'})
        self.commit(self.b, {LATEST: 'newer\n'})
        hook = self.a / '.git/hooks/pre-push'
        hook.write_text('#!/bin/sh\ngit -C ' + str(self.b) + ' push origin HEAD:main >/dev/null 2>&1\n')
        hook.chmod(0o755)
        rc, result, _ = self.publish(self.a)
        self.assertEqual(rc, 2)
        self.assertEqual(result['result'], 'CONFLICT_FAIL_CLOSED')
        self.assertEqual(self.read_remote(LATEST), 'newer')

    def test_observability_has_identity_base_remote_paths_and_reason(self):
        self.commit(self.a, {LATEST: 'synthetic\n'})
        rc, result, _ = self.publish(self.a)
        self.assertEqual(rc, 0)
        for key in ('workflow', 'run_id', 'initial_base_sha', 'remote_sha', 'changed_paths',
                    'result', 'conflict_reason', 'capital_authority'):
            self.assertIn(key, result)
        self.assertEqual(result['capital_authority'], 0)
        self.assertEqual(result['changed_paths'], [LATEST])


if __name__ == '__main__':
    unittest.main(verbosity=2)
