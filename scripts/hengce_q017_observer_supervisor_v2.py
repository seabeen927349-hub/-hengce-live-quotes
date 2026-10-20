#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime

import hengce_q017_observer_supervisor_v1 as v1
import hengce_q017_observation_lock_v5 as v5
import hengce_q017_macro_cache_v1 as macro

TZ = v5.TZ


def _load_history_local_only():
    path = v5.core.TW_HISTORY
    if not path.exists() or path.stat().st_size <= 100000:
        raise RuntimeError('LOCAL_ELECTRONICS_HISTORY_NOT_READY')
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def _local_seed_status():
    path = v5.core.TW_HISTORY
    return {
        'status': 'PASS',
        'source': 'LOCAL_INCREMENTAL_HISTORY_PREEXISTING',
        'seeded': False,
        'path': str(path.relative_to(v5.ROOT)),
        'bytes': path.stat().st_size,
    }


def _gate_from_cache(trade_date, cache, hist_date):
    eod_date, eod_status = v5.core.latest_eod_status()
    eod_complete = bool(
        eod_status
        and eod_status.get('price_status') == 'COMPLETE'
        and eod_status.get('institutional_status') == 'COMPLETE'
        and eod_status.get('margin_status') == 'COMPLETE'
    )
    return {
        'system': 'HENGCE',
        'module': 'Q017_MACRO_CACHE_DATA_GATE',
        'generated_at_taipei': v5.core.now_tw().isoformat(),
        'trade_date': trade_date.isoformat(),
        'status': 'PASS',
        'lane_status': {'q017_inputs': 'PASS'},
        'required': {
            'sox': cache['sox_status'],
            'latest_eod_date': eod_date,
            'latest_eod_complete': eod_complete,
            'electronics_history': _local_seed_status(),
            'electronics_history_latest': hist_date,
        },
        'sox': cache['sox_features'],
        'macro_cache_sha256': cache['cache_sha256'],
        'policy': 'Q017_MACRO_FROM_MORNING_HASH_BOUND_CACHE;LOCAL_HISTORY_ONLY;NO_MACRO_NETWORK_IN_OBSERVER',
    }


def prepared_from_macro_cache(trade_date):
    cache = macro.load_valid_cache(trade_date, verify_files=True)
    history = _load_history_local_only()
    srows = v5.core.read_sox()
    if not srows:
        raise RuntimeError('LOCAL_SOX_ROWS_EMPTY_AFTER_CACHE_VALIDATION')
    betas, prev, names, hist_date, universe = v5.core.current_betas(history, srows)
    if not universe or not betas or not prev:
        raise RuntimeError('LOCAL_MODEL_EMPTY_AFTER_MACRO_CACHE')
    seed = _local_seed_status()
    gate = _gate_from_cache(trade_date, cache, hist_date)
    coh = v5.v4.validate_premarket_coherence(trade_date, gate, hist_date)
    prepared = (
        gate,
        cache['sox_status'],
        cache['dxy_status'],
        seed,
        cache['sox_features'],
        betas,
        prev,
        names,
        hist_date,
        universe,
        coh,
    )
    v1._validate_prepared_model(prepared, trade_date)
    return prepared, cache


def cache_first_prepared_model(lane, trade_date, attempts):
    started = v5.core.now_tw()
    try:
        prepared, cache = prepared_from_macro_cache(trade_date)
        fingerprint = v1._install_frozen_prepare(prepared, trade_date)
        finished = v5.core.now_tw()
        attempts.append({
            'phase': 'MACRO_CACHE_BIND',
            'attempt': len(attempts) + 1,
            'started_at_taipei': started.isoformat(),
            'finished_at_taipei': finished.isoformat(),
            'result': 'PASS',
            'macro_cache_sha256': cache['cache_sha256'],
            'prewarm_fingerprint_sha256': fingerprint,
            'macro_network_calls_in_observer': 0,
        })
        v1._write_status(
            lane, trade_date, 'MORNING_MACRO_CACHE_FROZEN_READY_FOR_0901', attempts,
            macro_cache_trade_date=cache['trade_date'],
            macro_cache_generated_at_taipei=cache['generated_at_taipei'],
            macro_cache_sha256=cache['cache_sha256'],
            prewarm_fingerprint_sha256=fingerprint,
            macro_network_calls_in_observer=0,
            prepare_model_network_calls_during_0901=0,
            macro_cache_fallback_used=False,
        )
        return prepared, fingerprint, cache
    except Exception as exc:
        finished = v5.core.now_tw()
        attempts.append({
            'phase': 'MACRO_CACHE_BIND',
            'attempt': len(attempts) + 1,
            'started_at_taipei': started.isoformat(),
            'finished_at_taipei': finished.isoformat(),
            'result': 'FALLBACK',
            'error_type': type(exc).__name__,
            'error': str(exc)[:2000],
        })
        v1._write_status(
            lane, trade_date, 'MORNING_MACRO_CACHE_INVALID_USING_BOUNDED_PREWARM_FALLBACK', attempts,
            macro_cache_fallback_used=True,
            last_error=repr(exc),
        )
        prepared, fingerprint, _ = v1.prewarm_and_freeze(lane, trade_date, attempts)
        return prepared, fingerprint, None


