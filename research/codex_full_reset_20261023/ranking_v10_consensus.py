#!/usr/bin/env python3
from __future__ import annotations
import csv,gzip,json,math,statistics
from collections import defaultdict,deque
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HIST=ROOT/'research/codex_full_reset_20261023/results/stage_b/TWSE_ELECTRONICS_DAILY_2023_2025.csv.gz'
CURR=ROOT/'hengce/q017_radar/data/twse_electronics_history_2026.csv'
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v10_consensus_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v10_consensus_events.jsonl'
PERIODS={'2024':('2024-01-01','2024-12-31'),'2025':('2025-01-01','2025-12-31'),'2026':('2026-01-01','2026-10-22')}
TRAIN_END={'2024':'2023-12-31','2025':'2024-12-31','2026':'2025-12-31'}
COSTS=(.008,.012,.016);JUMP=.15;H=20;TOPN=3;TURNMIN=20_000_000.
FACTORS=('resid_rev','mom20','skip5_60','liquidity','lowvol')
V6=(.20,.25,.30,.05,.20)
V9_SHRINK=.90
CONSENSUS_BLEND=.50
V6_REF={'combined_return_012':2.5027,'combined_maxdd_012':-0.4061,'years_012':{'2024':.2943,'2025':.4192,'2026':.9070}}

class R:
 __slots__=('d','t','o','c','turn','r1','r5','r20','r60','turn20','vol20','beta60','resid5','bad')
 def __init__(self,d,t,o,c,turn):
  self.d=d;self.t=t;self.o=o;self.c=c;self.turn=turn
  self.r1=self.r5=self.r20=self.r60=self.turn20=self.vol20=self.beta60=self.resid5=None;self.bad=False

def ff(x):
 if x in (None,'','--','---'):return None
 try:
  v=float(str(x).replace(',',''));return v if math.isfinite(v) else None
 except:return None

def load(p):
 op=gzip.open if p.suffix=='.gz' else open;out=[]
 with op(p,'rt',encoding='utf-8-sig',newline='') as fh:
  for x in csv.DictReader(fh):
   d=(x.get('date') or '').strip();t=(x.get('ticker') or '').strip()
   if d and len(t)==4 and t.isdigit():out.append(R(d,t,ff(x.get('open')),ff(x.get('close')),ff(x.get('turnover_ntd'))))
 return out

by=defaultdict(dict)
for r in load(HIST)+load(CURR):by[r.d][r.t]=r
dates=sorted(by);di={d:i for i,d in enumerate(dates)}
for i,d in enumerate(dates):
 if i==0:continue
 pd=dates[i-1]
 for t,r in by[d].items():
  p=by[pd].get(t)
  if p and p.c and r.c and p.c>0 and r.c>0:
   z=r.c/p.c-1;r.bad=abs(z)>JUMP
   if not r.bad:r.r1=z
mkt=defaultdict(dict)
for i,d in enumerate(dates):
 for t,r in by[d].items():
  for h in (5,20,60):
   if i<h:continue
   q=by[dates[i-h]].get(t)
   if not q or not q.c or not r.c or q.c<=0 or r.c<=0:continue
   ok=True
   for j in range(i-h+1,i+1):
    z=by[dates[j]].get(t)
    if z is None or z.bad:ok=False;break
   if ok:setattr(r,f'r{h}',r.c/q.c-1)
  if i>=19:
   zs=[by[dates[j]].get(t) for j in range(i-19,i+1)]
   if all(z is not None and z.turn is not None and z.turn>=0 for z in zs):r.turn20=statistics.mean(z.turn for z in zs)
   if all(z is not None and z.r1 is not None for z in zs):
    vv=[z.r1 for z in zs]
    if len(set(vv))>1:r.vol20=statistics.stdev(vv)
 for h in (1,5):
  vals=[getattr(r,f'r{h}') for r in by[d].values() if getattr(r,f'r{h}') is not None]
  if vals:mkt[d][f'r{h}']=statistics.median(vals)
hh=defaultdict(lambda:deque(maxlen=60))
for d in dates:
 mr=mkt[d].get('r1')
 for t,r in by[d].items():
  h=hh[t]
  if len(h)>=30:
   xs=[x for x,y in h];ys=[y for x,y in h];xb=statistics.mean(xs);yb=statistics.mean(ys);den=sum((x-xb)**2 for x in xs)
   if den>0:r.beta60=sum((x-xb)*(y-yb) for x,y in h)/den
  if r.beta60 is not None and r.r5 is not None and mkt[d].get('r5') is not None:r.resid5=r.r5-r.beta60*mkt[d]['r5']
  if mr is not None and r.r1 is not None:h.append((mr,r.r1))

