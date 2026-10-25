#!/usr/bin/env python3
from __future__ import annotations

import json, math, statistics
from collections import Counter, defaultdict
from pathlib import Path

# Mechanical PIT OHLCV loader/cleaner only. No prior model score/pick is reused.
import research.codex_full_reset_20261023.nextday_o2_reversal_analog_tailrisk as raw

ROOT=Path(__file__).resolve().parents[2]
RESET=ROOT/'research'/'codex_full_reset_20261023'
OUT=RESET/'nextday_w1_wide_tail_basket_result.json'
EVENTS=RESET/'nextday_w1_wide_tail_basket_events.jsonl'
PRIMARY_COST=0.002
COSTS=(0.0,0.002,0.004,0.006,0.008)
TRAIN=('2023-01-01','2023-12-31'); DEV=('2024-01-01','2024-12-31'); VAL=('2025-01-01','2025-12-31'); DIAG=('2026-01-01','2026-10-22')
BINS=5; TAIL_Q=0.25; BASKET_SIZE=20
FAIL_CLOSED_RETURN=-0.15
GROUPS={
 'MOMENTUM_RELATIVE':('r1','r5','r20','rel20','dist_high20'),
 'CANDLE_GEOMETRY':('gap','body','close_loc','range_pct'),
 'RISK_LIQUIDITY':('vol_ratio','turn_ratio','vol20'),
}
FEATURES=tuple(dict.fromkeys(k for ks in GROUPS.values() for k in ks))


def future_overnight(d,t,fail_closed=False):
    """Signal-time universe is independent of future availability.

    Training may skip unavailable labels. Evaluation never removes a selected stock
    because of future information: missing/discontinuity legs are assigned a fixed
    conservative -15% gross return and explicitly counted.
    """
    i=raw.di[d]
    if i+2>=len(raw.dates):
        return (FAIL_CLOSED_RETURN,True) if fail_closed else (None,True)
    ed,xd=raw.dates[i+1],raw.dates[i+2]
    s=raw.by[d].get(t); e=raw.by[ed].get(t); x=raw.by[xd].get(t)
    if not s or not e or not x or s['c']<=0 or e['c']<=0 or x['o']<=0:
        return (FAIL_CLOSED_RETURN,True) if fail_closed else (None,True)
    # Large discontinuities are usually corporate-action/data events. Do not let
    # evaluation drop them after selection; fail closed instead.
    if abs(e['c']/s['c']-1)>raw.JUMP or abs(x['o']/e['c']-1)>raw.JUMP:
        return (FAIL_CLOSED_RETURN,True) if fail_closed else (None,True)
    return (x['o']/e['c']-1,False)


def ranks(pairs):
    a=sorted(pairs,key=lambda z:(z[1],z[0]));n=len(a);out={};i=0
    while i<n:
        j=i+1
        while j<n and a[j][1]==a[i][1]:j+=1
        p=((i+j-1)/2+.5)/n
        for q in range(i,j):out[a[q][0]]=p
        i=j
    return out

def quantile(vals,q):
    a=sorted(vals);n=len(a)
    if not n:return 0.0
    pos=(n-1)*q;lo=math.floor(pos);hi=math.ceil(pos)
    if lo==hi:return a[lo]
    return a[lo]*(hi-pos)+a[hi]*(pos-lo)

# Signal-time panels: current-date OHLCV only. No future outcome is used for membership.
panels={}
for d in raw.dates:
    if d<TRAIN[0] or d>DIAG[1] or d not in raw.market:continue
    xs=[]
    for t in raw.by[d]:
        x=raw.stock.get((d,t))
        if not x or any(k not in x for k in FEATURES):continue
        xs.append((t,x))
    if len(xs)<BASKET_SIZE:continue
    rr={k:ranks([(t,x[k]) for t,x in xs]) for k in FEATURES}
    stocks=[]
    for t,x in xs:
        stocks.append({'signal_date':d,'ticker':t,'turn20':x['turn20'],**{f'rank_{k}':rr[k][t] for k in FEATURES}})
    panels[d]=stocks

