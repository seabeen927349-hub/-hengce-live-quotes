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

    def publish(self, root, profile=None):
        report = self.root / ('reports-' + root.name)
        command = [sys.executable, '-B', str(PUBLISH), '--repo', str(root), '--report-dir', str(report)]
        if profile:
            command += ['--profile', profile]
        run = subprocess.run(command, text=True, capture_output=True, timeout=20)
        reports = sorted(report.glob('*.json')) if report.exists() else []
        self.assertTrue(reports, run.stdout + run.stderr)
        entries = [json.loads(p.read_text()) for p in reports]
        return run.returncode, entries[-1], entries

    def read_remote(self, path):
        return git(self.remote, 'show', 'main:' + path)

    def test_real_0745_0815_0850_0901_interleaving_publishes_both_captures(self):
        # 07:45 primary and 08:15 backup both start from B; no clock sleeps,
        # market values or outcomes. 08:50 E2 publishes R before either capture.
        e2 = self.clone('e2-0850')
        self.commit(e2, {LATEST: '08:50 synthetic E2 bind\n',
                         'hengce/dual_engine/latest.json': '08:50 synthetic display\n'})
        self.assertEqual(self.publish(e2)[0], 0)
        r = git(self.remote, 'rev-parse', 'main')
        self.commit(self.a, {PRIMARY: '09:01 synthetic primary capture\n',
                            'hengce/q017_radar/observation_latest.json': 'primary pointer\n',
                            'hengce/q017_radar/observer_supervisor_primary_status.json': 'primary status\n'})
        self.commit(self.b, {BACKUP: '09:01 synthetic backup capture\n',
                            'hengce/q017_radar/backup_observation_status.json': 'backup status\n'})
        for root, profile in ((self.a, 'q017-primary-capture'), (self.b, 'q017-backup-capture')):
            rc, result, attempts = self.publish(root, profile)
            self.assertEqual(rc, 0, result)
            self.assertEqual(result['result'], 'PUBLISHED')
            self.assertIn('RETRY_REVALIDATED', [x['result'] for x in attempts])
            self.assertEqual(result['initial_base_sha'], self.base)
            self.assertIn(r, [x['remote_sha'] for x in attempts] if root == self.a else [r])
        self.assertEqual(self.read_remote(LATEST), '08:50 synthetic E2 bind')
        self.assertEqual(self.read_remote(PRIMARY), '09:01 synthetic primary capture')
        self.assertEqual(self.read_remote(BACKUP), '09:01 synthetic backup capture')

    def test_q017_macro_dependency_change_fails_closed(self):
        self.commit(self.a, {'hengce/q017_radar/data/macro_cache/latest.json': 'changed macro\n'})
        git(self.a, 'push', 'origin', 'HEAD:main')
        self.commit(self.b, {BACKUP: 'capture using old macro\n'})
        rc, result, _ = self.publish(self.b, 'q017-backup-capture')
        self.assertEqual(rc, 2)
        self.assertIn('READ_DEPENDENCY', result['conflict_reason'])

    def test_transplanted_capture_can_publish_following_decision(self):
        self.commit(self.a, {LATEST: '08:50 E2 update\n'})
        self.assertEqual(self.publish(self.a)[0], 0)
        self.commit(self.b, {PRIMARY: '09:01 capture\n'})
        self.assertEqual(self.publish(self.b, 'q017-primary-capture')[0], 0)
        accepted = git(self.remote, 'rev-parse', 'main')
        self.assertEqual(git(self.b, 'rev-parse', 'HEAD'), accepted)
        self.assertEqual((self.b / LATEST).read_text(), '08:50 E2 update\n')
        self.commit(self.b, {'hengce/q017_radar/decision/synthetic_0901.json': 'synthetic decision\n'})
        self.assertEqual(self.publish(self.b, 'q017-decision-display')[0], 0)

    def test_capture_profile_cannot_publish_out_of_contract_writes(self):
        self.commit(self.a, {LATEST: 'E2 cannot masquerade as Q017 capture\n'})
        rc, result, _ = self.publish(self.a, 'q017-primary-capture')
        self.assertEqual(rc, 2)
        self.assertIn('WRITE_SET', result['conflict_reason'])

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
        git(self.b, 'commit', '--amend', '--no-edit', '--date=2020-01-01T00:00:00Z')
        self.assertEqual(self.publish(self.a)[0], 0)
        before = git(self.remote, 'rev-parse', 'main')
        self.assertEqual(self.publish(self.b)[1]['result'], 'IDEMPOTENT_NOOP')
        self.assertEqual(git(self.remote, 'rev-parse', 'main'), before)

    def test_simultaneous_e2_writers_have_exactly_one_winner(self):
        self.commit(self.a, {LATEST: 'primary\n'})
        self.commit(self.b, {LATEST: 'backup\n'})
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.publish, (self.a, self.b)))
        self.assertEqual(sorted(x[0] for x in results), [0, 2])
        self.assertIn(self.read_remote(LATEST), ('primary', 'backup'))

    def test_mixed_q017_status_conflict_retains_backup_capture_in_ci_artifact(self):
        self.commit(self.a, {PRIMARY: 'primary capture\n', 'hengce/q017_radar/observer_supervisor_primary_status.json': 'primary status\n'})
        self.commit(self.b, {BACKUP: 'backup capture\n', 'hengce/q017_radar/observer_supervisor_backup_status.json': 'backup status\n'})
        self.assertEqual(self.publish(self.a)[0], 0)
        self.assertEqual(self.publish(self.b)[0], 2)
        retained = list((self.root / 'reports-backup/retained-evidence').glob('*/' + BACKUP))
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0].read_text(), 'backup capture\n')
        self.assertEqual(self.read_remote(PRIMARY), 'primary capture')

    def test_revalidation_does_not_reset_dirty_or_untracked_worktree(self):
        self.commit(self.a, {PRIMARY: 'primary\n'})
        self.commit(self.b, {BACKUP: 'backup\n'})
        (self.b / 'README').write_text('UNSTAGED SYNTHETIC DIAGNOSTIC\n')
        (self.b / 'untracked').write_text('UNTRACKED\n')
        head = git(self.b, 'rev-parse', 'HEAD')
        self.assertEqual(self.publish(self.a)[0], 0)
        self.assertEqual(self.publish(self.b)[0], 0)
        self.assertEqual((self.b / 'README').read_text(), 'UNSTAGED SYNTHETIC DIAGNOSTIC\n')
        self.assertEqual((self.b / 'untracked').read_text(), 'UNTRACKED\n')
        self.assertEqual(git(self.b, 'rev-parse', 'HEAD'), head)

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
