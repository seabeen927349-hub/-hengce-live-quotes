"""Settle descriptive HBA paths using released evidence, without inferring orders."""
import argparse
import json
import math
from datetime import date, datetime, time
from pathlib import Path

from hengce_hba_context_bridge_v1 import CARD_TZ, card_eod_leg, card_time
from hengce_hba_research_ledger import (LIVE, PREFIX, REPLAY, canonical, key_for,
                                        open_archive, sha, unpack)
from hengce_twse_calendar import CALENDAR_YEAR, is_trading_day, load_manifest, next_trading_day

HORIZONS = (5, 10, 20)
VERSION = 'HENGCE_HBA_RESEARCH_OUTCOMES_V1'


def sessions_after(anchor, calendar):
    day = anchor.date()
    if day.year != CALENDAR_YEAR:
        return []
    opening = datetime.combine(day, time(9), CARD_TZ)
    sessions = [day] if anchor < opening and is_trading_day(day, calendar) else []
    while len(sessions) < max(HORIZONS):
        try:
            day = date.fromisoformat(next_trading_day(day, calendar))
        except ValueError as exc:
            if str(exc) != 'TWSE_CALENDAR_COVERAGE_EXHAUSTED':
                raise
            break
        sessions.append(day)
    return sessions


def positive(value):
    try:
        n = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return n if math.isfinite(n) and n > 0 else None


def released(source, asof):
    return source and source['status'] == 'VERIFIED' and card_time(source['available_at']) <= asof


def settle_one(card, dates, prices, supplemental, policy, asof):
    days = [d.isoformat() for d in dates]
    base = {'start_session': days[0], 'end_session': days[-1], 'sessions': len(days)}
    if asof < datetime.combine(dates[-1], time(13, 30), CARD_TZ):
        return dict(base, status='PENDING')
    ticker = card['ticker']
    evidence = []
    closes, benchmark = [], []
    stock_open, index_open = None, None
    for day in days:
        rows, proof = prices[day]
        if not released(proof, asof):
            status = 'SOURCE_UNVERIFIED' if proof['status'] == 'UNVERIFIED' else 'PRICE_NOT_AVAILABLE'
            return dict(base, status=status, blocked_date=day, reason=proof.get('reason'))
        day_data = supplemental.get(day, {})
        info = day_data.get('stocks', {}).get(ticker, {})
        idx = day_data.get('benchmark', {})
        if not released(info, asof):
            return dict(base, status='TRADEABILITY_OR_CORPORATE_ACTION_UNVERIFIED', blocked_date=day)
        if info.get('trading_status') in ('HALTED', 'DELISTED', 'NOT_TRADABLE'):
            return dict(base, status=info['trading_status'], blocked_date=day)
        if info.get('trading_status') != 'TRADABLE' or info.get('corporate_action') != 'NONE_VERIFIED':
            return dict(base, status='CORPORATE_ACTION_OR_TRADEABILITY_BLOCKED', blocked_date=day)
        row = rows.get(ticker, {})
        close, volume = positive(row.get('Close')), positive(row.get('VolumeShares'))
        if close is None or volume is None:
            return dict(base, status='PRICE_OR_VOLUME_MISSING', blocked_date=day)
        if volume < policy['min_volume_shares']:
            return dict(base, status='INSUFFICIENT_VOLUME', blocked_date=day)
        if not released(idx, asof) or positive(idx.get('close')) is None:
            return dict(base, status='BENCHMARK_UNVERIFIED', blocked_date=day)
        if not closes:
            stock_open, index_open = positive(row.get('Open')), positive(idx.get('open'))
            if stock_open is None or index_open is None:
                return dict(base, status='OPEN_PRICE_MISSING', blocked_date=day)
        closes.append(close)
        benchmark.append(float(idx['close']))
        evidence.append({'date': day, 'price_sha256': proof['sha256'],
                         'tradeability_sha256': info['sha256'], 'benchmark_sha256': idx['sha256']})
    peak, drawdown = stock_open, 0.0
    for close in closes:
        peak = max(peak, close)
        drawdown = max(drawdown, 1-close/peak)
    bps = policy['cost_bps']
    buy = (bps['buy_fee'] + bps['slippage_per_side'])/10000
    sell = (bps['sell_fee'] + bps['sell_tax'] + bps['slippage_per_side'])/10000
    stock_return = closes[-1]/stock_open-1
    index_return = benchmark[-1]/index_open-1
    zone = card['research']['invalidation']
    breach = {'status': 'UNVERIFIED'}
    if zone['status'] == 'VERIFIED':
        breach = {'status': 'NOT_OBSERVED'}
        for day, close in zip(days, closes):
            if close < zone['downside_below_twd'] or close > zone['upside_above_twd']:
                breach = {'status': 'OBSERVED', 'date': day, 'close': close,
                          'side': 'BELOW' if close < zone['downside_below_twd'] else 'ABOVE'}
                break
    return dict(base, status='SETTLED_DESCRIPTIVE', entry_open=stock_open, end_close=closes[-1],
                gross_return=stock_return, benchmark_return=index_return,
                gross_excess_return=stock_return-index_return, max_drawdown=drawdown,
                illustrative_net_long_return=closes[-1]*(1-sell)/(stock_open*(1+buy))-1,
                range_invalidation=breach, evidence=evidence)


