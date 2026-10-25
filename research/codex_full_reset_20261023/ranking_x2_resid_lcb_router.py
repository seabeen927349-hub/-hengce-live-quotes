#!/usr/bin/env python3
from __future__ import annotations
import json, math, statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v43_expanding_regime_icir as v43

v41=v43.v41
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_x2_resid_lcb_router_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_x2_events.jsonl'
COSTS=(.008,.012,.016); COST_GATE=.012; CAP=.50; TOPN=3; MIN_PRIOR=3
V43_REF={'ret':3.4265,'dd':-0.1767,'rem':1.9312,'win':0.667,'ret16':3.0649,'rem16':1.6986}

def lcb(xs):
    if len(xs)<MIN_PRIOR:return None
    mu=statistics.mean(xs)
    if len(xs)<2:return mu
    se=statistics.stdev(xs)/math.sqrt(len(xs))
    return mu-se

def make_event(b,expert,prior_sigma):
    d=b['signal_date'];si=v41.DI[d];regime=b['regime'];F=v41.v13.features.get(d,{})
    if expert=='V43':
        w,diag,prior,fallback=v43.weights_at(d,regime)
        arr=[(sum(w[i]*vals[i] for i in range(5)),t) for t,vals in F.items()]
        rule='X2_EXPERT_V43_ICIR'
        extra={'factor_weights':dict(zip(v41.FACTORS,w)),'prior_regime_anchors':len(prior),'fallback':fallback}
    elif expert=='RESID':
        arr=[(vals[0],t) for t,vals in F.items()]
        rule='X2_EXPERT_PURE_RESID_REVERSION'
        extra={}
    else:
        raise ValueError(expert)
    arr.sort(key=lambda z:(-z[0],z[1]));picks=[t for s,t in arr[:TOPN]]
    if len(picks)<TOPN:return None,'NOT_ENOUGH_PICKS'
    cw=v41.v27.uncapped_cov_weights(d,picks)
    if cw is None:return None,'COVARIANCE_UNAVAILABLE'
    uncapped,cov,shr=cw;weights=v41.v27.cap_weights(uncapped,CAP)
    if weights is None:return None,'CAP_PROJECTION_FAILED'
    outs=[]
    for t in picks:
        o=v41.v13.outcome(t,si)
        if o is None:return None,'INVALID_OUTCOME'
        outs.append(o)
    gross=sum(wi*o[0] for wi,o in zip(weights,outs));daily=[]
    for k in range(v41.v13.H+1):daily.append([outs[0][3][k][0],sum(wi*o[3][k][1] for wi,o in zip(weights,outs))])
    e={'signal_date':d,'entry_date':outs[0][1],'exit_date':outs[0][2],'tickers':picks,'uncapped_weights':uncapped,'weights':weights,'weight_cap':CAP,'sample_covariance':cov,'shrunk_covariance':shr,'gross_return':gross,'daily':daily,'regime':regime,'breadth20':b['breadth20'],'year':b['year'],'ranking_rule':rule,'expert':expert,**extra}
    e['exposure']=v41.v19.exposure(e);e['vol_ratio']=v41.v19.vol_ratio(e)
    sig=v41.v30.predicted_sigma(e);q75=v41.v30.quantile(prior_sigma,v41.v30.TAIL_Q) if len(prior_sigma)>=v41.v30.MIN_PRIOR else None
    breadth=e.get('breadth20');fragile=(regime=='STRONG' and breadth is not None and v41.v30.BREADTH_LO<=breadth<v41.v30.BREADTH_HI);tail=(q75 is not None and sig>q75 and sig>0);mult=(q75/sig) if fragile and tail else 1.0
    e['predicted_daily_sigma']=sig;e['prior_sigma_q75']=q75;e['fragile_strong']=fragile;e['tail_vol']=tail;e['risk_multiplier']=mult;e['base_exposure']=e['exposure'];e['exposure']=e['base_exposure']*mult
    return e,None

def net(e,cost=COST_GATE):return e['exposure']*(e['gross_return']-cost)

