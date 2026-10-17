#!/usr/bin/env python3
import csv,json,math,os,time,urllib.parse,urllib.request
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';SRC=ROOT/'runner_horizon_causal_2026'/'summary.json';OUT=ROOT/'runner_stress_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;PART=.10;LAG=2;FILL=20
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
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API,'Accept':'application/json','User-Agent':'HENGCE-Q017-RUNNER-STRESS/1.0'})
 for a in range(7):
  try:
   with urllib.request.urlopen(req,timeout=30) as rr:
    rows=json.load(rr).get('data',[])
    if rows:return rows
  except Exception:pass
  time.sleep(min(30,2**a))
 raise RuntimeError(f'FETCH_FAIL {sym} {d}')
# Best causal sequence and exit dates are independent of transaction-cost assumptions because the decision is D10 day13 >= 0.
best=json.loads(SRC.read_text(encoding='utf-8'))['best_curve']
by_t=defaultdict(dict)
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
 c=f(r['close'])
 if c is not None:by_t[r['ticker']][r['date']]=c
cache={}
for e in best:
 key=(e['ticker'],e['entry']);rows=fetch(*key);z=[x for x in rows if dt(x.get('date')) and dt(x['date']).hour>=9]
 if not z:raise RuntimeError(f'NO_MINUTE {key}')
 cache[key]={'t0':dt(z[0]['date']),'rows':z};time.sleep(.3)
def sim(es,xs,cost,field='open'):
 cap=START;curve=[];wins=0
 for e in best:
  z=cache[(e['ticker'],e['entry'])];st=z['t0']+timedelta(minutes=LAG);en=st+timedelta(minutes=FILL);rem=cap;sh=0;spent=0.
  for x in z['rows']:
   t=dt(x['date'])
   if not t or t<st or t>en:continue
   raw=f(x.get(field));vol=f(x.get('volume')) or 0
   if not raw or raw<=0 or vol<=0:continue
   px=raw*(1+es);lots=min(math.floor(vol*PART),math.floor(rem/(px*1000)))
   if lots<=0:continue
   inv=lots*1000*px;rem-=inv;sh+=lots*1000;spent+=inv
  if sh<=0:continue
  raw=by_t[e['ticker']].get(e['exit'])
  if not raw:continue
  avg=spent/sh;net=raw*(1-xs)/avg-1-cost;pnl=spent*net;before=cap;cap+=pnl;wins+=net>0
  curve.append({'entry':e['entry'],'exit':e['exit'],'ticker':e['ticker'],'capital_before':before,'shares':sh,'avg_entry':avg,'net':net,'capital':cap})
 return {'entry_slip':es,'exit_slip':xs,'cost':cost,'field':field,'final':cap,'ret':cap/START-1,'events':len(curve),'wins':wins,'curve':curve}
rows=[];details={}
for es in (.002,.003,.005):
 for xs in (.002,.003,.005):
  for cost in (.006,.008,.010):
   for field in ('open','high'):
    r=sim(es,xs,cost,field);k=f'{es}_{xs}_{cost}_{field}';details[k]=r['curve'];rows.append({x:y for x,y in r.items() if x!='curve'})
rows.sort(key=lambda x:x['final'],reverse=True);anchor=next(x for x in rows if x['entry_slip']==.002 and x['exit_slip']==.002 and x['cost']==.006 and x['field']=='open');harsh=next(x for x in rows if x['entry_slip']==.005 and x['exit_slip']==.005 and x['cost']==.010 and x['field']=='high')
out={'objective':'verify D10-positive-day -> D11 runner remains profitable under execution stress','anchor':anchor,'harsh':harsh,'all_positive':all(x['final']>START for x in rows),'min_final':min(x['final'] for x in rows),'max_final':max(x['final'] for x in rows),'grid':rows,'anchor_curve':details[f"{anchor['entry_slip']}_{anchor['exit_slip']}_{anchor['cost']}_{anchor['field']}"]}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
