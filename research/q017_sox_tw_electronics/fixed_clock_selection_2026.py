#!/usr/bin/env python3
import csv,json,math,os,time,urllib.parse,urllib.request
from collections import defaultdict
from datetime import datetime,timedelta,time as dtime
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'fixed_clock_selection_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;PART=.10;SLIP=.002;COST=.006;HOLD=10;K=25;SOX5_MAX=-.02;RESMAX=.04;FILL_MIN=20
API_KEY=os.environ.get('FUGLE_API_KEY')
if not API_KEY:raise SystemExit('FUGLE_API_KEY missing')
def f(x):
 try:return float(str(x).replace(',','').strip())
 except:return None
def dt(v):
 try:return datetime.fromisoformat(v)
 except:return None
# Daily archive and PIT beta.
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
market_dates=sorted(by_d);mdidx={d:i for i,d in enumerate(market_dates)};aligned={d:sret.get(prevus(d)) for d in by_d};beta={};prevc={}
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
# Event dates are premarket-known SOX gate only, with no overlap based on fixed 10-day hold.
event_dates=[];busy=''
for d in market_dates:
 if busy and d<=busy:continue
 ft=feat.get(d)
 if not ft or ft['shock']>0 or ft['sox5'] is None or ft['sox5']>SOX5_MAX:continue
 j=mdidx[d]+HOLD-1
 if j>=len(market_dates):continue
 event_dates.append((d,market_dates[j]));busy=market_dates[j]

def fetch(sym,d):
 base=f'https://api.fugle.tw/marketdata/v1.0/stock/historical/candles/{sym}';q=urllib.parse.urlencode({'timeframe':'1','from':d,'to':d,'fields':'open,high,low,close,volume,average','sort':'asc'})
 req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API_KEY,'Accept':'application/json','User-Agent':'HENGCE-Q017-FIXED-CLOCK/1.0'})
 for a in range(5):
  try:
   with urllib.request.urlopen(req,timeout=30) as rr:return json.load(rr).get('data',[])
  except Exception:
   if a==4:return []
   time.sleep(2**a)
# Reduce API volume without outcome filtering: only candidates with PIT beta > 0 and daily residual <= gate can ever be selected by current score.
# Fetch minute data for all such eligible names on the 9 event dates so fixed-clock ranking is causal.
cache={};elig={}
for d,exitd in event_dates:
 ft=feat[d];lst=[]
 for r in by_d[d]:
  b=beta.get((d,r['ticker']));pc=prevc.get((d,r['ticker']))
  if b is None or b<=0 or not pc:continue
  daily_res=r['open']/pc-1-b*ft['shock']
  if daily_res<=RESMAX:lst.append(r['ticker'])
 elig[d]=lst
 for n,t in enumerate(lst,1):
  cache[(d,t)]=fetch(t,d)
  time.sleep(.08)
 print(f'{d} fetched {len(lst)} candidates',flush=True)

def first_print_by(rows,cutoff):
 hits=[]
 for x in rows:
  z=dt(x.get('date'))
  if z and z.time()<=cutoff and z.time()>=dtime(9,0) and f(x.get('open')) is not None:hits.append(x)
 return hits[0] if hits else None

def exit_close(ticker,exitd):
 r=next((x for x in by_t[ticker] if x['date']==exitd),None);return r['close'] if r else None

def simulate(cut_h,cut_m,price_field='open'):
 cap=START;curve=[];wins=0
 cutoff=dtime(cut_h,cut_m)
 for d,exitd in event_dates:
  ft=feat[d];cand=[]
  for t in elig[d]:
   first=first_print_by(cache.get((d,t),[]),cutoff)
   if not first:continue
   px0=f(first.get('open'));pc=prevc.get((d,t));b=beta.get((d,t))
   if not px0 or not pc or b is None:continue
   res=px0/pc-1-b*ft['shock']
   if res>RESMAX:continue
   score=b*(1+K*max(-res,0));cand.append((score,t,b,res,first['date']))
  if not cand:
   curve.append({'entry':d,'exit':exitd,'capital_before':cap,'capital':cap,'reason':'NO_OPENED_CANDIDATE'});continue
  score,t,b,res,first_ts=max(cand,key=lambda x:x[0]);rows=cache[(d,t)];decision=datetime.fromisoformat(d+'T'+f'{cut_h:02d}:{cut_m:02d}:00+08:00');start=decision+timedelta(minutes=1);end=start+timedelta(minutes=FILL_MIN)
  remaining=cap;shares=0;spent=0.;fills=[]
  for x in rows:
   z=dt(x.get('date'))
   if not z or z<start or z>end:continue
   raw=f(x.get(price_field));lotsvol=f(x.get('volume')) or 0
   if not raw or raw<=0 or lotsvol<=0:continue
   px=raw*(1+SLIP);caplots=math.floor(lotsvol*PART);afford=math.floor(remaining/(px*1000));lots=min(caplots,afford)
   if lots<=0:continue
   inv=lots*1000*px;remaining-=inv;shares+=lots*1000;spent+=inv;fills.append({'time':x['date'],'lots':lots,'raw_px':raw,'stressed_px':px})
  ex=exit_close(t,exitd)
  if shares<=0 or not ex:
   curve.append({'entry':d,'exit':exitd,'ticker':t,'score':score,'resid':res,'capital_before':cap,'capital':cap,'reason':'NO_FILL'});continue
  avg=spent/shares;net=ex/avg-1-COST;pnl=spent*net;before=cap;cap+=pnl;wins+=net>0
  curve.append({'entry':d,'exit':exitd,'ticker':t,'score':score,'beta':b,'resid':res,'first_print':first_ts,'decision_cutoff':f'{cut_h:02d}:{cut_m:02d}','capital_before':before,'shares':shares,'spent':spent,'deploy_ratio':spent/before,'avg_entry':avg,'exit_close':ex,'net':net,'pnl':pnl,'capital':cap,'fills':fills})
 return {'cutoff':f'{cut_h:02d}:{cut_m:02d}','price_field':price_field,'final':cap,'ret':cap/START-1,'events':len(curve),'wins':wins,'curve':curve}
rows=[];details={}
for h,m in [(9,1),(9,3),(9,5),(9,10),(9,15),(9,20),(9,25),(9,30)]:
 for pf in ('open','high'):
  r=simulate(h,m,pf);rec={k:v for k,v in r.items() if k!='curve'};rows.append(rec);details[(rec['cutoff'],pf)]=r['curve']
rows.sort(key=lambda x:x['final'],reverse=True);best=rows[0];bf=best['final']
summary={'objective':'fully causal fixed-clock selection: rank only stocks that have actually printed by decision time, then buy starting next minute','contract':{'hold_days':HOLD,'overshoot_k':K,'sox5_max':SOX5_MAX,'resid_max':RESMAX,'boardlot':True,'minute_participation_cap':PART,'slippage':SLIP,'roundtrip_cost':COST,'fill_window_min':FILL_MIN},'eligible_fetch_counts':{d:len(v) for d,v in elig.items()},'tested':len(rows),'best':best,'grid':rows,'surface':{'within_95pct_best':sum(r['final']>=.95*bf for r in rows),'within_90pct_best':sum(r['final']>=.9*bf for r in rows),'positive':sum(r['final']>START for r in rows)},'best_curve':details[(best['cutoff'],best['price_field'])]}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
