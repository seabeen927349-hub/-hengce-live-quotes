#!/usr/bin/env python3
import csv,json,math,os,time,urllib.parse,urllib.request
from datetime import datetime,timedelta,time as dtime
from pathlib import Path

ROOT=Path('research/q017_sox_tw_electronics'); ARC=ROOT/'archive_2026'; OUT=ROOT/'exit_clock_profit_2026'; OUT.mkdir(parents=True,exist_ok=True)
SRC=ROOT/'capacity_aware_multistock_2026'/'summary.json'; VALID=ROOT/'top1_20m_hard_stress_2026'/'summary.json'
START=2_000_000.; ENTRY_SLIP=.002; EXIT_SLIP=.002; COST=.006; PART=.10; LAG=2; FILL_MIN=20
API=os.environ.get('FUGLE_API_KEY')
if not API: raise SystemExit('FUGLE_API_KEY missing')

def f(x):
 try:return float(str(x).replace(',','').strip())
 except:return None

def fetch(sym,d):
 base=f'https://api.fugle.tw/marketdata/v1.0/stock/historical/candles/{sym}'
 q=urllib.parse.urlencode({'timeframe':'1','from':d,'to':d,'fields':'open,high,low,close,volume,average','sort':'asc'})
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API,'Accept':'application/json','User-Agent':'HENGCE-Q017-EXIT-CLOCK/1.1'})
 for a in range(5):
  try:
   with urllib.request.urlopen(req,timeout=30) as r:return json.load(r).get('data',[])
  except Exception:
   if a==4:return []
   time.sleep(2**a)

def dt(v):
 try:return datetime.fromisoformat(v)
 except:return None

by_t={}; dates=set()
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
 t=r['ticker']; d=r['date']; c=f(r['close']); dates.add(d)
 if c is not None: by_t.setdefault(t,{})[d]=c
market_dates=sorted(dates); di={d:i for i,d in enumerate(market_dates)}
snap=json.loads(SRC.read_text(encoding='utf-8'))['event_candidate_snapshot']
locked=[{'entry':ev['entry'],'ticker':ev['candidates'][0]['ticker']} for ev in snap]
cache={}
for e in locked:
 t=e['ticker']; d=e['entry']; cache[(t,d)]=fetch(t,d); time.sleep(.12)
 i=di[d]
 for hold in (9,10,11,12):
  j=i+hold-1
  if j<len(market_dates):
   xd=market_dates[j]; cache[(t,xd)]=fetch(t,xd); time.sleep(.12)

def entry_fill(t,d,capital,slip=ENTRY_SLIP):
 rows=cache.get((t,d),[]); tradable=[x for x in rows if dt(x.get('date')) and dt(x['date']).hour>=9]
 if not tradable:return 0,0.,[]
 t0=dt(tradable[0]['date']); start=t0+timedelta(minutes=LAG); end=start+timedelta(minutes=FILL_MIN)
 remaining=capital; shares=0; spent=0.;fills=[]
 for x in tradable:
  z=dt(x.get('date'))
  if not z or z<start or z>end:continue
  raw=f(x.get('open')); vol=f(x.get('volume')) or 0
  if not raw or vol<=0:continue
  px=raw*(1+slip); maxlots=math.floor(vol*PART); afford=math.floor(remaining/(px*1000)); lots=min(maxlots,afford)
  if lots<=0:continue
  inv=lots*1000*px; remaining-=inv; shares+=lots*1000; spent+=inv; fills.append((x['date'],lots,raw,px))
 return shares,spent,fills

def minute_px(t,d,hhmm,field):
 h,m=map(int,hhmm.split(':')); target=dtime(h,m)
 for x in cache.get((t,d),[]):
  z=dt(x.get('date'))
  if z and z.time()>=target:
   p=f(x.get(field))
   if p and p>0:return p,x['date']
 return None,None

def simulate(hold,hhmm,field,exit_slip=EXIT_SLIP):
 cap=START;curve=[]
 for e in locked:
  d=e['entry'];t=e['ticker'];i=di[d];j=i+hold-1
  if j>=len(market_dates):continue
  xd=market_dates[j];sh,spent,fills=entry_fill(t,d,cap)
  if sh<=0:curve.append({'entry':d,'ticker':t,'capital':cap,'reason':'NO_ENTRY_FILL'});continue
  if hhmm=='CLOSE':raw=by_t.get(t,{}).get(xd);ts=xd+' CLOSE'
  else:raw,ts=minute_px(t,xd,hhmm,field)
  if not raw:curve.append({'entry':d,'ticker':t,'exit':xd,'capital':cap,'reason':'NO_EXIT_PRICE'});continue
  sell=raw*(1-exit_slip);net=sell/(spent/sh)-1-COST;pnl=spent*net;before=cap;cap+=pnl
  curve.append({'entry':d,'exit':xd,'ticker':t,'capital_before':before,'shares':sh,'spent':spent,'avg_entry':spent/sh,'raw_exit':raw,'exit_price':sell,'exit_ts':ts,'net':net,'pnl':pnl,'capital':cap})
 return {'hold':hold,'time':hhmm,'field':field,'exit_slip':exit_slip,'final':cap,'ret':cap/START-1,'n':len(curve),'wins':sum(x.get('net',-9)>0 for x in curve),'curve':curve}

validated=json.loads(VALID.read_text(encoding='utf-8'))['anchors']['base']['final']
control=simulate(10,'CLOSE','close',0.0)
if abs(control['final']-validated)>1.0:
 raise SystemExit(f'BASE_REPRO_FAIL got={control["final"]} expected={validated}')
rows=[];details={}
for hold in (9,10,11,12):
 for tm in ('13:00','13:10','13:20','13:25','13:28','13:29','CLOSE'):
  fields=('open','low') if tm!='CLOSE' else ('close',)
  for field in fields:
   r=simulate(hold,tm,field,EXIT_SLIP);key=f'{hold}_{tm}_{field}';details[key]=r['curve'];rows.append({k:v for k,v in r.items() if k!='curve'})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];base10=next(x for x in rows if x['hold']==10 and x['time']=='CLOSE')
out={'objective':'retain only executable exit timing that increases 2M terminal capital','reproduction_control':{'expected':validated,'actual':control['final'],'pass':True},'contract':{'locked_selection':'capacity snapshot causal Top1','entry_rule':'first print +2 minutes, then 20-minute fill window','boardlot':True,'minute_participation':PART,'entry_slippage':ENTRY_SLIP,'exit_slippage':EXIT_SLIP,'roundtrip_cost':COST},'tested':len(rows),'baseline_D10_close_with_exit_slip':base10,'best':best,'improvement_vs_D10_close':best['final']-base10['final'],'grid':rows,'best_curve':details[f"{best['hold']}_{best['time']}_{best['field']}"]}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
