#!/usr/bin/env python3
from __future__ import annotations
import json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v15_state_exposure as v15

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v16_vol_target_exposure_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v16_champion_events.jsonl'
COSTS=(.008,.012,.016)
V14_REF={'combined_return_012':2.0942494161154364,'combined_maxdd_012':-0.29390473237009496,'remove_best_012':0.9769276596728977}
V6_REF={'combined_return_012':2.502731886924238,'combined_maxdd_012':-0.40608721504832834}

# Small, predeclared finite family. V6 selection and schedule are unchanged.
POLICIES={
 'V14_FIXED50':{'kind':'fixed','weak_base':.50},
 'WEAK_VOL050':{'kind':'weak_vol','weak_base':.50},
 'WEAK_VOL060':{'kind':'weak_vol','weak_base':.60},
 'WEAK_VOL075':{'kind':'weak_vol','weak_base':.75},
 'ALL_VOL100':{'kind':'all_vol','strong_base':1.00,'weak_base':.50},
 'ALL_VOL110':{'kind':'all_vol','strong_base':1.10,'weak_base':.55},
 'HIGHVOL_STEP110':{'kind':'step','threshold':1.10},
}

def clip(x,lo,hi):return max(lo,min(hi,x))

def vol_ratio(e):
    s=v15.state(e);a=s.get('median_vol20');b=s.get('prior60_median_vol20')
    return a/b if a is not None and b not in (None,0) else 1.0

def exposure(name,e):
    p=POLICIES[name];vr=vol_ratio(e);strong=e['regime']=='STRONG';k=p['kind']
    if k=='fixed':return 1.0 if strong else p['weak_base']
    if k=='weak_vol':return 1.0 if strong else clip(p['weak_base']/vr,.25,1.0)
    if k=='all_vol':return clip((p['strong_base'] if strong else p['weak_base'])/vr,.25,1.0)
    if k=='step':
        if strong:return .75 if vr>p['threshold'] else 1.0
        return .25 if vr>p['threshold'] else .50
    raise KeyError(name)

def product(xs):
    n=1.
    for x in xs:n*=1+x
    return n-1

def summarize(events,cost,name,with_events=False):
    nets=[];nav=1.;peak=1.;mdd=0.;out=[]
    for e in events:
        ex=exposure(name,e);net=ex*(e['gross_return']-cost);nets.append(net);base_nav=nav
        for j,(d,r) in enumerate(e['daily']):
            temp=base_nav*(1+ex*r-(ex*cost if j==len(e['daily'])-1 else 0));peak=max(peak,temp);mdd=min(mdd,temp/peak-1)
        nav=base_nav*(1+net)
        if with_events:
            z=dict(e);z['exposure']=ex;z['vol_ratio']=vol_ratio(e);z['scaled_net_return']=net;out.append(z)
    bi=max(range(len(nets)),key=lambda k:nets[k]) if nets else None
    m={'baskets':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,'compounded_return':product(nets),'max_drawdown':mdd,'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,'mean_net_return':statistics.mean(nets) if nets else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None}
    if with_events:m['events']=out
    return m

results=[]
for name in POLICIES:
    yrs={y:{str(c):summarize([e for e in v15.base if e['year']==y],c,name) for c in COSTS} for y in v15.v13.PERIODS}
    combined={str(c):summarize(v15.base,c,name) for c in COSTS}
    m12=[yrs[y]['0.012'] for y in v15.v13.PERIODS];m16=[yrs[y]['0.016'] for y in v15.v13.PERIODS]
    worst=min(x['compounded_return'] for x in m12);worst16=min(x['compounded_return'] for x in m16);minrem=min(x['remove_best_basket_return'] for x in m12);worstdd=min(x['max_drawdown'] for x in m12);avgwin=statistics.mean(x['win_rate'] for x in m12)
    robust=worst>0 and worst16>0 and minrem>0
    calmar=combined['0.012']['compounded_return']/abs(combined['0.012']['max_drawdown']) if combined['0.012']['max_drawdown']<0 else 999
    obj=1.8*worst+.45*combined['0.012']['compounded_return']+.8*minrem+.35*avgwin+1.8*worstdd+1.6*combined['0.012']['max_drawdown']+.12*calmar+.15*worst16
    results.append({'policy':name,'definition':POLICIES[name],'years':yrs,'combined':combined,'robust':robust,'worst_year_return_012':worst,'worst_year_return_016':worst16,'min_remove_best_012':minrem,'worst_year_maxdd_012':worstdd,'calmar_like':calmar,'objective':obj})
rob=[r for r in results if r['robust']];pool=rob or results;pool.sort(key=lambda r:(r['objective'],r['calmar_like'],r['combined']['0.012']['compounded_return']),reverse=True);champ=pool[0]
cm=summarize(v15.base,.012,champ['policy'],True)
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in cm['events']:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
cr=champ['combined']['0.012']['compounded_return'];cd=champ['combined']['0.012']['max_drawdown'];rem=champ['combined']['0.012']['remove_best_basket_return']
strict_v6=champ['robust'] and cr>V6_REF['combined_return_012'] and cd>V6_REF['combined_maxdd_012']
strict_v14=champ['robust'] and cr>=V14_REF['combined_return_012'] and cd>=V14_REF['combined_maxdd_012'] and rem>=V14_REF['remove_best_012'] and (cr>V14_REF['combined_return_012'] or cd>V14_REF['combined_maxdd_012'] or rem>V14_REF['remove_best_012'])
status='V16_STRICTLY_DOMINATES_V6' if strict_v6 else ('V16_DOMINATES_V14' if strict_v14 else 'V16_DOES_NOT_BEAT_V14')
res={'status':status,'method':'frozen V6 ranking/schedule with finite signal-time volatility-targeted exposure policies','policies':POLICIES,'v6_reference':V6_REF,'v14_reference':V14_REF,'champion':champ,'all_results':results,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':len(results),'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Policies screened on exposed 2024-2026 history. Volatility ratio uses signal-time median stock vol20 divided by its prior-60-session median only.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(res,ensure_ascii=False,indent=2))
