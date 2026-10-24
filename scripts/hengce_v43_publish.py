#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

PREFIX = 'hengce/v43_daily/'


class Stop(RuntimeError):
    pass


def git(repo: Path, *args: str, env=None) -> bytes:
    p = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, env=env, timeout=60)
    if p.returncode:
        raise Stop(f"GIT_FAILED:{args[0]}:{p.stderr.decode(errors='replace')[-500:]}")
    return p.stdout


def changed_paths(repo: Path, a: str, b: str) -> list[str]:
    raw = git(repo, 'diff', '--name-only', '-z', a, b)
    return sorted(x.decode() for x in raw.split(b'\0') if x)


def transplant(repo: Path, remote: str, proposed: str, paths: list[str]) -> str:
    with tempfile.TemporaryDirectory(prefix='hengce-v43-publish-') as td:
        env = {**os.environ, 'GIT_INDEX_FILE': str(Path(td) / 'index')}
        git(repo, 'read-tree', remote, env=env)
        for path in paths:
            entry = git(repo, 'ls-tree', proposed, '--', path).decode().strip()
            if not entry:
                git(repo, 'update-index', '--force-remove', '--', path, env=env)
                continue
            meta, name = entry.split('\t', 1)
            mode, typ, blob = meta.split()
            if typ != 'blob' or name != path:
                raise Stop(f'UNEXPECTED_TREE_ENTRY:{path}')
            git(repo, 'update-index', '--add', '--cacheinfo', f'{mode},{blob},{path}', env=env)
        tree = git(repo, 'write-tree', env=env).decode().strip()
    return git(repo, 'commit-tree', tree, '-p', remote, '-m', 'HENGCE V43 daily isolated lease publication').decode().strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', type=Path, default=Path.cwd())
    ap.add_argument('--target', default='main')
    a = ap.parse_args()
    repo = a.repo.resolve()
    proposed = git(repo, 'rev-parse', 'HEAD').decode().strip()
    parents = git(repo, 'rev-list', '--parents', '-n', '1', proposed).decode().split()[1:]
    if len(parents) != 1:
        raise Stop('EXPECTED_ONE_PARENT')
    base = parents[0]
    paths = changed_paths(repo, base, proposed)
    if not paths:
        print('V43_PUBLISH_NO_CHANGES')
        return 0
    outside = [p for p in paths if not p.startswith(PREFIX)]
    if outside:
        raise Stop('V43_WRITE_SET_VIOLATION:' + ','.join(outside))

    ref = f'refs/heads/{a.target}'
    for attempt in range(1, 4):
        git(repo, 'fetch', '--no-tags', 'origin', ref)
        remote = git(repo, 'rev-parse', 'FETCH_HEAD').decode().strip()
        candidate = proposed
        if remote != base:
            git(repo, 'merge-base', '--is-ancestor', base, remote)
            remote_paths = changed_paths(repo, base, remote)
            conflicts = [p for p in remote_paths if p.startswith(PREFIX)]
            if conflicts:
                raise Stop('V43_REMOTE_NAMESPACE_CHANGED:' + ','.join(conflicts))
            candidate = transplant(repo, remote, proposed, paths)
        parent = git(repo, 'rev-parse', candidate + '^').decode().strip()
        if parent != remote:
            raise Stop('V43_CANDIDATE_PARENT_NOT_REMOTE')
        run = subprocess.run(
            ['git', '-C', str(repo), 'push', f'--force-with-lease={ref}:{remote}', 'origin', f'{candidate}:{ref}'],
            capture_output=True, timeout=60,
        )
        if run.returncode == 0:
            print(f'V43_PUBLISHED:{candidate}:attempt={attempt}:paths={len(paths)}')
            return 0
        print(f'V43_LEASE_RETRY:{attempt}')
    raise Stop('V43_PUBLISH_LEASE_RETRY_LIMIT')


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Stop as exc:
        print('V43_PUBLISH_FAIL_CLOSED:' + str(exc))
        raise SystemExit(2)
