#!/usr/bin/env python3
from __future__ import annotations
import json, math, statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v13_weak_regime_profiles as v13

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/nextday_n2_executable_analog_veto_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/nextday_n2_events.jsonl'
PERIODS=v13.PERIODS
MIN_PRIOR_SAME_REGIME=60
K_NEIGHBORS=16
MIN_TURNOVER=20_000_000.0
COST_STRESS=(0.0,0.002,0.004)


def pct_rank(vals):
    a=sorted(vals.items(),key=lambda kv:(kv[1],kv[0]));n=len(a);out={}
    if n<=1:return {t:.5 for t,_ in a}
    i=0
    while i<n:
        j=i+1
        while j<n and a[j][1]==a[i][1]:j+=1
        p=(((i+1)+j)/2-1)/(n-1)
        for k in range(i,j):out[a[k][0]]=p
        i=j
    return out


def day_top(d):
    F=v13.features.get(d,{})
    raw={}
    for t in F:
        r=v13.by[d].get(t)
        if r is None or r.c is None or r.o is None or r.o<=0 or r.turn is None or r.turn20 is None or r.turn20<MIN_TURNOVER:continue
        if r.r1 is None or r.r5 is None or r.r20 is None or r.vol20 is None or r.vol20<=0:continue
        body=r.c/r.o-1
        ta=r.turn/r.turn20 if r.turn20>0 else None
        if ta is None or not math.isfinite(ta):continue
        raw[t]={'r1':r.r1,'r5':r.r5,'r20':r.r20,'body':body,'turn_acc':ta,'lowvol':-r.vol20}
    if len(raw)<20:return None
    rr={k:pct_rank({t:x[k] for t,x in raw.items()}) for k in raw[next(iter(raw))]}
    rows=[]
    for t in raw:
        vec={k:rr[k][t] for k in rr}
        # fixed continuation-quality composite; no fit/grid
        score=statistics.mean((vec['r1'],vec['r5'],vec['r20'],vec['body'],vec['turn_acc'],vec['lowvol']))
        rows.append((score,t,vec,raw[t]))
    rows.sort(key=lambda z:(-z[0],z[1]))
    return rows[0]


def overnight_outcome(signal_date,t):
    i=v13.dates.index(signal_date)
    if i+2>=len(v13.dates):return None
    entry_date=v13.dates[i+1];exit_date=v13.dates[i+2]
    e=v13.by[entry_date].get(t);x=v13.by[exit_date].get(t)
    if not e or not x or e.o is None or x.c is None or e.o<=0 or x.c<=0 or e.bad or x.bad:return None
    return x.c/e.o-1,entry_date,exit_date


def dist(a,b):
    keys=('r1','r5','r20','body','turn_acc','lowvol')
    return math.sqrt(sum((a[k]-b[k])**2 for k in keys)/len(keys))


def summarize(events,cost):
    rs=[e['overnight_return']-cost for e in events]
    nav=1.0;peak=1.0;mdd=0.0
    for r in rs:
        nav*=1+r;peak=max(peak,nav);mdd=min(mdd,nav/peak-1)
    return {'trades':len(rs),'wins':sum(r>0 for r in rs),'losses':sum(r<=0 for r in rs),'win_rate':sum(r>0 for r in rs)/len(rs) if rs else None,'compounded_return':nav-1 if rs else 0.0,'mean_return':statistics.mean(rs) if rs else None,'worst_return':min(rs) if rs else None,'max_drawdown':mdd}

records=[];events=[];rejected={'warmup':0,'analog_loss_veto':0,'invalid_outcome':0}
for d in v13.dates:
    if d<'2024-01-01' or d>'2026-10-22':continue
    top=day_top(d)
    if top is None:continue
    score,t,vec,raw=top
    regime='STRONG' if v13.breadth.get(d,0)>=v13.BREADTH_CUTOFF else 'WEAK'
    # Only labels fully realized by this signal close are allowed.
    prior=[h for h in records if h['regime']==regime and h['exit_date']<=d]
    neigh=[];take=False
    if len(prior)<MIN_PRIOR_SAME_REGIME:
        rejected['warmup']+=1
    else:
        neigh=sorted(prior,key=lambda h:(dist(vec,h['rank_vector']),h['signal_date']))[:K_NEIGHBORS]
        take=(len(neigh)==K_NEIGHBORS and all(h['overnight_return']>0 for h in neigh))
        if not take:rejected['analog_loss_veto']+=1
    o=overnight_outcome(d,t)
    if o is None:
        rejected['invalid_outcome']+=1
        continue
    ret,entry_date,exit_date=o
    rec={'signal_date':d,'entry_date':entry_date,'exit_date':exit_date,'ticker':t,'score':score,'regime':regime,'overnight_return':ret,'take_trade':take,'rank_vector':vec,'raw_features':raw,'prior_realized_same_regime':len(prior),'neighbor_count':len(neigh),'neighbor_losses':sum(h['overnight_return']<=0 for h in neigh),'neighbor_worst':min((h['overnight_return'] for h in neigh),default=None)}
    if take:events.append(rec)
    records.append(rec)

years={}
for y,(s,e) in PERIODS.items():
    ys=[x for x in events if s<=x['signal_date']<=e]
    years[y]={str(c):summarize(ys,c) for c in COST_STRESS}
combined={str(c):summarize(events,c) for c in COST_STRESS}
zero_gross=combined['0.0']['trades']>0 and combined['0.0']['losses']==0
zero_20=combined['0.002']['trades']>0 and combined['0.002']['losses']==0
sample_ok=combined['0.0']['trades']>=30 and all(years[y]['0.0']['trades']>=5 for y in PERIODS)
status='N2_ZERO_LOSS_SAMPLE_QUALIFIED' if zero_gross and sample_ok else ('N2_ZERO_LOSS_TOO_SPARSE' if zero_gross else ('N2_NO_TRADES_PASSED_VETO' if not events else 'N2_REJECTED_HAS_LOSSES'))
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in events:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'objective':'precision-first executable one-overnight trade; any non-positive gross trade fails zero-loss','timing':'signal after day t close using only t-and-prior daily data; enter day t+1 open; exit day t+2 close','method':'fixed daily Top1 continuation-quality composite followed by expanding prior-only same-regime 6D nearest-analog counterexample veto; all 16 nearest fully-realized analogs must have positive overnight returns. No parameter grid.','min_prior_same_regime':MIN_PRIOR_SAME_REGIME,'k_neighbors':K_NEIGHBORS,'sample_rule':'at least 30 trades overall and at least 5 signal trades in each of 2024/2025/2026 before calling a zero-loss sample qualified','candidate_records':len(records),'rejected':rejected,'events_file':str(EVENTS.relative_to(ROOT)),'years':years,'combined':combined,'zero_loss_gross':zero_gross,'zero_loss_after_20bp_stress':zero_20,'sample_ok':sample_ok,'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Historical simulation on already-exposed research history. Even a qualified zero-loss sample cannot guarantee future gains and requires prospective validation.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(res,ensure_ascii=False,indent=2))
