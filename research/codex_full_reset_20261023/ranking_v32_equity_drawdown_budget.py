#!/usr/bin/env python3
from __future__ import annotations
import json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v30_fragile_strong_risk as v30

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v32_equity_drawdown_budget_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v32_events.jsonl'
COSTS=(.008,.012,.016)
PRIMARY_COST=.012
WEAK_DD_MULT=.50
V19_REF={'ret':2.3394980651997064,'dd':-0.25113023981269567,'rem':1.1916614382781274}
V30_REF={'ret':2.8508800598517157,'dd':-0.25219372871514845,'rem':1.5500728046277374,'max_weight':0.5000000000000001}


def build():
    # Decision state uses only this strategy's own realized history through the previous completed basket.
    # Primary 1.2% cost is part of the predeclared policy; resulting event exposures are then frozen for all stress costs.
    nav=1.0;peak=1.0;out=[]
    for e0 in sorted(v30.EV,key=lambda e:e['signal_date']):
        e=dict(e0)
        in_dd=nav < peak-1e-12
        mult=WEAK_DD_MULT if (e['regime']=='WEAK' and in_dd) else 1.0
        e['pre_signal_policy_nav']=nav;e['pre_signal_policy_peak']=peak;e['pre_signal_policy_drawdown']=nav/peak-1 if peak>0 else 0.0
        e['equity_dd_multiplier']=mult;e['base_exposure']=e['exposure'];e['exposure']=e['base_exposure']*mult
        b=nav
        for j,(d,r) in enumerate(e['daily']):
            temp=b*(1+e['exposure']*r-(e['exposure']*PRIMARY_COST if j==len(e['daily'])-1 else 0))
            peak=max(peak,temp)
        nav=b*(1+e['exposure']*(e['gross_return']-PRIMARY_COST))
        out.append(e)
    return out


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
    return {'baskets':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,'compounded_return':product(nets),'max_drawdown':mdd,'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,'mean_net_return':statistics.mean(nets) if nets else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None,'max_single_name_weight':max((max(e['weights']) for e in events),default=None),'mean_exposure':statistics.mean([e['exposure'] for e in events]) if events else None,'scaled_baskets':sum(e['equity_dd_multiplier']<1-1e-12 for e in events)}

EV=build();years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in v30.v19.v15.v13.PERIODS};combined={str(c):summarize(EV,c) for c in COSTS}
robust=all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
c=combined['0.012']
strict_v19=robust and c['compounded_return']>V19_REF['ret'] and c['max_drawdown']>V19_REF['dd'] and c['remove_best_basket_return']>V19_REF['rem'] and c['max_single_name_weight']<=.50+1e-10
strict_v30=robust and c['compounded_return']>=V30_REF['ret'] and c['max_drawdown']>=V30_REF['dd'] and c['remove_best_basket_return']>=V30_REF['rem']
status='V32_DOMINATES_V30' if strict_v30 else ('V32_STRICTLY_DOMINATES_V19' if strict_v19 else 'V32_DOES_NOT_BEAT_V19')
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'single fixed prior-only strategy-equity risk budget on frozen V30: before each completed non-overlap basket, if regime is WEAK and primary-cost strategy NAV is below its previously realized peak, multiply that basket exposure by 0.50; otherwise unchanged. Decision state uses only prior realized path.','primary_policy_cost':PRIMARY_COST,'weak_in_drawdown_multiplier':WEAK_DD_MULT,'robust':robust,'years':years,'combined':combined,'v19_reference':V19_REF,'v30_reference':V30_REF,'scaled_events':[{'signal_date':e['signal_date'],'pre_signal_policy_drawdown':e['pre_signal_policy_drawdown'],'base_exposure':e['base_exposure'],'exposure':e['exposure']} for e in EV if e['equity_dd_multiplier']<1-1e-12],'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'One structural prior-only equity-state overlay on exposed 2024-2026 history; no parameter grid, new data, ranking, weight, horizon or market-state threshold changes.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
