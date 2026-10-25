#!/usr/bin/env python3
from __future__ import annotations

import json, math, statistics
from collections import Counter, defaultdict
from pathlib import Path

# Reuse O2 only as a mechanical raw-OHLCV feature loader. None of O2's event
# families, labels, scores, selected picks, or outcomes are consumed below.
import research.codex_full_reset_20261023.nextday_o2_reversal_analog_tailrisk as raw

ROOT = Path(__file__).resolve().parents[2]
RESET = ROOT / 'research' / 'codex_full_reset_20261023'
OUT = RESET / 'nextday_o3_delayed_close_overnight_result.json'
EVENTS = RESET / 'nextday_o3_delayed_close_overnight_events.jsonl'

PRIMARY_COST = 0.002
COSTS = (0.0, 0.002, 0.004, 0.008)
TRAIN = ('2023-01-01', '2023-12-31')
DEV = ('2024-01-01', '2024-12-31')
VAL = ('2025-01-01', '2025-12-31')
DIAG = ('2026-01-01', '2026-10-22')
TARGET_COUNTS = (35, 45, 55)
BINS = 6
SMOOTH = 24.0
FEATURES = ('r1','r3','r5','r20','r60','gap','body','close_loc','vol_ratio','turn_ratio','breadth20','dispersion1','rel20')


def outcome(d, t):
    i = raw.di[d]
    if i + 2 >= len(raw.dates):
        return None
    ed, xd = raw.dates[i+1], raw.dates[i+2]
    s = raw.by[d].get(t); e = raw.by[ed].get(t); x = raw.by[xd].get(t)
    if not s or not e or not x or e['c'] <= 0 or x['o'] <= 0:
        return None
    # Fail closed on corporate-action-like discontinuities.
    if abs(e['c']/s['c'] - 1) > raw.JUMP:
        return None
    if abs(x['c']/e['c'] - 1) > raw.JUMP:
        return None
    gross = x['o']/e['c'] - 1
    return {
        'entry_date': ed,
        'exit_date': xd,
        'entry_close': e['c'],
        'exit_open': x['o'],
        'gross_return': gross,
        'net20': gross - PRIMARY_COST,
    }

rows = []
for d in raw.dates:
    if d < TRAIN[0] or d > DIAG[1] or d not in raw.market:
        continue
    for t in raw.by[d]:
        x = raw.stock.get((d,t))
        if not x or any(k not in x for k in FEATURES):
            continue
        o = outcome(d,t)
        if not o:
            continue
        rows.append({'signal_date':d,'ticker':t,**{k:x[k] for k in FEATURES},**o})

train = [r for r in rows if TRAIN[0] <= r['signal_date'] <= TRAIN[1]]
if len(train) < 10000:
    raise RuntimeError(f'INSUFFICIENT_2023_TRAIN:{len(train)}')


def qedges(vals, bins=BINS):
    a = sorted(vals); n = len(a); out=[]
    for q in range(1,bins):
        out.append(a[min(n-1, max(0, math.ceil(q*n/bins)-1))])
    return out

def bid(v, edges):
    i=0
    while i < len(edges) and v > edges[i]:
        i += 1
    return i

def logit(p):
    p=min(max(p,1e-6),1-1e-6)
    return math.log(p/(1-p))

edges = {k:qedges([r[k] for r in train]) for k in FEATURES}
global_p = sum(r['net20'] > 0 for r in train)/len(train)
global_mean = statistics.mean(r['net20'] for r in train)
cell = defaultdict(lambda:{'n':0,'w':0,'sum':0.0})
for r in train:
    for k in FEATURES:
        z=cell[(k,bid(r[k],edges[k]))]
        z['n'] += 1
        z['w'] += int(r['net20'] > 0)
        z['sum'] += r['net20']

# 2023-frozen additive quantile likelihood. Correlated-feature contributions are
# averaged rather than summed, to avoid artificial overconfidence.
def score(r):
    lod=[]; mus=[]; supports=[]
    for k in FEATURES:
        z=cell[(k,bid(r[k],edges[k]))]
        n=z['n']
        p=(z['w'] + SMOOTH*global_p)/(n+SMOOTH)
        m=(z['sum'] + SMOOTH*global_mean)/(n+SMOOTH)
        lod.append(logit(p)-logit(global_p))
        mus.append(m-global_mean)
        supports.append(n)
    # 1% expected-return edge contributes 0.08 score units; probability rank is primary.
    s = statistics.mean(lod) + 8.0*statistics.mean(mus)
    return s, min(supports), statistics.mean(mus)

scored=[]
for r in rows:
    s,n,m=score(r)
    q=dict(r); q['o3_score']=s; q['min_cell_n']=n; q['mean_feature_edge']=m
    scored.append(q)

# One stock per signal date, selected solely by 2023-frozen score.
daily=[]
byday=defaultdict(list)
for r in scored:
    byday[r['signal_date']].append(r)
for d,arr in byday.items():
    arr.sort(key=lambda z:(-z['o3_score'],-z['turn_ratio'],z['ticker']))
    daily.append(arr[0])
daily.sort(key=lambda z:z['signal_date'])


def wilson(w,n,z=1.959963984540054):
    if not n:return None
    p=w/n; z2=z*z; den=1+z2/n
    return (p+z2/(2*n)-z*math.sqrt(p*(1-p)/n+z2/(4*n*n)))/den

