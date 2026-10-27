#!/usr/bin/env python3
from __future__ import annotations
import json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v30_fragile_strong_risk as v30

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v31_weak_stagger_entry_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v31_events.jsonl'
COSTS=(.008,.012,.016)
DELAY=5
FIRST_SHARE=.50
V19_REF={'ret':2.3394980651997064,'dd':-0.25113023981269567,'rem':1.1916614382781274}
V30_REF={'ret':2.8508800598517157,'dd':-0.25219372871514845,'rem':1.5500728046277374,'max_weight':0.5000000000000001}
DATES=v30.v19.v15.v13.dates;BY=v30.v19.v15.v13.by;DI={d:i for i,d in enumerate(DATES)}


def delayed_leg(t,signal_i,exit_i):
    entry_i=signal_i+1+DELAY
    if entry_i>=exit_i:return None
    ed=DATES[entry_i];xd=DATES[exit_i]
    e=BY[ed].get(t);x=BY[xd].get(t)
    if e is None or x is None or e.o is None or x.c is None or e.o<=0 or x.c<=0:return None
    path={}
    for j in range(entry_i,exit_i+1):
        z=BY[DATES[j]].get(t)
        if z is None or z.c is None or z.c<=0 or z.bad:return None
        path[DATES[j]]=z.c/e.o-1
    return x.c/e.o-1,path,ed,xd


def build():
    out=[];invalid=[]
    for e0 in sorted(v30.EV,key=lambda e:e['signal_date']):
        e=dict(e0)
        if e['regime']!='WEAK':
            e['entry_style']='BASE';e['stagger_delay_sessions']=0;out.append(e);continue
        si=DI[e['signal_date']];exit_i=si+1+v30.v19.v15.v13.H
        legs=[];ok=True
        for t in e['tickers']:
            q=delayed_leg(t,si,exit_i)
            if q is None:ok=False;break
            legs.append(q)
        if not ok:
            invalid.append([e['signal_date'],'DELAYED_LEG_INVALID']);continue
        delayed_gross=sum(w*q[0] for w,q in zip(e['weights'],legs))
        full_daily={d:r for d,r in e['daily']};daily=[]
        for j in range(si+1,exit_i+1):
            d=DATES[j];r1=full_daily[d]
            if j<si+1+DELAY:r=FIRST_SHARE*r1
            else:
                r2=sum(w*q[1][d] for w,q in zip(e['weights'],legs))
                r=FIRST_SHARE*r1+(1-FIRST_SHARE)*r2
            daily.append([d,r])
        e['original_gross_return']=e['gross_return'];e['delayed_leg_gross_return']=delayed_gross
        e['gross_return']=FIRST_SHARE*e['original_gross_return']+(1-FIRST_SHARE)*delayed_gross
        e['daily']=daily;e['entry_style']='WEAK_STAGGER_50_50';e['stagger_delay_sessions']=DELAY;e['delayed_entry_date']=legs[0][2]
        out.append(e)
    return out,invalid


def product(xs):
    n=1.0
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
    return {'baskets':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,'compounded_return':product(nets),'max_drawdown':mdd,'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,'mean_net_return':statistics.mean(nets) if nets else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None,'max_single_name_weight':max((max(e['weights']) for e in events),default=None),'staggered_baskets':sum(e.get('entry_style')=='WEAK_STAGGER_50_50' for e in events)}

EV,INVALID=build();complete=(not INVALID and len(EV)==len(v30.EV))
years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in v30.v19.v15.v13.PERIODS}
combined={str(c):summarize(EV,c) for c in COSTS}
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
c=combined['0.012']
strict_v19=robust and c['compounded_return']>V19_REF['ret'] and c['max_drawdown']>V19_REF['dd'] and c['remove_best_basket_return']>V19_REF['rem'] and c['max_single_name_weight']<=.50+1e-10
strict_v30=robust and c['compounded_return']>=V30_REF['ret'] and c['max_drawdown']>=V30_REF['dd'] and c['remove_best_basket_return']>=V30_REF['rem']
status='V31_DOMINATES_V30' if strict_v30 else ('V31_STRICTLY_DOMINATES_V19' if strict_v19 else 'V31_DOES_NOT_BEAT_V19')
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'single fixed timing-risk overlay on frozen V30: STRONG unchanged; every WEAK basket deploys 50% at original next-open and 50% five sessions later at open, both sleeves exit at original H20 exit close; same Top3, cap50 weights and V30/V17 exposure','delay_sessions':DELAY,'first_share':FIRST_SHARE,'complete_common_schedule':complete,'invalid':INVALID,'robust':robust,'years':years,'combined':combined,'v19_reference':V19_REF,'v30_reference':V30_REF,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'One structural weak-regime stagger hypothesis evaluated on exposed 2024-2026 history. No parameter grid, new data, ranking, weight, schedule or original exit-date changes.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
