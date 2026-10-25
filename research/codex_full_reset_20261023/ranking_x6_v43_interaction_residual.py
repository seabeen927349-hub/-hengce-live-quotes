#!/usr/bin/env python3
from __future__ import annotations
import json, math, statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v43_expanding_regime_icir as v43

v41=v43.v41
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_x6_v43_interaction_residual_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_x6_events.jsonl'
COSTS=(.008,.012,.016); CAP=.50; TOPN=3; MIN_ANCHORS=3; STAB=.05
V43_REF={'ret':3.4265,'dd':-0.1767,'rem':1.9312,'win':0.667,'ret16':3.0649,'rem16':1.6986}
PAIRS=[(i,j) for i in range(5) for j in range(i+1,5)]
PAIR_NAMES=[v41.FACTORS[i]+'*'+v41.FACTORS[j] for i,j in PAIRS]

def rank_values(vals):
    a=sorted(vals.items(),key=lambda kv:(kv[1],kv[0]));n=len(a);out={}
    if n<=1:return {t:.5 for t,v in a}
    i=0
    while i<n:
        j=i+1
        while j<n and a[j][1]==a[i][1]:j+=1
        pct=(((i+1)+j)/2-1)/(n-1)
        for k in range(i,j):out[a[k][0]]=pct
        i=j
    return out

def corr(x,y):
    if len(x)<10:return None
    xb=statistics.mean(x);yb=statistics.mean(y);dx=sum((a-xb)**2 for a in x);dy=sum((b-yb)**2 for b in y)
    if dx<=1e-18 or dy<=1e-18:return None
    return sum((a-xb)*(b-yb) for a,b in zip(x,y))/math.sqrt(dx*dy)

def interactions(vals):
    c=[x-.5 for x in vals]
    return tuple(c[i]*c[j] for i,j in PAIRS)

ANCH=[]
for a in v41.ANCHORS:
    d=a['signal_date'];regime=a['regime'];F=v41.v13.features.get(d,{})
    target=v41.target_rank(d);w,_,_,_=v43.weights_at(d,regime)
    raw={t:sum(w[i]*vals[i] for i in range(5)) for t,vals in F.items() if t in target}
    base=rank_values(raw) if raw else {}
    rows=[]
    for t in raw:
        if t in base:rows.append({'ticker':t,'z':interactions(F[t]),'resid':target[t]-base[t]})
    ics=[corr([r['z'][k] for r in rows],[r['resid'] for r in rows]) for k in range(len(PAIRS))]
    ANCH.append({'signal_date':d,'exit_date':a['exit_date'],'regime':regime,'rows':rows,'ics':ics})

def learner(signal_date,regime):
    prior=[a for a in ANCH if a['exit_date']<signal_date and a['regime']==regime]
    if len(prior)<MIN_ANCHORS:return None,{'prior_anchors':len(prior),'fallback':True,'beta':0.0,'intercept':0.0,'weights':{n:0.0 for n in PAIR_NAMES}}
    stats=[]
    for k in range(len(PAIRS)):
        z=[a['ics'][k] for a in prior if a['ics'][k] is not None]
        if len(z)<MIN_ANCHORS:stats.append(0.0);continue
        mu=statistics.mean(z);sd=statistics.stdev(z) if len(z)>1 else 0.0;stats.append(mu/(sd+STAB))
    den=sum(abs(x) for x in stats)
    if den<=1e-18:return None,{'prior_anchors':len(prior),'fallback':True,'beta':0.0,'intercept':0.0,'weights':{n:0.0 for n in PAIR_NAMES}}
    weights=[x/den for x in stats];xs=[];ys=[]
    for a in prior:
        vals={r['ticker']:sum(weights[k]*r['z'][k] for k in range(len(PAIRS))) for r in a['rows']};rr=rank_values(vals) if vals else {}
        for r in a['rows']:
            if r['ticker'] in rr:xs.append(rr[r['ticker']]-.5);ys.append(r['resid'])
    if len(xs)<20:return None,{'prior_anchors':len(prior),'fallback':True,'beta':0.0,'intercept':0.0,'weights':dict(zip(PAIR_NAMES,weights))}
    xb=statistics.mean(xs);yb=statistics.mean(ys);vx=sum((x-xb)**2 for x in xs);beta=sum((x-xb)*(y-yb) for x,y in zip(xs,ys))/vx if vx>1e-18 else 0.0;intercept=yb-beta*xb
    return (weights,beta,intercept),{'prior_anchors':len(prior),'fallback':False,'beta':beta,'intercept':intercept,'weights':dict(zip(PAIR_NAMES,weights))}

