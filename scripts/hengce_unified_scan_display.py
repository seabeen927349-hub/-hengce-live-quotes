#!/usr/bin/env python3
"""Single user-facing HENGCE scan display.

This module never renders Q017 or E2 as competing engines. It consumes the
unified HENGCE candidate/action artifacts and fails closed when they are absent.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Taipei')
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / 'work_output' / 'intraday_action_board'
ACTION = DEFAULT_DIR / 'HENGCE_INTRADAY_ACTION_BOARD.json'
BASE = DEFAULT_DIR / 'HENGCE_UNIFIED_CANDIDATE_BASE.json'
OUT = ROOT / 'hengce' / 'unified' / 'latest.json'


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def atomic(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def parse_now(value: str | None):
    if not value:
        return datetime.now(TZ)
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def build(now: datetime, action=None, base=None):
    action = action if isinstance(action, dict) else None
    base = base if isinstance(base, dict) else None

    action_ok = bool(
        action
        and action.get('system') == 'HENGCE'
        and action.get('module') == 'HENGCE_UNIFIED_INTRADAY_ACTION_BOARD'
        and action.get('binding_status') == 'PASS'
        and isinstance(action.get('rows'), list)
    )
    base_ok = bool(
        base
        and base.get('system') == 'HENGCE'
        and base.get('module') == 'HENGCE_UNIFIED_CANDIDATE_ADAPTER'
        and isinstance(base.get('rows'), list)
    )

    common = {
        'schema_version': 1,
        'system': 'HENGCE',
        'module': 'HENGCE_UNIFIED_SCAN_DISPLAY',
        'generated_at_taipei': now.isoformat(),
        'architecture': 'SINGLE_HENGCE',
        'single_user_facing_output': True,
        'q017_internal_candidate_source': True,
        'q017_separate_ranking_displayed': False,
        'e2_separate_engine_displayed': False,
        'score_fusion': False,
        'candidate_union_policy': 'UNION_DEDUP_BY_TICKER_NO_SCORE_FUSION',
        'legacy_v3_separate_ranking_displayed': False,
    }

    if action_ok:
        rows = action.get('rows') or []
        common.update({
            'status': 'PASS',
            'binding_status': 'PASS',
            'authority': 'UNIFIED_HENGCE_ACTION_BOARD',
            'candidate_count': len(rows),
            'source_provenance_counts': action.get('source_provenance_counts'),
            'q017_contract_status': action.get('q017_contract_status'),
            'MarketContextState': action.get('MarketContextState'),
            'NewCapitalPolicy': action.get('NewCapitalPolicy'),
            'LiveSnapshotId': action.get('LiveSnapshotId'),
            'rows': rows,
            'display_policy': 'ONE_HENGCE_TABLE; Q017_IS_PROVENANCE_NOT_A_SEPARATE_ENGINE',
        })
        return common

    if base_ok:
        candidates = []
        for row in base.get('rows') or []:
            candidates.append({
                'Ticker': row.get('Ticker'),
                'Name': row.get('Name') or row.get('name'),
                'SourceProvenance': row.get('SourceProvenance'),
                'LegacyScore': row.get('LegacyScore'),
                'Q017Score': row.get('Q017Score'),
                'Q017Rank': row.get('Q017Rank'),
                'FormalCandidate': row.get('FormalCandidate'),
                'GeometryStatus': row.get('GeometryStatus'),
                'FinalAction': 'ABSTAIN',
                'ExecutionEligibility': 'FAIL_CLOSED_ACTION_BOARD_UNAVAILABLE',
            })
        common.update({
            'status': 'DATA_PENDING',
            'binding_status': 'FAIL_CLOSED',
            'authority': 'NO_FORMAL_ACTION_BOARD',
            'reason': 'UNIFIED_CANDIDATE_SET_EXISTS_BUT_ACTION_BOARD_NOT_BOUND',
            'candidate_count': len(candidates),
            'source_provenance_counts': base.get('source_provenance_counts'),
            'q017_contract_status': base.get('q017_contract_status'),
            'q017_contract_errors': base.get('q017_contract_errors'),
            'rows': candidates,
            'display_policy': 'ONE_HENGCE_TABLE_FAIL_CLOSED; NO_SEPARATE_ENGINE_FALLBACK',
        })
        return common

    common.update({
        'status': 'DATA_PENDING',
        'binding_status': 'FAIL_CLOSED',
        'authority': 'NO_FORMAL_HENGCE_OUTPUT',
        'reason': 'UNIFIED_CANDIDATE_AND_ACTION_ARTIFACTS_UNAVAILABLE',
        'candidate_count': 0,
        'source_provenance_counts': {'LEGACY': 0, 'Q017': 0, 'BOTH': 0},
        'q017_contract_status': 'UNAVAILABLE',
        'rows': [],
        'display_policy': 'ONE_HENGCE_OUTPUT_ONLY; NO_DUAL_ENGINE_FALLBACK',
    })
    return common


def self_test():
    now = datetime.fromisoformat('2026-10-23T10:00:00+08:00')
    base = {
        'system':'HENGCE','module':'HENGCE_UNIFIED_CANDIDATE_ADAPTER',
        'q017_contract_status':'PASS','source_provenance_counts':{'LEGACY':0,'Q017':1,'BOTH':0},
        'rows':[{'Ticker':'3008','Name':'大立光','SourceProvenance':'Q017','LegacyScore':None,'Q017Score':1.5,'Q017Rank':1,'FormalCandidate':True,'GeometryStatus':'UNAVAILABLE'}],
    }
    pending = build(now, None, base)
    assert pending['architecture'] == 'SINGLE_HENGCE'
    assert pending['binding_status'] == 'FAIL_CLOSED'
    assert pending['rows'][0]['FinalAction'] == 'ABSTAIN'
    assert 'q017' not in pending and 'e2' not in pending

    action = {
        'system':'HENGCE','module':'HENGCE_UNIFIED_INTRADAY_ACTION_BOARD','binding_status':'PASS',
        'q017_contract_status':'PASS','source_provenance_counts':{'LEGACY':1,'Q017':0,'BOTH':1},
        'MarketContextState':'NORMAL','NewCapitalPolicy':'NORMAL','LiveSnapshotId':'S1',
        'rows':[{'Ticker':'2330','SourceProvenance':'BOTH','FinalAction':'REVIEW_ENTRY'}],
    }
    passed = build(now, action, base)
    assert passed['status'] == 'PASS' and passed['rows'][0]['SourceProvenance'] == 'BOTH'
    assert passed['q017_separate_ranking_displayed'] is False
    assert passed['e2_separate_engine_displayed'] is False
    print('SELF_TEST_PASS: single HENGCE display only')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--now')
    ap.add_argument('--action')
    ap.add_argument('--base')
    ap.add_argument('--no-write', action='store_true')
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()
    if args.self_test:
        self_test(); return 0
    now = parse_now(args.now)
    action_path = Path(args.action) if args.action else ACTION
    base_path = Path(args.base) if args.base else BASE
    out = build(now, load(action_path), load(base_path))
    if not args.no_write:
        atomic(OUT, out)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get('binding_status') == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
