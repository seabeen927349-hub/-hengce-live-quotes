#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

Q017 = Path('hengce/q017_radar/latest.json')
SHADOW = Path('shadow/full_market_latest.json')
CONTRACT = Path('hengce/HENGCE_ELECTRONICS_LIVE_COVERAGE_CONTRACT_v1_0_20261022.json')
ROUTING = Path('hengce/HENGCE_LIVE_COVERAGE_ROUTING_v1_0_20261022.json')
OUT = Path('hengce/electronics_live/latest.json')
STATUS = Path('hengce/electronics_live/status.json')
ROLE = 'ELECTRONICS_QUOTE_CONTEXT_ONLY_NO_RANKING_SIGNAL_CAPITAL_AUTHORITY'
SCOPE = 'TWSE_LISTED_ELECTRONICS_ONLY'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def dump(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha_obj(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def false_authority():
    return {'ranking_authority': False, 'signal_authority': False, 'capital_authority': False, 'broker_order_execution': False}


def validate_contract(c, routing):
    if c.get('module') != 'HENGCE_ELECTRONICS_LIVE_COVERAGE' or c.get('role') != ROLE:
        raise SystemExit('ELECTRONICS_LIVE_CONTRACT_IDENTITY_MISMATCH')
    if c.get('universe_scope') != SCOPE:
        raise SystemExit('ELECTRONICS_LIVE_CONTRACT_SCOPE_MISMATCH')
    for k in ('membership', 'ranking', 'signal', 'capital', 'broker_execution'):
        if (c.get('authority') or {}).get(k) is not False:
            raise SystemExit('ELECTRONICS_LIVE_CONTRACT_AUTHORITY_MUST_BE_FALSE:' + k)
    locks = c.get('locks') or {}
    required_true = (
        'cover_all_q017_electronics_members',
        'cash_state_does_not_reduce_coverage',
        'missing_member_degrades_health',
        'bid_ask_never_promoted_to_executed_trade',
        'intraday_rerank_forbidden',
    )
    for k in required_true:
        if locks.get(k) is not True:
            raise SystemExit('ELECTRONICS_LIVE_CONTRACT_LOCK_MISSING:' + k)
    if routing.get('canonical_all_electronics_live_artifact') != str(OUT):
        raise SystemExit('LIVE_COVERAGE_ROUTING_CANONICAL_PATH_MISMATCH')
    if routing.get('legacy_priority_watchlist_is_all_electronics') is not False:
        raise SystemExit('LIVE_COVERAGE_ROUTING_LEGACY_SCOPE_MISMATCH')


def q017_members(q):
    if q.get('binding_status') != 'PASS':
        raise SystemExit('Q017_BINDING_NOT_PASS')
    u = q.get('universe_lock') or {}
    if u.get('scope') != SCOPE:
        raise SystemExit('Q017_UNIVERSE_SCOPE_MISMATCH')
    members = [str(x) for x in (u.get('members') or [])]
    if not members or len(members) != len(set(members)):
        raise SystemExit('Q017_UNIVERSE_MEMBERS_INVALID')
    if int(u.get('member_count') or -1) != len(members):
        raise SystemExit('Q017_UNIVERSE_MEMBER_COUNT_MISMATCH')
    return members, u


def shadow_map(s):
    if s.get('service') != 'HENGCE_FULL_MARKET_ROLLING_SHADOW':
        raise SystemExit('FULL_MARKET_SHADOW_IDENTITY_MISMATCH')
    if s.get('authority') != 'SHADOW_CONTEXT_ONLY_NO_CAPITAL_AUTHORITY':
        raise SystemExit('FULL_MARKET_SHADOW_AUTHORITY_MISMATCH')
    rows = s.get('quotes') or []
    out = {}
    for row in rows:
        t = str(row.get('ticker') or '')
        if not t:
            continue
        if t in out:
            raise SystemExit('FULL_MARKET_SHADOW_DUPLICATE_TICKER:' + t)
        out[t] = row
    return out


def display_fields(row):
    last = row.get('last_price')
    bid = row.get('best_bid')
    ask = row.get('best_ask')
    indicative = None
    basis = None
    if bid is not None and ask is not None:
        indicative = (float(bid) + float(ask)) / 2.0
        basis = 'BID_ASK_MIDPOINT_NON_EXECUTION'
    elif bid is not None:
        indicative = float(bid)
        basis = 'BEST_BID_NON_EXECUTION'
    elif ask is not None:
        indicative = float(ask)
        basis = 'BEST_ASK_NON_EXECUTION'
    if last is not None:
        return float(last), 'LAST_EXECUTED_TRADE', True, indicative, basis
    if indicative is not None:
        return indicative, basis, False, indicative, basis
    return None, 'NO_CURRENT_PRICE_AVAILABLE', False, None, None


def derive(q, s):
    members, u = q017_members(q)
    smap = shadow_map(s)
    rows = []
    missing = []
    for t in members:
        src = smap.get(t)
        if src is None:
            missing.append(t)
            src = {'ticker': t, 'name': None, 'fetch_ok': False, 'quote_fresh': False, 'trade_fresh': False, 'source': 'NONE'}
        display_price, semantics, executed, indicative, indicative_basis = display_fields(src)
        row = {
            'ticker': t,
            'name': src.get('name'),
            'display_price': display_price,
            'display_price_semantics': semantics,
            'executed_price_available': executed,
            'last_executed_price': src.get('last_price'),
            'indicative_price': indicative,
            'indicative_price_semantics': indicative_basis,
            'reference_close': src.get('reference_close'),
            'open': src.get('open'),
            'high': src.get('high'),
            'low': src.get('low'),
            'best_bid': src.get('best_bid'),
            'best_ask': src.get('best_ask'),
            'volume_lots': src.get('volume_lots'),
            'trade_time': src.get('trade_time'),
            'trade_freshness_seconds': src.get('trade_freshness_seconds'),
            'quote_freshness_seconds': src.get('quote_freshness_seconds'),
            'quote_fresh': bool(src.get('quote_fresh')),
            'trade_fresh': bool(src.get('trade_fresh')),
            'fetch_ok': bool(src.get('fetch_ok')),
            'source': src.get('source'),
            'transport_tier': src.get('tier'),
            **false_authority(),
        }
        rows.append(row)
    count = len(members)
    provider = sum(r['fetch_ok'] for r in rows)
    qfresh = sum(r['fetch_ok'] and r['quote_fresh'] for r in rows)
    trade = sum(r['executed_price_available'] for r in rows)
    indicative = sum(r['indicative_price'] is not None for r in rows)
    price_available = sum(r['display_price'] is not None for r in rows)
    coverage = provider / count if count else 0.0
    fresh_ratio = qfresh / count if count else 0.0
    shadow_gate = bool((s.get('full_market_gate') or {}).get('pass'))
    healthy = (not missing and provider == count and fresh_ratio >= 0.98 and shadow_gate)
    payload = {
        'schema_version': 1,
        'system': 'HENGCE',
        'artifact': 'ELECTRONICS_LIVE_COVERAGE',
        'authority': ROLE,
        'scope': SCOPE,
        'generated_at_taipei': s.get('generated_at_taipei'),
        'snapshot_id': s.get('snapshot_id'),
        'source_q017_trade_date': q.get('trade_date'),
        'source_q017_market_state': q.get('market_state'),
        'source_q017_binding_status': q.get('binding_status'),
        'source_q017_membership_date': u.get('membership_date'),
        'source_q017_universe_sha256': u.get('universe_sha256'),
        'source_full_market_payload_sha256': s.get('payload_sha256'),
        'source_full_market_status': s.get('status'),
        'member_count': count,
        'provider_covered_count': provider,
        'quote_fresh_count': qfresh,
        'executed_price_available_count': trade,
        'indicative_price_available_count': indicative,
        'display_price_available_count': price_available,
        'provider_coverage_ratio': coverage,
        'quote_fresh_ratio': fresh_ratio,
        'missing_member_count': len(missing),
        'missing_members': missing,
        'full_market_gate_pass': shadow_gate,
        'status': 'PASS_FULL_ELECTRONICS_LIVE_COVERAGE' if healthy else 'DEGRADED_ELECTRONICS_LIVE_COVERAGE',
        'fully_healthy': healthy,
        'cash_state_does_not_reduce_coverage': True,
        'intraday_rerank_performed': False,
        'formal_q017_decision_immutable': True,
        'legacy_77_watchlist_is_not_coverage_authority': True,
        **false_authority(),
        'rows': rows,
    }
    payload['payload_sha256'] = sha_obj({k: v for k, v in payload.items() if k != 'payload_sha256'})
    return payload


def validate_payload(p, q):
    members, _ = q017_members(q)
    if p.get('authority') != ROLE or p.get('scope') != SCOPE:
        raise SystemExit('ELECTRONICS_LIVE_OUTPUT_IDENTITY_MISMATCH')
    rows = p.get('rows') or []
    tickers = [str(r.get('ticker')) for r in rows]
    if tickers != members:
        raise SystemExit('ELECTRONICS_LIVE_OUTPUT_MEMBER_SET_MISMATCH')
    if int(p.get('member_count') or -1) != len(members):
        raise SystemExit('ELECTRONICS_LIVE_OUTPUT_COUNT_MISMATCH')
    for k in ('ranking_authority', 'signal_authority', 'capital_authority', 'broker_order_execution'):
        if p.get(k) is not False:
            raise SystemExit('ELECTRONICS_LIVE_TOPLEVEL_AUTHORITY_VIOLATION:' + k)
    if p.get('intraday_rerank_performed') is not False or p.get('formal_q017_decision_immutable') is not True:
        raise SystemExit('ELECTRONICS_LIVE_RERANK_LOCK_VIOLATION')
    for r in rows:
        for k in ('ranking_authority', 'signal_authority', 'capital_authority', 'broker_order_execution'):
            if r.get(k) is not False:
                raise SystemExit('ELECTRONICS_LIVE_ROW_AUTHORITY_VIOLATION:' + str(r.get('ticker')) + ':' + k)
        if r.get('last_executed_price') is None and r.get('executed_price_available') is not False:
            raise SystemExit('NON_EXECUTED_PRICE_PROMOTED:' + str(r.get('ticker')))
        if r.get('last_executed_price') is None and r.get('display_price') is not None and 'NON_EXECUTION' not in str(r.get('display_price_semantics')):
            raise SystemExit('INDICATIVE_PRICE_SEMANTICS_INVALID:' + str(r.get('ticker')))
    missing = [r['ticker'] for r in rows if not r.get('fetch_ok')]
    if missing and p.get('fully_healthy') is not False:
        raise SystemExit('MISSING_MEMBER_FALSE_HEALTHY')
    return True


def build():
    c = load(CONTRACT)
    routing = load(ROUTING)
    validate_contract(c, routing)
    q = load(Q017)
    s = load(SHADOW)
    p = derive(q, s)
    validate_payload(p, q)
    dump(OUT, p)
    st = {k: v for k, v in p.items() if k != 'rows'}
    dump(STATUS, st)
    print(json.dumps({k: p[k] for k in ('snapshot_id', 'member_count', 'provider_covered_count', 'quote_fresh_count', 'executed_price_available_count', 'indicative_price_available_count', 'missing_member_count', 'status', 'fully_healthy')}, ensure_ascii=False, indent=2))


def validate():
    c = load(CONTRACT)
    routing = load(ROUTING)
    validate_contract(c, routing)
    q = load(Q017)
    p = load(OUT)
    validate_payload(p, q)
    print(json.dumps({'validate': 'PASS', 'member_count': p.get('member_count'), 'status': p.get('status'), 'fully_healthy': p.get('fully_healthy'), 'ranking_authority': False, 'signal_authority': False, 'capital_authority': False, 'broker_order_execution': False}, ensure_ascii=False))


def self_test():
    q = {'binding_status': 'PASS', 'trade_date': '2026-10-22', 'market_state': 'CASH', 'universe_lock': {'scope': SCOPE, 'membership_date': '2026-10-21', 'member_count': 3, 'universe_sha256': 'u', 'members': ['3042', '8150', '3055']}}
    baseq = lambda t, **kw: {'ticker': t, 'name': t, 'last_price': kw.get('last_price', 100.0), 'best_bid': kw.get('best_bid', 99.9), 'best_ask': kw.get('best_ask', 100.1), 'reference_close': 99.0, 'open': 100.0, 'high': 101.0, 'low': 98.0, 'volume_lots': 1000, 'trade_time': '2026-10-22T12:00:00+08:00', 'trade_freshness_seconds': 1, 'quote_freshness_seconds': 1, 'quote_fresh': True, 'trade_fresh': True, 'fetch_ok': True, 'source': 'TWSE_MIS', 'tier': 'TIER_3_MARKET'}
    s = {'service': 'HENGCE_FULL_MARKET_ROLLING_SHADOW', 'authority': 'SHADOW_CONTEXT_ONLY_NO_CAPITAL_AUTHORITY', 'generated_at_taipei': '2026-10-22T12:00:00+08:00', 'snapshot_id': 'S', 'payload_sha256': 'p', 'status': 'SHADOW_FULL_MARKET_READY', 'full_market_gate': {'pass': True}, 'quotes': [baseq('3042'), baseq('8150', last_price=None, best_bid=99.0, best_ask=99.1), baseq('3055'), baseq('2330')]}
    s['quotes'][1]['last_price'] = None
    p = derive(q, s)
    validate_payload(p, q)
    assert p['member_count'] == 3 and len(p['rows']) == 3
    assert p['source_q017_market_state'] == 'CASH' and p['cash_state_does_not_reduce_coverage'] is True
    r = [x for x in p['rows'] if x['ticker'] == '8150'][0]
    assert r['executed_price_available'] is False and r['display_price'] == 99.05
    assert 'NON_EXECUTION' in r['display_price_semantics']
    assert all(x['ticker'] != '2330' for x in p['rows'])
    assert p['fully_healthy'] is True
    s2 = json.loads(json.dumps(s))
    s2['quotes'] = [x for x in s2['quotes'] if x['ticker'] != '8150']
    p2 = derive(q, s2)
    validate_payload(p2, q)
    assert p2['fully_healthy'] is False and p2['missing_members'] == ['8150']
    s3 = json.loads(json.dumps(s))
    s3['quotes'].append(json.loads(json.dumps(s3['quotes'][0])))
    try:
        derive(q, s3)
        raise AssertionError('duplicate not rejected')
    except SystemExit as e:
        assert 'DUPLICATE_TICKER' in str(e)
    qbad = json.loads(json.dumps(q))
    qbad['universe_lock']['member_count'] = 4
    try:
        derive(qbad, s)
        raise AssertionError('bad count not rejected')
    except SystemExit as e:
        assert 'MEMBER_COUNT_MISMATCH' in str(e)
    assert all(p[k] is False for k in ('ranking_authority', 'signal_authority', 'capital_authority', 'broker_order_execution'))
    print(json.dumps({'self_test': 'PASS', 'three_member_cash_full_coverage': True, '8150_bid_ask_not_promoted_to_trade': True, 'non_electronics_ignored': True, 'missing_member_degrades_health': True, 'duplicate_quote_rejected': True, 'membership_count_mismatch_rejected': True, 'intraday_rerank_forbidden': True, 'zero_authority': True}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=('build', 'validate', 'self-test'), default='build')
    a = ap.parse_args()
    {'build': build, 'validate': validate, 'self-test': self_test}[a.mode]()


if __name__ == '__main__':
    main()
