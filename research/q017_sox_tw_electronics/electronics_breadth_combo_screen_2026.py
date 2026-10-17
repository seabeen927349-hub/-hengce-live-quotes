#!/usr/bin/env python3
import csv,json,statistics
from collections import defaultdict
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'electronics_breadth_combo_screen_2026';OUT.mkdir(parents=True,exist_ok=True)
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
by_t=defaultdict(dict);by_d=defaultdict(list)
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
 o=f(r['open']);c=f(r['close'])
 if o is None or c is None:continue
 t=r['ticker'];d=r['date'];by_t[t][d]={'open':o,'close':c};by_d[d].append({'ticker':t,'open':o,'close':c})
md=sorted(by_d);mi={d:i for i,d in enumerate(md)};aligned={d:sret.get(prev(sd,d)) for d in md}
# strictly prior beta
beta={};prevc={}
for t,mp in by_t.items():
 obs=[];pc=None
 for d in md:
  r=mp.get(d)
  if not r:continue
  prevc[(d,t)]=pc;sh=aligned.get(d)
  if pc and sh is not None:
   tr=r['close']/pc-1
   if len(obs)>=30:
    z=obs[-60:];mx=sum(a for a,b in z)/len(z);my=sum(b for a,b in z)/len(z);vv=sum((a-mx)**2 for a,b in z)
    beta[(d,t)]=sum((a-mx)*(b-my) for a,b in z)/vv if vv else 0
   obs.append((sh,tr))
  pc=r['close']
feat={}
for d in md:
 us=prev(sd,d);ux=prev(dd,d);sh=sret.get(us)
 if not us or sh is None or not ux:continue
 si=sd.index(us);di=dd.index(ux);s5=sox[si][1]/sox[si-5][1]-1 if si>=5 else None;dx5=dxy[di][1]/dxy[di-5][1]-1 if di>=5 else None
 feat[d]={'shock':sh,'sox5':s5,'dxy5':dx5}
# market breadth, all ending at previous Taiwan close only
breadth={}
for i,d in enumerate(md):
 if i<21:continue
 p1,p5=md[i-1],md[i-6]
 r1=[];r5=[];above20=[]
 for t,mp in by_t.items():
  if p1 in mp and md[i-2] in mp:
   r1.append(mp[p1]['close']/mp[md[i-2]]['close']-1)
  if p1 in mp and p5 in mp:
   r5.append(mp[p1]['close']/mp[p5]['close']-1)
  hist=[mp[x]['close'] for x in md[i-20:i] if x in mp]
  if p1 in mp and len(hist)>=15:
   above20.append(1.0 if mp[p1]['close']>sum(hist)/len(hist) else 0.0)
 if r5:
  breadth[d]={'up1_share':sum(x>0 for x in r1)/len(r1) if r1 else None,
              'up5_share':sum(x>0 for x in r5)/len(r5),
              'median5':statistics.median(r5),
              'above20_share':sum(above20)/len(above20) if above20 else None}
# candidates from current proven score
cand={}
for d in md:
 ft=feat.get(d);a=[]
 if not ft:continue
 for r in by_d[d]:
  t=r['ticker'];b=beta.get((d,t));pc=prevc.get((d,t))
  if b is None or b<=0 or not pc:continue
  res=r['open']/pc-1-b*ft['shock']
  if res<=RESMAX:a.append((b*(1+K*max(-res,0)),t,r['open'],b,res))
 a.sort(reverse=True);cand[d]=a

def gate_breadth(d,metric,side,th):
 if metric=='none':return True
 v=breadth.get(d,{}).get(metric)
 if v is None:return False
 return v<=th if side=='le' else v>=th

def run(metric='none',side='ge',th=0):
 cap=START;busy=None;curve=[]
 for d in md:
  if busy and d<=busy:continue
  ft=feat.get(d)
  if not ft or ft['shock']>0 or ft['sox5'] is None or ft['sox5']>-.03 or ft['dxy5'] is None or ft['dxy5']<-.005:continue
  if not gate_breadth(d,metric,side,th):continue
  i=mi[d]
  if i+10>=len(md) or not cand.get(d):continue
  _,t,op,b,res=cand[d][0];d9,d10,d11=md[i+8],md[i+9],md[i+10];mp=by_t[t]
  if any(x not in mp for x in (d9,d10,d11)):continue
  c9,c10,c11=mp[d9]['close'],mp[d10]['close'],mp[d11]['close'];ext=c10>=c9;xd=d11 if ext else d10;raw=c11 if ext else c10
  net=raw*(1-XS)/op-1-COST;cap*=1+net;busy=xd
  curve.append({'entry':d,'ticker':t,'exit':xd,'net':net,'capital':cap,'breadth':breadth.get(d),'beta':b,'resid':res})
 return cap,curve
specs=[('none','ge',0)]
for m in ('up1_share','up5_share','above20_share'):
 for th in (.20,.30,.40,.50,.60,.70,.80):
  specs += [(m,'le',th),(m,'ge',th)]
for th in (-.12,-.10,-.08,-.06,-.04,-.02,0,.02,.04):
 specs += [('median5','le',th),('median5','ge',th)]
rows=[];details={}
for m,s,th in specs:
 cap,curve=run(m,s,th);key=f'{m}_{s}_{th}';details[key]=curve;rows.append({'metric':m,'side':s,'threshold':th,'final':cap,'ret':cap/START-1,'events':len(curve),'wins':sum(x['net']>0 for x in curve)})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];bc=details[f"{best['metric']}_{best['side']}_{best['threshold']}"];base=next(x for x in rows if x['metric']=='none')
# robustness in same metric/side: nearest numeric thresholds by distance
same=sorted([x for x in rows if x['metric']==best['metric'] and x['side']==best['side']],key=lambda x:abs(x['threshold']-best['threshold']))[:3] if best['metric']!='none' else [best]
out={'objective':'screen prior-known Taiwan electronics breadth filters inside validated SOX5 x DXY5 gate; no timing optimization','baseline':base,'tested':len(rows),'best':best,'improvement':best['final']-base['final'],'local_same_family':same,'top20':rows[:20],'best_curve':bc}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
