#!/usr/bin/env python3
import json,math,os,time,urllib.parse,urllib.request
from datetime import datetime,timedelta
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');SRC=ROOT/'capacity_aware_multistock_2026'/'summary.json';OUT=ROOT/'top3_multiminute_waterfall_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;PART=.10;SLIP=.002;COST=.006;LAG=2;N=3
API_KEY=os.environ.get('FUGLE_API_KEY')
if not API_KEY:raise SystemExit('FUGLE_API_KEY missing')
events=json.loads(SRC.read_text(encoding='utf-8'))['event_candidate_snapshot']
def f(x):
 try:return float(x)
 except:return None
def dt(v):
 try:return datetime.fromisoformat(v)
 except:return None
def fetch(sym,d):
 base=f'https://api.fugle.tw/marketdata/v1.0/stock/historical/candles/{sym}';q=urllib.parse.urlencode({'timeframe':'1','from':d,'to':d,'fields':'open,high,low,close,volume,average','sort':'asc'})
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API_KEY,'Accept':'application/json','User-Agent':'HENGCE-Q017-TOP3-WATERFALL/1.1'})
 for a in range(5):
  try:
   with urllib.request.urlopen(req,timeout=30) as rr:return json.load(rr).get('data',[])
  except Exception:
   if a==4:raise
   time.sleep(2**a)
cache={}
for ev in events:
 for c in ev['candidates'][:N]:
  key=(c['ticker'],ev['entry'])
  if key not in cache:
   rows=fetch(*key);z=[x for x in rows if dt(x.get('date')) and dt(x['date']).hour>=9]
   if z:cache[key]={'t0':dt(z[0]['date']),'rows':z}
   time.sleep(.12)

def sim(window,pfield):
 cap=START;curve=[];wins=0
 for ev in events:
  before=cap;remaining=cap;positions={};actions=[]
  for rank,c in enumerate(ev['candidates'][:N],1):
   z=cache.get((c['ticker'],ev['entry']))
   if not z or not z['t0']:continue
   start=z['t0']+timedelta(minutes=LAG);end=start+timedelta(minutes=window-1)
   for x in z['rows']:
    t=dt(x['date'])
    if t and start<=t<=end:actions.append((t,rank,c,x))
  actions.sort(key=lambda q:(q[0],q[1]))
  for t,rank,c,x in actions:
   raw=f(x.get(pfield));lotsvol=f(x.get('volume')) or 0
   if not raw or raw<=0 or lotsvol<=0:continue
   px=raw*(1+SLIP);caplots=math.floor(lotsvol*PART);afford=math.floor(remaining/(px*1000));lots=min(caplots,afford)
   if lots<=0:continue
   inv=lots*1000*px;remaining-=inv
   p=positions.setdefault(c['ticker'],{'rank':rank,'score':c['score'],'shares':0,'spent':0.0,'exit_close':c['exit_close'],'fills':[]})
   p['shares']+=lots*1000;p['spent']+=inv;p['fills'].append({'time':x['date'],'lots':lots,'raw_px':raw,'stressed_px':px})
  pnl=0;plist=[]
  for p in positions.values():
   avg=p['spent']/p['shares'];net=p['exit_close']/avg-1-COST;pp=p['spent']*net;pnl+=pp;wins+=net>0
   plist.append({**p,'avg_entry':avg,'net':net,'pnl':pp})
  cap+=pnl;curve.append({'entry':ev['entry'],'capital_before':before,'deploy_ratio':1-remaining/before if before else 0,'cash_not_deployed':remaining,'event_pnl':pnl,'capital':cap,'positions':plist})
 return {'final':cap,'ret':cap/START-1,'events':len(curve),'position_wins':wins,'curve':curve}
res={}
for w in (1,3,5,10):
 for pf in ('open','high'):res[f'{w}m_{pf}']=sim(w,pf)
summary={'objective':'combine capacity-aware Top3 routing with live-feasible minute-by-minute waterfall fills','contract':{'topN':N,'minute_participation_cap':PART,'lag_minutes_after_first_print':LAG,'slippage':SLIP,'roundtrip_cost':COST},'results':res}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:{kk:vv for kk,vv in v.items() if kk!='curve'} for k,v in res.items()},ensure_ascii=False,indent=2))
