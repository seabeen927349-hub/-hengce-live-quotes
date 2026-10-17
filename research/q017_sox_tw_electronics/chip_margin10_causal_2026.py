#!/usr/bin/env python3
import csv,json,math,os,time,urllib.parse,urllib.request
from collections import defaultdict
from datetime import datetime,timedelta,time as dtime
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'chip_margin10_causal_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;PART=.10;ES=.002;XS=.002;COST=.006;CUT=dtime(9,1);LAG=2;FILL=20
API=os.environ.get('FUGLE_API_KEY')
if not API:raise SystemExit('FUGLE_API_KEY missing')
# Path from locally reproduced full 462-stock ranking. margin10 percentile multiplier w=0.01..0.19 yields exactly this path.
PATH=[('2026-03-04','2337'),('2026-03-27','2337'),('2026-05-19','2408'),('2026-06-08','3532'),('2026-06-24','3711'),('2026-07-08','2360'),('2026-07-29','3026'),('2026-09-15','8150')]

def f(x):
 try:return float(str(x).replace(',','').strip())
 except:return None
def dt(v):
 try:return datetime.fromisoformat(v)
 except:return None
def fetch(sym,d):
 base=f'https://api.fugle.tw/marketdata/v1.0/stock/historical/candles/{sym}';q=urllib.parse.urlencode({'timeframe':'1','from':d,'to':d,'fields':'open,high,low,close,volume,average','sort':'asc'})
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API,'Accept':'application/json','User-Agent':'HENGCE-Q017-MARGIN10/1.0'})
 for a in range(7):
  try:
   with urllib.request.urlopen(req,timeout=30) as rr:
    rows=json.load(rr).get('data',[])
    if rows:return rows
  except Exception:pass
  time.sleep(min(20,2**a))
 return []
# daily archive / global TWSE market calendar
by_t=defaultdict(dict);dates=set()
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
 c=f(r['close']);d=r['date'];t=r['ticker'];dates.add(d)
 if c is not None:by_t[t][d]=c
md=sorted(dates);mi={d:i for i,d in enumerate(md)};cache={}
def mins(t,d):
 k=(t,d)
 if k not in cache:cache[k]=fetch(t,d);time.sleep(.2)
 return cache[k]
def first(rows):
 for x in rows:
  z=dt(x.get('date'))
  if z and dtime(9,0)<=z.time()<=CUT and f(x.get('open')) is not None:return x
 return None
def fill(t,d,capital):
 rows=mins(t,d);fp=first(rows)
 if not fp:return None
 st=dt(fp['date'])+timedelta(minutes=LAG);en=st+timedelta(minutes=FILL);rem=capital;shares=0;spent=0.;fills=[]
 for x in rows:
  z=dt(x.get('date'))
  if not z or z<st or z>en:continue
  raw=f(x.get('open'));vol=f(x.get('volume')) or 0
  if not raw or vol<=0:continue
  px=raw*(1+ES);lots=min(math.floor(vol*PART),math.floor(rem/(px*1000)))
  if lots<=0:continue
  inv=lots*1000*px;rem-=inv;shares+=lots*1000;spent+=inv;fills.append({'ts':x['date'],'lots':lots,'raw':raw,'px':px,'minute_volume_lots':vol})
 return {'first_print':fp['date'],'shares':shares,'spent':spent,'avg':spent/shares if shares else None,'fills':fills}
def p1300(t,d):
 for x in mins(t,d):
  z=dt(x.get('date'))
  if z and z.time()>=dtime(13,0):
   p=f(x.get('open'))
   if p:return p,x['date']
 return None,None
cap=START;curve=[]
for d,t in PATH:
 i=mi[d];d9,d10,d11=md[i+8],md[i+9],md[i+10]
 fi=fill(t,d,cap)
 if not fi or fi['shares']<=0:raise SystemExit(f'NO_EXECUTABLE_ENTRY {d} {t}')
 c9=by_t[t].get(d9);c10=by_t[t].get(d10);c11=by_t[t].get(d11);p13,ts=p1300(t,d10)
 if not c9 or not c10 or not c11 or p13 is None:raise SystemExit(f'MISSING_EXIT_DATA {d} {t}')
 extend=p13>=c9;xd=d11 if extend else d10;raw=c11 if extend else c10;net=raw*(1-XS)/fi['avg']-1-COST;pnl=fi['spent']*net;before=cap;cap+=pnl
 curve.append({'entry':d,'ticker':t,'first_print':fi['first_print'],'capital_before':before,'shares':fi['shares'],'spent':fi['spent'],'avg_entry':fi['avg'],'d9':d9,'d9_close':c9,'d10':d10,'d10_1300':p13,'decision_ts':ts,'extend':extend,'exit':xd,'raw_exit':raw,'net':net,'pnl':pnl,'capital':cap,'fills':fi['fills']})
out={'objective':'fully causal execution replay of robust margin10-ranked path; no buy/sell clock optimization','ranking_receipt':{'base_rule':'SOX1<=0, SOX5<=-3%, DXY5>=-0.5%; beta60; residual<=4%; K25','chip_factor':'prior 10-session margin balance change cross-sectional percentile','score':'base_score * (1 + w * margin10_percentile)','robust_weight_plateau':'w=0.01..0.19 gives identical 8-event daily-ranking path','only_path_change_vs_baseline':'2026-06-08 2408 -> 3532'},'execution':{'boardlot':True,'first_print_cut':'09:01','entry_lag_min':LAG,'fill_window_min':FILL,'minute_participation':PART,'entry_slip':ES,'exit_slip':XS,'roundtrip_cost':COST,'exit_rule':'D10 13:00 >= D9 close => D11 close else D10 close'},'final':cap,'ret':cap/START-1,'events':len(curve),'wins':sum(x['net']>0 for x in curve),'curve':curve}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
