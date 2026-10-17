#!/usr/bin/env python3
import csv,json,math,os,time,urllib.parse,urllib.request
from datetime import datetime,timedelta,time as dtime
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'exit_clock_profit_2026';OUT.mkdir(parents=True,exist_ok=True)
SRC=ROOT/'capacity_aware_multistock_2026'/'summary.json';VALID=ROOT/'top1_20m_hard_stress_2026'/'summary.json'
START=2_000_000.;ENTRY_SLIP=.002;EXIT_SLIP=.002;COST=.006;PART=.10;LAG=2;FILL_MIN=20
API=os.environ.get('FUGLE_API_KEY')
if not API:raise SystemExit('FUGLE_API_KEY missing')
def f(x):
 try:return float(str(x).replace(',','').strip())
 except:return None
def fetch(sym,d):
 base=f'https://api.fugle.tw/marketdata/v1.0/stock/historical/candles/{sym}';q=urllib.parse.urlencode({'timeframe':'1','from':d,'to':d,'fields':'open,high,low,close,volume,average','sort':'asc'})
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API,'Accept':'application/json','User-Agent':'HENGCE-Q017-EXIT-CLOCK/1.2'})
 for a in range(5):
  try:
   with urllib.request.urlopen(req,timeout=30) as r:return json.load(r).get('data',[])
  except Exception:
   if a==4:return []
   time.sleep(2**a)
def dt(v):
 try:return datetime.fromisoformat(v)
 except:return None
by_t={};dates=set()
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
 t=r['ticker'];d=r['date'];c=f(r['close']);dates.add(d)
 if c is not None:by_t.setdefault(t,{})[d]=c
market_dates=sorted(dates);di={d:i for i,d in enumerate(market_dates)}
snap=json.loads(SRC.read_text(encoding='utf-8'))['event_candidate_snapshot'];locked=[{'entry':ev['entry'],'ticker':ev['candidates'][0]['ticker']} for ev in snap]
HOLDS=range(10,21);cache={}
for e in locked:
 t=e['ticker'];d=e['entry'];cache[(t,d)]=fetch(t,d);time.sleep(.08);i=di[d]
 for hold in HOLDS:
  j=i+hold-1
  if j<len(market_dates):
   xd=market_dates[j];cache[(t,xd)]=fetch(t,xd);time.sleep(.08)
def entry_fill(t,d,capital):
 rows=cache.get((t,d),[]);trad=[x for x in rows if dt(x.get('date')) and dt(x['date']).hour>=9]
 if not trad:return 0,0.
 t0=dt(trad[0]['date']);start=t0+timedelta(minutes=LAG);end=start+timedelta(minutes=FILL_MIN);rem=capital;shares=0;spent=0.
 for x in trad:
  z=dt(x.get('date'))
  if not z or z<start or z>end:continue
  raw=f(x.get('open'));vol=f(x.get('volume')) or 0
  if not raw or vol<=0:continue
  px=raw*(1+ENTRY_SLIP);lots=min(math.floor(vol*PART),math.floor(rem/(px*1000)))
  if lots<=0:continue
  inv=lots*1000*px;rem-=inv;shares+=lots*1000;spent+=inv
 return shares,spent
def minute_px(t,d,tm,field):
 h,m=map(int,tm.split(':'));target=dtime(h,m)
 for x in cache.get((t,d),[]):
  z=dt(x.get('date'))
  if z and z.time()>=target:
   p=f(x.get(field))
   if p and p>0:return p
 return None
def simulate(hold,tm,field,exit_slip=EXIT_SLIP):
 cap=START;wins=0;curve=[]
 for e in locked:
  d=e['entry'];t=e['ticker'];j=di[d]+hold-1
  if j>=len(market_dates):continue
  xd=market_dates[j];sh,spent=entry_fill(t,d,cap)
  if sh<=0:continue
  raw=by_t.get(t,{}).get(xd) if tm=='CLOSE' else minute_px(t,xd,tm,field)
  if not raw:continue
  sell=raw*(1-exit_slip);net=sell/(spent/sh)-1-COST;pnl=spent*net;cap+=pnl;wins+=net>0;curve.append({'entry':d,'exit':xd,'ticker':t,'net':net,'capital':cap})
 return {'hold':hold,'time':tm,'field':field,'final':cap,'ret':cap/START-1,'n':len(curve),'wins':wins,'curve':curve}
validated=json.loads(VALID.read_text(encoding='utf-8'))['anchors']['base']['final'];control=simulate(10,'CLOSE','close',0.0)
if abs(control['final']-validated)>1:raise SystemExit(f'BASE_REPRO_FAIL {control["final"]} != {validated}')
rows=[];details={}
for hold in HOLDS:
 for tm in ('13:00','13:20','CLOSE'):
  fields=('open','low') if tm!='CLOSE' else ('close',)
  for field in fields:
   r=simulate(hold,tm,field);k=f'{hold}_{tm}_{field}';details[k]=r['curve'];rows.append({x:y for x,y in r.items() if x!='curve'})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];base=next(x for x in rows if x['hold']==10 and x['time']=='CLOSE');near=[x for x in rows if x['final']>=best['final']*.95]
out={'objective':'maximize executable 2M terminal capital; stop only after hold peak is interior','reproduction_control':{'expected':validated,'actual':control['final'],'pass':True},'tested':len(rows),'baseline_D10_close':base,'best':best,'best_is_hold_boundary':best['hold'] in (min(HOLDS),max(HOLDS)),'within_95pct_best':len(near),'top20':rows[:20],'best_curve':details[f"{best['hold']}_{best['time']}_{best['field']}"]}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
