#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import queue
import time
from datetime import datetime, time as dtime
from pathlib import Path

import requests

import hengce_q017_observation_lock_v5 as v5
import hengce_q017_backup_observer_v5 as backup
import hengce_q017_premarket_snapshot_v1 as premarket_snapshot

TZ = v5.TZ
RADAR = v5.RADAR
CONNECT_TIMEOUT_SECONDS = 2.5
READ_TIMEOUT_SECONDS = 6.0
PREWARM_START = dtime(8, 30, 0)
PREFERRED_REFRESH = dtime(8, 50, 0)
PREWARM_HARD_STOP = dtime(9, 0, 45)
_ORIGINAL_PREPARE_MODEL = v5.v4.prepare_model


def _status_path(lane: str) -> Path:
    return RADAR / f'observer_supervisor_{lane}_status.json'


def _attempts_path(lane: str, trade_date) -> Path:
    p = RADAR / 'observer_supervisor_attempts'
    p.mkdir(parents=True, exist_ok=True)
    return p / f'{trade_date.strftime("%Y%m%d")}_{lane}.json'


def _deadline(trade_date):
    return datetime.combine(trade_date, dtime(9, 1, 59, 999999), tzinfo=TZ)


def _at(trade_date, t: dtime):
    return datetime.combine(trade_date, t, tzinfo=TZ)


def _retry_sleep_seconds(now) -> float:
    minute_of_day = now.hour * 60 + now.minute
    if minute_of_day < 8 * 60 + 45:
        return 60.0
    if minute_of_day < 9 * 60:
        return 20.0
    if minute_of_day < 9 * 60 + 1:
        return 5.0
    return 1.0


def _prewarm_timeout_seconds(now) -> float:
    # A late-started runner must never spend the legal observation minute
    # inside SOX/DXY/history preparation.
    minute_of_day = now.hour * 60 + now.minute
    if minute_of_day < 8 * 60 + 50:
        return 45.0
    if minute_of_day < 8 * 60 + 58:
        return 20.0
    if minute_of_day < 9 * 60:
        return 8.0
    return 4.0


def _write_status(lane: str, trade_date, state: str, attempts, **extra):
    payload = {
        'schema_version': 3,
        'system': 'HENGCE',
        'module': 'Q017_OBSERVER_SUPERVISOR',
        'lane': lane,
        'trade_date': trade_date.isoformat(),
        'generated_at_taipei': v5.core.now_tw().isoformat(),
        'state': state,
        'authority': 'INFRASTRUCTURE_DIAGNOSTIC_ONLY_NO_RANKING_AUTHORITY',
        'strict_observation_window': '09:01:00-09:01:59.999999 Asia/Taipei',
        'late_market_backfill_forbidden': True,
        'prewarm': {
            'persisted_fallback': '06:30 Q017 premarket snapshot, hash-validated, zero signal authority',
            'live_start_taipei': '08:30:00',
            'preferred_refresh_taipei': '08:50:00',
            'hard_stop_taipei': '09:00:45',
            'purpose': 'freeze causal T-1 model/macro before the 09:01 quote critical section',
            'network_prepare_during_0901_forbidden_when_candidate_ready': True,
        },
        'transport': {
            'provider': 'TWSE_MIS',
            'connect_timeout_seconds': CONNECT_TIMEOUT_SECONDS,
            'read_timeout_seconds': READ_TIMEOUT_SECONDS,
            'batch_size': v5.v4.BATCH_SIZE,
            'workers': v5.v4.WORKERS,
        },
        'attempt_count': len(attempts),
        'attempts': attempts[-100:],
    }
    payload.update(extra)
    v5.core.atomic_json(_status_path(lane), payload)
    v5.core.atomic_json(_attempts_path(lane, trade_date), payload)
    return payload


