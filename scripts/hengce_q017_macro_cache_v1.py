#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

import hengce_daily_command_center as core
import hengce_q017_decision_lock as legacy

ROOT = core.ROOT
DATA = core.DATA
CACHE_DIR = DATA / 'macro_cache'
CACHE_HISTORY = CACHE_DIR / 'history'
CACHE_LATEST = CACHE_DIR / 'latest.json'
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_HISTORY.mkdir(parents=True, exist_ok=True)

SCHEMA_VERSION = 1


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    if not path.exists():
        raise RuntimeError(f'MACRO_CACHE_SOURCE_FILE_MISSING:{path}')
    return _sha256_bytes(path.read_bytes())


def canonical_sha(obj) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return _sha256_bytes(raw)


def cache_path(trade_date) -> Path:
    return CACHE_DIR / f'{trade_date.strftime("%Y%m%d")}.json'


def _parse_date(value: str):
    return datetime.strptime(str(value), '%Y-%m-%d').date()


def _validate_causal_session(label: str, session: str, trade_date):
    d = _parse_date(session)
    if d >= trade_date:
        raise RuntimeError(f'{label}_SESSION_NOT_CAUSAL:{session}>={trade_date.isoformat()}')
    return d


def validate_cache(payload, trade_date=None, verify_files=True):
    if not isinstance(payload, dict):
        raise RuntimeError('MACRO_CACHE_NOT_OBJECT')
    if payload.get('schema_version') != SCHEMA_VERSION:
        raise RuntimeError('MACRO_CACHE_SCHEMA_MISMATCH')
    if payload.get('status') != 'PASS':
        raise RuntimeError('MACRO_CACHE_STATUS_NOT_PASS')
    td = _parse_date(payload.get('trade_date'))
    if trade_date is not None and td != trade_date:
        raise RuntimeError(f'MACRO_CACHE_TRADE_DATE_MISMATCH:{td}!={trade_date}')

    sox = payload.get('sox_status') or {}
    sf = payload.get('sox_features') or {}
    dxy = payload.get('dxy_status') or {}
    if sox.get('status') != 'PASS':
        raise RuntimeError('MACRO_CACHE_SOX_NOT_PASS')
    if dxy.get('status') != 'PASS':
        raise RuntimeError('MACRO_CACHE_DXY_NOT_PASS')
    _validate_causal_session('SOX', sox.get('latest_session'), td)
    _validate_causal_session('DXY', dxy.get('latest_session'), td)
    if sf.get('sox_1d') is None or sf.get('sox_5d') is None:
        raise RuntimeError('MACRO_CACHE_SOX_FEATURES_MISSING')
    if dxy.get('dxy_5d') is None:
        raise RuntimeError('MACRO_CACHE_DXY_5D_MISSING')

    expected = payload.get('cache_sha256')
    body = {k: v for k, v in payload.items() if k != 'cache_sha256'}
    actual = canonical_sha(body)
    if not expected or expected != actual:
        raise RuntimeError('MACRO_CACHE_HASH_MISMATCH')

    if verify_files:
        files = payload.get('files') or {}
        if files.get('sox_csv_sha256') != _sha256_file(core.SOX_CSV):
            raise RuntimeError('MACRO_CACHE_SOX_CSV_HASH_MISMATCH')
        if files.get('dxy_csv_sha256') != _sha256_file(legacy.DXY_CSV):
            raise RuntimeError('MACRO_CACHE_DXY_CSV_HASH_MISMATCH')
    return payload


def load_valid_cache(trade_date, verify_files=True):
    p = cache_path(trade_date)
    if not p.exists():
        raise RuntimeError(f'MACRO_CACHE_DATED_FILE_MISSING:{p.name}')
    payload = json.loads(p.read_text(encoding='utf-8'))
    return validate_cache(payload, trade_date=trade_date, verify_files=verify_files)


