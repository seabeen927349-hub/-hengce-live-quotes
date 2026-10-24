#!/usr/bin/env python3
from __future__ import annotations
import csv,gzip,json,math,statistics,itertools
from collections import defaultdict,deque,Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HIST=ROOT/'research/codex_full_reset_20261023/results/stage_b/TWSE_ELECTRONICS_DAILY_2023_2025.csv.gz'
CURR=ROOT/'hengce/q017_radar/data/twse_electronics_history_2026.csv'
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v3_2026_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v3_2026_champion_events.jsonl'
START='2026-01-01';END='2026-10-22';WARM='2025-07-01';JUMP=.15
COSTS=(.008,.012,.016)
TOPNS=(3,5,8);HORIZONS=(5,10,15,20);TURNMINS=(20_000_000.0,50_000_000.0);RESIDS=(1,3,5)
PROFILES={
 'V2':(.40,.20,.15,.00,.10,.15),
 'RR_TREND':(.45,.25,.00,.15,.05,.10),
 'BALANCED':(.35,.20,.00,.20,.10,.15),
 'MOMENTUM':(.25,.25,.00,.30,.05,.15),
 'DEFENSIVE':(.35,.15,.00,.15,.10,.25),
 'LIQUID':(.35,.15,.00,.15,.20,.15),
}
# weights=(resid_rev,mom20,mom60,skip5_60,liquidity,lowvol)

class R:
 __slots__=('d','t','o','c','turn','r1','r3','r5','r20','r60','turn20','vol20','beta60','resid1','resid3','resid5','bad')
 def __init__(self,d,t,o,c,turn):
  self.d=d;self.t=t;self.o=o;self.c=c;self.turn=turn
  self.r1=self.r3=self.r5=self.r20=self.r60=self.turn20=self.vol20=self.beta60=self.resid1=self.resid3=self.resid5=None;self.bad=False

def ff(x):
 if x in (None,'','--','---'):return None
 try:
  v=float(str(x).replace(',',''));return v if math.isfinite(v) else None
 except:return None

def load(path):
 op=gzip.open if path.suffix=='.gz' else open;out=[]
 with op(path,'rt',encoding='utf-8-sig',newline='') as fh:
  for x in csv.DictReader(fh):
   d=(x.get('date') or '').strip();t=(x.get('ticker') or '').strip()
   if not d or d<WARM or len(t)!=4 or not t.isdigit():continue
   out.append(R(d,t,ff(x.get('open')),ff(x.get('close')),ff(x.get('turnover_ntd'))))
 return out

by=defaultdict(dict)
for r in load(HIST)+load(CURR):by[r.d][r.t]=r
dates=sorted(by);idx={d:i for i,d in enumerate(dates)}
# 1d + discontinuity guard
for i,d in enumerate(dates):
 if i==0:continue
 pd=dates[i-1]
 for t,r in by[d].items():
  p=by[pd].get(t)
  if p and p.c and r.c and p.c>0 and r.c>0:
   z=r.c/p.c-1;r.bad=abs(z)>JUMP
   if not r.bad:r.r1=z
# horizon returns/liquidity/vol/market
mkt=defaultdict(dict)
for i,d in enumerate(dates):
 for t,r in by[d].items():
  for h in (3,5,20,60):
   if i<h:continue
   q=by[dates[i-h]].get(t)
   if not q or not q.c or not r.c or q.c<=0 or r.c<=0:continue
   ok=True
   for j in range(i-h+1,i+1):
    z=by[dates[j]].get(t)
    if z is None or z.bad:ok=False;break
   if ok:setattr(r,f'r{h}',r.c/q.c-1)
  if i>=19:
   vals=[]
   for j in range(i-19,i+1):
    z=by[dates[j]].get(t)
    if z is None or z.turn is None or z.turn<0:vals=[];break
    vals.append(z.turn)
   if len(vals)==20:r.turn20=statistics.mean(vals)
   vals=[]
   for j in range(i-19,i+1):
    z=by[dates[j]].get(t)
    if z is None or z.r1 is None:vals=[];break
    vals.append(z.r1)
   if len(vals)==20 and len(set(vals))>1:r.vol20=statistics.stdev(vals)
 for h in (1,3,5):
  vals=[getattr(r,f'r{h}') for r in by[d].values() if getattr(r,f'r{h}') is not None]
  if vals:mkt[d][f'r{h}']=statistics.median(vals)
# beta60 prior-only and residuals
hist=defaultdict(lambda:deque(maxlen=60))
for d in dates:
 mr1=mkt[d].get('r1')
 for t,r in by[d].items():
  h=hist[t]
  if len(h)>=30:
   xs=[a for a,b in h];ys=[b for a,b in h];xb=statistics.mean(xs);yb=statistics.mean(ys);den=sum((x-xb)**2 for x in xs)
   if den>0:r.beta60=sum((x-xb)*(y-yb) for x,y in h)/den
  if r.beta60 is not None:
   for k in (1,3,5):
    rv=getattr(r,f'r{k}');mv=mkt[d].get(f'r{k}')
    if rv is not None and mv is not None:setattr(r,f'resid{k}',rv-r.beta60*mv)
  if mr1 is not None and r.r1 is not None:h.append((mr1,r.r1))

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

