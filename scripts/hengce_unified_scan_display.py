#!/usr/bin/env python3
"""Render one HENGCE result only from a complete, current, committed bundle."""
from __future__ import annotations
import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from hengce_unified_contracts import atomic, strict_loads, digest, aware, geometry, ZERO_AUTHORITY
from hengce_unified_runner import locations, NAMES

TZ = ZoneInfo('Asia/Taipei')
ROOT, DEFAULT_DIR = locations()
ACTION = DEFAULT_DIR / NAMES['action']
BASE = DEFAULT_DIR / NAMES['base']
OUT = ROOT / 'hengce/unified/latest.json'


def load(path):
    try:
        return strict_loads(Path(path).read_bytes())
    except (OSError, ValueError):
        return None


def parse_now(value):
    return aware(value).astimezone(TZ) if value else datetime.now(TZ)


def build(now, action=None, base=None, receipt=None):
    common = {'schema_version': 2, 'system': 'HENGCE', 'module': 'HENGCE_UNIFIED_SCAN_DISPLAY',
              **ZERO_AUTHORITY, 'generated_at_taipei': now.isoformat(), 'architecture': 'SINGLE_HENGCE',
              'single_user_facing_output': True, 'q017_internal_candidate_source': True,
              'q017_separate_ranking_displayed': False, 'e2_separate_engine_displayed': False,
              'legacy_v3_separate_ranking_displayed': False, 'score_fusion': False,
              'binding_status': 'FAIL_CLOSED', 'status': 'DATA_PENDING', 'rows': [],
              'authority': 'NO_FORMAL_HENGCE_OUTPUT', 'candidate_count': 0}
    try:
        if not all(isinstance(x, dict) for x in (action, base, receipt)):
            raise ValueError('INCOMPLETE_PUBLICATION')
        if (receipt.get('schema_version') != 3 or receipt.get('binding_status') != 'PASS' or
            action.get('schema_version') != 2 or action.get('binding_status') != 'PASS' or
            action.get('module') != 'HENGCE_UNIFIED_INTRADAY_ACTION_BOARD' or
            base.get('schema_version') != 2 or base.get('module') != 'HENGCE_UNIFIED_CANDIDATE_ADAPTER'):
            raise ValueError('UNSUPPORTED_OR_UNBOUND_PUBLICATION')
        for obj in (action, base, receipt):
            if obj.get('system') != 'HENGCE' or any(obj.get(k) != v or type(obj.get(k)) is not type(v) for k, v in ZERO_AUTHORITY.items()):
                raise ValueError('AUTHORITY_ENVELOPE_MISMATCH')
        transaction = receipt.get('transaction_id')
        if not transaction or any(x.get('transaction_id') != transaction for x in (action, base)):
            raise ValueError('TRANSACTION_MISMATCH')
        if (receipt.get('base_hash') != digest(base) or receipt.get('action_hash') != digest(action)
            or action.get('base_hash') != digest(base)):
            raise ValueError('PUBLICATION_HASH_MISMATCH')
        if action.get('BaseRunId') != base.get('run_id'):
            raise ValueError('SOURCE_RUN_MISMATCH')
        for obj in (action, receipt):
            if obj.get('trade_date') != now.date().isoformat():
                raise ValueError('STALE_ACTION_SESSION')
            age = (now - aware(obj.get('generated_at'))).total_seconds()
            if not -30 <= age <= 480:
                raise ValueError('STALE_ACTION_PUBLICATION')
        age = (now - aware(action.get('LiveGeneratedAt'))).total_seconds()
        if not -30 <= age <= 480:
            raise ValueError('STALE_SOURCE_SNAPSHOT')
        source_rows = {r['Ticker']: r for r in base['rows']}
        rows = action['rows']
        if not isinstance(rows, list) or len(source_rows) != len(base['rows']) or len(rows) != len(source_rows):
            raise ValueError('INCONSISTENT_CANDIDATE_SET')
        seen = set()
        for row in rows:
            name = row['Ticker']; src = source_rows.get(name)
            if name in seen or src is None:
                raise ValueError('INCONSISTENT_TICKER')
            seen.add(name)
            for key in ('SourceProvenance', 'LegacyScore', 'Q017Score', 'Q017Rank', 'LegacyEvidence', 'Q017Evidence', 'FormalCandidate'):
                if row.get(key) != src.get(key):
                    raise ValueError('SOURCE_EVIDENCE_MISMATCH')
            if row.get('FinalAction') not in {'ABSTAIN', 'REVIEW_ENTRY', 'REVIEW_PROBE', 'EXIT_ALL'}:
                raise ValueError('UNKNOWN_ACTION')
            if src.get('SourceProvenance') == 'Q017' and row.get('FinalAction') != 'ABSTAIN':
                raise ValueError('Q017_ONLY_ACTION_AUTHORITY_VIOLATION')
            if row.get('FinalAction') in {'REVIEW_ENTRY', 'REVIEW_PROBE'} and (row.get('GeometryStatus') != 'AVAILABLE' or geometry(src) is None or src.get('FormalCandidate') is not True or src.get('SourceProvenance') == 'Q017'):
                raise ValueError('GEOMETRY_AUTHORITY_VIOLATION')
        common.update(status='PASS', binding_status='PASS', authority='UNIFIED_HENGCE_ACTION_BOARD',
                      transaction_id=transaction, candidate_count=len(rows), rows=rows,
                      q017_contract_status=base.get('q017_contract_status'),
                      source_provenance_counts=base.get('source_provenance_counts'),
                      MarketContextState=action.get('MarketContextState'),
                      NewCapitalPolicy=action.get('NewCapitalPolicy'), LiveSnapshotId=action.get('LiveSnapshotId'))
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        common['reason'] = str(exc)
    return common


def self_test():
    now = parse_now('2026-10-23T10:00:00+08:00')
    assert build(now)['binding_status'] == 'FAIL_CLOSED'
    assert build(now, {'binding_status': 'PASS'})['rows'] == []
    print('SELF_TEST_PASS: incomplete publication cannot acquire display authority')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--now'); parser.add_argument('--action'); parser.add_argument('--base'); parser.add_argument('--receipt')
    parser.add_argument('--no-write', action='store_true'); parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test(); return 0
    now = parse_now(args.now)
    out = build(now, load(args.action or ACTION), load(args.base or BASE),
                load(args.receipt or DEFAULT_DIR / NAMES['receipt']))
    if not args.no_write:
        atomic(OUT, out)
    print(json.dumps(out, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if out['binding_status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
