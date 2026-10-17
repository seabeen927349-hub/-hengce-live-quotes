#!/usr/bin/env python3
import csv,json
from collections import defaultdict
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'beta_momentum_combo_screen_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;COST=.006;XS=.002

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
md=sorted(by_d);mi={d:i for i,d in enumerate(md)};aligned={d:sret.get(prev(sd,d)) for d in md};prevc={};mom={};betas={w:{} for w in (30,40,60,80,100)}
for t,rs in by_t.items():
 obs=[];pc=None
 for i,r in enumerate(rs):
  d=r['date'];prevc[(d,t)]=pc;sh=aligned.get(d)
  for n in (5,10,20):
   if pc and i>=n and rs[i-n]['close']>0:mom[(d,t,n)]=pc/rs[i-n]['close']-1
  if pc and sh is not None:
   tr=r['close']/pc-1
   if len(obs)>=30:
    for w in betas:
     z=obs[-w:]
     if len(z)<30:continue
     mx=sum(a for a,b in z)/len(z);my=sum(b for a,b in z)/len(z);vv=sum((a-mx)**2 for a,b in z)
     betas[w][(d,t)]=sum((a-mx)*(b-my) for a,b in z)/vv if vv else 0
   obs.append((sh,tr))
  pc=r['close']
feat={}
for d in md:
 us=prev(sd,d);ux=prev(dd,d);sh=sret.get(us)
 if not us or sh is None or not ux:continue
 si=sd.index(us);di=dd.index(ux);s5=sox[si][1]/sox[si-5][1]-1 if si>=5 else None;d5=dxy[di][1]/dxy[di-5][1]-1 if di>=5 else None
 feat[d]={'shock':sh,'sox5':s5,'dxy5':d5}

def pass_mom(t,d,kind,th):
 if kind=='none':return True
 n=int(kind[1:kind.index('_')]);side=kind.split('_')[1];v=mom.get((d,t,n))
 if v is None:return False
 return v<=th if side=='le' else v>=th

def run(w,resmax,k,mkind,mth):
 cap=START;busy=None;curve=[]
 for d in md:
  if busy and d<=busy:continue
  ft=feat.get(d)
  if not ft or ft['shock']>0 or ft['sox5'] is None or ft['sox5']>-.03 or ft['dxy5'] is None or ft['dxy5']<-.005:continue
  i=mi[d]
  if i+10>=len(md):continue
  z=[]
  for r in by_d[d]:
   t=r['ticker'];b=betas[w].get((d,t));pc=prevc.get((d,t))
   if b is None or b<=0 or not pc or not pass_mom(t,d,mkind,mth):continue
   res=r['open']/pc-1-b*ft['shock']
   if res<=resmax:z.append((b*(1+k*max(-res,0)),t,r['open'],b,res))
  if not z:continue
  z.sort(reverse=True);_,t,op,b,res=z[0];d9,d10,d11=md[i+8],md[i+9],md[i+10];mp={r['date']:r['close'] for r in by_t[t]};c9,c10,c11=mp.get(d9),mp.get(d10),mp.get(d11)
  if not c9 or not c10 or not c11:continue
  ext=c10>=c9;xd=d11 if ext else d10;raw=c11 if ext else c10;net=raw*(1-XS)/op-1-COST;cap*=1+net;busy=xd
  curve.append({'entry':d,'ticker':t,'exit':xd,'net':net,'capital':cap,'beta':b,'resid':res,'m5':mom.get((d,t,5)),'m10':mom.get((d,t,10)),'m20':mom.get((d,t,20))})
 return cap,curve
mom_specs=[('none',0),('m5_le',0),('m5_le',-.05),('m5_ge',0),('m5_ge',.05),('m10_le',0),('m10_le',-.10),('m10_ge',0),('m10_ge',.10),('m20_le',0),('m20_le',-.10),('m20_ge',0),('m20_ge',.10)]
rows=[];details={}
for w in (30,40,60,80,100):
 for rg in (.03,.04,.05):
  for k in (15,25,35):
   for mk,mt in mom_specs:
    cap,curve=run(w,rg,k,mk,mt);key=f'{w}_{rg}_{k}_{mk}_{mt}';details[key]=curve;rows.append({'beta_window':w,'resmax':rg,'k':k,'mom_filter':mk,'mom_th':mt,'final':cap,'ret':cap/START-1,'events':len(curve),'wins':sum(e['net']>0 for e in curve)})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];key=f"{best['beta_window']}_{best['resmax']}_{best['k']}_{best['mom_filter']}_{best['mom_th']}";curve=details[key]
# robustness around beta/res/k for exact momentum family
wg=[30,40,60,80,100];rg=[.03,.04,.05];kg=[15,25,35]
def near(g,v):
 i=g.index(v);return g[max(0,i-1):min(len(g),i+2)]
vals=[]
for w in near(wg,best['beta_window']):
 for r in near(rg,best['resmax']):
  for k in near(kg,best['k']):vals.append(run(w,r,k,best['mom_filter'],best['mom_th'])[0])
vals.sort()
out={'objective':'screen beta-window and prior-momentum selection combinations inside validated SOX5 x DXY5 gate; no timing optimization','tested':len(rows),'best':best,'robustness':{'n':len(vals),'positive':sum(v>START for v in vals),'above90pct_best':sum(v>=.9*best['final'] for v in vals),'median':vals[len(vals)//2],'min':vals[0]},'top30':rows[:30],'best_curve':curve}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
