#!/usr/bin/env python3
"""Read existing Git evidence only. Never imports models or generates signals."""
import argparse
import ast
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PIN = 'b975f1443d8c3b4360cddaf1d25d65054ab1d4ed'
OUT = Path(__file__).parent / 'evidence_inventory.json'
UNIVERSE = 'hengce/HENGCE_ELECTRONICS_ONLY_UNIVERSE_LOCK_v1_0_20261021.json'
E2_LOCK = 'hengce/E2_PROFIT_MAX_LOCK_v1_0_20261019.json'
E2_DISPLAY = 'hengce/E2_PROFIT_MAX_DISPLAY_EXECUTION_LOCK_v1_0_20261019.json'
CONTEXT = 'hengce/HENGCE_ELECTRONICS_LIVE_COVERAGE_CONTRACT_v1_0_20261022.json'


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'


class Evidence:
    def __init__(self, root=ROOT):
        self.root = root
        self.paths = subprocess.check_output(
            ['git', '-C', str(root), 'ls-tree', '-r', '--name-only', PIN], text=True).splitlines()
        self.consulted = {}

    def read(self, path):
        # Explicit evidence reads only; metadata listing is not holdout access.
        if re.search(r'holdout|sealed|user.?trade', path, re.I):
            raise ValueError('FORBIDDEN_EVIDENCE_READ: ' + path)
        raw = subprocess.check_output(['git', '-C', str(self.root), 'show', PIN + ':' + path])
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        self.consulted[path] = {'git_blob_sha': blob, 'sha256': hashlib.sha256(raw).hexdigest()}
        return raw.decode('utf-8-sig')

    def obj(self, path):
        return json.loads(self.read(path))


def timestamp_fields(obj, prefix=''):
    found = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = prefix + '/' + key
            if isinstance(value, str) and re.match(r'^\d{4}-\d{2}-\d{2}T', value):
                found.add(path)
            found.update(timestamp_fields(value, path))
    elif isinstance(obj, list):
        for value in obj:
            found.update(timestamp_fields(value, prefix + '/*'))
    return sorted(found)


def csv_coverage(text):
    reader = csv.DictReader(io.StringIO(text))
    fields = reader.fieldnames or []
    date = next((k for k in fields if k.lower() == 'date'), None)
    ticker = next((k for k in fields if k.lower() == 'ticker'), None)
    dates, counts, tickers, rows = set(), {}, set(), 0
    for row in reader:
        rows += 1
        if date and row.get(date):
            d = row[date]
            dates.add(d)
            counts[d] = counts.get(d, 0) + 1
        if ticker and row.get(ticker):
            tickers.add(row[ticker])
    return {'classification': 'PRESENT', 'fields': fields, 'rows': rows,
            'date_min': min(dates) if dates else None, 'date_max': max(dates) if dates else None,
            'observed_dates': sorted(dates), 'rows_by_date': counts,
            'unique_tickers': len(tickers) if ticker else None,
            'completeness': 'NOT_PROVEN_BY_ROW_COUNTS',
            'calendar_semantics': 'OBSERVED_ROWS_ONLY_NOT_AUTHORITATIVE_EXCHANGE_CALENDAR'}


