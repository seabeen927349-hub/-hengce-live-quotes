#!/usr/bin/env python3
import csv,json
from collections import defaultdict
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'pullback_trend_combo_screen_2026';OUT.mkdir(parents=True,exist_ok=True)
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
md=sorted(by_d);mi={d:i for i,d in enumerate(md)};aligned={d:sret.get(prev(sd,d)) for d in md};beta={};prevc={};mom={}
for t,rs in by_t.items():
 obs=[];pc=None
 for i,r in enumerate(rs):
  d=r['date'];prevc[(d,t)]=pc;sh=aligned.get(d)
  for n in (5,10,20):
   if pc and i>=n and rs[i-n]['close']>0:mom[(d,t,n)]=pc/rs[i-n]['close']-1
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

def passes(t,d,kind):
 m5=mom.get((d,t,5));m10=mom.get((d,t,10));m20=mom.get((d,t,20))
 if kind=='none':return True
 if None in (m5,m10,m20):return False
 if kind=='p5_t10':return m5<=0 and m10>=0
 if kind=='p5_t20':return m5<=0 and m20>=0
 if kind=='p5_t10_t20':return m5<=0 and m10>=0 and m20>=0
 if kind=='p2_t5':return m5<=-.02 and m10>=.05
 if kind=='p5_t10p10':return m5<=-.05 and m10>=.10
 if kind=='p5_t20p10':return m5<=-.05 and m20>=.10
 return True

def bonus(t,d,a,b):
 m5=mom.get((d,t,5)) or 0;m10=mom.get((d,t,10)) or 0;m20=mom.get((d,t,20)) or 0
 return (1+a*max(-m5,0))*(1+b*max(m10,0))*(1+0.5*b*max(m20,0))
def run(kind,a,b):
 cap=START;busy=None;curve=[]
 for d in md:
  if busy and d<=busy:continue
  ft=feat.get(d)
  if not ft or ft['shock']>0 or ft['sox5'] is None or ft['sox5']>-.03 or ft['dxy5'] is None or ft['dxy5']<-.005:continue
  i=mi[d]
  if i+10>=len(md):continue
  z=[]
  for r in by_d[d]:
   t=r['ticker'];bb=beta.get((d,t));pc=prevc.get((d,t))
   if bb is None or bb<=0 or not pc or not passes(t,d,kind):continue
   res=r['open']/pc-1-bb*ft['shock']
   if res<=RESMAX:
    base=bb*(1+K*max(-res,0));z.append((base*bonus(t,d,a,b),t,r['open'],bb,res))
  if not z:continue
  z.sort(reverse=True);_,t,op,bb,res=z[0];d9,d10,d11=md[i+8],md[i+9],md[i+10];mp={x['date']:x['close'] for x in by_t[t]};c9,c10,c11=mp.get(d9),mp.get(d10),mp.get(d11)
  if not c9 or not c10 or not c11:continue
  ext=c10>=c9;xd=d11 if ext else d10;raw=c11 if ext else c10;net=raw*(1-XS)/op-1-COST;cap*=1+net;busy=xd
  curve.append({'entry':d,'ticker':t,'exit':xd,'net':net,'capital':cap,'m5':mom.get((d,t,5)),'m10':mom.get((d,t,10)),'m20':mom.get((d,t,20)),'beta':bb,'resid':res})
 return cap,curve
rows=[];details={}
for kind in ('none','p5_t10','p5_t20','p5_t10_t20','p2_t5','p5_t10p10','p5_t20p10'):
 for a in (0,1,2,3,5,8):
  for b in (0,.5,1,2,3):
   cap,curve=run(kind,a,b);key=f'{kind}_{a}_{b}';details[key]=curve;rows.append({'filter':kind,'pullback_bonus':a,'trend_bonus':b,'final':cap,'ret':cap/START-1,'events':len(curve),'wins':sum(x['net']>0 for x in curve)})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];bc=details[f"{best['filter']}_{best['pullback_bonus']}_{best['trend_bonus']}"];base=next(x for x in rows if x['filter']=='none' and x['pullback_bonus']==0 and x['trend_bonus']==0)
# robust family around bonus coefficients for winning filter
same=[x for x in rows if x['filter']==best['filter']];near=sorted(same,key=lambda x:abs(x['pullback_bonus']-best['pullback_bonus'])+abs(x['trend_bonus']-best['trend_bonus']))[:9]
out={'objective':'screen medium-term uptrend plus short-term pullback selection combinations inside validated SOX5 x DXY5 gate; no timing optimization','baseline':base,'tested':len(rows),'best':best,'improvement':best['final']-base['final'],'nearby_same_filter':near,'top30':rows[:30],'best_curve':bc}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