# 2023 training labels. Only training labels may be unavailable; this does not affect
# any later signal-time universe. Residual is versus the same training night's median.
train_rows=[]
for d,stocks in panels.items():
    if not(TRAIN[0]<=d<=TRAIN[1]):continue
    labelled=[]
    for s in stocks:
        g,bad=future_overnight(d,s['ticker'],fail_closed=False)
        if g is not None:labelled.append((s,g))
    if len(labelled)<20:continue
    med=statistics.median(g-PRIMARY_COST for _,g in labelled)
    for s,g in labelled:
        train_rows.append((s,(g-PRIMARY_COST)-med))
if len(train_rows)<10000:raise RuntimeError(f'INSUFFICIENT_2023_TRAIN:{len(train_rows)}')

cell=defaultdict(list)
for s,resid in train_rows:
    for grp,ks in GROUPS.items():
        for k in ks:
            b=min(BINS-1,int(s[f'rank_{k}']*BINS));cell[(grp,k,b)].append(resid)
tail={key:quantile(vals,TAIL_Q) for key,vals in cell.items()}

def tail_score(s):
    sleeves=[]
    for grp,ks in GROUPS.items():
        qs=[]
        for k in ks:
            b=min(BINS-1,int(s[f'rank_{k}']*BINS));qs.append(tail[(grp,k,b)])
        sleeves.append(statistics.mean(qs))
    return statistics.median(sleeves)+.35*min(sleeves)

# Two fixed, executable-ish 20-stock designs, every eligible night:
# W1 = downside-tail ranked 20; L20 = pure prior-turnover top20 control.
strategies={'W1_TAIL20':[],'L20_LIQUIDITY':[],'ALL_EQUAL':[]}
for d,stocks in sorted(panels.items()):
    if d<DEV[0]:continue
    scored=[]
    for s in stocks:
        q=dict(s);q['tail_score']=tail_score(s);scored.append(q)
    picks={
        'W1_TAIL20':sorted(scored,key=lambda z:(-z['tail_score'],z['ticker']))[:BASKET_SIZE],
        'L20_LIQUIDITY':sorted(scored,key=lambda z:(-z['turn20'],z['ticker']))[:BASKET_SIZE],
        'ALL_EQUAL':scored,
    }
    for name,chosen in picks.items():
        returns=[];bad=0
        for q in chosen:
            g,is_bad=future_overnight(d,q['ticker'],fail_closed=True)
            returns.append(g);bad+=int(is_bad)
        if not returns:continue
        strategies[name].append({
            'signal_date':d,'tickers':[q['ticker'] for q in chosen],
            'legs':len(chosen),'gross_return':statistics.mean(returns),
            'fail_closed_legs':bad,'mean_tail_score':statistics.mean(q['tail_score'] for q in chosen),
            'mean_turn20':statistics.mean(q['turn20'] for q in chosen),
        })

def wilson(w,n,z=1.959963984540054):
    if not n:return None
    p=w/n;z2=z*z;den=1+z2/n
    return (p+z2/(2*n)-z*math.sqrt(p*(1-p)/n+z2/(4*n*n)))/den

def metric(rs,cost):
    xs=[r['gross_return']-cost for r in rs];n=len(xs);w=sum(x>0 for x in xs)
    nav=1.;peak=1.;mdd=0.;cur=mx=0
    for x in xs:
        nav*=1+x;peak=max(peak,nav);mdd=min(mdd,nav/peak-1)
        if x<=0:cur+=1;mx=max(mx,cur)
        else:cur=0
    leg_n=sum(r['legs'] for r in rs);bad=sum(r['fail_closed_legs'] for r in rs)
    tc=Counter(t for r in rs for t in r['tickers'])
    return {'nights':n,'underlying_legs':leg_n,'wins':w,'losses':n-w,'win_rate':w/n if n else None,'wilson95_lower':wilson(w,n),
            'mean_return':statistics.mean(xs) if xs else None,'median_return':statistics.median(xs) if xs else None,
            'worst_return':min(xs) if xs else None,'best_return':max(xs) if xs else None,'compounded_return':nav-1 if n else 0.0,
            'max_drawdown':mdd,'max_consecutive_losses':mx,'fail_closed_legs':bad,'fail_closed_leg_share':bad/leg_n if leg_n else None,
            'top_ticker_leg_share':max(tc.values())/leg_n if leg_n and tc else None}
