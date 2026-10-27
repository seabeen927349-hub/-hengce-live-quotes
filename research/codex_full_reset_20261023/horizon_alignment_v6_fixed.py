#!/usr/bin/env python3
from __future__ import annotations
import json, math, statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v13_weak_regime_profiles as v13

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/horizon_alignment_v6_fixed_result.json'
V6=(.20,.25,.30,.05,.20)
START='2024-01-01'; END='2026-10-22'
HORIZONS=(1,2,3,5,10,20)
COSTS=(0.0,0.002,0.004)
REGIMES=(('ALL',0.0),('STRONG',0.50))
Z95=1.959963984540054


def wilson_lower(w,n,z=Z95):
    if n<=0:return None
    p=w/n;z2=z*z;den=1+z2/n
    center=p+z2/(2*n)
    rad=z*math.sqrt(p*(1-p)/n+z2/(4*n*n))
    return (center-rad)/den


def top1_v6(d):
    F=v13.features.get(d,{})
    arr=[]
    for t,vals in F.items():
        score=sum(V6[i]*vals[i] for i in range(5))
        arr.append((score,t))
    arr.sort(key=lambda z:(-z[0],z[1]))
    return arr[0] if arr else None


def outcome(signal_date,t,h):
    i=v13.dates.index(signal_date)
    # Preserve the existing next-day definition at H=1:
    # signal after t close; enter t+1 open; exit t+(H+1) close.
    if i+1>=len(v13.dates) or i+h+1>=len(v13.dates):return None
    entry_date=v13.dates[i+1];exit_date=v13.dates[i+h+1]
    e=v13.by[entry_date].get(t);x=v13.by[exit_date].get(t)
    if not e or not x or e.o is None or x.c is None or e.o<=0 or x.c<=0 or e.bad or x.bad:return None
    return {'signal_date':signal_date,'entry_date':entry_date,'exit_date':exit_date,'ticker':t,'ret':x.c/e.o-1,'breadth20':v13.breadth.get(signal_date,0.0)}


def summarize(rows,cost,h):
    rs=[r['ret']-cost for r in rows]
    n=len(rs);w=sum(x>0 for x in rs)
    nav=1.;peak=1.;mdd=0.
    for x in rs:
        nav*=1+x;peak=max(peak,nav);mdd=min(mdd,nav/peak-1)
    mean=statistics.mean(rs) if rs else None
    return {
        'trades':n,'wins':w,'losses':n-w,
        'win_rate':w/n if n else None,
        'wilson95_lower':wilson_lower(w,n) if n else None,
        'mean_return':mean,
        'mean_return_per_horizon_session':mean/h if mean is not None else None,
        'median_return':statistics.median(rs) if rs else None,
        'worst_return':min(rs) if rs else None,
        'best_return':max(rs) if rs else None,
        'naive_compounded_return':nav-1 if n else 0.0,
        'naive_max_drawdown':mdd,
    }

# Build one fixed Top1 signal per signal date, then evaluate every horizon from exactly that signal.
signals=[]
for d in v13.dates:
    if d<START or d>END:continue
    top=top1_v6(d)
    if top:
        score,t=top
        signals.append({'signal_date':d,'ticker':t,'score':score,'breadth20':v13.breadth.get(d,0.0)})

results={}
for regime,gate in REGIMES:
    results[regime]={}
    for h in HORIZONS:
        rows=[]
        for s in signals:
            if s['breadth20']<gate:continue
            r=outcome(s['signal_date'],s['ticker'],h)
            if r:rows.append(r)
        by_year={}
        for y in ('2024','2025','2026'):
            yr=[r for r in rows if r['signal_date'].startswith(y)]
            by_year[y]={str(c):summarize(yr,c,h) for c in COSTS}
        ycounts={y:sum(r['signal_date'].startswith(y) for r in rows) for y in ('2024','2025','2026')}
        sample_ok=len(rows)>=60 and min(ycounts.values())>=15
        gross=summarize(rows,0.0,h);c20=summarize(rows,0.002,h);c40=summarize(rows,0.004,h)
        gross_year=[by_year[y]['0.0'] for y in ('2024','2025','2026')]
        # Predeclared descriptive onset criterion; not used to tune any rule.
        stable_edge=(sample_ok and gross['win_rate'] is not None and gross['win_rate']>=0.55
                     and all(x['win_rate'] is not None and x['win_rate']>0.50 for x in gross_year)
                     and all(x['mean_return'] is not None and x['mean_return']>0 for x in gross_year)
                     and c20['mean_return'] is not None and c20['mean_return']>0)
        results[regime][str(h)]={
            'timing':f'signal after t close; enter t+1 open; exit t+{h+1} close',
            'sample_ok':sample_ok,'year_counts':ycounts,
            'combined':{'0.0':gross,'0.002':c20,'0.004':c40},
            'years':by_year,'stable_edge':stable_edge,
        }

onset={}
for regime,_ in REGIMES:
    good=[h for h in HORIZONS if results[regime][str(h)]['stable_edge']]
    onset[regime]=min(good) if good else None

# Descriptive ranking only: prioritize cross-year consistency, then combined win rate.
ranking={}
for regime,_ in REGIMES:
    arr=[]
    for h in HORIZONS:
        block=results[regime][str(h)]
        yrs=[block['years'][y]['0.0']['win_rate'] for y in ('2024','2025','2026')]
        minyr=min(x for x in yrs if x is not None)
        comb=block['combined']['0.0']
        arr.append({'horizon':h,'min_year_win_rate':minyr,'combined_win_rate':comb['win_rate'],'combined_mean_return':comb['mean_return'],'combined_mean_per_session':comb['mean_return_per_horizon_session'],'stable_edge':block['stable_edge']})
    arr.sort(key=lambda z:(-z['min_year_win_rate'],-z['combined_win_rate'],-z['combined_mean_per_session'],z['horizon']))
    ranking[regime]=arr

res={
 'status':'HORIZON_ALIGNMENT_COMPLETE',
 'objective':'fixed-signal horizon alignment for existing V6 Top1; identify where directional edge becomes cross-year stable without retuning weights or thresholds',
 'signal':'V6 Top1 using fixed weights (0.20,0.25,0.30,0.05,0.20)',
 'period':f'{START} through {END}',
 'horizons':HORIZONS,
 'regimes':{'ALL':'no breadth gate','STRONG':'canonical breadth20 >= 0.50'},
 'cost_stress':COSTS,
 'results':results,
 'alignment_onset':onset,
 'descriptive_ranking':ranking,
 'stable_edge_definition':'sample >=60 and >=15/year; gross combined win rate >=55%; every year gross win rate >50%; every year gross mean return >0; combined mean return remains >0 after 20bp stress',
 'interpretation_guards':[
   'No factor weights, breadth thresholds, horizons, or labels are selected after seeing these results; horizon set was fixed at 1/2/3/5/10/20.',
   'Naive compounded return and drawdown treat overlapping horizon trades sequentially and are not portfolio-realistic; use win rate and per-trade mean/median as primary alignment metrics.',
   'This is descriptive historical research on an already-exposed archive, not future unseen market data and not a guarantee.'
 ],
 'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False}
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('===HORIZON_ALIGNMENT===')
print(json.dumps(res,ensure_ascii=False,indent=2))
