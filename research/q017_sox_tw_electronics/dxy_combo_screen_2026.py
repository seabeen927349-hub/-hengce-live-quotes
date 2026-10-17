#!/usr/bin/env python3
import csv,json
from collections import defaultdict
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'dxy_combo_screen_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;COST=.006;XS=.002;RESMAX=.04;K=25.
def f(x):
 try:return float(str(x).replace(',','').strip())
 except:return None
# generic US series
def load(path):
 a=[]
 for r in csv.DictReader(path.open(encoding='utf-8')):
  c=f(r['close'])
  if c is not None:a.append((r['date'],c))
 a.sort();return a
sox=load(ARC/'sox_2026.csv');dxy=load(ARC/'dxy_2026.csv')
sd=[d for d,_ in sox];dd=[d for d,_ in dxy]
sret={sox[i][0]:sox[i][1]/sox[i-1][1]-1 for i in range(1,len(sox))};dret={dxy[i][0]:dxy[i][1]/dxy[i-1][1]-1 for i in range(1,len(dxy))}
def prev(ds,d):
 z=[u for u in ds if u<d];return z[-1] if z else None
by_t=defaultdict(list);by_d=defaultdict(list)
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
 o=f(r['open']);c=f(r['close'])
 if o is None or c is None:continue
 x={'date':r['date'],'ticker':r['ticker'],'open':o,'close':c};by_t[r['ticker']].append(x);by_d[r['date']].append(x)
for t in by_t:by_t[t].sort(key=lambda x:x['date'])
md=sorted(by_d);mi={d:i for i,d in enumerate(md)}
aligned={d:sret.get(prev(sd,d)) for d in md};beta={};pcache={}
for t,rs in by_t.items():
 obs=[];pc=None
 for r in rs:
  d=r['date'];pcache[(d,t)]=pc;sh=aligned.get(d)
  if pc and sh is not None:
   tr=r['close']/pc-1
   if len(obs)>=30:
    z=obs[-60:];mx=sum(a for a,b in z)/len(z);my=sum(b for a,b in z)/len(z);vv=sum((a-mx)**2 for a,b in z)
    beta[(d,t)]=sum((a-mx)*(b-my) for a,b in z)/vv if vv else 0
   obs.append((sh,tr))
  pc=r['close']
feat={}
for d in md:
 us=prev(sd,d);ux=prev(dd,d);sh=sret.get(us);dx=dret.get(ux)
 if not us or sh is None or not ux or dx is None:continue
 si=sd.index(us);di=dd.index(ux)
 s5=sox[si][1]/sox[si-5][1]-1 if si>=5 else None
 d5=dxy[di][1]/dxy[di-5][1]-1 if di>=5 else None
 feat[d]={'shock':sh,'sox5':s5,'dxy1':dx,'dxy5':d5}
cand={}
for d in md:
 ft=feat.get(d);a=[]
 if not ft:continue
 for r in by_d[d]:
  t=r['ticker'];b=beta.get((d,t));pc=pcache.get((d,t))
  if b is None or b<=0 or not pc:continue
  res=r['open']/pc-1-b*ft['shock']
  if res<=RESMAX:a.append((b*(1+K*max(-res,0)),r,t,res,b))
 a.sort(key=lambda q:q[0],reverse=True);cand[d]=a

def dxy_pass(ft,kind,th):
 if kind=='none':return True
 v=ft['dxy1'] if kind.startswith('d1') else ft['dxy5']
 if v is None:return False
 return v<=th if kind.endswith('le') else v>=th

def run(shock_max,sox5_max,kind,th):
 cap=START;busy=None;curve=[]
 for d in md:
  if busy and d<=busy:continue
  ft=feat.get(d)
  if not ft or ft['shock']>shock_max or ft['sox5'] is None or ft['sox5']>sox5_max or not dxy_pass(ft,kind,th):continue
  i=mi[d]
  if i+10>=len(md) or not cand.get(d):continue
  _,r,t,res,b=cand[d][0];d9,d10,d11=md[i+8],md[i+9],md[i+10]
  mp={x['date']:x['close'] for x in by_t[t]};c9,c10,c11=mp.get(d9),mp.get(d10),mp.get(d11)
  if not c9 or not c10 or not c11:continue
  extend=c10>=c9;xd=d11 if extend else d10;raw=c11 if extend else c10
  net=raw*(1-XS)/r['open']-1-COST;cap*=1+net;busy=xd
  curve.append({'entry':d,'ticker':t,'exit':xd,'net':net,'capital':cap,'dxy1':ft['dxy1'],'dxy5':ft['dxy5'],'shock':ft['shock'],'sox5':ft['sox5'],'resid':res,'beta':b})
 return cap,curve
filters=[('none',0)]
for th in (-.01,-.0075,-.005,-.0025,0):filters.append(('d1le',th))
for th in (0,.0025,.005,.0075,.01):filters.append(('d1ge',th))
for th in (-.02,-.015,-.01,-.005,0):filters.append(('d5le',th))
for th in (0,.005,.01,.015,.02):filters.append(('d5ge',th))
rows=[];details={}
for sh in (0,-.005,-.01,-.015,-.02,-.025,-.03):
 for s5 in (-.01,-.02,-.03,-.04,-.05):
  for kind,th in filters:
   cap,curve=run(sh,s5,kind,th);key=f'{sh}_{s5}_{kind}_{th}';details[key]=curve
   rows.append({'shock_max':sh,'sox5_max':s5,'dxy_filter':kind,'dxy_th':th,'final':cap,'ret':cap/START-1,'events':len(curve),'wins':sum(x['net']>0 for x in curve)})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];bc=details[f"{best['shock_max']}_{best['sox5_max']}_{best['dxy_filter']}_{best['dxy_th']}"]
# family breadth: same DXY filter threshold, nearby SOX gates
vals=[]
shg=[0,-.005,-.01,-.015,-.02,-.025,-.03];s5g=[-.01,-.02,-.03,-.04,-.05]
def near(g,v):
 i=g.index(v);return g[max(0,i-1):min(len(g),i+2)]
for sh in near(shg,best['shock_max']):
 for s5 in near(s5g,best['sox5_max']):
  cap,_=run(sh,s5,best['dxy_filter'],best['dxy_th']);vals.append(cap)
vals.sort()
out={'objective':'screen SOX x DXY signal combinations only; no buy/sell clock optimization','tested':len(rows),'best':best,'robustness':{'n':len(vals),'positive':sum(v>START for v in vals),'above90pct_best':sum(v>=.9*best['final'] for v in vals),'median':vals[len(vals)//2],'min':vals[0]},'top20':rows[:20],'best_curve':bc}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