def split(rs,p):return[r for r in rs if p[0]<=r['signal_date']<=p[1]]
def stress(rs):return{str(c):metric(rs,c) for c in COSTS}

periods={'2024':DEV,'2025':VAL,'2026':DIAG}
report={}
for name,rs in strategies.items():
    report[name]={label:stress(split(rs,p)) for label,p in periods.items()}

# Historical-only judgment: W1 must beat liquidity-only and all-equal in at least
# two of three years at 20bp to claim stock-selection win-rate value.
w1=[report['W1_TAIL20'][y]['0.002']['win_rate'] for y in periods]
l20=[report['L20_LIQUIDITY'][y]['0.002']['win_rate'] for y in periods]
allr=[report['ALL_EQUAL'][y]['0.002']['win_rate'] for y in periods]
beats_l=sum(a>b for a,b in zip(w1,l20));beats_all=sum(a>b for a,b in zip(w1,allr))
if beats_l>=2 and beats_all>=2:status='W1_WIDE_TAIL_SELECTION_FRONTIER_HISTORICAL'
elif beats_l>=2:status='W1_WIDE_TAIL_BEATS_LIQUIDITY_NOT_MARKET_CORE'
else:status='W1_WIDE_TAIL_REJECTED_AS_SELECTION_EDGE'

with EVENTS.open('w',encoding='utf-8') as fh:
    for name,rs in strategies.items():
        if name=='ALL_EQUAL':continue
        for r in rs:fh.write(json.dumps({'strategy':name,**r},ensure_ascii=False)+'\n')
res={
 'status':status,'model':'W1 wide downside-tail 20-stock overnight basket vs liquidity20 and all-equal controls',
 'timing':'signal after t close; predetermined entry t+1 close; exit t+2 open',
 'new_mode':'Use broad diversification as the core mechanism. W1 fixes 20 stocks every eligible night and ranks only by a 2023-fitted 25th-percentile market-relative residual floor. No day gate, no basket-size sweep, no threshold search.',
 'controls':'L20 chooses top20 by prior 20-day turnover only. ALL_EQUAL holds the whole signal-time eligible electronics universe. All controls use the same fail-closed future-outcome policy.',
 'leakage_hardening':'Evaluation membership is determined solely at signal date. A selected leg with missing or >15% discontinuous future data is not dropped; it is assigned -15% gross and counted.',
 'protocol':{'fit':'2023 only','tail_quantile_fixed':TAIL_Q,'basket_size_fixed':BASKET_SIZE,'day_filter':'none','primary_cost':PRIMARY_COST,'cost_stress':COSTS,'fail_closed_return':FAIL_CLOSED_RETURN,'2025_2026':'reused historical diagnostics, not pristine OOS'},
 'train_rows_2023':len(train_rows),'results':report,
 'selection_edge_checks_20bp':{'beats_liquidity20_years':beats_l,'beats_all_equal_years':beats_all,'W1_win_rates':dict(zip(periods,w1)),'L20_win_rates':dict(zip(periods,l20)),'ALL_EQUAL_win_rates':dict(zip(periods,allr))},
 'events_file':str(EVENTS.relative_to(ROOT)),
 'research_boundary':'W1 was proposed after C0 exposed the broad-market overnight effect. All 2024-2026 results are therefore historical diagnostics for this architecture; prospective validation remains required.',
 'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
 'caveat':'Historical research only. Close auction execution, slippage, capacity, corporate actions and real fees require separate validation.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('W1_RESULT='+json.dumps(res,ensure_ascii=False,separators=(',',':')))
