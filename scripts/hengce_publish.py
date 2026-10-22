#!/usr/bin/env python3
"""Publish one generated commit with an exact remote lease; never rebase outputs.

No model imports, clocks used by decisions, market calls or artifact rewrites.
Canonical/observation immutability follows explicit producer contracts below.
"""
import argparse
import fnmatch
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

# Producer write_once contracts, not a filename-based authority inference.
# E2 history is intentionally NOT listed: it is a mutable per-date snapshot.
IMMUTABLE_PREFIXES = (
    'hengce/q017_radar/observations/',
    'hengce/q017_radar/backup_observations/',
    'hengce/q017_radar/decision/',
    'hengce/q017_radar/history/',
    'hengce/q017_radar/backup_observation_history/',
)

# Publication contracts, not model authority. Read dependencies are conservative
# supersets: every path (including newly introduced paths) is a dependency unless
# explicitly proven unrelated by the producer sources named in the inventory.
TRANSPORT_ONLY = ('latest.json', 'live/**', 'shadow/**', 'hengce/electronics_live/**')
BACKUP_WRITES = (
    'hengce/q017_radar/backup_observations/**',
    'hengce/q017_radar/backup_observation_history/**',
    'hengce/q017_radar/backup_observation_latest.json',
    'hengce/q017_radar/backup_observation_status.json',
    'hengce/q017_radar/backup_observation_attempts/**',
    'hengce/q017_radar/backup_observation_attempt_latest.json',
    'hengce/q017_radar/observer_supervisor_backup_status.json',
    'hengce/q017_radar/observer_supervisor_attempts/*_backup.json',
)
PRIMARY_CAPTURE_WRITES = (
    'hengce/q017_radar/observations/**', 'hengce/q017_radar/observation_latest.json',
    'hengce/q017_radar/history/**', 'hengce/q017_radar/decision_attempts/**',
    'hengce/q017_radar/decision_attempt_latest.json', 'hengce/q017_radar/latest.json',
    'hengce/q017_radar/observer_supervisor_primary_status.json',
    'hengce/q017_radar/observer_supervisor_attempts/*_primary.json',
)
PROFILES = {
    'conservative-all': {'writes': ('**',), 'unrelated': ()},
    'q017-primary-capture': {
        'writes': PRIMARY_CAPTURE_WRITES,
        'unrelated': TRANSPORT_ONLY + BACKUP_WRITES + ('hengce/e2_live/**', 'hengce/dual_engine/**'),
    },
    'q017-backup-capture': {
        'writes': BACKUP_WRITES,
        'unrelated': TRANSPORT_ONLY + (
            'hengce/e2_live/**', 'hengce/dual_engine/**',
            'hengce/q017_radar/observations/**', 'hengce/q017_radar/observation_latest.json',
            'hengce/q017_radar/history/**', 'hengce/q017_radar/observer_supervisor_primary_status.json',
            'hengce/q017_radar/observer_supervisor_attempts/*_primary.json'),
    },
    'q017-decision-display': {
        'writes': ('hengce/q017_radar/decision/**', 'hengce/q017_radar/decision_latest.json',
                   'hengce/q017_radar/latest.json', 'hengce/q017_radar/history/**',
                   'hengce/q017_radar/signal_ledger.jsonl', 'hengce/dual_engine/latest.json'),
        # Display reads E2 state: E2 is deliberately NOT excluded here.
        'unrelated': TRANSPORT_ONLY + BACKUP_WRITES,
    },
}


def matches(path, patterns):
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


class Stop(RuntimeError):
    pass


def git(repo, *args, env=None, data=None):
    run = subprocess.run(['git', '-C', str(repo), *args], input=data, capture_output=True,
                         env=env, timeout=60)
    if run.returncode:
        raise Stop('GIT_OPERATION_FAILED:' + args[0])
    return run.stdout


def tree(repo, ref):
    result = {}
    for row in git(repo, 'ls-tree', '-rz', ref).split(b'\0'):
        if row:
            meta, name = row.split(b'\t', 1)
            result[name.decode()] = tuple(meta.decode().split())  # mode, type, blob
    return result


def immutable(path):
    return path.startswith(IMMUTABLE_PREFIXES)


