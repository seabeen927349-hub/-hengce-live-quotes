#!/usr/bin/env python3
import csv,json,math,os,time,urllib.parse,urllib.request
from collections import defaultdict
from datetime import datetime,timedelta,time as dtime
from pathlib import Path

ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';CACHE=ROOT/'chip_teacher_combo_screen_2026'/'cache';OUT=ROOT/'chip_teacher_sequence_causal_2026';OUT.mkdir(parents=True,exist_ok=True)
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
 base=f'https://api.fugle.tw/marketdata/v1.0/stock/historical/candles/{sym}'
 q=urllib.parse.urlencode({'timeframe':'1','from':d,'to':d,'fields':'open,high,low,close,volume,average','sort':'asc'})
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API,'Accept':'application/json','User-Agent':'HENGCE-Q017-TEACHER-SEQUENCE-CAUSAL/1.0'})
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

def teacher(d,t,w,mw):
 i=mi[d];ds=md[max(0,i-w):i];mds=md[max(0,i-mw-1):i]
 F=sum((chips.get(x,{}).get('inst',{}).get(t,{}) or {}).get('foreign',0) for x in ds)
 T=sum((chips.get(x,{}).get('inst',{}).get(t,{}) or {}).get('trust',0) for x in ds)
 bals=[chips.get(x,{}).get('margin',{}).get(t) for x in mds];bals=[x for x in bals if x is not None]
 M=(bals[-1]-bals[0]) if len(bals)>=2 else None
 return {'foreign':F,'trust':T,'margin_change':M,'match':F<0 and T>0 and M is not None and M<0}

cand={}
for d in md:
 ft=feat.get(d);a=[]
 if not ft:continue
 for r in by_d[d]:
  t=r['ticker'];b=beta.get((d,t));pc=prevc.get((d,t))
  if b is None or b<=0 or not pc:continue
  res=r['open']/pc-1-b*ft['shock']
  if res<=RESMAX:a.append({'ticker':t,'score':b*(1+K*max(-res,0)),'beta':b,'resid':res})
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
def choose(d,spec):
 z=visible_top(d,spec['N'])
 if not z:return None
 if spec['kind']=='baseline':return dict(z[0],teacher=None,base_rank=1)
 for i,c in enumerate(z,1):
  q=teacher(d,c['ticker'],spec['iw'],spec['mw'])
  if q['match']:return dict(c,teacher=q,base_rank=i)
 return dict(z[0],teacher=teacher(d,z[0]['ticker'],spec['iw'],spec['mw']),base_rank=1)
def fill(c,d,capital,entry_slip=ES):
 rows=mins(c['ticker'],d);fp=first(rows)
 if not fp:return 0,0.
 st=dt(fp['date'])+timedelta(minutes=LAG);en=st+timedelta(minutes=FILL);rem=capital;sh=0;spent=0.
 for x in rows:
  z=dt(x.get('date'))
  if not z or z<st or z>en:continue
  raw=f(x.get('open'));vol=f(x.get('volume')) or 0
  if not raw or vol<=0:continue
  px=raw*(1+entry_slip);lots=min(math.floor(vol*PART),math.floor(rem/(px*1000)))
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
def run(spec,entry_slip=ES,exit_slip=XS,cost=COST):
 cap=START;busy=None;curve=[]
 for d in md:
  if busy and d<=busy:continue
  ft=feat.get(d)
  if not ft or ft['shock']>0 or ft['sox5'] is None or ft['sox5']>-.03 or ft['dxy5'] is None or ft['dxy5']<-.005:continue
  i=mi[d]
  if i+10>=len(md):continue
  c=choose(d,spec)
  if not c:continue
  sh,spent=fill(c,d,cap,entry_slip)
  if sh<=0:continue
  d9,d10,d11=md[i+8],md[i+9],md[i+10];avg=spent/sh;p=p1300(c['ticker'],d10);c9=close(c['ticker'],d9);c10=close(c['ticker'],d10);c11=close(c['ticker'],d11)
  if not c9 or not c10 or not c11:continue
  ext=p is not None and p>=c9;xd=d11 if ext else d10;raw=c11 if ext else c10;net=raw*(1-exit_slip)/avg-1-cost;pnl=spent*net;cap+=pnl;busy=xd
  curve.append({'entry':d,'ticker':c['ticker'],'base_rank':c['base_rank'],'exit':xd,'extend':ext,'teacher':c['teacher'],'net':net,'pnl':pnl,'capital':cap})
 return {'final':cap,'ret':cap/START-1,'events':len(curve),'wins':sum(e['net']>0 for e in curve),'curve':curve}

specs=[{'N':1,'kind':'baseline','iw':5,'mw':5}]
for iw,mw in ((3,3),(3,5),(5,3),(5,5),(10,3),(10,5),(10,10)):
 specs.append({'N':3,'kind':'teacher','iw':iw,'mw':mw})
rows=[];details={}
for s in specs:
 r=run(s);key=json.dumps(s,sort_keys=True);details[key]=r['curve'];rows.append({'spec':s,'final':r['final'],'ret':r['ret'],'events':r['events'],'wins':r['wins']})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];base=next(x for x in rows if x['spec']['kind']=='baseline')
# Execution stress only for best teacher concept; no time optimization.
stress=[]
for es in (.002,.003,.005):
 for xs in (.002,.003,.005):
  for cost in (.006,.008,.01):
   r=run(best['spec'],es,xs,cost);stress.append({'entry_slip':es,'exit_slip':xs,'cost':cost,'final':r['final'],'events':r['events'],'wins':r['wins']})
stress.sort(key=lambda x:x['final'])
out={'objective':'fully causal validation of teacher sequence only: foreign selling + trust buying + margin declining inside visible Top3; no timing optimization','contract':{'market_gate':'SOX1<=0, SOX5<=-3%, DXY5>=-0.5%','candidate_pool':'visible Top3 by beta60*(1+25*negative residual), residual<=4%','teacher_rule':'prefer highest base-ranked Top3 candidate with prior-window ForeignNet<0, TrustNet>0, MarginBalanceChange<0; otherwise fallback Top1','entry':'first print observed by 09:01; +2m; 20m fill; 10% participation','exit':'existing D10/D11 rule'},'baseline':base,'tested':len(rows),'best':best,'improvement':best['final']-base['final'],'neighbor_grid':rows,'stress':{'tested':len(stress),'min_final':stress[0]['final'],'median_final':stress[len(stress)//2]['final'],'all_positive':all(x['final']>START for x in stress),'rows':stress},'best_curve':details[json.dumps(best['spec'],sort_keys=True)]}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
