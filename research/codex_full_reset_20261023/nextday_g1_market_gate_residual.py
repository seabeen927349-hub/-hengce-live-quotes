#!/usr/bin/env python3
from __future__ import annotations

import json, math, statistics
from collections import Counter, defaultdict
from pathlib import Path

# Mechanical PIT OHLCV loader/cleaner only. G1 does not use O2 event families,
# analog scores, selections, or outcomes.
import research.codex_full_reset_20261023.nextday_o2_reversal_analog_tailrisk as raw

ROOT = Path(__file__).resolve().parents[2]
RESET = ROOT / 'research' / 'codex_full_reset_20261023'
OUT = RESET / 'nextday_g1_market_gate_residual_result.json'
EVENTS = RESET / 'nextday_g1_market_gate_residual_events.jsonl'

PRIMARY_COST = 0.002
COSTS = (0.0, 0.002, 0.004, 0.008)
TRAIN = ('2023-01-01', '2023-12-31')
DEV = ('2024-01-01', '2024-12-31')
VAL = ('2025-01-01', '2025-12-31')
DIAG = ('2026-01-01', '2026-10-22')
TARGET_COUNTS = (35, 45, 55)
K_MARKET = 32
MARKET_SMOOTH = 8.0
RESID_BINS = 5
RESID_SMOOTH = 40.0

MARKET_FEATURES = (
    'breadth1','breadth5','breadth20','median_r1','median_r5','median_r20',
    'dispersion1','dispersion20','median_close_loc','median_turn_ratio',
    'frac_high20','frac_low20',
)
STOCK_FEATURES = (
    'r1','r5','r20','close_loc','vol_ratio','turn_ratio','dist_high20','rel20',
)


def outcome(d, t):
    """Same executable horizon as O3, but G1 learns a different decomposition.

    Signal is after t close. Entry is predetermined at t+1 close; exit t+2 open.
    No t+1 information is used to choose the trade.
    """
    i = raw.di[d]
    if i + 2 >= len(raw.dates):
        return None
    ed, xd = raw.dates[i+1], raw.dates[i+2]
    s = raw.by[d].get(t); e = raw.by[ed].get(t); x = raw.by[xd].get(t)
    if not s or not e or not x or e['c'] <= 0 or x['o'] <= 0:
        return None
    if abs(e['c']/s['c'] - 1) > raw.JUMP or abs(x['c']/e['c'] - 1) > raw.JUMP:
        return None
    gross = x['o']/e['c'] - 1
    return {
        'entry_date': ed, 'exit_date': xd,
        'entry_close': e['c'], 'exit_open': x['o'],
        'gross_return': gross, 'net20': gross - PRIMARY_COST,
    }


def percentile_ranks(pairs):
    """Return stable 0..1 ranks for (ticker,value), averaged over exact ties."""
    a = sorted(pairs, key=lambda z: (z[1], z[0]))
    n = len(a)
    out = {}
    i = 0
    while i < n:
        j = i + 1
        while j < n and a[j][1] == a[i][1]:
            j += 1
        pct = ((i + j - 1) / 2 + 0.5) / n
        for k in range(i, j):
            out[a[k][0]] = pct
        i = j
    return out

