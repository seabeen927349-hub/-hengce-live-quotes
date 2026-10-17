#!/usr/bin/env python3
import json,time
from pathlib import Path
import pandas as pd
ROOT=Path('research/q017_sox_tw_electronics');OUT=ROOT/'archive_2026';OUT.mkdir(parents=True,exist_ok=True)
URL='https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?field_tdr_date_value=2026&type=daily_treasury_yield_curve'

def main():
 last=None
 for a in range(4):
  try:
   tabs=pd.read_html(URL)
   hit=None
   for df in tabs:
    cols=[str(c).strip() for c in df.columns]
    if 'Date' in cols and ('10-year' in cols or '10 Yr' in cols or '10 YR' in cols):
     hit=df;break
   if hit is None:
    for df in tabs:
     cols=[str(c).strip() for c in df.columns]
     if 'Date' in cols and any('10' in c and ('Yr' in c or 'YR' in c or 'year' in c) for c in cols):hit=df;break
   if hit is None:raise ValueError('NO_TREASURY_TABLE')
   cols={str(c).strip():c for c in hit.columns};datecol=cols['Date'];ten=next(c for c in hit.columns if '10' in str(c) and ('Yr' in str(c) or 'YR' in str(c) or 'year' in str(c)))
   z=pd.DataFrame({'date':pd.to_datetime(hit[datecol],errors='coerce'),'yield10':pd.to_numeric(hit[ten],errors='coerce')}).dropna()
   z=z[(z.date.dt.year==2026)&(z.date<=pd.Timestamp('2026-10-17'))].sort_values('date');z['date']=z.date.dt.strftime('%Y-%m-%d')
   if len(z)<180:raise ValueError(f'UST10_ROWS_TOO_FEW:{len(z)}')
   p=OUT/'ust10y_2026.csv';z[['date','yield10']].to_csv(p,index=False)
   st={'status':'PASS','rows':int(len(z)),'latest':z.iloc[-1]['date'],'source':URL};(OUT/'ust10y_acquisition_status.json').write_text(json.dumps(st,indent=2),encoding='utf-8');print(json.dumps(st));return 0
  except Exception as e:last=repr(e);time.sleep(2**a)
 print(json.dumps({'status':'ERROR','error':last}));return 2
if __name__=='__main__':raise SystemExit(main())
