#!/usr/bin/env python3
import csv,json,math,os,time,urllib.parse,urllib.request
from collections import defaultdict
from datetime import datetime,timedelta,time as dtime
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'runner_horizon_causal_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;SOX5_MAX=-.02;RESMAX=.04;K=25.;PART=.10;ES=.002;XS=.002;COST=.006;LAG=2;FILL=20;CUT=dtime(9,1)
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
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API,'Accept':'application/json','User-Agent':'HENGCE-Q017-RUNNER-HORIZON/1.0'})
 for a in range(7):
  try:
   with urllib.request.urlopen(req,timeout=30) as rr:
    rows=json.load(rr).get('data',[])
    if rows:return rows
  except Exception:pass
  time.sleep(min(30,2**a))
 return []
sox=[]
for r in csv.DictReader((ARC/'sox_2026.csv').open(encoding='utf-8')):
 c=f(r['close']);
 if c is not None:sox.append((r['date'],c))
sox.sort();sd=[d for d,_ in sox];sret={sox[i][0]:sox[i][1]/sox[i-1][1]-1 for i in range(1,len(sox))}
def prevus(d):
 z=[u for u in sd if u<d];return z[-1] if z else None
by_t=defaultdict(list);by_d=defaultdict(list)
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
 o=f(r['open']);c=f(r['close'])
 if o is None or c is None:continue
 x={'date':r['date'],'ticker':r['ticker'],'open':o,'close':c};by_t[r['ticker']].append(x);by_d[r['date']].append(x)
for t in by_t:by_t[t].sort(key=lambda x:x['date'])
mdates=sorted(by_d);mi={d:i for i,d in enumerate(mdates)};aligned={d:sret.get(prevus(d)) for d in mdates};beta={};prevc={}
for t,rs in by_t.items():
 obs=[];pc=None
 for r in rs:
  prevc[(r['date'],t)]=pc;sh=aligned.get(r['date'])
  if pc and sh is not None:
   tr=r['close']/pc-1
   if len(obs)>=30:
    z=obs[-60:];mx=sum(a for a,b in z)/len(z);my=sum(b for a,b in z)/len(z);vv=sum((a-mx)**2 for a,b in z)
    beta[(r['date'],t)]=sum((a-mx)*(b-my) for a,b in z)/vv if vv else 0
   obs.append((sh,tr))
  pc=r['close']
feat={}
for d in mdates:
 u=prevus(d);sh=aligned.get(d)
 if not u or sh is None:continue
 ui=sd.index(u);r5=sox[ui][1]/sox[ui-5][1]-1 if ui>=5 else None;feat[d]={'shock':sh,'sox5':r5}
ranked={}
for d in mdates:
 ft=feat.get(d);lst=[]
 if ft and ft['shock']<=0 and ft['sox5'] is not None and ft['sox5']<=SOX5_MAX:
  for r in by_d[d]:
   b=beta.get((d,r['ticker']));pc=prevc.get((d,r['ticker']))
   if b is None or b<=0 or not pc:continue
   res=r['open']/pc-1-b*ft['shock']
   if res<=RESMAX:lst.append({'ticker':r['ticker'],'score':b*(1+K*max(-res,0)),'beta':b,'resid':res})
  lst.sort(key=lambda x:x['score'],reverse=True)
 ranked[d]=lst
cache={};selcache={}
def mins(t,d):
 k=(t,d)
 if k not in cache:cache[k]=fetch(t,d);time.sleep(.3)
 return cache[k]
def first(rows):
 for x in rows:
  z=dt(x.get('date'))
  if z and dtime(9,0)<=z.time()<=CUT and f(x.get('open')) is not None:return x
 return None
def select(d):
 if d in selcache:return selcache[d]
 for c in ranked.get(d,[]):
  fp=first(mins(c['ticker'],d))
  if fp:selcache[d]={**c,'fp':fp['date']};return selcache[d]
 selcache[d]=None;return None
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
# D10 13:00 positive-day signal proved robust at 0/2/5%; use the simplest sign test and optimize only runner horizon.
def run(ext_hold,day_threshold):
 cap=START;busy=None;curve=[]
 for d in mdates:
  if busy and d<=busy:continue
  ft=feat.get(d)
  if not ft or ft['shock']>0 or ft['sox5'] is None or ft['sox5']>SOX5_MAX:continue
  i=mi[d]
  if i+ext_hold-1>=len(mdates):continue
  d9=mdates[i+8];d10=mdates[i+9];dx=mdates[i+ext_hold-1];c=select(d)
  if not c:continue
  sh,spent=fill(c,d,cap)
  if sh<=0:continue
  avg=spent/sh;p=p1300(c['ticker'],d10);c9=close(c['ticker'],d9);c10=close(c['ticker'],d10);cx=close(c['ticker'],dx)
  if not c10 or not cx:continue
  day13=(p/c9-1) if p and c9 else None;extend=day13 is not None and day13>=day_threshold;xd=dx if extend else d10;raw=cx if extend else c10;net=raw*(1-XS)/avg-1-COST;pnl=spent*net;before=cap;cap+=pnl;busy=xd
  curve.append({'entry':d,'exit':xd,'ticker':c['ticker'],'extend':extend,'day13':day13,'capital_before':before,'spent':spent,'avg_entry':avg,'raw_exit':raw,'net':net,'capital':cap})
 return {'extend_hold':ext_hold,'day_threshold':day_threshold,'final':cap,'ret':cap/START-1,'events':len(curve),'extended':sum(e['extend'] for e in curve),'wins':sum(e['net']>0 for e in curve),'curve':curve}
rows=[];details={}
for h in (11,12,13,14,15):
 for th in (0,.02,.05):
  r=run(h,th);k=f'{h}_{th}';details[k]=r['curve'];rows.append({x:y for x,y in r.items() if x!='curve'})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];bf=best['final']
out={'objective':'maximize executable 2M terminal capital by D10 13:00 positive-day runner horizon only','tested':len(rows),'best':best,'best_is_horizon_boundary':best['extend_hold'] in (11,15),'within_99pct_best':sum(x['final']>=.99*bf for x in rows),'within_95pct_best':sum(x['final']>=.95*bf for x in rows),'grid':rows,'best_curve':details[f"{best['extend_hold']}_{best['day_threshold']}"]}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
