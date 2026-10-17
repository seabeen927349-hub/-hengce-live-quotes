#!/usr/bin/env python3
import csv,json,math,os,time,urllib.parse,urllib.request
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'capacity_aware_multistock_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;PART=.10;SLIP=.002;COST=.006;SOX5_MAX=-.02;RESMAX=.04;K=25;HOLD=10;LAG=2
API_KEY=os.environ.get('FUGLE_API_KEY')
if not API_KEY:raise SystemExit('FUGLE_API_KEY missing')
def f(x):
 try:return float(str(x).replace(',','').strip())
 except:return None
# SOX
sox=[]
for r in csv.DictReader((ARC/'sox_2026.csv').open(encoding='utf-8')):
 c=f(r['close']);
 if c is not None:sox.append((r['date'],c))
sox.sort();sd=[d for d,_ in sox];sret={sox[i][0]:sox[i][1]/sox[i-1][1]-1 for i in range(1,len(sox))}
def prevus(d):
 z=[u for u in sd if u<d];return z[-1] if z else None
# TWSE
by_t=defaultdict(list);by_d=defaultdict(list)
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
 o=f(r['open']);c=f(r['close'])
 if o is None or c is None:continue
 x={'date':r['date'],'ticker':r['ticker'],'open':o,'close':c};by_t[r['ticker']].append(x);by_d[r['date']].append(x)
for t in by_t:by_t[t].sort(key=lambda x:x['date'])
market_dates=sorted(by_d);mdidx={d:i for i,d in enumerate(market_dates)}
aligned={d:sret.get(prevus(d)) for d in by_d};beta={};prevc={}
for t,rs in by_t.items():
 obs=[];pc=None
 for r in rs:
  prevc[(r['date'],t)]=pc
  sh=aligned.get(r['date'])
  if pc and sh is not None:
   tr=r['close']/pc-1
   if len(obs)>=30:
    z=obs[-60:];mx=sum(a for a,b in z)/len(z);my=sum(b for a,b in z)/len(z);vv=sum((a-mx)**2 for a,b in z)
    beta[(r['date'],t)]=sum((a-mx)*(b-my) for a,b in z)/vv if vv else 0
   obs.append((sh,tr))
  pc=r['close']
feat={}
for d in market_dates:
 u=prevus(d);sh=aligned.get(d)
 if not u or sh is None:continue
 ui=sd.index(u);r5=sox[ui][1]/sox[ui-5][1]-1 if ui>=5 else None;feat[d]={'shock':sh,'sox5':r5}
# Freeze event dates using same no-overlap HOLD=10 calendar rule; rank top 5 using only open-known score.
events=[];busy=''
for d in market_dates:
 if busy and d<=busy:continue
 ft=feat.get(d)
 if not ft or ft['shock']>0 or ft['sox5'] is None or ft['sox5']>SOX5_MAX:continue
 j=mdidx[d]+HOLD-1
 if j>=len(market_dates):continue
 exitd=market_dates[j];cs=[]
 for r in by_d[d]:
  b=beta.get((d,r['ticker']));pc=prevc.get((d,r['ticker']))
  if b is None or not pc:continue
  res=r['open']/pc-1-b*ft['shock']
  if res>RESMAX:continue
  score=b*(1+K*max(-res,0));exitrow=next((x for x in by_t[r['ticker']] if x['date']==exitd),None)
  if exitrow:cs.append({'ticker':r['ticker'],'score':score,'beta':b,'resid':res,'official_open':r['open'],'exit_close':exitrow['close']})
 if not cs:continue
 cs.sort(key=lambda x:x['score'],reverse=True);events.append({'entry':d,'exit':exitd,'shock':ft['shock'],'sox5':ft['sox5'],'candidates':cs[:5]});busy=exitd

def dt(v):
 try:return datetime.fromisoformat(v)
 except:return None
def fetch(sym,d):
 base=f'https://api.fugle.tw/marketdata/v1.0/stock/historical/candles/{sym}';q=urllib.parse.urlencode({'timeframe':'1','from':d,'to':d,'fields':'open,high,low,close,volume,average','sort':'asc'})
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API_KEY,'Accept':'application/json','User-Agent':'HENGCE-Q017-CAPACITY/1.0'})
 for a in range(5):
  try:
   with urllib.request.urlopen(req,timeout=30) as rr:return json.load(rr).get('data',[])
  except Exception:
   if a==4:raise
   time.sleep(2**a)
# add executable lag-2 price and capacity for each candidate
for ev in events:
 for c in ev['candidates']:
  rows=fetch(c['ticker'],ev['entry']);z=[x for x in rows if dt(x.get('date')) and dt(x['date']).hour>=9]
  if not z:continue
  t0=dt(z[0]);target=t0+timedelta(minutes=LAG);hit=next((x for x in z if dt(x['date'])>=target and f(x.get('open'))),None)
  if hit:
   c['entry_time']=hit['date'];c['entry_price']=f(hit['open'])*(1+SLIP);c['minute_volume_lots']=f(hit.get('volume')) or 0;c['capacity_lots']=math.floor(c['minute_volume_lots']*PART)
  time.sleep(.12)

def sim(n):
 cap=START;curve=[];wins=0
 for ev in events:
  remaining=cap;positions=[];event_pnl=0
  for c in ev['candidates'][:n]:
   px=c.get('entry_price');cl=c.get('capacity_lots',0)
   if not px or cl<=0:continue
   afford=math.floor(remaining/(px*1000));lots=min(cl,afford)
   if lots<=0:continue
   invested=lots*1000*px;remaining-=invested;net=c['exit_close']/px-1-COST;pnl=invested*net;event_pnl+=pnl;wins+=net>0
   positions.append({'ticker':c['ticker'],'rank':ev['candidates'].index(c)+1,'score':c['score'],'lots':lots,'invested':invested,'entry_price':px,'exit_close':c['exit_close'],'net':net,'pnl':pnl})
  cap+=event_pnl
  curve.append({'entry':ev['entry'],'exit':ev['exit'],'capital_before':cap-event_pnl,'cash_not_deployed':remaining,'deploy_ratio':1-remaining/(cap-event_pnl) if cap-event_pnl else 0,'event_pnl':event_pnl,'capital':cap,'positions':positions})
 return {'final':cap,'ret':cap/START-1,'events':len(curve),'position_wins':wins,'curve':curve}
res={f'top{n}_sequential':sim(n) for n in (1,2,3,5)}
summary={'objective':'maximize executable capital deployment by routing leftover cash to next-highest pre-trade score candidates','contract':{'boardlot':True,'minute_participation_cap':PART,'lag_minutes_after_first_print':LAG,'slippage':SLIP,'roundtrip_cost':COST,'hold_market_days':HOLD},'results':res,'event_candidate_snapshot':events}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:{'final':v['final'],'ret':v['ret'],'events':v['events']} for k,v in res.items()},ensure_ascii=False,indent=2))