class Reporter:
    def __init__(self, directory, base, proposed, paths, profile='conservative-all'):
        self.directory = Path(directory)
        self.identity = dict(workflow=os.environ.get('GITHUB_WORKFLOW', 'LOCAL_SYNTHETIC_OR_MANUAL'),
                             run_id=os.environ.get('GITHUB_RUN_ID', 'LOCAL'),
                             run_attempt=os.environ.get('GITHUB_RUN_ATTEMPT', 'LOCAL'),
                             job=os.environ.get('GITHUB_JOB', 'LOCAL'),
                             initial_base_sha=base, proposed_sha=proposed, changed_paths=sorted(paths),
                             dependency_profile=profile, write_set=sorted(paths),
                             immutable_write_set=sorted(p for p in paths if immutable(p)),
                             allowed_write_patterns=list(PROFILES[profile]['writes']),
                             authoritative_read_dependency_set={
                                 'mode': 'ALL_PATHS_EXCEPT_PROVEN_UNRELATED',
                                 'excluded_patterns': list(PROFILES[profile]['unrelated']),
                                 'unknown_paths': 'READ_DEPENDENCY_FAIL_CLOSED'},
                             capital_authority=0, signal_authority=False)

    def emit(self, result, remote=None, reason='', **extra):
        entry = {**self.identity, 'remote_sha': remote, 'result': result,
                 'conflict_reason': reason, **extra}
        self.directory.mkdir(parents=True, exist_ok=True)
        # Independent unique files, outside the checkout; no shared latest pointer.
        path = self.directory / (str(time.time_ns()) + '-' + uuid.uuid4().hex + '.json')
        with path.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + '\n')
        print(json.dumps(entry, ensure_ascii=False, sort_keys=True), flush=True)
        return entry


def transplanted_commit(repo, remote, wanted, paths):
    # Isolated index: never reset, rebase, stash or rewrite the producer worktree.
    with tempfile.TemporaryDirectory(prefix='hengce-publish-index-') as td:
        env = {**os.environ, 'GIT_INDEX_FILE': str(Path(td) / 'index')}
        git(repo, 'read-tree', remote, env=env)
        for path in paths:
            if path not in wanted:
                git(repo, 'update-index', '--force-remove', '--', path, env=env)
                continue
            mode, _, blob = wanted[path]
            git(repo, 'update-index', '--add', '--cacheinfo', mode + ',' + blob + ',' + path, env=env)
        combined = git(repo, 'write-tree', env=env).decode().strip()
    return git(repo, 'commit-tree', combined, '-p', remote, '-m',
               'HENGCE lease publication: transplant dependency-revalidated bytes').decode().strip()


def adopt_accepted_checkout(repo, proposed, accepted):
    if proposed != accepted:
        # Git's two-tree update preserves dirty paths unchanged between trees and
        # refuses to overwrite dirty/untracked collisions. Never reset/stash.
        # Subsequent computation must start from the accepted publication base,
        # not an unpublished sibling commit left behind by a transplant/no-op.
        try:
            git(repo, 'read-tree', '-u', '-m', proposed, accepted)
            git(repo, 'update-ref', 'HEAD', accepted, proposed)
        except Stop as exc:
            raise Stop('ACCEPTED_PUBLICATION_LOCAL_SYNC_FAILED:' + accepted + ':' + str(exc)) from exc


