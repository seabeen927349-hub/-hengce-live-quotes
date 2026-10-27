#!/usr/bin/env python3
from __future__ import annotations
import json, statistics
from collections import defaultdict
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v43_expanding_regime_icir as v43

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_x7_dominant_factor_direction_archetype_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_x7_events.jsonl'
COSTS=(.008,.012,.016); CAP=.50; TOPN=3
FRONTIER_RET=3.4265
MIN_CELL_N=5


def archetype(vals, weights):
    contrib=[weights[i]*vals[i] for i in range(5)]
    k=max(range(5), key=lambda i:(abs(contrib[i]),-i))
    return f"{v43.v41.FACTORS[k]}:{'POS' if vals[k]>=0 else 'NEG'}"


def base_snapshot(d):
    regime='STRONG' if v43.v41.v13.breadth[d]>=v43.v41.v13.BREADTH_CUTOFF else 'WEAK'
    weights,_,_,_=v43.weights_at(d,regime)
    F=v43.v41.v13.features.get(d,{})
    scores={t:sum(weights[i]*vals[i] for i in range(5)) for t,vals in F.items()}
    ranks=v43.v41.v13.ranks(scores) if scores else {}
    return regime,weights,F,ranks


ANCHOR_ROWS=[]
for a in v43.v41.ANCHORS:
    d=a['signal_date']
    regime,weights,F,base_ranks=base_snapshot(d)
    target=v43.v41.target_rank(d)
    rows=[]
    for t in sorted(set(F).intersection(base_ranks).intersection(target)):
        rows.append((archetype(F[t],weights),target[t]-base_ranks[t]))
    ANCHOR_ROWS.append({'signal_date':d,'exit_date':a['exit_date'],'regime':regime,'rows':rows})


def prior_calibration(signal_date):
    cells=defaultdict(list)
    for a in ANCHOR_ROWS:
        if a['exit_date'] < signal_date:
            for cell,resid in a['rows']:
                cells[cell].append(resid)
    means={cell:(statistics.mean(z) if len(z)>=MIN_CELL_N else 0.0) for cell,z in cells.items()}
    counts={cell:len(z) for cell,z in cells.items()}
    return means,counts


def build():
    out=[]; invalid=[]; prior_sigma=[]; calibration_log=[]
    for b in sorted(v43.v41.v19.v15.base,key=lambda e:e['signal_date']):
        d=b['signal_date']; si=v43.v41.DI[d]; regime=b['regime']
        w,diag,prior,fallback=v43.weights_at(d,regime)
        F=v43.v41.v13.features.get(d,{})
        scores={t:sum(w[i]*vals[i] for i in range(5)) for t,vals in F.items()}
        base_ranks=v43.v41.v13.ranks(scores) if scores else {}
        cal,counts=prior_calibration(d)
        arr=[]
        for t,vals in F.items():
            cell=archetype(vals,w)
            arr.append((base_ranks.get(t,0.0)+cal.get(cell,0.0),t,cell))
        arr.sort(key=lambda z:(-z[0],z[1]))
        picks=[t for _,t,_ in arr[:TOPN]]
        calibration_log.append({'signal_date':d,'regime':regime,'factor_weights':dict(zip(v43.v41.FACTORS,w)),'prior_regime_anchors':len(prior),'v43_fallback':fallback,'cell_counts':counts,'cell_mean_residual':cal,'picked_archetypes':[cell for _,_,cell in arr[:TOPN]]})
        if len(picks)<TOPN: invalid.append([d,'NOT_ENOUGH_PICKS']); continue
        cw=v43.v41.v27.uncapped_cov_weights(d,picks)
        if cw is None: invalid.append([d,'COVARIANCE_UNAVAILABLE']); continue
        uncapped,cov,shr=cw; weights=v43.v41.v27.cap_weights(uncapped,CAP)
        if weights is None: invalid.append([d,'CAP_PROJECTION_FAILED']); continue
        outs=[]; ok=True
        for t in picks:
            o=v43.v41.v13.outcome(t,si)
            if o is None: ok=False; break
            outs.append(o)
        if not ok: invalid.append([d,'INVALID_OUTCOME']); continue
        gross=sum(wi*o[0] for wi,o in zip(weights,outs)); daily=[]
        for k in range(v43.v41.v13.H+1):
            daily.append([outs[0][3][k][0],sum(wi*o[3][k][1] for wi,o in zip(weights,outs))])
        e={'signal_date':d,'entry_date':outs[0][1],'exit_date':outs[0][2],'tickers':picks,'uncapped_weights':uncapped,'weights':weights,'weight_cap':CAP,'sample_covariance':cov,'shrunk_covariance':shr,'gross_return':gross,'daily':daily,'regime':regime,'breadth20':b['breadth20'],'year':b['year'],'factor_weights':dict(zip(v43.v41.FACTORS,w)),'ranking_rule':'V43_BASE_RANK_PLUS_PRIOR_ONLY_DOMINANT_FACTOR_DIRECTION_MEAN_RESIDUAL'}
        e['exposure']=v43.v41.v19.exposure(e); e['vol_ratio']=v43.v41.v19.vol_ratio(e)
        sig=v43.v41.v30.predicted_sigma(e)
        q75=v43.v41.v30.quantile(prior_sigma,v43.v41.v30.TAIL_Q) if len(prior_sigma)>=v43.v41.v30.MIN_PRIOR else None
        breadth=e.get('breadth20')
        fragile=(regime=='STRONG' and breadth is not None and v43.v41.v30.BREADTH_LO<=breadth<v43.v41.v30.BREADTH_HI)
        tail=(q75 is not None and sig>q75 and sig>0); mult=(q75/sig) if fragile and tail else 1.0
        e['predicted_daily_sigma']=sig; e['prior_sigma_q75']=q75; e['fragile_strong']=fragile; e['tail_vol']=tail; e['risk_multiplier']=mult; e['base_exposure']=e['exposure']; e['exposure']=e['base_exposure']*mult
        out.append(e); prior_sigma.append(sig)
    return out,invalid,calibration_log


