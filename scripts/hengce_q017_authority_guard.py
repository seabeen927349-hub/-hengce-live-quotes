#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Taipei')
ROOT = Path(__file__).resolve().parents[1]
RADAR = ROOT / 'hengce' / 'q017_radar'
LATEST = RADAR / 'latest.json'
DECISION_DIR = RADAR / 'decision'

ALLOWED_MODULES = {
    'Q017_SOX_ELECTRONICS_DECISION_LOCK',
    'Q017_SOX_ELECTRONICS_RADAR_LOCKED',
    'Q017_AUTHORITY_GUARD_FAIL_CLOSED',
}
FORBIDDEN_MODULES = {
    'Q017_SOX_ELECTRONICS_RADAR',
}


def now_tw() -> datetime:
    return datetime.now(TZ)


def canonical_sha(obj) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def atomic_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def decision_path_for(trade_date: str) -> Path:
    ymd = trade_date.replace('-', '')
    return DECISION_DIR / f'{ymd}_0901.json'


def validate(payload: dict) -> tuple[bool, str]:
    module = payload.get('module')
    if module in FORBIDDEN_MODULES:
        return False, 'LEGACY_RADAR_MODULE_FORBIDDEN'
    if module not in ALLOWED_MODULES:
        return False, f'UNKNOWN_OR_UNAUTHORIZED_MODULE:{module}'

    if module == 'Q017_AUTHORITY_GUARD_FAIL_CLOSED':
        if payload.get('binding_status') != 'DATA_PENDING':
            return False, 'GUARD_PLACEHOLDER_MUST_BE_DATA_PENDING'
        if payload.get('market_state') != 'DATA_PENDING':
            return False, 'GUARD_PLACEHOLDER_MARKET_STATE_MUST_BE_DATA_PENDING'
        if payload.get('top3') not in ([], None):
            return False, 'GUARD_PLACEHOLDER_TOP3_MUST_BE_EMPTY'
        if payload.get('authority') != 'NO_FORMAL_SIGNAL':
            return False, 'GUARD_PLACEHOLDER_MUST_HAVE_ZERO_AUTHORITY'
        return True, 'VALID_FAIL_CLOSED_PLACEHOLDER'

    if int(payload.get('schema_version') or 0) < 2:
        return False, 'FORMAL_Q017_REQUIRES_SCHEMA_V2'
    trade_date = str(payload.get('trade_date') or '')
    if len(trade_date) != 10:
        return False, 'TRADE_DATE_MISSING'
    p = decision_path_for(trade_date)
    if not p.exists():
        return False, 'NO_IMMUTABLE_0901_DECISION_SNAPSHOT'

    decision = read_json(p)
    decision_hash = decision.get('decision_snapshot_sha256')
    expected = canonical_sha({k: v for k, v in decision.items() if k != 'decision_snapshot_sha256'})
    if not decision_hash or decision_hash != expected:
        return False, 'DECISION_SNAPSHOT_HASH_INVALID'
    if payload.get('decision_snapshot_sha256') != decision_hash:
        return False, 'LATEST_NOT_BOUND_TO_DECISION_HASH'

    decision_top = [x.get('ticker') for x in decision.get('top3', [])]
    latest_top = [x.get('ticker') for x in payload.get('top3', [])]
    if latest_top != decision_top:
        return False, 'LATEST_TOP3_DIFFERS_FROM_LOCKED_DECISION'

    if module == 'Q017_SOX_ELECTRONICS_RADAR_LOCKED':
        monitor = payload.get('monitor') or {}
        if monitor.get('rerank_performed') is not False:
            return False, 'MONITOR_RERANK_FLAG_NOT_FALSE'
        if monitor.get('ranking_frozen') is not True:
            return False, 'MONITOR_RANKING_NOT_FROZEN'

    return True, 'VALID_LOCKED_Q017_AUTHORITY'


def quarantine_payload(rejected: dict, reason: str) -> dict:
    trade_date = str(rejected.get('trade_date') or now_tw().date().isoformat())
    rejected_top = []
    for x in rejected.get('top3') or []:
        if isinstance(x, dict) and x.get('ticker'):
            rejected_top.append(str(x['ticker']))
        elif isinstance(x, str):
            rejected_top.append(x)
    return {
        'schema_version': 2,
        'system': 'HENGCE',
        'module': 'Q017_AUTHORITY_GUARD_FAIL_CLOSED',
        'generated_at_taipei': now_tw().isoformat(),
        'trade_date': trade_date,
        'binding_status': 'DATA_PENDING',
        'market_state': 'DATA_PENDING',
        'authority': 'NO_FORMAL_SIGNAL',
        'top3': [],
        'formal_buy_count': 0,
        'reason': reason,
        'rejected_artifact': {
            'module': rejected.get('module'),
            'schema_version': rejected.get('schema_version'),
            'generated_at_taipei': rejected.get('generated_at_taipei'),
            'top3': rejected_top,
        },
        'policy': 'NO_VALID_0901_DECISION_LOCK_NO_FORMAL_Q017_SIGNAL',
        'repair_note': 'Legacy/unlocked radar output was quarantined automatically. Historical evidence is retained separately; it has zero capital authority.',
    }


def check_and_repair() -> int:
    if not LATEST.exists():
        print(json.dumps({'status': 'PASS', 'latest': 'ABSENT', 'authority': 'NO_FORMAL_SIGNAL'}))
        return 0
    payload = read_json(LATEST)
    ok, reason = validate(payload)
    if ok:
        print(json.dumps({'status': 'PASS', 'reason': reason, 'module': payload.get('module')}, ensure_ascii=False))
        return 0
    repaired = quarantine_payload(payload, reason)
    atomic_json(LATEST, repaired)
    print(json.dumps({'status': 'REPAIRED_FAIL_CLOSED', 'reason': reason, 'rejected_module': payload.get('module'), 'formal_buy_count': 0}, ensure_ascii=False))
    return 0


def self_test() -> int:
    good_guard = {
        'module': 'Q017_AUTHORITY_GUARD_FAIL_CLOSED',
        'binding_status': 'DATA_PENDING',
        'market_state': 'DATA_PENDING',
        'authority': 'NO_FORMAL_SIGNAL',
        'top3': [],
    }
    assert validate(good_guard)[0] is True
    bad_legacy = {
        'schema_version': 1,
        'module': 'Q017_SOX_ELECTRONICS_RADAR',
        'binding_status': 'PASS',
        'market_state': 'GO',
        'top3': [{'ticker': '7795'}, {'ticker': '2455'}, {'ticker': '2492'}],
    }
    ok, reason = validate(bad_legacy)
    assert ok is False and reason == 'LEGACY_RADAR_MODULE_FORBIDDEN'
    repaired = quarantine_payload(bad_legacy, reason)
    assert repaired['formal_buy_count'] == 0
    assert repaired['top3'] == []
    assert repaired['authority'] == 'NO_FORMAL_SIGNAL'
    print(json.dumps({'self_test': 'PASS', 'legacy_radar_rejected': True, 'fail_closed_buy_count': 0}))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['check-and-repair', 'self-test'], required=True)
    args = ap.parse_args()
    return self_test() if args.mode == 'self-test' else check_and_repair()


if __name__ == '__main__':
    raise SystemExit(main())
