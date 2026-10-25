#!/usr/bin/env python3
from __future__ import annotations

import json, math, statistics
from collections import Counter, defaultdict
from pathlib import Path

# Mechanical PIT OHLCV loader/cleaner only.
import research.codex_full_reset_20261023.nextday_o2_reversal_analog_tailrisk as raw

ROOT=Path(__file__).resolve().parents[2]
RESET=ROOT/'research'/'codex_full_reset_20261023'
OUT=RESET/'nextday_b2_portfolio_first_result.json'
EVENTS=RESET/'nextday_b2_portfolio_first_events.jsonl'
PRIMARY_COST=0.002
COSTS=(0.0,0.002,0.004,0.008)
TRAIN=('2023-01-01','2023-12-31'); DEV=('2024-01-01','2024-12-31'); VAL=('2025-01-01','2025-12-31'); DIAG=('2026-01-01','2026-10-22')
BINS=5; SMOOTH=40.0; BASKET_SIZE=7; POOL=30
GROUPS={
 'MOMENTUM_RELATIVE':('r1','r5','r20','rel20','dist_high20'),
 'CANDLE_GEOMETRY':('gap','body','close_loc','range_pct'),
 'RISK_LIQUIDITY':('vol_ratio','turn_ratio','vol20'),
}
FEATURES=tuple(dict.fromkeys(k for ks in GROUPS.values() for k in ks))


def outcome(d,t):
 i=raw.di[d]
 if i+2>=len(raw.dates): return None
 ed,xd=raw.dates[i+1],raw.dates[i+2]; s=raw.by[d].get(t); e=raw.by[ed].get(t); x=raw.by[xd].get(t)
 if not s or not e or not x or e['c']<=0 or x['o']<=0:return None
 if abs(e['c']/s['c']-1)>raw.JUMP or abs(x['c']/e['c']-1)>raw.JUMP:return None
 g=x['o']/e['c']-1
 return {'entry_date':ed,'exit_date':xd,'gross_return':g,'net20':g-PRIMARY_COST}

def ranks(pairs):
 a=sorted(pairs,key=lambda z:(z[1],z[0]));n=len(a);out={};i=0
 while i<n:
  j=i+1
  while j<n and a[j][1]==a[i][1]:j+=1
  p=((i+j-1)/2+.5)/n
  for q in range(i,j):out[a[q][0]]=p
  i=j
 return out

def hist20(d,t):
 i=raw.di[d];a=[]
 for j in range(i-19,i+1):
  if j<=0:return None
  p=raw.by[raw.dates[j-1]].get(t);q=raw.by[raw.dates[j]].get(t)
  if not p or not q or p['c']<=0 or q['c']<=0:return None
  r=q['c']/p['c']-1
  if abs(r)>raw.JUMP:return None
  a.append(r)
 return a if len(a)==20 else None

def cov(a,b):
 ma=statistics.mean(a);mb=statistics.mean(b)
 return sum((x-ma)*(y-mb) for x,y in zip(a,b))/(len(a)-1)

def vol(a):return max(statistics.stdev(a),1e-5)

panels={}
for d in raw.dates:
 if d<TRAIN[0] or d>DIAG[1] or d not in raw.market:continue
 xs=[]
 for t in raw.by[d]:
  x=raw.stock.get((d,t))
  if not x or any(k not in x for k in FEATURES):continue
  o=outcome(d,t);h=hist20(d,t)
  if o and h:xs.append((t,x,o,h))
 if len(xs)<30:continue
 rr={k:ranks([(t,x[k]) for t,x,_,_ in xs]) for k in FEATURES}
 med=statistics.median(o['net20'] for _,_,o,_ in xs)
 ss=[]
 for t,x,o,h in xs:
  ss.append({'signal_date':d,'ticker':t,**{f'rank_{k}':rr[k][t] for k in FEATURES},**o,'residual_net20':o['net20']-med,'hist20':h})
 panels[d]={'stocks':ss,'market_median_net20':med}

train=[s for d,p in panels.items() if TRAIN[0]<=d<=TRAIN[1] for s in p['stocks']]
if len(train)<10000:raise RuntimeError(f'INSUFFICIENT_2023:{len(train)}')
cell=defaultdict(lambda:{'n':0,'sum':0.0})
for s in train:
 for g,ks in GROUPS.items():
  for k in ks:
   b=min(BINS-1,int(s[f'rank_{k}']*BINS));z=cell[(g,k,b)];z['n']+=1;z['sum']+=s['residual_net20']

def expected_residual(s):
 sleeves=[]
 for g,ks in GROUPS.items():
  es=[]
  for k in ks:
   b=min(BINS-1,int(s[f'rank_{k}']*BINS));z=cell[(g,k,b)];es.append(z['sum']/(z['n']+SMOOTH))
  sleeves.append(statistics.mean(es))
 # Conservative ensemble: median plus a small penalty/reward from weakest sleeve.
 return statistics.median(sleeves)+.25*min(sleeves),sleeves

def portfolio_weights(chosen):
 inv=[1/vol(q['hist20']) for q in chosen];z=sum(inv);return[x/z for x in inv]

def portfolio_risk(chosen,w):
 v=0.0
 for i,a in enumerate(chosen):
  for j,b in enumerate(chosen):v+=w[i]*w[j]*cov(a['hist20'],b['hist20'])
 return math.sqrt(max(v,1e-10))

def objective(chosen):
 w=portfolio_weights(chosen);mu=sum(wi*q['mu'] for wi,q in zip(w,chosen));risk=portfolio_risk(chosen,w)
 return mu/risk,mu,risk,w

