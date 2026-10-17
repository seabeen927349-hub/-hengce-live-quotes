#!/usr/bin/env python3
import csv,json
from collections import defaultdict
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'vix_regime_screen_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;COST=.006;XS=.002;K=25;RESMAX=.04

def f(x):
 try:return float(str(x).replace(',','').strip())
 except:return None
def load(p):
 a=[]
 for r in csv.DictReader(p.open(encoding='utf-8')):
  c=f(r['close'])
  if c is not None:a.append((r['date'],c))
 a.sort();return a
sox=load(ARC/'sox_2026.csv');dxy=load(ARC/'dxy_2026.csv');vix=load(ARC/'vix_2026.csv')
sd=[d for d,_ in sox];dd=[d for d,_ in dxy];vd=[d for d,_ in vix]
sr={sox[i][0]:sox[i][1]/sox[i-1][1]-1 for i in range(1,len(sox))};vr={vix[i][0]:vix[i][1]/vix[i-1][1]-1 for i in range(1,len(vix))}
def prev(ds,d):
 z=[u for u in ds if u<d];return z[-1] if z else None
by_t=defaultdict(list);by_d=defaultdict(list)
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
 o=f(r['open']);c=f(r['close'])
 if o is None or c is None:continue
 x={'date':r['date'],'ticker':r['ticker'],'open':o,'close':c};by_t[r['ticker']].append(x);by_d[r['date']].append(x)
for t in by_t:by_t[t].sort(key=lambda x:x['date'])
md=sorted(by_d);mi={d:i for i,d in enumerate(md)};aligned={d:sr.get(prev(sd,d)) for d in md};beta={};prevc={}
for t,rs in by_t.items():
 obs=[];pc=None
 for r in rs:
  d=r['date'];prevc[(d,t)]=pc;sh=aligned.get(d)
  if pc and sh is not None:
   tr=r['close']/pc-1
   if len(obs)>=30:
    z=obs[-60:];mx=sum(a for a,b in z)/len(z);my=sum(b for a,b in z)/len(z);vv=sum((a-mx)**2 for a,b in z)
    beta[(d,t)]=sum((a-mx)*(b-my) for a,b in z)/vv if vv else 0
   obs.append((sh,tr))
  pc=r['close']
feat={}
for d in md:
 us=prev(sd,d);ux=prev(dd,d);uv=prev(vd,d);sh=sr.get(us)
 if not us or not ux or not uv or sh is None:continue
 si=sd.index(us);di=dd.index(ux);vi=vd.index(uv)
 if si<5 or di<5 or vi<5:continue
 feat[d]={'sox1':sh,'sox5':sox[si][1]/sox[si-5][1]-1,'dxy5':dxy[di][1]/dxy[di-5][1]-1,'vix':vix[vi][1],'vix1':vr.get(uv),'vix5':vix[vi][1]/vix[vi-5][1]-1}
cand={}
for d in md:
 ft=feat.get(d);z=[]
 if not ft:continue
 for r in by_d[d]:
  t=r['ticker'];b=beta.get((d,t));pc=prevc.get((d,t))
  if b is None or b<=0 or not pc:continue
  res=r['open']/pc-1-b*ft['sox1']
  if res<=RESMAX:z.append((b*(1+K*max(-res,0)),t,r['open'],b,res))
 z.sort(reverse=True);cand[d]=z

def passf(ft,mode,th):
 if mode=='none':return True
 if mode.endswith('ge'):return ft[mode[:-2]]>=th
 return ft[mode[:-2]]<=th

def run(mode,th):
 cap=START;busy=None;curve=[]
 for d in md:
  if busy and d<=busy:continue
  ft=feat.get(d)
  if not ft or ft['sox1']>0 or ft['sox5']>-.03 or ft['dxy5']<-.005 or not passf(ft,mode,th):continue
  i=mi[d]
  if i+10>=len(md) or not cand.get(d):continue
  _,t,op,b,res=cand[d][0];d9,d10,d11=md[i+8],md[i+9],md[i+10];mp={r['date']:r['close'] for r in by_t[t]};c9,c10,c11=mp.get(d9),mp.get(d10),mp.get(d11)
  if not c9 or not c10 or not c11:continue
  ext=c10>=c9;xd=d11 if ext else d10;raw=c11 if ext else c10;net=raw*(1-XS)/op-1-COST;cap*=1+net;busy=xd
  curve.append({'entry':d,'ticker':t,'exit':xd,'net':net,'capital':cap,'vix':ft['vix'],'vix1':ft['vix1'],'vix5':ft['vix5']})
 return cap,curve
modes={'none':[0],
 'vixge':[15,17,18,19,20,22,25,30], 'vixle':[15,17,18,19,20,22,25,30,35],
 'vix1ge':[-.2,-.1,-.05,0,.05,.1,.15,.2,.3,.4], 'vix1le':[-.2,-.1,-.05,0,.05,.1,.15,.2,.3,.4],
 'vix5ge':[-.3,-.2,-.1,-.05,0,.05,.1,.2,.3,.5], 'vix5le':[-.3,-.2,-.1,-.05,0,.05,.1,.2,.3,.5]}
rows=[];details={}
for mode,ths in modes.items():
 for th in ths:
  cap,curve=run(mode,th);details[(mode,th)]=curve;rows.append({'filter':mode,'threshold':th,'final':cap,'ret':cap/START-1,'events':len(curve),'wins':sum(e['net']>0 for e in curve)})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];curve=details[(best['filter'],best['threshold'])]
# robustness in same family = count configs within 95% of best; top config must beat no-filter materially to proceed causal
base=next(r for r in rows if r['filter']=='none')
same=[r for r in rows if r['filter']==best['filter']]
out={'objective':'screen VIX regime as third market factor on validated SOX5 x DXY5 gate; no buy/sell timing optimization','baseline':base,'tested':len(rows),'best':best,'improvement':best['final']-base['final'],'same_family_within95pct_best':sum(r['final']>=.95*best['final'] for r in same),'top30':rows[:30],'best_curve':curve}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