def product(xs):
    n=1.0
    for x in xs: n*=1+x
    return n-1


def summarize(events,cost):
    nets=[]; nav=1.; peak=1.; mdd=0.
    for e in events:
        ex=e['exposure']; net=ex*(e['gross_return']-cost); nets.append(net); b=nav
        for j,(d,r) in enumerate(e['daily']):
            temp=b*(1+ex*r-(ex*cost if j==len(e['daily'])-1 else 0)); peak=max(peak,temp); mdd=min(mdd,temp/peak-1)
        nav=b*(1+net)
    bi=max(range(len(nets)),key=lambda k:nets[k]) if nets else None
    return {'baskets':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,'compounded_return':product(nets),'max_drawdown':mdd,'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,'mean_net_return':statistics.mean(nets) if nets else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None,'max_single_name_weight':max((max(e['weights']) for e in events),default=None),'mean_exposure':statistics.mean([e['exposure'] for e in events]) if events else None}


EV,INVALID,CALIBRATION_LOG=build()
complete=(not INVALID and len(EV)==len(v43.v41.v19.v15.base))
years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in v43.v41.v13.PERIODS}
combined={str(c):summarize(EV,c) for c in COSTS}
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
c=combined['0.012']; beats=robust and c['compounded_return']>FRONTIER_RET
status='X7_BEATS_V43_FRONTIER' if beats else 'X7_DOES_NOT_BEAT_V43_FRONTIER'
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV: fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'single fixed X7: preserve V43 ICIR factor weights and execution/risk stack; rank by V43 base cross-sectional rank plus expanding prior-only mean residual keyed only by dominant weighted factor and sign (10 archetypes). No grid or parameter search.','archetype_definition':'argmax abs(V43_weight_i * feature_i), crossed with sign(feature_i)','min_cell_n':MIN_CELL_N,'training_anchor_count':len(ANCHOR_ROWS),'calibration_log':CALIBRATION_LOG,'complete_common_schedule':complete,'invalid':INVALID,'robust':robust,'years':years,'combined':combined,'frontier_return_reference':FRONTIER_RET,'frontier_gate':'valid complete robust run and 0.012 compounded return strictly above 3.4265','events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'One preregistered low-dimensional structural calibration hypothesis. Same PIT universe, costs, H20 schedule, covariance weighting, exposure and fragile-strong tail-risk stack as V43.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(res,ensure_ascii=False,indent=2))
