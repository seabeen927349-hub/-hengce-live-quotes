#!/usr/bin/env python3
from __future__ import annotations
import copy,json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_x12_prior_q25_skip as x12

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_x13_median_confidence_full_exposure_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_x13_events.jsonl'
COSTS=(.008,.012,.016)
MIN_PRIOR=x12.MIN_PRIOR


def build():
    out=[];prior=[];log=[]
    for e0 in sorted(x12.EV,key=lambda e:e['signal_date']):
        e=copy.deepcopy(e0)
        raw=e['x10_confidence_multiplier']
        prior_median=statistics.median(prior) if len(prior)>=MIN_PRIOR else None
        eligible=(e['x12_take_trade'] and prior_median is not None and raw>=prior_median and not e['x11_underwater_gate'])
        pre=e['exposure']
        if eligible:
            e['exposure']=1.0
        e['x13_prior_multiplier_median']=prior_median
        e['x13_high_confidence_full_exposure']=eligible
        e['x13_pre_tier_exposure']=pre
        e['ranking_rule']='X13_EXACT_X12_WITH_PRIOR_MEDIAN_HIGH_CONFIDENCE_FULL_EXPOSURE_WHEN_NOT_UNDERWATER'
        out.append(e)
        log.append({'signal_date':e['signal_date'],'raw_x10_multiplier':raw,'prior_multiplier_median':prior_median,'x12_take_trade':e['x12_take_trade'],'underwater_gate':e['x11_underwater_gate'],'tier_applied':eligible,'pre_tier_exposure':pre,'final_exposure':e['exposure']})
        prior.append(raw)
    return out,log


def product(xs):
    z=1.0
    for x in xs:z*=1+x
    return z-1


def summarize(events,cost):
    nets=[];active=[];nav=1.;peak=1.;mdd=0.
    for e in events:
        ex=e['exposure'];net=ex*(e['gross_return']-cost);nets.append(net);b=nav
        if ex>1e-12:active.append(net)
        for j,(d,r) in enumerate(e['daily']):
            temp=b*(1+ex*r-(ex*cost if j==len(e['daily'])-1 else 0));peak=max(peak,temp);mdd=min(mdd,temp/peak-1)
        nav=b*(1+net)
    bi=max(range(len(active)),key=lambda i:active[i]) if active else None
    return {'scheduled_baskets':len(events),'active_trades':len(active),'wins':sum(x>0 for x in active),'win_rate':sum(x>0 for x in active)/len(active) if active else None,'compounded_return':product(nets),'max_drawdown':mdd,'remove_best_active_trade_return':product([x for i,x in enumerate(active) if i!=bi]) if bi is not None and len(active)>1 else None,'mean_active_net_return':statistics.mean(active) if active else None,'best_active_trade_net':max(active) if active else None,'worst_active_trade_net':min(active) if active else None,'max_single_name_weight':max((max(e['weights']) for e in events if e['exposure']>1e-12),default=None),'mean_exposure_all_schedule':statistics.mean([e['exposure'] for e in events]) if events else None}

EV,TIER_LOG=build()
complete=(len(EV)==len(x12.EV))
years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in x12.x11.x10.v43.v41.v13.PERIODS}
combined={str(c):summarize(EV,c) for c in COSTS}
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_active_trade_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
x12ref=x12.combined['0.012'];c=combined['0.012']
dominates=robust and c['compounded_return']>x12ref['compounded_return'] and c['max_drawdown']>=x12ref['max_drawdown'] and c['remove_best_active_trade_return']>x12ref['remove_best_active_trade_return'] and c['win_rate']>=x12ref['win_rate']
status='X13_STRICTLY_DOMINATES_X12' if dominates else 'X13_ELIMINATED_NO_STRICT_DOMINANCE'
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'single fixed X13: keep exact X12 Q25 skip gate and all upstream X11/V43 logic. After four prior multipliers exist, if an active trade has current X10 confidence multiplier at or above the expanding prior-only median and X11 is not underwater, set exposure to 1.0; otherwise leave X12 exposure unchanged. No future outcomes used.','min_prior_multipliers':MIN_PRIOR,'complete_common_schedule':complete,'invalid':[],'robust':robust,'tier_log':TIER_LOG,'years':years,'combined':combined,'x12_reference':x12ref,'strictly_dominates_x12':dominates,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'One fixed prior-only exposure-tier hypothesis. Exact X12 stock picks, weights, schedule, Q25 trade filter, costs and upstream risk controls retained; no grid or parameter scan.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(res,ensure_ascii=False,indent=2))