def ranks(vals):
 a=sorted(vals.items(),key=lambda kv:(kv[1],kv[0]));n=len(a);out={}
 if n<=1:return {t:.5 for t,v in a}
 i=0
 while i<n:
  j=i+1
  while j<n and a[j][1]==a[i][1]:j+=1
  pct=(((i+1)+j)/2-1)/(n-1)
  for k in range(i,j):out[a[k][0]]=pct
  i=j
 return out

def corr(x,y):
 if len(x)<10:return None
 xb=statistics.mean(x);yb=statistics.mean(y);dx=sum((a-xb)**2 for a in x);dy=sum((b-yb)**2 for b in y)
 if dx<=0 or dy<=0:return None
 return sum((a-xb)*(b-yb) for a,b in zip(x,y))/math.sqrt(dx*dy)

F={}
for d in dates:
 elig={t:r for t,r in by[d].items() if r.resid5 is not None and r.r20 is not None and r.r60 is not None and r.r5 is not None and r.turn20 is not None and r.vol20 is not None and r.turn20>=TURNMIN}
 if len(elig)<10:continue
 rr=ranks({t:-r.resid5 for t,r in elig.items()});m20=ranks({t:r.r20 for t,r in elig.items()});sk=ranks({t:r.r60-r.r5 for t,r in elig.items()});liq=ranks({t:r.turn20 for t,r in elig.items()});lv=ranks({t:-r.vol20 for t,r in elig.items()})
 F[d]={t:(rr[t],m20[t],sk[t],liq[t],lv[t]) for t in elig}

def outcome(t,si):
 ei=si+1;xi=ei+H
 if xi>=len(dates):return None
 ed,xd=dates[ei],dates[xi];e=by[ed].get(t);x=by[xd].get(t)
 if not e or not x or e.o is None or x.c is None or e.o<=0 or x.c<=0:return None
 path=[]
 for j in range(ei,xi+1):
  z=by[dates[j]].get(t)
  if z is None or z.c is None or z.c<=0 or z.bad:return None
  path.append((dates[j],z.c/e.o-1))
 return x.c/e.o-1,ed,xd,path

def target_returns(d):
 i=di[d];out={}
 for t in F.get(d,{}):
  o=outcome(t,i)
  if o is not None:out[t]=o[0]
 return out

def learn_weights(end_date):
 anchors=[];next_i=-1
 for i,d in enumerate(dates):
  if d<'2023-01-01' or d>end_date or i<next_i or d not in F:continue
  if i+1+H>=len(dates) or dates[i+1+H]>end_date:continue
  anchors.append(d);next_i=i+H+2
 ics={f:[] for f in FACTORS}
 for d in anchors:
  tr=target_returns(d);common=[t for t in F[d] if t in tr]
  if len(common)<20:continue
  yr=ranks({t:tr[t] for t in common})
  for k,f in enumerate(FACTORS):
   ic=corr([F[d][t][k] for t in common],[yr[t] for t in common])
   if ic is not None:ics[f].append(ic)
 vals=[];diag={}
 for f in FACTORS:
  a=ics[f];mu=statistics.mean(a) if a else 0.;vals.append(max(0.,mu));diag[f]={'n':len(a),'mean_ic':mu}
 s=sum(vals);raw=[v/s for v in vals] if s>0 else list(V6)
 w=[V9_SHRINK*V6[i]+(1-V9_SHRINK)*raw[i] for i in range(5)];ss=sum(w);w=[x/ss for x in w]
 return w,raw,diag,anchors

def consensus_cache(year,start,end):
 v9,raw,diag,anchors=learn_weights(TRAIN_END[year]);cache={}
 for d in dates:
  if d<start or d>end or d not in F:continue
  s6={t:sum(V6[i]*v[i] for i in range(5)) for t,v in F[d].items()}
  s9={t:sum(v9[i]*v[i] for i in range(5)) for t,v in F[d].items()}
  r6=ranks(s6);r9=ranks(s9)
  arr=[(CONSENSUS_BLEND*r6[t]+(1-CONSENSUS_BLEND)*r9[t],t) for t in F[d]]
  arr.sort(key=lambda z:(-z[0],z[1]));cache[d]=[t for s,t in arr]
 return cache,v9,raw,diag,anchors

