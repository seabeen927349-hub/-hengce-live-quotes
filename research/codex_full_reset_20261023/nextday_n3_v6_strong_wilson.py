#!/usr/bin/env python3
from __future__ import annotations
import json, math, statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v13_weak_regime_profiles as v13

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/nextday_n3_v6_strong_wilson_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/nextday_n3_events.jsonl'
V6=(.20,.25,.30,.05,.20)
MIN_PRIOR_COHORT=25
Z95=1.959963984540054
COST_STRESS=(0.0,0.002,0.004)
EVAL_START='2024-01-01'
EVAL_END='2026-10-22'


def wilson_lower(w,n,z=Z95):
    if n<=0:return None
    p=w/n;z2=z*z;den=1+z2/n
    center=p+z2/(2*n)
    rad=z*math.sqrt(p*(1-p)/n+z2/(4*n*n))
    return (center-rad)/den


def top1_v6(d):
    F=v13.features.get(d,{})
    if not F:return None
    arr=[]
    for t,vals in F.items():
        score=sum(V6[i]*vals[i] for i in range(5))
        arr.append((score,t,vals))
    arr.sort(key=lambda z:(-z[0],z[1]))
    if not arr:return None
    score,t,vals=arr[0]
    second=arr[1][0] if len(arr)>1 else score
    return score,t,vals,score-second


def overnight_outcome(signal_date,t):
    i=v13.dates.index(signal_date)
    if i+2>=len(v13.dates):return None
    entry_date=v13.dates[i+1];exit_date=v13.dates[i+2]
    e=v13.by[entry_date].get(t);x=v13.by[exit_date].get(t)
    if not e or not x or e.o is None or x.c is None or e.o<=0 or x.c<=0 or e.bad or x.bad:return None
    return x.c/e.o-1,entry_date,exit_date


def summarize(events,cost):
    rs=[e['overnight_return']-cost for e in events]
    nav=1.;peak=1.;mdd=0.
    for r in rs:
        nav*=1+r;peak=max(peak,nav);mdd=min(mdd,nav/peak-1)
    return {'trades':len(rs),'wins':sum(r>0 for r in rs),'losses':sum(r<=0 for r in rs),'win_rate':sum(r>0 for r in rs)/len(rs) if rs else None,'compounded_return':nav-1 if rs else 0.0,'mean_return':statistics.mean(rs) if rs else None,'median_return':statistics.median(rs) if rs else None,'worst_return':min(rs) if rs else None,'max_drawdown':mdd}

records=[];events=[];diag={'weak_regime':0,'insufficient_prior_cohort':0,'wilson_veto':0,'invalid_outcome':0}
for d in v13.dates:
    if d<'2023-01-01' or d>EVAL_END:continue
    top=top1_v6(d)
    if top is None:continue
    score,t,vals,margin=top
    regime='STRONG' if v13.breadth.get(d,0)>=v13.BREADTH_CUTOFF else 'WEAK'
    o=overnight_outcome(d,t)
    if o is None:
        diag['invalid_outcome']+=1
        continue
    ret,entry_date,exit_date=o
    # Signal decision uses only fully-realized prior STRONG Top1 records. 2023 is training-only warmup.
    prior=[h for h in records if h['regime']=='STRONG' and h['exit_date']<=d and h['score']>=score]
    wins=sum(h['overnight_return']>0 for h in prior)
    lb=wilson_lower(wins,len(prior)) if len(prior)>=MIN_PRIOR_COHORT else None
    take=False
    if regime!='STRONG':
        diag['weak_regime']+=1
    elif len(prior)<MIN_PRIOR_COHORT:
        diag['insufficient_prior_cohort']+=1
    elif lb is None or lb<=.50:
        diag['wilson_veto']+=1
    else:
        take=True
    rec={'signal_date':d,'entry_date':entry_date,'exit_date':exit_date,'ticker':t,'score':score,'margin_top1_top2':margin,'factor_ranks':{'resid_rev':vals[0],'mom20':vals[1],'skip5_60':vals[2],'liquidity':vals[3],'lowvol':vals[4]},'breadth20':v13.breadth.get(d),'regime':regime,'overnight_return':ret,'take_trade':take,'prior_dominating_strong_n':len(prior),'prior_dominating_strong_wins':wins,'prior_dominating_win_rate':wins/len(prior) if prior else None,'wilson95_lower':lb,'training_only':d<EVAL_START}
    records.append(rec)
    if take and EVAL_START<=d<=EVAL_END:events.append(rec)

years={}
for y,(s,e) in v13.PERIODS.items():
    ys=[x for x in events if s<=x['signal_date']<=e]
    years[y]={str(c):summarize(ys,c) for c in COST_STRESS}
combined={str(c):summarize(events,c) for c in COST_STRESS}
zero_gross=combined['0.0']['trades']>0 and combined['0.0']['losses']==0
zero_20=combined['0.002']['trades']>0 and combined['0.002']['losses']==0
sample_ok=combined['0.0']['trades']>=20 and sum(years[y]['0.0']['trades']>0 for y in years)>=2
if zero_gross and sample_ok:status='N3_ZERO_LOSS_SAMPLE_QUALIFIED'
elif zero_gross:status='N3_ZERO_LOSS_TOO_SPARSE'
elif not events:status='N3_NO_TRADES_PASSED_CONFIDENCE'
else:status='N3_REJECTED_HAS_LOSSES'
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in events:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'objective':'bounded final N-series test: maximize next-day precision without nearest-neighbor unanimity or parameter search','timing':'signal after t close; enter t+1 open; exit t+2 close','method':'frozen V6 five-factor Top1, only canonical STRONG breadth regime. For each current score, form an expanding prior-only cohort of fully-realized STRONG Top1 observations with score >= current score; take only when the conventional 95% Wilson lower bound of prior win probability is above 50%. 2023 is training-only warmup; evaluation is 2024-2026. No grid.','v6_weights':V6,'breadth_cutoff':v13.BREADTH_CUTOFF,'min_prior_cohort':MIN_PRIOR_COHORT,'confidence_level':.95,'decision_floor':.50,'diagnostics':diag,'candidate_records':len(records),'events_file':str(EVENTS.relative_to(ROOT)),'years':years,'combined':combined,'zero_loss_gross':zero_gross,'zero_loss_after_20bp_stress':zero_20,'sample_ok':sample_ok,'new_model_evaluations':1,'research_boundary':'N1-N3 bounded series complete; do not tune thresholds/K/weights on this exposed period','authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Historical simulation on already-exposed research history. A historical zero-loss sample cannot guarantee future gains.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(res,ensure_ascii=False,indent=2))
