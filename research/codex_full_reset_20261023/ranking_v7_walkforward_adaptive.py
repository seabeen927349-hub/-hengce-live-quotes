#!/usr/bin/env python3
from __future__ import annotations
import csv,gzip,json,math,statistics,itertools
from collections import defaultdict,deque,Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HIST=ROOT/'research/codex_full_reset_20261023/results/stage_b/TWSE_ELECTRONICS_DAILY_2023_2025.csv.gz'
CURR=ROOT/'hengce/q017_radar/data/twse_electronics_history_2026.csv'
OUT=ROOT/'research/codex_full_reset_20261023/ranking_v7_walkforward_adaptive_result.json'
EVENTS=ROOT/'research/codex_full_reset_20261023/ranking_v7_champion_events.jsonl'
PERIODS={'2024':('2024-01-01','2024-12-31'),'2025':('2025-01-01','2025-12-31'),'2026':('2026-01-01','2026-10-22')}
COSTS=(.008,.012,.016);JUMP=.15
TOPN=3;H=20;TURNMIN=20_000_000.0;RH=5;SELECTION_COST=.012
PROFILES={
 'V6':(.20,.25,.30,.05,.20),
 'RESIDUAL_HEAVY':(.30,.20,.25,.05,.20),
 'TREND_HEAVY':(.15,.25,.40,.05,.15),
 'LOWVOL_HEAVY':(.15,.20,.25,.05,.35),
 'BALANCED':(.25,.20,.30,.10,.15),
 'LIQUID_DEFENSIVE':(.20,.20,.25,.15,.20),
}
META=[(w,p) for w in (4,6,9) for p in (0.0,0.5,1.0)]
V6_REFERENCE={'combined_return_012':2.5027,'combined_maxdd_012':-0.4061}

class R:
 __slots__=('d','t','o','c','turn','r1','r3','r5','r20','r60','turn20','vol20','beta60','resid5','bad')
 def __init__(self,d,t,o,c,turn):
  self.d=d;self.t=t;self.o=o;self.c=c;self.turn=turn
  self.r1=self.r3=self.r5=self.r20=self.r60=self.turn20=self.vol20=self.beta60=self.resid5=None;self.bad=False

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
   if not d or len(t)!=4 or not t.isdigit():continue
   out.append(R(d,t,ff(x.get('open')),ff(x.get('close')),ff(x.get('turnover_ntd'))))
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
   tv=[];rv=[]
   for j in range(i-19,i+1):
    z=by[dates[j]].get(t)
    if z is None or z.turn is None or z.turn<0:tv=[];break
    tv.append(z.turn)
   if len(tv)==20:r.turn20=statistics.mean(tv)
   for j in range(i-19,i+1):
    z=by[dates[j]].get(t)
    if z is None or z.r1 is None:rv=[];break
    rv.append(z.r1)
   if len(rv)==20 and len(set(rv))>1:r.vol20=statistics.stdev(rv)
 for h in (1,5):
  vals=[getattr(r,f'r{h}') for r in by[d].values() if getattr(r,f'r{h}') is not None]
  if vals:mkt[d][f'r{h}']=statistics.median(vals)
hist=defaultdict(lambda:deque(maxlen=60))
for d in dates:
 mr1=mkt[d].get('r1')
 for t,r in by[d].items():
  hh=hist[t]
  if len(hh)>=30:
   xs=[a for a,b in hh];ys=[b for a,b in hh];xb=statistics.mean(xs);yb=statistics.mean(ys);den=sum((x-xb)**2 for x in xs)
   if den>0:r.beta60=sum((x-xb)*(y-yb) for x,y in hh)/den
  if r.beta60 is not None and r.r5 is not None and mkt[d].get('r5') is not None:r.resid5=r.r5-r.beta60*mkt[d]['r5']
  if mr1 is not None and r.r1 is not None:hh.append((mr1,r.r1))

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

def make_cache(w):
 cache={}
 for d in dates:
  elig={t:r for t,r in by[d].items() if r.resid5 is not None and r.r20 is not None and r.r60 is not None and r.r5 is not None and r.turn20 is not None and r.vol20 is not None and r.turn20>=TURNMIN}
  if not elig:continue
  rr=ranks({t:-r.resid5 for t,r in elig.items()});m20=ranks({t:r.r20 for t,r in elig.items()});sk=ranks({t:r.r60-r.r5 for t,r in elig.items()});liq=ranks({t:r.turn20 for t,r in elig.items()});lv=ranks({t:-r.vol20 for t,r in elig.items()})
  arr=[(w[0]*rr[t]+w[1]*m20[t]+w[2]*sk[t]+w[3]*liq[t]+w[4]*lv[t],t) for t in elig]
  arr.sort(key=lambda x:(-x[0],x[1]));cache[d]=[t for _,t in arr]
 return cache

CACHES={p:make_cache(w) for p,w in PROFILES.items()}

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

def basket(profile,d):
 i=di[d];picks=CACHES[profile].get(d,[])[:TOPN]
 if len(picks)<TOPN:return None
 outs=[(t,outcome(t,i)) for t in picks]
 if any(o is None for t,o in outs):return None
 gross=statistics.mean(o[0] for t,o in outs);daily=[]
 for k in range(H+1):daily.append([outs[0][1][3][k][0],statistics.mean(o[3][k][1] for t,o in outs)])
 return {'signal_date':d,'entry_date':outs[0][1][1],'exit_date':outs[0][1][2],'tickers':picks,'gross_return':gross,'daily':daily}

