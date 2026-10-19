#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time as dtime
from pathlib import Path

import requests

import hengce_daily_command_center as core

TZ = core.TZ
ROOT = core.ROOT
RADAR = core.RADAR
HISTORY = core.HISTORY
LATEST = core.LATEST
SIGNAL_LEDGER = core.SIGNAL_LEDGER
DECISION_DIR = RADAR / 'decision'
DECISION_LATEST = RADAR / 'decision_latest.json'
MIS_URL = 'https://mis.twse.com.tw/stock/api/getStockInfo.jsp'
DECISION_HOUR = 9
DECISION_MINUTE = 1
DECISION_SECOND = 5
MIN_PROVIDER_COVERAGE = 0.98
BATCH_SIZE = 40
WORKERS = 10

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


def prepare_model(today):
    # Preserve the command-center's currently locked model thresholds and beta implementation.
    # The decision layer additionally enforces the command-center contract's premarket PASS dependency.
    gate = core.premarket(today)
    if gate.get('status') != 'PASS':
        raise RuntimeError(f'PREMARKET_GATE_NOT_PASS:{gate.get("status")}')
    req = gate.get('required') or {}
    eod_date = str(req.get('latest_eod_date') or '')
    hist_gate_date = str(req.get('electronics_history_latest') or '').replace('-', '')
    if not eod_date or not hist_gate_date or eod_date != hist_gate_date:
        raise RuntimeError(f'PREMARKET_DATE_MISMATCH:EOD={eod_date}:HISTORY={hist_gate_date}')
    seed = req.get('electronics_history') or core.ensure_tw_history()
    sox_status = req.get('sox') or core.refresh_sox(today)
    history = core.load_tw_history()
    srows = core.read_sox()
    sf = core.sox_features(today)
    betas, prevclose, names, hist_date, universe = core.current_betas(history, srows)
    return gate, sox_status, seed, sf, betas, prevclose, names, hist_date, universe


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

    premarket_gate, sox_status, seed, sf, betas, prevclose, names, hist_date, universe = prepare_model(today)
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

    one = sf['sox_1d'] <= 0.0
    five = sf['sox_5d'] <= -0.02
    market_state = 'GO' if one and five else 'WATCH' if one or five else 'CASH'
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
            # This is valid causal absence: no open was observable inside the locked minute.
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
            'qualified': binding == 'PASS' and market_state == 'GO',
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
        'schema_version': 2,
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
            'tw_history': seed,
            'tw_history_latest_date': hist_date,
            'eligible_beta_count': len(eligible),
            'provider_returned_count': len(records),
            'provider_coverage': provider_coverage,
            'provider_coverage_required': MIN_PROVIDER_COVERAGE,
            'opened_by_decision_count': opened,
            'batch_failures': failures[:20],
        },
        'sox': sf,
        'rules': {
            'sox_1d_max': 0.0,
            'sox_5d_max': -0.02,
            'residual_max': 0.04,
            'score': 'beta*(1+25*max(-residual,0))',
            'top_n': 3,
            'research_hold_days': 10,
        },
        'top3': top3,
        'new': [x['ticker'] for x in top3 if x.get('new')],
        'dropped': [t for t in previous_top if t not in current_top],
        'note': 'Top3 is frozen from the 09:01 causal snapshot. Later radar runs may update marks only and may not rerank.',
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
            'schema_version': 2,
            'system': 'HENGCE',
            'module': 'Q017_SOX_ELECTRONICS_RADAR_LOCKED',
            'trade_date': today.isoformat(),
            'generated_at_taipei': core.now_tw().isoformat(),
            'binding_status': 'DATA_PENDING',
            'market_state': 'DATA_PENDING',
            'top3': [],
            'monitor': {'status': 'NO_DECISION_SNAPSHOT', 'rerank_performed': False},
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
    sample = {'a': 1, 'b': [2, 3]}
    assert canonical_sha(sample) == canonical_sha({'b': [2, 3], 'a': 1})
    print(json.dumps({'self_test': 'PASS', 'cutoff': '09:01', 'rerank_after_lock': False}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['decision', 'monitor', 'self-test'], required=True)
    ap.add_argument('--date')
    args = ap.parse_args()
    target = datetime.strptime(args.date, '%Y-%m-%d').date() if args.date else None
    if args.mode == 'self-test':
        self_test(); return 0
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
            'error': repr(e),
            'policy': 'FAIL_CLOSED_NO_FORMAL_SIGNAL',
        }
        core.atomic_json(core.DATA_STATUS, fail)
        print(json.dumps(fail, ensure_ascii=False, indent=2))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
