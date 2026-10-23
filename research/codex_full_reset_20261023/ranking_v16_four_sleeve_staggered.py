#!/usr/bin/env python3
from __future__ import annotations
import runpy,json,math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'research/codex_full_reset_20261023/ranking_v13_weak_regime_profiles.py'
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v16_four_sleeve_result.json'
TRADES=ROOT/'research/codex_full_reset_20261023/ranking_v16_trades.jsonl'
ns=runpy.run_path(str(BASE))
features=ns['features'];breadth=ns['breadth'];V6=tuple(ns['V6']);CUT=ns['BREADTH_CUTOFF'];PERIODS=ns['PERIODS'];COSTS=ns['COSTS'];outcome=ns['outcome'];dates=ns['dates']
STRONG=(.10,.25,.35,.15,.15);WEAK=V6;WEAK_EXPOSURE=.75
H=20;TOPN=3;SLOTS=4;OFFSETS=(0,5,10,15);CYCLE=21
V15_REF={'combined_return_012':3.3790209800153486,'combined_maxdd_012':-0.3574083605790588,'combined_remove_best_012':2.210105424105228}

def make_cache():
 cache={}
 for d,F in features.items():
  w=STRONG if breadth[d]>=CUT else WEAK
  arr=[(sum(w[i]*v[i] for i in range(5)),t) for t,v in F.items()]
  arr.sort(key=lambda z:(-z[0],z[1]));cache[d]=[t for s,t in arr]
 return cache
CACHE=make_cache()

def exp_for(d):return 1.0 if breadth[d]>=CUT else WEAK_EXPOSURE

def build_trades(start,end):
 first=next(i for i,d in enumerate(dates) if d>=start);last=max(i for i,d in enumerate(dates) if d<=end)
 trades=[];censored=0
 for slot,off in enumerate(OFFSETS):
  si=first+off
  while si<=last:
   d=dates[si];xi=si+1+H
   if xi>last:break
   picks=CACHE.get(d,[])[:TOPN]
   if len(picks)==TOPN:
    outs=[(t,outcome(t,si)) for t in picks]
    if all(o is not None for t,o in outs):
     daily=[]
     for k in range(H+1):daily.append([outs[0][1][3][k][0],sum(o[3][k][1] for t,o in outs)/TOPN])
     trades.append({'id':f'{slot}:{d}','slot':slot,'signal_date':d,'entry_date':outs[0][1][1],'exit_date':outs[0][1][2],'tickers':picks,'gross_return':sum(o[0] for t,o in outs)/TOPN,'daily':daily,'regime':'STRONG' if breadth[d]>=CUT else 'WEAK','breadth20':breadth[d],'exposure':exp_for(d)})
    else:censored+=1
   si+=CYCLE
 return trades,censored

def simulate_year(start,end,cost,skip_id=None):
 trades,censored=build_trades(start,end);by_slot={s:[] for s in range(SLOTS)}
 for t in trades:by_slot[t['slot']].append(t)
 # Each sleeve owns 25% initial capital and compounds independently; no cross-sleeve rebalancing.
 series={d:[.25]*SLOTS for d in dates if start<=d<=end}
 final=[]
 for s in range(SLOTS):
  nav=.25
  for t in by_slot[s]:
   if t['id']==skip_id:continue
   base=nav;x=t['exposure']
   for j,(d,r) in enumerate(t['daily']):
    if d in series:series[d][s]=base*(1+x*r-(x*cost if j==len(t['daily'])-1 else 0))
   nav=base*(1+x*(t['gross_return']-cost))
   # carry forward after exit until next trade; filled below using last-known scan
  final.append(nav)
 # Convert sparse per-slot marks to last-known sleeve NAV; entries with untouched .25 after prior trades need carrying.
 for s in range(SLOTS):
  lastv=.25
  active={}
  for t in by_slot[s]:
   if t['id']==skip_id:continue
   for j,(d,r) in enumerate(t['daily']):active[d]=series[d][s]
  for d in [d for d in dates if start<=d<=end]:
   if d in active:lastv=active[d]
   series[d][s]=lastv
 total=[(d,sum(series[d])) for d in series]
 peak=1.;mdd=0.
 for d,n in total:peak=max(peak,n);mdd=min(mdd,n/peak-1)
 # Recompute final total directly from sequential sleeve compounding.
 fsum=0.
 for s in range(SLOTS):
  nav=.25
  for t in by_slot[s]:
   if t['id']==skip_id:continue
   nav*=1+t['exposure']*(t['gross_return']-cost)
  fsum+=nav
 nets=[t['exposure']*(t['gross_return']-cost) for t in trades]
 return {'return':fsum-1,'max_drawdown':mdd,'trades':len(trades),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,'censored':censored},trades

