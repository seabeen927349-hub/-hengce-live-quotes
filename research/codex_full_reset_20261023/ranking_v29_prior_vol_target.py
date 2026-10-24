#!/usr/bin/env python3
from __future__ import annotations
import json,math,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v19_diversification as v19
import research.codex_full_reset_20261023.ranking_v27_capped_covariance as v27

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v29_prior_vol_target_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v29_events.jsonl'
COSTS=(.008,.012,.016)
CAP=.50
MIN_PRIOR=3
V19_REF={'ret':2.3394980651997064,'dd':-0.25113023981269567,'rem':1.1916614382781274}
V27_REF={'ret':2.7564277213056774,'dd':-0.25219372871514845,'rem':1.487525974782037,'max_weight':0.5000000000000001}


def predicted_sigma(e):
    w=e['weights'];s=e['shrunk_covariance']
    var=sum(w[i]*s[i][j]*w[j] for i in range(3) for j in range(3))
    return math.sqrt(max(0.0,var))


def build():
    base,invalid=v27.build(CAP);out=[];prior=[]
    for e0 in sorted(base,key=lambda e:e['signal_date']):
        e=dict(e0);sig=predicted_sigma(e);ref=statistics.median(prior) if len(prior)>=MIN_PRIOR else None
        mult=1.0 if ref is None or sig<=0 else min(1.0,ref/sig)
        e['predicted_daily_sigma']=sig;e['prior_sigma_median']=ref;e['vol_target_multiplier']=mult
        e['base_exposure']=e['exposure'];e['exposure']=e['base_exposure']*mult
        out.append(e);prior.append(sig)
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
    return {'baskets':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,'compounded_return':product(nets),'max_drawdown':mdd,'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,'mean_net_return':statistics.mean(nets) if nets else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None,'max_single_name_weight':max((max(e['weights']) for e in events),default=None),'min_exposure':min((e['exposure'] for e in events),default=None),'mean_exposure':statistics.mean([e['exposure'] for e in events]) if events else None}

EV,INVALID=build();complete=(not INVALID and len(EV)==len(v19.v15.base))
years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in v19.v15.v13.PERIODS}
combined={str(c):summarize(EV,c) for c in COSTS}
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
c=combined['0.012']
strict_v19=robust and c['compounded_return']>V19_REF['ret'] and c['max_drawdown']>V19_REF['dd'] and c['remove_best_basket_return']>V19_REF['rem'] and c['max_single_name_weight']<=CAP+1e-10
strict_v27=robust and c['compounded_return']>=V27_REF['ret'] and c['max_drawdown']>=V27_REF['dd'] and c['remove_best_basket_return']>=V27_REF['rem']
status='V29_DOMINATES_V27' if strict_v27 else ('V29_STRICTLY_DOMINATES_V19' if strict_v19 else 'V29_DOES_NOT_BEAT_V19')
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'single prior-only volatility target on frozen V27 cap50 baskets: predicted daily sigma from signal-time shrunk covariance; after 3 prior baskets, scale exposure by min(1, expanding-prior median sigma/current sigma); no outcome-dependent gate; V19 selection, V17 base exposure, H20 and schedule unchanged','weight_cap':CAP,'min_prior_sigma_observations':MIN_PRIOR,'complete_common_schedule':complete,'invalid':INVALID,'robust':robust,'years':years,'combined':combined,'v19_reference':V19_REF,'v27_reference':V27_REF,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'One structural prior-only exposure rule on exposed 2024-2026 history. Threshold is the expanding median of signal-time predicted portfolio volatility; no new data and no return-based tuning.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
