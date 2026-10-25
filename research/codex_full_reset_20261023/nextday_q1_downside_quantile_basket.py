#!/usr/bin/env python3
from __future__ import annotations

import json, math, statistics
from collections import Counter, defaultdict
from pathlib import Path

# Mechanical PIT OHLCV loader/cleaner only.
import research.codex_full_reset_20261023.nextday_o2_reversal_analog_tailrisk as raw

ROOT=Path(__file__).resolve().parents[2]
RESET=ROOT/'research'/'codex_full_reset_20261023'
OUT=RESET/'nextday_q1_downside_quantile_basket_result.json'
EVENTS=RESET/'nextday_q1_downside_quantile_basket_events.jsonl'
PRIMARY_COST=0.002
COSTS=(0.0,0.002,0.004,0.008)
TRAIN=('2023-01-01','2023-12-31'); DEV=('2024-01-01','2024-12-31'); VAL=('2025-01-01','2025-12-31'); DIAG=('2026-01-01','2026-10-22')
BINS=5; TAIL_Q=0.25; BASKET_SIZE=5; MAX_CORR=0.85
GROUPS={
 'MOMENTUM_RELATIVE':('r1','r5','r20','rel20','dist_high20'),
 'CANDLE_GEOMETRY':('gap','body','close_loc','range_pct'),
 'RISK_LIQUIDITY':('vol_ratio','turn_ratio','vol20'),
}
FEATURES=tuple(dict.fromkeys(k for ks in GROUPS.values() for k in ks))

def outcome(d,t):
 i=raw.di[d]
 if i+2>=len(raw.dates):return None
 ed,xd=raw.dates[i+1],raw.dates[i+2];s=raw.by[d].get(t);e=raw.by[ed].get(t);x=raw.by[xd].get(t)
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

def corr(a,b):
 ma=statistics.mean(a);mb=statistics.mean(b);xa=[x-ma for x in a];xb=[x-mb for x in b]
 da=math.sqrt(sum(x*x for x in xa));db=math.sqrt(sum(x*x for x in xb))
 return sum(x*y for x,y in zip(xa,xb))/(da*db) if da>1e-12 and db>1e-12 else 1.0

def quantile(vals,q):
 a=sorted(vals);n=len(a)
 if not n:return 0.0
 pos=(n-1)*q;lo=math.floor(pos);hi=math.ceil(pos)
 if lo==hi:return a[lo]
 return a[lo]*(hi-pos)+a[hi]*(pos-lo)

# Cross-sectional signal-date ranks + future pure overnight labels.
panels={}
for d in raw.dates:
 if d<TRAIN[0] or d>DIAG[1] or d not in raw.market:continue
 xs=[]
 for t in raw.by[d]:
  x=raw.stock.get((d,t))
  if not x or any(k not in x for k in FEATURES):continue
  o=outcome(d,t);h=hist20(d,t)
  if o and h:xs.append((t,x,o,h))
 if len(xs)<20:continue
 rr={k:ranks([(t,x[k]) for t,x,_,_ in xs]) for k in FEATURES}
 med=statistics.median(o['net20'] for _,_,o,_ in xs)
 ss=[]
 for t,x,o,h in xs:
  ss.append({'signal_date':d,'ticker':t,**{f'rank_{k}':rr[k][t] for k in FEATURES},**o,'residual_net20':o['net20']-med,'hist20':h})
 panels[d]={'stocks':ss,'market_median_net20':med}

train=[s for d,p in panels.items() if TRAIN[0]<=d<=TRAIN[1] for s in p['stocks']]
if len(train)<10000:raise RuntimeError(f'INSUFFICIENT_2023:{len(train)}')

# Fit downside distributions, not expected-return means. Each cell stores the 2023
# market-relative residual distribution, then only its fixed 25th percentile is used.
cell=defaultdict(list)
for s in train:
 for g,ks in GROUPS.items():
  for k in ks:
   b=min(BINS-1,int(s[f'rank_{k}']*BINS));cell[(g,k,b)].append(s['residual_net20'])
tail={key:quantile(vals,TAIL_Q) for key,vals in cell.items()}