def metrics(start,end,cost):
 base,tr=simulate_year(start,end,cost)
 best=max(tr,key=lambda t:t['exposure']*(t['gross_return']-cost)) if tr else None
 rb,_=simulate_year(start,end,cost,best['id'] if best else None)
 base['remove_best_trade_return']=rb['return'];base['best_trade_id']=best['id'] if best else None
 return base,tr

years={};alltr=[]
for y,(s,e) in PERIODS.items():
 years[y]={}
 for c in COSTS:
  m,tr=metrics(s,e,c);years[y][str(c)]=m
  if c==.012:
   for t in tr:t['year']=y
   alltr.extend(tr)
# Combined is year-by-year chained, matching prior annual reset convention; drawdown is worst chained annual NAV path approximation via yearly DD.
def chain(cost):
 ret=1.;wins=trades=cens=0;dds=[]
 for y in PERIODS:
  m=years[y][str(cost)];ret*=1+m['return'];wins+=m['wins'];trades+=m['trades'];cens+=m['censored'];dds.append(m['max_drawdown'])
 # remove globally best trade exactly by recomputing the affected year and chaining other years.
 best=None
 for t in alltr:
  score=t['exposure']*(t['gross_return']-cost)
  if best is None or score>best[0]:best=(score,t)
 rb=1.
 for y,(s,e) in PERIODS.items():
  skip=best[1]['id'] if best and best[1]['year']==y else None
  m,_=simulate_year(s,e,cost,skip);rb*=1+m['return']
 return {'compounded_return':ret-1,'max_drawdown':min(dds),'trades':trades,'wins':wins,'win_rate':wins/trades if trades else None,'remove_best_trade_return':rb-1,'censored':cens,'best_trade_id':best[1]['id'] if best else None}
combined={str(c):chain(c) for c in COSTS}
m12=[years[y]['0.012'] for y in PERIODS];m16=[years[y]['0.016'] for y in PERIODS]
robust=all(m['return']>0 and m['remove_best_trade_return']>0 and m['trades']>=20 for m in m12) and all(m['return']>0 for m in m16)
cr=combined['0.012']['compounded_return'];cd=combined['0.012']['max_drawdown'];rb=combined['0.012']['remove_best_trade_return']
strict=robust and cr>V15_REF['combined_return_012'] and cd>V15_REF['combined_maxdd_012'] and rb>V15_REF['combined_remove_best_012']
status='V16_STRICTLY_DOMINATES_V15' if strict else ('V16_RISK_ADJUSTED_CHALLENGER' if robust and cd>V15_REF['combined_maxdd_012'] else 'V16_DOES_NOT_BEAT_V15')
with TRADES.open('w',encoding='utf-8') as fh:
 for t in alltr:fh.write(json.dumps(t,ensure_ascii=False)+'\n')
res={'status':status,'method':'four independent 25% capital sleeves using fixed V15 selection, staggered at offsets 0/5/10/15 and recycled every 21 sessions','fixed':{'strong_weights':STRONG,'weak_weights':WEAK,'weak_exposure':WEAK_EXPOSURE,'slots':SLOTS,'offsets':OFFSETS,'cycle_sessions':CYCLE,'holding_sessions':H,'top_n':TOPN},'years':years,'combined':combined,'robust':robust,'v15_reference':V15_REF,'new_model_evaluations':1,'trades_file':str(TRADES.relative_to(ROOT)),'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'One fixed exposed-history portfolio-architecture challenger. Each sleeve compounds independently; no cross-sleeve rebalancing or leverage.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
