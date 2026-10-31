#!/usr/bin/env python3
"""Probe MOPS iXBRL table headers for Q2/Q3/Q4 YTD selection.
NO prices. NO returns. Data semantics only.
"""
from __future__ import annotations
import datetime as dt, io, json, re
from pathlib import Path
import pandas as pd, requests

OUT=Path('research/selection_core_rebuild/generated/IF07_PERIOD_COLUMN_PROBE.json')
OUT.parent.mkdir(parents=True,exist_ok=True)
SAMPLES=[('2454',2024,2),('3037',2025,3),('2330',2023,4)]
CODES={'4000','5000','6900','AAAA','1170','130X','1XXX','2XXX'}

def norm_code(x):
 s=str(x).strip()
 if re.fullmatch(r'\d+\.0',s): s=s[:-2]
 return s

def flat(c):
 if isinstance(c,tuple): return ' | '.join(str(x).strip() for x in c if str(x).strip() and not str(x).startswith('Unnamed'))
 return str(c).strip()

def fetch(stock,y,q):
 u='https://mopsov.twse.com.tw/server-java/FileDownLoad'
 p={'functionName':'t164sb01','step':'9','co_id':stock,'year':str(y),'season':str(q),'report_id':'C'}
 r=requests.get(u,params=p,headers={'User-Agent':'Mozilla/5.0 HENGCE-IF07-period-probe/0.1','Referer':'https://mopsov.twse.com.tw/mops/web/t203sb01'},timeout=90)
 tabs=pd.read_html(io.BytesIO(r.content))
 out={'ticker':stock,'year':y,'quarter':q,'status':r.status_code,'bytes':len(r.content),'content_disposition':r.headers.get('content-disposition'),'tables':[]}
 for i,df in enumerate(tabs[:6]):
  x=df.copy(); x.columns=[flat(c) for c in x.columns]
  hitrows=[]
  for _,rr in x.iterrows():
   vals=[None if pd.isna(v) else v for v in rr.tolist()]
   if any(norm_code(v) in CODES for v in vals if v is not None):
    hitrows.append([None if v is None else str(v) for v in vals])
  if hitrows:
   out['tables'].append({'table_index':i,'columns':[str(c) for c in x.columns],'rows':hitrows})
 return out

def main():
 obj={'system':'HENGCE','artifact':'IF07_PERIOD_COLUMN_PROBE','generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'contains_price_or_forward_return_data':False,'samples':[fetch(*s) for s in SAMPLES]}
 OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'samples':[(x['ticker'],x['year'],x['quarter'],[(t['table_index'],len(t['rows'])) for t in x['tables']]) for x in obj['samples']]},ensure_ascii=False))
if __name__=='__main__': main()
