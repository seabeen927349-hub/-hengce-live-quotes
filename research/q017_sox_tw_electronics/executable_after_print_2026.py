#!/usr/bin/env python3
import json,os,time,urllib.parse,urllib.request
from datetime import datetime,timedelta
from pathlib import Path

ROOT=Path('research/q017_sox_tw_electronics');SRC=ROOT/'executable_entry_2026'/'summary.json';OUT=ROOT/'executable_after_print_2026';OUT.mkdir(parents=True,exist_ok=True)
START=2_000_000.;COST=.004
API_KEY=os.environ.get('FUGLE_API_KEY')
if not API_KEY: raise SystemExit('FUGLE_API_KEY missing')
src=json.loads(SRC.read_text(encoding='utf-8'));events=src['selected_events']

def ff(x):
    try:return float(x)
    except:return None

def fetch(symbol,d):
    base=f'https://api.fugle.tw/marketdata/v1.0/stock/historical/candles/{symbol}'
    q=urllib.parse.urlencode({'timeframe':'1','from':d,'to':d,'fields':'open,high,low,close,volume,average','sort':'asc'})
    req=urllib.request.Request(base+'?'+q,headers={'X-API-KEY':API_KEY,'Accept':'application/json','User-Agent':'HENGCE-Q017-AFTER-PRINT/1.0'})
    for a in range(5):
        try:
            with urllib.request.urlopen(req,timeout=30) as r:return json.load(r).get('data',[])
        except Exception:
            if a==4:raise
            time.sleep(2**a)

def dt(x):
    try:return datetime.fromisoformat(x['date'])
    except:return None

def first_regular(rows):
    z=[x for x in rows if dt(x) and dt(x).hour>=9 and (dt(x).hour<13 or (dt(x).hour==13 and dt(x).minute<=30))]
    return z[0] if z else None

def first_at_or_after(rows,target,field='open'):
    for x in rows:
        t=dt(x);p=ff(x.get(field))
        if t and t>=target and p and p>0:return p,x['date']
    return None,None

out_events=[]
for e in events:
    rows=fetch(e['ticker'],e['entry']);fst=first_regular(rows)
    if not fst: raise SystemExit(f'NO_MINUTE_DATA:{e["entry"]}:{e["ticker"]}')
    t0=dt(fst)
    z=dict(e);z['first_print_time']=fst['date'];z['first_print_open']=ff(fst.get('open'))
    for lag in (1,2,3,5,10):
        p,ts=first_at_or_after(rows,t0+timedelta(minutes=lag),'open');z[f'after_print_{lag}m']=p;z[f'after_print_{lag}m_ts']=ts
    p,ts=first_at_or_after(rows,t0+timedelta(minutes=1),'high');z['after_print_1m_high']=p;z['after_print_1m_high_ts']=ts
    out_events.append(z);time.sleep(.2)

variants=['after_print_1m','after_print_1m_high','after_print_2m','after_print_3m','after_print_5m','after_print_10m']
res={}
for v in variants:
    cap=START;wins=0;n=0;curve=[]
    for e in out_events:
        p=e.get(v)
        if not p:continue
        r=e['exit_close']/p-1-COST;cap*=1+r;n+=1;wins+=r>0
        curve.append({'entry':e['entry'],'exit':e['exit'],'ticker':e['ticker'],'first_print_time':e['first_print_time'],'entry_time':e.get(v+'_ts'),'entry_price':p,'ret_net':r,'capital':cap})
    res[v]={'final':cap,'ret':cap/START-1,'n':n,'wins':wins,'events':curve}
summary={'objective':'strict causality: select only after opening print and fill no earlier than a later minute','rule':src['frozen_rule'],'variants':res,'events':out_events}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
