#!/usr/bin/env python3
from __future__ import annotations
import copy,json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_x10_v43_gap_confidence_exposure as x10

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_x11_tail_confidence_drawdown_gate_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_x11_events.jsonl'
COSTS=(.008,.012,.016)
STATE_COST=.012
TAIL_Q=x10.v43.v41.v30.TAIL_Q
MIN_PRIOR=x10.v43.v41.v30.MIN_PRIOR

def build():
    out=[];invalid=[];log=[];prior_mult=[];pending=[];nav=1.0;peak=1.0
    src=sorted(x10.EV,key=lambda e:e['signal_date'])
    for e0 in src:
        d=e0['signal_date']
        still=[]
        for p in pending:
            if p['exit_date']<d:
                nav*=1+p['exposure']*(p['gross_return']-STATE_COST)
                peak=max(peak,nav)
            else:
                still.append(p)
        pending=still
        e=copy.deepcopy(e0)
        base=e['x10_base_v43_exposure'];raw=e['x10_confidence_multiplier']
        q75=x10.v43.v41.v30.quantile(prior_mult,TAIL_Q) if len(prior_mult)>=MIN_PRIOR else None
        capped_mult=min(raw,q75) if q75 is not None else raw
        target=min(1.0,max(0.0,base*capped_mult))
        prior_dd=nav/peak-1.0
        underwater=prior_dd<0
        final_ex=min(target,base) if underwater and target>base else target
        e['x11_prior_multiplier_q75']=q75
        e['x11_tail_capped_multiplier']=capped_mult
        e['x11_prior_closed_nav']=nav
        e['x11_prior_closed_peak']=peak
        e['x11_prior_closed_drawdown']=prior_dd
        e['x11_underwater_gate']=underwater
        e['x11_pre_gate_exposure']=target
        e['exposure']=final_ex
        e['ranking_rule']='X11_EXACT_X10_V43_PICKS_WITH_PRIOR_Q75_CONFIDENCE_TAIL_CAP_AND_PRIOR_CLOSED_EQUITY_UNDERWATER_GATE'
        out.append(e);pending.append(e);prior_mult.append(raw)
        log.append({'signal_date':d,'tickers':e['tickers'],'base_v43_exposure':base,'raw_x10_multiplier':raw,'prior_multiplier_q75':q75,'tail_capped_multiplier':capped_mult,'prior_closed_drawdown':prior_dd,'underwater_gate':underwater,'pre_gate_exposure':target,'final_exposure':final_ex})
    return out,invalid,log

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
    return {'baskets':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,'compounded_return':product(nets),'max_drawdown':mdd,'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,'mean_net_return':statistics.mean(nets) if nets else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None,'max_single_name_weight':max((max(e['weights']) for e in events),default=None),'mean_exposure':statistics.mean([e['exposure'] for e in events]) if events else None}

EV,INVALID,RISK_LOG=build();complete=(not INVALID and len(EV)==len(x10.v43.EV));years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in x10.v43.v41.v13.PERIODS};combined={str(c):summarize(EV,c) for c in COSTS}
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
v43ref=x10.v43.summarize(x10.v43.EV,.012);c=combined['0.012'];dominates=robust and c['compounded_return']>v43ref['compounded_return'] and c['max_drawdown']>=v43ref['max_drawdown'] and c['remove_best_basket_return']>v43ref['remove_best_basket_return']
status='X11_STRICTLY_DOMINATES_V43' if dominates else 'X11_DOES_NOT_STRICTLY_DOMINATE_V43'
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'single fixed X11: exact X10/V43 picks. Cap the X10 confidence multiplier at the expanding prior-only 75th percentile after the same four-observation minimum already used by V30; additionally, if prior fully-closed X11 equity at the central 1.2% cost is below its prior closed-equity peak, do not allow confidence exposure above the original V43 base exposure. De-risking below V43 remains allowed. No future outcome is used in either gate.','tail_quantile':TAIL_Q,'min_prior_multipliers':MIN_PRIOR,'state_cost':STATE_COST,'complete_common_schedule':complete,'invalid':INVALID,'robust':robust,'risk_log':RISK_LOG,'years':years,'combined':combined,'v43_reference':v43ref,'strictly_dominates_v43':dominates,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'One fixed exposed-history risk-control hypothesis on X10. Exact V43 stock picks, covariance/risk stack, H20 schedule and cost evaluation retained; no grid or parameter scan.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