def scores_at(d,regime):
    F=v41.v13.features.get(d,{});w,diag,prior,fallback=v43.weights_at(d,regime)
    raw={t:sum(w[i]*vals[i] for i in range(5)) for t,vals in F.items()};base=rank_values(raw) if raw else {};fit,meta=learner(d,regime)
    meta.update({'factor_weights':dict(zip(v41.FACTORS,w)),'v43_prior_regime_anchors':len(prior),'v43_fallback':fallback})
    if fit is None:return dict(base),meta
    iw,beta,intercept=fit;comp={t:sum(iw[k]*interactions(vals)[k] for k in range(len(PAIRS))) for t,vals in F.items()};crank=rank_values(comp) if comp else {}
    return {t:base[t]+intercept+beta*(crank[t]-.5) for t in base if t in crank},meta

def build():
    out=[];invalid=[];prior_sigma=[];score_log=[]
    for b in sorted(v41.v19.v15.base,key=lambda e:e['signal_date']):
        d=b['signal_date'];si=v41.DI[d];regime=b['regime'];scores,meta=scores_at(d,regime);arr=sorted([(s,t) for t,s in scores.items()],key=lambda z:(-z[0],z[1]));picks=[t for s,t in arr[:TOPN]]
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
        e={'signal_date':d,'entry_date':outs[0][1],'exit_date':outs[0][2],'tickers':picks,'uncapped_weights':uncapped,'weights':weights,'weight_cap':CAP,'sample_covariance':cov,'shrunk_covariance':shr,'gross_return':gross,'daily':daily,'regime':regime,'breadth20':b['breadth20'],'year':b['year'],'ranking_rule':'X6_V43_PLUS_PRIOR_ONLY_PAIR_INTERACTION_RESIDUAL','interaction_beta':meta['beta'],'interaction_prior_anchors':meta['prior_anchors'],'factor_weights':meta['factor_weights']}
        e['exposure']=v41.v19.exposure(e);e['vol_ratio']=v41.v19.vol_ratio(e)
        sig=v41.v30.predicted_sigma(e);q75=v41.v30.quantile(prior_sigma,v41.v30.TAIL_Q) if len(prior_sigma)>=v41.v30.MIN_PRIOR else None;breadth=e.get('breadth20');fragile=(regime=='STRONG' and breadth is not None and v41.v30.BREADTH_LO<=breadth<v41.v30.BREADTH_HI);tail=(q75 is not None and sig>q75 and sig>0);mult=(q75/sig) if fragile and tail else 1.0
        e['predicted_daily_sigma']=sig;e['prior_sigma_q75']=q75;e['fragile_strong']=fragile;e['tail_vol']=tail;e['risk_multiplier']=mult;e['base_exposure']=e['exposure'];e['exposure']=e['base_exposure']*mult;out.append(e);prior_sigma.append(sig)
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
status='X6_DOMINATES_V43' if strict else ('X6_ALPHA_IMPROVEMENT' if alpha else 'X6_DOES_NOT_BEAT_V43')
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'X6 nonlinear residual alpha: retain canonical signal-time V43 base ranks. On canonical non-overlapping H20 anchors, store only realized V43 rank errors. Ten centered pairwise factor interactions are evaluated by anchor-level residual IC; current same-regime prior anchors produce signed ICIR weights with the same +0.05 stabilizer. The weighted interaction composite is cross-sectionally ranked, and a closed-form prior-only OLS maps that rank to V43 residual error. No grid or manually tuned blend coefficient; insufficient history falls back exactly to V43. Top3/cap50/exposure/V30 unchanged.','min_anchors':MIN_ANCHORS,'icir_stabilizer':STAB,'complete_common_schedule':complete,'invalid':INVALID,'robust':robust,'years':years,'combined':combined,'v43_reference':V43_REF,'score_log':SCORE_LOG,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Exposed historical evaluation years. Every residual label is admitted only after its H20 exit; each anchor base prediction is itself signal-time V43. No parameter grid, new data, horizon, schedule, or cost assumption.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
