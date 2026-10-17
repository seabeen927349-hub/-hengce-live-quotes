#!/usr/bin/env python3
import csv,json,math,os,time,urllib.parse,urllib.request
from collections import defaultdict
from datetime import datetime,time as dtime
from pathlib import Path
ROOT=Path('research/q017_sox_tw_electronics'); ARC=ROOT/'archive_2026'; CACHE=ROOT/'chip_teacher_combo_screen_2026'/'cache'; OUT=ROOT/'replay_20261014_hscore'; OUT.mkdir(parents=True,exist_ok=True)
TARGET='2026-10-14'; K=25.; RESMAX=.04; CUT=dtime(9,1); API=os.environ.get('FUGLE_API_KEY')

def f(x):
 try:return float(str(x).replace(',','').strip())
 except:return None

def dt(x):
 try:return datetime.fromisoformat(x)
 except:return None

def load(p):
 a=[]
 for r in csv.DictReader(p.open(encoding='utf-8')):
  c=f(r['close'])
  if c is not None:a.append((r['date'],c))
 a.sort();return a

def prev(ds,d):
 z=[x for x in ds if x<d];return z[-1] if z else None

def fetch(sym,d):
 if not API:return []
 q=urllib.parse.urlencode({'timeframe':'1','from':d,'to':d,'fields':'open,high,low,close,volume,average','sort':'asc'})
 req=urllib.request.Request(f'https://api.fugle.tw/marketdata/v1.0/stock/historical/candles/{sym}?{q}',headers={'X-API-KEY':API,'Accept':'application/json','User-Agent':'HENGCE-REPLAY-20261014/1.0'})
 try:
  with urllib.request.urlopen(req,timeout=30) as rr:return json.load(rr).get('data',[])
 except:return []

def visible(sym,d):
 rows=fetch(sym,d)
 if not rows:return True
 for x in rows:
  z=dt(x.get('date'))
  if z and dtime(9,0)<=z.time()<=CUT and f(x.get('open')) is not None:return True
 return False

def pct(v,hist):
 hist=[x for x in hist if x is not None]
 if not hist:return .5
 return sum(x<=v for x in hist)/len(hist)

sox=load(ARC/'sox_2026.csv'); dxy=load(ARC/'dxy_2026.csv'); sd=[d for d,_ in sox]; dd=[d for d,_ in dxy]; sret={sox[i][0]:sox[i][1]/sox[i-1][1]-1 for i in range(1,len(sox))}
by_t=defaultdict(list);by_d=defaultdict(list);names={}
for r in csv.DictReader((ARC/'twse_electronics_membership_2026.csv').open(encoding='utf-8')):
 o=f(r.get('open'));c=f(r.get('close'));t=r.get('ticker')
 if o is None or c is None or not t:continue
 names[t]=r.get('name') or r.get('company_name') or ''
 x={'date':r['date'],'ticker':t,'open':o,'close':c};by_t[t].append(x);by_d[r['date']].append(x)
for t in by_t:by_t[t].sort(key=lambda x:x['date'])
md=sorted(by_d);mi={d:i for i,d in enumerate(md)};aligned={d:sret.get(prev(sd,d)) for d in md};beta={};prevc={}
for t,rs in by_t.items():
 obs=[];pc=None
 for r in rs:
  d=r['date'];prevc[(d,t)]=pc;sh=aligned.get(d)
  if pc and sh is not None:
   tr=r['close']/pc-1
   if len(obs)>=30:
    z=obs[-60:];mx=sum(a for a,b in z)/len(z);my=sum(b for a,b in z)/len(z);vv=sum((a-mx)**2 for a,b in z);beta[(d,t)]=sum((a-mx)*(b-my) for a,b in z)/vv if vv else 0
   obs.append((sh,tr))
  pc=r['close']
feat={}
for d in md:
 us=prev(sd,d);ux=prev(dd,d);sh=sret.get(us)
 if not us or sh is None or not ux:continue
 si=sd.index(us);di=dd.index(ux)
 feat[d]={'us_date':us,'shock':sh,'sox5':sox[si][1]/sox[si-5][1]-1 if si>=5 else None,'dxy_date':ux,'dxy5':dxy[di][1]/dxy[di-5][1]-1 if di>=5 else None}