def build(root=ROOT):
    ev = Evidence(root)
    # B01: commands and refs are evidence, not a declaration of reproducibility.
    workflows = {}
    for p in ev.paths:
        if p.startswith('.github/workflows/') and p.endswith(('.yml', '.yaml')):
            lines = ev.read(p).splitlines()
            workflows[p] = [{'line': n, 'text': line.strip()} for n, line in enumerate(lines, 1)
                            if re.search(r'uses:|runs-on:|python-version:|node-version:|pip install|npm |apt-get|curl |wget ', line)]
    imports = {}
    for p in ev.paths:
        if p.endswith('.py') and p.startswith(('scripts/', 'research/', 'tests/')):
            tree = ast.parse(ev.read(p), filename=p)
            modules = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules.update(x.name.split('.')[0] for x in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules.add(node.module.split('.')[0])
            imports[p] = sorted(modules)

    # B02/B04/B06: existing bytes and fields only, not recomputed rankings.
    qobs, qdec, e2, temporal = [], [], [], []
    patterns = [('hengce/q017_radar/observations/', qobs),
                ('hengce/q017_radar/decision/', qdec), ('hengce/e2_live/history/', e2)]
    for prefix, target in patterns:
        for p in ev.paths:
            if p.startswith(prefix) and p.endswith('.json'):
                obj = ev.obj(p)
                entry = {'path': p, 'schema_version': obj.get('schema_version'),
                         'trade_date': obj.get('trade_date', obj.get('signal_asof')),
                         'generated_at_taipei': obj.get('generated_at_taipei'),
                         'authority': obj.get('authority'), 'binding_status': obj.get('binding_status')}
                for key in ('observation_snapshot_sha256', 'decision_snapshot_sha256', 'rules',
                            'universe_lock', 'observation_lock', 'decision_lock', 'capital_authority_twd',
                            'broker_order_execution', 'market_state', 'action', 'locks'):
                    if key in obj:
                        entry[key] = obj[key]
                entry['lineage_fields_present'] = sorted(k for k in obj if k in (
                    'eligible_models', 'quotes', 'top3', 'top1', 'market_gate', 'local_gate',
                    'macro_gate', 'data_status', 'strict', 'extension_shadow', 'paper_position'))
                entry['lineage_counts'] = {k: len(obj[k]) for k in ('eligible_models', 'quotes', 'top3') if k in obj}
                entry['complete_rejected_ranked_candidate_ledger'] = 'ABSENT_IN_REVIEWED_ARTIFACT'
                target.append(entry)
                temporal.append({'path': p, 'timestamp_field_paths': timestamp_fields(obj),
                                 'publication_time': 'NOT_PROVEN', 'first_seen_time': 'NOT_PROVEN',
                                 'revision_history': 'GIT_ARTIFACT_HISTORY_NOT_PROVIDER_REVISION_HISTORY'})

    universe, lock, display, context = (ev.obj(p) for p in (UNIVERSE, E2_LOCK, E2_DISPLAY, CONTEXT))
    rolling_path = 'shadow/full_market_latest.json'
    rolling = ev.obj(rolling_path)
    quote_rows = rolling['quotes']
    current_quote_evidence = {
        'path': rolling_path, 'classification': 'PRESENT_CURRENT_CONTEXT_ONLY',
        'generated_at_taipei': rolling['generated_at_taipei'], 'authority': rolling['authority'],
        'row_count': len(quote_rows),
        'fields_with_nonnull_row_counts': {k: sum(q.get(k) is not None for q in quote_rows)
            for k in ('best_bid', 'best_ask', 'volume_lots', 'trade_time', 'fetched_at_taipei')},
        'quote_fresh_count': rolling['quote_fresh_count'], 'trade_fresh_count': rolling['trade_fresh_count'],
        'executable_volume': 'NOT_PROVEN_BY_CUMULATIVE_VOLUME',
        'historical_depth_queue_latency_fill_panel': 'NOT_PRESENT_IN_THIS_SNAPSHOT'}
    smoke_path = 'receipts/HENGCE_FULL_MARKET_INTRADAY_SHADOW_SMOKE_RECEIPT_20261010.json'
    smoke = ev.obj(smoke_path)
    q012_path = 'research/q012/HENGCE_Q012_FEATURE_INTEGRITY_CONTRACT_20261017.json'
    q012 = ev.obj(q012_path)
    # EOD flags are copied, never inferred from a date, row count or other legs.
    eod = []
    for p in ev.paths:
        if re.fullmatch(r'eod/\d{8}/status.json', p):
            obj = ev.obj(p)
            keys = ('target_date', 'price_status', 'price_date', 'price_rows', 'institutional_status',
                    'institutional_date', 'institutional_rows', 'margin_status', 'margin_date',
                    'margin_rows', 'formal_complete_day', 'three_leg_complete', 'downstream_ready',
                    'completed_at_taipei', 'last_run_at_taipei', 'status')
            eod.append({'path': p, **{k: obj.get(k) for k in keys},
                        'missing_flag_semantics': 'UNKNOWN_NOT_IMPLICIT_TRUE',
                        'leg_files': [q for q in ev.paths if q.startswith(p.rsplit('/', 1)[0] + '/') and q.endswith('.csv')]})
            temporal.append({'path': p, 'timestamp_field_paths': timestamp_fields(obj),
                             'publication_time': 'NOT_PROVEN', 'first_seen_time': 'NOT_PROVEN',
                             'revision_history': 'GIT_ARTIFACT_HISTORY_NOT_PROVIDER_REVISION_HISTORY'})
    csvs = [p for p in ev.paths if (
        p.startswith('hengce/q017_radar/data/') and p.endswith('.csv')) or re.fullmatch(
        r'research/e2_profit_max/membership/twse_electronics_membership_\d{4}\.csv', p)]
    coverage = {p: csv_coverage(ev.read(p)) for p in csvs}

    source = 'scripts/hengce_q017_observation_lock_v5.py'
    qsource = ev.read(source)
    evidence_paths = lambda entries: [x['path'] for x in entries]
    baselines = {
        'Q017': {'classification': 'PARTIAL', 'formula_schema_sources': [source],
                 'existing_observations': evidence_paths(qobs), 'existing_expected_outputs': evidence_paths(qdec),
                 'universe': 'TWSE_LISTED_ELECTRONICS_ONLY',
                 'ranking': 'score DESC; existing Python stable-sort tie order preserved',
                 'entry_exit': '09:01 observation; research_hold_days=10 is not a fill contract',
                 'timestamp_semantics': 'capture time is causal; generated time may be later',
                 'data_cutoffs': [{'path': x['path'], 'membership_date': x['universe_lock'].get('membership_date')}
                                  for x in qobs],
                 'cost_capital': 'NO_NEW_CAPITAL_AUTHORITY; complete cost/fill model not proven',
                 'full_ranking_numerical_baseline': 'EXISTING_ENGINEERING_REPLAY_ONLY_NO_NEW_REGENERATION',
                 'formula_source_contains_frozen_score': 'beta*(1+25*max(-residual,0))' in qsource},
        'E2': {'classification': 'PARTIAL', 'lock_source': E2_LOCK, 'frozen_lock': lock,
               'execution_contract_source': E2_DISPLAY, 'execution_contract': display['paper_state'],
               'existing_expected_outputs': evidence_paths(e2),
               'data_cutoffs': [x['trade_date'] for x in e2],
               'timestamp_semantics': 'signal_asof is event date; generated_at is computation time, not publication',
               'ranking': 'separate Top1 score; full historical candidate ledger not proven',
               'capital_authority_twd': 0, 'broker_execution': False},
        'M1': {'classification': 'PARTIAL', 'authority_source': UNIVERSE,
               'universe': universe['engines']['M1']['required_universe'],
               'authority': 'RESEARCH_SHADOW_ONLY', 'capital_authority': 0,
               'formula_version': None, 'data_cutoff': None, 'ranking_rule': None,
               'entry_exit': None, 'cost_assumptions': None,
               'numerical_baseline': 'ABSENT_IN_REVIEWED_EVIDENCE', 'expected_outputs': [],
               'gap': 'No standalone M1 formula, runner and numerical output identified. Electronics_m1 is a market return field, not M1 engine evidence. Do not proxy M1 with E2 or full-market shadow.',
               'next_evidence': 'Provide pre-existing authentic M1 runner/version/output and input hashes; no reconstruction authorized.'},
        'LEGACY_HENGCE': {'classification': 'NOT_APPLICABLE', 'scope': 'CURRENT_FORMAL_BASELINE',
                          'reason': 'Legacy is revoked from formal selection; not a substitute for Q017/E2/M1.',
                          'separate_legacy_numerical_manifest': 'ABSENT_IN_REVIEWED_EVIDENCE'}
    }
    gaps = {'calendar_security_master': 'ABSENT_IN_REVIEWED_SOURCES',
            'suspension_limit_status': 'NO_COMPLETE_EFFECTIVE_DATED_PANEL_PROVEN',
            'corporate_action_vintages': 'ABSENT_IN_REVIEWED_SOURCES',
            'label_tail_coverage': 'NOT_EVALUATED_NO_LABEL_GENERATION_AUTHORIZED'}
    return {
        'schema_version': 1, 'mode': 'READ_ONLY_RESEARCH_EVIDENCE', 'source_commit': PIN,
        'baseline_runtime_manifest': 'requirements-replay.txt',
        'hard_locks': {'phase2_authorized': False, 'B10': 'BLOCKED_PENDING_EXPLICIT_HUMAN_AUTHORIZATION',
                       'PROMOTE_TO_PRODUCTION': 'FORBIDDEN', 'capital_authority': 0,
                       'broker_execution': False, 'historical_signals_regenerated': False,
                       'holdout_accessed': False, 'user_trades_are_model_evidence': False},
        'B01': {'classification': 'PARTIAL', 'workflow_dependency_evidence': workflows,
                'static_python_imports': imports, 'scope': 'All tracked workflows and Python sources at source_commit; dynamic imports, embedded payload contents and external bundle dependencies not proven.',
                'unfrozen': ['runner image digest', 'OS packages', 'tzdata', 'Python patch version',
                             'wheel hashes', 'production floating dependencies', 'Node/binary supply chain']},
        'B02': {'classification': 'PARTIAL', 'baselines': baselines,
                'output_hash_semantics': 'source_index SHA256 is raw bytes; embedded decision hashes use their original canonicalization'},
        'B03': {'classification': 'PARTIAL', 'csv_datasets': coverage, 'eod_days': eod,
                'formal_complete_days_explicit_true': [x['target_date'] for x in eod if x['formal_complete_day'] is True],
                'evidence_gaps': gaps, 'market_history_downloaded': False},
        'B04': {'classification': 'PARTIAL', 'artifacts': temporal,
                'irrecoverable_retrospectively_without_original_provider_logs':
                ['first-seen', 'publication time', 'overwritten upstream revisions'],
                'prospective_remedy': 'Capture original provider event/publication/fetch/first-seen times, revision ID and raw content hash separately; unknown stays null.'},
        'B05': {'classification': 'PARTIAL',
                'authentic_0901_observations': evidence_paths(qobs),
                'DAILY_NEXT_OPEN_RESEARCH': {'status': 'NOT_AUTHORIZED',
                    'intraday_0903_0905_required': False,
                    'gates': ['coverage', 'PIT', 'costs', 'next-open executability', 'governance', 'B10']},
                'INTRADAY_TIMING_RESEARCH': {'status': 'BLOCKED_BY_EVIDENCE',
                    'historical_0903_0905': 'ABSENT_IN_REVIEWED_SOURCES',
                    'bid_ask_depth_queue_latency_fill_volume_panel': 'NOT_PROVEN',
                    'daily_ohlc_substitution': 'FORBIDDEN'},
                'current_quote_context_contract': {'path': CONTEXT, 'authority': context['authority']},
                'current_quote_snapshot': current_quote_evidence,
                'existing_transport_smoke': {'path': smoke_path, 'market_state': smoke['market_state'],
                    'result': smoke['result'], 'historical_fill_evidence': False},
                'existing_microstructure_contract': {'path': q012_path, 'rules': q012['rules'],
                    'limitations': q012['limitations'], 'raw_event_panel_proven_by_contract': False},
                'current_quotes_are_historical_executability': False},
        'B06': {'classification': 'PARTIAL', 'Q017_observations': qobs, 'Q017_decisions': qdec,
                'E2_states': e2, 'M1': 'NUMERICAL_LINEAGE_ABSENT_IN_REVIEWED_EVIDENCE',
                'candidate_reconstruction': 'FORBIDDEN',
                'prospective_contract': 'governance.json#/prospective_lineage'},
        'source_index': dict(sorted(ev.consulted.items()))
    }


def validate_requirements(text):
    pins = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if not re.fullmatch(r'[A-Za-z0-9_.-]+==\d+(?:\.\d+)+(?:[a-z0-9.]*)?', line):
            raise ValueError('FLOATING_OR_UNSUPPORTED_RESEARCH_DEPENDENCY: ' + line)
        pins.append(line.lower())
    names = [p.split('==')[0].replace('_', '-') for p in pins]
    expected = {'requests', 'openpyxl', 'pyyaml', 'certifi', 'charset-normalizer', 'idna', 'urllib3', 'et-xmlfile'}
    if len(names) != len(set(names)) or set(names) != expected:
        raise ValueError('REPLAY_DEPENDENCY_SET_MUST_HAVE_EIGHT_UNIQUE_PINS')
    return pins


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    validate_requirements((OUT.parent / 'requirements-replay.txt').read_text())
    text = encode(build())
    if args.check:
        if OUT.read_text(encoding='utf-8') != text:
            raise SystemExit('STALE_OR_CHANGED_EVIDENCE_INVENTORY')
        print('PASS: pinned evidence, source hashes and dependency pins')
    else:
        OUT.write_text(text, encoding='utf-8')
        print('WROTE research-only evidence inventory')


if __name__ == '__main__':
    main()
