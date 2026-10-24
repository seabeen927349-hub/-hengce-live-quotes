#!/usr/bin/env python3
from __future__ import annotations
import json,math,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v13_weak_regime_profiles as v13
import research.codex_full_reset_20261023.ranking_v19_diversification as v19
import research.codex_full_reset_20261023.ranking_v27_capped_covariance as v27
import research.codex_full_reset_20261023.ranking_v30_fragile_strong_risk as v30

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v41_expanding_regime_ic_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v41_events.jsonl'
COSTS=(.008,.012,.016);CAP=.50;TOPN=3
FACTORS=('resid_rev','mom20','skip5_60','liquidity','lowvol')
BASE=(.20,.25,.30,.05,.20);SHRINK=.90;MIN_REGIME_ANCHORS=3
GLOBAL={
 '2024':(.21026935533573474,.24955453687572232,.2865882760386327,.07358783174991028,.18000000000000002),
 '2025':(.20159241998850475,.2512249587399482,.2864638040929887,.05990526148737986,.20081355569117848),
 '2026':(.1880651272237035,.25859212409312254,.28170466457881926,.0745153923199833,.19712269178437147),
}
V39_REF={'ret':3.382144667539377,'dd':-0.2638974028182084,'rem':1.901878991023918}
V40_REF={'ret':2.898849351073437,'dd':-0.19583905838470095,'rem':1.5818383187701044}
DI={d:i for i,d in enumerate(v13.dates)}


def corr(x,y):
    if len(x)<10:return None
    xb=statistics.mean(x);yb=statistics.mean(y);dx=sum((a-xb)**2 for a in x);dy=sum((b-yb)**2 for b in y)
    if dx<=0 or dy<=0:return None
    return sum((a-xb)*(b-yb) for a,b in zip(x,y))/math.sqrt(dx*dy)

def target_rank(d):
    vals={};i=DI[d]
    for t in v13.features.get(d,{}):
        o=v13.outcome(t,i)
        if o is not None:vals[t]=o[0]
    return v13.ranks(vals) if vals else {}

# Precompute the same non-overlapping H20 training anchors used by V9, with each label's realization date.
ANCHORS=[];next_i=-1
for i,d in enumerate(v13.dates):
    if d<'2023-01-01' or i<next_i or d not in v13.features:continue
    xi=i+1+v13.H
    if xi>=len(v13.dates):break
    exit_date=v13.dates[xi]
    yr=target_rank(d);common=[t for t in v13.features[d] if t in yr]
    if len(common)>=20:
        ics={}
        for k,f in enumerate(FACTORS):
            ics[f]=corr([v13.features[d][t][k] for t in common],[yr[t] for t in common])
        regime='STRONG' if v13.breadth[d]>=v13.BREADTH_CUTOFF else 'WEAK'
        ANCHORS.append({'signal_date':d,'exit_date':exit_date,'regime':regime,'ics':ics})
    next_i=i+v13.H+2

def weights_at(signal_date,regime):
    y=signal_date[:4]
    prior=[a for a in ANCHORS if a['exit_date']<signal_date and a['regime']==regime]
    vals=[];diag={}
    for f in FACTORS:
        z=[a['ics'][f] for a in prior if a['ics'][f] is not None]
        mu=statistics.mean(z) if z else None
        diag[f]={'n':len(z),'mean_ic':mu}
        vals.append(max(0.0,mu) if mu is not None else 0.0)
    valid=min((diag[f]['n'] for f in FACTORS),default=0)
    if valid<MIN_REGIME_ANCHORS or sum(vals)<=0:
        return list(GLOBAL[y]),diag,prior,True
    s=sum(vals);raw=[x/s for x in vals];w=[SHRINK*BASE[i]+(1-SHRINK)*raw[i] for i in range(5)];z=sum(w)
    return [x/z for x in w],diag,prior,False

