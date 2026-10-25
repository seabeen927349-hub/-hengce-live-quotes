#!/usr/bin/env python3
from __future__ import annotations
import json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v43_expanding_regime_icir as v43

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_x9_two_period_rank_maximin_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_x9_events.jsonl'
COSTS=(.008,.012,.016); CAP=.50; TOPN=3
FRONTIER_RET=3.4265
BASE_SCHEDULE=sorted(v43.v41.v19.v15.base,key=lambda e:e['signal_date'])
PREV_SIGNAL={b['signal_date']:(BASE_SCHEDULE[i-1]['signal_date'] if i>0 else None) for i,b in enumerate(BASE_SCHEDULE)}
BASE_BY_DATE={b['signal_date']:b for b in BASE_SCHEDULE}

def pct_ranks(score_map):
    arr=sorted(score_map.items(),key=lambda kv:(kv[1],kv[0]))
    n=len(arr)
    if n<=1:return {t:1.0 for t,_ in arr}
    return {t:i/(n-1) for i,(t,_) in enumerate(arr)}

def raw_scores(d,regime):
    w,diag,prior,fallback=v43.weights_at(d,regime)
    F=v43.v41.v13.features.get(d,{})
    scores={t:sum(w[i]*vals[i] for i in range(5)) for t,vals in F.items()}
    return scores,w,diag,prior,fallback

def rank_at(d,regime):
    cur,w,diag,prior,fallback=raw_scores(d,regime)
    cur_r=pct_ranks(cur)
    prev_d=PREV_SIGNAL.get(d)
    prev_r={}
    if prev_d:
        pb=BASE_BY_DATE[prev_d]
        ps,_,_,_,_=raw_scores(prev_d,pb['regime'])
        prev_r=pct_ranks(ps)
    arr=[];log={}
    for t in cur:
        if t in prev_r:
            score=min(cur_r[t],prev_r[t]); used=True
        else:
            score=cur_r[t]; used=False
        arr.append((score,t));log[t]={'current_pct_rank':cur_r[t],'previous_pct_rank':prev_r.get(t),'x9_maximin':score,'used_previous':used}
    arr.sort(key=lambda z:(-z[0],z[1]))
    return [t for _,t in arr[:TOPN]],w,diag,prior,fallback,log

def build():
    out=[];invalid=[];prior_sigma=[];ranking_log=[]
    for b in BASE_SCHEDULE:
        d=b['signal_date'];si=v43.v41.DI[d];regime=b['regime']
        picks,w,diag,prior,fallback,log=rank_at(d,regime)
        ranking_log.append({'signal_date':d,'previous_signal_date':PREV_SIGNAL.get(d),'regime':regime,'weights':dict(zip(v43.v41.FACTORS,w)),'prior_regime_anchors':len(prior),'fallback':fallback,'picks':picks,'pick_scores':{t:log[t] for t in picks}})
        if len(picks)<TOPN:invalid.append([d,'NOT_ENOUGH_PICKS']);continue
        cw=v43.v41.v27.uncapped_cov_weights(d,picks)
        if cw is None:invalid.append([d,'COVARIANCE_UNAVAILABLE']);continue
        uncapped,cov,shr=cw;weights=v43.v41.v27.cap_weights(uncapped,CAP)
        if weights is None:invalid.append([d,'CAP_PROJECTION_FAILED']);continue
        outs=[];ok=True
        for t in picks:
            o=v43.v41.v13.outcome(t,si)
            if o is None:ok=False;break
            outs.append(o)
        if not ok:invalid.append([d,'INVALID_OUTCOME']);continue
        gross=sum(wi*o[0] for wi,o in zip(weights,outs));daily=[]
        for k in range(v43.v41.v13.H+1):daily.append([outs[0][3][k][0],sum(wi*o[3][k][1] for wi,o in zip(weights,outs))])
        e={'signal_date':d,'entry_date':outs[0][1],'exit_date':outs[0][2],'tickers':picks,'uncapped_weights':uncapped,'weights':weights,'weight_cap':CAP,'sample_covariance':cov,'shrunk_covariance':shr,'gross_return':gross,'daily':daily,'regime':regime,'breadth20':b['breadth20'],'year':b['year'],'factor_weights':dict(zip(v43.v41.FACTORS,w)),'prior_regime_anchors':len(prior),'ranking_rule':'X9_MIN_CURRENT_PREVIOUS_V43_CROSS_SECTIONAL_PERCENTILE_RANK'}
        e['exposure']=v43.v41.v19.exposure(e);e['vol_ratio']=v43.v41.v19.vol_ratio(e)
        sig=v43.v41.v30.predicted_sigma(e);q75=v43.v41.v30.quantile(prior_sigma,v43.v41.v30.TAIL_Q) if len(prior_sigma)>=v43.v41.v30.MIN_PRIOR else None;breadth=e.get('breadth20');fragile=(regime=='STRONG' and breadth is not None and v43.v41.v30.BREADTH_LO<=breadth<v43.v41.v30.BREADTH_HI);tail=(q75 is not None and sig>q75 and sig>0);mult=(q75/sig) if fragile and tail else 1.0
        e['predicted_daily_sigma']=sig;e['prior_sigma_q75']=q75;e['fragile_strong']=fragile;e['tail_vol']=tail;e['risk_multiplier']=mult;e['base_exposure']=e['exposure'];e['exposure']=e['base_exposure']*mult
        out.append(e);prior_sigma.append(sig)
    return out,invalid,ranking_log

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

EV,INVALID,RANKING_LOG=build();complete=(not INVALID and len(EV)==len(BASE_SCHEDULE));years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in v43.v41.v13.PERIODS};combined={str(c):summarize(EV,c) for c in COSTS}
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
c=combined['0.012'];beats=robust and c['compounded_return']>FRONTIER_RET
status='X9_BEATS_V43_FRONTIER' if beats else 'X9_DOES_NOT_BEAT_V43_FRONTIER'
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'single fixed X9: rank each stock by the minimum of current and immediately prior formal-signal V43 cross-sectional percentile ranks when prior exists; otherwise current rank. This is a parameter-free persistence maximin rule. V43 execution/risk/cost/H20 schedule unchanged.','frontier_reference_return':FRONTIER_RET,'complete_common_schedule':complete,'invalid':INVALID,'robust':robust,'ranking_log':RANKING_LOG,'years':years,'combined':combined,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'One fixed structural ranking hypothesis; no grid, parameter scan, new data, horizon or schedule changes.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
