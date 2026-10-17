#!/usr/bin/env python3
import csv,json,math,os,time,urllib.parse,urllib.request
from collections import defaultdict
from datetime import datetime,timedelta,time as dtime
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'dxy_combo_causal_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;RESMAX=.04;K=25.;PART=.10;ES=.002;XS=.002;COST=.006;LAG=2;FILL=20;CUT=dtime(9,1)
API=os.environ.get('FUGLE_API_KEY')
if not API:raise SystemExit('FUGLE_API_KEY missing')
def f(x):
 try:return float(str(x).replace(',','').strip())
 except:return None
def dt(v):
 try:return datetime.fromisoformat(v)
 except:return None
def fetch(sym,d):
 base=f'https://api.fugle.tw/marketdata/v1.0/stock/historical/candles/{sym}';q=urllib.parse.urlencode({'timeframe':'1','from':d,'to':d,'fields':'open,high,low,close,volume,average','sort':'asc'})
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API,'Accept':'application/json','User-Agent':'HENGCE-Q017-DXY-CAUSAL/1.0'})
 for a in range(7):
  try:
   with urllib.request.urlopen(req,timeout=30) as rr:
    rows=json.load(rr).get('data',[])
    if rows:return rows
  except Exception:pass
  time.sleep(min(20,2**a))
 return []
def load(path):
 a=[]
 for r in csv.DictReader(path.open(encoding='utf-8')):
  c=f(r['close'])
  if c is not None:a.append((r['date'],c))
 a.sort();return a
sox=load(ARC/'sox_2026.csv');dxy=load(ARC/'dxy_2026.csv')
sd=[d for d,_ in sox];dd=[d for d,_ in dxy]
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
 si=sd.index(us);di=dd.index(ux)
 s5=sox[si][1]/sox[si-5][1]-1 if si>=5 else None;d5=dxy[di][1]/dxy[di-5][1]-1 if di>=5 else None
 feat[d]={'shock':sh,'sox5':s5,'dxy5':d5}
cand={}
for d in md:
 ft=feat.get(d);lst=[]
 if not ft:continue
 for r in by_d[d]:
  t=r['ticker'];b=beta.get((d,t));pc=prevc.get((d,t))
  if b is None or b<=0 or not pc:continue
  res=r['open']/pc-1-b*ft['shock']
  if res<=RESMAX:lst.append({'ticker':t,'score':b*(1+K*max(-res,0)),'beta':b,'resid':res})
 lst.sort(key=lambda x:x['score'],reverse=True);cand[d]=lst
cache={}
def mins(t,d):
 k=(t,d)
 if k not in cache:cache[k]=fetch(t,d);time.sleep(.18)
 return cache[k]
def first(rows):
 for x in rows:
  z=dt(x.get('date'))
  if z and dtime(9,0)<=z.time()<=CUT and f(x.get('open')) is not None:return x
 return None
def choose(d):
 for c in cand.get(d,[]):
  if first(mins(c['ticker'],d)):return c
 return None
def fill(c,d,capital):
 rows=mins(c['ticker'],d);fp=first(rows)
 if not fp:return 0,0.
 st=dt(fp['date'])+timedelta(minutes=LAG);en=st+timedelta(minutes=FILL);rem=capital;sh=0;spent=0.
 for x in rows:
  z=dt(x.get('date'))
  if not z or z<st or z>en:continue
  raw=f(x.get('open'));vol=f(x.get('volume')) or 0
  if not raw or vol<=0:continue
  px=raw*(1+ES);lots=min(math.floor(vol*PART),math.floor(rem/(px*1000)))
  if lots<=0:continue
  inv=lots*1000*px;rem-=inv;sh+=lots*1000;spent+=inv
 return sh,spent
def close(t,d):
 r=next((x for x in by_t[t] if x['date']==d),None);return r['close'] if r else None
def p1300(t,d):
 for x in mins(t,d):
  z=dt(x.get('date'))
  if z and z.time()>=dtime(13,0):
   p=f(x.get('open'))
   if p:return p
 return None
# DXY threshold None = baseline with no DXY filter.
def run(shock_max,sox5_max,dxy5_min):
 cap=START;busy=None;curve=[]
 for d in md:
  if busy and d<=busy:continue
  ft=feat.get(d)
  if not ft or ft['shock']>shock_max or ft['sox5'] is None or ft['sox5']>sox5_max:continue
  if dxy5_min is not None and (ft['dxy5'] is None or ft['dxy5']<dxy5_min):continue
  i=mi[d]
  if i+10>=len(md):continue
  d9,d10,d11=md[i+8],md[i+9],md[i+10];c=choose(d)
  if not c:continue
  sh,spent=fill(c,d,cap)
  if sh<=0:continue
  avg=spent/sh;p=p1300(c['ticker'],d10);c9=close(c['ticker'],d9);c10=close(c['ticker'],d10);c11=close(c['ticker'],d11)
  if not c9 or not c10 or not c11:continue
  extend=p is not None and p>=c9;xd=d11 if extend else d10;raw=c11 if extend else c10;net=raw*(1-XS)/avg-1-COST;pnl=spent*net;cap+=pnl;busy=xd
  curve.append({'entry':d,'exit':xd,'ticker':c['ticker'],'extend':extend,'shock':ft['shock'],'sox5':ft['sox5'],'dxy5':ft['dxy5'],'beta':c['beta'],'resid':c['resid'],'net':net,'capital':cap})
 return {'final':cap,'ret':cap/START-1,'events':len(curve),'wins':sum(e['net']>0 for e in curve),'curve':curve}
shock_grid=[0,-.005,-.01,-.015,-.02]
sox5_grid=[-.02,-.025,-.03,-.035,-.04]
dxy_grid=[None,-.005,0,.005,.01]
rows=[];details={}
for sh in shock_grid:
 for s5 in sox5_grid:
  for dx in dxy_grid:
   r=run(sh,s5,dx);key=f'{sh}_{s5}_{dx}';details[key]=r['curve'];rows.append({'shock_max':sh,'sox5_max':s5,'dxy5_min':'NONE' if dx is None else dx,'final':r['final'],'ret':r['ret'],'events':r['events'],'wins':r['wins']})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];bd=None if best['dxy5_min']=='NONE' else float(best['dxy5_min']);br=run(best['shock_max'],best['sox5_max'],bd)
def near(g,v):
 i=g.index(v);return g[max(0,i-1):min(len(g),i+2)]
vals=[]
for sh in near(shock_grid,best['shock_max']):
 for s5 in near(sox5_grid,best['sox5_max']):
  for dx in near(dxy_grid,bd):vals.append(run(sh,s5,dx)['final'])
vals.sort()
base=run(0,-.02,None)
out={'objective':'validate SOX x DXY combinations only; buy/sell timing fixed','contract':{'entry':'09:01 causal candidate; first print +2m; 20m fill; 10% minute participation; 0.2% entry slip','exit':'D10 13:00 vs D9 close; strong=>D11 close, weak=>D10 close; 0.2% exit slip','cost':COST},'baseline':{k:v for k,v in base.items() if k!='curve'},'tested':len(rows),'best':best,'improvement_vs_baseline':best['final']-base['final'],'robustness':{'n':len(vals),'positive':sum(v>START for v in vals),'above90pct_best':sum(v>=.9*best['final'] for v in vals),'median':vals[len(vals)//2],'min':vals[0]},'top20':rows[:20],'best_curve':br['curve']}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
