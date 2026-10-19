#!/usr/bin/env python3
import csv, io, json, bisect
from datetime import datetime, timezone, date, timedelta
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

def enriched(series):
    ds=sorted(series); out={}
    for i,d in enumerate(ds):
        c=series[d]
        out[d]=(c,c/series[ds[i-1]]-1 if i else None,c/series[ds[i-5]]-1 if i>=5 else None)
    return ds,out

def save(path, series):
    ds,e=enriched(series)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['date','close','ret1','ret5'])
        for d in ds:w.writerow([d,*e[d]])
    return ds,e

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
    except Exception:dxy={}
if not src:raise SystemExit('DXY_EXACT_DOWNLOAD_FAIL')

sd,se=save(OUT/'sox_daily.csv',sox);dd,de=save(OUT/'dxy_DX-Y.NYB_daily.csv',dxy)
# Daily causal bit mask for Taiwan decision dates. 1=SOX1<=0, 2=SOX5<=-3%, 4=DXY5>=-0.5%.
# Each value uses the latest completed U.S. session strictly before Taiwan date D.
with (OUT/'macro_gate_mask_daily.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.writer(f);w.writerow(['date','mask'])
    d=date(2023,1,1); end=date.fromisoformat(END)
    while d<=end:
        ds=d.isoformat(); si=bisect.bisect_left(sd,ds)-1; di=bisect.bisect_left(dd,ds)-1; mask=0
        if si>=0 and di>=0:
            _,s1,s5=se[sd[si]]; _,_,d5=de[dd[di]]
            if s1 is not None and s1<=0:mask|=1
            if s5 is not None and s5<=-0.03:mask|=2
            if d5 is not None and d5>=-0.005:mask|=4
        w.writerow([ds,mask]);d+=timedelta(days=1)
rec={'status':'PASS','research_only':True,'sox_rows':len(sd),'sox_latest':sd[-1],'dxy_symbol':'DX-Y.NYB','dxy_rows':len(dd),'dxy_latest':dd[-1],'dxy_proxy_used':False,'causal_join_rule':'Taiwan signal date D may use only U.S. session_date < D','mask_bits':{'1':'SOX_1D<=0','2':'SOX_5D<=-0.03','4':'DXY_5D>=-0.005'},'threshold_policy':'reuse Q017 thresholds; no threshold optimization','q017_mutated':False}
(OUT/'macro_receipt.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n');print(json.dumps(rec,ensure_ascii=False))
