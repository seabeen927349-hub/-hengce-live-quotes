#!/usr/bin/env python3
import json,math,os,time,urllib.parse,urllib.request
from datetime import datetime,timedelta
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');SRC=ROOT/'capacity_aware_multistock_2026'/'summary.json';OUT=ROOT/'score_sizing_profit_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;LAG=2;TIMEOUT=20;PART=.10;SLIP=.002;COST=.006
API=os.environ.get('FUGLE_API_KEY')
if not API:raise SystemExit('FUGLE_API_KEY missing')
events=json.loads(SRC.read_text(encoding='utf-8'))['event_candidate_snapshot']
def f(x):
 try:return float(x)
 except:return None
def dt(v):
 try:return datetime.fromisoformat(v)
 except:return None
def fetch(sym,d):
 base=f'https://api.fugle.tw/marketdata/v1.0/stock/historical/candles/{sym}';q=urllib.parse.urlencode({'timeframe':'1','from':d,'to':d,'fields':'open,high,low,close,volume,average','sort':'asc'})
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API,'Accept':'application/json','User-Agent':'HENGCE-Q017-SCORE-SIZING/1.0'})
 for a in range(7):
  try:
   with urllib.request.urlopen(req,timeout=30) as rr:
    rows=json.load(rr).get('data',[])
    if rows:return rows
  except Exception:pass
  time.sleep(min(30,2**a))
 raise RuntimeError(f'FETCH_FAIL {sym} {d}')
cache={}
for ev in events:
 c=ev['candidates'][0];key=(c['ticker'],ev['entry']);rows=fetch(*key);z=[x for x in rows if dt(x.get('date')) and dt(x['date']).hour>=9]
 if not z:raise RuntimeError(f'NO_MINUTE {key}')
 cache[key]={'t0':dt(z[0]['date']),'rows':z};time.sleep(.3)
def fill(ev,capital,budget_frac):
 c=ev['candidates'][0];z=cache[(c['ticker'],ev['entry'])];budget=capital*budget_frac;rem=budget;shares=0;spent=0.;start=z['t0']+timedelta(minutes=LAG);end=start+timedelta(minutes=TIMEOUT)
 for x in z['rows']:
  t=dt(x['date'])
  if not t or t<start or t>end:continue
  raw=f(x.get('open'));vol=f(x.get('volume')) or 0
  if not raw or raw<=0 or vol<=0:continue
  px=raw*(1+SLIP);lots=min(math.floor(vol*PART),math.floor(rem/(px*1000)))
  if lots<=0:continue
  inv=lots*1000*px;rem-=inv;shares+=lots*1000;spent+=inv
 return shares,spent
def sim(kind,a,b):
 cap=START;curve=[];wins=0
 for ev in events:
  c=ev['candidates'][0];score=float(c['score'])
  if kind=='threshold': frac=1.0 if score>=a else b
  else: frac=max(b,min(1.0,score/a))
  sh,spent=fill(ev,cap,frac)
  if sh<=0:curve.append({'entry':ev['entry'],'ticker':c['ticker'],'score':score,'target_frac':frac,'capital':cap});continue
  avg=spent/sh;net=c['exit_close']/avg-1-COST;pnl=spent*net;before=cap;cap+=pnl;wins+=net>0
  curve.append({'entry':ev['entry'],'ticker':c['ticker'],'score':score,'target_frac':frac,'actual_frac':spent/before,'net':net,'capital':cap})
 return {'kind':kind,'a':a,'b':b,'final':cap,'ret':cap/START-1,'n':len(curve),'wins':wins,'curve':curve}
rows=[];details={}
for th in (.6,.8,1.0,1.2,1.4,1.6):
 for low in (0,.25,.5,.75,1.0):
  r=sim('threshold',th,low);k=f't_{th}_{low}';details[k]=r['curve'];rows.append({x:y for x,y in r.items() if x!='curve'})
for ref in (.8,1.0,1.2,1.4,1.6,1.8):
 for floor in (.25,.5,.75):
  r=sim('linear',ref,floor);k=f'l_{ref}_{floor}';details[k]=r['curve'];rows.append({x:y for x,y in r.items() if x!='curve'})
base=sim('threshold',0,1.0);rows.append({x:y for x,y in base.items() if x!='curve'});details['base']=base['curve']
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0]
out={'objective':'increase 2M terminal capital using only entry-time score for position size','baseline':{k:v for k,v in base.items() if k!='curve'},'best':best,'improvement':best['final']-base['final'],'top15':rows[:15],'best_curve':details['base' if best['kind']=='threshold' and best['a']==0 else (f"t_{best['a']}_{best['b']}" if best['kind']=='threshold' else f"l_{best['a']}_{best['b']}")]}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
