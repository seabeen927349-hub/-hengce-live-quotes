#!/usr/bin/env python3
from __future__ import annotations
import json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v13_weak_regime_profiles as v13

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v15_state_exposure_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v15_champion_events.jsonl'
COSTS=(.008,.012,.016)
V6_REF={'combined_return_012':2.502731886924238,'combined_maxdd_012':-0.40608721504832834}
V14_REF={'combined_return_012':2.0942494161154364,'combined_maxdd_012':-0.29390473237009496}

# Frozen V6 ranking/schedule. Only exposure changes.
cache=v13.make_cache(v13.V6)
base=[]
for y,(s,e) in v13.PERIODS.items():
    ev,_=v13.simulate(cache,s,e)
    for x in ev:
        x=dict(x);x['year']=y
        base.append(x)
base.sort(key=lambda x:x['signal_date'])

# Signal-time market state; no future outcome fields.
dates=v13.dates
idx={d:i for i,d in enumerate(dates)}
market_vol={}
for d in dates:
    vals=[r.vol20 for r in v13.by[d].values() if r.vol20 is not None]
    if vals: market_vol[d]=statistics.median(vals)
vol_hist={}
for i,d in enumerate(dates):
    prior=[market_vol[dates[j]] for j in range(max(0,i-60),i) if dates[j] in market_vol]
    vol_hist[d]=statistics.median(prior) if len(prior)>=20 else None

def state(e):
    d=e['signal_date'];i=idx[d]
    prev_b=None
    for j in range(i-20,max(-1,i-61),-1):
        if j>=0 and dates[j] in v13.breadth:
            prev_b=v13.breadth[dates[j]];break
    b=v13.breadth.get(d,e['breadth20'])
    slope=(b-prev_b) if prev_b is not None else 0.0
    m5=v13.mkt[d].get('r5')
    mv=market_vol.get(d);vh=vol_hist.get(d)
    lowvol=(mv is not None and vh is not None and mv<=vh)
    return {'breadth20':b,'breadth_slope20':slope,'mkt5':m5,'lowvol':lowvol,'median_vol20':mv,'prior60_median_vol20':vh}

POLICIES={
 'FIXED50':'weak=0.50',
 'MKT5_RECOVERY':'weak=0.75 if market median 5d return >0 else 0.25',
 'BREADTH_RECOVERY':'weak=0.75 if breadth improved vs prior ~20-session observation else 0.25',
 'RECOVERY_OR':'weak=0.75 if mkt5>0 OR breadth_slope>0 else 0.25',
 'DUAL_RECOVERY':'weak=1.00 if mkt5>0 AND breadth_slope>0; 0.50 if one; 0.25 if neither',
 'LOWVOL_WEAK':'weak=0.75 if current median vol20 <= prior60 median else 0.25',
 'TRIPLE_STATE':'weak=1.00 if all(mkt5>0,breadth_slope>0,lowvol); 0.75 if 2; 0.50 if 1; 0.25 if 0',
}

def exposure(policy,e):
    if e['regime']=='STRONG':return 1.0
    s=state(e);a=bool(s['mkt5'] is not None and s['mkt5']>0);b=s['breadth_slope20']>0;c=s['lowvol']
    if policy=='FIXED50':return .50
    if policy=='MKT5_RECOVERY':return .75 if a else .25
    if policy=='BREADTH_RECOVERY':return .75 if b else .25
    if policy=='RECOVERY_OR':return .75 if (a or b) else .25
    if policy=='DUAL_RECOVERY':return 1.0 if (a and b) else (.50 if (a or b) else .25)
    if policy=='LOWVOL_WEAK':return .75 if c else .25
    if policy=='TRIPLE_STATE':
        n=sum((a,b,c));return (1.0,.75,.50,.25)[3-n]
    raise KeyError(policy)

def product(xs):
    n=1.
    for x in xs:n*=1+x
    return n-1

def summarize(events,cost,policy,with_events=False):
    nets=[];nav=1.;peak=1.;mdd=0.;scaled=[]
    for e in events:
        exp=exposure(policy,e);net=exp*(e['gross_return']-cost);nets.append(net);base_nav=nav
        for j,(d,r) in enumerate(e['daily']):
            temp=base_nav*(1+exp*r-(exp*cost if j==len(e['daily'])-1 else 0));peak=max(peak,temp);mdd=min(mdd,temp/peak-1)
        nav=base_nav*(1+net)
        if with_events:
            z=dict(e);z['exposure']=exp;z['state']=state(e);z['scaled_net_return']=net;scaled.append(z)
    bi=max(range(len(nets)),key=lambda k:nets[k]) if nets else None
    m={'baskets':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,'compounded_return':product(nets),'max_drawdown':mdd,'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,'mean_net_return':statistics.mean(nets) if nets else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None}
    if with_events:m['scaled_events']=scaled
    return m

results=[]
for p in POLICIES:
    yrs={y:{str(c):summarize([e for e in base if e['year']==y],c,p) for c in COSTS} for y in v13.PERIODS}
    combined={str(c):summarize(base,c,p) for c in COSTS}
    m12=[yrs[y]['0.012'] for y in v13.PERIODS];m16=[yrs[y]['0.016'] for y in v13.PERIODS]
    worst=min(x['compounded_return'] for x in m12);worst16=min(x['compounded_return'] for x in m16);minrem=min(x['remove_best_basket_return'] for x in m12);worstdd=min(x['max_drawdown'] for x in m12);avgwin=statistics.mean(x['win_rate'] for x in m12)
    robust=worst>0 and worst16>0 and minrem>0
    calmar=combined['0.012']['compounded_return']/abs(combined['0.012']['max_drawdown']) if combined['0.012']['max_drawdown']<0 else 999
    obj=1.8*worst+.45*combined['0.012']['compounded_return']+.8*minrem+.35*avgwin+1.8*worstdd+1.6*combined['0.012']['max_drawdown']+.12*calmar+.15*worst16
    results.append({'policy':p,'definition':POLICIES[p],'years':yrs,'combined':combined,'robust':robust,'worst_year_return_012':worst,'worst_year_return_016':worst16,'min_remove_best_012':minrem,'worst_year_maxdd_012':worstdd,'calmar_like':calmar,'objective':obj})
rob=[r for r in results if r['robust']];pool=rob or results;pool.sort(key=lambda r:(r['objective'],r['calmar_like'],r['combined']['0.012']['compounded_return']),reverse=True);champ=pool[0]
cm=summarize(base,.012,champ['policy'],True)
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in cm['scaled_events']:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
cr=champ['combined']['0.012']['compounded_return'];cd=champ['combined']['0.012']['max_drawdown']
strict_v6=champ['robust'] and cr>V6_REF['combined_return_012'] and cd>V6_REF['combined_maxdd_012']
strict_v14=champ['robust'] and cr>=V14_REF['combined_return_012'] and cd>=V14_REF['combined_maxdd_012'] and (cr>V14_REF['combined_return_012'] or cd>V14_REF['combined_maxdd_012'])
status='V15_STRICTLY_DOMINATES_V6' if strict_v6 else ('V15_DOMINATES_V14' if strict_v14 else 'V15_DOES_NOT_BEAT_V14')
res={'status':status,'method':'frozen V6 ranking and schedule; finite signal-time weak-regime exposure policies','policies':POLICIES,'v6_reference':V6_REF,'v14_reference':V14_REF,'champion':champ,'all_results':results,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':len(results),'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Policies are screened on exposed 2024-2026 history. All state variables are signal-time-only; no new data and no selection-formula changes.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(res,ensure_ascii=False,indent=2))
