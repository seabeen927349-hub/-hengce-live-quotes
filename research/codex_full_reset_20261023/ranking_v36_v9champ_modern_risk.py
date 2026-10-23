#!/usr/bin/env python3
from __future__ import annotations
import json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v9_walkforward_ic as v9
import research.codex_full_reset_20261023.ranking_v13_weak_regime_profiles as v13
import research.codex_full_reset_20261023.ranking_v19_diversification as v19
import research.codex_full_reset_20261023.ranking_v27_capped_covariance as v27
import research.codex_full_reset_20261023.ranking_v30_fragile_strong_risk as v30

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v36_v9champ_modern_risk_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v36_events.jsonl'
COSTS=(.008,.012,.016)
CAP=.50
TOPN=3
METHOD='MEAN_IC'
SHRINK=.90
V30_REF={'ret':2.8508800598517157,'dd':-0.25219372871514845,'rem':1.5500728046277374,'max_weight':0.5000000000000001}
V32_REF={'ret':2.513405145180079,'dd':-0.17014957723452873,'rem':1.326595160875482}
V33_REF={'ret':2.47212917645407,'dd':-0.1624723468868463,'rem':1.2992619997027308}
DI={d:i for i,d in enumerate(v13.dates)}

LEARNED={}
for y in v13.PERIODS:
    w,raw,diag,anchors=v9.yearly_weights(y,METHOD,SHRINK)
    LEARNED[y]={
      'final_weights':dict(zip(v9.FACTORS,w)),
      'raw_learned_weights':dict(zip(v9.FACTORS,raw)),
      'factor_ic':diag,
      'training_anchors':anchors,
      'training_end':v9.TRAIN_END[y],
    }


def rank_cache():
    cache={}
    for d,F in v13.features.items():
        y=d[:4]
        if y not in LEARNED:continue
        w=[LEARNED[y]['final_weights'][f] for f in v9.FACTORS]
        arr=[]
        for t,vals in F.items():
            arr.append((sum(w[i]*vals[i] for i in range(5)),t))
        arr.sort(key=lambda z:(-z[0],z[1]))
        cache[d]=[t for s,t in arr]
    return cache

CACHE=rank_cache()


def build():
    out=[];invalid=[];prior_sigma=[]
    # Preserve the modern common signal schedule from V19/V30; only stock ranking changes.
    for b in sorted(v19.v15.base,key=lambda e:e['signal_date']):
        d=b['signal_date'];si=DI[d];picks=CACHE.get(d,[])[:TOPN]
        if len(picks)<TOPN:
            invalid.append([d,'NOT_ENOUGH_PICKS']);continue
        cw=v27.uncapped_cov_weights(d,picks)
        if cw is None:
            invalid.append([d,'COVARIANCE_UNAVAILABLE']);continue
        uncapped,cov,shr=cw;weights=v27.cap_weights(uncapped,CAP)
        if weights is None:
            invalid.append([d,'CAP_PROJECTION_FAILED']);continue
        outs=[];ok=True
        for t in picks:
            o=v13.outcome(t,si)
            if o is None:ok=False;break
            outs.append(o)
        if not ok:
            invalid.append([d,'INVALID_OUTCOME']);continue
        gross=sum(wi*o[0] for wi,o in zip(weights,outs));daily=[]
        for k in range(v13.H+1):
            dd=outs[0][3][k][0]
            dr=sum(wi*o[3][k][1] for wi,o in zip(weights,outs))
            daily.append([dd,dr])
        e={
          'signal_date':d,'entry_date':outs[0][1],'exit_date':outs[0][2],
          'tickers':picks,'uncapped_weights':uncapped,'weights':weights,'weight_cap':CAP,
          'sample_covariance':cov,'shrunk_covariance':shr,'gross_return':gross,'daily':daily,
          'regime':b['regime'],'breadth20':b['breadth20'],'year':b['year'],
          'factor_weights':LEARNED[b['year']]['final_weights'],
          'ranking_rule':'V9_CHAMPION_MEAN_IC_SHRINK_0.90',
        }
        # Modern exposure/diversification layer.
        e['exposure']=v19.exposure(e);e['vol_ratio']=v19.vol_ratio(e)
        # Recompute V30 fragile-strong overlay from THIS V36 basket series only.
        sig=v30.predicted_sigma(e)
        q75=v30.quantile(prior_sigma,v30.TAIL_Q) if len(prior_sigma)>=v30.MIN_PRIOR else None
        breadth=e.get('breadth20')
        fragile=(e['regime']=='STRONG' and breadth is not None and v30.BREADTH_LO<=breadth<v30.BREADTH_HI)
        tail=(q75 is not None and sig>q75 and sig>0)
        mult=(q75/sig) if fragile and tail else 1.0
        e['predicted_daily_sigma']=sig;e['prior_sigma_q75']=q75;e['fragile_strong']=fragile;e['tail_vol']=tail;e['risk_multiplier']=mult
        e['base_exposure']=e['exposure'];e['exposure']=e['base_exposure']*mult
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
    return {
      'baskets':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,
      'compounded_return':product(nets),'max_drawdown':mdd,
      'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,
      'mean_net_return':statistics.mean(nets) if nets else None,
      'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None,
      'max_single_name_weight':max((max(e['weights']) for e in events),default=None),
      'mean_exposure':statistics.mean([e['exposure'] for e in events]) if events else None,
      'scaled_baskets':sum(e['risk_multiplier']<1-1e-12 for e in events),
    }

