#!/usr/bin/env python3
import json,math,os,time,urllib.parse,urllib.request
from datetime import datetime,timedelta
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');SRC=ROOT/'capacity_aware_multistock_2026'/'summary.json';OUT=ROOT/'fixed_weight_top3_2026';OUT.mkdir(parents=True,exist_ok=True)
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
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API_KEY,'Accept':'application/json','User-Agent':'HENGCE-Q017-FIXED-WEIGHT/1.0'})
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

def fill_candidate(c,entry,target_cash,timeout_min,pfield):
 z=cache.get((c['ticker'],entry])

def execute_one(c,entry,target_cash,timeout_min,pfield):
 z=cache.get((c['ticker'],entry))
 if not z or not z['t0'] or target_cash<=0:return {'shares':0,'spent':0.0,'fills':[]}
 order_time=z['t0']+timedelta(minutes=LAG);deadline=order_time+timedelta(minutes=timeout_min)
 remaining=target_cash;shares=0;spent=0.0;fills=[]
 for x in z['rows']:
  t=dt(x['date'])
  if not t or t<order_time or t>deadline:continue
  raw=f(x.get(pfield));lotsvol=f(x.get('volume')) or 0
  if not raw or raw<=0 or lotsvol<=0:continue
  px=raw*(1+SLIP);caplots=math.floor(lotsvol*PART);afford=math.floor(remaining/(px*1000));lots=min(caplots,afford)
  if lots<=0:continue
  inv=lots*1000*px;remaining-=inv;shares+=lots*1000;spent+=inv;fills.append({'time':x['date'],'lots':lots,'raw_px':raw,'stressed_px':px})
 return {'shares':shares,'spent':spent,'fills':fills,'unfilled_target':remaining}

weights={'100_0_0':(1,0,0),'80_20_0':(.8,.2,0),'70_30_0':(.7,.3,0),'70_20_10':(.7,.2,.1),'60_30_10':(.6,.3,.1),'60_20_20':(.6,.2,.2),'50_30_20':(.5,.3,.2),'equal3':(1/3,1/3,1/3)}
def sim(ws,timeout,pfield):
 cap=START;curve=[];wins=0
 for ev in events:
  before=cap;pnl=0;pos=[];spent_total=0
  for rank,(c,w) in enumerate(zip(ev['candidates'][:N],ws),1):
   ex=execute_one(c,ev['entry'],before*w,timeout,pfield)
   if ex['shares']<=0:continue
   avg=ex['spent']/ex['shares'];net=c['exit_close']/avg-1-COST;pp=ex['spent']*net;pnl+=pp;spent_total+=ex['spent'];wins+=net>0
   pos.append({'rank':rank,'ticker':c['ticker'],'weight_target':w,'shares':ex['shares'],'spent':ex['spent'],'avg_entry':avg,'net':net,'pnl':pp,'fills':ex['fills']})
  cap+=pnl;curve.append({'entry':ev['entry'],'capital_before':before,'deploy_ratio':spent_total/before if before else 0,'event_pnl':pnl,'capital':cap,'positions':pos})
 return {'final':cap,'ret':cap/START-1,'position_wins':wins,'curve':curve}
rows=[];details={}
for name,ws in weights.items():
 for timeout in (5,10,20,30):
  for pf in ('open','high'):
   r=sim(ws,timeout,pf);rec={'weights':name,'timeout_min':timeout,'price_field':pf,'final':r['final'],'ret':r['ret'],'position_wins':r['position_wins']};rows.append(rec);details[(name,timeout,pf)]=r['curve']
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];bf=best['final']
summary={'objective':'causal Top3 allocation: reserve fixed capital weights ex ante, no retroactive overflow reallocation','contract':{'minute_participation_cap':PART,'lag_minutes_after_first_print':LAG,'slippage':SLIP,'roundtrip_cost':COST},'tested':len(rows),'best':best,'top20':rows[:20],'surface':{'within_95pct_best':sum(r['final']>=.95*bf for r in rows),'within_90pct_best':sum(r['final']>=.9*bf for r in rows),'positive':sum(r['final']>START for r in rows)},'best_curve':details[(best['weights'],best['timeout_min'],best['price_field'])]}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