def settlement(record, receipt, ticker, root, asof, policy=None, supplemental=None):
    _, cards = unpack(record)
    formed = card_time(record['formed_at_taipei'])
    if receipt:
        if record['mode'] != LIVE or receipt['key'] != key_for(record):
            raise ValueError('INVALID_PROSPECTIVE_RECEIPT')
        anchor = card_time(receipt['published_at_taipei'])
        if anchor < formed.replace(microsecond=0):
            raise ValueError('PUBLICATION_BEFORE_FORMATION')
    else:
        if record['mode'] != REPLAY:
            raise ValueError('PROSPECTIVE_RECEIPT_REQUIRED')
        anchor = formed
    if asof < anchor:
        raise ValueError('SETTLEMENT_BEFORE_ANCHOR')
    calendar, _, calendar_sha = load_manifest()
    days = sessions_after(anchor, calendar)
    prices = {}
    for day in days:
        if datetime.combine(day, time(13, 30), CARD_TZ) <= asof:
            prices[day.isoformat()] = card_eod_leg(root, day.isoformat(), 'price', asof)
    def outcomes(card):
        results = {}
        for n in HORIZONS:
            window = days[:n]
            if len(window) < n:
                results[str(n)] = {'status': 'TRADING_CALENDAR_UNVERIFIED', 'sessions': len(window)}
            elif datetime.combine(window[-1], time(13, 30), CARD_TZ) > asof or policy is not None:
                results[str(n)] = settle_one(card, window, prices, supplemental or {}, policy, asof)
            else:
                results[str(n)] = {'status': 'SETTLEMENT_POLICY_OR_SUPPLEMENT_UNVERIFIED',
                                   'start_session': window[0].isoformat(), 'end_session': window[-1].isoformat()}
        symbol = card['ticker']
        return {'ticker': symbol, 'stock_event_id': sha(canonical([record['snapshot_id'], symbol])),
                'results': results}

    result = {'schema': VERSION, 'mode': record['mode'], 'snapshot_id': record['snapshot_id'],
              'snapshot_sha256': sha(canonical(record)), 'reference_time_taipei': anchor.isoformat(),
              'asof_taipei': asof.isoformat(), 'calendar_sha256': calendar_sha, 'publication_receipt': receipt,
              'interpretation': 'DESCRIPTIVE_PRICE_PATH_ONLY_NO_DIRECTION_LABEL_OR_ORDERS'}
    if ticker is None:
        return {**result, 'stocks': [outcomes(card) for card in cards.values()]}
    return {**result, **outcomes(cards[ticker])}


