#!/usr/bin/env python3
import json,math,os,time,urllib.parse,urllib.request
from datetime import datetime,timedelta
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');SRC=ROOT/'capacity_aware_multistock_2026'/'summary.json';OUT=ROOT/'entry_price_cap_profit_2026';OUT.mkdir(parents=True,exist_ok=True)
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
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API,'Accept':'application/json','User-Agent':'HENGCE-Q017-ENTRY-CAP/1.0'})
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
 cache[key]={'t0':dt(z[0]['date']),'rows':z,'reference':f(z[0].get('open'))};time.sleep(.3)
def sim(cap_pct,field='open'):
 cap=START;curve=[];wins=0
 for ev in events:
  c=ev['candidates'][0];z=cache[(c['ticker'],ev['entry'])];ref=z['reference'];start=z['t0']+timedelta(minutes=LAG);end=start+timedelta(minutes=TIMEOUT);remaining=cap;shares=0;spent=0.
  limit=None if cap_pct is None else ref*(1+cap_pct)
  for x in z['rows']:
   t=dt(x['date'])
   if not t or t<start or t>end:continue
   raw=f(x.get(field));vol=f(x.get('volume')) or 0
   if not raw or raw<=0 or vol<=0:continue
   if limit is not None and raw>limit:continue
   px=raw*(1+SLIP);lots=min(math.floor(vol*PART),math.floor(remaining/(px*1000)))
   if lots<=0:continue
   inv=lots*1000*px;remaining-=inv;shares+=lots*1000;spent+=inv
  if shares<=0:
   curve.append({'entry':ev['entry'],'ticker':c['ticker'],'capital_before':cap,'capital':cap,'deploy_ratio':0,'no_fill':True});continue
  avg=spent/shares;net=c['exit_close']/avg-1-COST;pnl=spent*net;before=cap;cap+=pnl;wins+=net>0
  curve.append({'entry':ev['entry'],'ticker':c['ticker'],'capital_before':before,'deploy_ratio':spent/before,'reference':ref,'limit':limit,'shares':shares,'avg_entry':avg,'net':net,'capital':cap})
 return {'cap_pct':cap_pct,'field':field,'final':cap,'ret':cap/START-1,'n':len(curve),'filled_events':sum(not x.get('no_fill') for x in curve),'wins':wins,'curve':curve}
vals=[None,-.02,-.01,-.005,0,.005,.01,.015,.02,.03]
rows=[];details={}
for v in vals:
 for field in ('open','high'):
  r=sim(v,field);k=f'{v}_{field}';details[k]=r['curve'];rows.append({x:y for x,y in r.items() if x!='curve'})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];base=next(x for x in rows if x['cap_pct'] is None and x['field']=='open')
# local robustness around best among open-field caps
openrows=sorted([x for x in rows if x['field']=='open'],key=lambda x:(999 if x['cap_pct'] is None else x['cap_pct']))
out={'objective':'increase 2M terminal capital only through causal no-chase entry price caps','baseline':base,'best':best,'improvement':best['final']-base['final'],'open_cap_curve':openrows,'grid':rows,'best_curve':details[f"{best['cap_pct']}_{best['field']}"]}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