def build_scores(resid_h,turnmin,weights):
 cache={}
 for d in dates:
  elig={t:r for t,r in by[d].items() if getattr(r,f'resid{resid_h}') is not None and r.r20 is not None and r.r60 is not None and r.r5 is not None and r.turn20 is not None and r.vol20 is not None and r.turn20>=turnmin}
  if not elig:continue
  rr=ranks({t:-getattr(r,f'resid{resid_h}') for t,r in elig.items()});m20=ranks({t:r.r20 for t,r in elig.items()});m60=ranks({t:r.r60 for t,r in elig.items()});sk=ranks({t:r.r60-r.r5 for t,r in elig.items()});liq=ranks({t:r.turn20 for t,r in elig.items()});lv=ranks({t:-r.vol20 for t,r in elig.items()})
  w=weights;s=[]
  for t in elig:
   sc=w[0]*rr[t]+w[1]*m20[t]+w[2]*m60[t]+w[3]*sk[t]+w[4]*liq[t]+w[5]*lv[t]
   s.append((sc,t))
  s.sort(key=lambda x:(-x[0],x[1]));cache[d]=[t for _,t in s]
 return cache

def outcome(t,si,H):
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

def product(xs):
 n=1.0
 for x in xs:n*=1+x
 return n-1

def summarize(events,cost):
 nets=[e['gross_return']-cost for e in events];nav=1;peak=1;mdd=0
 for e in events:
  base=nav
  for j,(d,r) in enumerate(e['daily_gross_returns']):
   temp=base*(1+r-(cost if j==len(e['daily_gross_returns'])-1 else 0));peak=max(peak,temp);mdd=min(mdd,temp/peak-1)
  nav=base*(1+e['gross_return']-cost)
 best=max(range(len(nets)),key=lambda k:nets[k]) if nets else None
 remove=product([r for k,r in enumerate(nets) if k!=best]) if best is not None else None
 return {'baskets':len(nets),'wins':sum(r>0 for r in nets),'win_rate':sum(r>0 for r in nets)/len(nets) if nets else None,'compounded_return':product(nets),'max_drawdown':mdd,'remove_best_basket_return':remove,'mean_net_return':statistics.mean(nets) if nets else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None}

def simulate(cache,topn,H):
 events=[];censored=0;next_free=-1
 for i,d in enumerate(dates):
  if d<START or d>END or i<next_free:continue
  ranked=cache.get(d,[]);picks=ranked[:topn]
  if len(picks)<topn:continue
  xi=i+1+H
  if xi>=len(dates) or dates[xi]>END:continue
  outs=[(t,outcome(t,i,H)) for t in picks]
  if any(o is None for t,o in outs):censored+=1;next_free=xi+1;continue
  gross=statistics.mean(o[0] for t,o in outs);daily=[]
  for k in range(H+1):daily.append([outs[0][1][3][k][0],statistics.mean(o[3][k][1] for t,o in outs)])
  events.append({'signal_date':d,'entry_date':outs[0][1][1],'exit_date':outs[0][1][2],'tickers':picks,'gross_return':gross,'daily_gross_returns':daily});next_free=xi+1
 return events,censored

results=[];score_cache={}
for pname,weights in PROFILES.items():
 for rh,turn in itertools.product(RESIDS,TURNMINS):
  cache=build_scores(rh,turn,weights)
  for topn,H in itertools.product(TOPNS,HORIZONS):
   ev,cens=simulate(cache,topn,H);m008=summarize(ev,.008);m012=summarize(ev,.012);m016=summarize(ev,.016)
   objective=(m012['compounded_return'] if m012['compounded_return'] is not None else -9)+(m012['remove_best_basket_return'] or -9)*.45+(m012['win_rate'] or 0)*.25+(m012['max_drawdown'] or -1)*.45+(m016['compounded_return'] if m016['compounded_return'] is not None else -9)*.15
   results.append({'profile':pname,'residual_horizon':rh,'turnover_min':turn,'top_n':topn,'holding_sessions':H,'censored':cens,'m008':m008,'m012':m012,'m016':m016,'objective':objective})

eligible=[r for r in results if r['m012']['baskets']>=10 and r['m012']['compounded_return']>0 and r['m016']['compounded_return']>0 and r['m012']['remove_best_basket_return'] is not None and r['m012']['remove_best_basket_return']>0]
if not eligible:eligible=[r for r in results if r['m012']['baskets']>=8 and r['m012']['compounded_return']>0]
eligible.sort(key=lambda r:(r['objective'],r['m012']['compounded_return'],r['m012']['win_rate'],r['m012']['max_drawdown']),reverse=True)
champ=eligible[0] if eligible else max(results,key=lambda r:r['objective'])
cc=build_scores(champ['residual_horizon'],champ['turnover_min'],PROFILES[champ['profile']]);cev,ccens=simulate(cc,champ['top_n'],champ['holding_sessions'])
with EVENTS.open('w',encoding='utf-8') as fh:
 for e in cev:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
res={'status':'EXPOSED_HISTORICAL_OPTIMIZATION_ONLY','period':[START,END],'universe':'TWSE_LISTED_ELECTRONICS_PIT_DAILY_4DIGIT','search_space':{'profiles':list(PROFILES),'residual_horizons':list(RESIDS),'top_n':list(TOPNS),'holding_sessions':list(HORIZONS),'turnover_min':list(TURNMINS),'total_configs':len(results)},'champion':champ,'top10':eligible[:10],'v2_reference':[r for r in results if r['profile']=='V2' and r['residual_horizon']==5 and r['turnover_min']==50_000_000.0 and r['top_n']==5 and r['holding_sessions']==10][0],'champion_ticker_counts':Counter(t for e in cev for t in e['tickers']).most_common(20),'champion_events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':len(results),'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'2026 is already exposed and used for optimization; champion is not pristine OOS. Prospective shadow is required before production claims.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(res,ensure_ascii=False,indent=2))
