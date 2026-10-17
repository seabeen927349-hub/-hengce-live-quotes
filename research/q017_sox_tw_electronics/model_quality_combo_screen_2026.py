#!/usr/bin/env python3
import csv,json,math,statistics
from collections import defaultdict
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'model_quality_combo_screen_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;COST=.006;XS=.002;RESMAX=.04;K=25.
def f(x):
 try:return float(str(x).replace(',','').strip())
 except:return None
def load(path):
 a=[]
 for r in csv.DictReader(path.open(encoding='utf-8')):
  c=f(r['close'])
  if c is not None:a.append((r['date'],c))
 a.sort();return a
sox=load(ARC/'sox_2026.csv');dxy=load(ARC/'dxy_2026.csv');sd=[d for d,_ in sox];dd=[d for d,_ in dxy]
sret={sox[i][0]:sox[i][1]/sox[i-1][1]-1 for i in range(1,len(sox))}
def prev(ds,d):
 z=[u for u in ds if u<d];return z[-1] if z else None
by_t=defaultdict(list);by_d=defaultdict(list)
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
 o=f(r['open']);c=f(r['close'])
 if o is None or c is None:continue
 x={'date':r['date'],'ticker':r['ticker'],'open':o,'close':c};by_t[r['ticker']].append(x);by_d[r['date']].append(x)
for t in by_t:by_t[t].sort(key=lambda x:x['date'])
md=sorted(by_d);mi={d:i for i,d in enumerate(md)};aligned={d:sret.get(prev(sd,d)) for d in md};prevc={};qual={}
def reg(z):
 if len(z)<10:return None
 mx=sum(a for a,b in z)/len(z);my=sum(b for a,b in z)/len(z);vv=sum((a-mx)**2 for a,b in z)
 if vv<=0:return None
 b=sum((a-mx)*(y-my) for a,y in z)/vv;a=my-b*mx
 yh=[a+b*x for x,y in z];ssr=sum((y-p)**2 for (_,y),p in zip(z,yh));sst=sum((y-my)**2 for x,y in z)
 r2=1-ssr/sst if sst>0 else 0;idio=math.sqrt(ssr/len(z));return b,r2,idio
for t,rs in by_t.items():
 obs=[];pc=None
 for r in rs:
  d=r['date'];prevc[(d,t)]=pc;sh=aligned.get(d)
  if pc and sh is not None:
   tr=r['close']/pc-1
   if len(obs)>=30:
    r60=reg(obs[-60:]);r20=reg(obs[-20:]) if len(obs)>=20 else None
    if r60:
     b60,r2,idio=r60;b20=r20[0] if r20 else None
     stab=abs(b20-b60)/(abs(b60)+1e-9) if b20 is not None else None
     qual[(d,t)]={'beta':b60,'r2':r2,'idio':idio,'beta_stability':stab,'beta20':b20}
   obs.append((sh,tr))
  pc=r['close']
feat={}
for d in md:
 us=prev(sd,d);ux=prev(dd,d);sh=sret.get(us)
 if not us or sh is None or not ux:continue
 si=sd.index(us);di=dd.index(ux);s5=sox[si][1]/sox[si-5][1]-1 if si>=5 else None;dx5=dxy[di][1]/dxy[di-5][1]-1 if di>=5 else None
 feat[d]={'shock':sh,'sox5':s5,'dxy5':dx5}

def passq(q,metric,side,th):
 if metric=='none':return True
 v=q.get(metric)
 if v is None:return False
 return v<=th if side=='le' else v>=th

def run(metric='none',side='ge',th=0,bonus=0):
 cap=START;busy=None;curve=[]
 for d in md:
  if busy and d<=busy:continue
  ft=feat.get(d)
  if not ft or ft['shock']>0 or ft['sox5'] is None or ft['sox5']>-.03 or ft['dxy5'] is None or ft['dxy5']<-.005:continue
  i=mi[d]
  if i+10>=len(md):continue
  z=[]
  for r in by_d[d]:
   t=r['ticker'];q=qual.get((d,t));pc=prevc.get((d,t))
   if not q or q['beta']<=0 or not pc or not passq(q,metric,side,th):continue
   res=r['open']/pc-1-q['beta']*ft['shock']
   if res<=RESMAX:
    s=q['beta']*(1+K*max(-res,0))
    if metric=='r2' and bonus>0:s*=1+bonus*max(q['r2'],0)
    if metric=='idio' and bonus>0:s/=1+bonus*q['idio']
    if metric=='beta_stability' and bonus>0:s/=1+bonus*q['beta_stability']
    z.append((s,t,r['open'],q,res))
  if not z:continue
  z.sort(reverse=True,key=lambda x:x[0]);_,t,op,q,res=z[0];d9,d10,d11=md[i+8],md[i+9],md[i+10];mp={x['date']:x['close'] for x in by_t[t]};c9,c10,c11=mp.get(d9),mp.get(d10),mp.get(d11)
  if not c9 or not c10 or not c11:continue
  ext=c10>=c9;xd=d11 if ext else d10;raw=c11 if ext else c10;net=raw*(1-XS)/op-1-COST;cap*=1+net;busy=xd
  curve.append({'entry':d,'ticker':t,'exit':xd,'net':net,'capital':cap,'quality':q,'resid':res})
 return cap,curve
specs=[('none','ge',0,0)]
for th in (0,.05,.10,.15,.20,.25,.30,.40):specs.append(('r2','ge',th,0))
for th in (.02,.03,.04,.05,.06,.08,.10):specs += [('idio','le',th,0),('idio','ge',th,0)]
for th in (.1,.2,.3,.5,.75,1.0,1.5):specs += [('beta_stability','le',th,0),('beta_stability','ge',th,0)]
for b in (.5,1,2,3,5):specs += [('r2','ge',0,b),('idio','ge',0,b),('beta_stability','ge',0,b)]
rows=[];details={}
for m,s,th,b in specs:
 cap,curve=run(m,s,th,b);key=f'{m}_{s}_{th}_{b}';details[key]=curve;rows.append({'metric':m,'side':s,'threshold':th,'bonus':b,'final':cap,'ret':cap/START-1,'events':len(curve),'wins':sum(x['net']>0 for x in curve)})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];base=next(x for x in rows if x['metric']=='none');bc=details[f"{best['metric']}_{best['side']}_{best['threshold']}_{best['bonus']}"]
same=[x for x in rows if x['metric']==best['metric'] and x['side']==best['side'] and x['bonus']==best['bonus']]
near=sorted(same,key=lambda x:abs(x['threshold']-best['threshold']))[:4]
out={'objective':'screen SOX regression model-quality filters/weights inside validated SOX5 x DXY5 gate; no timing optimization','baseline':base,'tested':len(rows),'best':best,'improvement':best['final']-base['final'],'nearby_same_family':near,'top25':rows[:25],'best_curve':bc}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