def install_resilient_transport():
    """Bound one hung MIS batch without changing Q017 semantics."""
    legacy = v5.v4.legacy

    def mis_batch_bounded(tickers):
        ex_ch = '|'.join(f'tse_{t}.tw' for t in tickers)
        params = {'ex_ch': ex_ch, 'json': '1', 'delay': '0'}
        headers = {
            'User-Agent': 'Mozilla/5.0 HENGCE-Q017-OBS-SUPERVISOR/3.0',
            'Accept': 'application/json',
            'Referer': 'https://mis.twse.com.tw/stock/index.jsp',
        }
        started = v5.core.now_tw()
        r = requests.get(
            legacy.MIS_URL,
            params=params,
            headers=headers,
            timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
        )
        r.raise_for_status()
        fetched = v5.core.now_tw()
        data = r.json()
        rows = data.get('msgArray') if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise RuntimeError('MIS_MSGARRAY_MISSING')
        out = {}
        wanted = set(str(x) for x in tickers)
        for row in rows:
            ticker = str(row.get('c') or '').strip()
            if ticker not in wanted:
                continue
            out[ticker] = {
                'ticker': ticker,
                'name': str(row.get('n') or '').strip(),
                'open': legacy.fnum(row.get('o')),
                'reference_close': legacy.fnum(row.get('y')),
                'last_price': legacy.fnum(row.get('z')),
                'best_bid': legacy.fnum(str(row.get('b') or '').split('_')[0]),
                'best_ask': legacy.fnum(str(row.get('a') or '').split('_')[0]),
                'fetched_at_taipei': fetched.isoformat(),
                'source': 'TWSE_MIS',
            }
        return out, started, fetched

    v5.v4.mis_batch = mis_batch_bounded
    return mis_batch_bounded


def _prepare_worker(trade_date, outq):
    try:
        outq.put(('PASS', _ORIGINAL_PREPARE_MODEL(trade_date)))
    except BaseException as exc:
        outq.put(('FAIL', (type(exc).__name__, str(exc)[:4000])))


def _bounded_prepare_model(trade_date, timeout_seconds: float):
    """Run slow premarket preparation in a killable subprocess."""
    methods = mp.get_all_start_methods()
    ctx = mp.get_context('fork' if 'fork' in methods else methods[0])
    outq = ctx.Queue(maxsize=1)
    proc = ctx.Process(target=_prepare_worker, args=(trade_date, outq), daemon=True)
    proc.start()
    try:
        tag, payload = outq.get(timeout=timeout_seconds)
    except queue.Empty:
        if proc.is_alive():
            proc.terminate()
        proc.join(timeout=2)
        if proc.is_alive():
            proc.kill(); proc.join(timeout=2)
        raise TimeoutError(f'PREWARM_TIMEOUT_AFTER_{timeout_seconds:.1f}S')
    finally:
        try:
            outq.close()
        except Exception:
            pass
    proc.join(timeout=2)
    if proc.is_alive():
        proc.terminate(); proc.join(timeout=2)
    if tag != 'PASS':
        etype, message = payload
        raise RuntimeError(f'PREWARM_CHILD_FAIL:{etype}:{message}')
    return payload


def _validate_prepared_model(prepared, trade_date):
    if not isinstance(prepared, tuple) or len(prepared) != 11:
        raise RuntimeError('PREWARM_PREPARED_MODEL_SHAPE_INVALID')
    gate, sox_status, dxy_status, seed, sf, betas, prev, names, hist_date, universe, coh = prepared
    if (gate or {}).get('status') != 'PASS':
        raise RuntimeError('PREWARM_GATE_NOT_PASS')
    if (sox_status or {}).get('status') != 'PASS':
        raise RuntimeError('PREWARM_SOX_STATUS_NOT_PASS')
    if not universe or not betas or not prev:
        raise RuntimeError('PREWARM_MODEL_EMPTY')
    if sf.get('sox_1d') is None or sf.get('sox_5d') is None:
        raise RuntimeError('PREWARM_SOX_FEATURES_MISSING')
    if (dxy_status or {}).get('status') != 'PASS' or (dxy_status or {}).get('dxy_5d') is None:
        raise RuntimeError('PREWARM_DXY_FEATURE_MISSING')
    hd = datetime.strptime(str(hist_date), '%Y-%m-%d').date()
    if hd >= trade_date:
        raise RuntimeError('PREWARM_HISTORY_NOT_CAUSAL')
    if (coh or {}).get('status') != 'PASS':
        raise RuntimeError('PREWARM_COHERENCE_NOT_PASS')
    return prepared