def signal_dates(start,end):
 out=[];next_free=-1
 for i,d in enumerate(dates):
  if d<start or d>end or i<next_free:continue
  if i+1+H>=len(dates) or dates[i+1+H]>end:continue
  # Require every profile to have a valid comparable basket on this common schedule.
  bs={p:basket(p,d) for p in PROFILES}
  if any(v is None for v in bs.values()):continue
  out.append((d,bs));next_free=i+H+2
 return out

# Common completed hypothetical profile history begins in 2023 and is never reset.
SCHEDULE=[]
for y,(s,e) in {'2023':('2023-01-01','2023-12-31'),**PERIODS}.items():
 for d,bs in signal_dates(s,e):SCHEDULE.append((d,y,bs))
SCHEDULE.sort()

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
 return {'baskets':len(nets),'wins':sum(x>0 for x in nets),'win_rate':sum(x>0 for x in nets)/len(nets) if nets else None,'compounded_return':product(nets),'max_drawdown':mdd,'remove_best_basket_return':product([x for k,x in enumerate(nets) if k!=bi]) if bi is not None else None,'mean_net_return':statistics.mean(nets) if nets else None,'best_basket_net':max(nets) if nets else None,'worst_basket_net':min(nets) if nets else None}

def selector_score(xs,penalty):
 if not xs:return -999.
 mu=statistics.mean(xs)
 sd=statistics.stdev(xs) if len(xs)>1 else 0.
 return mu-penalty*sd

def run_meta(window,penalty):
 history={p:[] for p in PROFILES};ev=[];choices=[]
 for d,y,bs in SCHEDULE:
  # At d, history only contains baskets whose exits are from earlier common schedule points.
  eligible={p:history[p][-window:] for p in PROFILES if len(history[p])>=min(3,window)}
  if y!='2023':
   if eligible:
    scored=[(selector_score(v,penalty),p) for p,v in eligible.items()]
    scored.sort(key=lambda z:(-z[0],z[1]));chosen=scored[0][1]
   else:chosen='V6'
   e=dict(bs[chosen]);e['year']=y;e['chosen_profile']=chosen;e['selector_window']=window;e['selector_penalty']=penalty;ev.append(e)
   choices.append({'signal_date':d,'year':y,'chosen_profile':chosen,'prior_counts':{p:len(history[p]) for p in PROFILES}})
  # Update only after selection at d. Because common schedule is non-overlap, prior scheduled basket exited before the next d.
  for p,b in bs.items():history[p].append(b['gross_return']-SELECTION_COST)
 return ev,choices

results=[]
for window,penalty in META:
 ev,choices=run_meta(window,penalty);yrs={}
 for y in PERIODS:
  yy=[e for e in ev if e['year']==y];yrs[y]={str(c):summarize(yy,c) for c in COSTS}
 combined={str(c):summarize(ev,c) for c in COSTS}
 ms=[yrs[y]['0.012'] for y in PERIODS];m16=[yrs[y]['0.016'] for y in PERIODS]
 worst=min(x['compounded_return'] for x in ms);worst16=min(x['compounded_return'] for x in m16);minrem=min(x['remove_best_basket_return'] for x in ms);worstdd=min(x['max_drawdown'] for x in ms);avgwin=statistics.mean(x['win_rate'] for x in ms)
 robust=worst>0 and worst16>0 and minrem>0
 obj=2.0*worst+.35*combined['0.012']['compounded_return']+.75*minrem+.45*avgwin+1.2*worstdd+1.0*combined['0.012']['max_drawdown']
 results.append({'window':window,'penalty':penalty,'years':yrs,'combined':combined,'worst_year_return_012':worst,'worst_year_return_016':worst16,'min_remove_best_012':minrem,'worst_year_maxdd_012':worstdd,'avg_win_rate_012':avgwin,'robust':robust,'objective':obj,'profile_counts':Counter(e['chosen_profile'] for e in ev)})

rob=[r for r in results if r['robust']]
pool=rob or results
pool.sort(key=lambda r:(r['objective'],r['combined']['0.012']['compounded_return']),reverse=True)
champ=pool[0]
cev,cchoices=run_meta(champ['window'],champ['penalty'])
with EVENTS.open('w',encoding='utf-8') as fh:
 for e in cev:fh.write(json.dumps(e,ensure_ascii=False)+'\n')
cr=champ['combined']['0.012']['compounded_return'];cd=champ['combined']['0.012']['max_drawdown']
dominates_v6=(cr>=V6_REFERENCE['combined_return_012'] and cd>V6_REFERENCE['combined_maxdd_012'] and champ['robust'])
material_risk_improvement=(cd>=-0.35 and champ['robust'] and cr>=1.75)
status='V7_DOMINATES_V6' if dominates_v6 else ('V7_MATERIAL_RISK_IMPROVEMENT' if material_risk_improvement else 'V7_DOES_NOT_BEAT_V6')
res={'status':status,'method':'prior-only adaptive selector over six fixed ranking profiles','fixed_base':{'residual_horizon':RH,'turnover_min':TURNMIN,'top_n':TOPN,'holding_sessions':H,'selection_cost':SELECTION_COST},'profiles':PROFILES,'meta_configs':[{'window':w,'penalty':p} for w,p in META],'periods':PERIODS,'v6_reference':V6_REFERENCE,'champion':champ,'top_configs':pool[:9],'champion_choices':cchoices,'events_file':str(EVENTS.relative_to(ROOT)),'new_model_evaluations':len(results),'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False,'merge_authorized':False},'caveat':'Adaptive decisions use only earlier completed common-schedule basket outcomes. 2024-2026 are still exposed for meta-config screening; this is historical research, not pristine OOS.'}
OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2,default=dict)+'\n',encoding='utf-8');print(json.dumps(res,ensure_ascii=False,indent=2,default=dict))
