#!/usr/bin/env python3
import csv,json,math,os,time,urllib.parse,urllib.request
from datetime import datetime,timedelta
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
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API,'Accept':'application/json','User-Agent':'HENGCE-Q017-HOLD-SCAN/1.0'})
 last=None
 for a in range(7):
  try:
   with urllib.request.urlopen(req,timeout=30) as r:
    rows=json.load(r).get('data',[])
    if rows:return rows
    last='EMPTY'
  except Exception as e:last=repr(e)
  time.sleep(min(30,2**a))
 raise RuntimeError(f'FUGLE_FETCH_FAIL {sym} {d} {last}')
def dt(v):
 try:return datetime.fromisoformat(v)
 except:return None
by_t={};dates=set()
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
 t=r['ticker'];d=r['date'];c=f(r['close']);dates.add(d)
 if c is not None:by_t.setdefault(t,{})[d]=c
market_dates=sorted(dates);di={d:i for i,d in enumerate(market_dates)}
snap=json.loads(SRC.read_text(encoding='utf-8'))['event_candidate_snapshot'];locked=[{'entry':ev['entry'],'ticker':ev['candidates'][0]['ticker']} for ev in snap]
# Fetch only nine entry sessions first; never let exit-data rate limiting contaminate the entry control.
entry_cache={}
for e in locked:
 key=(e['ticker'],e['entry']);entry_cache[key]=fetch(*key);time.sleep(.35)
def entry_fill(t,d,capital):
 rows=entry_cache[(t,d)];trad=[x for x in rows if dt(x.get('date')) and dt(x['date']).hour>=9]
 if not trad:raise RuntimeError(f'NO_ENTRY_MINUTES {t} {d}')
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
def sim_close(hold,exit_slip):
 cap=START;wins=0;curve=[]
 for e in locked:
  d=e['entry'];t=e['ticker'];j=di[d]+hold-1
  if j>=len(market_dates):continue
  xd=market_dates[j];sh,spent=entry_fill(t,d,cap);raw=by_t.get(t,{}).get(xd)
  if sh<=0 or not raw:continue
  sell=raw*(1-exit_slip);net=sell/(spent/sh)-1-COST;pnl=spent*net;cap+=pnl;wins+=net>0;curve.append({'entry':d,'exit':xd,'ticker':t,'net':net,'capital':cap})
 return {'hold':hold,'final':cap,'ret':cap/START-1,'n':len(curve),'wins':wins,'curve':curve}
validated=json.loads(VALID.read_text(encoding='utf-8'))['anchors']['base']['final'];control=sim_close(10,0.0)
if abs(control['final']-validated)>1:raise SystemExit(f'BASE_REPRO_FAIL {control["final"]} != {validated}')
rows=[];details={}
for hold in range(5,61):
 r=sim_close(hold,EXIT_SLIP);details[hold]=r['curve'];rows.append({k:v for k,v in r.items() if k!='curve'})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];top_holds=sorted({best['hold']-2,best['hold']-1,best['hold'],best['hold']+1,best['hold']+2})
out={'objective':'find true executable close-exit hold peak before minute-timing refinement','reproduction_control':{'expected':validated,'actual':control['final'],'pass':True},'baseline_D10_close':next(x for x in rows if x['hold']==10),'best_close_hold':best,'best_is_boundary':best['hold'] in (5,60),'top10':rows[:10],'refine_holds':[h for h in top_holds if 5<=h<=60],'best_curve':details[best['hold']]}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
