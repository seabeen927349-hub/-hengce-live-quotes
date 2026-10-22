"""Reproduce the existing main-writer topology from the authoritative Git pin."""
import argparse
import fnmatch
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]
PIN = 'd38f2c44a6f4efb254cc126ed2b9e162121589e3'
OUT = ROOT / 'docs/engineering/writer-topology.json'
sys.path.insert(0, str(ROOT / 'scripts'))
from hengce_publish import IMMUTABLE_PREFIXES, PROFILES


def publication_profile(workflow, step):
    return {
        ('.github/workflows/hengce-q017-primary-observer.yml',
         'Persist canonical evidence and supervisor diagnostics before computation'): 'q017-primary-capture',
        ('.github/workflows/hengce-q017-primary-observer.yml',
         'Persist decision, authority and display'): 'q017-decision-display',
        ('.github/workflows/hengce-q017-backup-observer.yml',
         'Persist backup evidence or failure diagnostics'): 'q017-backup-capture',
    }.get((workflow, step), 'conservative-all')

# Explicit producer/consumer references identify paths; names confer no authority.
PATH_ROLES = {
    'scripts/hengce_q017_observation_lock_v5.py': [
        'hengce/q017_radar/observations/', 'hengce/q017_radar/decision/',
        'hengce/q017_radar/observation_latest.json', 'hengce/q017_radar/decision_latest.json',
        'hengce/q017_radar/latest.json'],
    'scripts/hengce_q017_backup_observer_v5.py': [
        'hengce/q017_radar/backup_observations/', 'hengce/q017_radar/backup_observation_latest.json',
        'hengce/q017_radar/backup_observation_status.json', 'hengce/q017_radar/backup_observation_attempt_latest.json'],
    'scripts/hengce_q017_observer_supervisor_v1.py': [
        'hengce/q017_radar/observer_supervisor_primary_status.json',
        'hengce/q017_radar/observer_supervisor_backup_status.json',
        'hengce/q017_radar/observer_supervisor_attempts/'],
    'scripts/hengce_q017_decision_lock_v4.py': ['hengce/q017_radar/decision_attempt_latest.json',
        'hengce/q017_radar/decision_attempts/'],
    'scripts/hengce_e2_live.py': ['hengce/e2_live/state_latest.json', 'hengce/e2_live/morning_latest.json',
                                'hengce/e2_live/history/'],
    'scripts/hengce_dual_engine_display.py': ['hengce/dual_engine/latest.json'],
    'scripts/hengce_q017_10d_review.py': ['hengce/q017_review_10d/ledger_latest.json', 'hengce/q017_review_10d/review_latest.json'],
    'scripts/hengce_q017_macro_cache_v1.py': ['hengce/q017_radar/data/macro_cache/latest.json',
        'hengce/q017_radar/data/sox_status.json', 'hengce/q017_radar/data/dxy_status.json'],
    'scripts/hengce_electronics_live_coverage.py': ['hengce/electronics_live/latest.json', 'hengce/electronics_live/status.json'],
    'scripts/hengce_full_market_shadow.py': ['shadow/full_market_latest.json', 'shadow/deployment_status.json'],
    'scripts/hengce_live_quote_transport.py': ['latest.json', 'live/quotes/'],
    'scripts/hengce_eod_incremental_ingest.py': ['eod/*/status.json'],
    '.github/workflows/hengce-q017-infrastructure-selfverify.yml': ['hengce/q017_radar/selfverify/infrastructure_latest.json'],
    '.github/workflows/hengce-live-universe-authoritative-handoff.yml': ['hengce/live_universe.json']
}


def show(path):
    return subprocess.check_output(['git', '-C', str(ROOT), 'show', PIN + ':' + path], text=True)


def staged_paths(run):
    # Resolve only literal paths in git-add statements and their existing path
    # arrays/for-p loops. Preserve raw statements alongside dynamic expressions.
    run = run.replace('\\\n', ' ')
    candidates = []
    for line in run.splitlines():
        if 'git add' in line:
            candidates.append(line.split('git add', 1)[1].split(';', 1)[0].split('||', 1)[0])
    candidates += re.findall(r'paths=\((.*?)\)', run, re.S)
    candidates += re.findall(r'for p in\s+(.*?);\s*do', run, re.S)
    prefixes = ('hengce/', 'research/', 'eod/', 'receipts/', 'scripts/', '.github/', 'shadow/', 'live/', 'latest.json')
    return sorted({token for value in candidates for token in shlex.split(value) if token.startswith(prefixes)})


