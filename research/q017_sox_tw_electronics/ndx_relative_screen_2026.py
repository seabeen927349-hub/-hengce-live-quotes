#!/usr/bin/env python3
import csv,json
from collections import defaultdict
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'ndx_relative_screen_2026';OUT.mkdir(parents=True,exist_ok=True)
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
sox=load(ARC/'sox_2026.csv');dxy=load(ARC/'dxy_2026.csv');ndx=load(ARC/'ndx_2026.csv')
sd=[d for d,_ in sox];dd=[d for d,_ in dxy];nd=[d for d,_ in ndx]
sr={sox[i][0]:sox[i][1]/sox[i-1][1]-1 for i in range(1,len(sox))};nr={ndx[i][0]:ndx[i][1]/ndx[i-1][1]-1 for i in range(1,len(ndx))}
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
 us=prev(sd,d);ux=prev(dd,d);un=prev(nd,d);sh=sr.get(us);nh=nr.get(un)
 if not us or not ux or not un or sh is None or nh is None:continue
 si=sd.index(us);di=dd.index(ux);ni=nd.index(un)
 if si<5 or di<5 or ni<5:continue
 s5=sox[si][1]/sox[si-5][1]-1;d5=dxy[di][1]/dxy[di-5][1]-1;n5=ndx[ni][1]/ndx[ni-5][1]-1
 feat[d]={'sox1':sh,'sox5':s5,'dxy5':d5,'ndx1':nh,'ndx5':n5,'rel1':sh-nh,'rel5':s5-n5}
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

def run(s5max,d5min,mode,th):
 cap=START;busy=None;curve=[]
 for d in md:
  if busy and d<=busy:continue
  ft=feat.get(d)
  if not ft or ft['sox1']>0 or ft['sox5']>s5max or ft['dxy5']<d5min:continue
  if mode!='none':
   v=ft[mode[:-2]];op=mode[-2:]
   if op=='le' and not v<=th:continue
   if op=='ge' and not v>=th:continue
  i=mi[d]
  if i+10>=len(md) or not cand.get(d):continue
  _,t,opx,b,res=cand[d][0];d9,d10,d11=md[i+8],md[i+9],md[i+10]
  mp={r['date']:r['close'] for r in by_t[t]};c9=mp.get(d9);c10=mp.get(d10);c11=mp.get(d11)
  if not c9 or not c10 or not c11:continue
  ext=c10>=c9;xd=d11 if ext else d10;raw=c11 if ext else c10;net=raw*(1-XS)/opx-1-COST;cap*=1+net;busy=xd
  curve.append({'entry':d,'ticker':t,'exit':xd,'net':net,'capital':cap,**ft})
 return cap,curve
rows=[];details={}
s5grid=[-.02,-.025,-.03,-.035,-.04,-.05];d5grid=[-.01,-.005,0,.005]
modes={'none':[0], 'rel1le':[-.06,-.05,-.04,-.03,-.02,-.015,-.01,-.005,0,.005,.01], 'rel1ge':[-.06,-.05,-.04,-.03,-.02,-.015,-.01,-.005,0,.005,.01], 'rel5le':[-.10,-.08,-.06,-.05,-.04,-.03,-.02,-.01,0,.01,.02], 'rel5ge':[-.10,-.08,-.06,-.05,-.04,-.03,-.02,-.01,0,.01,.02]}
for s5 in s5grid:
 for d5 in d5grid:
  for mode,ths in modes.items():
   for th in ths:
    cap,curve=run(s5,d5,mode,th);key=(s5,d5,mode,th);details[key]=curve;rows.append({'sox5_max':s5,'dxy5_min':d5,'relative_filter':mode,'threshold':th,'final':cap,'ret':cap/START-1,'events':len(curve),'wins':sum(e['net']>0 for e in curve)})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];key=(best['sox5_max'],best['dxy5_min'],best['relative_filter'],best['threshold']);curve=details[key]
# count exact-neighbor stable outcomes around best threshold within same mode, plus market-gate neighbors
same=[r for r in rows if r['relative_filter']==best['relative_filter'] and r['final']>=.95*best['final']]
out={'objective':'screen SOX relative-to-NDX shock as a new market combination; no buy/sell clock optimization','tested':len(rows),'best':best,'within95_same_family':len(same),'top30':rows[:30],'best_curve':curve}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
