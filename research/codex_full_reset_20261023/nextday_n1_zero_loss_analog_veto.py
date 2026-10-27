#!/usr/bin/env python3
from __future__ import annotations
import json, math, statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v13_weak_regime_profiles as v13

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/nextday_n1_zero_loss_analog_veto_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/nextday_n1_events.jsonl'
PERIODS=v13.PERIODS
MIN_PRIOR_SAME_REGIME=40
K_NEIGHBORS=12
MIN_TURNOVER=20_000_000.0
COST_STRESS=(0.0,0.002,0.004)


def pct_rank(vals):
    a=sorted(vals.items(),key=lambda kv:(kv[1],kv[0])); n=len(a); out={}
    if n<=1:return {t:.5 for t,_ in a}
    for i,(t,_) in enumerate(a):out[t]=i/(n-1)
    return out


def day_candidates(d):
    F=v13.features.get(d,{})
    raw={}
    for t in F:
        r=v13.by[d].get(t)
        if r is None or r.c is None or r.o is None or r.o<=0 or r.turn is None or r.turn20 is None or r.turn20<MIN_TURNOVER:
            continue
        if r.r1 is None or r.r5 is None or r.vol20 is None or r.vol20<=0:continue
        body=r.c/r.o-1
        turn_acc=r.turn/r.turn20 if r.turn20>0 else None
        if turn_acc is None or not math.isfinite(turn_acc):continue
        raw[t]={'r1':r.r1,'r5':r.r5,'body':body,'turn_acc':turn_acc,'lowvol':-r.vol20}
    if len(raw)<20:return []
    ranks={k:pct_rank({t:x[k] for t,x in raw.items()}) for k in ('r1','r5','body','turn_acc','lowvol')}
    out=[]
    for t in raw:
        score=statistics.mean(ranks[k][t] for k in ranks)
        out.append((score,t,raw[t]))
    out.sort(key=lambda z:(-z[0],z[1]))
    return out


def nextday_return(d,t):
    i=v13.dates.index(d)
    if i+1>=len(v13.dates):return None
    nd=v13.dates[i+1]
    a=v13.by[d].get(t); b=v13.by[nd].get(t)
    if not a or not b or a.c is None or b.c is None or a.c<=0 or b.c<=0 or b.bad:return None
    return b.c/a.c-1,nd


def summarize(events,cost):
    rs=[e['nextday_return']-cost for e in events]
    nav=1.0; peak=1.0; mdd=0.0
    for r in rs:
        nav*=1+r; peak=max(peak,nav); mdd=min(mdd,nav/peak-1)
    return {'trades':len(rs),'wins':sum(r>0 for r in rs),'losses':sum(r<=0 for r in rs),'win_rate':sum(r>0 for r in rs)/len(rs) if rs else None,'compounded_return':nav-1 if rs else 0.0,'mean_return':statistics.mean(rs) if rs else None,'worst_return':min(rs) if rs else None,'max_drawdown':mdd}

history=[]; events=[]; rejected={'warmup':0,'analog_loss_veto':0,'invalid_outcome':0}
for d in v13.dates:
    if d<'2024-01-01' or d>'2026-10-22':continue
    cand=day_candidates(d)
    if not cand:continue
    score,t,diag=cand[0]
    regime='STRONG' if v13.breadth.get(d,0)>=v13.BREADTH_CUTOFF else 'WEAK'
    same=[h for h in history if h['regime']==regime]
    take=False; neigh=[]
    if len(same)<MIN_PRIOR_SAME_REGIME:
        rejected['warmup']+=1
    else:
        neigh=sorted(same,key=lambda h:(abs(h['score']-score),h['signal_date']))[:K_NEIGHBORS]
        take=(len(neigh)==K_NEIGHBORS and all(h['nextday_return']>0 for h in neigh))
        if not take:rejected['analog_loss_veto']+=1
    outcome=nextday_return(d,t)
    if outcome is None:
        rejected['invalid_outcome']+=1
        continue
    ret,exit_date=outcome
    rec={'signal_date':d,'exit_date':exit_date,'ticker':t,'score':score,'regime':regime,'nextday_return':ret,'take_trade':take,'neighbor_count':len(neigh),'neighbor_losses':sum(h['nextday_return']<=0 for h in neigh),'neighbor_worst':min((h['nextday_return'] for h in neigh),default=None),'features':diag}
    if take:events.append(rec)
    history.append(rec)

years={}
for y,(s,e) in PERIODS.items():
    ys=[x for x in events if s<=x['signal_date']<=e]
    years[y]={str(c):summarize(ys,c) for c in COST_STRESS}
combined={str(c):summarize(events,c) for c in COST_STRESS}
zero_loss_gross=(combined['0.0']['trades']>0 and combined['0.0']['losses']==0)
zero_loss_20bp=(combined['0.002']['trades']>0 and combined['0.002']['losses']==0)
status='N1_ZERO_LOSS_SAMPLE_FOUND' if zero_loss_gross else ('N1_NO_TRADES_PASSED_VETO' if not events else 'N1_REJECTED_HAS_LOSSES')
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in events:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'objective':'precision-first next-day close-to-close; any non-positive gross next-day trade is a model failure','signal_timing':'after signal-date close; entry reference=signal-date close; exit reference=next trading-day close','method':'daily Top1 fixed continuation composite (r1,r5,intraday close/open body, turnover acceleration, low volatility), then expanding prior-only same-regime nearest-score counterexample veto. Trade only if all 12 nearest prior same-regime Top1 analogs were positive. No grid and no future outcome enters a signal decision.','min_prior_same_regime':MIN_PRIOR_SAME_REGIME,'k_neighbors':K_NEIGHBORS,'rejected':rejected,'candidate_history':len(history),'events_file':str(EVENTS.relative_to(ROOT)),'years':years,'combined':combined,'zero_loss_gross':zero_loss_gross,'zero_loss_after_20bp_stress':zero_loss_20bp,'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Historical simulation on the already-exposed 2024-2026 research period. Zero historical losses, if observed, is not a guarantee of future gains; prospective post-lock evidence is required.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(res,ensure_ascii=False,indent=2))
