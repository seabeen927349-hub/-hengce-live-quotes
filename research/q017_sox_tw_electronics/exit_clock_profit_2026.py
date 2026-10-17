#!/usr/bin/env python3
import csv,json,math,os,time,urllib.parse,urllib.request
from datetime import datetime,time as dtime
from pathlib import Path

ROOT=Path('research/q017_sox_tw_electronics'); ARC=ROOT/'archive_2026'; OUT=ROOT/'exit_clock_profit_2026'; OUT.mkdir(parents=True,exist_ok=True)
BASE=ROOT/'fixed_clock_selection_2026'/'summary.json'
START=2_000_000.; ENTRY_SLIP=.002; EXIT_SLIP=.002; COST=.006; PART=.10; FILL_MIN=20
API=os.environ.get('FUGLE_API_KEY')
if not API: raise SystemExit('FUGLE_API_KEY missing')

def f(x):
 try:return float(str(x).replace(',','').strip())
 except:return None

def fetch(sym,d):
 base=f'https://api.fugle.tw/marketdata/v1.0/stock/historical/candles/{sym}'
 q=urllib.parse.urlencode({'timeframe':'1','from':d,'to':d,'fields':'open,high,low,close,volume,average','sort':'asc'})
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API,'Accept':'application/json','User-Agent':'HENGCE-Q017-EXIT-CLOCK/1.0'})
 for a in range(5):
  try:
   with urllib.request.urlopen(req,timeout=30) as r:return json.load(r).get('data',[])
  except Exception:
   if a==4:return []
   time.sleep(2**a)

def dt(v):
 try:return datetime.fromisoformat(v)
 except:return None

# global TWSE dates + closes
by_t={}; dates=set()
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
 t=r['ticker']; d=r['date']; c=f(r['close']); dates.add(d)
 if c is not None: by_t.setdefault(t,{})[d]=c
market_dates=sorted(dates); di={d:i for i,d in enumerate(market_dates)}
base=json.loads(BASE.read_text(encoding='utf-8'))
events=[x for x in base['best_curve'] if x.get('ticker')]
# lock causal selection from validated replay; only execution timing changes.
locked=[{'entry':e['entry'],'ticker':e['ticker']} for e in events]
cache={}
for e in locked:
 t=e['ticker']; d=e['entry']; cache[(t,d)]=fetch(t,d); time.sleep(.12)
 i=di[d]
 for hold in (9,10,11):
  j=i+hold-1
  if j<len(market_dates):
   xd=market_dates[j]; cache[(t,xd)]=fetch(t,xd); time.sleep(.12)

def entry_fill(t,d,capital):
 rows=cache.get((t,d),[]); remaining=capital; shares=0; spent=0.;fills=[]
 start=datetime.fromisoformat(d+'T09:02:00+08:00'); end=datetime.fromisoformat(d+'T09:22:00+08:00')
 for x in rows:
  z=dt(x.get('date'))
  if not z or z<start or z>end:continue
  raw=f(x.get('open')); vol=f(x.get('volume')) or 0
  if not raw or vol<=0:continue
  px=raw*(1+ENTRY_SLIP); maxlots=math.floor(vol*PART); afford=math.floor(remaining/(px*1000)); lots=min(maxlots,afford)
  if lots<=0:continue
  inv=lots*1000*px;remaining-=inv;shares+=lots*1000;spent+=inv;fills.append((x['date'],lots,raw,px))
 return shares,spent,fills

def minute_px(t,d,hhmm,field):
 h,m=map(int,hhmm.split(':')); target=dtime(h,m)
 rows=cache.get((t,d),[])
 for x in rows:
  z=dt(x.get('date'))
  if z and z.time()>=target:
   p=f(x.get(field))
   if p and p>0:return p,x['date']
 return None,None

def simulate(hold,hhmm,field):
 cap=START;curve=[]
 for e in locked:
  d=e['entry'];t=e['ticker']; i=di[d]; j=i+hold-1
  if j>=len(market_dates):continue
  xd=market_dates[j]
  sh,spent,fills=entry_fill(t,d,cap)
  if sh<=0: curve.append({'entry':d,'ticker':t,'capital':cap,'reason':'NO_ENTRY_FILL'});continue
  if hhmm=='CLOSE': raw=by_t.get(t,{}).get(xd);ts=xd+' CLOSE'
  else: raw,ts=minute_px(t,xd,hhmm,field)
  if not raw: curve.append({'entry':d,'ticker':t,'exit':xd,'capital':cap,'reason':'NO_EXIT_PRICE'});continue
  sell=raw*(1-EXIT_SLIP); gross=(sell/(spent/sh))-1; net=gross-COST; pnl=spent*net; before=cap;cap+=pnl
  curve.append({'entry':d,'exit':xd,'ticker':t,'capital_before':before,'shares':sh,'spent':spent,'avg_entry':spent/sh,'raw_exit':raw,'exit_price':sell,'exit_ts':ts,'net':net,'pnl':pnl,'capital':cap})
 return {'hold':hold,'time':hhmm,'field':field,'final':cap,'ret':cap/START-1,'n':len(curve),'wins':sum(x.get('net',-9)>0 for x in curve),'curve':curve}

rows=[];details={}
for hold in (9,10,11):
 for tm in ('13:00','13:10','13:20','13:25','13:28','13:29','CLOSE'):
  fields=('open','low') if tm!='CLOSE' else ('close',)
  for field in fields:
   r=simulate(hold,tm,field); key=f'{hold}_{tm}_{field}';details[key]=r['curve'];rows.append({k:v for k,v in r.items() if k!='curve'})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];base10=next(x for x in rows if x['hold']==10 and x['time']=='CLOSE')
out={'objective':'only retain exit timing that increases executable 2M terminal capital','contract':{'locked_selection':'validated 09:01 causal Top1','entry_window':'09:02-09:22','boardlot':True,'minute_participation':PART,'entry_slippage':ENTRY_SLIP,'exit_slippage':EXIT_SLIP,'roundtrip_cost':COST},'tested':len(rows),'baseline_D10_close':base10,'best':best,'improvement_vs_D10_close':best['final']-base10['final'],'grid':rows,'best_curve':details[f"{best['hold']}_{best['time']}_{best['field']}"]}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False,indent=2))
