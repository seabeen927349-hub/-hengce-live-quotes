#!/usr/bin/env python3
"""HENGCE IF-07 direct iXBRL table + electronic-book scope probe.
NO price data. NO forward returns.
"""
from __future__ import annotations
import datetime as dt, io, json, re
from pathlib import Path
import pandas as pd
import requests
from bs4 import BeautifulSoup

OUT=Path('research/selection_core_rebuild/generated/IF07_IXBRL_TABLE_PROBE.json')
OUT.parent.mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 HENGCE-IF07-ixbrl-table-probe/0.1'
TARGETS=['營業收入','營業成本','營業毛利','營業利益','應收帳款','存貨','資產總計','負債總計','營業活動之淨現金流入','取得不動產、廠房及設備']

def now(): return dt.datetime.now(dt.timezone.utc).isoformat()

def flat(c):
    if isinstance(c,tuple): return ' | '.join(str(x).strip() for x in c if str(x).strip() and not str(x).startswith('Unnamed'))
    return str(c).strip()

def find_rows(content:bytes):
    tabs=pd.read_html(io.BytesIO(content))
    hits={t:[] for t in TARGETS}
    summaries=[]
    for i,df in enumerate(tabs):
        df=df.copy(); df.columns=[flat(c) for c in df.columns]
        summaries.append({'i':i,'rows':len(df),'cols':[str(c) for c in df.columns[:12]]})
        for _,r in df.iterrows():
            vals=[str(v) for v in r.tolist() if not pd.isna(v)]
            joined=' | '.join(vals)
            for t in TARGETS:
                if t in joined and len(hits[t])<8:
                    hits[t].append({'table':i,'row':vals[:20]})
    return summaries,hits

def ebook_query(s,year):
    p={'step':'1','colorchg':'1','co_id':'2330','year':year,'seamon':'','mtype':'A'}
    r=s.get('https://doc.twse.com.tw/server-java/t57sb01',params=p,timeout=45); r.encoding='big5'
    soup=BeautifulSoup(r.text,'lxml'); rows=[]
    for tr in soup.find_all('tr'):
        cells=[' '.join(td.stripped_strings) for td in tr.find_all(['td','th'])]
        if cells and '2330' in cells and any('AI1.pdf' in x or 'A11.pdf' in x for x in cells): rows.append(cells)
    return {'year_param':year,'status':r.status_code,'row_count':len(rows),'rows':rows[:30]}

def main():
    s=requests.Session(); s.headers.update({'User-Agent':UA,'Accept-Language':'zh-TW,zh;q=0.9'})
    u='https://mopsov.twse.com.tw/server-java/FileDownLoad'
    p={'functionName':'t164sb01','step':'9','co_id':'2330','year':'2023','season':'1','report_id':'C'}
    r=s.get(u,params=p,headers={'Referer':'https://mopsov.twse.com.tw/mops/web/t203sb01'},timeout=60)
    summaries,hits=find_rows(r.content)
    obj={'system':'HENGCE','artifact':'IF07_IXBRL_TABLE_PROBE','generated_at_utc':now(),'contains_price_or_forward_return_data':False,
         'ixbrl':{'status':r.status_code,'bytes':len(r.content),'content_disposition':r.headers.get('content-disposition'),'table_count':len(summaries),'table_summaries':summaries,'target_hits':hits},
         'ebook_year_112':ebook_query(s,'112'),'ebook_year_blank':ebook_query(s,'')}
    OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'tables':len(summaries),'target_counts':{k:len(v) for k,v in hits.items()},'ebook_blank_rows':obj['ebook_year_blank']['row_count']},ensure_ascii=False))
if __name__=='__main__': main()
