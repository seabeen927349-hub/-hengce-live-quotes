#!/usr/bin/env python3
from __future__ import annotations
import json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v36_v9champ_modern_risk as v36

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v37_v36_equity_budget_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v37_events.jsonl'
COSTS=(.008,.012,.016)
PRIMARY_COST=.012
WEAK_DD_MULT=.50
V30_REF={'ret':2.8508800598517157,'dd':-0.25219372871514845,'rem':1.5500728046277374}
V32_REF={'ret':2.513405145180079,'dd':-0.17014957723452873,'rem':1.326595160875482}
V36_REF={'ret':3.1564604706266746,'dd':-0.320100536250974,'rem':1.7524297420116035,'max_weight':0.5000000000000001}


def build():
    # Exact V32 prior-only equity-state policy applied to the frozen V36 event stream.
    # No new parameter: if prior completed-basket policy NAV is below its realized peak
    # and the new basket regime is WEAK, halve V36 exposure; otherwise leave V36 unchanged.
    nav=1.0;peak=1.0;out=[]
    for e0 in sorted(v36.EV,key=lambda e:e['signal_date']):
        e=dict(e0)
        in_dd=nav < peak-1e-12
        mult=WEAK_DD_MULT if (e['regime']=='WEAK' and in_dd) else 1.0
        e['pre_signal_policy_nav']=nav
        e['pre_signal_policy_peak']=peak
        e['pre_signal_policy_drawdown']=nav/peak-1.0 if peak>0 else 0.0
        e['equity_dd_multiplier']=mult
        e['v36_exposure']=e['exposure']
        e['exposure']=e['v36_exposure']*mult
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
    return {
      'baskets':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,
      'compounded_return':product(nets),'max_drawdown':mdd,
      'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,
      'mean_net_return':statistics.mean(nets) if nets else None,
      'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None,
      'max_single_name_weight':max((max(e['weights']) for e in events),default=None),
      'mean_exposure':statistics.mean([e['exposure'] for e in events]) if events else None,
      'equity_scaled_baskets':sum(e['equity_dd_multiplier']<1-1e-12 for e in events),
    }

EV=build()
years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in v36.v13.PERIODS}
combined={str(c):summarize(EV,c) for c in COSTS}
robust=all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
c=combined['0.012']
dom_v30=robust and c['compounded_return']>=V30_REF['ret'] and c['max_drawdown']>=V30_REF['dd'] and c['remove_best_basket_return']>=V30_REF['rem'] and (c['compounded_return']>V30_REF['ret'] or c['max_drawdown']>V30_REF['dd'] or c['remove_best_basket_return']>V30_REF['rem'])
dom_v32=robust and c['compounded_return']>=V32_REF['ret'] and c['max_drawdown']>=V32_REF['dd'] and c['remove_best_basket_return']>=V32_REF['rem'] and (c['compounded_return']>V32_REF['ret'] or c['max_drawdown']>V32_REF['dd'] or c['remove_best_basket_return']>V32_REF['rem'])
new_balance=robust and c['compounded_return']>V30_REF['ret'] and c['max_drawdown']>-0.25 and c['remove_best_basket_return']>V30_REF['rem']
status='V37_DOMINATES_V30' if dom_v30 else ('V37_DOMINATES_V32' if dom_v32 else ('V37_NEW_BALANCE_FRONTIER' if new_balance else 'V37_DOES_NOT_IMPROVE_FRONTIER'))
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={
 'status':status,
 'method':'single fixed V37: exact V32 prior-only WEAK-underwater 0.50 equity budget applied to frozen V36. V36 ranking, Top3/H20/common schedule, cap50 covariance, V19 exposure and V30 fragile-strong overlay are unchanged.',
 'primary_policy_cost':PRIMARY_COST,'weak_in_drawdown_multiplier':WEAK_DD_MULT,
 'robust':robust,'years':years,'combined':combined,
 'v30_reference':V30_REF,'v32_reference':V32_REF,'v36_reference':V36_REF,
 'scaled_events':[{'signal_date':e['signal_date'],'pre_signal_policy_drawdown':e['pre_signal_policy_drawdown'],'v36_exposure':e['v36_exposure'],'exposure':e['exposure']} for e in EV if e['equity_dd_multiplier']<1-1e-12],
 'events_file':str(EVENTS.relative_to(ROOT)),
 'new_model_evaluations':1,
 'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
 'caveat':'One fixed structural combination of two previously tested exposed-history components. No parameter grid, new data, ranking re-learning, horizon or schedule changes. Historical research only.'
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(res,ensure_ascii=False,indent=2))
