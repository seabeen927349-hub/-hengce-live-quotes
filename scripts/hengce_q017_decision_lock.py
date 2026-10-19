#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time as dtime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

import hengce_daily_command_center as core

TZ = core.TZ
ET = ZoneInfo('America/New_York')
ROOT = core.ROOT
RADAR = core.RADAR
HISTORY = core.HISTORY
LATEST = core.LATEST
SIGNAL_LEDGER = core.SIGNAL_LEDGER
DECISION_DIR = RADAR / 'decision'
DECISION_LATEST = RADAR / 'decision_latest.json'
MIS_URL = 'https://mis.twse.com.tw/stock/api/getStockInfo.jsp'
DXY_ENDPOINTS = [
    'https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB',
    'https://query2.finance.yahoo.com/v8/finance/chart/DX-Y.NYB',
]
DXY_CSV = core.DATA / 'dxy_2026.csv'
DXY_STATUS = core.DATA / 'dxy_status.json'
DECISION_HOUR = 9
DECISION_MINUTE = 1
DECISION_SECOND = 5
MIN_PROVIDER_COVERAGE = 0.98
BATCH_SIZE = 40
WORKERS = 10

# Frozen Q017_LOCK_20261018 market gate. Do not tune here.
SOX_1D_MAX = 0.0
SOX_5D_MAX = -0.03
DXY_5D_MIN = -0.005

DECISION_DIR.mkdir(parents=True, exist_ok=True)


def canonical_sha(obj):
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def chunks(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i:i+n]


def fnum(x):
    if x in (None, '', '-', '--'):
        return None
    try:
        return float(str(x).replace(',', ''))
    except Exception:
        return None