def build():
    out=[];invalid=[];prior_sigma=[];weight_log=[]
    for b in sorted(v19.v15.base,key=lambda e:e['signal_date']):
        d=b['signal_date'];si=DI[d];regime=b['regime'];w,diag,prior,fallback=weights_at(d,regime)
        F=v13.features.get(d,{})
        arr=[(sum(w[i]*vals[i] for i in range(5)),t) for t,vals in F.items()];arr.sort(key=lambda z:(-z[0],z[1]));picks=[t for s,t in arr[:TOPN]]
        weight_log.append({'signal_date':d,'regime':regime,'weights':dict(zip(FACTORS,w)),'prior_regime_anchors':len(prior),'fallback':fallback,'factor_ic':diag})
        if len(picks)<TOPN:invalid.append([d,'NOT_ENOUGH_PICKS']);continue
        cw=v27.uncapped_cov_weights(d,picks)
        if cw is None:invalid.append([d,'COVARIANCE_UNAVAILABLE']);continue
        uncapped,cov,shr=cw;weights=v27.cap_weights(uncapped,CAP)
        if weights is None:invalid.append([d,'CAP_PROJECTION_FAILED']);continue
        outs=[];ok=True
        for t in picks:
            o=v13.outcome(t,si)
            if o is None:ok=False;break
            outs.append(o)
        if not ok:invalid.append([d,'INVALID_OUTCOME']);continue
        gross=sum(wi*o[0] for wi,o in zip(weights,outs));daily=[]
        for k in range(v13.H+1):daily.append([outs[0][3][k][0],sum(wi*o[3][k][1] for wi,o in zip(weights,outs))])
        e={'signal_date':d,'entry_date':outs[0][1],'exit_date':outs[0][2],'tickers':picks,'uncapped_weights':uncapped,'weights':weights,'weight_cap':CAP,'sample_covariance':cov,'shrunk_covariance':shr,'gross_return':gross,'daily':daily,'regime':regime,'breadth20':b['breadth20'],'year':b['year'],'factor_weights':dict(zip(FACTORS,w)),'prior_regime_anchors':len(prior),'ranking_rule':'SIGNAL_TIME_EXPANDING_REGIME_PRIOR_MEAN_IC_SHRINK_0.90'}
        e['exposure']=v19.exposure(e);e['vol_ratio']=v19.vol_ratio(e)
        sig=v30.predicted_sigma(e);q75=v30.quantile(prior_sigma,v30.TAIL_Q) if len(prior_sigma)>=v30.MIN_PRIOR else None;breadth=e.get('breadth20');fragile=(regime=='STRONG' and breadth is not None and v30.BREADTH_LO<=breadth<v30.BREADTH_HI);tail=(q75 is not None and sig>q75 and sig>0);mult=(q75/sig) if fragile and tail else 1.0
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

EV,INVALID,WEIGHT_LOG=build();complete=(not INVALID and len(EV)==len(v19.v15.base));years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in v13.PERIODS};combined={str(c):summarize(EV,c) for c in COSTS}
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
c=combined['0.012'];dom39=robust and c['compounded_return']>=V39_REF['ret'] and c['max_drawdown']>=V39_REF['dd'] and c['remove_best_basket_return']>=V39_REF['rem'];alpha=robust and c['compounded_return']>V39_REF['ret'] and c['remove_best_basket_return']>V39_REF['rem'] and c['max_drawdown']>=-.30
status='V41_DOMINATES_V39' if dom39 else ('V41_ALPHA_IMPROVEMENT' if alpha else 'V41_DOES_NOT_IMPROVE_FRONTIER')
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'single fixed V41: signal-time expanding prior-only regime-conditioned MEAN_IC factor learning with exact V9 0.90 shrink toward V6. Only H20 anchors whose outcomes are fully realized before each signal are usable. Minimum 3 same-regime anchors else canonical annual V9 global fallback. Modern V39 execution/risk stack unchanged.','shrink_to_v6':SHRINK,'min_regime_anchors':MIN_REGIME_ANCHORS,'training_anchor_count':len(ANCHORS),'weight_log':WEIGHT_LOG,'complete_common_schedule':complete,'invalid':INVALID,'robust':robust,'years':years,'combined':combined,'v39_reference':V39_REF,'v40_reference':V40_REF,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'One prior-only structural alpha hypothesis on exposed evaluation years; no grid, new data, horizon or schedule changes.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
