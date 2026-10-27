#!/usr/bin/env python3
from __future__ import annotations

import json, math, statistics, time, urllib.parse, urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Reuse W1's PIT electronics universe, 2023-fitted tail score and fail-closed
# t+1-close -> t+2-open outcome mechanic. No prior result is used to tune T86.
import research.codex_full_reset_20261023.nextday_w1_wide_tail_basket as w1

ROOT = Path(__file__).resolve().parents[2]
RESET = ROOT / 'research' / 'codex_full_reset_20261023'
OUT = RESET / 'nextday_t86_institutional_challenger_result.json'
EVENTS = RESET / 'nextday_t86_institutional_challenger_events.jsonl'
CACHE = RESET / 'nextday_t86_cache_2024_2026.json'

PRIMARY_COST = 0.002
COSTS = (0.0, 0.002, 0.004, 0.006, 0.008)
BASKET = 20
PERIODS = {'2024': w1.DEV, '2025': w1.VAL, '2026': w1.DIAG}
MIN_COVERAGE = 0.95


def fnum(x):
    try:
        return float(str(x).replace(',', '').strip())
    except Exception:
        return 0.0


def field_index(fields, pred):
    for i, f in enumerate(fields):
        if pred(str(f).replace(' ', '')):
            return i
    return None


def fetch_t86(d):
    ymd = d.replace('-', '')
    q = urllib.parse.urlencode({'date': ymd, 'selectType': 'ALLBUT0999', 'response': 'json'})
    url = 'https://www.twse.com.tw/rwd/zh/fund/T86?' + q
    last = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 HENGCE-research/1.0',
                'Accept': 'application/json,text/plain,*/*',
            })
            with urllib.request.urlopen(req, timeout=25) as r:
                obj = json.loads(r.read().decode('utf-8-sig'))
            fields = obj.get('fields') or []
            data = obj.get('data') or []
            if not fields or not data:
                raise RuntimeError('EMPTY_T86')
            ix_code = field_index(fields, lambda s: '證券代號' in s)
            ix_foreign = field_index(fields, lambda s: '外陸資買賣超股數' in s and '不含外資自營商' in s)
            ix_trust = field_index(fields, lambda s: '投信買賣超股數' in s)
            ix_dealer = field_index(fields, lambda s: s == '自營商買賣超股數')
            ix_total = field_index(fields, lambda s: '三大法人買賣超股數' in s)
            needed = (ix_code, ix_foreign, ix_trust, ix_total)
            if any(x is None for x in needed):
                raise RuntimeError('T86_SCHEMA:' + '|'.join(map(str, fields)))
            out = {}
            for row in data:
                if not row or ix_code >= len(row):
                    continue
                t = str(row[ix_code]).strip()
                if not (len(t) == 4 and t.isdigit()):
                    continue
                out[t] = {
                    'foreign': fnum(row[ix_foreign]),
                    'trust': fnum(row[ix_trust]),
                    'dealer': fnum(row[ix_dealer]) if ix_dealer is not None and ix_dealer < len(row) else 0.0,
                    'total': fnum(row[ix_total]),
                }
            if not out:
                raise RuntimeError('NO_TICKERS')
            return d, out, None
        except Exception as e:
            last = repr(e)
            time.sleep(0.35 * (attempt + 1))
    return d, None, last


def ranks(pairs):
    a = sorted(pairs, key=lambda z: (z[1], z[0]))
    n = len(a); out = {}; i = 0
    while i < n:
        j = i + 1
        while j < n and a[j][1] == a[i][1]:
            j += 1
        p = ((i + j - 1) / 2 + 0.5) / n
        for k in range(i, j):
            out[a[k][0]] = p
        i = j
    return out


def wilson(w, n, z=1.959963984540054):
    if not n:
        return None
    p = w / n; z2 = z*z; den = 1 + z2/n
    return (p + z2/(2*n) - z*math.sqrt(p*(1-p)/n + z2/(4*n*n))) / den


def metric(rs, cost):
    xs = [r['gross_return'] - cost for r in rs]
    n = len(xs); wins = sum(x > 0 for x in xs)
    nav = peak = 1.0; mdd = 0.0; cur = mx = 0
    for x in xs:
        nav *= 1 + x; peak = max(peak, nav); mdd = min(mdd, nav/peak - 1)
        if x <= 0:
            cur += 1; mx = max(mx, cur)
        else:
            cur = 0
    legs = sum(r['legs'] for r in rs); bad = sum(r['fail_closed_legs'] for r in rs)
    tc = Counter(t for r in rs for t in r['tickers'])
    return {
        'nights': n, 'wins': wins, 'losses': n-wins,
        'win_rate': wins/n if n else None, 'wilson95_lower': wilson(wins, n),
        'mean_return': statistics.mean(xs) if xs else None,
        'median_return': statistics.median(xs) if xs else None,
        'worst_return': min(xs) if xs else None, 'best_return': max(xs) if xs else None,
        'compounded_return': nav-1 if n else 0.0, 'max_drawdown': mdd,
        'max_consecutive_losses': mx, 'underlying_legs': legs,
        'fail_closed_legs': bad, 'fail_closed_leg_share': bad/legs if legs else None,
        'top_ticker_leg_share': max(tc.values())/legs if legs and tc else None,
    }


