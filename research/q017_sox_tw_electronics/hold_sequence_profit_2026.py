#!/usr/bin/env python3
import csv,json,math,os,time,urllib.parse,urllib.request
from collections import defaultdict
from datetime import datetime,timedelta,time as dtime
from pathlib import Path

ROOT=Path('research/q017_sox_tw_electronics'); ARC=ROOT/'archive_2026'; OUT=ROOT/'hold_sequence_profit_2026'; OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.; SOX5_MAX=-.02; RESMAX=.04; K=25.; PART=.10; SLIP=.002; EXIT_SLIP=.002; COST=.006; LAG=2; FILL_MIN=20
CUT=dtime(9,1); API=os.environ.get('FUGLE_API_KEY')
if not API: raise SystemExit('FUGLE_API_KEY missing')

def f(x):
 try:return float(str(x).replace(',','').strip())
 except:return None

def dt(v):
 try:return datetime.fromisoformat(v)
 except:return None

def fetch(sym,d):
 base=f'https://api.fugle.tw/marketdata/v1.0/stock/historical/candles/{sym}'
 q=urllib.parse.urlencode({'timeframe':'1','from':d,'to':d,'fields':'open,high,low,close,volume,average','sort':'asc'})
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API,'Accept':'application/json','User-Agent':'HENGCE-Q017-HOLD-SEQUENCE/1.0'})
 last=None
 for a in range(7):
  try:
   with urllib.request.urlopen(req,timeout=30) as rr:
    rows=json.load(rr).get('data',[])
    if rows:return rows
    last='EMPTY'
  except Exception as e:last=repr(e)
  time.sleep(min(30,2**a))
 return []

# Daily panel + SOX alignment.
sox=[]
for r in csv.DictReader((ARC/'sox_2026.csv').open(encoding='utf-8')):
 c=f(r['close'])
 if c is not None:sox.append((r['date'],c))
sox.sort();sd=[d for d,_ in sox];sret={sox[i][0]:sox[i][1]/sox[i-1][1]-1 for i in range(1,len(sox))}
def prevus(d):
 z=[u for u in sd if u<d];return z[-1] if z else None
by_t=defaultdict(list);by_d=defaultdict(list)
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
 o=f(r['open']);c=f(r['close'])
 if o is None or c is None:continue
 x={'date':r['date'],'ticker':r['ticker'],'open':o,'close':c};by_t[r['ticker']].append(x);by_d[r['date']].append(x)
for t in by_t:by_t[t].sort(key=lambda x:x['date'])
market_dates=sorted(by_d);md={d:i for i,d in enumerate(market_dates)};last_date=market_dates[-1]
aligned={d:sret.get(prevus(d)) for d in market_dates};beta={};prevc={}
for t,rs in by_t.items():
 obs=[];pc=None
 for r in rs:
  prevc[(r['date'],t)]=pc;sh=aligned.get(r['date'])
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

# Daily-score ranking is safe as an ordering device: official open is the first print. We traverse from highest score downward and only accept names whose first print existed by 09:01.
ranked={}
for d in market_dates:
 ft=feat.get(d);lst=[]
 if not ft or ft['shock']>0 or ft['sox5'] is None or ft['sox5']>SOX5_MAX: ranked[d]=[];continue
 for r in by_d[d]:
  b=beta.get((d,r['ticker']));pc=prevc.get((d,r['ticker']))
  if b is None or b<=0 or not pc:continue
  res=r['open']/pc-1-b*ft['shock']
  if res>RESMAX:continue
  score=b*(1+K*max(-res,0));lst.append({'ticker':r['ticker'],'score':score,'beta':b,'resid':res,'official_open':r['open']})
 lst.sort(key=lambda x:x['score'],reverse=True);ranked[d]=lst

minute_cache={};selection_cache={}
def minutes(t,d):
 key=(t,d)
 if key not in minute_cache:
  minute_cache[key]=fetch(t,d);time.sleep(.32)
 return minute_cache[key]
def first_print_by(rows):
 hits=[]
 for x in rows:
  z=dt(x.get('date'))
  if z and dtime(9,0)<=z.time()<=CUT and f(x.get('open')) is not None:hits.append(x)
 return hits[0] if hits else None

