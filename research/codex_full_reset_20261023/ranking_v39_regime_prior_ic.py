#!/usr/bin/env python3
from __future__ import annotations
import json,math,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v13_weak_regime_profiles as v13
import research.codex_full_reset_20261023.ranking_v19_diversification as v19
import research.codex_full_reset_20261023.ranking_v27_capped_covariance as v27
import research.codex_full_reset_20261023.ranking_v30_fragile_strong_risk as v30

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v39_regime_prior_ic_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v39_events.jsonl'
COSTS=(.008,.012,.016);CAP=.50;TOPN=3
FACTORS=('resid_rev','mom20','skip5_60','liquidity','lowvol')
BASE=(.20,.25,.30,.05,.20);SHRINK=.90;MIN_REGIME_ANCHORS=3
TRAIN_END={'2024':'2023-12-31','2025':'2024-12-31','2026':'2025-12-31'}
# Canonical V9 global annual weights are fallback only when a regime lacks enough prior anchors.
GLOBAL={
 '2024':(.21026935533573474,.24955453687572232,.2865882760386327,.07358783174991028,.18000000000000002),
 '2025':(.20159241998850475,.2512249587399482,.2864638040929887,.05990526148737986,.20081355569117848),
 '2026':(.1880651272237035,.25859212409312254,.28170466457881926,.0745153923199833,.19712269178437147),
}
V30_REF={'ret':2.8508800598517157,'dd':-0.25219372871514845,'rem':1.5500728046277374}
V36_REF={'ret':3.1564604706266746,'dd':-0.320100536250974,'rem':1.7524297420116035}
DI={d:i for i,d in enumerate(v13.dates)}


def corr(x,y):
    if len(x)<10:return None
    xb=statistics.mean(x);yb=statistics.mean(y)
    dx=sum((a-xb)**2 for a in x);dy=sum((b-yb)**2 for b in y)
    if dx<=0 or dy<=0:return None
    return sum((a-xb)*(b-yb) for a,b in zip(x,y))/math.sqrt(dx*dy)


def target_rank(d):
    vals={}
    i=DI[d]
    for t in v13.features.get(d,{}):
        o=v13.outcome(t,i)
        if o is not None:vals[t]=o[0]
    return v13.ranks(vals) if vals else {}


def anchors_until(end_date):
    out=[];next_i=-1
    for i,d in enumerate(v13.dates):
        if d<'2023-01-01' or d>end_date or i<next_i or d not in v13.features:continue
        if i+1+v13.H>=len(v13.dates) or v13.dates[i+1+v13.H]>end_date:continue
        out.append(d);next_i=i+v13.H+2
    return out


def learn_regime(year,regime):
    anchors=[d for d in anchors_until(TRAIN_END[year]) if ('STRONG' if v13.breadth[d]>=v13.BREADTH_CUTOFF else 'WEAK')==regime]
    ics={f:[] for f in FACTORS}
    for d in anchors:
        yr=target_rank(d);common=[t for t in v13.features[d] if t in yr]
        if len(common)<20:continue
        for k,f in enumerate(FACTORS):
            ic=corr([v13.features[d][t][k] for t in common],[yr[t] for t in common])
            if ic is not None:ics[f].append(ic)
    valid_anchor_count=min((len(v) for v in ics.values()),default=0)
    diag={f:{'n':len(ics[f]),'mean_ic':statistics.mean(ics[f]) if ics[f] else None} for f in FACTORS}
    if valid_anchor_count<MIN_REGIME_ANCHORS:
        return list(GLOBAL[year]),diag,anchors,True
    stats=[max(0.0,statistics.mean(ics[f])) if ics[f] else 0.0 for f in FACTORS]
    s=sum(stats)
    raw=[x/s for x in stats] if s>0 else list(BASE)
    w=[SHRINK*BASE[i]+(1-SHRINK)*raw[i] for i in range(5)];z=sum(w);w=[x/z for x in w]
    return w,diag,anchors,False

LEARNED={}
for y in v13.PERIODS:
    LEARNED[y]={}
    for regime in ('STRONG','WEAK'):
        w,diag,anchors,fallback=learn_regime(y,regime)
        LEARNED[y][regime]={'final_weights':dict(zip(FACTORS,w)),'factor_ic':diag,'training_anchors':anchors,'training_end':TRAIN_END[y],'fallback_to_global_v9':fallback}


