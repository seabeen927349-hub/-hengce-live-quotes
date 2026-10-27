#!/usr/bin/env python3
from __future__ import annotations
import json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v13_weak_regime_profiles as v13

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v14_weak_exposure_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v14_champion_events.jsonl'
EXPOSURES=(0.0,0.25,0.50,0.75,1.0)
COSTS=(.008,.012,.016)
V6_REF={'combined_return_012':2.502731886924238,'combined_maxdd_012':-0.40608721504832834}

cache=v13.make_cache(v13.V6)
base=[]
for y,(s,e) in v13.PERIODS.items():
    ev,_=v13.simulate(cache,s,e)
    for x in ev:
        x=dict(x);x['year']=y
        base.append(x)
base.sort(key=lambda x:x['signal_date'])

def product(xs):
    n=1.0
    for x in xs:n*=1+x
    return n-1

def summarize(events,cost,weak_exposure):
    nets=[];nav=1.;peak=1.;mdd=0.;scaled=[]
    for e in events:
        exp=1.0 if e['regime']=='STRONG' else weak_exposure
        net=exp*(e['gross_return']-cost)
        nets.append(net)
        base_nav=nav
        for j,(d,r) in enumerate(e['daily']):
            temp=base_nav*(1+exp*r-(exp*cost if j==len(e['daily'])-1 else 0))
            peak=max(peak,temp);mdd=min(mdd,temp/peak-1)
        nav=base_nav*(1+net)
        z=dict(e);z['exposure']=exp;z['scaled_net_return']=net;scaled.append(z)
    bi=max(range(len(nets)),key=lambda k:nets[k]) if nets else None
    return {
      'baskets':len(nets),'active_baskets':sum((1.0 if e['regime']=='STRONG' else weak_exposure)>0 for e in events),
      'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,
      'compounded_return':product(nets),'max_drawdown':mdd,
      'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,
      'mean_net_return':statistics.mean(nets) if nets else None,
      'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None,
      'scaled_events':scaled
    }

results=[]
for exp in EXPOSURES:
    yrs={}
    for y in v13.PERIODS:
        yy=[e for e in base if e['year']==y]
        yrs[y]={}
        for c in COSTS:
            m=summarize(yy,c,exp);m.pop('scaled_events',None);yrs[y][str(c)]=m
    combined={}
    for c in COSTS:
        m=summarize(base,c,exp);m.pop('scaled_events',None);combined[str(c)]=m
    m12=[yrs[y]['0.012'] for y in v13.PERIODS];m16=[yrs[y]['0.016'] for y in v13.PERIODS]
    worst=min(x['compounded_return'] for x in m12);worst16=min(x['compounded_return'] for x in m16)
    minrem=min(x['remove_best_basket_return'] for x in m12);worstdd=min(x['max_drawdown'] for x in m12);avgwin=statistics.mean(x['win_rate'] for x in m12)
    robust=worst>0 and worst16>0 and minrem>0
    calmar_like=combined['0.012']['compounded_return']/abs(combined['0.012']['max_drawdown']) if combined['0.012']['max_drawdown']<0 else 999
    obj=1.6*worst+.35*combined['0.012']['compounded_return']+.8*minrem+.35*avgwin+1.8*worstdd+1.6*combined['0.012']['max_drawdown']+.10*calmar_like
    results.append({'weak_exposure':exp,'years':yrs,'combined':combined,'robust':robust,'worst_year_return_012':worst,'worst_year_return_016':worst16,'min_remove_best_012':minrem,'worst_year_maxdd_012':worstdd,'calmar_like':calmar_like,'objective':obj})

rob=[r for r in results if r['robust']];pool=rob or results
pool.sort(key=lambda r:(r['objective'],r['calmar_like'],r['combined']['0.012']['compounded_return']),reverse=True)
champ=pool[0]
cm=summarize(base,.012,champ['weak_exposure'])
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in cm['scaled_events']:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
cr=champ['combined']['0.012']['compounded_return'];cd=champ['combined']['0.012']['max_drawdown']
strict=champ['robust'] and cr>V6_REF['combined_return_012'] and cd>V6_REF['combined_maxdd_012']
risk=champ['robust'] and cd>=-.32 and cr>=2.0
status='V14_STRICTLY_DOMINATES_V6' if strict else ('V14_MATERIAL_RISK_IMPROVEMENT' if risk else 'V14_DOES_NOT_BEAT_V6')
res={'status':status,'method':'frozen V6 ranking; strong breadth 100% exposure; finite weak-breadth exposure scaling','weak_exposures':EXPOSURES,'v6_reference':V6_REF,'champion':champ,'all_results':results,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':len(results),'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Exposure levels screened on exposed 2024-2026 history; V6 selection/schedule unchanged. Cash allocation is modeled by linear exposure scaling of basket path and proportional transaction cost.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(res,ensure_ascii=False,indent=2))
