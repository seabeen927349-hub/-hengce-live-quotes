#!/usr/bin/env python3
from __future__ import annotations
import json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v41_expanding_regime_ic as v41

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v43_expanding_regime_icir_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v43_events.jsonl'
COSTS=(.008,.012,.016);CAP=.50;TOPN=3;ICIR_STABILIZER=.05
V39_REF={'ret':3.382144667539377,'dd':-0.2638974028182084,'rem':1.901878991023918}
V41_REF={'ret':3.2434637773620763,'dd':-0.18593461605119255,'rem':1.8100437842487898}

def weights_at(signal_date,regime):
    y=signal_date[:4]
    prior=[a for a in v41.ANCHORS if a['exit_date']<signal_date and a['regime']==regime]
    stats=[];diag={}
    for f in v41.FACTORS:
        z=[a['ics'][f] for a in prior if a['ics'][f] is not None]
        mu=statistics.mean(z) if z else None;sd=statistics.stdev(z) if len(z)>1 else 0.0
        stat=max(0.0,mu/(sd+ICIR_STABILIZER)) if mu is not None else 0.0
        diag[f]={'n':len(z),'mean_ic':mu,'sd_ic':sd,'icir_stat':stat};stats.append(stat)
    valid=min((diag[f]['n'] for f in v41.FACTORS),default=0)
    if valid<v41.MIN_REGIME_ANCHORS or sum(stats)<=0:
        return list(v41.GLOBAL[y]),diag,prior,True
    s=sum(stats);raw=[x/s for x in stats];w=[v41.SHRINK*v41.BASE[i]+(1-v41.SHRINK)*raw[i] for i in range(5)];z=sum(w)
    return [x/z for x in w],diag,prior,False

def build():
    out=[];invalid=[];prior_sigma=[];weight_log=[]
    for b in sorted(v41.v19.v15.base,key=lambda e:e['signal_date']):
        d=b['signal_date'];si=v41.DI[d];regime=b['regime'];w,diag,prior,fallback=weights_at(d,regime)
        F=v41.v13.features.get(d,{});arr=[(sum(w[i]*vals[i] for i in range(5)),t) for t,vals in F.items()];arr.sort(key=lambda z:(-z[0],z[1]));picks=[t for s,t in arr[:TOPN]]
        weight_log.append({'signal_date':d,'regime':regime,'weights':dict(zip(v41.FACTORS,w)),'prior_regime_anchors':len(prior),'fallback':fallback,'factor_icir':diag})
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
        for k in range(v41.v13.H+1):daily.append([outs[0][3][k][0],sum(wi*o[3][k][1] for wi,o in zip(weights,outs))])
        e={'signal_date':d,'entry_date':outs[0][1],'exit_date':outs[0][2],'tickers':picks,'uncapped_weights':uncapped,'weights':weights,'weight_cap':CAP,'sample_covariance':cov,'shrunk_covariance':shr,'gross_return':gross,'daily':daily,'regime':regime,'breadth20':b['breadth20'],'year':b['year'],'factor_weights':dict(zip(v41.FACTORS,w)),'prior_regime_anchors':len(prior),'ranking_rule':'SIGNAL_TIME_EXPANDING_REGIME_PRIOR_ICIR_SHRINK_0.90'}
        e['exposure']=v41.v19.exposure(e);e['vol_ratio']=v41.v19.vol_ratio(e)
        sig=v41.v30.predicted_sigma(e);q75=v41.v30.quantile(prior_sigma,v41.v30.TAIL_Q) if len(prior_sigma)>=v41.v30.MIN_PRIOR else None;breadth=e.get('breadth20');fragile=(regime=='STRONG' and breadth is not None and v41.v30.BREADTH_LO<=breadth<v41.v30.BREADTH_HI);tail=(q75 is not None and sig>q75 and sig>0);mult=(q75/sig) if fragile and tail else 1.0
        e['predicted_daily_sigma']=sig;e['prior_sigma_q75']=q75;e['fragile_strong']=fragile;e['tail_vol']=tail;e['risk_multiplier']=mult;e['base_exposure']=e['exposure'];e['exposure']=e['base_exposure']*mult
        out.append(e);prior_sigma.append(sig)
    return out,invalid,weight_log

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

EV,INVALID,WEIGHT_LOG=build();complete=(not INVALID and len(EV)==len(v41.v19.v15.base));years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in v41.v13.PERIODS};combined={str(c):summarize(EV,c) for c in COSTS}
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
c=combined['0.012'];dom41=robust and c['compounded_return']>=V41_REF['ret'] and c['max_drawdown']>=V41_REF['dd'] and c['remove_best_basket_return']>=V41_REF['rem'];alpha=robust and c['compounded_return']>V39_REF['ret'] and c['remove_best_basket_return']>V39_REF['rem'] and c['max_drawdown']>=-.30
status='V43_DOMINATES_V41' if dom41 else ('V43_ALPHA_IMPROVEMENT' if alpha else 'V43_DOES_NOT_IMPROVE_FRONTIER')
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'single fixed V43: signal-time expanding prior-only regime-conditioned ICIR factor learning using the original V9 ICIR definition mean_ic/(sd_ic+0.05), positive orientation only, exact 0.90 shrink toward V6. Modern V41 execution/risk stack unchanged.','icir_stabilizer':ICIR_STABILIZER,'shrink_to_v6':v41.SHRINK,'min_regime_anchors':v41.MIN_REGIME_ANCHORS,'weight_log':WEIGHT_LOG,'complete_common_schedule':complete,'invalid':INVALID,'robust':robust,'years':years,'combined':combined,'v39_reference':V39_REF,'v41_reference':V41_REF,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'One pre-existing V9 ICIR method ported into the prior-only V41 structure; no grid, new data, horizon or schedule changes.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