daily=[]
for d,p in sorted(panels.items()):
 if d<DEV[0]:continue
 arr=[]
 for s in p['stocks']:
  mu,sl=expected_residual(s);q=dict(s);q['mu']=mu;q['sleeves']=sl;arr.append(q)
 # Outcome-free pool: best positive predicted residuals; if <POOL positive, fill by rank.
 arr.sort(key=lambda q:(-q['mu'],q['ticker']));pool=arr[:POOL]
 if len(pool)<BASKET_SIZE:continue
 chosen=[];unused=pool[:]
 while len(chosen)<BASKET_SIZE:
  best=None
  for q in unused:
   cand=chosen+[q];obj,mu,risk,w=objective(cand)
   key=(obj,mu,-risk,q['mu'])
   if best is None or key>best[0]:best=(key,q)
  q=best[1];chosen.append(q);unused.remove(q)
 obj,pmu,prisk,w=objective(chosen)
 gross=sum(wi*q['gross_return'] for wi,q in zip(w,chosen))
 daily.append({'signal_date':d,'entry_date':chosen[0]['entry_date'],'exit_date':chosen[0]['exit_date'],'tickers':[q['ticker'] for q in chosen],
               'weights':w,'gross_return':gross,'net20':gross-PRIMARY_COST,'predicted_residual':pmu,'signal_portfolio_risk':prisk,'signal_objective':obj,
               'market_median_net20':p['market_median_net20'],'leg_gross_returns':[q['gross_return'] for q in chosen]})

def wilson(w,n,z=1.959963984540054):
 if not n:return None
 p=w/n;z2=z*z;den=1+z2/n
 return(p+z2/(2*n)-z*math.sqrt(p*(1-p)/n+z2/(4*n*n)))/den

def metrics(rs,cost):
 xs=[r['gross_return']-cost for r in rs];n=len(xs);w=sum(x>0 for x in xs);nav=1.;peak=1.;mdd=0.;cur=mx=0
 for x in xs:
  nav*=1+x;peak=max(peak,nav);mdd=min(mdd,nav/peak-1)
  if x<=0:cur+=1;mx=max(mx,cur)
  else:cur=0
 tc=Counter(t for r in rs for t in r['tickers'])
 return {'basket_nights':n,'underlying_legs':n*BASKET_SIZE,'wins':w,'losses':n-w,'win_rate':w/n if n else None,'wilson95_lower':wilson(w,n),
         'mean_return':statistics.mean(xs) if xs else None,'median_return':statistics.median(xs) if xs else None,'worst_return':min(xs) if xs else None,'best_return':max(xs) if xs else None,
         'compounded_return':nav-1 if n else 0.0,'max_drawdown':mdd,'max_consecutive_losses':mx,'top_ticker_leg_share':max(tc.values())/(n*BASKET_SIZE) if n and tc else None}
def split(rs,p):return[r for r in rs if p[0]<=r['signal_date']<=p[1]]
def stress(rs):return{str(c):metrics(rs,c) for c in COSTS}
dev=split(daily,DEV);val=split(daily,VAL);diag=split(daily,DIAG);pre=dev+val
v=metrics(val,PRIMARY_COST);d=metrics(diag,PRIMARY_COST)
if v['win_rate'] is not None and v['win_rate']>=.68 and d['win_rate'] is not None and d['win_rate']>=.60 and v['mean_return']>0 and d['mean_return']>0:status='B2_PORTFOLIO_FIRST_HISTORICAL_FRONTIER'
elif v['win_rate'] is not None and v['win_rate']>=.62 and d['win_rate'] is not None and d['win_rate']>=.58 and v['mean_return']>0 and d['mean_return']>0:status='B2_PORTFOLIO_FIRST_PROMISING'
else:status='B2_PORTFOLIO_FIRST_REJECTED'
with EVENTS.open('w',encoding='utf-8') as fh:
 for label,rs in [('DEV_2024',dev),('REUSED_2025',val),('DIAGNOSTIC_2026',diag)]:
  for r in rs:fh.write(json.dumps({'split':label,**r},ensure_ascii=False)+'\n')
res={'status':status,'model':'B2 portfolio-first seven-stock inverse-vol overnight basket','timing':'signal after t close; enter t+1 close; exit t+2 open','new_mode':'No day gate and no top1. Every eligible night, greedily choose a seven-stock combination maximizing 2023-fitted expected cross-sectional residual per signal-day covariance risk; inverse-vol weights are determined only from prior 20-day returns.',
'independence':'Raw TWSE electronics OHLC/turnover only; no HENGCE/V/X/HR, O3/G1/B1 selected identities, T86, or future-day feature.','groups':GROUPS,
'protocol':{'fit':'2023 only','day_filter':'none','basket_size_fixed':BASKET_SIZE,'candidate_pool_fixed':POOL,'bins':BINS,'smoothing':SMOOTH,'risk_window':20,'primary_cost':PRIMARY_COST,'cost_stress':COSTS,'2025_2026':'reused historical diagnostics, not pristine OOS'},
'train_rows_2023':len(train),'development_2024':stress(dev),'reused_validation_2025':stress(val),'pre2026':stress(pre),'diagnostic_2026':stress(diag),'events_file':str(EVENTS.relative_to(ROOT)),
'research_boundary':'B2 is a new post-B1 hypothesis. Because B1 already exposed 2025/2026, these years are historical diagnostics only; prospective confirmation still requires unseen data.',
'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Historical research only; close fills, slippage, capacity, and future stability require prospective validation.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('B2_RESULT='+json.dumps(res,ensure_ascii=False,separators=(',',':')))