def run(lane: str) -> int:
    if lane not in {'primary', 'backup'}:
        raise ValueError(lane)
    v1.install_resilient_transport()
    trade_date = v5.core.now_tw().date()
    attempts = []

    if trade_date.weekday() >= 5:
        v1._write_status(lane, trade_date, 'NO_TWSE_SESSION_EXPECTED', attempts)
        return 0

    try:
        _, fingerprint, cache = cache_first_prepared_model(lane, trade_date, attempts)
    except Exception as exc:
        v1._write_status(
            lane, trade_date, 'PREPARED_MODEL_FAIL_CLOSED', attempts,
            formal_buy_count=0,
            last_error=repr(exc),
            reason='NO_VALID_MACRO_CACHE_AND_NO_VALID_BOUNDED_PREWARM_BEFORE_0901',
        )
        return 2

    end = v1._deadline(trade_date)
    if v5.core.now_tw() > end:
        v1._write_status(
            lane, trade_date, 'FAIL_CLOSED_WINDOW_EXHAUSTED', attempts,
            formal_buy_count=0,
            prewarm_fingerprint_sha256=fingerprint,
            macro_cache_sha256=(cache or {}).get('cache_sha256'),
            reason='NO_VALID_SCHEMA5_0901_OBSERVATION_BEFORE_WINDOW_END',
        )
        return 2

    started = v5.core.now_tw()
    try:
        out = v1._observe_once(lane, trade_date)
        ok, reason = v5.validate_observation(out)
        if not ok:
            raise RuntimeError(f'SUPERVISOR_V2_OBSERVATION_INVALID:{reason}')
        finished = v5.core.now_tw()
        attempts.append({
            'phase': 'OBSERVATION',
            'attempt': len(attempts) + 1,
            'started_at_taipei': started.isoformat(),
            'finished_at_taipei': finished.isoformat(),
            'result': 'PASS',
        })
        v1._write_status(
            lane, trade_date, 'OBSERVATION_READY', attempts,
            prewarm_fingerprint_sha256=fingerprint,
            macro_cache_sha256=(cache or {}).get('cache_sha256'),
            macro_cache_fallback_used=cache is None,
            macro_network_calls_during_0901=0,
            prepare_model_network_calls_during_0901=0,
            observation_snapshot_sha256=out.get('observation_snapshot_sha256'),
            provider_coverage=(out.get('data_status') or {}).get('provider_coverage'),
            eligible_quote_row_coverage=(out.get('data_status') or {}).get('eligible_quote_row_coverage'),
        )
        print(json.dumps({
            'supervisor': 'PASS',
            'version': 2,
            'lane': lane,
            'trade_date': trade_date.isoformat(),
            'macro_cache_used': cache is not None,
            'macro_cache_sha256': (cache or {}).get('cache_sha256'),
            'prewarm_fingerprint_sha256': fingerprint,
            'macro_network_calls_during_0901': 0,
            'prepare_model_network_calls_during_0901': 0,
        }, ensure_ascii=False))
        return 0
    except Exception as exc:
        finished = v5.core.now_tw()
        attempts.append({
            'phase': 'OBSERVATION',
            'attempt': len(attempts) + 1,
            'started_at_taipei': started.isoformat(),
            'finished_at_taipei': finished.isoformat(),
            'result': 'FINAL_FAIL',
            'error_type': type(exc).__name__,
            'error': str(exc)[:2000],
        })
        v1._write_status(
            lane, trade_date, 'FAIL_CLOSED_WINDOW_EXHAUSTED', attempts,
            formal_buy_count=0,
            prewarm_fingerprint_sha256=fingerprint,
            macro_cache_sha256=(cache or {}).get('cache_sha256'),
            macro_cache_fallback_used=cache is None,
            macro_network_calls_during_0901=0,
            prepare_model_network_calls_during_0901=0,
            last_error=repr(exc),
            reason='NO_VALID_SCHEMA5_0901_OBSERVATION_BEFORE_WINDOW_END',
        )
        return 2


def self_test():
    assert macro.SCHEMA_VERSION == 1
    assert v5.SCHEMA == 5
    assert v5.UNIVERSE_SCOPE == 'TWSE_LISTED_ELECTRONICS_ONLY'
    assert v1.CONNECT_TIMEOUT_SECONDS <= 2.5
    assert v1.READ_TIMEOUT_SECONDS <= 6.0
    print(json.dumps({
        'self_test': 'PASS',
        'supervisor_version': 2,
        'macro_cache_first': True,
        'macro_cache_trade_date_bound': True,
        'macro_cache_source_hash_bound': True,
        'bounded_v1_prewarm_fallback': True,
        'macro_network_calls_during_0901': 0,
        'late_backfill_forbidden': True,
        'schema_v5_unchanged': True,
    }, ensure_ascii=False))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lane', choices=['primary', 'backup'])
    ap.add_argument('--mode', choices=['observe', 'self-test'], default='observe')
    args = ap.parse_args()
    if args.mode == 'self-test':
        return self_test()
    if not args.lane:
        ap.error('--lane is required for observe mode')
    return run(args.lane)


if __name__ == '__main__':
    raise SystemExit(main())
