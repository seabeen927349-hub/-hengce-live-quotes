#!/usr/bin/env python3
import csv,json,math,os,time,urllib.parse,urllib.request
from collections import defaultdict
from datetime import datetime,timedelta,time as dtime
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'dual_sleeve_causal_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;SOX5=-.03;DXY5=-.005;RES=.04;K=25.;PART=.10;ES=.002;XS=.002;COST=.006;CUT=dtime(9,1);LAG=2;FILL=20
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
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API,'Accept':'application/json','User-Agent':'HENGCE-Q017-DUAL/1.0'})
 for a in range(7):
  try:
   with urllib.request.urlopen(req,timeout=30) as rr:
    rows=json.load(rr).get('data',[])
    if rows:return rows
  except Exception:pass
  time.sleep(min(20,2**a))
 return []
def load(p):
 a=[]
 for r in csv.DictReader(p.open(encoding='utf-8')):
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
 if not us or not ux or sh is None:continue
 si=sd.index(us);di=dd.index(ux)
 if si<5 or di<5:continue
 feat[d]={'shock':sh,'sox5':sox[si][1]/sox[si-5][1]-1,'dxy5':dxy[di][1]/dxy[di-5][1]-1}
ranked={}
for d in md:
 ft=feat.get(d);z=[]
 if not ft or ft['shock']>0 or ft['sox5']>SOX5 or ft['dxy5']<DXY5:ranked[d]=[];continue
 for r in by_d[d]:
  t=r['ticker'];b=beta.get((d,t));pc=prevc.get((d,t))
  if b is None or b<=0 or not pc:continue
  res=r['open']/pc-1-b*ft['shock']
  if res<=RES:z.append({'ticker':t,'score':b*(1+K*max(-res,0)),'beta':b,'resid':res})
 z.sort(key=lambda x:x['score'],reverse=True);ranked[d]=z
cache={};selcache={}
def mins(t,d):
 k=(t,d)
 if k not in cache:cache[k]=fetch(t,d);time.sleep(.18)
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
  if fp:selcache[d]={**c,'first_print':fp['date']};return selcache[d]
 selcache[d]=None;return None
def fill(c,d,capital):
 if capital<=0:return None
 rows=mins(c['ticker'],d);fp=first(rows)
 if not fp:return None
 st=dt(fp['date'])+timedelta(minutes=LAG);en=st+timedelta(minutes=FILL);rem=capital;shares=0;spent=0.
 for x in rows:
  z=dt(x.get('date'))
  if not z or z<st or z>en:continue
  raw=f(x.get('open'));vol=f(x.get('volume')) or 0
  if not raw or vol<=0:continue
  px=raw*(1+ES);lots=min(math.floor(vol*PART),math.floor(rem/(px*1000)))
  if lots<=0:continue
  inv=lots*1000*px;rem-=inv;shares+=lots*1000;spent+=inv
 return {'shares':shares,'spent':spent,'avg':spent/shares if shares else None}
def close(t,d):
 r=next((x for x in by_t[t] if x['date']==d),None);return r['close'] if r else None
def p1300(t,d):
 for x in mins(t,d):
  z=dt(x.get('date'))
  if z and z.time()>=dtime(13,0):
   p=f(x.get('open'))
   if p:return p
 return None
def one_sleeve():
 cap=START;busy=None;curve=[]
 for d in md:
  if busy and d<=busy:continue
  if not ranked.get(d):continue
  i=mi[d]
  if i+10>=len(md):continue
  c=select(d)
  if not c:continue
  fi=fill(c,d,cap)
  if not fi or fi['shares']<=0:continue
  d9,d10,d11=md[i+8],md[i+9],md[i+10];p=p1300(c['ticker'],d10);c9=close(c['ticker'],d9);c10=close(c['ticker'],d10);c11=close(c['ticker'],d11)
  if p is None or not c9 or not c10 or not c11:continue
  ext=p>=c9;xd=d11 if ext else d10;raw=c11 if ext else c10;net=raw*(1-XS)/fi['avg']-1-COST;pnl=fi['spent']*net;cap+=pnl;busy=xd;curve.append({'entry':d,'ticker':c['ticker'],'sleeve':0,'exit':xd,'net':net,'capital':cap,'spent':fi['spent']})
 return cap,curve
def dual(w0):
 caps=[START*w0,START*(1-w0)];busy=[None,None];curve=[]
 for d in md:
  if not ranked.get(d):continue
  free=[j for j in (0,1) if busy[j] is None or d>busy[j]]
  if not free:continue
  j=0 if 0 in free else 1
  if caps[j]<1000:continue
  i=mi[d]
  if i+10>=len(md):continue
  c=select(d)
  if not c:continue
  fi=fill(c,d,caps[j])
  if not fi or fi['shares']<=0:continue
  d9,d10,d11=md[i+8],md[i+9],md[i+10];p=p1300(c['ticker'],d10);c9=close(c['ticker'],d9);c10=close(c['ticker'],d10);c11=close(c['ticker'],d11)
  if p is None or not c9 or not c10 or not c11:continue
  ext=p>=c9;xd=d11 if ext else d10;raw=c11 if ext else c10;net=raw*(1-XS)/fi['avg']-1-COST;pnl=fi['spent']*net;caps[j]+=pnl;busy[j]=xd;curve.append({'entry':d,'ticker':c['ticker'],'sleeve':j,'exit':xd,'net':net,'capital_after':caps[j],'spent':fi['spent']})
 return sum(caps),caps,curve
base,bc=one_sleeve();rows=[];details={}
for w in (.85,.90,.925,.95,.975):
 z=dual(w);rows.append({'main_weight':w,'final':z[0],'ret':z[0]/START-1,'sleeve_caps':z[1],'events':len(z[2]),'wins':sum(x['net']>0 for x in z[2])});details[str(w)]=z[2]
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0]
out={'objective':'test fixed precommitted main/satellite capital sleeves; signal/entry/exit clocks unchanged','baseline':{'final':base,'ret':base/START-1,'events':len(bc),'wins':sum(x['net']>0 for x in bc)},'tested':rows,'best':best,'improvement':best['final']-base,'best_curve':details[str(best['main_weight'])]}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
