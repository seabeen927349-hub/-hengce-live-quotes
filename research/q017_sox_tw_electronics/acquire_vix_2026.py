#!/usr/bin/env python3
import csv,io,json,time
from pathlib import Path
from datetime import datetime
import requests
ROOT=Path('research/q017_sox_tw_electronics');OUT=ROOT/'archive_2026';OUT.mkdir(parents=True,exist_ok=True)
URL='https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv';UA={'User-Agent':'Mozilla/5.0 (HENGCE Q017 research)'}
def main():
 last=None
 for a in range(5):
  try:
   r=requests.get(URL,headers=UA,timeout=(8,30))
   if r.status_code==200 and r.content:
    text=r.content.decode('utf-8-sig',errors='replace');rows=[]
    for x in csv.DictReader(io.StringIO(text)):
     ds=(x.get('DATE') or x.get('Date') or '').strip()
     dt=None
     for fmt in ('%m/%d/%Y','%Y-%m-%d'):
      try:dt=datetime.strptime(ds,fmt).date();break
      except:pass
     if not dt or dt.year!=2026 or dt>datetime(2026,10,17).date():continue
     try:c=float((x.get('CLOSE') or x.get('Close') or '').strip())
     except:continue
     rows.append({'date':dt.isoformat(),'close':c})
    rows.sort(key=lambda x:x['date'])
    if len(rows)<180:raise ValueError(f'VIX_ROWS_TOO_FEW:{len(rows)}')
    p=OUT/'vix_2026.csv'
    with p.open('w',newline='',encoding='utf-8') as f:
     w=csv.DictWriter(f,fieldnames=['date','close']);w.writeheader();w.writerows(rows)
    st={'status':'PASS','rows':len(rows),'latest':rows[-1]['date'],'source':URL};(OUT/'vix_acquisition_status.json').write_text(json.dumps(st,indent=2),encoding='utf-8');print(json.dumps(st));return 0
   last=f'HTTP {r.status_code}'
  except Exception as e:last=repr(e)
  time.sleep(2**a)
 print(json.dumps({'status':'ERROR','error':last}));return 2
if __name__=='__main__':raise SystemExit(main())
