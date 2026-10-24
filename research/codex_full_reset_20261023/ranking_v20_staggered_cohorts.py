#!/usr/bin/env python3
from __future__ import annotations
import json,statistics
from collections import defaultdict
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v19_diversification as v19

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v20_staggered_cohorts_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v20_champion_events.jsonl'
COSTS=(.008,.012,.016)
CONFIGS={
 'K1_BASE':(0,),
 'K2_STAGGER':(0,11),
 'K4_STAGGER':(0,5,11,16),
}
V19_REF={'ret':2.3394980651997064,'dd':-0.25113023981269567,'rem':1.1916614382781274}
DATES=v19.v15.v13.dates
DI={d:i for i,d in enumerate(DATES)}
PERIODS=v19.v15.v13.PERIODS
BASE_BY_YEAR={y:[e for e in v19.v15.base if e['year']==y] for y in PERIODS}


def make_event(d,year,cohort):
    i=DI[d]
    ranked=v19.cache.get(d,[]); picks=ranked[:3]
    if len(picks)<3:return None,'NOT_ENOUGH_PICKS'
    outs=[]
    for t in picks:
        o=v19.v15.v13.outcome(t,i); r=v19.v15.v13.by[d].get(t)
        if o is None or r is None or r.vol20 is None or r.vol20<=0:return None,'INVALID_OUTCOME_OR_VOL'
        outs.append((t,o,r.vol20))
    raw=[1/x[2] for x in outs]; s=sum(raw); w=[x/s for x in raw]
    gross=sum(wi*o[1][0] for wi,o in zip(w,outs)); daily=[]
    for k in range(v19.v15.v13.H+1):
        dd=outs[0][1][3][k][0]
        dr=sum(wi*o[1][3][k][1] for wi,o in zip(w,outs))
        daily.append([dd,dr])
    b=v19.v15.v13.breadth.get(d)
    if b is None:return None,'MISSING_BREADTH'
    e={'signal_date':d,'entry_date':outs[0][1][1],'exit_date':outs[0][1][2],'tickers':picks,'weights':w,'gross_return':gross,'daily':daily,'breadth20':b,'regime':'STRONG' if b>=.5 else 'WEAK','year':year,'cohort':cohort}
    e['exposure']=v19.exposure(e); e['vol_ratio']=v19.vol_ratio(e)
    return e,None


def build_config(offsets):
    all_events=[]; invalid=[]
    for y,(start,end) in PERIODS.items():
        seen=set()
        bases=BASE_BY_YEAR[y]
        for base in bases:
            bi=DI[base['signal_date']]
            for cohort,off in enumerate(offsets):
                j=bi+off
                if j>=len(DATES):continue
                d=DATES[j]
                if d<start or d>end:continue
                # Require exit to remain within the same evaluation year.
                if j+1+v19.v15.v13.H>=len(DATES) or DATES[j+1+v19.v15.v13.H]>end:continue
                key=(cohort,d)
                if key in seen:continue
                seen.add(key)
                e,err=make_event(d,y,cohort)
                if e is None:invalid.append({'year':y,'signal_date':d,'cohort':cohort,'reason':err})
                else:all_events.append(e)
    all_events.sort(key=lambda e:(e['year'],e['signal_date'],e['cohort']))
    return all_events,invalid


def run_year(events,year,k,cost,disabled_key=None,emit=False):
    start,end=PERIODS[year]
    yd=[d for d in DATES if start<=d<=end]
    ev=[e for e in events if e['year']==year]
    byc=defaultdict(list)
    for e in ev:byc[e['cohort']].append(e)
    # Each cohort is a fixed capital sleeve. Start equal and keep its own NAV.
    cohort_series=[]; event_nets=[]; emitted=[]
    for c in range(k):
        cev=sorted(byc.get(c,[]),key=lambda e:e['signal_date'])
        nav=1.0/k; series={d:nav for d in yd}; cursor=0
        for e in cev:
            key=(e['year'],e['signal_date'],e['cohort'])
            disabled=(key==disabled_key)
            ex=e['exposure']; base_nav=nav
            if disabled:
                net=0.0
                # Sleeve stays cash for this scheduled holding window.
                for d,_ in e['daily']:
                    if d in series:series[d]=base_nav
            else:
                net=ex*(e['gross_return']-cost)
                for q,(d,r) in enumerate(e['daily']):
                    if d in series:
                        series[d]=base_nav*(1+ex*r-(ex*cost if q==len(e['daily'])-1 else 0))
                nav=base_nav*(1+net)
            event_nets.append((key,net))
            if emit:
                z=dict(e);z['sleeve_start_nav']=base_nav;z['scaled_net_return']=net;z['disabled_for_remove_best']=disabled;emitted.append(z)
            # Carry the new NAV from exit onward until overwritten by a future live path.
            exit_i=yd.index(e['exit_date']) if e['exit_date'] in yd else None
            if exit_i is not None:
                for d2 in yd[exit_i+1:]:
                    if series[d2]==base_nav or series[d2] < 0: series[d2]=nav
        # Robust carry-forward pass: any untouched date after a changed path should hold last observed value.
        last=1.0/k
        live_paths={d for e in cev for d,_ in e['daily'] if d in series}
        for d in yd:
            if d in live_paths:
                last=series[d]
            else:
                series[d]=last
        cohort_series.append(series)
    total=[]
    for d in yd:total.append((d,sum(s[d] for s in cohort_series)))
    peak=total[0][1] if total else 1.;mdd=0.
    for d,n in total:
        peak=max(peak,n);mdd=min(mdd,n/peak-1)
    ret=total[-1][1]-1 if total else None
    wins=sum(n>0 for _,n in event_nets);wr=wins/len(event_nets) if event_nets else None
    out={'baskets':len(event_nets),'wins':wins,'win_rate':wr,'compounded_return':ret,'max_drawdown':mdd,'mean_basket_net':statistics.mean(n for _,n in event_nets) if event_nets else None,'worst_basket_net':min((n for _,n in event_nets),default=None),'best_basket_net':max((n for _,n in event_nets),default=None)}
    if emit:out['events']=emitted;out['nav_path']=total
    return out,event_nets


