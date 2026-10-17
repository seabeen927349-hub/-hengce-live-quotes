#!/usr/bin/env python3
import json,math,os,time,urllib.parse,urllib.request
from datetime import datetime,timedelta
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');SRC=ROOT/'capacity_aware_multistock_2026'/'summary.json';OUT=ROOT/'top1_20m_hard_stress_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;LAG=2;TIMEOUT=20;COST0=.006
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
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API_KEY,'Accept':'application/json','User-Agent':'HENGCE-Q017-HARD-STRESS/1.0'})
 for a in range(5):
  try:
   with urllib.request.urlopen(req,timeout=30) as rr:return json.load(rr).get('data',[])
  except Exception:
   if a==4:raise
   time.sleep(2**a)
cache={}
for ev in events:
 c=ev['candidates'][0];key=(c['ticker'],ev['entry']);rows=fetch(*key);z=[x for x in rows if dt(x.get('date')) and dt(x['date']).hour>=9]
 if z:cache[key]={'t0':dt(z[0]['date']),'rows':z}
 time.sleep(.12)

def event_fill(ev,capital,part,slip,pfield):
 c=ev['candidates'][0];z=cache.get((c['ticker'],ev['entry']))
 if not z or not z['t0']:return {'shares':0,'spent':0.0,'fills':[],'ticker':c['ticker'],'exit_close':c['exit_close']}
 start=z['t0']+timedelta(minutes=LAG);end=start+timedelta(minutes=TIMEOUT);remaining=capital;shares=0;spent=0.0;fills=[]
 for x in z['rows']:
  t=dt(x['date'])
  if not t or t<start or t>end:continue
  raw=f(x.get(pfield));lotsvol=f(x.get('volume')) or 0
  if not raw or raw<=0 or lotsvol<=0:continue
  px=raw*(1+slip);caplots=math.floor(lotsvol*part);afford=math.floor(remaining/(px*1000));lots=min(caplots,afford)
  if lots<=0:continue
  inv=lots*1000*px;remaining-=inv;shares+=lots*1000;spent+=inv;fills.append({'time':x['date'],'lots':lots,'raw_px':raw,'stressed_px':px})
 return {'shares':shares,'spent':spent,'fills':fills,'ticker':c['ticker'],'exit_close':c['exit_close'],'cash':remaining}

def simulate(part,slip,cost,pfield,exclude=None):
 exclude=set(exclude or []);cap=START;curve=[];wins=0
 for ev in events:
  if ev['entry'] in exclude:continue
  before=cap;fill=event_fill(ev,before,part,slip,pfield)
  if fill['shares']<=0:
   curve.append({'entry':ev['entry'],'ticker':fill['ticker'],'capital_before':before,'capital':cap,'shares':0});continue
  avg=fill['spent']/fill['shares'];net=fill['exit_close']/avg-1-cost;pnl=fill['spent']*net;cap+=pnl;wins+=net>0
  curve.append({'entry':ev['entry'],'ticker':fill['ticker'],'capital_before':before,'shares':fill['shares'],'spent':fill['spent'],'deploy_ratio':fill['spent']/before,'avg_entry':avg,'net':net,'pnl':pnl,'capital':cap,'fills':fill['fills']})
 return {'final':cap,'ret':cap/START-1,'events':len(curve),'wins':wins,'curve':curve}

rows=[];details={}
for part in (.02,.05,.10):
 for slip in (.002,.003,.005):
  for cost in (.006,.008,.010):
   for pf in ('open','high'):
    r=simulate(part,slip,cost,pf);rec={'participation':part,'slippage':slip,'cost':cost,'price_field':pf,'final':r['final'],'ret':r['ret'],'events':r['events'],'wins':r['wins']};rows.append(rec);details[(part,slip,cost,pf)]=r['curve']
# Predeclared practical base and conservative anchors.
anchors={}
for name,key in {'base':(.10,.002,.006,'open'),'high_price':(.10,.002,.006,'high'),'5pct_capacity':(.05,.002,.006,'open'),'2pct_capacity':(.02,.002,.006,'open'),'cost1pct':(.10,.002,.010,'open'),'slip05pct':(.10,.005,.006,'open'),'hard_combo':(.05,.005,.010,'high')}.items():
 r=simulate(*key);anchors[name]={k:v for k,v in r.items() if k!='curve'}
# Concentration under fixed practical base: determine event PnL from base curve, then rerun excluding top events.
base=simulate(.10,.002,.006,'open');ranked=sorted([x for x in base['curve'] if 'pnl' in x],key=lambda x:x['pnl'],reverse=True)
concentration={'base':{k:v for k,v in base.items() if k!='curve'}}
for n in (1,2,3):
 r=simulate(.10,.002,.006,'open',[x['entry'] for x in ranked[:n]]);concentration[f'remove_top_{n}']={k:v for k,v in r.items() if k!='curve'}
rows.sort(key=lambda x:x['final'],reverse=True)
summary={'objective':'hard-stress fully causal Top1 20-minute execution','contract':{'boardlot':True,'lag_minutes_after_first_print':LAG,'timeout_min':TIMEOUT},'tested':len(rows),'anchors':anchors,'concentration':concentration,'top20':rows[:20]}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