def mis_batch(tickers):
    ex_ch = '|'.join(f'tse_{t}.tw' for t in tickers)
    params = {'ex_ch': ex_ch, 'json': '1', 'delay': '0'}
    headers = {
        'User-Agent': 'Mozilla/5.0 HENGCE-Q017-DECISION-LOCK/1.0',
        'Accept': 'application/json',
        'Referer': 'https://mis.twse.com.tw/stock/index.jsp',
    }
    started = core.now_tw()
    r = requests.get(MIS_URL, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    fetched = core.now_tw()
    data = r.json()
    rows = data.get('msgArray') if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise RuntimeError('MIS_MSGARRAY_MISSING')
    out = {}
    for row in rows:
        ticker = str(row.get('c') or '').strip()
        if ticker not in tickers:
            continue
        out[ticker] = {
            'ticker': ticker,
            'name': str(row.get('n') or '').strip(),
            'open': fnum(row.get('o')),
            'reference_close': fnum(row.get('y')),
            'last_price': fnum(row.get('z')),
            'best_bid': fnum(str(row.get('b') or '').split('_')[0]),
            'best_ask': fnum(str(row.get('a') or '').split('_')[0]),
            'fetched_at_taipei': fetched.isoformat(),
            'source': 'TWSE_MIS',
        }
    return out, started, fetched


def decision_path(today):
    return DECISION_DIR / f'{today.strftime("%Y%m%d")}_0901.json'


def wait_for_decision_minute(today):
    now = core.now_tw()
    if today != now.date():
        raise RuntimeError('DECISION_CAPTURE_ONLY_ALLOWED_FOR_CURRENT_TRADE_DATE')
    target = datetime.combine(today, dtime(DECISION_HOUR, DECISION_MINUTE, DECISION_SECOND), tzinfo=TZ)
    end = datetime.combine(today, dtime(DECISION_HOUR, DECISION_MINUTE, 59, 999999), tzinfo=TZ)
    if now > end:
        raise RuntimeError(f'DECISION_WINDOW_MISSED:{now.isoformat()}')
    if now < target:
        time.sleep((target - now).total_seconds())
    return target, end


def _dxy_rows_from_yahoo(payload, today):
    chart = (payload or {}).get('chart') or {}
    if chart.get('error'):
        raise RuntimeError(f'DXY_YAHOO_ERROR:{chart.get("error")}')
    results = chart.get('result') or []
    if not results:
        raise RuntimeError('DXY_YAHOO_RESULT_MISSING')
    result = results[0]
    timestamps = result.get('timestamp') or []
    indicators = result.get('indicators') or {}
    quotes = indicators.get('quote') or []
    closes = (quotes[0].get('close') if quotes else None) or []
    if not timestamps or not closes:
        raise RuntimeError('DXY_YAHOO_SERIES_MISSING')
    rows = {}
    for ts, close in zip(timestamps, closes):
        c = fnum(close)
        if c is None or c <= 0:
            continue
        # Yahoo daily bars are assigned to the exchange-local session date.
        # At Taiwan 09:01, the previous US weekday session is completed. We
        # exclude same/future Taiwan dates and weekend pseudo/live bars so a
        # Sunday streaming row can never enter the completed-session gate.
        d = datetime.fromtimestamp(int(ts), timezone.utc).astimezone(ET).date()
        if d.year != 2026 or d >= today or d.weekday() >= 5:
            continue
        rows[d.isoformat()] = c
    return [{'date': d, 'close': rows[d]} for d in sorted(rows)]


def _load_dxy_cache():
    if not DXY_CSV.exists():
        return []
    out = []
    with DXY_CSV.open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            c = fnum(r.get('close'))
            d = str(r.get('date') or '')
            if len(d) == 10 and c is not None and c > 0:
                out.append({'date': d, 'close': c})
    return sorted({r['date']: r for r in out}.values(), key=lambda x: x['date'])


def _dxy_status_from_rows(rows, today, source, refreshed_at):
    rows = [r for r in rows if r['date'] < today.isoformat() and datetime.strptime(r['date'], '%Y-%m-%d').date().weekday() < 5]
    if len(rows) < 6:
        raise RuntimeError(f'DXY_ROWS_TOO_FEW:{len(rows)}')
    latest_date = datetime.strptime(rows[-1]['date'], '%Y-%m-%d').date()
    stale_days = (today - latest_date).days
    if stale_days > 7:
        raise RuntimeError(f'DXY_STALE:{latest_date}')
    dxy5 = rows[-1]['close'] / rows[-6]['close'] - 1
    return {
        'status': 'PASS',
        'source': source,
        'symbol': 'DX-Y.NYB',
        'latest_session': rows[-1]['date'],
        'latest_close': rows[-1]['close'],
        'five_sessions_back': rows[-6]['date'],
        'five_sessions_back_close': rows[-6]['close'],
        'dxy_5d': dxy5,
        'rows': len(rows),
        'stale_days': stale_days,
        'refreshed_at_taipei': refreshed_at,
        'causal_rule': 'completed weekday sessions strictly before Taiwan trade date; weekend/current pseudo-bars excluded',
    }


def refresh_dxy(today=None):
    today = today or core.now_tw().date()
    now = core.now_tw()
    period1 = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
    period2 = int(now.astimezone(timezone.utc).timestamp()) + 86400
    errors = []
    for endpoint in DXY_ENDPOINTS:
        try:
            r = requests.get(
                endpoint,
                params={
                    'period1': period1,
                    'period2': period2,
                    'interval': '1d',
                    'events': 'history',
                    'includeAdjustedClose': 'true',
                },
                headers={'User-Agent': 'Mozilla/5.0 HENGCE-Q017-DXY/1.0', 'Accept': 'application/json'},
                timeout=(8, 25),
            )
            r.raise_for_status()
            rows = _dxy_rows_from_yahoo(r.json(), today)
            status = _dxy_status_from_rows(rows, today, f'Yahoo Finance chart {endpoint.split("//",1)[1].split("/",1)[0]} / DX-Y.NYB', now.isoformat())
            DXY_CSV.parent.mkdir(parents=True, exist_ok=True)
            with DXY_CSV.open('w', encoding='utf-8', newline='') as f:
                w = csv.DictWriter(f, fieldnames=['date', 'close'])
                w.writeheader(); w.writerows(rows)
            core.atomic_json(DXY_STATUS, status)
            return status
        except Exception as e:
            errors.append(f'{endpoint}:{type(e).__name__}:{e}')

    # Same-symbol cache is allowed only as a continuity fallback and is still
    # subject to the completed-session freshness test. A different index or
    # futures proxy is never substituted.
    cached = _load_dxy_cache()
    if cached:
        try:
            status = _dxy_status_from_rows(cached, today, 'LOCAL_CACHED_DX-Y.NYB_SAME_SYMBOL', now.isoformat())
            status['network_errors'] = errors
            status['cache_fallback'] = True
            core.atomic_json(DXY_STATUS, status)
            return status
        except Exception as e:
            errors.append(f'CACHE:{type(e).__name__}:{e}')
    raise RuntimeError('DXY_DOWNLOAD_FAIL:' + ' | '.join(errors[-4:]))


def evaluate_market_gate(sf, dxy_status):
    checks = {
        'sox_1d_lte_0': sf['sox_1d'] <= SOX_1D_MAX,
        'sox_5d_lte_minus_3pct': sf['sox_5d'] <= SOX_5D_MAX,
        'dxy_5d_gte_minus_0_5pct': dxy_status['dxy_5d'] >= DXY_5D_MIN,
    }
    return all(checks.values()), checks


def prepare_model(today):
    # Q017 score/beta implementation is preserved. Market-gate thresholds are
    # sourced from the frozen Q017_LOCK_20261018 contract, not the legacy
    # command-center's old -2% SOX-only gate.
    gate = core.premarket(today)
    if gate.get('status') != 'PASS':
        raise RuntimeError(f'PREMARKET_GATE_NOT_PASS:{gate.get("status")}')
    req = gate.get('required') or {}
    seed = req.get('electronics_history') or core.ensure_tw_history()
    sox_status = req.get('sox') or core.refresh_sox(today)
    dxy_status = refresh_dxy(today)
    history = core.load_tw_history()
    srows = core.read_sox()
    sf = core.sox_features(today)
    betas, prevclose, names, hist_date, universe = core.current_betas(history, srows)
    return gate, sox_status, dxy_status, seed, sf, betas, prevclose, names, hist_date, universe


def write_once(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=2) + '\n'
    try:
        with path.open('x', encoding='utf-8') as f:
            f.write(text)
    except FileExistsError:
        existing = json.loads(path.read_text(encoding='utf-8'))
        if canonical_sha(existing) != canonical_sha(obj):
            raise RuntimeError(f'IMMUTABLE_DECISION_CONFLICT:{path}')
        return existing, False
    return obj, True


def capture_decision(today=None):
    today = today or core.now_tw().date()
    p = decision_path(today)
    if p.exists():
        existing = json.loads(p.read_text(encoding='utf-8'))
        core.atomic_json(DECISION_LATEST, existing)
        core.atomic_json(LATEST, existing)
        if existing.get('binding_status') != 'PASS':
            raise RuntimeError('EXISTING_DECISION_SNAPSHOT_IS_DATA_PENDING')
        return existing

    premarket_gate, sox_status, dxy_status, seed, sf, betas, prevclose, names, hist_date, universe = prepare_model(today)
    eligible = [t for t in universe if betas.get(t) is not None and betas.get(t) > 0 and prevclose.get(t)]
    if not eligible:
        raise RuntimeError('NO_ELIGIBLE_BETA_UNIVERSE')

    _, decision_end = wait_for_decision_minute(today)
    capture_started = core.now_tw()
    records = {}
    failures = []
    batch_windows = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(mis_batch, batch): batch for batch in chunks(eligible, BATCH_SIZE)}
        for fut in as_completed(futures):
            batch = futures[fut]
            try:
                result, started, fetched = fut.result()
                records.update(result)
                batch_windows.append((started, fetched))
            except Exception as e:
                failures.append({'tickers': batch, 'error': f'{type(e).__name__}:{e}'})
    capture_finished = core.now_tw()

    in_window = (
        capture_started.hour == DECISION_HOUR
        and capture_started.minute == DECISION_MINUTE
        and capture_finished <= decision_end
        and all(s.hour == DECISION_HOUR and s.minute == DECISION_MINUTE and f <= decision_end for s, f in batch_windows)
    )
    provider_coverage = len(records) / len(eligible)
    binding = 'PASS' if in_window and provider_coverage >= MIN_PROVIDER_COVERAGE else 'DATA_PENDING'

    gate_go, gate_checks = evaluate_market_gate(sf, dxy_status)
    passed_checks = sum(bool(v) for v in gate_checks.values())
    market_state = 'GO' if gate_go else 'WATCH' if passed_checks >= 1 else 'CASH'
    if binding != 'PASS':
        market_state = 'DATA_PENDING'

    candidates = []
    opened = 0
    for t in eligible:
        q = records.get(t)
        if not q:
            continue
        op = q.get('open')
        pc = q.get('reference_close') or prevclose.get(t)
        if op is None or pc in (None, 0):
            continue
        opened += 1
        beta = betas[t]
        gap = op / pc - 1
        expected = beta * sf['sox_1d']
        residual = gap - expected
        if residual > 0.04:
            continue
        score = beta * (1 + 25 * max(-residual, 0))
        candidates.append({
            'ticker': t,
            'name': q.get('name') or names.get(t, ''),
            'beta': beta,
            'open': op,
            'previous_close': pc,
            'gap': gap,
            'expected_gap': expected,
            'residual': residual,
            'score': score,
            'qualified': binding == 'PASS' and gate_go,
            'decision_observed_at_taipei': q.get('fetched_at_taipei'),
        })

    candidates.sort(key=lambda x: x['score'], reverse=True)
    top3 = candidates[:3]

    previous_top = []
    previous_files = sorted([x for x in DECISION_DIR.glob('*_0901.json') if x != p])
    if previous_files:
        try:
            previous_top = [x['ticker'] for x in json.loads(previous_files[-1].read_text(encoding='utf-8')).get('top3', [])]
        except Exception:
            previous_top = []
    current_top = [x['ticker'] for x in top3]
    for x in top3:
        x['new'] = x['ticker'] not in previous_top

    payload = {
        'schema_version': 3,
        'system': 'HENGCE',
        'module': 'Q017_SOX_ELECTRONICS_DECISION_LOCK',
        'trade_date': today.isoformat(),
        'generated_at_taipei': capture_finished.isoformat(),
        'binding_status': binding,
        'market_state': market_state,
        'authority': 'FORMAL_Q017_DECISION_INPUT_NOT_BROKER_ORDER',
        'decision_lock': {
            'cutoff_label': '09:01',
            'capture_window_taipei': '09:01:00-09:01:59.999999',
            'capture_started_at_taipei': capture_started.isoformat(),
            'capture_finished_at_taipei': capture_finished.isoformat(),
            'window_valid': in_window,
            'immutable': True,
            'rerank_after_lock': False,
            'observable_rule': 'ticker is rank-eligible only when open is present in a TWSE MIS response fetched inside the locked decision minute',
            'missing_open_semantics': 'NOT_OPENED_BY_DECISION_CUTOFF_NOT_DATA_FAILURE',
        },
        'data_status': {
            'premarket_gate': premarket_gate,
            'sox': sox_status,
            'dxy': dxy_status,
            'tw_history': seed,
            'tw_history_latest_date': hist_date,
            'eligible_beta_count': len(eligible),
            'provider_returned_count': len(records),
            'provider_coverage': provider_coverage,
            'provider_coverage_required': MIN_PROVIDER_COVERAGE,
            'opened_by_decision_count': opened,
            'batch_failures': failures[:20],
        },
        'market_gate': {
            'gate_go': gate_go,
            'checks': gate_checks,
            'sox_1d': sf['sox_1d'],
            'sox_5d': sf['sox_5d'],
            'dxy_5d': dxy_status['dxy_5d'],
            'source_lock': 'Q017_LOCK_20261018.json',
        },
        'sox': sf,
        'dxy': {
            'session': dxy_status['latest_session'],
            'five_sessions_back': dxy_status['five_sessions_back'],
            'dxy_5d': dxy_status['dxy_5d'],
        },
        'rules': {
            'sox_1d_max': SOX_1D_MAX,
            'sox_5d_max': SOX_5D_MAX,
            'dxy_5d_min': DXY_5D_MIN,
            'residual_max': 0.04,
            'score': 'beta*(1+25*max(-residual,0))',
            'top_n': 3,
            'research_hold_days': 10,
            'authority': 'Q017_LOCK_20261018.json',
        },
        'top3': top3,
        'new': [x['ticker'] for x in top3 if x.get('new')],
        'dropped': [t for t in previous_top if t not in current_top],
        'note': 'Top3 is frozen from the 09:01 causal snapshot. Later monitor runs may update marks only and may not rerank. Frozen market gate is SOX1D<=0, SOX5D<=-3%, DXY5D>=-0.5%.',
    }
    payload['decision_snapshot_sha256'] = canonical_sha({k: v for k, v in payload.items() if k != 'decision_snapshot_sha256'})

    stored, created = write_once(p, payload)
    core.atomic_json(DECISION_LATEST, stored)
    core.atomic_json(LATEST, stored)
    if created:
        stamp = capture_finished.strftime('%Y%m%dT%H%M%S')
        core.atomic_json(HISTORY / f'{stamp}_DECISION_LOCK.json', stored)
        with SIGNAL_LEDGER.open('a', encoding='utf-8') as f:
            f.write(json.dumps({
                'time': stored['generated_at_taipei'],
                'date': stored['trade_date'],
                'event': 'Q017_DECISION_LOCK',
                'market_state': stored['market_state'],
                'gate_go': stored['market_gate']['gate_go'],
                'top3': current_top,
                'decision_snapshot_sha256': stored['decision_snapshot_sha256'],
            }, ensure_ascii=False) + '\n')
    if binding != 'PASS':
        raise RuntimeError(f'DECISION_LOCK_DATA_PENDING:window={in_window}:coverage={provider_coverage:.4f}')
    return stored


