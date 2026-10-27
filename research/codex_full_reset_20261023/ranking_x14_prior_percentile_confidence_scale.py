#!/usr/bin/env python3
from __future__ import annotations
import bisect,copy,json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_x12_prior_q25_skip as x12

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_x14_prior_percentile_confidence_scale_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_x14_events.jsonl'
COSTS=(.008,.012,.016)
MIN_PRIOR=x12.MIN_PRIOR
STATE_COST=.012


def prior_percentile(prior,x):
    if len(prior)<MIN_PRIOR:return None
    a=sorted(prior)
    lo=bisect.bisect_left(a,x);hi=bisect.bisect_right(a,x)
    return ((lo+hi)/2.0)/len(a)


def build():
    out=[];prior=[];log=[]
    for e0 in sorted(x12.EV,key=lambda e:e['signal_date']):
        e=copy.deepcopy(e0)
        raw=e['x10_confidence_multiplier']
        pct=prior_percentile(prior,raw)
        pre=e['exposure']
        eligible=(e['x12_take_trade'] and pre>1e-12 and pct is not None and pct>0.5 and not e['x11_underwater_gate'])
        uplift=0.0
        if eligible:
            uplift=(pct-0.5)  # 0..0.5, so max exposure multiplier is 1.5x
            e['exposure']=min(1.0,pre*(1.0+uplift))
        e['x14_prior_confidence_percentile']=pct
        e['x14_continuous_uplift']=uplift
        e['x14_pre_scale_exposure']=pre
        e['x14_scale_applied']=eligible
        e['ranking_rule']='X14_EXACT_X12_WITH_PRIOR_EMPIRICAL_CONFIDENCE_PERCENTILE_CONTINUOUS_SCALE_WHEN_NOT_UNDERWATER'
        out.append(e)
        log.append({'signal_date':e['signal_date'],'raw_x10_multiplier':raw,'prior_confidence_percentile':pct,'x12_take_trade':e['x12_take_trade'],'underwater_gate':e['x11_underwater_gate'],'scale_applied':eligible,'continuous_uplift':uplift,'pre_scale_exposure':pre,'final_exposure':e['exposure']})
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

EV,SCALE_LOG=build();complete=(len(EV)==len(x12.EV));years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in x12.x11.x10.v43.v41.v13.PERIODS};combined={str(c):summarize(EV,c) for c in COSTS}
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_active_trade_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
x12ref=x12.combined['0.012'];v43ref=x12.x11.x10.v43.summarize(x12.x11.x10.v43.EV,.012);c=combined['0.012']
dominates_x12=robust and c['compounded_return']>x12ref['compounded_return'] and c['max_drawdown']>=x12ref['max_drawdown'] and c['remove_best_active_trade_return']>x12ref['remove_best_active_trade_return'] and c['win_rate']>=x12ref['win_rate']
dominates_v43=robust and c['compounded_return']>v43ref['compounded_return'] and c['max_drawdown']>=v43ref['max_drawdown'] and c['remove_best_active_trade_return']>v43ref['remove_best_basket_return']
if dominates_x12:status='X14_STRICTLY_DOMINATES_X12'
elif dominates_v43:status='X14_STRICTLY_DOMINATES_V43_BUT_NOT_X12'
else:status='X14_ELIMINATED_NO_STRICT_DOMINANCE'
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'single fixed X14: retain exact X12 trade filter and upstream V43/X11 logic. For active trades only, compute the current X10 confidence multiplier empirical percentile against earlier formal signal multipliers. When at least four prior observations exist, percentile is above 50%, and X11 prior-closed equity is not underwater, smoothly scale X12 exposure by 1+(percentile-0.5), capped at 1.0. Thus uplift ranges continuously from 0 to +50%; otherwise exposure is unchanged. No future outcomes used.','min_prior_multipliers':MIN_PRIOR,'complete_common_schedule':complete,'invalid':[],'robust':robust,'scale_log':SCALE_LOG,'years':years,'combined':combined,'x12_reference':x12ref,'v43_reference':v43ref,'strictly_dominates_x12':dominates_x12,'strictly_dominates_v43':dominates_v43,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'One fixed prior-only continuous exposure hypothesis. Exact X12 stock picks, weights, H20 schedule, Q25 filter, costs and upstream risk controls retained; no parameter grid or future-informed tuning.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
