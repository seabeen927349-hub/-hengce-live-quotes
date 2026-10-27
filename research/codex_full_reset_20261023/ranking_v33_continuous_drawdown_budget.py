#!/usr/bin/env python3
from __future__ import annotations
import json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v30_fragile_strong_risk as v30

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v33_continuous_drawdown_budget_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v33_events.jsonl'
COSTS=(.008,.012,.016)
PRIMARY_COST=.012
WEAK_BASE_MULT=.50
V19_REF={'ret':2.3394980651997064,'dd':-0.25113023981269567,'rem':1.1916614382781274}
V32_REF={'ret':2.513405145180079,'dd':-0.17014957723452873,'rem':1.326595160875482,'max_weight':0.5000000000000001}


def build():
    # Single structural rule, no new market threshold:
    # - begin from frozen V30 exposure;
    # - use only realized policy NAV through the prior completed basket;
    # - if underwater, multiply risk-off states by recovery ratio NAV/peak;
    # - WEAK retains V32's fixed 0.50 risk budget, then receives the continuous ratio;
    # - V30 fragile-strong + tail-vol states receive only the continuous ratio;
    # - all other states are unchanged.
    nav=1.0;peak=1.0;out=[]
    for e0 in sorted(v30.EV,key=lambda e:e['signal_date']):
        e=dict(e0)
        recovery=(nav/peak) if peak>0 else 1.0
        in_dd=nav < peak-1e-12
        state='NORMAL';mult=1.0
        if in_dd and e['regime']=='WEAK':
            state='WEAK_UNDERWATER';mult=WEAK_BASE_MULT*recovery
        elif in_dd and e.get('fragile_strong') and e.get('tail_vol'):
            state='FRAGILE_TAIL_UNDERWATER';mult=recovery
        e['pre_signal_policy_nav']=nav
        e['pre_signal_policy_peak']=peak
        e['pre_signal_policy_drawdown']=recovery-1.0
        e['recovery_ratio']=recovery
        e['continuous_budget_state']=state
        e['continuous_budget_multiplier']=mult
        e['base_exposure']=e['exposure']
        e['exposure']=e['base_exposure']*mult
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
        'baskets':len(nets),
        'wins':sum(x>0 for x in nets),
        'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,
        'compounded_return':product(nets),
        'max_drawdown':mdd,
        'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,
        'mean_net_return':statistics.mean(nets) if nets else None,
        'best_basket_net':max(nets) if nets else None,
        'worst_basket_net':min(nets) if nets else None,
        'max_single_name_weight':max((max(e['weights']) for e in events),default=None),
        'mean_exposure':statistics.mean([e['exposure'] for e in events]) if events else None,
        'scaled_baskets':sum(e['continuous_budget_multiplier']<1-1e-12 for e in events),
    }

EV=build()
years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in v30.v19.v15.v13.PERIODS}
combined={str(c):summarize(EV,c) for c in COSTS}
robust=all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
c=combined['0.012']
strict_v19=robust and c['compounded_return']>V19_REF['ret'] and c['max_drawdown']>V19_REF['dd'] and c['remove_best_basket_return']>V19_REF['rem'] and c['max_single_name_weight']<=.50+1e-10
pareto_v32=robust and c['max_drawdown']>V32_REF['dd'] and c['compounded_return']>V19_REF['ret'] and c['remove_best_basket_return']>V19_REF['rem']
strict_v32=robust and c['compounded_return']>=V32_REF['ret'] and c['max_drawdown']>=V32_REF['dd'] and c['remove_best_basket_return']>=V32_REF['rem'] and (c['compounded_return']>V32_REF['ret'] or c['max_drawdown']>V32_REF['dd'] or c['remove_best_basket_return']>V32_REF['rem'])
status='V33_STRICTLY_DOMINATES_V32' if strict_v32 else ('V33_NEW_LOWER_DD_FRONTIER' if pareto_v32 else ('V33_STRICTLY_DOMINATES_V19' if strict_v19 else 'V33_DOES_NOT_BEAT_V19'))
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={
    'status':status,
    'method':'single fixed continuous prior-only drawdown budget on frozen V30: when prior completed-basket policy NAV is below realized peak, WEAK exposure = V30 exposure * 0.50 * (NAV/peak); fragile-strong + tail-vol exposure = V30 exposure * (NAV/peak); all other exposures unchanged. No new market threshold.',
    'primary_policy_cost':PRIMARY_COST,
    'weak_base_multiplier':WEAK_BASE_MULT,
    'robust':robust,
    'years':years,
    'combined':combined,
    'v19_reference':V19_REF,
    'v32_reference':V32_REF,
    'scaled_events':[{'signal_date':e['signal_date'],'state':e['continuous_budget_state'],'pre_signal_policy_drawdown':e['pre_signal_policy_drawdown'],'recovery_ratio':e['recovery_ratio'],'base_exposure':e['base_exposure'],'exposure':e['exposure']} for e in EV if e['continuous_budget_multiplier']<1-1e-12],
    'events_file':str(EVENTS.relative_to(ROOT)),
    'new_model_evaluations':1,
    'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
    'caveat':'One structural prior-only risk-budget hypothesis on exposed 2024-2026 history; no grid, no new data, no ranking, stock selection, covariance weighting, horizon or schedule changes.'
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(res,ensure_ascii=False,indent=2))