def _prepared_fingerprint(prepared):
    _, _, dxy_status, _, sf, betas, prev, _, hist_date, universe, _ = prepared
    material = {
        'hist_date': str(hist_date),
        'universe': sorted(str(x) for x in universe),
        'betas': {str(k): betas[k] for k in sorted(betas)},
        'previous_close': {str(k): prev[k] for k in sorted(prev)},
        'sox': sf,
        'dxy': {
            'latest_session': (dxy_status or {}).get('latest_session'),
            'five_sessions_back': (dxy_status or {}).get('five_sessions_back'),
            'dxy_5d': (dxy_status or {}).get('dxy_5d'),
        },
    }
    return v5.csha(material)


def _install_frozen_prepare(prepared, trade_date):
    fingerprint = _prepared_fingerprint(prepared)

    def frozen(requested_date):
        if requested_date != trade_date:
            raise RuntimeError('FROZEN_PREWARM_TRADE_DATE_MISMATCH')
        return prepared

    v5.v4.prepare_model = frozen
    return fingerprint


def _wait_until(target, lane, trade_date, attempts, state):
    while True:
        now = v5.core.now_tw()
        if now >= target:
            return
        _write_status(lane, trade_date, state, attempts, wake_target_taipei=target.isoformat())
        time.sleep(min(30.0, max(0.0, (target - now).total_seconds())))


def _load_persisted_candidate(lane, trade_date, attempts):
    started = v5.core.now_tw()
    try:
        prepared, meta = premarket_snapshot.load_snapshot(trade_date)
        _validate_prepared_model(prepared, trade_date)
        generated = datetime.fromisoformat(meta['generated_at_taipei']).astimezone(TZ)
        attempts.append({
            'phase': 'PREWARM_CACHE',
            'attempt': len(attempts) + 1,
            'started_at_taipei': started.isoformat(),
            'finished_at_taipei': v5.core.now_tw().isoformat(),
            'result': 'PASS',
            'candidate_source': 'PERSISTED_0630_SNAPSHOT',
            'snapshot_sha256': meta.get('snapshot_sha256'),
            'snapshot_model_fingerprint_sha256': meta.get('model_fingerprint_sha256'),
            'fingerprint_sha256': _prepared_fingerprint(prepared),
        })
        _write_status(
            lane, trade_date, 'PREWARM_CACHE_READY', attempts,
            candidate_source='PERSISTED_0630_SNAPSHOT',
            prewarm_candidate_at_taipei=generated.isoformat(),
            snapshot_sha256=meta.get('snapshot_sha256'),
            prewarm_fingerprint_sha256=_prepared_fingerprint(prepared),
        )
        return prepared, generated, meta
    except Exception as exc:
        attempts.append({
            'phase': 'PREWARM_CACHE',
            'attempt': len(attempts) + 1,
            'started_at_taipei': started.isoformat(),
            'finished_at_taipei': v5.core.now_tw().isoformat(),
            'result': 'MISS_OR_INVALID',
            'error_type': type(exc).__name__,
            'error': str(exc)[:2000],
        })
        _write_status(lane, trade_date, 'PREWARM_CACHE_UNAVAILABLE', attempts, last_error=repr(exc))
        return None, None, None


