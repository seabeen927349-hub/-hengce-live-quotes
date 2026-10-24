#!/usr/bin/env python3
from __future__ import annotations
import json, statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v19_diversification as v19

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v22_dual_horizon_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v22_events.jsonl'
COSTS=(.008,.012,.016)
V19_REF={'ret':2.3394980651997064,'dd':-0.25113023981269567,'rem':1.1916614382781274}
DATES=v19.v15.v13.dates
DI={d:i for i,d in enumerate(DATES)}
BY=v19.v15.v13.by
BASE=sorted(v19.v15.base,key=lambda e:e['signal_date'])
CACHE=v19.cache


def outcome_h(t,si,h):
    ei=si+1; xi=ei+h
    if xi>=len(DATES): return None
    ed,xd=DATES[ei],DATES[xi]
    e=BY[ed].get(t); x=BY[xd].get(t)
    if e is None or x is None or e.o is None or x.c is None or e.o<=0 or x.c<=0:return None
    path=[]
    for j in range(ei,xi+1):
        z=BY[DATES[j]].get(t)
        if z is None or z.c is None or z.c<=0 or z.bad:return None
        path.append((DATES[j],z.c/e.o-1))
    return x.c/e.o-1,ed,xd,path


def build_events():
    out=[]; invalid=[]
    for b in BASE:
        d=b['signal_date']; si=DI[d]
        picks=CACHE.get(d,[])[:3]
        if len(picks)<3:
            invalid.append([d,'NOT_ENOUGH_PICKS']);continue
        rows=[];ok=True
        for t in picks:
            r=BY[d].get(t)
            o20=outcome_h(t,si,20);o10=outcome_h(t,si,10)
            if r is None or r.vol20 is None or r.vol20<=0 or o20 is None or o10 is None:
                ok=False;break
            rows.append((t,r.vol20,o20,o10))
        if not ok:
            invalid.append([d,'INVALID_OUTCOME_OR_VOL']);continue
        raw=[1/x[1] for x in rows];ss=sum(raw);w=[x/ss for x in raw]
        g20=sum(wi*x[2][0] for wi,x in zip(w,rows));g10=sum(wi*x[3][0] for wi,x in zip(w,rows))
        p20=[];p10=[]
        for k in range(21):
            dd=rows[0][2][3][k][0]
            p20.append([dd,sum(wi*x[2][3][k][1] for wi,x in zip(w,rows))])
        for k in range(11):
            dd=rows[0][3][3][k][0]
            p10.append([dd,sum(wi*x[3][3][k][1] for wi,x in zip(w,rows))])
        e={'signal_date':d,'entry_date':rows[0][2][1],'exit20_date':rows[0][2][2],'exit10_date':rows[0][3][2],
           'tickers':picks,'weights':w,'gross20':g20,'gross10':g10,'path20':p20,'path10':p10,
           'regime':b['regime'],'breadth20':b['breadth20'],'year':b['year']}
        e['exposure']=v19.exposure(e);e['vol_ratio']=v19.vol_ratio(e)
        out.append(e)
    return out,invalid

EVENT_LIST,INVALID=build_events()


def product(xs):
    n=1.
    for x in xs:n*=1+x
    return n-1


def event_path(e,cost):
    ex=e['exposure']; p10={d:r for d,r in e['path10']}; p20=e['path20']; term10=e['gross10']-cost
    rel=[]
    for k,(d,r20) in enumerate(p20):
        if d in p10:
            r10=p10[d]-(cost if d==e['exit10_date'] else 0)
        else:
            r10=term10
        r20n=r20-(cost if d==e['exit20_date'] else 0)
        rel.append([d,ex*(.5*r20n+.5*r10)])
    return rel


def summarize(events,cost,disabled=None,emit=False):
    nets=[];nav=1.;peak=1.;mdd=0.;out=[]
    for e in events:
        key=(e['year'],e['signal_date'])
        if disabled==key:
            net=0.; path=[[d,0.] for d,_ in e['path20']]
        else:
            net=e['exposure']*(.5*(e['gross20']-cost)+.5*(e['gross10']-cost));path=event_path(e,cost)
        nets.append((key,net));b=nav
        for d,r in path:
            temp=b*(1+r);peak=max(peak,temp);mdd=min(mdd,temp/peak-1)
        nav=b*(1+net)
        if emit:
            z=dict(e);z['scaled_net_return']=net;z['disabled_for_remove_best']=(disabled==key);out.append(z)
    best=max(nets,key=lambda x:x[1])[0] if nets else None
    return {'baskets':len(nets),'wins':sum(n>0 for _,n in nets),'win_rate':sum(n>0 for _,n in nets)/len(nets) if nets else None,
            'compounded_return':product([n for _,n in nets]),'max_drawdown':mdd,
            'remove_best_basket_return':product([n for k,n in nets if k!=best]) if len(nets)>1 else None,
            'mean_net_return':statistics.mean(n for _,n in nets) if nets else None,
            'best_basket_net':max((n for _,n in nets),default=None),'worst_basket_net':min((n for _,n in nets),default=None),
            'best_key':best,'events':out if emit else None}

complete=(not INVALID and len(EVENT_LIST)==len(BASE))
years={y:{str(c):summarize([e for e in EVENT_LIST if e['year']==y],c) for c in COSTS} for y in v19.v15.v13.PERIODS}
combined={}
for c in COSTS:
    m=summarize(EVENT_LIST,c);best=m['best_key'];m['remove_best_basket_return']=summarize(EVENT_LIST,c,disabled=best)['compounded_return'];m.pop('events',None);combined[str(c)]=m
for y in years:
    for c in list(years[y]):
        years[y][c].pop('events',None)
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
full=summarize(EVENT_LIST,.012,emit=True)
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in full['events']:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
c=combined['0.012'];strict=robust and c['compounded_return']>V19_REF['ret'] and c['max_drawdown']>V19_REF['dd'] and c['remove_best_basket_return']>V19_REF['rem'];risk=robust and c['max_drawdown']>=-.20 and c['compounded_return']>=2.0 and c['remove_best_basket_return']>=1.0
status='V22_STRICTLY_DOMINATES_V19' if strict else ('V22_MATERIAL_RISK_IMPROVEMENT' if risk else 'V22_DOES_NOT_BEAT_V19')
res={'status':status,'method':'single fixed 50/50 dual-horizon sleeve: V19 Top3 inverse-vol on original signal dates; half capital exits at H10 close and stays cash, half exits at H20 close; V17 exposure unchanged','complete_common_schedule':complete,'invalid':INVALID,'years':years,'combined':combined,'v19_reference':V19_REF,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Single candidate evaluated on exposed 2024-2026 history. No extra signals are created after the H10 sleeve exits.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
