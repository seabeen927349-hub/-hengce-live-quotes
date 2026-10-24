#!/usr/bin/env python3
from __future__ import annotations
import json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v19_diversification as v19
import research.codex_full_reset_20261023.ranking_v27_capped_covariance as v27

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v28_risk_model_blend_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v28_events.jsonl'
COSTS=(.008,.012,.016)
BLEND=.50
CAP=.50
V19_REF={'ret':2.3394980651997064,'dd':-0.25113023981269567,'rem':1.1916614382781274}
V27_REF={'ret':2.7564277213056774,'dd':-0.25219372871514845,'rem':1.487525974782037,'max_weight':0.5000000000000001}
DI={d:i for i,d in enumerate(v19.v15.v13.dates)}


def build():
    cov_ev,cov_invalid=v27.build(CAP)
    iv_ev,iv_invalid=v19.build_variant(3,'INV_VOL')
    cov={e['signal_date']:e for e in cov_ev};iv={e['signal_date']:e for e in iv_ev}
    invalid=list(cov_invalid)+list(iv_invalid);out=[]
    for b in sorted(v19.v15.base,key=lambda e:e['signal_date']):
        d=b['signal_date'];a=cov.get(d);q=iv.get(d)
        if a is None or q is None:
            invalid.append([d,'MISSING_COMPONENT']);continue
        if a['tickers']!=q['tickers']:
            invalid.append([d,'PICK_MISMATCH']);continue
        raw=[BLEND*x+(1-BLEND)*y for x,y in zip(a['weights'],q['weights'])]
        w=v27.cap_weights(raw,CAP)
        if w is None:
            invalid.append([d,'CAP_PROJECTION_FAILED']);continue
        si=DI[d];outs=[];ok=True
        for t in a['tickers']:
            o=v19.v15.v13.outcome(t,si)
            if o is None:ok=False;break
            outs.append(o)
        if not ok:
            invalid.append([d,'INVALID_OUTCOME']);continue
        gross=sum(wi*o[0] for wi,o in zip(w,outs));daily=[]
        for k in range(v19.v15.v13.H+1):
            dd=outs[0][3][k][0];dr=sum(wi*o[3][k][1] for wi,o in zip(w,outs));daily.append([dd,dr])
        e={'signal_date':d,'entry_date':outs[0][1],'exit_date':outs[0][2],'tickers':a['tickers'],'covariance_cap50_weights':a['weights'],'inverse_vol_weights':q['weights'],'precap_blend_weights':raw,'weights':w,'weight_cap':CAP,'blend_covariance':BLEND,'gross_return':gross,'daily':daily,'regime':b['regime'],'breadth20':b['breadth20'],'year':b['year']}
        e['exposure']=v19.exposure(e);e['vol_ratio']=v19.vol_ratio(e);out.append(e)
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
    return {'baskets':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,'compounded_return':product(nets),'max_drawdown':mdd,'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,'mean_net_return':statistics.mean(nets) if nets else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None,'max_single_name_weight':max((max(e['weights']) for e in events),default=None)}

EV,INVALID=build();complete=(not INVALID and len(EV)==len(v19.v15.base))
years={y:{str(c):summarize([e for e in EV if e['year']==y],c) for c in COSTS} for y in v19.v15.v13.PERIODS}
combined={str(c):summarize(EV,c) for c in COSTS}
robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
c=combined['0.012']
strict_v19=robust and c['compounded_return']>V19_REF['ret'] and c['max_drawdown']>V19_REF['dd'] and c['remove_best_basket_return']>V19_REF['rem'] and c['max_single_name_weight']<=CAP+1e-10
strict_v27=robust and c['compounded_return']>=V27_REF['ret'] and c['max_drawdown']>=V27_REF['dd'] and c['remove_best_basket_return']>=V27_REF['rem'] and c['max_single_name_weight']<=CAP+1e-10
status='V28_DOMINATES_V27' if strict_v27 else ('V28_STRICTLY_DOMINATES_V19' if strict_v19 else 'V28_DOES_NOT_BEAT_V19')
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in EV:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'single fixed risk-model ensemble: 50% frozen V27 cap50 covariance weights + 50% frozen V19 inverse-vol weights, then deterministic 50% hard cap; V19 stock selection, V17 exposure, H20 and schedule unchanged','blend_covariance':BLEND,'weight_cap':CAP,'complete_common_schedule':complete,'invalid':INVALID,'robust':robust,'years':years,'combined':combined,'v19_reference':V19_REF,'v27_reference':V27_REF,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':1,'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'One predeclared 50/50 risk-model blend evaluated on exposed 2024-2026 history; no new data, ranking, schedule or horizon changes.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