def build():
    out=[];invalid=[];router_log=[]
    histories={'V43':[],'RESID':[]};sigmas={'V43':[],'RESID':[]}
    for b in sorted(v41.v19.v15.base,key=lambda e:e['signal_date']):
        d=b['signal_date'];regime=b['regime'];cands={}
        for expert in ('V43','RESID'):
            e,err=make_event(b,expert,sigmas[expert])
            if err is not None:invalid.append([d,expert,err]);continue
            cands[expert]=e
        if len(cands)!=2:continue
        scores={};counts={}
        for expert in ('V43','RESID'):
            prior=[e for e in histories[expert] if e['regime']==regime and e['exit_date']<d]
            vals=[net(e) for e in prior];scores[expert]=lcb(vals);counts[expert]=len(vals)
        choose='V43'
        if scores['V43'] is not None and scores['RESID'] is not None and scores['RESID']>scores['V43']:
            choose='RESID'
        sel=dict(cands[choose]);sel['router_lcb']=scores;sel['router_prior_counts']=counts;sel['router_choice']=choose;sel['ranking_rule']='X2_PRIOR_ONLY_REGIME_LCB_EXPERT_ROUTER'
        out.append(sel)
        router_log.append({'signal_date':d,'regime':regime,'choice':choose,'lcb':scores,'prior_counts':counts,'v43_picks':cands['V43']['tickers'],'resid_picks':cands['RESID']['tickers']})
        for expert in ('V43','RESID'):
            histories[expert].append(cands[expert]);sigmas[expert].append(cands[expert]['predicted_daily_sigma'])
    return out,invalid,router_log

def product(xs):
    n=1.0
    for x in xs:n*=1+x
    return n-1

def summarize(events,cost):
    nets=[];nav=1.;peak=1.;mdd=0.
    for e in events:
        ex=e['exposure'];netr=ex*(e['gross_return']-cost);nets.append(netr);b=nav
        for j,(d,r) in enumerate(e['daily']):
            temp=b*(1+ex*r-(ex*cost if j==len(e['daily'])-1 else 0));peak=max(peak,temp);mdd=min(mdd,temp/peak-1)
        nav=b*(1+netr)
    bi=max(range(len(nets)),key=lambda k:nets[k]) if nets else None
    return {'baskets':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,'compounded_return':product(nets),'max_drawdown':mdd,'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,'mean_net_return':statistics.mean(nets) if nets else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None,'max_single_name_weight':max((max(e['weights']) for e in events),default=None),'mean_exposure':statistics.mean([e['exposure'] for e in events]) if events else None}

EV,INVALID,ROUTER_LOG=build();complete=(not INVALID and len(EV)==len(v41.v19.v15.base));years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in v41.v13.PERIODS};combined={str(c):summarize(EV,c) for c in COSTS}
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
c=combined['0.012'];strict=robust and c['compounded_return']>V43_REF['ret'] and c['max_drawdown']>=V43_REF['dd'] and c['remove_best_basket_return']>V43_REF['rem'];alpha=robust and c['compounded_return']>V43_REF['ret'] and c['remove_best_basket_return']>V43_REF['rem'] and c['max_drawdown']>=-.30
status='X2_DOMINATES_V43' if strict else ('X2_ALPHA_IMPROVEMENT' if alpha else 'X2_DOES_NOT_BEAT_V43')
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'X2 structural expert router: each signal independently builds the canonical V43 expert and a pure residual-reversion expert under the same Top3/cap50/exposure/V30 risk stack. Within the current regime, only fully realized prior baskets are used. Residual expert replaces V43 only when its one-standard-error lower confidence bound of 1.2%-cost basket returns exceeds V43; otherwise default V43. No parameter grid.','gate_cost':COST_GATE,'min_prior':MIN_PRIOR,'complete_common_schedule':complete,'invalid':INVALID,'robust':robust,'years':years,'combined':combined,'v43_reference':V43_REF,'router_log':ROUTER_LOG,'choice_counts':{k:sum(x['choice']==k for x in ROUTER_LOG) for k in ('V43','RESID')},'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Exposed historical evaluation years; routing uses only prior fully realized same-regime baskets. No new data, horizon, schedule, or parameter grid.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
