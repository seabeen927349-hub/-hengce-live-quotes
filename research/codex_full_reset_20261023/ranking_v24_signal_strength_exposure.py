#!/usr/bin/env python3
from __future__ import annotations
import json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v19_diversification as v19

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v24_signal_strength_exposure_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v24_events.jsonl'
COSTS=(.008,.012,.016)
V19_REF={'ret':2.3394980651997064,'dd':-0.25113023981269567,'rem':1.1916614382781274}
DATES=v19.v15.v13.dates;DI={d:i for i,d in enumerate(DATES)}

# Signal strength is computed from the frozen V6 score distribution only.
DAILY_CONF={}
for d,F in v19.v15.v13.features.items():
    scores=[]
    for t,v in F.items():
        s=sum(v19.v15.v13.V6[i]*v[i] for i in range(5));scores.append((s,t))
    if len(scores)<10:continue
    vals=[s for s,t in scores];sd=statistics.stdev(vals) if len(set(vals))>1 else 0.0
    if sd<=0:continue
    vals_sorted=sorted(vals,reverse=True)
    conf=(statistics.mean(vals_sorted[:3])-statistics.median(vals))/sd
    DAILY_CONF[d]=conf

PRIOR_MED={}
for d,c in DAILY_CONF.items():
    i=DI[d];prior=[]
    for j in range(max(0,i-60),i):
        q=DAILY_CONF.get(DATES[j])
        if q is not None:prior.append(q)
    PRIOR_MED[d]=statistics.median(prior) if len(prior)>=20 else None

BASE,INVALID=v19.build_variant(3,'INV_VOL')

def clip(x,lo,hi):return max(lo,min(hi,x))

def adjusted_exposure(e):
    base=e['exposure'];c=DAILY_CONF.get(e['signal_date']);pm=PRIOR_MED.get(e['signal_date'])
    if c is None or pm is None or pm<=0:return base,1.0,c,pm
    mult=clip(c/pm,.75,1.10)
    # No leverage above 100%; strong signals can restore reduced V17 exposure toward 100%.
    ex=clip(base*mult,.20,1.0)
    return ex,mult,c,pm

EV=[]
for e in BASE:
    z=dict(e);ex,m,c,pm=adjusted_exposure(z);z['base_exposure']=z['exposure'];z['exposure']=ex;z['confidence_multiplier']=m;z['signal_confidence']=c;z['prior60_median_confidence']=pm;EV.append(z)
complete=(not INVALID and len(EV)==len(v19.v15.base))

def product(xs):
    n=1.
    for x in xs:n*=1+x
    return n-1

def summarize(events,cost):
    nets=[];nav=1.;peak=1.;mdd=0.
    for e in events:
        ex=e['exposure'];net=ex*(e['gross_return']-cost);nets.append(net);b=nav
        for j,(d,r) in enumerate(e['daily']):
            temp=b*(1+ex*r-(ex*cost if j==len(e['daily'])-1 else 0));peak=max(peak,temp);mdd=min(mdd,temp/peak-1)
        nav=b*(1+net)
    bi=max(range(len(nets)),key=lambda k:nets[k]) if nets else None
    return {'baskets':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,'compounded_return':product(nets),'max_drawdown':mdd,'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,'mean_net_return':statistics.mean(nets) if nets else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None}

years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in v19.v15.v13.PERIODS}
combined={str(c):summarize(EV,c) for c in COSTS}
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
c=combined['0.012'];strict=robust and c['compounded_return']>V19_REF['ret'] and c['max_drawdown']>V19_REF['dd'] and c['remove_best_basket_return']>V19_REF['rem'];risk=robust and c['max_drawdown']>=-.22 and c['compounded_return']>=2.20 and c['remove_best_basket_return']>=1.10
status='V24_STRICTLY_DOMINATES_V19' if strict else ('V24_MATERIAL_RISK_IMPROVEMENT' if risk else 'V24_DOES_NOT_BEAT_V19')
res={'status':status,'method':'single fixed V19 candidate with signal-time confidence exposure multiplier: confidence=(mean top3 frozen-V6 score - median eligible score)/cross-sectional score stdev; multiplier=clip(confidence/prior60-session median confidence,0.75,1.10); final exposure=clip(V17 exposure*multiplier,0.20,1.00)','complete_common_schedule':complete,'invalid':INVALID,'years':years,'combined':combined,'v19_reference':V19_REF,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Single structural candidate evaluated on exposed 2024-2026 history. Confidence and its prior-60 reference use signal-time/prior-only cross-sectional information; no new data.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