# Build one independent day panel. Features are all known at signal date t.
panels = {}
for d in raw.dates:
    if d < TRAIN[0] or d > DIAG[1] or d not in raw.market:
        continue
    xs = []
    for t in raw.by[d]:
        x = raw.stock.get((d,t))
        if not x or any(k not in x for k in STOCK_FEATURES):
            continue
        o = outcome(d,t)
        if not o:
            continue
        xs.append((t,x,o))
    if len(xs) < 20:
        continue

    r1 = [x['r1'] for _,x,_ in xs]
    r5 = [x['r5'] for _,x,_ in xs]
    r20 = [x['r20'] for _,x,_ in xs]
    mfeat = {
        'breadth1': sum(v > 0 for v in r1)/len(r1),
        'breadth5': sum(v > 0 for v in r5)/len(r5),
        'breadth20': sum(v > 0 for v in r20)/len(r20),
        'median_r1': statistics.median(r1),
        'median_r5': statistics.median(r5),
        'median_r20': statistics.median(r20),
        'dispersion1': statistics.pstdev(r1),
        'dispersion20': statistics.pstdev(r20),
        'median_close_loc': statistics.median(x['close_loc'] for _,x,_ in xs),
        'median_turn_ratio': statistics.median(x['turn_ratio'] for _,x,_ in xs),
        'frac_high20': sum(x['dist_high20'] >= .97 for _,x,_ in xs)/len(xs),
        'frac_low20': sum(x['dist_low20'] <= 1.05 for _,x,_ in xs)/len(xs),
    }
    nets = [o['net20'] for _,_,o in xs]
    night_median = statistics.median(nets)
    night_mean = statistics.mean(nets)
    night_breadth = sum(v > 0 for v in nets)/len(nets)

    ranks = {}
    for k in STOCK_FEATURES:
        ranks[k] = percentile_ranks([(t,x[k]) for t,x,_ in xs])
    stocks = []
    for t,x,o in xs:
        q = {
            'signal_date': d, 'ticker': t,
            **{f'rank_{k}': ranks[k][t] for k in STOCK_FEATURES},
            **o,
        }
        # Cost cancels in the residual because every stock on a night pays the same fixed cost.
        q['residual_net20'] = o['net20'] - night_median
        stocks.append(q)
    panels[d] = {
        'signal_date': d, **mfeat,
        'night_median_net20': night_median,
        'night_mean_net20': night_mean,
        'night_win_breadth_net20': night_breadth,
        'favorable_night': night_median > 0,
        'stocks': stocks,
    }

train_days = [p for d,p in panels.items() if TRAIN[0] <= d <= TRAIN[1]]
if len(train_days) < 150:
    raise RuntimeError(f'INSUFFICIENT_2023_MARKET_DAYS:{len(train_days)}')

# ---------- Stage 1: market-level regime gate ----------
# Robust z-scales are fixed on 2023 only. The gate asks whether a historical
# market state similar to today's tended to lead to a broad positive overnight.
market_center = {}
market_scale = {}
for k in MARKET_FEATURES:
    vals = sorted(p[k] for p in train_days)
    med = statistics.median(vals)
    mad = statistics.median(abs(v-med) for v in vals)
    market_center[k] = med
    market_scale[k] = max(1.4826*mad, 1e-4)

global_fav = sum(p['favorable_night'] for p in train_days)/len(train_days)
global_med = statistics.mean(p['night_median_net20'] for p in train_days)
global_breadth = statistics.mean(p['night_win_breadth_net20'] for p in train_days)


def market_distance(a,b):
    s = 0.0
    for k in MARKET_FEATURES:
        s += min(abs(a[k]-b[k])/market_scale[k], 4.0)
    return s/len(MARKET_FEATURES)


def gate_score(p):
    near = sorted(train_days, key=lambda h: market_distance(p,h))[:K_MARKET]
    n = len(near)
    fav = sum(h['favorable_night'] for h in near)
    pred_p = (fav + MARKET_SMOOTH*global_fav)/(n + MARKET_SMOOTH)
    pred_med = (sum(h['night_median_net20'] for h in near) + MARKET_SMOOTH*global_med)/(n + MARKET_SMOOTH)
    pred_breadth = (sum(h['night_win_breadth_net20'] for h in near) + MARKET_SMOOTH*global_breadth)/(n + MARKET_SMOOTH)
    # Rank score only; fixed before 2024/25/26 readout. 100bp of predicted median
    # edge is deliberately comparable to a 10 percentage-point breadth shift.
    score = pred_med + .01*(pred_breadth-.5) + .004*(pred_p-.5)
    return score, pred_p, pred_med, pred_breadth

# ---------- Stage 2: cross-sectional residual alpha ----------
# The stock learner never predicts absolute overnight return. It predicts only
# excess return versus that night's market median from same-day percentile ranks.
train_stocks = [s for p in train_days for s in p['stocks']]
cell = defaultdict(lambda: {'n':0,'sum':0.0})
for s in train_stocks:
    for k in STOCK_FEATURES:
        b = min(RESID_BINS-1, int(s[f'rank_{k}']*RESID_BINS))
        z = cell[(k,b)]
        z['n'] += 1
        z['sum'] += s['residual_net20']


