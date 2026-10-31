#!/usr/bin/env python3
"""Probe whether official TWSE electronic-book t57sb01 supports a market-wide quarter query.

NO prices. NO returns. One bounded request only.
"""
from __future__ import annotations
import datetime as dt, hashlib, json, re
from pathlib import Path
import requests
from bs4 import BeautifulSoup

OUT=Path('research/selection_core_rebuild/generated/IF07_T57_BATCH_MODE_PROBE.json')
OUT.parent.mkdir(parents=True,exist_ok=True)
URL='https://doc.twse.com.tw/server-java/t57sb01'

def main():
 s=requests.Session(); s.headers.update({'User-Agent':'Mozilla/5.0 HENGCE-IF07-t57-batch-probe/0.1','Accept-Language':'zh-TW,zh;q=0.9'})
 p={'step':'1','colorchg':'1','co_id':'','year':'112','seamon':'1','mtype':'A','isnew':'true'}
 r=s.get(URL,params=p,timeout=90); r.encoding='big5'; text=r.text
 soup=BeautifulSoup(text,'lxml')
 rows=[]
 for tr in soup.find_all('tr'):
  cells=[' '.join(td.stripped_strings) for td in tr.find_all(['td','th'])]
  if cells: rows.append(cells)
 tickers=sorted(set(re.findall(r'(?<!\d)(\d{4})(?!\d)', '\n'.join(' | '.join(x) for x in rows))))
 files=sorted(set(re.findall(r'20\d{4}_\d{4}_AI1\.pdf',text)))
 upload_hits=re.findall(r'\d{2,3}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}',text)
 low=text.lower(); blocked=any(x in low for x in ['查詢過量','access denied','this page can not be accessed','this page cannot be accessed','for security reasons'])
 obj={'system':'HENGCE','artifact':'IF07_T57_BATCH_MODE_PROBE','generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'contains_price_or_forward_return_data':False,'request':p,'http_status':r.status_code,'bytes':len(r.content),'sha256':hashlib.sha256(r.content).hexdigest(),'security_or_rate_blocked':blocked,'table_row_count':len(rows),'parsed_4digit_ticker_count':len(tickers),'parsed_4digit_tickers_sample':tickers[:30],'ai1_file_count':len(files),'ai1_file_sample':files[:20],'upload_timestamp_count':len(upload_hits),'upload_timestamp_sample':upload_hits[:20],'contains_2330':('2330' in tickers or '202301_2330_AI1.pdf' in text),'contains_2454':('2454' in tickers or '202301_2454_AI1.pdf' in text),'body_text_prefix':' '.join(soup.stripped_strings)[:1000]}
 obj['verdict']='PASS_AS_MARKET_WIDE_T57_BATCH' if r.status_code==200 and not blocked and len(files)>10 and len(upload_hits)>10 else 'FAIL_OR_INCONCLUSIVE_AS_MARKET_WIDE_T57_BATCH'
 OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:obj[k] for k in ['verdict','http_status','bytes','security_or_rate_blocked','parsed_4digit_ticker_count','ai1_file_count','upload_timestamp_count','contains_2330','contains_2454']},ensure_ascii=False))
if __name__=='__main__': main()