def prewarm_and_freeze(lane: str, trade_date, attempts):
    start = _at(trade_date, PREWARM_START)
    refresh = _at(trade_date, PREFERRED_REFRESH)
    hard_stop = _at(trade_date, PREWARM_HARD_STOP)

    candidate, candidate_at, cache_meta = _load_persisted_candidate(lane, trade_date, attempts)
    candidate_source = 'PERSISTED_0630_SNAPSHOT' if candidate is not None else None
    valid_cache_retained = candidate is not None

    now = v5.core.now_tw()
    if now < start:
        _wait_until(start, lane, trade_date, attempts, 'WAITING_FOR_0830_LIVE_PREWARM')

    # A very late GitHub runner can still use the validated 06:30 model cache.
    # It must not start slow SOX/DXY/history I/O after 09:00:45.
    if v5.core.now_tw() > hard_stop:
        if candidate is None:
            raise RuntimeError('LATE_RUNNER_NO_VALID_0630_PREWARM_SNAPSHOT')
        fingerprint = _install_frozen_prepare(candidate, trade_date)
        frozen_at = v5.core.now_tw()
        _write_status(
            lane, trade_date, 'PREWARM_FROZEN_FROM_PERSISTED_CACHE_LATE_RUNNER', attempts,
            candidate_source=candidate_source,
            prewarm_candidate_at_taipei=candidate_at.isoformat() if candidate_at else None,
            prewarm_frozen_at_taipei=frozen_at.isoformat(),
            prewarm_fingerprint_sha256=fingerprint,
            snapshot_sha256=(cache_meta or {}).get('snapshot_sha256'),
            prepare_model_network_calls_during_0901=0,
        )
        return candidate, fingerprint, candidate_source

    live_success_before_refresh = False
    while v5.core.now_tw() <= hard_stop:
        now = v5.core.now_tw()
        timeout_seconds = min(_prewarm_timeout_seconds(now), max(1.0, (hard_stop - now).total_seconds()))
        started = now
        try:
            prepared = _bounded_prepare_model(trade_date, timeout_seconds)
            _validate_prepared_model(prepared, trade_date)
            candidate = prepared
            candidate_at = v5.core.now_tw()
            candidate_source = 'LIVE_PREWARM'
            attempts.append({
                'phase': 'PREWARM_LIVE',
                'attempt': len(attempts) + 1,
                'started_at_taipei': started.isoformat(),
                'finished_at_taipei': candidate_at.isoformat(),
                'result': 'PASS',
                'timeout_seconds': timeout_seconds,
                'candidate_source': candidate_source,
                'fingerprint_sha256': _prepared_fingerprint(candidate),
            })
            _write_status(
                lane, trade_date, 'PREWARM_LIVE_CANDIDATE_READY', attempts,
                candidate_source=candidate_source,
                valid_persisted_cache_also_available=valid_cache_retained,
                prewarm_candidate_at_taipei=candidate_at.isoformat(),
                prewarm_fingerprint_sha256=_prepared_fingerprint(candidate),
            )
            if started < refresh:
                live_success_before_refresh = True
                _wait_until(refresh, lane, trade_date, attempts, 'PREWARM_LIVE_READY_WAITING_PREFERRED_REFRESH')
                continue
            break
        except Exception as exc:
            finished = v5.core.now_tw()
            attempts.append({
                'phase': 'PREWARM_LIVE',
                'attempt': len(attempts) + 1,
                'started_at_taipei': started.isoformat(),
                'finished_at_taipei': finished.isoformat(),
                'result': 'RETRYABLE_FAIL' if finished <= hard_stop else 'FINAL_FAIL',
                'timeout_seconds': timeout_seconds,
                'valid_candidate_retained': candidate is not None,
                'retained_candidate_source': candidate_source,
                'error_type': type(exc).__name__,
                'error': str(exc)[:2000],
            })
            _write_status(
                lane, trade_date, 'PREWARM_LIVE_RETRYING', attempts,
                valid_candidate_retained=candidate is not None,
                retained_candidate_source=candidate_source,
                last_error=repr(exc),
            )
            if candidate is not None and live_success_before_refresh and finished >= refresh:
                break
            if finished >= hard_stop:
                break
            time.sleep(min(_retry_sleep_seconds(finished), max(0.0, (hard_stop - finished).total_seconds())))

    if candidate is None:
        raise RuntimeError('NO_VALID_PREWARM_MODEL_OR_0630_SNAPSHOT_BEFORE_0900_45')
    fingerprint = _install_frozen_prepare(candidate, trade_date)
    frozen_at = v5.core.now_tw()
    _write_status(
        lane, trade_date, 'PREWARM_FROZEN_READY_FOR_0901', attempts,
        candidate_source=candidate_source,
        prewarm_candidate_at_taipei=candidate_at.isoformat() if candidate_at else None,
        prewarm_frozen_at_taipei=frozen_at.isoformat(),
        prewarm_fingerprint_sha256=fingerprint,
        snapshot_sha256=(cache_meta or {}).get('snapshot_sha256') if candidate_source == 'PERSISTED_0630_SNAPSHOT' else None,
        prepare_model_network_calls_during_0901=0,
    )
    return candidate, fingerprint, candidate_source


