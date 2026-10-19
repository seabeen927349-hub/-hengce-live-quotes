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

FORMAL_SCHEMA_MIN = 3
SOX_1D_MAX = 0.0
SOX_5D_MAX = -0.03
DXY_5D_MIN = -0.005

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


def _f(x):
    try:
        return float(x)
    except Exception:
        return None


def _validate_frozen_gate(decision: dict) -> tuple[bool, str]:
    if int(decision.get('schema_version') or 0) < FORMAL_SCHEMA_MIN:
        return False, 'DECISION_REQUIRES_SCHEMA_V3'
    if decision.get('module') != 'Q017_SOX_ELECTRONICS_DECISION_LOCK':
        return False, 'DECISION_MODULE_NOT_FORMAL_LOCK'

    rules = decision.get('rules') or {}
    if _f(rules.get('sox_1d_max')) != SOX_1D_MAX:
        return False, 'Q017_GATE_DRIFT_SOX1D'
    if _f(rules.get('sox_5d_max')) != SOX_5D_MAX:
        return False, 'Q017_GATE_DRIFT_SOX5D'
    if _f(rules.get('dxy_5d_min')) != DXY_5D_MIN:
        return False, 'Q017_GATE_DRIFT_DXY5D'
    if rules.get('authority') != 'Q017_LOCK_20261018.json':
        return False, 'Q017_GATE_AUTHORITY_LOCK_MISSING'

    mg = decision.get('market_gate') or {}
    s1 = _f(mg.get('sox_1d'))
    s5 = _f(mg.get('sox_5d'))
    d5 = _f(mg.get('dxy_5d'))
    if s1 is None or s5 is None or d5 is None:
        return False, 'Q017_GATE_VALUES_MISSING'
    if mg.get('source_lock') != 'Q017_LOCK_20261018.json':
        return False, 'Q017_MARKET_GATE_SOURCE_LOCK_MISSING'

    expected = s1 <= SOX_1D_MAX and s5 <= SOX_5D_MAX and d5 >= DXY_5D_MIN
    if mg.get('gate_go') is not expected:
        return False, 'Q017_GATE_BOOLEAN_INCONSISTENT'
    if (decision.get('market_state') == 'GO') is not expected:
        return False, 'Q017_MARKET_STATE_INCONSISTENT_WITH_FROZEN_GATE'

    dxy_status = ((decision.get('data_status') or {}).get('dxy') or {})
    if dxy_status.get('status') != 'PASS':
        return False, 'DXY_DATA_STATUS_NOT_PASS'
    if _f(dxy_status.get('dxy_5d')) != d5:
        return False, 'DXY_VALUE_MISMATCH'

    for item in decision.get('top3') or []:
        if bool(item.get('qualified')) is not expected:
            return False, 'TOP3_QUALIFIED_FLAG_INCONSISTENT_WITH_FROZEN_GATE'
    return True, 'FROZEN_Q017_GATE_VALID'


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
        if int(payload.get('formal_buy_count') or 0) != 0:
            return False, 'GUARD_PLACEHOLDER_BUY_COUNT_MUST_BE_ZERO'
        return True, 'VALID_FAIL_CLOSED_PLACEHOLDER'

    if int(payload.get('schema_version') or 0) < FORMAL_SCHEMA_MIN:
        return False, 'FORMAL_Q017_REQUIRES_SCHEMA_V3'
    trade_date = str(payload.get('trade_date') or '')
    if len(trade_date) != 10:
        return False, 'TRADE_DATE_MISSING'
    p = decision_path_for(trade_date)
    if not p.exists():
        return False, 'NO_IMMUTABLE_0901_DECISION_SNAPSHOT'

    decision = read_json(p)
    gate_ok, gate_reason = _validate_frozen_gate(decision)
    if not gate_ok:
        return False, gate_reason

    decision_hash = decision.get('decision_snapshot_sha256')
    expected_hash = canonical_sha({k: v for k, v in decision.items() if k != 'decision_snapshot_sha256'})
    if not decision_hash or decision_hash != expected_hash:
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

    return True, 'VALID_LOCKED_Q017_AUTHORITY_SCHEMA_V3_FROZEN_GATE'


def quarantine_payload(rejected: dict, reason: str) -> dict:
    trade_date = str(rejected.get('trade_date') or now_tw().date().isoformat())
    rejected_top = []
    for x in rejected.get('top3') or []:
        if isinstance(x, dict) and x.get('ticker'):
            rejected_top.append(str(x['ticker']))
        elif isinstance(x, str):
            rejected_top.append(x)
    return {
        'schema_version': 3,
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
        'policy': 'NO_VALID_SCHEMA_V3_0901_DECISION_LOCK_NO_FORMAL_Q017_SIGNAL',
        'required_gate': {
            'sox_1d_max': SOX_1D_MAX,
            'sox_5d_max': SOX_5D_MAX,
            'dxy_5d_min': DXY_5D_MIN,
            'authority': 'Q017_LOCK_20261018.json',
        },
        'repair_note': 'Legacy, unlocked, old-schema, or gate-drifted Q017 output was quarantined automatically. It has zero capital authority.',
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
        'schema_version': 3,
        'module': 'Q017_AUTHORITY_GUARD_FAIL_CLOSED',
        'binding_status': 'DATA_PENDING',
        'market_state': 'DATA_PENDING',
        'authority': 'NO_FORMAL_SIGNAL',
        'formal_buy_count': 0,
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

    bad_schema2 = {
        'schema_version': 2,
        'module': 'Q017_SOX_ELECTRONICS_DECISION_LOCK',
        'binding_status': 'PASS',
        'market_state': 'GO',
        'trade_date': '2026-10-19',
        'top3': [],
    }
    ok2, reason2 = validate(bad_schema2)
    assert ok2 is False and reason2 == 'FORMAL_Q017_REQUIRES_SCHEMA_V3'

    repaired = quarantine_payload(bad_legacy, reason)
    assert repaired['formal_buy_count'] == 0
    assert repaired['top3'] == []
    assert repaired['authority'] == 'NO_FORMAL_SIGNAL'
    assert repaired['required_gate']['sox_5d_max'] == -0.03
    assert repaired['required_gate']['dxy_5d_min'] == -0.005

    print(json.dumps({
        'self_test': 'PASS',
        'legacy_radar_rejected': True,
        'schema_v2_formal_rejected': True,
        'frozen_gate_enforced': {'sox_1d_max': 0.0, 'sox_5d_max': -0.03, 'dxy_5d_min': -0.005},
        'fail_closed_buy_count': 0,
    }))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['check-and-repair', 'self-test'], required=True)
    args = ap.parse_args()
    return self_test() if args.mode == 'self-test' else check_and_repair()


if __name__ == '__main__':
    raise SystemExit(main())
