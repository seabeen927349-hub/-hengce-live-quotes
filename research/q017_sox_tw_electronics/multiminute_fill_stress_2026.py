#!/usr/bin/env python3
import json,math,os,time,urllib.parse,urllib.request
from datetime import datetime,timedelta
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');SRC=ROOT/'executable_hold_timing_surface_2026'/'summary.json';OUT=ROOT/'multiminute_fill_stress_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;PART=.10;SLIP=.002;COST=.006
API_KEY=os.environ.get('FUGLE_API_KEY')
if not API_KEY:raise SystemExit('FUGLE_API_KEY missing')
events=json.loads(SRC.read_text(encoding='utf-8'))['best_events']

def f(x):
 try:return float(x)
 except:return None
def dt(v):
 try:return datetime.fromisoformat(v)
 except:return None
def fetch(symbol,d):
 base=f'https://api.fugle.tw/marketdata/v1.0/stock/historical/candles/{symbol}'
 q=urllib.parse.urlencode({'timeframe':'1','from':d,'to':d,'fields':'open,high,low,close,volume,average','sort':'asc'})
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API_KEY,'Accept':'application/json','User-Agent':'HENGCE-Q017-MULTIFILL/1.0'})
 for a in range(5):
  try:
   with urllib.request.urlopen(req,timeout=30) as r:return json.load(r).get('data',[])
  except Exception:
   if a==4:raise
   time.sleep(2**a)

cache={}
for e in events:
 rows=fetch(e['ticker'],e['entry']);cache[(e['ticker'],e['entry'])]=rows;time.sleep(.15)

def simulate(window,price_field):
 cap=START;curve=[];wins=0
 for e in events:
  rows=cache[(e['ticker'],e['entry'])];start=dt(e['entry_time']);end=start+timedelta(minutes=window-1)
  eligible=[x for x in rows if dt(x.get('date')) and start<=dt(x['date'])<=end]
  cash=cap;fills=[];shares=0;spent=0.0
  for x in eligible:
   raw=f(x.get(price_field))
   if raw is None and price_field=='average':raw=f(x.get('open'))
   lots=f(x.get('volume')) or 0
   if not raw or raw<=0 or lots<=0:continue
   px=raw*(1+SLIP)
   cap_lots=math.floor(lots*PART)
   affordable_lots=math.floor(cash/(px*1000))
   qlots=min(cap_lots,affordable_lots)
   if qlots<=0:continue
   q=qlots*1000;amt=q*px;cash-=amt;shares+=q;spent+=amt
   fills.append({'time':x['date'],'raw_px':raw,'stressed_px':px,'minute_volume_lots':lots,'fill_lots':qlots})
  if shares<=0:
   curve.append({'entry':e['entry'],'ticker':e['ticker'],'shares':0,'capital':cap,'fills':fills});continue
  avg=spent/shares;net=e['exit_close']/avg-1-COST;pnl=spent*net;cap+=pnl;wins+=net>0
  curve.append({'entry':e['entry'],'ticker':e['ticker'],'shares':shares,'avg_entry':avg,'invested':spent,'cash_uninvested_at_entry':cash,'exit_close':e['exit_close'],'net_ret_on_invested':net,'pnl':pnl,'capital':cap,'fills':fills})
 return {'final':cap,'ret':cap/START-1,'n':sum(x['shares']>0 for x in curve),'wins':wins,'curve':curve}

results={}
for w in (1,2,3,5,10):
 for pf in ('open','average','high'):
  results[f'{w}m_{pf}']=simulate(w,pf)
summary={'objective':'replace one-minute instant fill with boardlot accumulation across multiple minutes','contract':{'boardlot':True,'minute_participation_cap':PART,'slippage':SLIP,'roundtrip_cost':COST,'volume_unit':'Fugle board lots'},'results':results}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:{kk:vv for kk,vv in v.items() if kk!='curve'} for k,v in results.items()},ensure_ascii=False,indent=2))