def _observe_once(lane: str, trade_date):
    if lane == 'backup':
        backup.activate_backup_lane()
        return backup.observe(trade_date)
    return v5.collect_observation(trade_date)


def run(lane: str) -> int:
    if lane not in {'primary', 'backup'}:
        raise ValueError(lane)
    install_resilient_transport()
    trade_date = v5.core.now_tw().date()
    attempts = []

    if trade_date.weekday() >= 5:
        _write_status(lane, trade_date, 'NO_TWSE_SESSION_EXPECTED', attempts)
        return 0

    try:
        _, fingerprint, candidate_source = prewarm_and_freeze(lane, trade_date, attempts)
    except Exception as exc:
        _write_status(
            lane, trade_date, 'PREWARM_FAIL_CLOSED', attempts,
            formal_buy_count=0, last_error=repr(exc),
            reason='NO_VALID_CAUSAL_MODEL_READY_BEFORE_0901_CRITICAL_SECTION',
        )
        return 2

    end = _deadline(trade_date)
    if v5.core.now_tw() > end:
        _write_status(
            lane, trade_date, 'FAIL_CLOSED_WINDOW_EXHAUSTED', attempts,
            formal_buy_count=0,
            candidate_source=candidate_source,
            prewarm_fingerprint_sha256=fingerprint,
            reason='NO_VALID_SCHEMA5_0901_OBSERVATION_BEFORE_WINDOW_END',
        )
        return 2

    started = v5.core.now_tw()
    try:
        # prepare_model is frozen. Only the TWSE MIS quote transport remains
        # live in the legal 09:01 critical section.
        out = _observe_once(lane, trade_date)
        ok, reason = v5.validate_observation(out)
        if not ok:
            raise RuntimeError(f'SUPERVISOR_OBSERVATION_INVALID:{reason}')
        attempts.append({
            'phase': 'OBSERVATION',
            'attempt': len(attempts) + 1,
            'started_at_taipei': started.isoformat(),
            'finished_at_taipei': v5.core.now_tw().isoformat(),
            'result': 'PASS',
        })
        _write_status(
            lane, trade_date, 'OBSERVATION_READY', attempts,
            candidate_source=candidate_source,
            prewarm_fingerprint_sha256=fingerprint,
            prepare_model_network_calls_during_0901=0,
            observation_snapshot_sha256=out.get('observation_snapshot_sha256'),
            provider_coverage=(out.get('data_status') or {}).get('provider_coverage'),
            eligible_quote_row_coverage=(out.get('data_status') or {}).get('eligible_quote_row_coverage'),
        )
        print(json.dumps({
            'supervisor': 'PASS', 'lane': lane, 'trade_date': trade_date.isoformat(),
            'candidate_source': candidate_source,
            'prewarm_fingerprint_sha256': fingerprint,
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
        _write_status(
            lane, trade_date, 'FAIL_CLOSED_WINDOW_EXHAUSTED', attempts,
            formal_buy_count=0,
            candidate_source=candidate_source,
            prewarm_fingerprint_sha256=fingerprint,
            prepare_model_network_calls_during_0901=0,
            last_error=repr(exc),
            reason='NO_VALID_SCHEMA5_0901_OBSERVATION_BEFORE_WINDOW_END',
        )
        return 2


def self_test() -> int:
    fn = install_resilient_transport()
    assert callable(fn)
    assert v5.v4.mis_batch is fn
    assert 0 < CONNECT_TIMEOUT_SECONDS < 5
    assert 0 < READ_TIMEOUT_SECONDS < 10
    assert PREWARM_START == dtime(8, 30, 0)
    assert PREFERRED_REFRESH == dtime(8, 50, 0)
    assert PREWARM_HARD_STOP == dtime(9, 0, 45)
    assert _prewarm_timeout_seconds(datetime(2026, 10, 21, 8, 40, tzinfo=TZ)) == 45.0
    assert _prewarm_timeout_seconds(datetime(2026, 10, 21, 8, 55, tzinfo=TZ)) == 20.0
    assert _prewarm_timeout_seconds(datetime(2026, 10, 21, 8, 59, tzinfo=TZ)) == 8.0
    assert _prewarm_timeout_seconds(datetime(2026, 10, 21, 9, 0, 30, tzinfo=TZ)) == 4.0
    assert _retry_sleep_seconds(datetime(2026, 10, 21, 7, 50, tzinfo=TZ)) == 60.0
    assert _retry_sleep_seconds(datetime(2026, 10, 21, 8, 50, tzinfo=TZ)) == 20.0
    assert _deadline(datetime(2026, 10, 21).date()).isoformat().startswith('2026-10-21T09:01:59.999999')
    assert premarket_snapshot.AUTHORITY == 'INFRASTRUCTURE_CACHE_ONLY_NO_SIGNAL_AUTHORITY'
    assert premarket_snapshot.BUILD_CUTOFF == dtime(9, 0, 45)

    trade_date = datetime(2026, 10, 21).date()
    synthetic = (
        {'status': 'PASS'}, {'status': 'PASS'},
        {'status': 'PASS', 'dxy_5d': 0.0, 'latest_session': '2026-10-20', 'five_sessions_back': '2026-10-13'},
        'seed', {'sox_1d': -0.01, 'sox_5d': -0.04},
        {'2330': 1.1}, {'2330': 1000.0}, {'2330': '台積電'},
        '2026-10-20', ['2330'], {'status': 'PASS'},
    )
    _validate_prepared_model(synthetic, trade_date)
    fingerprint = _install_frozen_prepare(synthetic, trade_date)
    assert v5.v4.prepare_model(trade_date) is synthetic
    assert len(fingerprint) == 64
    try:
        v5.v4.prepare_model(datetime(2026, 10, 22).date())
        raise AssertionError('trade-date mismatch must fail')
    except RuntimeError as exc:
        assert 'TRADE_DATE_MISMATCH' in str(exc)
    v5.v4.prepare_model = _ORIGINAL_PREPARE_MODEL

    print(json.dumps({
        'self_test': 'PASS',
        'persisted_0630_snapshot_fallback': True,
        'snapshot_authority': premarket_snapshot.AUTHORITY,
        'prewarm_start_taipei': '08:30:00',
        'preferred_refresh_taipei': '08:50:00',
        'prewarm_hard_stop_taipei': '09:00:45',
        'prewarm_subprocess_hard_timeout': True,
        'late_runner_can_use_validated_snapshot': True,
        'frozen_prepare_during_0901': True,
        'prepare_model_network_calls_during_0901': 0,
        'late_backfill_forbidden': True,
        'transport_connect_timeout_seconds': CONNECT_TIMEOUT_SECONDS,
        'transport_read_timeout_seconds': READ_TIMEOUT_SECONDS,
        'core_schema_v5_not_modified': True,
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