def covers(prefix, path):
    return path.startswith(prefix) if prefix.endswith('/') else fnmatch.fnmatchcase(path, prefix)


def build():
    paths = subprocess.check_output(['git', '-C', str(ROOT), 'ls-tree', '-r', '--name-only', PIN, '.github/workflows'], text=True).splitlines()
    rows = []
    for path in paths:
        config = yaml.load(show(path), Loader=yaml.BaseLoader)
        for job_id, job in config.get('jobs', {}).items():
            publications = []
            for step in job.get('steps', []):
                run = step.get('run', '')
                if 'git push origin HEAD:main' not in run:
                    continue
                prefixes = staged_paths(run)
                profile = publication_profile(path, step.get('name'))
                roles = [{'producer_reference': source, 'paths': [p for p in outputs if any(covers(prefix, p) for prefix in prefixes)]}
                         for source, outputs in PATH_ROLES.items()]
                publications.append({
                    'step': step.get('name'), 'step_condition': step.get('if'),
                    'dependency_profile': profile,
                    'allowed_write_patterns': list(PROFILES[profile]['writes']),
                    'authoritative_read_dependency_set': {
                        'mode': 'ALL_PATHS_EXCEPT_PROVEN_UNRELATED',
                        'excluded_patterns': list(PROFILES[profile]['unrelated']),
                        'unknown_paths': 'READ_DEPENDENCY_FAIL_CLOSED'},
                    'runtime_write_set': 'Exact mode/type/blob delta of generated commit against its computation parent; emitted in receipts.',
                    'writable_path_prefixes_or_globs': prefixes,
                    'staging_statements': [line.strip() for line in run.replace('\\\n', ' ').splitlines() if 'git add' in line],
                    'immutable_paths': [p for p in IMMUTABLE_PREFIXES if any(covers(prefix, p) for prefix in prefixes)],
                    'canonical_latest_status_paths': [r for r in roles if r['paths']],
                    'other_staged_paths': 'Opaque mutable outputs unless the producer contract explicitly freezes them; no authority inferred.',
                    'before_arbitration': 'DIRECT_PUSH_WITH_BLIND_REBASE_RETRY' if '--rebase' in run or 'git rebase' in run else 'DIRECT_PUSH_REJECTS_NON_FAST_FORWARD',
                    'after_arbitration': 'EXACT_REMOTE_LEASE; WRITE_CONFLICT_OR_READ_DEPENDENCY_CHANGE_STOP; PROVEN_UNRELATED_DELTA_TRANSPLANT'
                })
            if publications:
                rows.append({'workflow': path, 'job': job_id,
                    'workflow_concurrency': config.get('concurrency'), 'job_concurrency': job.get('concurrency'),
                    'schedules': (config.get('on') or {}).get('schedule', []), 'triggers': config.get('on'),
                    'concurrent_with_other_workflows_allowed': True,
                    'concurrency_meaning': 'Existing groups are preserved; no cross-workflow capture serialization.',
                    'publications': publications})
    return {'source_commit': PIN, 'purpose': 'EXISTING_WRITER_TOPOLOGY_PLUS_PUBLICATION_ARBITRATION_MAP',
            'authority': 'INVENTORY_ONLY_NO_SIGNAL_RANKING_OR_CAPITAL_AUTHORITY',
            'scope': 'All existing workflow job steps containing a literal git push origin HEAD:main. Non-main branch writer q017-2026-sox-electronics-research is excluded. External human/API writers cannot be inventoried from repository YAML.',
            'producer_references': PATH_ROLES, 'immutable_prefixes': list(IMMUTABLE_PREFIXES),
            'writers': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    text = json.dumps(build(), ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    if args.check:
        if OUT.read_text() != text:
            raise SystemExit('STALE_WRITER_TOPOLOGY')
        print('PASS: authoritative writer topology matches pinned source')
    else:
        OUT.write_text(text)
        print('WROTE', OUT)