def tail_score(s):
 sleeves=[];supports=[]
 for g,ks in GROUPS.items():
  qs=[]
  for k in ks:
   b=min(BINS-1,int(s[f'rank_{k}']*BINS));qs.append(tail[(g,k,b)]);supports.append(len(cell[(g,k,b)]))
  sleeves.append(statistics.mean(qs))
 # Conservative objective: typical sleeve floor plus weakest-sleeve penalty.
 score=statistics.median(sleeves)+.35*min(sleeves)
 return score,sleeves,min(supports)

daily=[]
for d,p in sorted(panels.items()):
 if d<DEV[0]:continue
 arr=[]
 for s in p['stocks']:
  sc,sl,n=tail_score(s);q=dict(s);q['tail_score']=sc;q['tail_sleeves']=sl;q['min_cell_n']=n;arr.append(q)
 arr.sort(key=lambda q:(-q['tail_score'],q['ticker']))
 chosen=[]
 for q in arr:
  if len(chosen)>=BASKET_SIZE:break
  if all(corr(q['hist20'],z['hist20'])<=MAX_CORR for z in chosen):chosen.append(q)
 if len(chosen)<BASKET_SIZE:
  used={z['ticker'] for z in chosen}
  for q in arr:
   if q['ticker'] not in used:
    chosen.append(q);used.add(q['ticker'])
    if len(chosen)>=BASKET_SIZE:break
 if len(chosen)<BASKET_SIZE:continue
 g=statistics.mean(q['gross_return'] for q in chosen)
 daily.append({'signal_date':d,'entry_date':chosen[0]['entry_date'],'exit_date':chosen[0]['exit_date'],'tickers':[q['ticker'] for q in chosen],
               'gross_return':g,'net20':g-PRIMARY_COST,'mean_tail_score':statistics.mean(q['tail_score'] for q in chosen),
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
if v['win_rate'] is not None and v['win_rate']>=.68 and d['win_rate'] is not None and d['win_rate']>=.62 and v['mean_return']>0 and d['mean_return']>0:status='Q1_DOWNSIDE_QUANTILE_HISTORICAL_FRONTIER'
elif v['win_rate'] is not None and v['win_rate']>=.62 and d['win_rate'] is not None and d['win_rate']>=.58 and v['mean_return']>0 and d['mean_return']>0:status='Q1_DOWNSIDE_QUANTILE_PROMISING'
else:status='Q1_DOWNSIDE_QUANTILE_REJECTED'
with EVENTS.open('w',encoding='utf-8') as fh:
 for label,rs in [('DEV_2024',dev),('REUSED_2025',val),('DIAGNOSTIC_2026',diag)]:
  for r in rs:fh.write(json.dumps({'split':label,**r},ensure_ascii=False)+'\n')
res={'status':status,'model':'Q1 downside-quantile five-stock equal-weight overnight basket','timing':'signal after t close; enter t+1 close; exit t+2 open',
'new_mode':'Optimize the 25th-percentile market-relative residual floor instead of mean residual or top1 score. Every eligible night trades five diversified stocks; no day gate and no threshold search.',
'independence':'Raw TWSE electronics OHLC/turnover only; no HENGCE/V/X/HR, O3/G1/B1/B2 selected identities, T86, or future-day feature.','groups':GROUPS,
'protocol':{'fit':'2023 only','day_filter':'none','tail_quantile_fixed':TAIL_Q,'basket_size_fixed':BASKET_SIZE,'max_pair_corr':MAX_CORR,'bins':BINS,'primary_cost':PRIMARY_COST,'cost_stress':COSTS,'2025_2026':'reused historical diagnostics, not pristine OOS'},
'train_rows_2023':len(train),'development_2024':stress(dev),'reused_validation_2025':stress(val),'pre2026':stress(pre),'diagnostic_2026':stress(diag),'events_file':str(EVENTS.relative_to(ROOT)),
'research_boundary':'Q1 is a new post-B1/B2 hypothesis. All later years have already been exposed at project level, so results are historical diagnostics and require prospective confirmation.',
'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Historical research only; close fills, slippage, capacity, and future stability require prospective validation.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Q1_RESULT='+json.dumps(res,ensure_ascii=False,separators=(',',':')))