def metrics(rs,cost):
    xs=[r['gross_return']-cost for r in rs]; n=len(xs); w=sum(x>0 for x in xs)
    nav=1.; peak=1.; mdd=0.; cur=mx=0
    for x in xs:
        nav*=1+x; peak=max(peak,nav); mdd=min(mdd,nav/peak-1)
        if x<=0: cur+=1; mx=max(mx,cur)
        else: cur=0
    c=Counter(r['ticker'] for r in rs)
    return {
        'trades':n,'wins':w,'losses':n-w,'win_rate':w/n if n else None,
        'wilson95_lower':wilson(w,n),'mean_return':statistics.mean(xs) if xs else None,
        'median_return':statistics.median(xs) if xs else None,
        'worst_return':min(xs) if xs else None,'best_return':max(xs) if xs else None,
        'compounded_return':nav-1 if n else 0.0,'max_drawdown':mdd,'max_consecutive_losses':mx,
        'top_ticker_share':max(c.values())/n if n and c else None,
    }
def split(rs,p): return [r for r in rs if p[0] <= r['signal_date'] <= p[1]]
def stress(rs): return {str(c):metrics(rs,c) for c in COSTS}

dev_all=split(daily,DEV)
if len(dev_all) < max(TARGET_COUNTS):
    raise RuntimeError(f'INSUFFICIENT_2024_DAILY:{len(dev_all)}')
configs=[]
for target in TARGET_COUNTS:
    ranked=sorted(dev_all,key=lambda r:(-r['o3_score'],r['signal_date']))
    th=ranked[target-1]['o3_score']
    sel=[r for r in dev_all if r['o3_score']>=th]
    m=metrics(sel,PRIMARY_COST)
    configs.append({'target_count':target,'threshold':th,'actual_dev_count':len(sel),'dev_net20':m})
# One finite 2024-only choice: conservative hit-rate lower bound, then mean economics.
configs.sort(key=lambda c:((c['dev_net20']['wilson95_lower'] or -1),c['dev_net20']['mean_return'] or -9,-abs(c['actual_dev_count']-45)),reverse=True)
champ=configs[0]; threshold=champ['threshold']
selected=[r for r in daily if r['signal_date']>=DEV[0] and r['o3_score']>=threshold]
dev=split(selected,DEV); val=split(selected,VAL); diag=split(selected,DIAG); pre=dev+val

val20=metrics(val,PRIMARY_COST)
coverage_ok=30 <= val20['trades'] <= 70
positive_econ=(val20['mean_return'] is not None and val20['mean_return']>0 and val20['median_return'] is not None and val20['median_return']>0)
if coverage_ok and positive_econ and val20['win_rate'] is not None and val20['win_rate']>=.75:
    status='O3_OVERNIGHT_TARGET_GRADE_REUSED_VALIDATION'
elif coverage_ok and val20['mean_return'] is not None and val20['mean_return']>0 and val20['win_rate'] is not None and val20['win_rate']>=.60:
    status='O3_OVERNIGHT_PROMISING_REUSED_VALIDATION'
else:
    status='O3_OVERNIGHT_REJECTED'

with EVENTS.open('w',encoding='utf-8') as fh:
    for label,rs in [('DEV_2024',dev),('REUSED_2025',val),('DIAGNOSTIC_2026',diag)]:
        for r in rs:
            fh.write(json.dumps({'split':label,**r},ensure_ascii=False)+'\n')

res={
    'status':status,
    'model':'O3 2023-frozen additive quantile likelihood for delayed-close pure overnight target',
    'timing':'signal after t close using t-or-earlier OHLCV only; predetermined entry at t+1 close; exit t+2 open',
    'target':'t+1 close -> t+2 open, primary win = gross - 20bp > 0',
    'why_this_timing':'O2 path decomposition found entry-day intraday and exit-day intraday legs structurally negative, while the close-to-next-open leg was the only recurrently positive-mean segment. O3 trains directly on that segment rather than post-hoc changing O2 exits.',
    'independence':'Raw TWSE electronics OHLC/turnover state only. O2 module is imported solely for mechanical raw feature construction; O2 families/scores/picks/outcomes are not used.',
    'features':FEATURES,
    'protocol':{
        'fit':'2023 only','threshold_selection':'2024 only','2025':'reused validation, not pristine global OOS because earlier project work exposed 2025',
        '2026':'diagnostic only; excluded from threshold/model selection','target_counts_2024':TARGET_COUNTS,
        'primary_cost':PRIMARY_COST,'cost_stress':COSTS,'bins':BINS,'smoothing':SMOOTH,
    },
    'train_rows_2023':len(train),'daily_candidates_total':len(daily),'global_2023_net20_win_rate':global_p,'global_2023_mean_net20':global_mean,
    'development_configs':configs,'selected_threshold':threshold,'selected_target_count':champ['target_count'],
    'development_2024':stress(dev),'reused_validation_2025':stress(val),'pre2026':stress(pre),'historical_diagnostic_2026':stress(diag),
    'acceptance_checks':{'validation_coverage_30_to_70':coverage_ok,'validation_positive_mean_and_median_net20':positive_econ,'target_grade_reused_validation_requires_net20_win_rate_gte_0_75':True,'promising_reused_validation_requires_net20_win_rate_gte_0_60_and_positive_mean':True},
    'events_file':str(EVENTS.relative_to(ROOT)),
    'research_boundary':'Hypothesis is informed by the prior O2 path audit, which exposed 2024-2026. Therefore O3 is a historical diagnostic/research model, not a pristine holdout proof, even though its code itself fits only 2023 and selects threshold only on 2024.',
    'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
    'caveat':'Historical research only; market-at-close execution and slippage must be validated separately. No historical hit rate guarantees future gains.'
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('O3_RESULT='+json.dumps(res,ensure_ascii=False,separators=(',',':')))
