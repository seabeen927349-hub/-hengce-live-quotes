#!/usr/bin/env python3
# Reuse the validated causal teacher framework; only add one rule:
# a teacher-matching Top2/Top3 may replace Top1 only if its baseline score is close enough to Top1.
import csv,json,math,os,time,urllib.parse,urllib.request
from collections import defaultdict
from datetime import datetime,timedelta,time as dtime
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';CACHE=ROOT/'chip_teacher_combo_screen_2026'/'cache';OUT=ROOT/'chip_teacher_score_gap_causal_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;RESMAX=.04;K=25.;PART=.10;ES=.002;XS=.002;COST=.006;CUT=dtime(9,1);API=os.environ.get('FUGLE_API_KEY')
if not API:raise SystemExit('FUGLE_API_KEY missing')
def f(x):
 try:return float(str(x).replace(',','').strip())
 except:return None
def dt(v):
 try:return datetime.fromisoformat(v)
 except:return None
def load(p):
 a=[]
 for r in csv.DictReader(p.open(encoding='utf-8')):
  c=f(r['close']);
  if c is not None:a.append((r['date'],c))
 a.sort();return a
def prev(ds,d):
 z=[u for u in ds if u<d];return z[-1] if z else None
def fetch(sym,d):
 q=urllib.parse.urlencode({'timeframe':'1','from':d,'to':d,'fields':'open,high,low,close,volume,average','sort':'asc'});url=f'https://api.fugle.tw/marketdata/v1.0/stock/historical/candles/{sym}?{q}'
 req=urllib.request.Request(url,headers={'X-API-KEY':API,'Accept':'application/json','User-Agent':'HENGCE-Q017-TEACHER-GAP/1.0'})
 for a in range(7):
  try:
   with urllib.request.urlopen(req,timeout=30) as rr:
    rows=json.load(rr).get('data',[])
    if rows:return rows
  except Exception:pass
  time.sleep(min(20,2**a))
 return []
sox=load(ARC/'sox_2026.csv');dxy=load(ARC/'dxy_2026.csv');sd=[d for d,_ in sox];dd=[d for d,_ in dxy];sret={sox[i][0]:sox[i][1]/sox[i-1][1]-1 for i in range(1,len(sox))}
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
    z=obs[-60:];mx=sum(a for a,b in z)/len(z);my=sum(b for a,b in z)/len(z);vv=sum((a-mx)**2 for a,b in z);beta[(d,t)]=sum((a-mx)*(b-my) for a,b in z)/vv if vv else 0
   obs.append((sh,tr))
  pc=r['close']
feat={}
for d in md:
 us=prev(sd,d);ux=prev(dd,d);sh=sret.get(us)
 if not us or sh is None or not ux:continue
 si=sd.index(us);di=dd.index(ux);feat[d]={'shock':sh,'sox5':sox[si][1]/sox[si-5][1]-1 if si>=5 else None,'dxy5':dxy[di][1]/dxy[di-5][1]-1 if di>=5 else None}
chips={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in CACHE.glob('*.json')}
def teacher(d,t,iw,mw):
 i=mi[d];ds=md[max(0,i-iw):i];ms=md[max(0,i-mw-1):i];F=sum((chips.get(x,{}).get('inst',{}).get(t,{}) or {}).get('foreign',0) for x in ds);T=sum((chips.get(x,{}).get('inst',{}).get(t,{}) or {}).get('trust',0) for x in ds);b=[chips.get(x,{}).get('margin',{}).get(t) for x in ms];b=[x for x in b if x is not None];M=(b[-1]-b[0]) if len(b)>=2 else None;return {'F':F,'T':T,'M':M,'match':F<0 and T>0 and M is not None and M<0}
cand={}
for d in md:
 ft=feat.get(d);a=[]
 if not ft:continue
 for r in by_d[d]:
  t=r['ticker'];b=beta.get((d,t));pc=prevc.get((d,t))
  if b is None or b<=0 or not pc:continue
  res=r['open']/pc-1-b*ft['shock']
  if res<=RESMAX:a.append({'ticker':t,'score':b*(1+K*max(-res,0))})
 cand[d]=sorted(a,key=lambda x:x['score'],reverse=True)