def evaluate(name,offsets,cost):
    events,invalid=build_config(offsets);k=len(offsets)
    years={};all_nets=[]
    for y in PERIODS:
        m,nets=run_year(events,y,k,cost);years[y]=m;all_nets+=nets
    # Chain yearly NAVs exactly as the evaluation resets positions at year boundaries.
    combined_ret=1.0
    for y in PERIODS:combined_ret*=1+years[y]['compounded_return']
    combined_ret-=1
    # Continuous chained max drawdown.
    scale=1.;peak=1.;mdd=0.;full=[]
    for y in PERIODS:
        m,_=run_year(events,y,k,cost,emit=True)
        for d,n in m['nav_path']:
            x=scale*n;peak=max(peak,x);mdd=min(mdd,x/peak-1);full.append((d,x))
        scale*=1+m['compounded_return']
    best_key=max(all_nets,key=lambda x:x[1])[0] if all_nets else None
    rem_scale=1.
    for y in PERIODS:
        m,_=run_year(events,y,k,cost,disabled_key=best_key);rem_scale*=1+m['compounded_return']
    rem=rem_scale-1
    return {'name':name,'offsets':list(offsets),'cohorts':k,'invalid':invalid,'complete':not invalid,'years':years,'combined':{'compounded_return':combined_ret,'max_drawdown':mdd,'remove_best_basket_return':rem,'baskets':sum(years[y]['baskets'] for y in PERIODS),'wins':sum(years[y]['wins'] for y in PERIODS),'win_rate':sum(years[y]['wins'] for y in PERIODS)/sum(years[y]['baskets'] for y in PERIODS) if sum(years[y]['baskets'] for y in PERIODS) else None},'events':events,'best_key':best_key}

results=[]
for name,offs in CONFIGS.items():
    per={}
    for c in COSTS:
        x=evaluate(name,offs,c);per[str(c)]={'years':x['years'],'combined':x['combined'],'invalid':x['invalid'],'complete':x['complete']}
    m12=per['0.012'];m16=per['0.016']
    robust=m12['complete'] and m16['complete'] and all(m12['years'][y]['compounded_return']>0 for y in PERIODS) and all(m16['years'][y]['compounded_return']>0 for y in PERIODS)
    # yearly remove-best is intentionally not used because sleeve overlap makes global account remove-best the exact portfolio metric.
    c12=m12['combined'];calmar=c12['compounded_return']/abs(c12['max_drawdown']) if c12['max_drawdown']<0 else 999
    obj=.55*c12['compounded_return']+2.2*c12['max_drawdown']+.9*c12['remove_best_basket_return']+.10*calmar
    results.append({'name':name,'offsets':list(offs),'costs':per,'robust':robust,'calmar_like':calmar,'objective':obj})

pool=[r for r in results if r['robust']] or results
pool.sort(key=lambda r:(r['objective'],r['calmar_like'],r['costs']['0.012']['combined']['compounded_return']),reverse=True);champ=pool[0]
ce=evaluate(champ['name'],tuple(champ['offsets']),.012)
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in ce['events']:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
c=champ['costs']['0.012']['combined'];strict=champ['robust'] and c['compounded_return']>V19_REF['ret'] and c['max_drawdown']>V19_REF['dd'] and c['remove_best_basket_return']>V19_REF['rem'];risk=champ['robust'] and c['max_drawdown']>=-.20 and c['compounded_return']>=2.0
status='V20_STRICTLY_DOMINATES_V19' if strict else ('V20_MATERIAL_RISK_IMPROVEMENT' if risk else 'V20_DOES_NOT_BEAT_V19')
res={'status':status,'method':'frozen V19 Top3 inverse-vol selection + V17 exposure; fixed time-diversification cohorts anchored to original V19 signal schedule','configs':{k:list(v) for k,v in CONFIGS.items()},'v19_reference':V19_REF,'champion':champ,'all_results':results,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':len(CONFIGS),'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'2024-2026 are exposed screening years. K2/K4 add scheduled staggered cohorts without changing factor formula, ranking, holding horizon, or exposure rule. Any invalid planned cohort event rejects completeness for that config.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