def build_cache(trade_date=None):
    trade_date = trade_date or core.now_tw().date()
    if trade_date.weekday() >= 5:
        return {
            'schema_version': SCHEMA_VERSION,
            'system': 'HENGCE',
            'module': 'Q017_MORNING_MACRO_CACHE',
            'trade_date': trade_date.isoformat(),
            'generated_at_taipei': core.now_tw().isoformat(),
            'status': 'SKIP_WEEKEND',
        }

    sox_status = core.refresh_sox(trade_date)
    sox_features = core.sox_features(trade_date)
    dxy_status = legacy.refresh_dxy(trade_date)

    _validate_causal_session('SOX', sox_status.get('latest_session'), trade_date)
    _validate_causal_session('DXY', dxy_status.get('latest_session'), trade_date)
    if sox_features.get('sox_1d') is None or sox_features.get('sox_5d') is None:
        raise RuntimeError('MACRO_CACHE_SOX_FEATURES_MISSING_AFTER_REFRESH')
    if dxy_status.get('dxy_5d') is None:
        raise RuntimeError('MACRO_CACHE_DXY_5D_MISSING_AFTER_REFRESH')

    generated = core.now_tw()
    payload = {
        'schema_version': SCHEMA_VERSION,
        'system': 'HENGCE',
        'module': 'Q017_MORNING_MACRO_CACHE',
        'trade_date': trade_date.isoformat(),
        'generated_at_taipei': generated.isoformat(),
        'status': 'PASS',
        'authority': 'Q017_PREMARKET_INPUT_CACHE_ONLY_NOT_MARKET_OBSERVATION',
        'causal_policy': 'SOX_AND_DXY_COMPLETED_SESSIONS_STRICTLY_BEFORE_TAIWAN_TRADE_DATE',
        'sox_status': sox_status,
        'sox_features': sox_features,
        'dxy_status': dxy_status,
        'files': {
            'sox_csv': str(core.SOX_CSV.relative_to(ROOT)),
            'sox_csv_sha256': _sha256_file(core.SOX_CSV),
            'dxy_csv': str(legacy.DXY_CSV.relative_to(ROOT)),
            'dxy_csv_sha256': _sha256_file(legacy.DXY_CSV),
        },
        'observation_policy': {
            'contains_0901_quotes': False,
            'may_be_prepared_before_market_open': True,
            'cannot_substitute_for_q017_0901_observation': True,
        },
    }
    payload['cache_sha256'] = canonical_sha(payload)
    validate_cache(payload, trade_date=trade_date, verify_files=True)

    dated = cache_path(trade_date)
    core.atomic_json(dated, payload)
    core.atomic_json(CACHE_LATEST, payload)
    stamp = generated.strftime('%Y%m%dT%H%M%S')
    core.atomic_json(CACHE_HISTORY / f'{stamp}.json', payload)
    return payload


def self_test():
    td = datetime(2026, 10, 21).date()
    synthetic = {
        'schema_version': SCHEMA_VERSION,
        'system': 'HENGCE',
        'module': 'Q017_MORNING_MACRO_CACHE',
        'trade_date': td.isoformat(),
        'generated_at_taipei': '2026-10-21T06:37:00+08:00',
        'status': 'PASS',
        'authority': 'Q017_PREMARKET_INPUT_CACHE_ONLY_NOT_MARKET_OBSERVATION',
        'causal_policy': 'SOX_AND_DXY_COMPLETED_SESSIONS_STRICTLY_BEFORE_TAIWAN_TRADE_DATE',
        'sox_status': {'status': 'PASS', 'latest_session': '2026-10-20'},
        'sox_features': {'sox_1d': -0.01, 'sox_5d': -0.04},
        'dxy_status': {'status': 'PASS', 'latest_session': '2026-10-20', 'dxy_5d': 0.001},
        'files': {'sox_csv': 'x', 'sox_csv_sha256': 'a', 'dxy_csv': 'y', 'dxy_csv_sha256': 'b'},
        'observation_policy': {'contains_0901_quotes': False, 'may_be_prepared_before_market_open': True, 'cannot_substitute_for_q017_0901_observation': True},
    }
    synthetic['cache_sha256'] = canonical_sha(synthetic)
    validate_cache(synthetic, trade_date=td, verify_files=False)
    bad = json.loads(json.dumps(synthetic))
    bad['dxy_status']['latest_session'] = td.isoformat()
    bad['cache_sha256'] = canonical_sha({k: v for k, v in bad.items() if k != 'cache_sha256'})
    try:
        validate_cache(bad, trade_date=td, verify_files=False)
        raise AssertionError('same-day DXY session must fail causal validation')
    except RuntimeError as exc:
        assert 'NOT_CAUSAL' in str(exc)
    print(json.dumps({
        'self_test': 'PASS',
        'schema_version': SCHEMA_VERSION,
        'trade_date_bound': True,
        'sox_dxy_completed_session_causality': True,
        'source_file_sha256_bound': True,
        'cannot_substitute_for_0901_observation': True,
    }, ensure_ascii=False))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['refresh', 'validate', 'self-test'], required=True)
    ap.add_argument('--date')
    args = ap.parse_args()
    trade_date = datetime.strptime(args.date, '%Y-%m-%d').date() if args.date else core.now_tw().date()
    if args.mode == 'self-test':
        return self_test()
    if args.mode == 'refresh':
        out = build_cache(trade_date)
    else:
        out = load_valid_cache(trade_date, verify_files=True)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
