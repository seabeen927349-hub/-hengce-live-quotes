#!/usr/bin/env python3
from __future__ import annotations
import json, math, statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v43_expanding_regime_icir as v43

v41=v43.v41
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_x5_v43_knn_residual_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_x5_events.jsonl'
COSTS=(.008,.012,.016); CAP=.50; TOPN=3
V43_REF={'ret':3.4265,'dd':-0.1767,'rem':1.9312,'win':0.667,'ret16':3.0649,'rem16':1.6986}

# Historical labels are residual errors of a genuinely signal-time V43 prediction.
# They are unavailable to a future signal until the anchor H20 exit date has passed.
TRAIN_ANCHORS=[]
for a in v41.ANCHORS:
    d=a['signal_date']; regime=a['regime']; F=v41.v13.features.get(d,{})
    y=v41.target_rank(d); w,diag,prior,fallback=v43.weights_at(d,regime)
    raw={t:sum(w[i]*vals[i] for i in range(5)) for t,vals in F.items() if t in y}
    br=v41.v13.ranks(raw) if raw else {}
    rows=[(tuple(F[t]), y[t]-br[t], t) for t in raw if t in br]
    TRAIN_ANCHORS.append({'signal_date':d,'exit_date':a['exit_date'],'regime':regime,'rows':rows,'fallback':fallback})


def corrected_scores(signal_date,regime):
    F=v41.v13.features.get(signal_date,{})
    w,diag,prior,fallback=v43.weights_at(signal_date,regime)
    raw={t:sum(w[i]*vals[i] for i in range(5)) for t,vals in F.items()}
    base=v41.v13.ranks(raw) if raw else {}
    train=[]
    for a in TRAIN_ANCHORS:
        if a['exit_date']<signal_date and a['regime']==regime: train.extend(a['rows'])
    if not train:
        return dict(base),{'train_rows':0,'k':0,'factor_weights':dict(zip(v41.FACTORS,w)),'prior_regime_anchors':len(prior),'v43_fallback':fallback,'mean_abs_correction':0.0}
    k=max(1,int(math.sqrt(len(train))))
    out={};corrs=[]
    for t,x in F.items():
        near=[]
        for z,resid,src_t in train:
            ds=sum((x[i]-z[i])**2 for i in range(5))
            near.append((ds,resid,src_t))
        near.sort(key=lambda q:(q[0],q[2]))
        correction=statistics.mean(q[1] for q in near[:k]);corrs.append(abs(correction))
        out[t]=base[t]+correction
    return out,{'train_rows':len(train),'k':k,'factor_weights':dict(zip(v41.FACTORS,w)),'prior_regime_anchors':len(prior),'v43_fallback':fallback,'mean_abs_correction':statistics.mean(corrs) if corrs else 0.0}


def build():
    out=[];invalid=[];prior_sigma=[];score_log=[]
    for b in sorted(v41.v19.v15.base,key=lambda e:e['signal_date']):
        d=b['signal_date'];si=v41.DI[d];regime=b['regime'];scores,meta=corrected_scores(d,regime)
        arr=sorted([(s,t) for t,s in scores.items()],key=lambda z:(-z[0],z[1]));picks=[t for s,t in arr[:TOPN]]
        score_log.append({'signal_date':d,'regime':regime,'picks':picks,'top10':arr[:10],**meta})
        if len(picks)<TOPN:invalid.append([d,'NOT_ENOUGH_PICKS']);continue
        cw=v41.v27.uncapped_cov_weights(d,picks)
        if cw is None:invalid.append([d,'COVARIANCE_UNAVAILABLE']);continue
        uncapped,cov,shr=cw;weights=v41.v27.cap_weights(uncapped,CAP)
        if weights is None:invalid.append([d,'CAP_PROJECTION_FAILED']);continue
        outs=[];ok=True
        for t in picks:
            o=v41.v13.outcome(t,si)
            if o is None:ok=False;break
            outs.append(o)
        if not ok:invalid.append([d,'INVALID_OUTCOME']);continue
        gross=sum(wi*o[0] for wi,o in zip(weights,outs));daily=[]
        for j in range(v41.v13.H+1):daily.append([outs[0][3][j][0],sum(wi*o[3][j][1] for wi,o in zip(weights,outs))])
        e={'signal_date':d,'entry_date':outs[0][1],'exit_date':outs[0][2],'tickers':picks,'uncapped_weights':uncapped,'weights':weights,'weight_cap':CAP,'sample_covariance':cov,'shrunk_covariance':shr,'gross_return':gross,'daily':daily,'regime':regime,'breadth20':b['breadth20'],'year':b['year'],'ranking_rule':'X5_V43_PLUS_PRIOR_ONLY_KNN_RESIDUAL_CORRECTION','corrected_scores':{t:scores[t] for t in picks},'knn_train_rows':meta['train_rows'],'knn_k':meta['k'],'factor_weights':meta['factor_weights'],'prior_regime_anchors':meta['prior_regime_anchors']}
        e['exposure']=v41.v19.exposure(e);e['vol_ratio']=v41.v19.vol_ratio(e)
        sig=v41.v30.predicted_sigma(e);q75=v41.v30.quantile(prior_sigma,v41.v30.TAIL_Q) if len(prior_sigma)>=v41.v30.MIN_PRIOR else None
        breadth=e.get('breadth20');fragile=(regime=='STRONG' and breadth is not None and v41.v30.BREADTH_LO<=breadth<v41.v30.BREADTH_HI);tail=(q75 is not None and sig>q75 and sig>0);mult=(q75/sig) if fragile and tail else 1.0
        e['predicted_daily_sigma']=sig;e['prior_sigma_q75']=q75;e['fragile_strong']=fragile;e['tail_vol']=tail;e['risk_multiplier']=mult;e['base_exposure']=e['exposure'];e['exposure']=e['base_exposure']*mult
        out.append(e);prior_sigma.append(sig)
    return out,invalid,score_log


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

EV,INVALID,SCORE_LOG=build();complete=(not INVALID and len(EV)==len(v41.v19.v15.base));years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in v41.v13.PERIODS};combined={str(c):summarize(EV,c) for c in COSTS}
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
c=combined['0.012'];strict=robust and c['compounded_return']>V43_REF['ret'] and c['max_drawdown']>=V43_REF['dd'] and c['remove_best_basket_return']>V43_REF['rem'];alpha=robust and c['compounded_return']>V43_REF['ret'] and c['remove_best_basket_return']>V43_REF['rem'] and c['max_drawdown']>=-.30
status='X5_DOMINATES_V43' if strict else ('X5_ALPHA_IMPROVEMENT' if alpha else 'X5_DOES_NOT_BEAT_V43')
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'X5 nonlinear residual corrector: canonical signal-time V43 produces a cross-sectional base rank. Historical canonical H20 anchors store only V43 out-of-sample ranking errors (realized target rank minus signal-time V43 base rank). For each current stock, same-regime fully-realized prior error states are searched in five-factor rank space with deterministic k=floor(sqrt(N)); mean neighbor error is added one-for-one to the current V43 base rank. Thus the nonlinear learner models only V43 residual error rather than replacing the proven baseline. No blend coefficient or parameter grid. Top3/cap50/exposure/V30 unchanged.','complete_common_schedule':complete,'invalid':INVALID,'robust':robust,'years':years,'combined':combined,'v43_reference':V43_REF,'score_log':SCORE_LOG,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Exposed historical evaluation years. Each historical base prediction is itself signal-time prior-only; residual labels are admitted only after their H20 exit. No grid, new data, horizon, schedule, or cost assumption.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