def publish(repo, report_dir, profile='conservative-all'):
    remote = None
    reporter = Reporter(report_dir, None, None, [])
    try:
        proposed = git(repo, 'rev-parse', 'HEAD').decode().strip()
        parents = git(repo, 'rev-list', '--parents', '-n', '1', proposed).decode().split()[1:]
        if len(parents) != 1:
            raise Stop('EXPECTED_SINGLE_GENERATED_COMMIT_WITH_ONE_PARENT')
        base = parents[0]
        original, wanted = tree(repo, base), tree(repo, proposed)
        paths = sorted(p for p in original.keys() | wanted.keys() if original.get(p) != wanted.get(p))
        reporter = Reporter(report_dir, base, proposed, paths, profile)
        outside = [p for p in paths if not matches(p, PROFILES[profile]['writes'])]
        if outside:
            raise Stop('WRITE_SET_OUTSIDE_DEPENDENCY_PROFILE:' + ','.join(outside))
        invalid = [p for p in paths if immutable(p) and
                   (p in original or wanted.get(p, ('',))[0] != '100644')]
        # Preserve captured evidence in the CI artifact even if mutable status
        # conflicts later reject the entire publication. This is not authority.
        for path in paths:
            if immutable(path) and path not in original and wanted.get(path, ('',))[0] == '100644':
                retained = Path(report_dir) / 'retained-evidence' / proposed / path
                retained.parent.mkdir(parents=True, exist_ok=True)
                retained.write_bytes(git(repo, 'cat-file', 'blob', wanted[path][2]))
        # Three leases at most; every retry checks the original base/proposal.
        for attempt in range(1, 4):
            git(repo, 'fetch', '--no-tags', 'origin', 'refs/heads/main')
            remote = git(repo, 'rev-parse', 'FETCH_HEAD').decode().strip()
            current = tree(repo, remote)
            if invalid:
                raise Stop('IMMUTABLE_EXISTING_BYTES_OR_MODE_CHANGE:' + ','.join(invalid))
            conflicts = [p for p in paths if immutable(p) and p in current and current.get(p) != wanted.get(p)]
            if conflicts:
                raise Stop('IMMUTABLE_REMOTE_CONFLICT:' + ','.join(conflicts))
            if all(current.get(p) == wanted.get(p) for p in paths):
                reporter.emit('IDEMPOTENT_NOOP', remote, attempt=attempt)
                adopt_accepted_checkout(repo, proposed, remote)
                return 0
            candidate = proposed
            if remote != base:
                git(repo, 'merge-base', '--is-ancestor', base, remote)
                remote_paths = sorted(p for p in original.keys() | current.keys() if original.get(p) != current.get(p))
                overlapping = [p for p in paths if current.get(p) != original.get(p) and current.get(p) != wanted.get(p)]
                if overlapping:
                    raise Stop('REMOTE_ADVANCED_WRITE_SET_CONFLICT:' + ','.join(overlapping))
                dependencies = [p for p in remote_paths if not matches(p, PROFILES[profile]['unrelated'])]
                if dependencies:
                    raise Stop('REMOTE_ADVANCED_READ_DEPENDENCY_CHANGED:' + ','.join(dependencies))
                reporter.emit('RETRY_REVALIDATED', remote, attempt=attempt,
                              remote_changed_paths=remote_paths,
                              revalidation='NO_INCOMPATIBLE_WRITE_OVERLAP_AND_NO_READ_DEPENDENCY_CHANGED')
                candidate = transplanted_commit(repo, remote, wanted, paths)
            # Candidate always has exactly the fetched remote as parent; the
            # explicit lease rejects advancement/rewind between fetch and push.
            if git(repo, 'rev-parse', candidate + '^').decode().strip() != remote:
                raise Stop('CANDIDATE_PARENT_IS_NOT_OBSERVED_REMOTE')
            run = subprocess.run(['git', '-C', str(repo), 'push',
                                  '--force-with-lease=refs/heads/main:' + remote,
                                  'origin', candidate + ':refs/heads/main'], capture_output=True, timeout=60)
            if run.returncode == 0:
                reporter.emit('PUBLISHED', remote, attempt=attempt, published_sha=candidate)
                adopt_accepted_checkout(repo, proposed, candidate)
                return 0
            # A rejected lease is re-fetched and revalidated from ORIGINAL bytes,
            # never from a rebased or conflict-resolved proposal.
            reporter.emit('CONFLICT_FAIL_CLOSED', remote, reason='PUSH_REJECTED_OR_ACK_UNKNOWN_REFETCH_REQUIRED',
                          attempt=attempt)
        raise Stop('PUBLISH_LEASE_RETRY_LIMIT')
    except (Stop, subprocess.TimeoutExpired, OSError) as exc:
        reason = str(exc) if isinstance(exc, Stop) else type(exc).__name__
        reporter.emit('CONFLICT_FAIL_CLOSED', remote, reason)
        return 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path.cwd())
    parser.add_argument('--profile', choices=sorted(PROFILES), default='conservative-all')
    parser.add_argument('--report-dir', type=Path, default=Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir())) / 'hengce-publication')
    args = parser.parse_args()
    return publish(args.repo, args.report_dir, args.profile)


if __name__ == '__main__':
    raise SystemExit(main())
