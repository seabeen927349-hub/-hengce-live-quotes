#!/usr/bin/env python3
from __future__ import annotations
import runpy,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'research/codex_full_reset_20261023/ranking_v13_weak_regime_profiles.py'
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v15_liqtrend_weak075_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v15_events.jsonl'
ns=runpy.run_path(str(BASE))
features=ns['features'];breadth=ns['breadth'];V6=tuple(ns['V6']);CUT=ns['BREADTH_CUTOFF'];PERIODS=ns['PERIODS'];COSTS=ns['COSTS'];simulate=ns['simulate']
STRONG=(.10,.25,.35,.15,.15) # V14 LIQ_TREND
WEAK=V6
WEAK_EXPOSURE=.75
TOPN=3;H=20;TURNMIN=20_000_000.
V6_REF={'combined_return_012':2.502731886924238,'combined_maxdd_012':-0.40608721504832834,'combined_remove_best_012':1.2379}

def make_cache():
 cache={}
 for d,F in features.items():
  w=STRONG if breadth[d]>=CUT else WEAK
  arr=[(sum(w[i]*v[i] for i in range(5)),t) for t,v in F.items()]
  arr.sort(key=lambda z:(-z[0],z[1]));cache[d]=[t for s,t in arr]
 return cache

def exposure(e):return 1.0 if e['regime']=='STRONG' else WEAK_EXPOSURE

def summarize(ev,cost):
 nets=[];nav=1.;peak=1.;mdd=0.
 for e in ev:
  x=exposure(e);net=x*(e['gross_return']-cost);nets.append(net);base=nav
  for j,(d,r) in enumerate(e['daily']):
   temp=base*(1+x*r-(x*cost if j==len(e['daily'])-1 else 0));peak=max(peak,temp);mdd=min(mdd,temp/peak-1)
  nav=base*(1+net)
 bi=max(range(len(nets)),key=lambda k:nets[k]) if nets else None
 def prod(a):
  z=1.
  for q in a:z*=1+q
  return z-1
 return {'baskets':len(nets),'wins':sum(q>0 for q in nets),'win_rate':sum(q>0 for q in nets)/len(nets) if nets else None,'compounded_return':prod(nets),'max_drawdown':mdd,'remove_best_basket_return':prod([q for k,q in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None}

cache=make_cache();years={};all_ev=[];cens=0
for y,(s,e) in PERIODS.items():
 ev,c=simulate(cache,s,e);cens+=c
 for x in ev:x['year']=y;x['exposure']=exposure(x)
 all_ev.extend(ev);years[y]={str(cost):summarize(ev,cost) for cost in COSTS}
combined={str(cost):summarize(sorted(all_ev,key=lambda z:z['signal_date']),cost) for cost in COSTS}
m12=[years[y]['0.012'] for y in PERIODS];m16=[years[y]['0.016'] for y in PERIODS]
robust=all(x['baskets']>=7 and x['compounded_return']>0 and x['remove_best_basket_return']>0 for x in m12) and all(x['compounded_return']>0 for x in m16)
cr=combined['0.012']['compounded_return'];cd=combined['0.012']['max_drawdown'];rb=combined['0.012']['remove_best_basket_return']
strict_dom=robust and cr>V6_REF['combined_return_012'] and cd>V6_REF['combined_maxdd_012'] and rb>V6_REF['combined_remove_best_012']
status='V15_STRICTLY_DOMINATES_V6' if strict_dom else 'V15_DOES_NOT_STRICTLY_DOMINATE_V6'
with EVENTS.open('w',encoding='utf-8') as fh:
 for e in all_ev:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'fixed V14 LIQ_TREND ranking in strong breadth; frozen V6 ranking at 75% exposure in weak breadth','fixed':{'breadth_cutoff':CUT,'strong_weights':STRONG,'weak_weights':WEAK,'strong_exposure':1.0,'weak_exposure':WEAK_EXPOSURE,'top_n':TOPN,'holding_sessions':H,'turnover_min':TURNMIN},'years':years,'combined':combined,'robust':robust,'censored':cens,'v6_reference':V6_REF,'new_model_evaluations':1,'events_file':str(EVENTS.relative_to(ROOT)),'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'V15 is one fixed historical challenger assembled from already exposed V14 strong-regime evidence and a previously observed 75% weak-regime risk overlay; not pristine OOS.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
