#!/usr/bin/env python3
from __future__ import annotations
import json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v19_diversification as v19

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v25_conviction_risk_weight_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v25_events.jsonl'
COSTS=(.008,.012,.016)
V19_REF={'ret':2.3394980651997064,'dd':-0.25113023981269567,'rem':1.1916614382781274}
DATES=v19.v15.v13.dates;DI={d:i for i,d in enumerate(DATES)}


def score_map(d):
    F=v19.v15.v13.features.get(d,{})
    return {t:sum(v19.v15.v13.V6[i]*v[i] for i in range(5)) for t,v in F.items()}


def build():
    out=[];invalid=[]
    for b in sorted(v19.v15.base,key=lambda e:e['signal_date']):
        d=b['signal_date'];si=DI[d];scores=score_map(d);picks=v19.cache.get(d,[])[:3]
        if len(picks)<3 or len(scores)<10:
            invalid.append([d,'MISSING_SCORE_OR_PICKS']);continue
        med=statistics.median(scores.values());rows=[];raw=[];ok=True
        for t in picks:
            r=v19.v15.v13.by[d].get(t);o=v19.v15.v13.outcome(t,si);s=scores.get(t)
            if r is None or r.vol20 is None or r.vol20<=0 or o is None or s is None:
                ok=False;break
            margin=max(s-med,1e-6)
            rows.append((t,o,r.vol20,s,margin));raw.append(margin/r.vol20)
        if not ok or sum(raw)<=0:
            invalid.append([d,'INVALID_OUTCOME_VOL_OR_WEIGHT']);continue
        ss=sum(raw);w=[x/ss for x in raw]
        gross=sum(wi*x[1][0] for wi,x in zip(w,rows));daily=[]
        for k in range(v19.v15.v13.H+1):
            dd=rows[0][1][3][k][0];dr=sum(wi*x[1][3][k][1] for wi,x in zip(w,rows));daily.append([dd,dr])
        e={'signal_date':d,'entry_date':rows[0][1][1],'exit_date':rows[0][1][2],'tickers':picks,'weights':w,'scores':[x[3] for x in rows],'score_median':med,'score_margins':[x[4] for x in rows],'gross_return':gross,'daily':daily,'regime':b['regime'],'breadth20':b['breadth20'],'year':b['year']}
        e['exposure']=v19.exposure(e);e['vol_ratio']=v19.vol_ratio(e);out.append(e)
    return out,invalid

EV,INVALID=build();complete=(not INVALID and len(EV)==len(v19.v15.base))

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
    return {'baskets':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,'compounded_return':product(nets),'max_drawdown':mdd,'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,'mean_net_return':statistics.mean(nets) if nets else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None,'max_single_name_weight':max((max(e['weights']) for e in events),default=None)}

years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in v19.v15.v13.PERIODS}
combined={str(c):summarize(EV,c) for c in COSTS}
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
c=combined['0.012'];strict=robust and c['compounded_return']>V19_REF['ret'] and c['max_drawdown']>V19_REF['dd'] and c['remove_best_basket_return']>V19_REF['rem'];risk=robust and c['max_drawdown']>=-.22 and c['compounded_return']>=2.20 and c['remove_best_basket_return']>=1.10
status='V25_STRICTLY_DOMINATES_V19' if strict else ('V25_MATERIAL_RISK_IMPROVEMENT' if risk else 'V25_DOES_NOT_BEAT_V19')
res={'status':status,'method':'single fixed stock-level conviction-risk weighting on frozen V19 schedule: Top3 unchanged; weight_i proportional to max(V6_score_i - cross-sectional median V6 score,1e-6)/vol20_i; V17 exposure and H20 unchanged','complete_common_schedule':complete,'invalid':INVALID,'years':years,'combined':combined,'v19_reference':V19_REF,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Single structural candidate evaluated on exposed 2024-2026 history. All weighting inputs are signal-time-only; no new data.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
