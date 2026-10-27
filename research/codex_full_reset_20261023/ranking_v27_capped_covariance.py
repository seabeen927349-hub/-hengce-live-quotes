#!/usr/bin/env python3
from __future__ import annotations
import json,statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v19_diversification as v19

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v27_capped_covariance_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v27_champion_events.jsonl'
COSTS=(.008,.012,.016)
CAPS=(.40,.50)
SHRINK=.50
V19_REF={'ret':2.3394980651997064,'dd':-0.25113023981269567,'rem':1.1916614382781274}
V26_REF={'ret':2.5648849745572893,'dd':-0.22966756926145038,'rem':1.3606853716432386,'max_weight':0.9308168675163553}
DATES=v19.v15.v13.dates;DI={d:i for i,d in enumerate(DATES)};BY=v19.v15.v13.by


def invert3(a):
    m=[list(map(float,row))+[1.0 if i==j else 0.0 for j in range(3)] for i,row in enumerate(a)]
    for c in range(3):
        piv=max(range(c,3),key=lambda r:abs(m[r][c]))
        if abs(m[piv][c])<1e-14:return None
        m[c],m[piv]=m[piv],m[c]
        q=m[c][c];m[c]=[x/q for x in m[c]]
        for r in range(3):
            if r==c:continue
            f=m[r][c];m[r]=[x-f*y for x,y in zip(m[r],m[c])]
    return [row[3:] for row in m]


def uncapped_cov_weights(d,picks):
    i=DI[d];series=[]
    for t in picks:
        vals=[]
        for j in range(i-19,i+1):
            if j<0:return None
            r=BY[DATES[j]].get(t)
            if r is None or r.r1 is None:return None
            vals.append(r.r1)
        series.append(vals)
    means=[statistics.mean(x) for x in series]
    cov=[[sum((series[a][k]-means[a])*(series[b][k]-means[b]) for k in range(20))/19 for b in range(3)] for a in range(3)]
    shr=[[cov[a][b]*((1-SHRINK) if a!=b else 1.0) for b in range(3)] for a in range(3)]
    inv=invert3(shr)
    if inv is None:return None
    raw=[max(0.0,sum(inv[i][j] for j in range(3))) for i in range(3)]
    if sum(raw)<=1e-14:return None
    s=sum(raw);return [x/s for x in raw],cov,shr


def cap_weights(w,cap):
    # Deterministic capped-simplex redistribution, preserving relative weight among uncapped names.
    w=[max(0.0,float(x)) for x in w]
    s=sum(w)
    if s<=0:return None
    w=[x/s for x in w]
    for _ in range(12):
        over=[i for i,x in enumerate(w) if x>cap+1e-14]
        if not over:break
        excess=sum(w[i]-cap for i in over)
        for i in over:w[i]=cap
        free=[i for i,x in enumerate(w) if i not in over and x<cap-1e-14]
        if not free:
            return None
        base=sum(w[i] for i in free)
        if base<=1e-14:
            add=excess/len(free)
            for i in free:w[i]+=add
        else:
            for i in free:w[i]+=excess*w[i]/base
    s=sum(w)
    if s<=0:return None
    w=[x/s for x in w]
    if max(w)>cap+1e-10:return None
    return w


def build(cap):
    out=[];invalid=[]
    for b in sorted(v19.v15.base,key=lambda e:e['signal_date']):
        d=b['signal_date'];si=DI[d];picks=v19.cache.get(d,[])[:3]
        if len(picks)<3:
            invalid.append([d,'NOT_ENOUGH_PICKS']);continue
        cw=uncapped_cov_weights(d,picks)
        if cw is None:
            invalid.append([d,'COVARIANCE_UNAVAILABLE']);continue
        uncapped,cov,shr=cw;w=cap_weights(uncapped,cap)
        if w is None:
            invalid.append([d,'CAP_PROJECTION_FAILED']);continue
        outs=[];ok=True
        for t in picks:
            o=v19.v15.v13.outcome(t,si)
            if o is None:ok=False;break
            outs.append(o)
        if not ok:
            invalid.append([d,'INVALID_OUTCOME']);continue
        gross=sum(wi*o[0] for wi,o in zip(w,outs));daily=[]
        for k in range(v19.v15.v13.H+1):
            dd=outs[0][3][k][0];dr=sum(wi*o[3][k][1] for wi,o in zip(w,outs));daily.append([dd,dr])
        e={'signal_date':d,'entry_date':outs[0][1],'exit_date':outs[0][2],'tickers':picks,'uncapped_weights':uncapped,'weights':w,'weight_cap':cap,'sample_covariance':cov,'shrunk_covariance':shr,'gross_return':gross,'daily':daily,'regime':b['regime'],'breadth20':b['breadth20'],'year':b['year']}
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

results=[]
for cap in CAPS:
    ev,invalid=build(cap);complete=(not invalid and len(ev)==len(v19.v15.base))
    years={y:{str(c):summarize([e for e in ev if e['year']==y],c) for c in COSTS} for y in v19.v15.v13.PERIODS}
    combined={str(c):summarize(ev,c) for c in COSTS}
    robust=complete and all(years[y]['0.012']['compounded_return']>0 and years[y]['0.012']['remove_best_basket_return']>0 for y in years) and all(years[y]['0.016']['compounded_return']>0 for y in years)
    c=combined['0.012']
    dominates_v19=robust and c['compounded_return']>V19_REF['ret'] and c['max_drawdown']>V19_REF['dd'] and c['remove_best_basket_return']>V19_REF['rem'] and c['max_single_name_weight']<=cap+1e-10
    results.append({'cap':cap,'complete_common_schedule':complete,'invalid':invalid,'robust':robust,'dominates_v19':dominates_v19,'years':years,'combined':combined,'events':ev})

# Finite predeclared comparison: among robust capped candidates, maximize 1.2% return; DD/remove-best are reported and V19 dominance is mandatory for upgrade.
pool=[r for r in results if r['robust'] and r['dominates_v19']] or [r for r in results if r['robust']] or results
pool.sort(key=lambda r:(r['combined']['0.012']['compounded_return'],r['combined']['0.012']['max_drawdown'],r['combined']['0.012']['remove_best_basket_return']),reverse=True)
champ=pool[0];c=champ['combined']['0.012']
strict=champ['dominates_v19']
beats_v26_quality=champ['robust'] and c['max_single_name_weight']<=.50+1e-10 and c['compounded_return']>=V26_REF['ret'] and c['max_drawdown']>=V26_REF['dd'] and c['remove_best_basket_return']>=V26_REF['rem']
status='V27_STRICTLY_DOMINATES_V19_WITH_CAP' if strict else 'V27_DOES_NOT_BEAT_V19'
if beats_v26_quality:status='V27_DOMINATES_V26_WITH_CAP'
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in champ['events']:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
clean=[]
for r in results:
    q=dict(r);q.pop('events',None);clean.append(q)
champ_clean=dict(champ);champ_clean.pop('events',None)
res={'status':status,'method':'finite V27: frozen V26 50%-diagonal-shrink covariance weights projected to hard 40% or 50% single-name caps; V19 selection, V17 exposure, H20 and schedule unchanged','caps':CAPS,'shrinkage_to_diagonal':SHRINK,'v19_reference':V19_REF,'v26_reference':V26_REF,'champion':champ_clean,'all_results':clean,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':len(CAPS),'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Only two predeclared caps (40%,50%) evaluated on exposed 2024-2026 history; no new data and no ranking/schedule changes.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
