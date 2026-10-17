#!/usr/bin/env python3
import csv,json,math,os,time,urllib.parse,urllib.request
from collections import defaultdict
from datetime import datetime,timedelta,time as dtime
from pathlib import Path

ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';CACHE=ROOT/'chip_teacher_combo_screen_2026'/'cache';OUT=ROOT/'chip_teacher_rerank_causal_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;RESMAX=.04;K=25.;PART=.10;ES=.002;XS=.002;COST=.006;LAG=2;FILL=20;CUT=dtime(9,1)
API=os.environ.get('FUGLE_API_KEY')
if not API:raise SystemExit('FUGLE_API_KEY missing')

def f(x):
 try:return float(str(x).replace(',','').strip())
 except:return None
def dt(v):
 try:return datetime.fromisoformat(v)
 except:return None
def load(path):
 a=[]
 for r in csv.DictReader(path.open(encoding='utf-8')):
  c=f(r['close'])
  if c is not None:a.append((r['date'],c))
 a.sort();return a
def prev(ds,d):
 z=[u for u in ds if u<d];return z[-1] if z else None

def fetch(sym,d):
 base=f'https://api.fugle.tw/marketdata/v1.0/stock/historical/candles/{sym}';q=urllib.parse.urlencode({'timeframe':'1','from':d,'to':d,'fields':'open,high,low,close,volume,average','sort':'asc'})
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API,'Accept':'application/json','User-Agent':'HENGCE-Q017-TEACHER-CAUSAL/1.0'})
 for a in range(7):
  try:
   with urllib.request.urlopen(req,timeout=30) as rr:
    rows=json.load(rr).get('data',[])
    if rows:return rows
  except Exception:pass
  time.sleep(min(20,2**a))
 return []

sox=load(ARC/'sox_2026.csv');dxy=load(ARC/'dxy_2026.csv');sd=[d for d,_ in sox];dd=[d for d,_ in dxy]
sret={sox[i][0]:sox[i][1]/sox[i-1][1]-1 for i in range(1,len(sox))}
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
 si=sd.index(us);di=dd.index(ux);s5=sox[si][1]/sox[si-5][1]-1 if si>=5 else None;dx5=dxy[di][1]/dxy[di-5][1]-1 if di>=5 else None
 feat[d]={'shock':sh,'sox5':s5,'dxy5':dx5}
chips={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in CACHE.glob('*.json')}
windows=(1,3,5,10)
def chip_features(d,t):
 i=mi[d];prior=md[max(0,i-11):i];out={}
 for w in windows:
  ds=prior[-w:]
  out[f'f{w}']=sum((chips.get(x,{}).get('inst',{}).get(t,{}) or {}).get('foreign',0) for x in ds)
  out[f't{w}']=sum((chips.get(x,{}).get('inst',{}).get(t,{}) or {}).get('trust',0) for x in ds)
  bals=[chips.get(x,{}).get('margin',{}).get(t) for x in prior[-(w+1):]];bals=[x for x in bals if x is not None]
  out[f'm{w}']=(bals[-1]-bals[0]) if len(bals)>=2 else None
 return out
cand={}
for d in md:
 ft=feat.get(d);a=[]
 if not ft:continue
 for r in by_d[d]:
  t=r['ticker'];b=beta.get((d,t));pc=prevc.get((d,t))
  if b is None or b<=0 or not pc:continue
  res=r['open']/pc-1-b*ft['shock']
  if res<=RESMAX:a.append({'ticker':t,'score':b*(1+K*max(-res,0)),'beta':b,'resid':res,'chip':chip_features(d,t)})
 cand[d]=sorted(a,key=lambda x:x['score'],reverse=True)
cache={}
def mins(t,d):
 k=(t,d)
 if k not in cache:cache[k]=fetch(t,d);time.sleep(.14)
 return cache[k]
def first(rows):
 for x in rows:
  z=dt(x.get('date'))
  if z and dtime(9,0)<=z.time()<=CUT and f(x.get('open')) is not None:return x
 return None
