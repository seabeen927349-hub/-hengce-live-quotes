#!/usr/bin/env python3
import csv,json,math,os,time,urllib.parse,urllib.request
from collections import defaultdict
from datetime import datetime,timedelta,time as dtime
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';SRC=ROOT/'runner_horizon_causal_2026'/'summary.json';OUT=ROOT/'runner_exit_clock_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;PART=.10;ES=.002;XS=.002;COST=.006;LAG=2;FILL=20
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
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API,'Accept':'application/json','User-Agent':'HENGCE-Q017-RUNNER-EXIT-CLOCK/1.0'})
 for a in range(7):
  try:
   with urllib.request.urlopen(req,timeout=30) as rr:
    rows=json.load(rr).get('data',[])
    if rows:return rows
  except Exception:pass
  time.sleep(min(30,2**a))
 return []
best=json.loads(SRC.read_text(encoding='utf-8'))['best_curve']
by_t=defaultdict(dict)
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
 c=f(r['close'])
 if c is not None:by_t[r['ticker']][r['date']]=c
entry_cache={};exit_cache={}
for e in best:
 k=(e['ticker'],e['entry']);rows=fetch(*k);z=[x for x in rows if dt(x.get('date')) and dt(x['date']).hour>=9]
 if not z:raise RuntimeError(f'NO_ENTRY_MINUTE {k}')
 entry_cache[k]={'t0':dt(z[0]['date']),'rows':z};time.sleep(.25)
 if e['extend']:
  k2=(e['ticker'],e['exit']);exit_cache[k2]=fetch(*k2);time.sleep(.25)
def minute_px(t,d,tm,field='open'):
 h,m=map(int,tm.split(':'));target=dtime(h,m)
 for x in exit_cache.get((t,d),[]):
  z=dt(x.get('date'))
  if z and z.time()>=target:
   p=f(x.get(field))
   if p and p>0:return p,x['date']
 return None,None
def run(tm,field='open'):
 cap=START;curve=[];wins=0
 for e in best:
  z=entry_cache[(e['ticker'],e['entry'])];st=z['t0']+timedelta(minutes=LAG);en=st+timedelta(minutes=FILL);rem=cap;sh=0;spent=0.
  for x in z['rows']:
   t=dt(x['date'])
   if not t or t<st or t>en:continue
   raw=f(x.get('open'));vol=f(x.get('volume')) or 0
   if not raw or vol<=0:continue
   px=raw*(1+ES);lots=min(math.floor(vol*PART),math.floor(rem/(px*1000)))
   if lots<=0:continue
   inv=lots*1000*px;rem-=inv;sh+=lots*1000;spent+=inv
  if sh<=0:continue
  if e['extend'] and tm!='CLOSE':raw,ts=minute_px(e['ticker'],e['exit'],tm,field)
  else:raw=by_t[e['ticker']].get(e['exit']);ts=e['exit']+' CLOSE'
  if not raw:continue
  avg=spent/sh;net=raw*(1-XS)/avg-1-COST;pnl=spent*net;before=cap;cap+=pnl;wins+=net>0
  curve.append({'entry':e['entry'],'exit':e['exit'],'ticker':e['ticker'],'extend':e['extend'],'capital_before':before,'avg_entry':avg,'raw_exit':raw,'exit_ts':ts,'net':net,'capital':cap})
 return {'time':tm,'field':field,'final':cap,'ret':cap/START-1,'events':len(curve),'wins':wins,'curve':curve}
rows=[];details={}
for tm in ('13:00','13:10','13:20','13:25','13:28','13:29','CLOSE'):
 fields=('open','low') if tm!='CLOSE' else ('close',)
 for field in fields:
  r=run(tm,field);k=f'{tm}_{field}';details[k]=r['curve'];rows.append({x:y for x,y in r.items() if x!='curve'})
rows.sort(key=lambda x:x['final'],reverse=True);bestrow=rows[0];base=next(x for x in rows if x['time']=='CLOSE');bf=bestrow['final']
out={'objective':'increase D11 runner terminal capital by executable exit clock only','baseline_D11_close':base,'best':bestrow,'improvement':bestrow['final']-base['final'],'within_99pct_best':sum(x['final']>=.99*bf for x in rows),'grid':rows,'best_curve':details[f"{bestrow['time']}_{bestrow['field']}"]}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
