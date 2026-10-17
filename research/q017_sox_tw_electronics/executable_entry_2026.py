#!/usr/bin/env python3
import csv,json,os,time,urllib.parse,urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT=Path('research/q017_sox_tw_electronics');ARC=ROOT/'archive_2026';OUT=ROOT/'executable_entry_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;COST=.004
SHOCK_MAX=0.0;SOX5_MAX=-.02;RESMAX=.04;HOLD=10;K=25
API_KEY=os.environ.get('FUGLE_API_KEY')
if not API_KEY: raise SystemExit('FUGLE_API_KEY missing')

def f(x):
    try:return float(str(x).replace(',','').strip())
    except:return None

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
idx={t:{r['date']:i for i,r in enumerate(rs)} for t,rs in by_t.items()};aligned={d:sret.get(prevus(d)) for d in by_d}

beta={};prevc={}
for t,rs in by_t.items():
    obs=[];pc=None
    for r in rs:
        prevc[(r['date'],t)]=pc
        if pc and aligned.get(r['date']) is not None:
            tr=r['close']/pc-1
            if len(obs)>=30:
                z=obs[-60:];mx=sum(a for a,b in z)/len(z);my=sum(b for a,b in z)/len(z);vv=sum((a-mx)**2 for a,b in z)
                beta[(r['date'],t)]=sum((a-mx)*(b-my) for a,b in z)/vv if vv else 0
            obs.append((aligned[r['date']],tr))
        pc=r['close']
feat={}
for d in sorted(by_d):
    u=prevus(d);sh=aligned.get(d)
    if not u or sh is None:continue
    ui=sd.index(u);r5=sox[ui][1]/sox[ui-5][1]-1 if ui>=5 else None
    feat[d]={'shock':sh,'sox5':r5}

# Freeze selection using only information available immediately after the official opening print.
selected=[];busy=''
for d in sorted(by_d):
    if busy and d<=busy:continue
    ft=feat.get(d)
    if not ft or ft['shock']>SHOCK_MAX or ft['sox5'] is None or ft['sox5']>SOX5_MAX:continue
    cs=[]
    for r in by_d[d]:
        b=beta.get((d,r['ticker']));pc=prevc.get((d,r['ticker']))
        if b is None or not pc:continue
        res=r['open']/pc-1-b*ft['shock']
        if res<=RESMAX:
            score=b*(1+K*max(-res,0));cs.append((score,b,res,r))
    if not cs:continue
    sc,b,res,r=max(cs,key=lambda x:x[0]);i=idx[r['ticker']][d];j=i+HOLD-1
    if j>=len(by_t[r['ticker']]):continue
    ex=by_t[r['ticker']][j];busy=ex['date']
    selected.append({'entry':d,'exit':busy,'ticker':r['ticker'],'official_open':r['open'],'exit_close':ex['close'],'score':sc,'beta':b,'resid':res,'shock':ft['shock'],'sox5':ft['sox5']})

def fetch_minutes(symbol,d):
    base=f'https://api.fugle.tw/marketdata/v1.0/stock/historical/candles/{symbol}'
    q=urllib.parse.urlencode({'timeframe':'1','from':d,'to':d,'fields':'open,high,low,close,volume,average','sort':'asc'})
    req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API_KEY,'Accept':'application/json','User-Agent':'HENGCE-Q017-EXECUTABLE/1.0'})
    for a in range(5):
        try:
            with urllib.request.urlopen(req,timeout=30) as rr:return json.load(rr).get('data',[])
        except Exception:
            if a==4:raise
            time.sleep(2**a)

def parse_minute(x):
    try:return datetime.fromisoformat(x['date'])
    except:return None

def px_at_or_after(rows,hhmm,field='open'):
    h,m=map(int,hhmm.split(':'))
    for x in rows:
        dt=parse_minute(x)
        if dt and (dt.hour,dt.minute)>=(h,m):
            p=f(x.get(field))
            if p and p>0:return p,x['date']
    return None,None

for e in selected:
    rows=fetch_minutes(e['ticker'],e['entry'])
    for hhmm in ('09:01','09:03','09:05','09:10'):
        p,ts=px_at_or_after(rows,hhmm,'open');e['entry_'+hhmm.replace(':','')]=p;e['ts_'+hhmm.replace(':','')]=ts
    # Conservative same-minute stress: pay the high of the first minute available at/after 09:01.
    p,ts=px_at_or_after(rows,'09:01','high');e['entry_0901_high']=p;e['ts_0901_high']=ts
    time.sleep(.25)

variants=['official_open','entry_0901','entry_0901_high','entry_0903','entry_0905','entry_0910']
summary={}
for v in variants:
    cap=START;wins=0;n=0;curve=[]
    for e in selected:
        p=e.get(v)
        if not p:continue
        ret=e['exit_close']/p-1-COST;cap*=1+ret;n+=1;wins+=ret>0
        curve.append({'entry':e['entry'],'exit':e['exit'],'ticker':e['ticker'],'entry_price':p,'ret_net':ret,'capital':cap})
    summary[v]={'final':cap,'ret':cap/START-1,'n':n,'wins':wins,'events':curve}

out={'objective':'replace impossible same-open fill with post-open executable minute prices','frozen_rule':{'shock_max':SHOCK_MAX,'sox5_max':SOX5_MAX,'resid_max':RESMAX,'hold':HOLD,'overshoot_k':K,'cost':COST},'selected_events':selected,'variants':summary}
(OUT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'events.csv').open('w',newline='',encoding='utf-8') as f0:
    w=csv.DictWriter(f0,fieldnames=list(selected[0].keys()));w.writeheader();w.writerows(selected)
print(json.dumps(out,ensure_ascii=False,indent=2))
