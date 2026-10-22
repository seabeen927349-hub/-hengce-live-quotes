"""Fail closed on changes outside Issue #14 research/test/infrastructure scope."""
import argparse
import subprocess


def check_paths(paths):
    forbidden = [p for p in paths if not (p.startswith('research/phase1_audit/') or
                 p == '.github/workflows/hengce-phase1-foundation.yml')]
    if forbidden:
        raise ValueError('STOP_PRODUCTION_OR_OUT_OF_SCOPE_CHANGE: ' + ', '.join(forbidden))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--head', default='HEAD')
    args = parser.parse_args()
    paths = subprocess.check_output(['git', 'diff', '--name-only', args.base, args.head], text=True).splitlines()
    check_paths(paths)
    print('PASS: all changed files are research/governance/test/infrastructure; production unchanged')