def current_marks(top3):
    key = os.environ.get('FUGLE_API_KEY', '').strip()
    marks = []
    for item in top3:
        t = item['ticker']
        price = None
        quote_time = None
        source = None
        if key:
            q, _ = core.fugle_quote(t, key)
            if q:
                lt = q.get('lastTrade') or {}
                price = fnum(lt.get('price'))
                source = 'FUGLE'
        if price is None:
            try:
                recs, _, fetched = mis_batch([t])
                q = recs.get(t) or {}
                price = q.get('last_price') or q.get('best_bid') or q.get('best_ask')
                quote_time = fetched.isoformat()
                source = 'TWSE_MIS'
            except Exception:
                pass
        ret = price / item['open'] - 1 if price is not None and item.get('open') else None
        marks.append({'ticker': t, 'price': price, 'return_from_locked_open': ret, 'source': source, 'quote_time_taipei': quote_time})
    return marks


def monitor(today=None):
    today = today or core.now_tw().date()
    p = decision_path(today)
    if not p.exists():
        payload = {
            'schema_version': 3,
            'system': 'HENGCE',
            'module': 'Q017_SOX_ELECTRONICS_RADAR_LOCKED',
            'trade_date': today.isoformat(),
            'generated_at_taipei': core.now_tw().isoformat(),
            'binding_status': 'DATA_PENDING',
            'market_state': 'DATA_PENDING',
            'authority': 'NO_FORMAL_SIGNAL',
            'formal_buy_count': 0,
            'top3': [],
            'monitor': {'status': 'NO_DECISION_SNAPSHOT', 'rerank_performed': False, 'ranking_frozen': True},
            'policy': 'NO_0901_DECISION_LOCK_NO_FORMAL_SIGNAL',
        }
        core.atomic_json(LATEST, payload)
        raise RuntimeError('NO_IMMUTABLE_0901_DECISION_SNAPSHOT')

    decision = json.loads(p.read_text(encoding='utf-8'))
    if decision.get('binding_status') != 'PASS':
        raise RuntimeError('DECISION_SNAPSHOT_NOT_BINDING')
    locked_hash = decision.get('decision_snapshot_sha256')
    expected_hash = canonical_sha({k: v for k, v in decision.items() if k != 'decision_snapshot_sha256'})
    if locked_hash != expected_hash:
        raise RuntimeError('DECISION_SNAPSHOT_HASH_MISMATCH')

    payload = dict(decision)
    payload['module'] = 'Q017_SOX_ELECTRONICS_RADAR_LOCKED'
    payload['generated_at_taipei'] = core.now_tw().isoformat()
    payload['decision_source_file'] = str(p.relative_to(ROOT))
    payload['monitor'] = {
        'status': 'PASS',
        'rerank_performed': False,
        'ranking_frozen': True,
        'marks': current_marks(decision.get('top3', [])),
    }
    core.atomic_json(LATEST, payload)
    stamp = core.now_tw().strftime('%Y%m%dT%H%M%S')
    core.atomic_json(HISTORY / f'{stamp}_MONITOR.json', payload)
    return payload


