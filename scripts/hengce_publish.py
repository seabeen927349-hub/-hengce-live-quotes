#!/usr/bin/env python3
"""Publish one generated commit with an exact remote lease; never rebase outputs.

No model imports, clocks used by decisions, market calls or artifact rewrites.
Canonical/observation immutability follows explicit producer contracts below.
"""
import argparse
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


def additions_only(base, target, paths):
    return all(p not in base and p in target and target[p][0] == '100644' and
               target[p][1] == 'blob' and immutable(p) for p in paths)


class Reporter:
    def __init__(self, directory, base, proposed, paths):
        self.directory = Path(directory)
        self.identity = dict(workflow=os.environ.get('GITHUB_WORKFLOW', 'LOCAL_SYNTHETIC_OR_MANUAL'),
                             run_id=os.environ.get('GITHUB_RUN_ID', 'LOCAL'),
                             run_attempt=os.environ.get('GITHUB_RUN_ATTEMPT', 'LOCAL'),
                             job=os.environ.get('GITHUB_JOB', 'LOCAL'),
                             initial_base_sha=base, proposed_sha=proposed, changed_paths=sorted(paths),
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


def merged_evidence_commit(repo, remote, wanted, paths):
    # Isolated index: never reset, rebase, stash or rewrite the producer worktree.
    with tempfile.TemporaryDirectory(prefix='hengce-publish-index-') as td:
        env = {**os.environ, 'GIT_INDEX_FILE': str(Path(td) / 'index')}
        git(repo, 'read-tree', remote, env=env)
        for path in paths:
            mode, _, blob = wanted[path]
            git(repo, 'update-index', '--add', '--cacheinfo', mode + ',' + blob + ',' + path, env=env)
        combined = git(repo, 'write-tree', env=env).decode().strip()
    return git(repo, 'commit-tree', combined, '-p', remote, '-m',
               'HENGCE lease publication: retain compatible immutable evidence').decode().strip()


def publish(repo, report_dir):
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
        reporter = Reporter(report_dir, base, proposed, paths)
        invalid = [p for p in paths if immutable(p) and
                   (p in original or wanted.get(p, ('',))[0] != '100644')]
        # Preserve captured evidence in the CI artifact even if mutable status
        # conflicts later reject the entire publication. This is not authority.
        for path in paths:
            if immutable(path) and path not in original and wanted.get(path, ('',))[0] == '100644':
                retained = Path(report_dir) / 'retained-evidence' / proposed / path
                retained.parent.mkdir(parents=True, exist_ok=True)
                retained.write_bytes(git(repo, 'cat-file', 'blob', wanted[path][2]))
        # Three leases at most. A mutable proposal never retries over advancement.
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
                return 0
            candidate = proposed
            if remote != base:
                # Validate BOTH complete deltas. Any changed input/code/mutable
                # status rejects the proposal even when Git would merge cleanly.
                git(repo, 'merge-base', '--is-ancestor', base, remote)
                remote_paths = [p for p in original.keys() | current.keys() if original.get(p) != current.get(p)]
                if not additions_only(original, wanted, paths) or not additions_only(original, current, remote_paths):
                    raise Stop('REMOTE_ADVANCED_REQUIRES_FRESH_COMPUTATION_OR_HUMAN_REVIEW')
                reporter.emit('RETRY_REVALIDATED', remote, attempt=attempt,
                              revalidation='BOTH_DELTAS_ARE_COMPATIBLE_IMMUTABLE_ADDITIONS_ONLY')
                candidate = merged_evidence_commit(repo, remote, wanted, paths)
            # Candidate always has exactly the fetched remote as parent; the
            # explicit lease rejects advancement/rewind between fetch and push.
            if git(repo, 'rev-parse', candidate + '^').decode().strip() != remote:
                raise Stop('CANDIDATE_PARENT_IS_NOT_OBSERVED_REMOTE')
            run = subprocess.run(['git', '-C', str(repo), 'push',
                                  '--force-with-lease=refs/heads/main:' + remote,
                                  'origin', candidate + ':refs/heads/main'], capture_output=True, timeout=60)
            if run.returncode == 0:
                reporter.emit('PUBLISHED', remote, attempt=attempt, published_sha=candidate)
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
    parser.add_argument('--report-dir', type=Path, default=Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir())) / 'hengce-publication')
    args = parser.parse_args()
    return publish(args.repo, args.report_dir)


if __name__ == '__main__':
    raise SystemExit(main())
