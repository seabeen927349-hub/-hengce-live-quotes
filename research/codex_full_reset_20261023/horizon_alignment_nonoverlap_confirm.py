#!/usr/bin/env python3
from __future__ import annotations
import json, math, statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v13_weak_regime_profiles as v13

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/horizon_alignment_nonoverlap_confirm_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/horizon_alignment_nonoverlap_confirm_events.jsonl'
V6=(.20,.25,.30,.05,.20)
START='2024-01-01'; END='2026-10-22'
HORIZONS=(3,10)
BREADTH_GATE=.50
COSTS=(0.0,.002,.004)
Z95=1.959963984540054


def wilson_lower(w,n,z=Z95):
    if n<=0:return None
    p=w/n;z2=z*z;den=1+z2/n
    center=p+z2/(2*n)
    rad=z*math.sqrt(p*(1-p)/n+z2/(4*n*n))
    return (center-rad)/den


def top1(d):
    F=v13.features.get(d,{})
    arr=[]
    for t,vals in F.items():
        s=sum(V6[i]*vals[i] for i in range(5))
        arr.append((s,t))
    arr.sort(key=lambda z:(-z[0],z[1]))
    return arr[0] if arr else None


def make_trade(signal_date,t,h,score,breadth):
    i=v13.dates.index(signal_date)
    if i+1>=len(v13.dates) or i+h+1>=len(v13.dates):return None
    entry_date=v13.dates[i+1]; exit_date=v13.dates[i+h+1]
    e=v13.by[entry_date].get(t); x=v13.by[exit_date].get(t)
    if not e or not x or e.o is None or x.c is None or e.o<=0 or x.c<=0 or e.bad or x.bad:return None
    return {'horizon':h,'signal_date':signal_date,'entry_date':entry_date,'exit_date':exit_date,'ticker':t,'score':score,'breadth20':breadth,'gross_return':x.c/e.o-1}


def schedule(h):
    rows=[]; last_exit=None
    for d in v13.dates:
        if d<START or d>END:continue
        if last_exit is not None and d<last_exit:continue
        breadth=v13.breadth.get(d,0.0)
        if breadth<BREADTH_GATE:continue
        z=top1(d)
        if not z:continue
        score,t=z
        r=make_trade(d,t,h,score,breadth)
        if not r:continue
        rows.append(r)
        # Position exits at this date's close; a signal observed at the same close is allowed,
        # but scanning is once per date so the next eligible signal is naturally later.
        last_exit=r['exit_date']
    return rows


def stats(rows,cost):
    rs=[r['gross_return']-cost for r in rows]
    n=len(rs); w=sum(x>0 for x in rs)
    nav=1.;peak=1.;mdd=0.
    for x in rs:
        nav*=1+x;peak=max(peak,nav);mdd=min(mdd,nav/peak-1)
    return {'trades':n,'wins':w,'losses':n-w,'win_rate':w/n if n else None,
            'wilson95_lower':wilson_lower(w,n) if n else None,
            'mean_return':statistics.mean(rs) if rs else None,
            'median_return':statistics.median(rs) if rs else None,
            'worst_return':min(rs) if rs else None,'best_return':max(rs) if rs else None,
            'compounded_return':nav-1 if n else 0.,'max_drawdown':mdd}

results={}; all_events=[]
for h in HORIZONS:
    rows=schedule(h); all_events.extend(rows)
    years={}
    for y in ('2024','2025','2026'):
        yr=[r for r in rows if r['signal_date'].startswith(y)]
        years[y]={str(c):stats(yr,c) for c in COSTS}
    combined={str(c):stats(rows,c) for c in COSTS}
    counts={y:years[y]['0.0']['trades'] for y in years}
    gross=combined['0.0']; c20=combined['0.002']
    confirm=(gross['trades']>=30 and min(counts.values())>=8
             and gross['win_rate'] is not None and gross['win_rate']>=.52
             and all(years[y]['0.0']['win_rate'] is not None and years[y]['0.0']['win_rate']>=.50 for y in years)
             and all(years[y]['0.0']['mean_return'] is not None and years[y]['0.0']['mean_return']>0 for y in years)
             and c20['mean_return'] is not None and c20['mean_return']>0)
    results[str(h)]={'timing':f'signal after t close; enter t+1 open; exit t+{h+1} close',
                     'scheduler':'strict single-position non-overlap; ignore any new signal while prior position remains open',
                     'year_counts':counts,'combined':combined,'years':years,'confirmation_pass':confirm}

EVENTS.write_text('\n'.join(json.dumps(x,ensure_ascii=False) for x in sorted(all_events,key=lambda r:(r['horizon'],r['signal_date'])))+'\n',encoding='utf-8')
res={
 'status':'HORIZON_NONOVERLAP_CONFIRM_COMPLETE',
 'objective':'confirm only the preregistered H3 and H10 STRONG horizons under a strict one-position-at-a-time schedule; no new model or horizon search',
 'source_signal':'fixed V6 Top1 weights (0.20,0.25,0.30,0.05,0.20), canonical STRONG breadth20 >= 0.50',
 'period':f'{START} through {END}','horizons':HORIZONS,'cost_stress':COSTS,
 'confirmation_rule':'per horizon: >=30 trades total and >=8/year; gross combined win rate >=52%; every year gross win rate >=50%; every year gross mean return >0; combined mean return after 20bp >0',
 'results':results,
 'confirmed_horizons':[h for h in HORIZONS if results[str(h)]['confirmation_pass']],
 'interpretation_guards':[
   'H3 and H10 were chosen only because they passed the immediately prior fixed horizon-alignment criterion; no other horizon is tested here.',
   'No V6 weights, breadth gate, holding period, scheduler, label, cost, or confirmation threshold is changed after observing this run.',
   'Single-position compounding is portfolio-interpretable for this simplified cash-only schedule, but excludes taxes, slippage beyond stated stress, liquidity constraints, and execution uncertainty.',
   'Historical archive is already exposed by prior research; this confirmation is diagnostic historical evidence, not future unseen OOS and not a performance guarantee.'
 ],
 'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False}
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('===HORIZON_NONOVERLAP_CONFIRM===')
print(json.dumps(res,ensure_ascii=False,indent=2))