def cands(d):
 ft=feat[d];z=[]
 for r in by_d[d]:
  t=r['ticker'];b=beta.get((d,t));pc=prevc.get((d,t))
  if b is None or b<=0 or not pc:continue
  res=r['open']/pc-1-b*ft['shock']
  if res<=RESMAX:z.append({'ticker':t,'name':names.get(t,''),'open':r['open'],'beta':b,'resid':res,'score':b*(1+K*max(-res,0))})
 z.sort(key=lambda x:x['score'],reverse=True);return z

# Prior-only reference distributions: one Top1 per prior Taiwan trading date.
market_hist=[];top1_hist=[];sep_hist=[]
for d in md:
 if d>=TARGET or d not in feat:continue
 ft=feat[d]
 if ft['sox5'] is None or ft['dxy5'] is None:continue
 cs=cands(d)
 if len(cs)<2:continue
 market_raw=max(0,-ft['shock'])+max(0,-ft['sox5'])+max(0,ft['dxy5']+.005)
 market_hist.append(market_raw);top1_hist.append(cs[0]['score']);sep_hist.append(cs[0]['score']/cs[1]['score']-1)

ft=feat[TARGET];raw=cands(TARGET);vis=[]
for c in raw:
 if visible(c['ticker'],TARGET):vis.append(c)
 if len(vis)>=3:break
if len(vis)<3:vis=raw[:3]
market_raw=max(0,-ft['shock'])+max(0,-ft['sox5'])+max(0,ft['dxy5']+.005);mp=pct(market_raw,market_hist)

chips={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in CACHE.glob('*.json')}
prior_days=[d for d in md if d<TARGET][-6:]
def teacher(t):
 ds=prior_days[-3:]; ms=prior_days[-6:]
 F=sum((chips.get(d,{}).get('inst',{}).get(t,{}) or {}).get('foreign',0) for d in ds)
 T=sum((chips.get(d,{}).get('inst',{}).get(t,{}) or {}).get('trust',0) for d in ds)
 bals=[chips.get(d,{}).get('margin',{}).get(t) for d in ms];bals=[x for x in bals if x is not None];M=bals[-1]-bals[0] if len(bals)>=2 else None
 if M is None:label='N/A'
 elif F<0 and T>0 and M<0:label='外資賣／投信接／融資退'
 elif F>0 and T>0 and M<0:label='雙法人買／融資退'
 elif F>0 and T<=0 and M<0:label='外資買／投信未接／融資退'
 elif F<0 and T>0:label='外資賣／投信接／融資未退'
 else:label='老師不同步'
 return {'foreign3':F,'trust3':T,'margin5_change':M,'label':label}

outrows=[]
for i,c in enumerate(vis,1):
 sp=pct(c['score'],top1_hist)  # same calibration across candidates: strength vs historical Top1 distribution
 sep=(c['score']/vis[1]['score']-1) if i==1 and len(vis)>1 else 0.0
 lp=pct(sep,sep_hist) if i==1 else 0.0
 hs=round(25*mp+55*sp+20*lp,1)
 grade='S' if hs>=90 else 'A' if hs>=80 else 'B' if hs>=70 else 'C' if hs>=60 else 'WEAK'
 outrows.append({**c,'hscore':hs,'grade':grade,'teacher':teacher(c['ticker']),'market_percentile':mp,'selection_percentile':sp,'leader_percentile':lp})

gate=ft['shock']<=0 and ft['sox5']<=-.03 and ft['dxy5']>=-.005
out={'as_of':'2026-10-14 09:01 Asia/Taipei','future_data_used':False,'market':{**ft,'gate_GO':gate,'market_raw':market_raw,'market_percentile':mp},'top3':outrows,'note':'H-Score display only; no switch authority; 10/14 close and later data not used.'}
(OUT/'report.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2))
