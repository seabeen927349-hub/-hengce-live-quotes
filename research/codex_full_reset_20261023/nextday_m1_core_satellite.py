#!/usr/bin/env python3
from __future__ import annotations

import json, statistics
from collections import Counter, defaultdict
from pathlib import Path

# W1 supplies the leakage-hardened signal-time universe, 2023-fitted tail score,
# and fail-closed future outcome mechanic. M1 does NOT reuse W1 selected identities.
import research.codex_full_reset_20261023.nextday_w1_wide_tail_basket as w1

ROOT=Path(__file__).resolve().parents[2]
RESET=ROOT/'research'/'codex_full_reset_20261023'
OUT=RESET/'nextday_m1_core_satellite_result.json'
EVENTS=RESET/'nextday_m1_core_satellite_events.jsonl'
CORE_N=20; SAT_N=5; CORE_WEIGHT=0.80; SAT_WEIGHT=0.20
PRIMARY_COST=w1.PRIMARY_COST; COSTS=w1.COSTS
PERIODS={'2024':w1.DEV,'2025':w1.VAL,'2026':w1.DIAG}


def realized(d,t):
    return w1.future_overnight(d,t,fail_closed=True)

rows=[]
for d,stocks in sorted(w1.panels.items()):
    if d<w1.DEV[0] or len(stocks)<CORE_N:continue
    scored=[]
    for s in stocks:
        q=dict(s);q['tail_score']=w1.tail_score(s);scored.append(q)
    core=sorted(scored,key=lambda z:(-z['turn20'],z['ticker']))[:CORE_N]
    sat=sorted(scored,key=lambda z:(-z['tail_score'],z['ticker']))[:SAT_N]
    weights=defaultdict(float)
    for q in core:weights[q['ticker']]+=CORE_WEIGHT/CORE_N
    for q in sat:weights[q['ticker']]+=SAT_WEIGHT/SAT_N
    gross=0.0;bad=0
    for t,wt in weights.items():
        g,is_bad=realized(d,t);gross+=wt*g;bad+=int(is_bad)
    rows.append({
      'signal_date':d,'gross_return':gross,'tickers':sorted(weights),'weights':dict(sorted(weights.items())),
      'core_tickers':[q['ticker'] for q in core],'satellite_tickers':[q['ticker'] for q in sat],
      'overlap_count':len(set(q['ticker'] for q in core)&set(q['ticker'] for q in sat)),
      'fail_closed_legs':bad,'legs':len(weights),
    })

def wilson(w,n,z=1.959963984540054):
    if not n:return None
    import math
    p=w/n;z2=z*z;den=1+z2/n
    return (p+z2/(2*n)-z*math.sqrt(p*(1-p)/n+z2/(4*n*n)))/den

def metric(rs,cost):
    xs=[r['gross_return']-cost for r in rs];n=len(xs);wins=sum(x>0 for x in xs)
    nav=1.;peak=1.;mdd=0.;cur=mx=0
    for x in xs:
        nav*=1+x;peak=max(peak,nav);mdd=min(mdd,nav/peak-1)
        if x<=0:cur+=1;mx=max(mx,cur)
        else:cur=0
    leg_n=sum(r['legs'] for r in rs);bad=sum(r['fail_closed_legs'] for r in rs)
    exposure=Counter()
    for r in rs:
        for t,wt in r['weights'].items():exposure[t]+=wt
    return {'nights':n,'wins':wins,'losses':n-wins,'win_rate':wins/n if n else None,'wilson95_lower':wilson(wins,n),
            'mean_return':statistics.mean(xs) if xs else None,'median_return':statistics.median(xs) if xs else None,
            'worst_return':min(xs) if xs else None,'best_return':max(xs) if xs else None,'compounded_return':nav-1 if n else 0.0,
            'max_drawdown':mdd,'max_consecutive_losses':mx,'mean_unique_legs':leg_n/n if n else None,
            'fail_closed_legs':bad,'fail_closed_leg_share':bad/leg_n if leg_n else None,
            'top_ticker_exposure_share':max(exposure.values())/n if n and exposure else None,
            'mean_core_satellite_overlap':statistics.mean(r['overlap_count'] for r in rs) if rs else None}
def split(rs,p):return[r for r in rs if p[0]<=r['signal_date']<=p[1]]
def stress(rs):return{str(c):metric(rs,c) for c in COSTS}

report={label:stress(split(rows,p)) for label,p in PERIODS.items()}
# Compare against W1's already-computed apples-to-apples L20 and W1 controls.
comparisons={}
for y in PERIODS:
    m=report[y]['0.002']; l=w1.report['L20_LIQUIDITY'][y]['0.002']; t=w1.report['W1_TAIL20'][y]['0.002']; a=w1.report['ALL_EQUAL'][y]['0.002']
    comparisons[y]={
      'M1_win_rate':m['win_rate'],'L20_win_rate':l['win_rate'],'W1_win_rate':t['win_rate'],'ALL_EQUAL_win_rate':a['win_rate'],
      'M1_minus_L20_pp':(m['win_rate']-l['win_rate'])*100,'M1_minus_ALL_pp':(m['win_rate']-a['win_rate'])*100,
      'M1_mean_return':m['mean_return'],'L20_mean_return':l['mean_return'],'W1_mean_return':t['mean_return'],'ALL_EQUAL_mean_return':a['mean_return'],
    }
beats_l=sum(comparisons[y]['M1_win_rate']>comparisons[y]['L20_win_rate'] for y in PERIODS)
beats_all=sum(comparisons[y]['M1_win_rate']>comparisons[y]['ALL_EQUAL_win_rate'] for y in PERIODS)
if beats_l>=2 and beats_all>=2:status='M1_CORE_SATELLITE_HISTORICAL_FRONTIER'
elif beats_l>=2:status='M1_CORE_SATELLITE_BEATS_EXECUTABLE_CORE_NOT_ALL_MARKET'
else:status='M1_CORE_SATELLITE_REJECTED_AS_WINRATE_UPGRADE'

with EVENTS.open('w',encoding='utf-8') as fh:
    for r in rows:fh.write(json.dumps(r,ensure_ascii=False)+'\n')
res={
 'status':status,'model':'M1 80% liquidity20 market core + 20% downside-tail5 alpha satellite',
 'timing':'signal after t close; predetermined entry t+1 close; exit t+2 open',
 'new_mode':'Treat broad diversification as the primary win-rate engine. Allocate a fixed 80% to a prior-turnover liquid core and only 20% to five 2023-fitted downside-tail names. No timing gate, no weight sweep, no threshold search.',
 'fixed_design':{'core_n':CORE_N,'satellite_n':SAT_N,'core_weight':CORE_WEIGHT,'satellite_weight':SAT_WEIGHT},
 'leakage_hardening':'Uses W1 signal-time-only universe and fail-closed -15% treatment for selected future missing/discontinuous legs.',
 'protocol':{'fit_tail_score':'2023 only','day_filter':'none','primary_cost':PRIMARY_COST,'cost_stress':COSTS,'2024_2026':'post-C0 historical diagnostics, not pristine OOS'},
 'results':report,'comparisons_20bp':comparisons,'beats_L20_years':beats_l,'beats_ALL_EQUAL_years':beats_all,
 'events_file':str(EVENTS.relative_to(ROOT)),
 'research_boundary':'Architecture fixed before reading W1 result. All reported later years are historical diagnostics and still require prospective confirmation.',
 'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
 'caveat':'Historical research only. Execution, fees, slippage, capacity and corporate actions remain live-trading risks.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('M1_RESULT='+json.dumps(res,ensure_ascii=False,separators=(',',':')))
