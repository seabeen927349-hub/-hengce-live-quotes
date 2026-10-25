#!/usr/bin/env python3
from __future__ import annotations
import json, statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v43_expanding_regime_icir as v43

v41=v43.v41
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_x3_factor_leaveoneout_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_x3_events.jsonl'
COSTS=(.008,.012,.016); CAP=.50; TOPN=3
V43_REF={'ret':3.4265,'dd':-0.1767,'rem':1.9312,'win':0.667,'ret16':3.0649,'rem16':1.6986}


def robust_score(vals,w):
    full=sum(w[i]*vals[i] for i in range(5))
    loo=[]
    for j in range(5):
        den=1.0-w[j]
        if den<=1e-12: continue
        loo.append(sum(w[i]*vals[i] for i in range(5) if i!=j)/den)
    return min(loo),full,loo


def build():
    out=[]; invalid=[]; prior_sigma=[]; score_log=[]
    for b in sorted(v41.v19.v15.base,key=lambda e:e['signal_date']):
        d=b['signal_date']; si=v41.DI[d]; regime=b['regime']; w,diag,prior,fallback=v43.weights_at(d,regime)
        F=v41.v13.features.get(d,{})
        rows=[]
        for t,vals in F.items():
            rs,full,loo=robust_score(vals,w)
            rows.append((rs,t,full,loo))
        rows.sort(key=lambda z:(-z[0],-z[2],z[1])); picks=[r[1] for r in rows[:TOPN]]
        score_log.append({'signal_date':d,'regime':regime,'factor_weights':dict(zip(v41.FACTORS,w)),'prior_regime_anchors':len(prior),'fallback':fallback,'picks':picks,'top10':[{'ticker':t,'worst_case':rs,'full_v43':full,'leave_one_out':dict(zip(v41.FACTORS,loo))} for rs,t,full,loo in rows[:10]]})
        if len(picks)<TOPN: invalid.append([d,'NOT_ENOUGH_PICKS']); continue
        cw=v41.v27.uncapped_cov_weights(d,picks)
        if cw is None: invalid.append([d,'COVARIANCE_UNAVAILABLE']); continue
        uncapped,cov,shr=cw; weights=v41.v27.cap_weights(uncapped,CAP)
        if weights is None: invalid.append([d,'CAP_PROJECTION_FAILED']); continue
        outs=[]; ok=True
        for t in picks:
            o=v41.v13.outcome(t,si)
            if o is None: ok=False; break
            outs.append(o)
        if not ok: invalid.append([d,'INVALID_OUTCOME']); continue
        gross=sum(wi*o[0] for wi,o in zip(weights,outs)); daily=[]
        for k in range(v41.v13.H+1): daily.append([outs[0][3][k][0],sum(wi*o[3][k][1] for wi,o in zip(weights,outs))])
        picked={r[1]:r for r in rows[:TOPN]}
        e={'signal_date':d,'entry_date':outs[0][1],'exit_date':outs[0][2],'tickers':picks,'uncapped_weights':uncapped,'weights':weights,'weight_cap':CAP,'sample_covariance':cov,'shrunk_covariance':shr,'gross_return':gross,'daily':daily,'regime':regime,'breadth20':b['breadth20'],'year':b['year'],'factor_weights':dict(zip(v41.FACTORS,w)),'prior_regime_anchors':len(prior),'ranking_rule':'X3_V43_FACTOR_LEAVE_ONE_OUT_WORST_CASE','robust_scores':{t:picked[t][0] for t in picks},'full_v43_scores':{t:picked[t][2] for t in picks}}
        e['exposure']=v41.v19.exposure(e); e['vol_ratio']=v41.v19.vol_ratio(e)
        sig=v41.v30.predicted_sigma(e); q75=v41.v30.quantile(prior_sigma,v41.v30.TAIL_Q) if len(prior_sigma)>=v41.v30.MIN_PRIOR else None
        breadth=e.get('breadth20'); fragile=(regime=='STRONG' and breadth is not None and v41.v30.BREADTH_LO<=breadth<v41.v30.BREADTH_HI); tail=(q75 is not None and sig>q75 and sig>0); mult=(q75/sig) if fragile and tail else 1.0
        e['predicted_daily_sigma']=sig; e['prior_sigma_q75']=q75; e['fragile_strong']=fragile; e['tail_vol']=tail; e['risk_multiplier']=mult; e['base_exposure']=e['exposure']; e['exposure']=e['base_exposure']*mult
        out.append(e); prior_sigma.append(sig)
    return out,invalid,score_log


def product(xs):
    n=1.0
    for x in xs:n*=1+x
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

EV,INVALID,SCORE_LOG=build(); complete=(not INVALID and len(EV)==len(v41.v19.v15.base))
years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in v41.v13.PERIODS}; combined={str(c):summarize(EV,c) for c in COSTS}
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
c=combined['0.012']; strict=robust and c['compounded_return']>V43_REF['ret'] and c['max_drawdown']>=V43_REF['dd'] and c['remove_best_basket_return']>V43_REF['rem']; alpha=robust and c['compounded_return']>V43_REF['ret'] and c['remove_best_basket_return']>V43_REF['rem'] and c['max_drawdown']>=-.30
status='X3_DOMINATES_V43' if strict else ('X3_ALPHA_IMPROVEMENT' if alpha else 'X3_DOES_NOT_BEAT_V43')
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV: fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'X3 structural confidence alpha: retain canonical signal-time V43 prior-only regime ICIR weights, but rank each stock by its worst leave-one-factor-out weighted score. A candidate must remain strong if any one of the five factors is omitted. No future labels enter selection and there is no penalty coefficient or parameter grid. Top3/cap50/exposure/V30 risk stack unchanged.','complete_common_schedule':complete,'invalid':INVALID,'robust':robust,'years':years,'combined':combined,'v43_reference':V43_REF,'score_log':SCORE_LOG,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Exposed historical evaluation years; V43 weights and leave-one-out scores use signal-time information only. No new data, horizon, schedule, cost assumption, or parameter grid.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(res,ensure_ascii=False,indent=2))