def self_test():
    assert DECISION_MINUTE == 1
    assert SOX_1D_MAX == 0.0
    assert SOX_5D_MAX == -0.03
    assert DXY_5D_MIN == -0.005
    sample = {'a': 1, 'b': [2, 3]}
    assert canonical_sha(sample) == canonical_sha({'b': [2, 3], 'a': 1})
    go, checks = evaluate_market_gate({'sox_1d': -0.01, 'sox_5d': -0.03}, {'dxy_5d': -0.004})
    assert go and all(checks.values())
    go2, _ = evaluate_market_gate({'sox_1d': -0.01, 'sox_5d': -0.025}, {'dxy_5d': -0.004})
    assert not go2
    go3, _ = evaluate_market_gate({'sox_1d': -0.01, 'sox_5d': -0.04}, {'dxy_5d': -0.006})
    assert not go3
    print(json.dumps({
        'self_test': 'PASS',
        'cutoff': '09:01',
        'rerank_after_lock': False,
        'frozen_gate': {'sox_1d_max': SOX_1D_MAX, 'sox_5d_max': SOX_5D_MAX, 'dxy_5d_min': DXY_5D_MIN},
    }))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['decision', 'monitor', 'self-test', 'dxy-smoke'], required=True)
    ap.add_argument('--date')
    args = ap.parse_args()
    target = datetime.strptime(args.date, '%Y-%m-%d').date() if args.date else None
    if args.mode == 'self-test':
        self_test(); return 0
    if args.mode == 'dxy-smoke':
        try:
            out = refresh_dxy(target)
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0
        except Exception as e:
            print(json.dumps({'status': 'DATA_PENDING', 'authority': 'NO_FORMAL_SIGNAL', 'error': repr(e)}, ensure_ascii=False, indent=2))
            return 2
    try:
        out = capture_decision(target) if args.mode == 'decision' else monitor(target)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        fail = {
            'system': 'HENGCE',
            'module': 'Q017_DECISION_LOCK',
            'mode': args.mode,
            'generated_at_taipei': core.now_tw().isoformat(),
            'status': 'DATA_PENDING',
            'authority': 'NO_FORMAL_SIGNAL',
            'formal_buy_count': 0,
            'error': repr(e),
            'policy': 'FAIL_CLOSED_NO_FORMAL_SIGNAL',
        }
        core.atomic_json(core.DATA_STATUS, fail)
        print(json.dumps(fail, ensure_ascii=False, indent=2))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
