#!/usr/bin/env python3
from __future__ import annotations
import json, math, statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v43_expanding_regime_icir as v43

v41=v43.v41
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_x4_regime_knn_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_x4_events.jsonl'
COSTS=(.008,.012,.016); CAP=.50; TOPN=3
V43_REF={'ret':3.4265,'dd':-0.1767,'rem':1.9312,'win':0.667,'ret16':3.0649,'rem16':1.6986}

# Expand only the same non-overlapping H20 anchors already admitted by V41/V43.
TRAIN_ANCHORS=[]
for a in v41.ANCHORS:
    d=a['signal_date']; yr=v41.target_rank(d); F=v41.v13.features.get(d,{})
    rows=[(tuple(F[t]),yr[t],t) for t in F if t in yr]
    TRAIN_ANCHORS.append({'signal_date':d,'exit_date':a['exit_date'],'regime':a['regime'],'rows':rows})


def predict_scores(signal_date,regime):
    rows=[]
    for a in TRAIN_ANCHORS:
        if a['exit_date']<signal_date and a['regime']==regime: rows.extend(a['rows'])
    F=v41.v13.features.get(signal_date,{})
    n=len(rows)
    if n==0: return {},{'train_rows':0,'k':0,'anchor_count':0}
    k=max(1,int(math.sqrt(n)))
    out={}
    for t,x in F.items():
        near=[]
        for z,y,src_t in rows:
            ds=sum((x[i]-z[i])**2 for i in range(5))
            near.append((ds,y,src_t))
        near.sort(key=lambda q:(q[0],q[2]))
        out[t]=statistics.mean(q[1] for q in near[:k])
    ac=sum(a['exit_date']<signal_date and a['regime']==regime for a in TRAIN_ANCHORS)
    return out,{'train_rows':n,'k':k,'anchor_count':ac}


def build():
    out=[];invalid=[];prior_sigma=[];score_log=[]
    for b in sorted(v41.v19.v15.base,key=lambda e:e['signal_date']):
        d=b['signal_date'];si=v41.DI[d];regime=b['regime'];scores,meta=predict_scores(d,regime)
        if not scores:
            invalid.append([d,'NO_PRIOR_TRAINING']);continue
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
        e={'signal_date':d,'entry_date':outs[0][1],'exit_date':outs[0][2],'tickers':picks,'uncapped_weights':uncapped,'weights':weights,'weight_cap':CAP,'sample_covariance':cov,'shrunk_covariance':shr,'gross_return':gross,'daily':daily,'regime':regime,'breadth20':b['breadth20'],'year':b['year'],'ranking_rule':'X4_PRIOR_ONLY_SAME_REGIME_SQRTN_KNN','knn_scores':{t:scores[t] for t in picks},'knn_train_rows':meta['train_rows'],'knn_k':meta['k'],'prior_regime_anchors':meta['anchor_count']}
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
status='X4_DOMINATES_V43' if strict else ('X4_ALPHA_IMPROVEMENT' if alpha else 'X4_DOES_NOT_BEAT_V43')
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'X4 nonlinear alpha: same-regime prior-only k-nearest-neighbor regression in the five-dimensional cross-sectional factor-rank space. Training rows come only from the canonical non-overlapping H20 V41/V43 anchors whose exits precede the current signal. k=floor(sqrt(N)) is deterministic; prediction is the unweighted mean H20 target rank of the k nearest historical stock states. Top3/cap50/exposure/V30 stack unchanged. No V43 score enters ranking.','complete_common_schedule':complete,'invalid':INVALID,'robust':robust,'years':years,'combined':combined,'v43_reference':V43_REF,'score_log':SCORE_LOG,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Exposed historical evaluation years; all labels are fully realized before each signal. No parameter grid, new data, horizon, schedule, or cost assumption.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