def visible_top(d,N):
 out=[]
 for c in cand.get(d,[]):
  if first(mins(c['ticker'],d)):
   out.append(c)
   if len(out)>=N:break
 return out
def pattern(c,kind,iw,mw):
 ch=c['chip'];F=ch.get(f'f{iw}');T=ch.get(f't{iw}');M=ch.get(f'm{mw}')
 if M is None:return False
 if kind=='institution_buy_margin_down':return ((F or 0)>0 or (T or 0)>0) and M<0
 if kind=='foreign_buy_trust_sell_margin_down':return (F or 0)>0 and (T or 0)<0 and M<0
 if kind=='trust_buy_foreign_sell_margin_down':return (T or 0)>0 and (F or 0)<0 and M<0
 if kind=='both_buy_margin_down':return (F or 0)>0 and (T or 0)>0 and M<0
 return False
def choose(d,spec):
 z=visible_top(d,spec['N'])
 if not z:return None
 if spec['kind']=='baseline':return z[0]
 g=[x for x in z if pattern(x,spec['kind'],spec['iw'],spec['mw'])]
 return g[0] if g else z[0]
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
def run(spec):
 cap=START;busy=None;curve=[]
 for d in md:
  if busy and d<=busy:continue
  ft=feat.get(d)
  if not ft or ft['shock']>0 or ft['sox5'] is None or ft['sox5']>-.03 or ft['dxy5'] is None or ft['dxy5']<-.005:continue
  i=mi[d]
  if i+10>=len(md):continue
  c=choose(d,spec)
  if not c:continue
  sh,spent=fill(c,d,cap)
  if sh<=0:continue
  d9,d10,d11=md[i+8],md[i+9],md[i+10];avg=spent/sh;p=p1300(c['ticker'],d10);c9=close(c['ticker'],d9);c10=close(c['ticker'],d10);c11=close(c['ticker'],d11)
  if not c9 or not c10 or not c11:continue
  ext=p is not None and p>=c9;xd=d11 if ext else d10;raw=c11 if ext else c10;net=raw*(1-XS)/avg-1-COST;pnl=spent*net;cap+=pnl;busy=xd
  curve.append({'entry':d,'ticker':c['ticker'],'exit':xd,'extend':ext,'net':net,'pnl':pnl,'capital':cap,'chip':c['chip'],'beta':c['beta'],'resid':c['resid']})
 return {'final':cap,'ret':cap/START-1,'events':len(curve),'wins':sum(e['net']>0 for e in curve),'curve':curve}

specs=[{'N':1,'kind':'baseline','iw':1,'mw':1}]
for N in (3,5):
 for kind in ('institution_buy_margin_down','foreign_buy_trust_sell_margin_down','trust_buy_foreign_sell_margin_down','both_buy_margin_down'):
  for iw in (1,3,5,10):
   for mw in (1,3,5,10):specs.append({'N':N,'kind':kind,'iw':iw,'mw':mw})
rows=[];details={}
for s in specs:
 r=run(s);key=json.dumps(s,sort_keys=True);details[key]=r['curve'];rows.append({'spec':s,'final':r['final'],'ret':r['ret'],'events':r['events'],'wins':r['wins']})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];base=next(x for x in rows if x['spec']['kind']=='baseline');fam=[x for x in rows if x['spec']['N']==best['spec']['N'] and x['spec']['kind']==best['spec']['kind']]
out={'objective':'fully causal minute-level validation of foreign/trust/margin rerank within visible baseline TopN; no timing optimization','contract':{'market_gate':'SOX1<=0, SOX5<=-3%, DXY5>=-0.5%','base_rank':'beta60*(1+25*negative residual), residual<=4%','candidate_visibility':'first print observed by 09:01','entry':'first print +2m, 20m fill, 10% minute participation, +0.2% slip','exit':'existing D10/D11 rule, -0.2% exit slip','cost':COST},'baseline':base,'tested':len(rows),'best':best,'improvement':best['final']-base['final'],'best_family_count':len(fam),'best_family_within99pct':sum(x['final']>=.99*best['final'] for x in fam),'top20':rows[:20],'best_curve':details[json.dumps(best['spec'],sort_keys=True)]}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