def select(d):
 if d in selection_cache:return selection_cache[d]
 for c in ranked.get(d,[]):
  rows=minutes(c['ticker'],d);fp=first_print_by(rows)
  if fp:
   # score already uses this same official first print; no lower-ranked name can beat it.
   out={**c,'first_print':fp['date']};selection_cache[d]=out;return out
 selection_cache[d]=None;return None

def entry_fill(c,d,capital):
 rows=minutes(c['ticker'],d);fp=first_print_by(rows)
 if not fp:return 0,0.,[]
 t0=dt(fp['date']);start=t0+timedelta(minutes=LAG);end=start+timedelta(minutes=FILL_MIN);rem=capital;shares=0;spent=0.;fills=[]
 for x in rows:
  z=dt(x.get('date'))
  if not z or z<start or z>end:continue
  raw=f(x.get('open'));vol=f(x.get('volume')) or 0
  if not raw or raw<=0 or vol<=0:continue
  px=raw*(1+SLIP);lots=min(math.floor(vol*PART),math.floor(rem/(px*1000)))
  if lots<=0:continue
  inv=lots*1000*px;rem-=inv;shares+=lots*1000;spent+=inv;fills.append({'time':x['date'],'lots':lots,'raw':raw,'px':px})
 return shares,spent,fills

def close_for(t,d):
 row=next((x for x in by_t[t] if x['date']==d),None);return row['close'] if row else None

def run(hold):
 cap=START;busy_until=None;events=[]
 for d in market_dates:
  # capital is unavailable through the planned exit session.
  if busy_until and d<=busy_until:continue
  ft=feat.get(d)
  if not ft or ft['shock']>0 or ft['sox5'] is None or ft['sox5']>SOX5_MAX:continue
  c=select(d)
  if not c:continue
  sh,spent,fills=entry_fill(c,d,cap)
  if sh<=0:continue
  planned_i=md[d]+hold-1;planned_exit=market_dates[planned_i] if planned_i<len(market_dates) else None
  exitd=planned_exit or last_date;raw=close_for(c['ticker'],exitd)
  if not raw:continue
  sell=raw*(1-EXIT_SLIP);net=sell/(spent/sh)-1-COST;pnl=spent*net;before=cap;cap+=pnl
  completed=planned_exit is not None
  events.append({'entry':d,'planned_exit':planned_exit,'valuation_date':exitd,'completed':completed,'ticker':c['ticker'],'score':c['score'],'beta':c['beta'],'resid':c['resid'],'capital_before':before,'shares':sh,'spent':spent,'deploy_ratio':spent/before,'avg_entry':spent/sh,'raw_exit_or_mtm':raw,'net_or_mtm':net,'capital':cap})
  busy_until=planned_exit or last_date
 return {'hold':hold,'final':cap,'ret':cap/START-1,'events':len(events),'completed':sum(e['completed'] for e in events),'open_mtm':sum(not e['completed'] for e in events),'wins_or_positive_mtm':sum(e['net_or_mtm']>0 for e in events),'curve':events}

rows=[];details={}
for h in range(8,21):
 r=run(h);details[h]=r['curve'];rows.append({k:v for k,v in r.items() if k!='curve'})
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];base=next(x for x in rows if x['hold']==10)
out={'objective':'maximize 2026-10-16 marked-to-market capital with hold-specific non-overlap event sequence','contract':{'single_capital_sleeve':True,'fixed_decision_cutoff':'09:01','selection':'PIT beta/residual score; only names printed by cutoff','entry':'first print +2m through +20m','boardlot':True,'minute_participation':PART,'entry_slippage':SLIP,'exit_or_mtm_slippage':EXIT_SLIP,'roundtrip_cost_applied_to_completed_or_mtm_proxy':COST,'terminal_date':last_date},'tested':len(rows),'baseline_hold10':base,'best':best,'best_is_boundary':best['hold'] in (8,20),'top10':rows[:10],'all':sorted(rows,key=lambda x:x['hold']),'best_curve':details[best['hold']]}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