def load_inputs(data, expected_sha):
    if sha(data) != expected_sha:
        raise ValueError('SETTLEMENT_INPUT_SHA_MISMATCH')
    inputs = json.loads(data)
    policy = inputs['policy']
    volume = policy['min_volume_shares']
    if (policy['version'] != VERSION or policy['benchmark'] != 'TAIEX'
            or type(volume) is not int or volume <= 0
            or set(policy['cost_bps']) != {'buy_fee', 'sell_fee', 'sell_tax', 'slippage_per_side'}
            or any(type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 500
                   for x in policy['cost_bps'].values())):
        raise ValueError('SETTLEMENT_POLICY_INVALID')
    for day, row in inputs['sessions'].items():
        day = date.fromisoformat(day)
        for evidence in [row['benchmark'], *row['stocks'].values()]:
            if (evidence['effective_date'] != day.isoformat()
                    or card_time(evidence['available_at']) < datetime.combine(day, time(13, 30), CARD_TZ)
                    or len(bytes.fromhex(evidence['sha256'])) != 32
                    or not evidence['source']):
                raise ValueError('SUPPLEMENTAL_PROVENANCE_INVALID')
    return policy, inputs['sessions']


def main():
    p = argparse.ArgumentParser()
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--replay', type=Path)
    source.add_argument('--bucket')
    p.add_argument('--owner')
    p.add_argument('--key')
    p.add_argument('--version-id')
    scope = p.add_mutually_exclusive_group(required=True)
    scope.add_argument('--ticker')
    scope.add_argument('--all', action='store_true')
    p.add_argument('--root', type=Path, default=Path('.'))
    p.add_argument('--historical-asof')
    p.add_argument('--inputs', type=Path)
    p.add_argument('--inputs-sha')
    p.add_argument('--reference-key')
    p.add_argument('--reference-version')
    args = p.parse_args()
    if bool(args.inputs) != bool(args.inputs_sha):
        p.error('--inputs and --inputs-sha must be supplied together')
    if (args.bucket and args.inputs) or (args.replay and args.reference_key):
        p.error('reference storage must match the observation mode')
    if bool(args.reference_key) != bool(args.reference_version):
        p.error('reference key and version must be supplied together')
    policy, supplemental = load_inputs(args.inputs.read_bytes(), args.inputs_sha) if args.inputs else (None, None)
    reference = None
    receipt = None
    if args.replay:
        record = json.loads(args.replay.read_bytes())
        if record['mode'] != REPLAY:
            p.error('local records are historical replay only')
        asof = card_time(args.historical_asof) if args.historical_asof else datetime.now(CARD_TZ)
    else:
        if not args.key or not args.version_id or args.historical_asof:
            p.error('prospective settlement requires an exact object key and version and uses the live clock')
        archive = open_archive(args.bucket, args.owner)
        raw, receipt = archive.read(args.key, args.version_id)
        record = json.loads(raw)
        asof = datetime.now(CARD_TZ)
        if args.reference_key:
            if not args.reference_key.startswith(f'{PREFIX}/references/'):
                p.error('use the separate governed reference prefix')
            inputs, reference = archive.read(args.reference_key, args.reference_version)
            if card_time(reference['published_at_taipei']) > asof:
                p.error('reference publication is after settlement cutoff')
            policy, supplemental = load_inputs(inputs, reference['sha256'])
    result = settlement(record, receipt, args.ticker, args.root, asof, policy, supplemental)
    if args.inputs:
        result['inputs_sha256'] = args.inputs_sha
    rows = result.get('stocks', [result])
    if receipt and any(window['status'] != 'PENDING' for row in rows for window in row['results'].values()):
        result['reference_receipt'] = reference
        # Keep repeated evaluations of the same evidence byte-identical. The
        # store supplies the write time and preserves any subsequent revision.
        data = canonical({k: v for k, v in result.items() if k != 'asof_taipei'})
        event = result.get('stock_event_id', record['snapshot_id'])
        key = f"{PREFIX}/{LIVE}/outcomes/{event}/{sha(data)}.json"
        result['result_receipt'] = archive.create(key, data)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