def residual_score(s):
    edges=[]; support=[]; positive=0
    for k in STOCK_FEATURES:
        b = min(RESID_BINS-1, int(s[f'rank_{k}']*RESID_BINS))
        z = cell[(k,b)]
        e = z['sum']/(z['n']+RESID_SMOOTH)  # shrink to zero market-relative edge
        edges.append(e); support.append(z['n'])
        positive += int(e > 0)
    return statistics.mean(edges), positive, min(support)

# Score every eligible day using only 2023-frozen gate and residual mappings.
daily=[]
for d,p in sorted(panels.items()):
    if d < DEV[0]:
        continue
    gs,gp,gm,gb = gate_score(p)
    arr=[]
    for s in p['stocks']:
        rs,pos,n = residual_score(s)
        q=dict(s)
        q.update({'residual_score':rs,'positive_feature_votes':pos,'min_residual_cell_n':n})
        arr.append(q)
    if not arr:
        continue
    arr.sort(key=lambda z:(-z['residual_score'],-z['positive_feature_votes'],-z['rank_turn_ratio'],z['ticker']))
    q=arr[0]
    q.update({
        'gate_score':gs,'gate_pred_favorable_p':gp,'gate_pred_median_net20':gm,
        'gate_pred_win_breadth_net20':gb,
        'realized_market_median_net20':p['night_median_net20'],
        'realized_market_win_breadth_net20':p['night_win_breadth_net20'],
    })
    daily.append(q)


def wilson(w,n,z=1.959963984540054):
    if not n: return None
    p=w/n; z2=z*z; den=1+z2/n
    return (p+z2/(2*n)-z*math.sqrt(p*(1-p)/n+z2/(4*n*n)))/den


def quarter(d):
    y=int(d[:4]); m=int(d[5:7]); return f'{y}-Q{(m-1)//3+1}'


def metrics(rs,cost):
    xs=[r['gross_return']-cost for r in rs]; n=len(xs); w=sum(x>0 for x in xs)
    nav=1.; peak=1.; mdd=0.; cur=mx=0
    for x in xs:
        nav*=1+x; peak=max(peak,nav); mdd=min(mdd,nav/peak-1)
        if x<=0: cur+=1; mx=max(mx,cur)
        else: cur=0
    c=Counter(r['ticker'] for r in rs)
    byq=defaultdict(list)
    for r,x in zip(rs,xs): byq[quarter(r['signal_date'])].append(x)
    qstats={q:{'trades':len(v),'wins':sum(x>0 for x in v),'win_rate':sum(x>0 for x in v)/len(v),'mean_return':statistics.mean(v)} for q,v in sorted(byq.items())}
    return {
        'trades':n,'wins':w,'losses':n-w,'win_rate':w/n if n else None,
        'wilson95_lower':wilson(w,n),'mean_return':statistics.mean(xs) if xs else None,
        'median_return':statistics.median(xs) if xs else None,'worst_return':min(xs) if xs else None,
        'best_return':max(xs) if xs else None,'compounded_return':nav-1 if n else 0.0,
        'max_drawdown':mdd,'max_consecutive_losses':mx,
        'top_ticker_share':max(c.values())/n if n and c else None,'quarterly':qstats,
    }


def split(rs,p): return [r for r in rs if p[0] <= r['signal_date'] <= p[1]]
def stress(rs): return {str(c):metrics(rs,c) for c in COSTS}

# Diagnostic baseline: residual alpha every eligible day, with no market abstention.
dev_all=split(daily,DEV)
val_all=split(daily,VAL)
diag_all=split(daily,DIAG)
if len(dev_all) < max(TARGET_COUNTS):
    raise RuntimeError(f'INSUFFICIENT_2024_DAILY:{len(dev_all)}')

# Finite 2024-only gate choice. No stock threshold and no 2025/2026 tuning.
configs=[]
for target in TARGET_COUNTS:
    ranked=sorted(dev_all,key=lambda r:(-r['gate_score'],r['signal_date']))
    th=ranked[target-1]['gate_score']
    sel=[r for r in dev_all if r['gate_score'] >= th]
    m=metrics(sel,PRIMARY_COST)
    configs.append({'target_count':target,'gate_threshold':th,'actual_dev_count':len(sel),'dev_net20':m})
