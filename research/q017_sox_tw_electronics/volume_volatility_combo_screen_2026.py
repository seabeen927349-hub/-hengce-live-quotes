#!/usr/bin/env python3
import csv,json,math,statistics
from collections import defaultdict
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'volume_volatility_combo_screen_2026';OUT.mkdir(parents=True,exist_ok=True)
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
 o=f(r.get('open'));h=f(r.get('high'));l=f(r.get('low'));c=f(r.get('close'));v=f(r.get('volume_shares'));ntd=f(r.get('turnover_ntd'))
 if o is None or c is None:continue
 x={'date':r['date'],'ticker':r['ticker'],'open':o,'high':h,'low':l,'close':c,'vol':v,'ntd':ntd};by_t[r['ticker']].append(x);by_d[r['date']].append(x)
for t in by_t:by_t[t].sort(key=lambda x:x['date'])
md=sorted(by_d);mi={d:i for i,d in enumerate(md)};aligned={d:sret.get(prev(sd,d)) for d in md};beta={};prevc={};fac={}
for t,rs in by_t.items():
 obs=[];pc=None
 for i,r in enumerate(rs):
  d=r['date'];prevc[(d,t)]=pc;sh=aligned.get(d)
  if i>=20:
   prev20=rs[i-20:i];prev5=rs[i-5:i]
   vols20=[x['vol'] for x in prev20 if x['vol'] and x['vol']>0];vols5=[x['vol'] for x in prev5 if x['vol'] and x['vol']>0]
   ntd20=[x['ntd'] for x in prev20 if x['ntd'] and x['ntd']>0]
   rets=[]
   for j in range(1,len(prev20)):
    if prev20[j-1]['close']>0:rets.append(prev20[j]['close']/prev20[j-1]['close']-1)
   pr=rs[i-1]
   range1=((pr['high']-pr['low'])/pr['close']) if pr['high'] is not None and pr['low'] is not None and pr['close'] else None
   fac[(d,t)]={
    'vol_ratio_5_20':(sum(vols5)/len(vols5))/(sum(vols20)/len(vols20)) if vols5 and vols20 else None,
    'turnover20':sum(ntd20)/len(ntd20) if ntd20 else None,
    'volatility20':statistics.pstdev(rets) if len(rets)>=10 else None,
    'range1':range1
   }
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

def passf(d,t,metric,side,th):
 if metric=='none':return True
 v=fac.get((d,t),{}).get(metric)
 if v is None:return False
 return v<=th if side=='le' else v>=th

def run(metric='none',side='ge',th=0):
 cap=START;busy=None;curve=[]
 for d in md:
  if busy and d<=busy:continue
  ft=feat.get(d)
  if not ft or ft['shock']>0 or ft['sox5'] is None or ft['sox5']>-.03 or ft['dxy5'] is None or ft['dxy5']<-.005:continue
  i=mi[d]
  if i+10>=len(md):continue
  z=[]
  for r in by_d[d]:
   t=r['ticker'];b=beta.get((d,t));pc=prevc.get((d,t))
   if b is None or b<=0 or not pc or not passf(d,t,metric,side,th):continue
   res=r['open']/pc-1-b*ft['shock']
   if res<=RESMAX:z.append((b*(1+K*max(-res,0)),t,r['open'],b,res))
  if not z:continue
  z.sort(reverse=True);_,t,op,b,res=z[0];d9,d10,d11=md[i+8],md[i+9],md[i+10];mp={x['date']:x['close'] for x in by_t[t]};c9,c10,c11=mp.get(d9),mp.get(d10),mp.get(d11)
  if not c9 or not c10 or not c11:continue
  ext=c10>=c9;xd=d11 if ext else d10;raw=c11 if ext else c10;net=raw*(1-XS)/op-1-COST;cap*=1+net;busy=xd
  curve.append({'entry':d,'ticker':t,'exit':xd,'net':net,'capital':cap,'factor':fac.get((d,t)),'beta':b,'resid':res})
 return cap,curve
specs=[('none','ge',0)]
for th in (.5,.75,1.0,1.25,1.5,2.0):specs += [('vol_ratio_5_20','ge',th),('vol_ratio_5_20','le',th)]
for th in (5e7,1e8,2e8,5e8,1e9,2e9):specs += [('turnover20','ge',th),('turnover20','le',th)]
for th in (.015,.02,.025,.03,.04,.05,.06):specs += [('volatility20','ge',th),('volatility20','le',th)]
for th in (.015,.02,.03,.04,.05,.07,.10):specs += [('range1','ge',th),('range1','le',th)]
rows=[];details={}
for m,s,th in specs:
 cap,curve=run(m,s,th);key=f'{m}_{s}_{th}';details[key]=curve;rows.append({'metric':m,'side':s,'threshold':th,'final':cap,'ret':cap/START-1,'events':len(curve),'wins':sum(x['net']>0 for x in curve)})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];base=next(x for x in rows if x['metric']=='none');bc=details[f"{best['metric']}_{best['side']}_{best['threshold']}"]
same=sorted([x for x in rows if x['metric']==best['metric'] and x['side']==best['side']],key=lambda x:abs(math.log((x['threshold']+1e-12)/(best['threshold']+1e-12))) if x['threshold']>0 and best['threshold']>0 else abs(x['threshold']-best['threshold']))[:3] if best['metric']!='none' else [best]
out={'objective':'screen prior-known stock volume/volatility/liquidity filters inside validated SOX5 x DXY5 gate; no timing optimization','baseline':base,'tested':len(rows),'best':best,'improvement':best['final']-base['final'],'local_same_family':same,'top25':rows[:25],'best_curve':bc}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
