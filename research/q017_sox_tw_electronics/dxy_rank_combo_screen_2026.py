#!/usr/bin/env python3
import csv,json
from collections import defaultdict
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'dxy_rank_combo_screen_2026';OUT.mkdir(parents=True,exist_ok=True)
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
md=sorted(by_d);mi={d:i for i,d in enumerate(md)};aligned={d:sret.get(prev(sd,d)) for d in md};beta={};prevc={}
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
 us=prev(sd,d);ux=prev(dd,d);sh=sret.get(us)
 if not us or sh is None or not ux:continue
 si=sd.index(us);di=dd.index(ux);s5=sox[si][1]/sox[si-5][1]-1 if si>=5 else None;d5=dxy[di][1]/dxy[di-5][1]-1 if di>=5 else None
 feat[d]={'shock':sh,'sox5':s5,'dxy5':d5}
rawcand={}
for d in md:
 ft=feat.get(d);a=[]
 if not ft:continue
 for r in by_d[d]:
  t=r['ticker'];b=beta.get((d,t));pc=prevc.get((d,t))
  if b is None or b<=0 or not pc:continue
  gap=r['open']/pc-1;res=gap-b*ft['shock'];a.append({'ticker':t,'open':r['open'],'beta':b,'resid':res})
 rawcand[d]=a

def sc(x,kind,k):
 b=x['beta'];res=x['resid'];neg=max(-res,0);pos=max(res,0)
 if kind=='beta_res':return b*(1+k*neg)
 if kind=='beta_res_sym':return b*(1+k*neg)/(1+k*pos)
 if kind=='res_only':return neg
 if kind=='beta_minus_pos':return b*(1+k*neg)-k*pos
 return b

def run(resmax,kind,k):
 cap=START;busy=None;curve=[]
 for d in md:
  if busy and d<=busy:continue
  ft=feat.get(d)
  if not ft or ft['shock']>0 or ft['sox5'] is None or ft['sox5']>-.03 or ft['dxy5'] is None or ft['dxy5']<-.005:continue
  i=mi[d]
  if i+10>=len(md):continue
  z=[x for x in rawcand.get(d,[]) if x['resid']<=resmax]
  if not z:continue
  z.sort(key=lambda x:sc(x,kind,k),reverse=True);x=z[0];t=x['ticker'];d9,d10,d11=md[i+8],md[i+9],md[i+10];mp={r['date']:r['close'] for r in by_t[t]};c9,c10,c11=mp.get(d9),mp.get(d10),mp.get(d11)
  if not c9 or not c10 or not c11:continue
  ext=c10>=c9;xd=d11 if ext else d10;raw=c11 if ext else c10;net=raw*(1-XS)/x['open']-1-COST;cap*=1+net;busy=xd
  curve.append({'entry':d,'ticker':t,'exit':xd,'net':net,'capital':cap,'beta':x['beta'],'resid':x['resid']})
 return cap,curve
rows=[];details={}
for rg in (.06,.05,.04,.03,.02,.01,0,-.01,-.02):
 for kind in ('beta','beta_res','beta_res_sym','res_only','beta_minus_pos'):
  for k in (0,10,25,50,75,100):
   cap,curve=run(rg,kind,k);key=f'{rg}_{kind}_{k}';details[key]=curve;rows.append({'resmax':rg,'rank':kind,'k':k,'final':cap,'ret':cap/START-1,'events':len(curve),'wins':sum(e['net']>0 for e in curve)})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];bc=details[f"{best['resmax']}_{best['rank']}_{best['k']}"]
# local neighborhood on resmax and k for best ranking family
rgs=[.06,.05,.04,.03,.02,.01,0,-.01,-.02];ks=[0,10,25,50,75,100]
def near(g,v):
 i=g.index(v);return g[max(0,i-1):min(len(g),i+2)]
vals=[]
for rg in near(rgs,best['resmax']):
 for k in near(ks,best['k']):vals.append(run(rg,best['rank'],k)[0])
vals.sort()
out={'objective':'screen selection/ranking combinations inside validated SOX5 x DXY5 market gate; no timing optimization','tested':len(rows),'best':best,'robustness':{'n':len(vals),'positive':sum(v>START for v in vals),'above90pct_best':sum(v>=.9*best['final'] for v in vals),'median':vals[len(vals)//2],'min':vals[0]},'top20':rows[:20],'best_curve':bc}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