def simulate(year,start,end):
 cache,w,raw,diag,anchors=consensus_cache(year,start,end);ev=[];cens=0;next_free=-1
 for i,d in enumerate(dates):
  if d<start or d>end or i<next_free:continue
  picks=cache.get(d,[])[:TOPN]
  if len(picks)<TOPN:continue
  xi=i+1+H
  if xi>=len(dates) or dates[xi]>end:continue
  outs=[(t,outcome(t,i)) for t in picks]
  if any(o is None for t,o in outs):cens+=1;next_free=xi+1;continue
  gross=statistics.mean(o[0] for t,o in outs);daily=[]
  for k in range(H+1):daily.append([outs[0][1][3][k][0],statistics.mean(o[3][k][1] for t,o in outs)])
  ev.append({'signal_date':d,'entry_date':outs[0][1][1],'exit_date':outs[0][1][2],'tickers':picks,'gross_return':gross,'daily':daily});next_free=xi+1
 return ev,cens,{'v9_weights':dict(zip(FACTORS,w)),'raw_ic_weights':dict(zip(FACTORS,raw)),'factor_ic':diag,'training_anchors':anchors,'training_end':TRAIN_END[year]}

def product(xs):
 n=1.
 for x in xs:n*=1+x
 return n-1

def summarize(ev,cost):
 nets=[e['gross_return']-cost for e in ev];nav=1.;peak=1.;mdd=0.
 for e in ev:
  base=nav
  for j,(d,r) in enumerate(e['daily']):
   temp=base*(1+r-(cost if j==len(e['daily'])-1 else 0));peak=max(peak,temp);mdd=min(mdd,temp/peak-1)
  nav=base*(1+e['gross_return']-cost)
 bi=max(range(len(nets)),key=lambda k:nets[k]) if nets else None
 return {'baskets':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,'compounded_return':product(nets),'max_drawdown':mdd,'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None and len(nets)>1 else None,'mean_net_return':statistics.mean(nets) if nets else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None}

years={};learned={};all_ev=[];censored=0
for y,(s,e) in PERIODS.items():
 ev,c,info=simulate(y,s,e);censored+=c
 for x in ev:x['year']=y
 all_ev.extend(ev);years[y]={str(cost):summarize(ev,cost) for cost in COSTS};learned[y]=info
combined={str(cost):summarize(sorted(all_ev,key=lambda z:z['signal_date']),cost) for cost in COSTS}
m12=[years[y]['0.012'] for y in PERIODS];m16=[years[y]['0.016'] for y in PERIODS]
enough=all(x['baskets']>=7 for x in m12);worst=min(x['compounded_return'] for x in m12);worst16=min(x['compounded_return'] for x in m16);minrem=min(x['remove_best_basket_return'] for x in m12);robust=enough and worst>0 and worst16>0 and minrem>0
cr=combined['0.012']['compounded_return'];cd=combined['0.012']['max_drawdown']
dom=robust and cr>=V6_REF['combined_return_012'] and cd>V6_REF['combined_maxdd_012']
mat=robust and cr>=1.75 and cd>=-.35
status='V10_DOMINATES_V6' if dom else ('V10_MATERIAL_RISK_IMPROVEMENT' if mat else 'V10_DOES_NOT_BEAT_V6')
with EVENTS.open('w',encoding='utf-8') as fh:
 for e in all_ev:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':status,'method':'fixed 50/50 cross-sectional consensus of frozen V6 composite rank and prior-history V9 MEAN_IC(.90 shrink) composite rank','fixed':{'v6_weights':dict(zip(FACTORS,V6)),'v9_shrink':V9_SHRINK,'consensus_blend_v6':CONSENSUS_BLEND,'top_n':TOPN,'holding_sessions':H,'turnover_min':TURNMIN},'years':years,'combined':combined,'learned':learned,'robust':robust,'enough_trades':enough,'worst_year_return_012':worst,'worst_year_return_016':worst16,'min_remove_best_012':minrem,'censored':censored,'v6_reference':V6_REF,'new_model_evaluations':1,'events_file':str(EVENTS.relative_to(ROOT)),'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'One fixed consensus challenger. V9 annual weights use only fully realized prior-year history; 2024-2026 remain exposed historical research.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2))