def rank_cache():
    cache={}
    for d,F in v13.features.items():
        y=d[:4]
        if y not in LEARNED:continue
        regime='STRONG' if v13.breadth[d]>=v13.BREADTH_CUTOFF else 'WEAK'
        w=[LEARNED[y][regime]['final_weights'][f] for f in FACTORS]
        arr=[(sum(w[i]*vals[i] for i in range(5)),t) for t,vals in F.items()]
        arr.sort(key=lambda z:(-z[0],z[1]));cache[d]=[t for s,t in arr]
    return cache
CACHE=rank_cache()


def build():
    out=[];invalid=[];prior_sigma=[]
    for b in sorted(v19.v15.base,key=lambda e:e['signal_date']):
        d=b['signal_date'];si=DI[d];picks=CACHE.get(d,[])[:TOPN]
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
        for k in range(v13.H+1):
            daily.append([outs[0][3][k][0],sum(wi*o[3][k][1] for wi,o in zip(weights,outs))])
        regime=b['regime']
        e={'signal_date':d,'entry_date':outs[0][1],'exit_date':outs[0][2],'tickers':picks,'uncapped_weights':uncapped,'weights':weights,'weight_cap':CAP,'sample_covariance':cov,'shrunk_covariance':shr,'gross_return':gross,'daily':daily,'regime':regime,'breadth20':b['breadth20'],'year':b['year'],'factor_weights':LEARNED[b['year']][regime]['final_weights'],'ranking_rule':'REGIME_CONDITIONED_PRIOR_MEAN_IC_SHRINK_0.90'}
        e['exposure']=v19.exposure(e);e['vol_ratio']=v19.vol_ratio(e)
        sig=v30.predicted_sigma(e);q75=v30.quantile(prior_sigma,v30.TAIL_Q) if len(prior_sigma)>=v30.MIN_PRIOR else None
        breadth=e.get('breadth20');fragile=(regime=='STRONG' and breadth is not None and v30.BREADTH_LO<=breadth<v30.BREADTH_HI);tail=(q75 is not None and sig>q75 and sig>0);mult=(q75/sig) if fragile and tail else 1.0
        e['predicted_daily_sigma']=sig;e['prior_sigma_q75']=q75;e['fragile_strong']=fragile;e['tail_vol']=tail;e['risk_multiplier']=mult;e['base_exposure']=e['exposure'];e['exposure']=e['base_exposure']*mult
        out.append(e);prior_sigma.append(sig)
    return out,invalid


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

EV,INVALID=build();complete=(not INVALID and len(EV)==len(v19.v15.base));years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in v13.PERIODS};combined={str(c):summarize(EV,c) for c in COSTS}
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
c=combined['0.012'];dom30=robust and c['compounded_return']>=V30_REF['ret'] and c['max_drawdown']>=V30_REF['dd'] and c['remove_best_basket_return']>=V30_REF['rem'];alpha=robust and c['compounded_return']>V36_REF['ret'] and c['remove_best_basket_return']>V36_REF['rem'] and c['max_drawdown']>=-.35
status='V39_DOMINATES_V30' if dom30 else ('V39_ALPHA_IMPROVEMENT_OVER_V36' if alpha else 'V39_DOES_NOT_IMPROVE_FRONTIER')
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'single fixed V39: annual prior-only MEAN_IC factor learning conditioned by contemporaneously-known STRONG/WEAK breadth regime, with exact V9 champion 0.90 shrink toward V6; minimum 3 prior regime anchors else fallback to canonical annual V9 global weights. Modern Top3/H20/common schedule/cap50 covariance/V19 exposure/V30 fragile-strong overlay unchanged.','shrink_to_v6':SHRINK,'min_regime_anchors':MIN_REGIME_ANCHORS,'learned':LEARNED,'complete_common_schedule':complete,'invalid':INVALID,'robust':robust,'years':years,'combined':combined,'v30_reference':V30_REF,'v36_reference':V36_REF,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'One structural prior-only alpha hypothesis on exposed historical evaluation years; no parameter grid, new data, horizon or schedule changes.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