EV,INVALID=build();complete=(not INVALID and len(EV)==len(v19.v15.base))
years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in v13.PERIODS}
combined={str(c):summarize(EV,c) for c in COSTS}
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
c=combined['0.012']
dom_v30=robust and c['compounded_return']>=V30_REF['ret'] and c['max_drawdown']>=V30_REF['dd'] and c['remove_best_basket_return']>=V30_REF['rem'] and (c['compounded_return']>V30_REF['ret'] or c['max_drawdown']>V30_REF['dd'] or c['remove_best_basket_return']>V30_REF['rem'])
alpha=robust and c['compounded_return']>V30_REF['ret'] and c['remove_best_basket_return']>V30_REF['rem'] and c['max_drawdown']>=-.30
balance=robust and c['compounded_return']>V32_REF['ret'] and c['max_drawdown']>V32_REF['dd'] and c['remove_best_basket_return']>V32_REF['rem']
status='V36_DOMINATES_V30' if dom_v30 else ('V36_ALPHA_IMPROVEMENT' if alpha else ('V36_NEW_BALANCE_FRONTIER' if balance else 'V36_DOES_NOT_IMPROVE_FRONTIER'))
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
base_by_date={e['signal_date']:e for e in v30.EV}
changed=sum(a!=b for e in EV for a,b in zip(base_by_date[e['signal_date']]['tickers'],e['tickers']))
res={
 'status':status,
 'method':'single fixed port of the exact historical V9 champion (annual prior-only MEAN_IC factor learning with 0.90 shrink toward V6) into the modern risk stack: same common schedule/Top3/H20/turnover eligibility, 50% capped covariance weights, V19 exposure, and V30 fragile-strong prior-vol overlay recomputed on V36 baskets.',
 'v9_champion':{'method':METHOD,'shrink_to_v6':SHRINK},
 'learned':LEARNED,
 'complete_common_schedule':complete,'invalid':INVALID,'robust':robust,
 'years':years,'combined':combined,
 'v30_reference':V30_REF,'v32_reference':V32_REF,'v33_reference':V33_REF,
 'changed_ticker_slots_vs_v30':changed,
 'events_file':str(EVENTS.relative_to(ROOT)),
 'new_model_evaluations':1,
 'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},
 'caveat':'Exact V9 champion was selected on exposed history in the earlier 8-method screen; V36 is one fixed structural port, not a resweep or pristine OOS test. No new data or production authority.'
}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(res,ensure_ascii=False,indent=2))
