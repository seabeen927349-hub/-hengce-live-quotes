#!/usr/bin/env python3
from __future__ import annotations
import json, math, statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v41_expanding_regime_ic as v41

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_x1_shock_propagation_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_x1_events.jsonl'
COSTS=(.008,.012,.016); CAP=.50; TOPN=3; LOOKBACK=60; MIN_EDGE_OBS=30; ZLOOKBACK=20
V43_REF={'ret':3.4265,'dd':-0.1767,'rem':1.9312,'win':0.667,'ret16':3.0649,'rem16':1.6986}
DATES=v41.v13.dates; DI={d:i for i,d in enumerate(DATES)}; BY=v41.v13.by; MKT=v41.v13.mkt

def corr(x,y):
    if len(x)<MIN_EDGE_OBS:return None
    xb=statistics.mean(x);yb=statistics.mean(y)
    dx=sum((a-xb)**2 for a in x);dy=sum((b-yb)**2 for b in y)
    if dx<=1e-18 or dy<=1e-18:return None
    return sum((a-xb)*(b-yb) for a,b in zip(x,y))/math.sqrt(dx*dy)

def resid_at(t,i):
    if i<0 or i>=len(DATES):return None
    d=DATES[i];r=BY[d].get(t);mr=MKT[d].get('r1')
    if r is None or r.r1 is None or r.beta60 is None or mr is None:return None
    return r.r1-r.beta60*mr

def zshock(t,i):
    cur=resid_at(t,i)
    if cur is None:return None
    hist=[]
    for k in range(max(0,i-ZLOOKBACK),i):
        z=resid_at(t,k)
        if z is not None:hist.append(z)
    if len(hist)<10:return None
    mu=statistics.mean(hist);sd=statistics.stdev(hist) if len(hist)>1 else 0.0
    if sd<=1e-12:return 0.0
    return (cur-mu)/sd

def edge(source,target,i):
    xs=[];ys=[]
    for k in range(max(1,i-LOOKBACK),i):
        x=resid_at(source,k-1);y=resid_at(target,k)
        if x is None or y is None:continue
        xs.append(x);ys.append(y)
    c=corr(xs,ys)
    if c is None:return None,len(xs)
    return c*(len(xs)/(len(xs)+MIN_EDGE_OBS)),len(xs)

def propagation_scores(d):
    i=DI[d];eligible=list(v41.v13.features.get(d,{}))
    z={t:zshock(t,i) for t in eligible};z={t:x for t,x in z.items() if x is not None}
    if len(z)<TOPN:return {},{'eligible':len(eligible),'z_available':len(z),'sources':[]}
    ns=max(TOPN,int(math.sqrt(len(z))))
    sources=sorted(z,key=lambda t:(-abs(z[t]),t))[:ns]
    out={};diag={}
    for target in eligible:
        num=0.0;den=0.0;used=0
        for source in sources:
            if source==target:continue
            e,n=edge(source,target,i)
            if e is None:continue
            impulse=math.tanh(z[source])
            num+=e*impulse;den+=abs(e);used+=1
        if den<=1e-12:continue
        pred=num/den;tz=z.get(target,0.0)
        absorbed=(math.copysign(min(abs(pred),abs(tz)),pred) if pred*tz>0 else 0.0)
        gap=pred-absorbed
        out[target]=gap
        diag[target]={'predicted_propagation':pred,'current_target_z':tz,'absorbed_component':absorbed,'gap':gap,'edges_used':used}
    return out,{'eligible':len(eligible),'z_available':len(z),'sources':[{'ticker':t,'z':z[t]} for t in sources],'target_diag':diag}

def build():
    out=[];invalid=[];prior_sigma=[];score_log=[]
    for b in sorted(v41.v19.v15.base,key=lambda e:e['signal_date']):
        d=b['signal_date'];si=DI[d];scores,meta=propagation_scores(d)
        arr=sorted([(s,t) for t,s in scores.items()],key=lambda x:(-x[0],x[1]));picks=[t for s,t in arr[:TOPN]]
        score_log.append({'signal_date':d,'regime':b['regime'],'picks':picks,'top_scores':arr[:10],'graph':meta})
        if len(picks)<TOPN:invalid.append([d,'NOT_ENOUGH_PROPAGATION_PICKS']);continue
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
        e={'signal_date':d,'entry_date':outs[0][1],'exit_date':outs[0][2],'tickers':picks,'uncapped_weights':uncapped,'weights':weights,'weight_cap':CAP,'sample_covariance':cov,'shrunk_covariance':shr,'gross_return':gross,'daily':daily,'regime':b['regime'],'breadth20':b['breadth20'],'year':b['year'],'ranking_rule':'X1_PRIOR_ONLY_RESIDUAL_SHOCK_PROPAGATION_GRAPH','propagation_scores':{t:scores[t] for t in picks}}
        e['exposure']=v41.v19.exposure(e);e['vol_ratio']=v41.v19.vol_ratio(e)
        sig=v41.v30.predicted_sigma(e);q75=v41.v30.quantile(prior_sigma,v41.v30.TAIL_Q) if len(prior_sigma)>=v41.v30.MIN_PRIOR else None
        breadth=e.get('breadth20');fragile=(e['regime']=='STRONG' and breadth is not None and v41.v30.BREADTH_LO<=breadth<v41.v30.BREADTH_HI);tail=(q75 is not None and sig>q75 and sig>0);mult=(q75/sig) if fragile and tail else 1.0
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
status='X1_DOMINATES_V43' if strict else ('X1_ALPHA_IMPROVEMENT' if alpha else 'X1_DOES_NOT_BEAT_V43')
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'X1 structural alpha: prior-only 60-day directed lead-lag graph on idiosyncratic daily residual returns. Current sqrt(N) largest residual shocks are information sources; lagged source->target correlation predicts propagation; already-aligned target shock is subtracted as absorbed information. No V43 factor score enters ranking. H20 common schedule, Top3, cap50 covariance, V17 exposure and V30 fragile-strong overlay unchanged.','lookback':LOOKBACK,'min_edge_obs':MIN_EDGE_OBS,'z_lookback':ZLOOKBACK,'complete_common_schedule':complete,'invalid':INVALID,'robust':robust,'years':years,'combined':combined,'v43_reference':V43_REF,'score_log':SCORE_LOG,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Exposed historical simulation on frozen 2024-2026 evaluation years; graph uses only information available on or before each signal date. No parameter grid or new data.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
