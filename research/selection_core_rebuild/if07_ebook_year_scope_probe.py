#!/usr/bin/env python3
"""Diagnose TWSE electronic-book metadata query scope on Actions runner.
NO prices. NO returns.
"""
from __future__ import annotations
import datetime as dt, json, time
from pathlib import Path
import requests
from bs4 import BeautifulSoup

OUT=Path('research/selection_core_rebuild/generated/IF07_EBOOK_YEAR_SCOPE_PROBE.json')
OUT.parent.mkdir(parents=True,exist_ok=True)
URL='https://doc.twse.com.tw/server-java/t57sb01'
TICKERS=['2330','2454','3037','2317','3008','2303']
YEARS=['','111','112','113','114','115']

def parse(stock,year):
 p={'step':'1','colorchg':'1','co_id':stock,'year':year,'seamon':'','mtype':'A'}
 last=None
 for a in range(4):
  try:
   r=requests.get(URL,params=p,headers={'User-Agent':'Mozilla/5.0 HENGCE-IF07-year-scope-probe/0.1','Accept-Language':'zh-TW,zh;q=0.9'},timeout=45)
   r.encoding='big5'; soup=BeautifulSoup(r.text,'lxml'); rows=[]
   for tr in soup.find_all('tr'):
    cells=[' '.join(td.stripped_strings) for td in tr.find_all(['td','th'])]
    if cells and stock in cells and len(cells)>=11 and cells[5]=='IFRSs合併財報': rows.append(cells)
   return {'ticker':stock,'year_param':year,'status':r.status_code,'bytes':len(r.content),'rows':rows,'row_count':len(rows),'body_prefix':' '.join(soup.stripped_strings)[:300]}
  except Exception as e:
   last=f'{type(e).__name__}: {e}'; time.sleep(1+a)
 return {'ticker':stock,'year_param':year,'error':last,'row_count':0,'rows':[]}

def main():
 out=[]
 for t in TICKERS:
  for y in YEARS: out.append(parse(t,y))
 obj={'system':'HENGCE','artifact':'IF07_EBOOK_YEAR_SCOPE_PROBE','generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'contains_price_or_forward_return_data':False,'results':out}
 OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({t:{y:next(x['row_count'] for x in out if x['ticker']==t and x['year_param']==y) for y in YEARS} for t in TICKERS},ensure_ascii=False))
if __name__=='__main__': main()
