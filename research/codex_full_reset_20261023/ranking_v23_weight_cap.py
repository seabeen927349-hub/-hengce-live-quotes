#!/usr/bin/env python3
from __future__ import annotations
import json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v19_diversification as v19

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v23_weight_cap_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v23_events.jsonl'
COSTS=(.008,.012,.016)
CAP=.50
V19_REF={'ret':2.3394980651997064,'dd':-0.25113023981269567,'rem':1.1916614382781274}
DATES=v19.v15.v13.dates;DI={d:i for i,d in enumerate(DATES)}


def cap_weights(w,cap=CAP):
    w=list(w)
    for _ in range(5):
        over=[i for i,x in enumerate(w) if x>cap+1e-15]
        if not over:break
        excess=sum(w[i]-cap for i in over)
        for i in over:w[i]=cap
        free=[i for i,x in enumerate(w) if i not in over and x<cap-1e-15]
        if not free:break
        base=sum(w[i] for i in free)
        if base<=0:
            add=excess/len(free)
            for i in free:w[i]+=add
        else:
            for i in free:w[i]+=excess*w[i]/base
    s=sum(w);return [x/s for x in w]


def build():
    base,invalid=v19.build_variant(3,'INV_VOL');out=[]
    for e in base:
        d=e['signal_date'];si=DI[d];picks=e['tickers'];w=cap_weights(e['weights'])
        outs=[];ok=True
        for t in picks:
            o=v19.v15.v13.outcome(t,si)
            if o is None:ok=False;break
            outs.append(o)
        if not ok:
            invalid.append([d,'INVALID_OUTCOME']);continue
        gross=sum(wi*o[0] for wi,o in zip(w,outs));daily=[]
        for k in range(v19.v15.v13.H+1):
            dd=outs[0][3][k][0];dr=sum(wi*o[3][k][1] for wi,o in zip(w,outs));daily.append([dd,dr])
        z=dict(e);z['uncapped_weights']=e['weights'];z['weights']=w;z['gross_return']=gross;z['daily']=daily;z['weight_cap']=CAP
        out.append(z)
    return out,invalid

EV,INVALID=build();complete=(not INVALID and len(EV)==len(v19.v15.base))

def summarize(events,cost):
    nets=[];nav=1.;peak=1.;mdd=0.
    for e in events:
        ex=e['exposure'];net=ex*(e['gross_return']-cost);nets.append(net);b=nav
        for j,(d,r) in enumerate(e['daily']):
            temp=b*(1+ex*r-(ex*cost if j==len(e['daily'])-1 else 0));peak=max(peak,temp);mdd=min(mdd,temp/peak-1)
        nav=b*(1+net)
    bi=max(range(len(nets)),key=lambda k:nets[k]) if nets else None
    prod=lambda xs:statistics.fmean([0]) if False else __import__('functools').reduce(lambda a,x:a*(1+x),xs,1.0)-1
    return {'baskets':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,'compounded_return':prod(nets),'max_drawdown':mdd,'remove_best_basket_return':prod([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,'mean_net_return':statistics.mean(nets) if nets else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None}

years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in v19.v15.v13.PERIODS}
combined={str(c):summarize(EV,c) for c in COSTS}
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
c=combined['0.012'];strict=robust and c['compounded_return']>V19_REF['ret'] and c['max_drawdown']>V19_REF['dd'] and c['remove_best_basket_return']>V19_REF['rem'];risk=robust and c['max_drawdown']>=-.22 and c['compounded_return']>=2.20 and c['remove_best_basket_return']>=1.10
status='V23_STRICTLY_DOMINATES_V19' if strict else ('V23_MATERIAL_RISK_IMPROVEMENT' if risk else 'V23_DOES_NOT_BEAT_V19')
res={'status':status,'method':'single fixed V19 Top3 inverse-vol portfolio with 50% maximum single-name basket weight; excess redistributed proportionally across uncapped names; V17 exposure, H20, schedule and selection unchanged','weight_cap':CAP,'complete_common_schedule':complete,'invalid':INVALID,'years':years,'combined':combined,'v19_reference':V19_REF,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Single fixed risk-control candidate evaluated on exposed 2024-2026 history; 50% cap chosen before this run, not optimized.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
