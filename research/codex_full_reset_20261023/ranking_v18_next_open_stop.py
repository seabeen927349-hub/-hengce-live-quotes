#!/usr/bin/env python3
from __future__ import annotations
import json, statistics
from pathlib import Path
import research.codex_full_reset_20261023.ranking_v15_state_exposure as v15

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v18_next_open_stop_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v18_champion_events.jsonl'
COSTS=(.008,.012,.016)
THRESHOLDS=(None,-.08,-.10,-.12,-.15,-.20)
V17_REF={'ret':2.1215791589270894,'dd':-0.28720698410951295,'rem':1.031059124000596}

def clip(x,lo,hi): return max(lo,min(hi,x))

def vol_ratio(e):
    s=e.get('state') or v15.state(e); a=s.get('median_vol20'); b=s.get('prior60_median_vol20')
    return a/b if a is not None and b not in (None,0) else 1.0

def v17_exposure(e):
    r=vol_ratio(e)
    if e['regime']=='STRONG': return .95 if r>1.10 else 1.0
    return clip(.60/r,.25,1.0)

DATE_INDEX={d:i for i,d in enumerate(v15.v13.dates)}

def apply_stop(e,thr):
    z=dict(e); z['base_exposure']=v17_exposure(e); z['stop_threshold']=thr
    if thr is None:
        z['effective_gross_return']=e['gross_return']; z['effective_path']=list(e['daily']); z['stop_triggered']=False
        return z
    daily=e['daily']
    for k,(d,r) in enumerate(daily[:-1]):
        if r<=thr:
            i=DATE_INDEX[d]
            if i+1>=len(v15.v13.dates): return None
            nd=v15.v13.dates[i+1]
            rets=[]
            for t in e['tickers']:
                entry=v15.v13.by[e['entry_date']].get(t); ex=v15.v13.by[nd].get(t)
                if entry is None or ex is None or entry.o is None or ex.o is None or entry.o<=0 or ex.o<=0: return None
                rets.append(ex.o/entry.o-1)
            gr=statistics.mean(rets)
            # Mark-to-market through trigger close, then terminal next-open liquidation point.
            path=[list(x) for x in daily[:k+1]]+[[nd,gr]]
            z['effective_gross_return']=gr; z['effective_path']=path; z['stop_triggered']=True; z['stop_trigger_date']=d; z['stop_exit_date']=nd
            return z
    z['effective_gross_return']=e['gross_return']; z['effective_path']=list(daily); z['stop_triggered']=False
    return z

def product(xs):
    n=1.
    for x in xs:n*=1+x
    return n-1

def summarize(events,cost,thr,emit=False):
    proc=[]
    for e in events:
        q=apply_stop(e,thr)
        if q is None:return None
        proc.append(q)
    nets=[];nav=1.;peak=1.;mdd=0.;out=[]
    for q in proc:
        ex=q['base_exposure'];net=ex*(q['effective_gross_return']-cost);nets.append(net);b=nav
        path=q['effective_path']
        for j,(d,r) in enumerate(path):
            temp=b*(1+ex*r-(ex*cost if j==len(path)-1 else 0));peak=max(peak,temp);mdd=min(mdd,temp/peak-1)
        nav=b*(1+net)
        if emit:
            q=dict(q);q['scaled_net_return']=net;out.append(q)
    bi=max(range(len(nets)),key=lambda k:nets[k]) if nets else None
    m={'baskets':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,'compounded_return':product(nets),'max_drawdown':mdd,'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,'mean_net_return':statistics.mean(nets) if nets else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None,'stops':sum(q['stop_triggered'] for q in proc)}
    if emit:m['events']=out
    return m

results=[]
for thr in THRESHOLDS:
    years={};valid=True
    for y in v15.v13.PERIODS:
        years[y]={}
        yy=[e for e in v15.base if e['year']==y]
        for c in COSTS:
            m=summarize(yy,c,thr)
            if m is None:valid=False;break
            years[y][str(c)]=m
        if not valid:break
    if not valid:
        results.append({'threshold':thr,'valid':False});continue
    combined={str(c):summarize(v15.base,c,thr) for c in COSTS}
    m12=[years[y]['0.012'] for y in v15.v13.PERIODS];m16=[years[y]['0.016'] for y in v15.v13.PERIODS]
    worst=min(x['compounded_return'] for x in m12);worst16=min(x['compounded_return'] for x in m16);minrem=min(x['remove_best_basket_return'] for x in m12);worstdd=min(x['max_drawdown'] for x in m12)
    robust=worst>0 and worst16>0 and minrem>0
    c12=combined['0.012']; calmar=c12['compounded_return']/abs(c12['max_drawdown']) if c12['max_drawdown']<0 else 999
    # Prefer Pareto risk/return, not raw return alone.
    obj=.55*c12['compounded_return']+1.8*c12['max_drawdown']+.9*c12['remove_best_basket_return']+1.2*worst+1.0*worstdd+.15*worst16+.10*calmar
    results.append({'threshold':thr,'valid':True,'years':years,'combined':combined,'robust':robust,'worst_year_return_012':worst,'worst_year_return_016':worst16,'min_remove_best_012':minrem,'worst_year_maxdd_012':worstdd,'calmar_like':calmar,'objective':obj})

pool=[r for r in results if r.get('valid') and r.get('robust')] or [r for r in results if r.get('valid')]
pool.sort(key=lambda r:(r['objective'],r['calmar_like'],r['combined']['0.012']['compounded_return']),reverse=True)
champ=pool[0]
cm=summarize(v15.base,.012,champ['threshold'],True)
with EVENTS.open('w',encoding='utf-8') as fh:
    for e in cm['events']:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
c=champ['combined']['0.012']
strict=champ['robust'] and c['compounded_return']>V17_REF['ret'] and c['max_drawdown']>V17_REF['dd'] and c['remove_best_basket_return']>V17_REF['rem']
risk=champ['robust'] and c['max_drawdown']>=-.25 and c['compounded_return']>=1.80 and c['remove_best_basket_return']>=.90
status='V18_STRICTLY_DOMINATES_V17' if strict else ('V18_MATERIAL_RISK_IMPROVEMENT' if risk else 'V18_DOES_NOT_BEAT_V17')
res={'status':status,'method':'frozen V17 signal/exposure; basket close threshold triggers full exit at next trading-session open; original non-overlap signal schedule remains frozen and cash stays idle until next scheduled basket','thresholds':THRESHOLDS,'v17_reference':V17_REF,'champion':champ,'all_results':results,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':len(THRESHOLDS),'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Thresholds screened on exposed 2024-2026 history. Trigger uses only end-of-day basket close return; liquidation uses next-session open to avoid same-close lookahead. Early exit does not create extra signals.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
