#!/usr/bin/env python3
from __future__ import annotations
import json,statistics,math
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v19_diversification as v19

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v26_covariance_weight_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v26_events.jsonl'
COSTS=(.008,.012,.016)
V19_REF={'ret':2.3394980651997064,'dd':-0.25113023981269567,'rem':1.1916614382781274}
DATES=v19.v15.v13.dates;DI={d:i for i,d in enumerate(DATES)};BY=v19.v15.v13.by
SHRINK=.50


def invert3(a):
    m=[list(map(float,row))+[1.0 if i==j else 0.0 for j in range(3)] for i,row in enumerate(a)]
    for c in range(3):
        piv=max(range(c,3),key=lambda r:abs(m[r][c]))
        if abs(m[piv][c])<1e-14:return None
        m[c],m[piv]=m[piv],m[c]
        q=m[c][c];m[c]=[x/q for x in m[c]]
        for r in range(3):
            if r==c:continue
            f=m[r][c];m[r]=[x-f*y for x,y in zip(m[r],m[c])]
    return [row[3:] for row in m]


def cov_weights(d,picks):
    i=DI[d]; series=[]
    for t in picks:
        vals=[]
        for j in range(i-19,i+1):
            if j<0:return None
            r=BY[DATES[j]].get(t)
            if r is None or r.r1 is None:return None
            vals.append(r.r1)
        series.append(vals)
    means=[statistics.mean(x) for x in series]
    cov=[[sum((series[a][k]-means[a])*(series[b][k]-means[b]) for k in range(20))/19 for b in range(3)] for a in range(3)]
    shr=[[cov[a][b]*((1-SHRINK) if a!=b else 1.0) for b in range(3)] for a in range(3)]
    # Equivalent to 50% sample covariance + 50% diagonal covariance.
    inv=invert3(shr)
    if inv is None:return None
    raw=[sum(inv[i][j] for j in range(3)) for i in range(3)]
    raw=[max(0.0,x) for x in raw]
    if sum(raw)<=1e-14:return None
    s=sum(raw);return [x/s for x in raw],cov,shr


def build():
    out=[];invalid=[]
    for b in sorted(v19.v15.base,key=lambda e:e['signal_date']):
        d=b['signal_date'];si=DI[d];picks=v19.cache.get(d,[])[:3]
        if len(picks)<3:
            invalid.append([d,'NOT_ENOUGH_PICKS']);continue
        cw=cov_weights(d,picks)
        if cw is None:
            invalid.append([d,'COVARIANCE_UNAVAILABLE']);continue
        w,cov,shr=cw;outs=[];ok=True
        for t in picks:
            o=v19.v15.v13.outcome(t,si)
            if o is None:ok=False;break
            outs.append(o)
        if not ok:
            invalid.append([d,'INVALID_OUTCOME']);continue
        gross=sum(wi*o[0] for wi,o in zip(w,outs));daily=[]
        for k in range(v19.v15.v13.H+1):
            dd=outs[0][3][k][0];dr=sum(wi*o[3][k][1] for wi,o in zip(w,outs));daily.append([dd,dr])
        e={'signal_date':d,'entry_date':outs[0][1],'exit_date':outs[0][2],'tickers':picks,'weights':w,'sample_covariance':cov,'shrunk_covariance':shr,'gross_return':gross,'daily':daily,'regime':b['regime'],'breadth20':b['breadth20'],'year':b['year']}
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
status='V26_STRICTLY_DOMINATES_V19' if strict else ('V26_MATERIAL_RISK_IMPROVEMENT' if risk else 'V26_DOES_NOT_BEAT_V19')
res={'status':status,'method':'single fixed covariance-aware portfolio construction on frozen V19 Top3 schedule: 20 signal-time daily returns, covariance shrunk 50% toward its diagonal, unconstrained minimum-variance Sigma^-1*1 weights clipped long-only and renormalized; V17 exposure and H20 unchanged','shrinkage_to_diagonal':SHRINK,'complete_common_schedule':complete,'invalid':INVALID,'years':years,'combined':combined,'v19_reference':V19_REF,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Single structural candidate evaluated on exposed 2024-2026 history. Covariance uses signal-time trailing returns only; no new data.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
