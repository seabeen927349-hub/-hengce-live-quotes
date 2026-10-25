#!/usr/bin/env python3
from __future__ import annotations
import copy,json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v43_expanding_regime_icir as v43

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_x10_v43_gap_confidence_exposure_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_x10_events.jsonl'
COSTS=(.008,.012,.016)
FRONTIER_RET=3.4265

BASE_BY_DATE={b['signal_date']:b for b in sorted(v43.v41.v19.v15.base,key=lambda e:e['signal_date'])}

def gap_at(d,regime):
    w,_,_,_=v43.weights_at(d,regime)
    F=v43.v41.v13.features.get(d,{})
    arr=sorted((sum(w[i]*vals[i] for i in range(5)),t) for t,vals in F.items())
    arr.reverse()
    if len(arr)<4:return None
    return arr[2][0]-arr[3][0]

def build():
    out=[];invalid=[];prior_gaps=[];log=[]
    base_events={e['signal_date']:e for e in v43.EV}
    for d,b in sorted(BASE_BY_DATE.items()):
        if d not in base_events:
            invalid.append([d,'MISSING_V43_BASE_EVENT']);continue
        e=copy.deepcopy(base_events[d])
        gap=gap_at(d,b['regime'])
        med=statistics.median(prior_gaps) if prior_gaps else None
        base_ex=e['exposure']
        if gap is None or med is None or med<=0:
            mult=1.0
        else:
            mult=gap/med
        final_ex=min(1.0,max(0.0,base_ex*mult))
        e['x10_base_v43_exposure']=base_ex
        e['x10_top3_top4_gap']=gap
        e['x10_prior_gap_median']=med
        e['x10_confidence_multiplier']=mult
        e['exposure']=final_ex
        e['ranking_rule']='X10_EXACT_V43_PICKS_WITH_PRIOR_MEDIAN_TOP3_TOP4_GAP_CONFIDENCE_EXPOSURE'
        out.append(e)
        log.append({'signal_date':d,'tickers':e['tickers'],'gap':gap,'prior_gap_median':med,'base_v43_exposure':base_ex,'confidence_multiplier':mult,'final_exposure':final_ex})
        if gap is not None and gap>=0:prior_gaps.append(gap)
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

EV,INVALID,CONFIDENCE_LOG=build();complete=(not INVALID and len(EV)==len(BASE_BY_DATE));years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in v43.v41.v13.PERIODS};combined={str(c):summarize(EV,c) for c in COSTS}
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
c=combined['0.012'];beats=robust and c['compounded_return']>FRONTIER_RET
status='X10_BEATS_V43_FRONTIER' if beats else 'X10_DOES_NOT_BEAT_V43_FRONTIER'
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'single fixed X10: exact V43 stock picks and covariance/risk stack, with a signal-time confidence exposure overlay. Confidence is current V43 rank-3 minus rank-4 score gap divided by the prior-only median of earlier formal-signal gaps; final exposure is base V43 exposure times that ratio, naturally capped at 1.0 and floored at 0. No future outcomes are used.','frontier_reference_return':FRONTIER_RET,'complete_common_schedule':complete,'invalid':INVALID,'robust':robust,'confidence_log':CONFIDENCE_LOG,'years':years,'combined':combined,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Exact V43 picks ensure common schedule comparability. One fixed prior-only confidence overlay; no grid, parameter scan, new data, horizon or schedule changes.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
