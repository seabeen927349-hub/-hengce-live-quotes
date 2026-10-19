#!/usr/bin/env python3
import csv, io, json
from datetime import datetime, timezone
from pathlib import Path
import requests, openpyxl

START='2022-12-01'; END='2026-10-19'
OUT=Path(__file__).resolve().parent/'macro'; OUT.mkdir(parents=True,exist_ok=True)
UA={'User-Agent':'Mozilla/5.0 HENGCE-E2/1.0'}

def num(x):
    try:return float(str(x).replace(',','').strip())
    except:return None

def dt(x):
    if isinstance(x,datetime):return x.date().isoformat()
    for f in ('%m/%d/%Y','%Y-%m-%d','%m/%d/%Y %H:%M:%S'):
        try:return datetime.strptime(str(x).strip(),f).date().isoformat()
        except:pass

def save(path, series):
    ds=sorted(series)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['date','close','ret1','ret5'])
        for i,d in enumerate(ds):
            c=series[d]; r1=c/series[ds[i-1]]-1 if i else ''; r5=c/series[ds[i-5]]-1 if i>=5 else ''
            w.writerow([d,c,r1,r5])
    return ds

r=requests.get('https://indexes.nasdaq.com/Index/ExportHistory/SOX',params={'startDate':START+'T00:00:00.000','endDate':END+'T00:00:00.000','timeOfDay':'EOD'},headers=UA,timeout=60);r.raise_for_status()
raw=r.content
records=list(openpyxl.load_workbook(io.BytesIO(raw),read_only=True,data_only=True).active.iter_rows(values_only=True)) if raw.startswith(b'PK') else list(csv.reader(io.StringIO(raw.decode('utf-8-sig',errors='replace'))))
sox={}
for x in records:
    if len(x)>=2:
        d,c=dt(x[0]),num(x[1])
        if d and START<=d<=END and c and c>0:sox[d]=c
if len(sox)<900:raise SystemExit('SOX_ROWS_TOO_FEW')

p1=int(datetime(2022,11,15,tzinfo=timezone.utc).timestamp());p2=int(datetime(2026,10,21,tzinfo=timezone.utc).timestamp())
dxy={};src=None
for host in ('query1.finance.yahoo.com','query2.finance.yahoo.com'):
    try:
        u=f'https://{host}/v8/finance/chart/DX-Y.NYB'
        q=requests.get(u,params={'period1':p1,'period2':p2,'interval':'1d','events':'history','includeAdjustedClose':'true'},headers=UA,timeout=45);q.raise_for_status();z=q.json()['chart']['result'][0]
        for t,c in zip(z['timestamp'],z['indicators']['quote'][0]['close']):
            if c is not None:
                d=datetime.fromtimestamp(t,tz=timezone.utc).date().isoformat()
                if START<=d<=END:dxy[d]=float(c)
        if len(dxy)>=900:src=u;break
    except Exception: dxy={}
if not src:raise SystemExit('DXY_EXACT_DOWNLOAD_FAIL')

sd=save(OUT/'sox_daily.csv',sox);dd=save(OUT/'dxy_DX-Y.NYB_daily.csv',dxy)
rec={'status':'PASS','research_only':True,'sox_rows':len(sd),'sox_latest':sd[-1],'dxy_symbol':'DX-Y.NYB','dxy_rows':len(dd),'dxy_latest':dd[-1],'dxy_proxy_used':False,'causal_join_rule':'Taiwan signal date D may use only U.S. session_date < D','threshold_policy':'reuse Q017 thresholds; no threshold optimization','q017_mutated':False}
(OUT/'macro_receipt.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n');print(json.dumps(rec,ensure_ascii=False))
