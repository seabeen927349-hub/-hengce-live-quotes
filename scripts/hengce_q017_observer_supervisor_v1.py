#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, time as dtime
from pathlib import Path

import requests

import hengce_q017_observation_lock_v5 as v5
import hengce_q017_backup_observer_v5 as backup

TZ = v5.TZ
RADAR = v5.RADAR
CONNECT_TIMEOUT_SECONDS = 2.5
READ_TIMEOUT_SECONDS = 6.0


def _status_path(lane: str) -> Path:
    return RADAR / f'observer_supervisor_{lane}_status.json'


def _attempts_path(lane: str, trade_date) -> Path:
    p = RADAR / 'observer_supervisor_attempts'
    p.mkdir(parents=True, exist_ok=True)
    return p / f'{trade_date.strftime("%Y%m%d")}_{lane}.json'


def _deadline(trade_date):
    return datetime.combine(trade_date, dtime(9, 1, 59, 999999), tzinfo=TZ)


def _retry_sleep_seconds(now) -> float:
    # Retry gently while far from the capture window, then become aggressive
    # close to 09:01. This avoids hammering upstream services for an hour.
    minute_of_day = now.hour * 60 + now.minute
    if minute_of_day < 8 * 60 + 45:
        return 60.0
    if minute_of_day < 9 * 60:
        return 20.0
    if minute_of_day < 9 * 60 + 1:
        return 5.0
    return 1.0


def _write_status(lane: str, trade_date, state: str, attempts, **extra):
    payload = {
        'schema_version': 1,
        'system': 'HENGCE',
        'module': 'Q017_OBSERVER_SUPERVISOR',
        'lane': lane,
        'trade_date': trade_date.isoformat(),
        'generated_at_taipei': v5.core.now_tw().isoformat(),
        'state': state,
        'authority': 'INFRASTRUCTURE_DIAGNOSTIC_ONLY_NO_RANKING_AUTHORITY',
        'strict_observation_window': '09:01:00-09:01:59.999999 Asia/Taipei',
        'late_market_backfill_forbidden': True,
        'transport': {
            'provider': 'TWSE_MIS',
            'connect_timeout_seconds': CONNECT_TIMEOUT_SECONDS,
            'read_timeout_seconds': READ_TIMEOUT_SECONDS,
            'batch_size': v5.v4.BATCH_SIZE,
            'workers': v5.v4.WORKERS,
        },
        'attempt_count': len(attempts),
        'attempts': attempts[-50:],
    }
    payload.update(extra)
    v5.core.atomic_json(_status_path(lane), payload)
    v5.core.atomic_json(_attempts_path(lane, trade_date), payload)
    return payload


def install_resilient_transport():
    """Keep quote semantics identical while bounding one hung MIS batch.

    v4.capture_provider_attempt resolves its module-global `mis_batch` at run
    time, so replacing that function changes transport timing only. Universe,
    formula, coverage, timestamp validation and 09:01 authority remain in v5.
    """
    legacy = v5.v4.legacy

    def mis_batch_bounded(tickers):
        ex_ch = '|'.join(f'tse_{t}.tw' for t in tickers)
        params = {'ex_ch': ex_ch, 'json': '1', 'delay': '0'}
        headers = {
            'User-Agent': 'Mozilla/5.0 HENGCE-Q017-OBS-SUPERVISOR/1.0',
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

    end = _deadline(trade_date)
    while True:
        now = v5.core.now_tw()
        if now > end:
            _write_status(
                lane,
                trade_date,
                'FAIL_CLOSED_WINDOW_EXHAUSTED',
                attempts,
                formal_buy_count=0,
                reason='NO_VALID_SCHEMA5_0901_OBSERVATION_BEFORE_WINDOW_END',
            )
            return 2

        started = now
        try:
            out = _observe_once(lane, trade_date)
            ok, reason = v5.validate_observation(out)
            if not ok:
                raise RuntimeError(f'SUPERVISOR_OBSERVATION_INVALID:{reason}')
            attempts.append({
                'attempt': len(attempts) + 1,
                'started_at_taipei': started.isoformat(),
                'finished_at_taipei': v5.core.now_tw().isoformat(),
                'result': 'PASS',
            })
            _write_status(
                lane,
                trade_date,
                'OBSERVATION_READY',
                attempts,
                observation_snapshot_sha256=out.get('observation_snapshot_sha256'),
                provider_coverage=(out.get('data_status') or {}).get('provider_coverage'),
                eligible_quote_row_coverage=(out.get('data_status') or {}).get('eligible_quote_row_coverage'),
            )
            print(json.dumps({'supervisor': 'PASS', 'lane': lane, 'trade_date': trade_date.isoformat(), 'attempts': len(attempts)}, ensure_ascii=False))
            return 0
        except Exception as exc:
            finished = v5.core.now_tw()
            attempts.append({
                'attempt': len(attempts) + 1,
                'started_at_taipei': started.isoformat(),
                'finished_at_taipei': finished.isoformat(),
                'result': 'RETRYABLE_FAIL' if finished <= end else 'FINAL_FAIL',
                'error_type': type(exc).__name__,
                'error': str(exc)[:2000],
            })
            state = 'RETRYING_BEFORE_0901_WINDOW_END' if finished <= end else 'FAIL_CLOSED_WINDOW_EXHAUSTED'
            _write_status(lane, trade_date, state, attempts, formal_buy_count=0, last_error=repr(exc))
            if finished > end:
                return 2
            remaining = max(0.0, (end - finished).total_seconds())
            if remaining <= 0:
                return 2
            time.sleep(min(_retry_sleep_seconds(finished), remaining))


def self_test() -> int:
    fn = install_resilient_transport()
    assert callable(fn)
    assert v5.v4.mis_batch is fn
    assert 0 < CONNECT_TIMEOUT_SECONDS < 5
    assert 0 < READ_TIMEOUT_SECONDS < 10
    assert _retry_sleep_seconds(datetime(2026, 10, 21, 7, 50, tzinfo=TZ)) == 60.0
    assert _retry_sleep_seconds(datetime(2026, 10, 21, 8, 50, tzinfo=TZ)) == 20.0
    assert _retry_sleep_seconds(datetime(2026, 10, 21, 9, 0, 30, tzinfo=TZ)) == 5.0
    assert _retry_sleep_seconds(datetime(2026, 10, 21, 9, 1, 30, tzinfo=TZ)) == 1.0
    assert _deadline(datetime(2026, 10, 21).date()).isoformat().startswith('2026-10-21T09:01:59.999999')
    print(json.dumps({
        'self_test': 'PASS',
        'preflight_retry_until_window_end': True,
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
