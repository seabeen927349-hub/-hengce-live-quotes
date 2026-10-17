#!/usr/bin/env python3
import csv,io,json,math,time
from datetime import datetime
from pathlib import Path
import requests
ROOT=Path('research/q017_sox_tw_electronics');OUT=ROOT/'archive_2026';OUT.mkdir(parents=True,exist_ok=True)
URL='https://indexes.nasdaq.com/Index/ExportHistory/NDX';UA={'User-Agent':'Mozilla/5.0 (HENGCE Q017 research)'}

def parse(raw):
 records=None
 if raw.startswith(b'PK'):
  import openpyxl
  ws=openpyxl.load_workbook(io.BytesIO(raw),read_only=True,data_only=True).active
  records=list(ws.iter_rows(values_only=True))
 else:records=list(csv.reader(io.StringIO(raw.decode('utf-8-sig',errors='replace'))))
 out=[]
 for rec in records:
  if len(rec)<2:continue
  ds=rec[0];dt=None
  if isinstance(ds,datetime):dt=ds.date()
  else:
   for fmt in ('%m/%d/%Y','%Y-%m-%d','%m/%d/%Y %H:%M:%S'):
    try:dt=datetime.strptime(str(ds).strip(),fmt).date();break
    except:pass
  if not dt or dt.year!=2026:continue
  try:c=float(str(rec[1]).replace(',','').strip())
  except:continue
  if math.isfinite(c) and c>0:out.append({'date':dt.isoformat(),'close':c})
 return sorted({r['date']:r for r in out}.values(),key=lambda r:r['date'])

def main():
 params={'startDate':'2026-01-01T00:00:00.000','endDate':'2026-10-17T00:00:00.000','timeOfDay':'EOD'};last=None
 for a in range(5):
  try:
   r=requests.get(URL,params=params,headers=UA,timeout=(8,30))
   if r.status_code==200 and r.content:
    rows=parse(r.content)
    if len(rows)<180:raise ValueError(f'NDX_ROWS_TOO_FEW:{len(rows)}')
    p=OUT/'ndx_2026.csv'
    with p.open('w',newline='',encoding='utf-8') as f:
     w=csv.DictWriter(f,fieldnames=['date','close']);w.writeheader();w.writerows(rows)
    (OUT/'ndx_acquisition_status.json').write_text(json.dumps({'status':'PASS','rows':len(rows),'latest':rows[-1]['date'],'source':r.url},indent=2),encoding='utf-8')
    print(json.dumps({'status':'PASS','rows':len(rows),'latest':rows[-1]['date']}));return 0
   last=f'HTTP {r.status_code}'
  except Exception as e:last=repr(e)
  time.sleep(2**a)
 print(json.dumps({'status':'ERROR','error':last}));return 2
if __name__=='__main__':raise SystemExit(main())
