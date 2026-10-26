#!/usr/bin/env python3
"""Offline Q017 replay against the immutable cleanup starting commit.

Run with the runtime dependencies installed: python -B tests/engineering/q017_cleanup_audit.py
No historical artifact in the checkout is written or regenerated.
"""
import argparse
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = '780e8a225de637c32b42da0d28f5aa1428e49e20'
RESULTS = ROOT / 'research/q017_codex_cleanup_20261026/results'


def sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def deny_network():
    import socket
    import requests
    import urllib.request
    def deny(*args, **kwargs):
        raise AssertionError('Q017_AUDIT_NETWORK_FORBIDDEN')
    socket.socket.connect = deny
    socket.create_connection = deny
    requests.sessions.Session.request = deny
    urllib.request.urlopen = deny


def probe(root):
    deny_network()
    from datetime import datetime
    from unittest.mock import patch
    sys.path.insert(0, str(root / 'scripts'))
    import hengce_q017_observation_lock_v5 as q
    import hengce_q017_authority_guard_v5 as guard
    semantic = {}; performance = {}
    for date in ('20261021', '20261022'):
        op = root / f'hengce/q017_radar/observations/{date}_0901_observation.json'
        dp = root / f'hengce/q017_radar/decision/{date}_0901.json'
        o = json.loads(op.read_text()); locked = json.loads(dp.read_text())
        assert q.validate_observation(o)[0]
        ranking = []
        def profile(frame, event, arg):
            if event == 'return' and frame.f_code is q.build_decision_from_observation.__code__:
                ranking.extend(copy.deepcopy(frame.f_locals['cand']))
        sys.setprofile(profile)
        try:
            decision = q.build_decision_from_observation(o, datetime.fromisoformat(locked['generated_at_taipei']))
        finally:
            sys.setprofile(None)
        assert decision == locked, 'FROZEN_DECISION_MISMATCH:' + date
        assert guard.validate_decision_payload(decision)[0]
        failures = {}
        for name in ('missing_quote', 'late_0902', 'late_0903', 'outside_electronics', 'coverage', 'universe_hash', 'observation_hash'):
            bad = copy.deepcopy(o); ticker = next(iter(bad['quotes']))
            if name == 'missing_quote': del bad['quotes'][ticker]
            elif name.startswith('late_'): bad['quotes'][ticker]['fetched_at_taipei'] = o['trade_date'] + 'T09:' + ('02' if name.endswith('0902') else '03') + ':00+08:00'
            elif name == 'outside_electronics': bad['eligible_models'][0]['ticker'] = '2603'
            elif name == 'coverage': bad['data_status']['eligible_quote_row_coverage'] = .99
            elif name == 'universe_hash': bad['universe_lock']['universe_sha256'] = '0' * 64
            elif name == 'observation_hash': bad['observation_snapshot_sha256'] = '0' * 64
            if name != 'observation_hash':
                bad['observation_snapshot_sha256'] = q.csha({k:v for k,v in bad.items() if k != 'observation_snapshot_sha256'})
            failures[name] = q.validate_observation(bad)
            assert failures[name][0] is False
            try: q.build_decision_from_observation(bad)
            except RuntimeError: pass
            else: raise AssertionError('INVALID_OBSERVATION_COMPUTED:' + name)
        semantic[date] = {'decision': decision, 'full_ranking': ranking, 'fail_closed': failures,
                          'formal_buy_count': sum(r.get('qualified') is True for r in decision['top3']) if decision['market_state'] == 'GO' else 0,
                          'fixture_raw_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (op, dp)}}
        reads = []; hashes = []; original_read = Path.read_text; original_hash = q.csha
        def read(path, *args, **kwargs):
            reads.append(str(path.relative_to(root))); return original_read(path, *args, **kwargs)
        def hashed(value):
            hashes.append(1); return original_hash(value)
        with patch.object(Path, 'read_text', read), patch.object(q, 'csha', hashed):
            assert guard.validate_decision_payload(decision)[0]
        samples = []
        for _ in range(5):
            start = time.perf_counter()
            for _ in range(20): assert guard.validate_decision_payload(decision)[0]
            samples.append((time.perf_counter() - start) / 20)
        compute_samples = []
        for _ in range(5):
            start = time.perf_counter()
            for _ in range(20):
                assert q.build_decision_from_observation(o, datetime.fromisoformat(locked['generated_at_taipei'])) == locked
            compute_samples.append((time.perf_counter() - start) / 20)
        performance[date] = {'guard_seconds_samples': samples, 'guard_seconds_median': sorted(samples)[2],
                             'recompute_seconds_samples': compute_samples, 'recompute_seconds_median': sorted(compute_samples)[2],
                             'file_reads_per_validation': len(reads), 'json_parses_per_validation': len(reads),
                             'canonical_hash_calls_per_validation': len(hashes), 'network_calls': 0,
                             'observation_bytes': op.stat().st_size, 'decision_bytes': dp.stat().st_size}
    return {'semantic': semantic, 'performance': performance}


def run_probe(root):
    p = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--probe', str(root)],
                       capture_output=True, text=True, timeout=90)
    if p.returncode: raise RuntimeError(p.stderr[-6000:])
    return json.loads(p.stdout)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--probe', type=Path); ap.add_argument('--baseline-only', action='store_true')
    ap.add_argument('--before',default=BASE); ap.add_argument('--after'); ap.add_argument('--report',type=Path); a = ap.parse_args()
    if a.probe:
        print(json.dumps(probe(a.probe), ensure_ascii=False, allow_nan=False)); return
    RESULTS.mkdir(parents=True, exist_ok=True)
    if not a.baseline_only:
        for name in ('EQUIVALENCE_TEST_REPORT.json','PERFORMANCE_BEFORE_AFTER.json'):
            (RESULTS/name).unlink(missing_ok=True)
        if a.report:a.report.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix='q017-audit-') as td:
        before = Path(td) / 'before'; before.mkdir()
        data = subprocess.check_output(['git', '-C', str(ROOT), 'archive', BASE])
        with tarfile.open(fileobj=io.BytesIO(data)) as archive: archive.extractall(before, filter='data')
        baseline = run_probe(before)
        if a.baseline_only:
            evidence = {'artifact_role':'OFFLINE_TEST_REPLAY_NOT_ORIGINAL_MARKET_CAPTURE', 'baseline_commit':BASE,
                        'formal_output_authority':False, **baseline}
            (RESULTS / 'BASELINE_REPLAY.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
            print('BASELINE_REPLAY_PASS'); return
        def export_revision(ref,name):
            dest=Path(td)/name;dest.mkdir()
            raw=subprocess.check_output(['git','-C',str(ROOT),'archive',ref])
            with tarfile.open(fileobj=io.BytesIO(raw)) as archive:archive.extractall(dest,filter='data')
            # Both revisions replay the exact original observations/decisions.
            for folder in ('observations','decision'):
                for original in (before/'hengce/q017_radar'/folder).glob('*.json'):
                    target=dest/'hengce/q017_radar'/folder/original.name
                    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,target)
            return dest
        before_sha=subprocess.check_output(['git','-C',str(ROOT),'rev-parse',a.before+'^{commit}'],text=True).strip()
        comparison_before=baseline if before_sha==BASE else run_probe(export_revision(before_sha,'comparison-before'))
        if comparison_before['semantic']!=baseline['semantic']:raise RuntimeError('FAIL_SEMANTIC_DRIFT_DETECTED_IN_BEFORE_REVISION')
        if a.after:
            after=export_revision(a.after,'after')
        else:
            after=Path(td)/'after';shutil.copytree(ROOT,after,ignore=shutil.ignore_patterns('.git','__pycache__','results'))
        current = run_probe(after)
        if baseline['semantic'] != current['semantic']:
            raise RuntimeError('FAIL_SEMANTIC_DRIFT_DETECTED')
        tests = []
        for path in ('scripts/test_hengce_q017_resilience_v5.py', 'scripts/test_hengce_q017_observer_resilience_v1.py',
                     'scripts/test_hengce_q017_decision_lock.py', 'scripts/test_hengce_q017_adversarial_v4.py',
                     'scripts/test_hengce_dual_engine_display_hard_lock.py',
                     'tests/engineering/test_q017_operational_boundary.py', 'tests/engineering/test_q017_cleanup.py'):
            bootstrap = "import runpy,sys;sys.path.insert(0,'tests/engineering');import q017_cleanup_audit as a;a.deny_network();sys.path.insert(0,'scripts');p=sys.argv[1];sys.argv=[p];runpy.run_path(p,run_name='__main__')"
            p = subprocess.run([sys.executable, '-B', '-c', bootstrap, path], cwd=ROOT, capture_output=True, text=True, timeout=120)
            tests.append({'command': path, 'returncode': p.returncode, 'output': (p.stdout + p.stderr)[-6000:]})
            if p.returncode: raise RuntimeError('AUDIT_REGRESSION_FAILED:' + path + '\n' + tests[-1]['output'])
        report = {'status': 'PASS', 'baseline_commit': BASE, 'comparison_before_commit':before_sha,
                  'comparison_after':a.after or 'WORKING_TREE', 'normalizations': [],
                  'regressions_source':'Working checkout (CI checks out the exact after/head SHA)',
                  'comparison': 'Exact JSON and canonical serialized SHA-256; fixed original computation timestamp; full candidate ranking observed at function return',
                  'semantic_payload_sha256': sha(current['semantic']), 'fixtures': {}, 'regressions': tests}
        for day, value in current['semantic'].items():
            d = value['decision']
            report['fixtures'][day] = {'decision_sha256': d['decision_snapshot_sha256'], 'full_ranking_sha256': sha(value['full_ranking']),
                                      'full_ranking_count': len(value['full_ranking']), 'top3': [r['ticker'] for r in d['top3']],
                                      'formal_buy_count': value['formal_buy_count'], 'market_state': d['market_state'],
                                      'observation_sha256': d['observation_snapshot_sha256'], 'universe_sha256': d['universe_lock']['universe_sha256'],
                                      'fixture_raw_sha256': value['fixture_raw_sha256'], 'fail_closed': value['fail_closed']}
        perf = {'method': '5 batches of 20 deterministic guard validations per fixture; perf_counter; network disabled; same interpreter',
                'before': baseline['performance'], 'after': current['performance'],
                'workflow_retries': 'Unchanged; no online workflow executed', 'critical_0901_network_lane': 'Unchanged; no capture code modified',
                'artifact_size': 'Original observation and decision bytes unchanged; audit outputs are separate'}
        for name, value in [('EQUIVALENCE_TEST_REPORT.json', report), ('PERFORMANCE_BEFORE_AFTER.json', perf)]:
            (RESULTS / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        if a.report:
            a.report.parent.mkdir(parents=True,exist_ok=True)
            a.report.write_text(json.dumps({'equivalence':report,'performance':perf},ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'status': 'PASS', 'semantic_payload_sha256': report['semantic_payload_sha256'], 'regression_commands': len(tests)}))


if __name__ == '__main__': main()