configs.sort(key=lambda c:((c['dev_net20']['wilson95_lower'] or -1),c['dev_net20']['mean_return'] or -9,-abs(c['actual_dev_count']-45)),reverse=True)
champ=configs[0]; threshold=champ['gate_threshold']
selected=[r for r in daily if r['gate_score'] >= threshold]
dev=split(selected,DEV); val=split(selected,VAL); diag=split(selected,DIAG); pre=dev+val

val20=metrics(val,PRIMARY_COST)
coverage_ok=30 <= val20['trades'] <= 70
positive_econ=(val20['mean_return'] is not None and val20['mean_return']>0 and val20['median_return'] is not None and val20['median_return']>0)
beats_o3_2025=(val20['win_rate'] is not None and val20['win_rate'] > 30/46)
if coverage_ok and positive_econ and beats_o3_2025:
    status='G1_MARKET_GATE_RESIDUAL_BEATS_O3_2025_REUSED_VALIDATION'
elif coverage_ok and val20['mean_return'] is not None and val20['mean_return']>0 and val20['win_rate'] is not None and val20['win_rate']>=.60:
    status='G1_MARKET_GATE_RESIDUAL_PROMISING_REUSED_VALIDATION'
else:
    status='G1_MARKET_GATE_RESIDUAL_REJECTED'

with EVENTS.open('w',encoding='utf-8') as fh:
    for label,rs in [('DEV_2024',dev),('REUSED_2025',val),('DIAGNOSTIC_2026',diag)]:
        for r in rs:
            fh.write(json.dumps({'split':label,**r},ensure_ascii=False)+'\n')

res={
    'status':status,
    'model':'G1 two-stage market overnight regime gate -> cross-sectional stock residual alpha',
    'timing':'signal after t close; predetermined entry t+1 close; exit t+2 open',
    'target':'pure overnight; primary win = gross - 20bp > 0',
    'new_mode':'Stage 1 predicts whether the whole electronics cross-section is likely to have a favorable overnight and can abstain. Stage 2 predicts only stock excess return versus the future night market median using same-day cross-sectional ranks. It never predicts absolute stock win probability.',
    'independence':'Raw TWSE electronics OHLC/turnover only. No HENGCE/V/X/HR rank, O3 score, O5 T86 data, or prior selected trade identity is used.',
    'market_features':MARKET_FEATURES,'stock_rank_features':STOCK_FEATURES,
    'protocol':{
        'fit':'2023 only','gate_threshold_selection':'2024 only','2025':'reused validation; frozen for G1 but not globally pristine because prior project work exposed 2025',
        '2026':'diagnostic only; excluded from model/threshold selection','target_counts_2024':TARGET_COUNTS,
        'market_knn':K_MARKET,'market_smoothing':MARKET_SMOOTH,'residual_bins':RESID_BINS,'residual_smoothing':RESID_SMOOTH,
        'primary_cost':PRIMARY_COST,'cost_stress':COSTS,
    },
    'train_market_days_2023':len(train_days),'train_stock_rows_2023':len(train_stocks),
    'global_2023_market_favorable_rate':global_fav,'global_2023_mean_market_median_net20':global_med,'global_2023_mean_market_win_breadth_net20':global_breadth,
    'development_configs':configs,'selected_gate_threshold':threshold,'selected_target_count':champ['target_count'],
    'ungated_residual_baseline':{'development_2024':stress(dev_all),'reused_validation_2025':stress(val_all),'diagnostic_2026':stress(diag_all)},
    'gated_development_2024':stress(dev),'gated_reused_validation_2025':stress(val),'gated_pre2026':stress(pre),'gated_historical_diagnostic_2026':stress(diag),
    'acceptance_checks':{
        'validation_coverage_30_to_70':coverage_ok,'validation_positive_mean_and_median_net20':positive_econ,
        'validation_win_rate_beats_o3_2025_30_of_46':beats_o3_2025,
        'o3_2025_reference_win_rate':30/46,
    },
    'events_file':str(EVENTS.relative_to(ROOT)),
    'research_boundary':'G1 architecture is fixed after O3/O4/O5 historical findings were already known. Thus 2025/2026 are reused historical diagnostics, not pristine global OOS, even though G1 itself fits 2023 and selects only on 2024.',
    'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
    'caveat':'Historical research only. Close execution/slippage and true prospective performance require separate validation; no historical hit rate guarantees future gains.'
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('G1_RESULT='+json.dumps(res,ensure_ascii=False,separators=(',',':')))