def split(rs, p):
    return [r for r in rs if p[0] <= r['signal_date'] <= p[1]]


def stress(rs):
    return {str(c): metric(rs, c) for c in COSTS}


# Only dates actually needed by the fixed 2024-2026 W1 signal-time panel.
dates = sorted(d for d in w1.panels if w1.DEV[0] <= d <= w1.DIAG[1])
cache = {}
if CACHE.exists():
    try:
        cache = json.loads(CACHE.read_text(encoding='utf-8'))
    except Exception:
        cache = {}
missing = [d for d in dates if d not in cache]
errors = {}
if missing:
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(fetch_t86, d) for d in missing]
        for fut in as_completed(futs):
            d, rows, err = fut.result()
            if rows is not None:
                cache[d] = rows
            else:
                errors[d] = err
CACHE.write_text(json.dumps(cache, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')

strategies = {
    'T86_TOTAL20': [],
    'T86_FOREIGN_TRUST20': [],
    'W1_T86_EQUAL_BLEND20': [],
    'W1_TOP25_T86_VETO20': [],
}
coverage_dates = []

for d in dates:
    inst = cache.get(d)
    stocks = w1.panels.get(d) or []
    if not inst or len(stocks) < BASKET:
        continue
    scored = []
    for s in stocks:
        t = s['ticker']; flow = inst.get(t)
        px = w1.raw.by[d].get(t)
        if not flow or not px or px['c'] <= 0 or px['turn'] <= 0:
            continue
        # Approximate traded shares from turnover NTD / close; only used for
        # cross-sectional scale normalization, not for P&L.
        traded_shares = px['turn'] / px['c']
        if traded_shares <= 0:
            continue
        q = dict(s)
        q['tail_score'] = w1.tail_score(s)
        q['foreign_ratio'] = flow['foreign'] / traded_shares
        q['trust_ratio'] = flow['trust'] / traded_shares
        q['dealer_ratio'] = flow['dealer'] / traded_shares
        q['total_ratio'] = flow['total'] / traded_shares
        scored.append(q)
    if len(scored) < 25:
        continue
    r_foreign = ranks([(q['ticker'], q['foreign_ratio']) for q in scored])
    r_trust = ranks([(q['ticker'], q['trust_ratio']) for q in scored])
    r_total = ranks([(q['ticker'], q['total_ratio']) for q in scored])
    r_tail = ranks([(q['ticker'], q['tail_score']) for q in scored])
    for q in scored:
        t = q['ticker']
        q['ft_consensus'] = 0.5*(r_foreign[t] + r_trust[t])
        q['total_rank'] = r_total[t]
        q['tail_rank'] = r_tail[t]
        q['blend'] = 0.5*(q['tail_rank'] + q['ft_consensus'])

    w1_top25 = sorted(scored, key=lambda z: (-z['tail_score'], z['ticker']))[:25]
    picks = {
        'T86_TOTAL20': sorted(scored, key=lambda z: (-z['total_rank'], z['ticker']))[:20],
        'T86_FOREIGN_TRUST20': sorted(scored, key=lambda z: (-z['ft_consensus'], z['ticker']))[:20],
        'W1_T86_EQUAL_BLEND20': sorted(scored, key=lambda z: (-z['blend'], z['ticker']))[:20],
        'W1_TOP25_T86_VETO20': sorted(w1_top25, key=lambda z: (-z['ft_consensus'], -z['tail_score'], z['ticker']))[:20],
    }
    coverage_dates.append(d)
    for name, chosen in picks.items():
        gross = []; bad = 0
        for q in chosen:
            g, is_bad = w1.future_overnight(d, q['ticker'], fail_closed=True)
            gross.append(g); bad += int(is_bad)
        strategies[name].append({
            'signal_date': d, 'tickers': [q['ticker'] for q in chosen],
            'legs': len(chosen), 'gross_return': statistics.mean(gross),
            'fail_closed_legs': bad,
            'mean_ft_consensus': statistics.mean(q['ft_consensus'] for q in chosen),
            'mean_total_rank': statistics.mean(q['total_rank'] for q in chosen),
            'mean_tail_rank': statistics.mean(q['tail_rank'] for q in chosen),
        })

report = {name: {y: stress(split(rs, p)) for y, p in PERIODS.items()} for name, rs in strategies.items()}
expected = {y: sum(1 for d in dates if p[0] <= d <= p[1]) for y, p in PERIODS.items()}
covered = {y: sum(1 for d in coverage_dates if p[0] <= d <= p[1]) for y, p in PERIODS.items()}
coverage = {y: covered[y]/expected[y] if expected[y] else 0.0 for y in PERIODS}

judgment = {}
for name in strategies:
    wr20 = {y: report[name][y]['0.002']['win_rate'] for y in PERIODS}
    mean40 = {y: report[name][y]['0.004']['mean_return'] for y in PERIODS}
    pooled = []
    for y, p in PERIODS.items():
        pooled.extend(split(strategies[name], p))
    pooled40 = metric(pooled, 0.004)
    coverage_ok = all(coverage[y] >= MIN_COVERAGE for y in PERIODS)
    wr_ok = all(wr20[y] is not None and wr20[y] >= 0.65 for y in PERIODS)
    ev40_all_years = all(mean40[y] is not None and mean40[y] > 0 for y in PERIODS)
    ev40_pooled = pooled40['mean_return'] is not None and pooled40['mean_return'] > 0
    strict_pass = coverage_ok and wr_ok and ev40_all_years and ev40_pooled
    judgment[name] = {
        'coverage_ok': coverage_ok,
        'win_rate_20bp_ge_65_each_year': wr_ok,
        'mean_40bp_positive_each_year': ev40_all_years,
        'mean_40bp_positive_pooled': ev40_pooled,
        'strict_pass': strict_pass,
        'win_rate_20bp_by_year': wr20,
        'mean_return_40bp_by_year': mean40,
        'pooled_40bp': pooled40,
    }

passes = [n for n, j in judgment.items() if j['strict_pass']]
if passes:
    # Fixed tie-break: maximize worst-year 20bp win rate, then pooled 40bp mean.
    passes.sort(key=lambda n: (
        min(judgment[n]['win_rate_20bp_by_year'].values()),
        judgment[n]['pooled_40bp']['mean_return']), reverse=True)
    status = 'T86_STRICT_GATE_PASS'
    champion = passes[0]
else:
    status = 'T86_STRICT_GATE_FAIL_PIVOT_MI_MARGN_TWT93U'
    champion = None

with EVENTS.open('w', encoding='utf-8') as fh:
    for name, rs in strategies.items():
        for r in rs:
            fh.write(json.dumps({'strategy': name, **r}, ensure_ascii=False) + '\n')

result = {
    'status': status,
    'champion': champion,
    'model_family': 'T86 causal institutional-flow challengers on PIT TWSE-listed electronics',
    'timing': 'T86 signal after t close; predetermined entry t+1 close; exit t+2 open',
    'fixed_designs': {
        'T86_TOTAL20': 'top20 by cross-sectional total institutional net-flow / traded-shares proxy',
        'T86_FOREIGN_TRUST20': 'top20 by equal-rank consensus of foreign and investment-trust net-flow ratios',
        'W1_T86_EQUAL_BLEND20': 'top20 by equal-rank blend of W1 tail score and foreign+trust consensus',
        'W1_TOP25_T86_VETO20': 'W1 top25 candidates, retain 20 with strongest foreign+trust consensus',
    },
    'no_tuning': 'No threshold search, no basket-size sweep, no year-specific parameter fitting.',
    'hard_gate': {'20bp_win_rate_each_year_min': 0.65, '40bp_mean_each_year_positive': True, '40bp_pooled_mean_positive': True, 'min_t86_date_coverage_each_year': MIN_COVERAGE},
    'date_coverage': {'expected': expected, 'covered': covered, 'share': coverage, 'fetch_errors_count': len(errors), 'fetch_errors_sample': dict(list(sorted(errors.items()))[:20])},
    'results': report,
    'judgment': judgment,
    'w1_reference_20bp': w1.report['W1_TAIL20'],
    'events_file': str(EVENTS.relative_to(ROOT)),
    'data_source': 'TWSE T86 official daily institutional trading report fetched by signal date',
    'research_boundary': 'Historical diagnostics only; no production promotion or capital authority.',
    'authority': {'research_only': True, 'capital_authority_twd': 0, 'broker_order_execution': False, 'production_promotion': False, 'merge_authorized': False},
}
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('T86_RESULT=' + json.dumps(result, ensure_ascii=False, separators=(',', ':')))
