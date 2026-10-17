#!/usr/bin/env python3
import csv,json,math,os,time,urllib.parse,urllib.request
from collections import defaultdict
from datetime import datetime,timedelta,time as dtime
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'dxy_m5_causal_2026';OUT.mkdir(parents=True,exist_ok=True)
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
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API,'Accept':'application/json','User-Agent':'HENGCE-Q017-DXY-M5/1.0'})
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
md=sorted(by_d);mi={d:i for i,d in enumerate(md)};aligned={d:sret.get(prev(sd,d)) for d in md};beta={};prevc={};m5={}
for t,rs in by_t.items():
 obs=[];pc=None
 for i,r in enumerate(rs):
  d=r['date'];prevc[(d,t)]=pc;sh=aligned.get(d)
  if pc and i>=5 and rs[i-5]['close']>0:m5[(d,t)]=pc/rs[i-5]['close']-1
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
cache={}
def mins(t,d):
 key=(t,d)
 if key not in cache:cache[key]=fetch(t,d);time.sleep(.16)
 return cache[key]
def first(rows):
 for x in rows:
  z=dt(x.get('date'))
  if z and dtime(9,0)<=z.time()<=CUT and f(x.get('open')) is not None:return x
 return None
def candidates(d,m5max):
 ft=feat.get(d);out=[]
 if not ft:return out
 for r in by_d[d]:
  t=r['ticker'];b=beta.get((d,t));pc=prevc.get((d,t));mv=m5.get((d,t))
  if b is None or b<=0 or not pc or (m5max is not None and (mv is None or mv>m5max)):continue
  res=r['open']/pc-1-b*ft['shock']
  if res<=RESMAX:out.append({'ticker':t,'score':b*(1+K*max(-res,0)),'beta':b,'resid':res,'m5':mv})
 out.sort(key=lambda x:x['score'],reverse=True);return out
def choose(d,m5max):
 for c in candidates(d,m5max):
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
def run(m5max):
 cap=START;busy=None;curve=[]
 for d in md:
  if busy and d<=busy:continue
  ft=feat.get(d)
  if not ft or ft['shock']>0 or ft['sox5'] is None or ft['sox5']>-.03 or ft['dxy5'] is None or ft['dxy5']<-.005:continue
  i=mi[d]
  if i+10>=len(md):continue
  c=choose(d,m5max)
  if not c:continue
  sh,spent=fill(c,d,cap)
  if sh<=0:continue
  d9,d10,d11=md[i+8],md[i+9],md[i+10];avg=spent/sh;p=p1300(c['ticker'],d10);c9=close(c['ticker'],d9);c10=close(c['ticker'],d10);c11=close(c['ticker'],d11)
  if not c9 or not c10 or not c11:continue
  ext=p is not None and p>=c9;xd=d11 if ext else d10;raw=c11 if ext else c10;net=raw*(1-XS)/avg-1-COST;pnl=spent*net;cap+=pnl;busy=xd
  curve.append({'entry':d,'ticker':c['ticker'],'exit':xd,'extend':ext,'m5':c['m5'],'beta':c['beta'],'resid':c['resid'],'net':net,'capital':cap})
 return {'final':cap,'ret':cap/START-1,'events':len(curve),'wins':sum(e['net']>0 for e in curve),'curve':curve}
thresholds=[None,.05,.02,0,-.02,-.05,-.08,-.10]
rows=[];details={}
for th in thresholds:
 r=run(th);key='NONE' if th is None else str(th);details[key]=r['curve'];rows.append({'m5_max':key,'final':r['final'],'ret':r['ret'],'events':r['events'],'wins':r['wins']})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];base=next(x for x in rows if x['m5_max']=='NONE');bf=best['final']
out={'objective':'causal validation of prior-5d momentum filter under validated SOX5 x DXY5 gate; timing fixed','contract':{'market_gate':'SOX1<=0, SOX5<=-3%, DXY5>=-0.5%','rank':'beta60*(1+25*negative residual), residual<=4%','entry':'09:01 causal; first print +2m; 20m fill; 10% minute participation; 0.2% slip','exit':'D10 13:00 sign vs D9 close; strong D11 else D10; 0.2% slip','cost':COST},'baseline':base,'tested':len(rows),'best':best,'improvement':best['final']-base['final'],'within_99pct_best':sum(x['final']>=.99*bf for x in rows),'grid':rows,'best_curve':details[best['m5_max']]}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