cache={}
def mins(t,d):
 k=(t,d)
 if k not in cache:cache[k]=fetch(t,d);time.sleep(.13)
 return cache[k]
def first(rows):
 for x in rows:
  z=dt(x.get('date'))
  if z and dtime(9,0)<=z.time()<=CUT and f(x.get('open')) is not None:return x
 return None
def vis(d):
 out=[]
 for c in cand.get(d,[]):
  if first(mins(c['ticker'],d)):
   out.append(c)
   if len(out)>=3:break
 return out
def choose(d,iw,mw,min_ratio):
 z=vis(d)
 if not z:return None
 top=z[0];topscore=top['score']
 for rank,c in enumerate(z,1):
  q=teacher(d,c['ticker'],iw,mw)
  if q['match'] and c['score']/topscore>=min_ratio:return dict(c,rank=rank,q=q,ratio=c['score']/topscore)
 return dict(top,rank=1,q=teacher(d,top['ticker'],iw,mw),ratio=1.0)
def fill(c,d,cap):
 rows=mins(c['ticker'],d);fp=first(rows)
 if not fp:return 0,0
 st=dt(fp['date'])+timedelta(minutes=2);en=st+timedelta(minutes=20);rem=cap;sh=0;spent=0
 for x in rows:
  z=dt(x.get('date'));p=f(x.get('open'));v=f(x.get('volume')) or 0
  if not z or z<st or z>en or not p or v<=0:continue
  px=p*(1+ES);lots=min(math.floor(v*.10),math.floor(rem/(px*1000)))
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
def run(iw,mw,ratio):
 cap=START;busy=None;curve=[]
 for d in md:
  if busy and d<=busy:continue
  ft=feat.get(d)
  if not ft or ft['shock']>0 or ft['sox5'] is None or ft['sox5']>-.03 or ft['dxy5'] is None or ft['dxy5']<-.005:continue
  i=mi[d]
  if i+10>=len(md):continue
  c=choose(d,iw,mw,ratio)
  if not c:continue
  sh,spent=fill(c,d,cap)
  if sh<=0:continue
  d9,d10,d11=md[i+8],md[i+9],md[i+10];avg=spent/sh;p=p1300(c['ticker'],d10);c9=close(c['ticker'],d9);c10=close(c['ticker'],d10);c11=close(c['ticker'],d11)
  ext=p is not None and c9 and p>=c9;raw=c11 if ext else c10;xd=d11 if ext else d10
  if not raw:continue
  net=raw*(1-XS)/avg-1-COST;pnl=spent*net;cap+=pnl;busy=xd;curve.append({'entry':d,'ticker':c['ticker'],'rank':c['rank'],'score_ratio':c['ratio'],'teacher':c['q'],'exit':xd,'net':net,'capital':cap})
 return cap,curve
rows=[];details={}
# baseline ratio >1 makes teacher override impossible.
for iw,mw in ((3,5),(5,5),(10,3),(10,5)):
 for ratio in (0,.80,.85,.90,.95,1.01):
  cap,curve=run(iw,mw,ratio);key=f'{iw}_{mw}_{ratio}';details[key]=curve;rows.append({'iw':iw,'mw':mw,'min_score_ratio':ratio,'final':cap,'events':len(curve),'wins':sum(x['net']>0 for x in curve)})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];base=next(x for x in rows if x['min_score_ratio']==1.01);near=[x for x in rows if x['iw']==best['iw'] and x['mw']==best['mw']]
out={'objective':'teacher pattern may override Top1 only when teacher candidate remains close in baseline strength','teacher':'foreign sells + trust buys + margin declines','baseline':base,'best':best,'improvement':best['final']-base['final'],'same_window_surface':near,'top20':rows[:20],'best_curve':details[f"{best['iw']}_{best['mw']}_{best['min_score_ratio']}"]}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
