#!/usr/bin/env python3
"""HENGCE IF-07 original-filing / correction gate probe.

NO prices, NO returns. Tests two official-source properties before panel build:
1) MOPS XBRL direct download returns structured filing bytes for an uncorrected sample.
2) TWSE electronic-book metadata exposes 財務報告更(補)正 so corrected company-quarters
   can be fail-closed before using current XBRL values.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import requests
from bs4 import BeautifulSoup

OUT=Path('research/selection_core_rebuild/generated/IF07_ORIGINAL_FILING_GATE_PROBE.json')
OUT.parent.mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 HENGCE-IF07-original-gate-probe/0.1'


def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def h(b:bytes): return hashlib.sha256(b).hexdigest()


def ebook_rows(s:requests.Session, stock:str, roc_year:int):
    u='https://doc.twse.com.tw/server-java/t57sb01'
    p={'step':'1','colorchg':'1','co_id':stock,'year':str(roc_year),'seamon':'','mtype':'A'}
    r=s.get(u,params=p,timeout=45); r.encoding='big5'
    soup=BeautifulSoup(r.text,'lxml')
    out=[]
    for tr in soup.find_all('tr'):
        cells=[' '.join(td.stripped_strings) for td in tr.find_all(['td','th'])]
        if cells and stock in ' '.join(cells) and any('AI1.pdf' in x or 'A11.pdf' in x for x in cells):
            out.append(cells)
    return {'status_code':r.status_code,'url':r.url,'rows':out,'bytes':len(r.content),'sha256':h(r.content)}


def xbrl_download(s:requests.Session, stock:str, western_year:int, quarter:int):
    u='https://mopsov.twse.com.tw/server-java/FileDownLoad'
    p={'functionName':'t164sb01','step':'9','co_id':stock,'year':str(western_year),'season':str(quarter),'report_id':'C'}
    r=s.get(u,params=p,headers={'Referer':'https://mopsov.twse.com.tw/mops/web/t203sb01'},timeout=60,allow_redirects=True)
    b=r.content
    kind='ZIP' if b[:2]==b'PK' else ('IXBRL_HTML' if b'ix:nonFraction' in b or b'ix:nonNumeric' in b else 'OTHER')
    files=[]
    text_markers={}
    if kind=='ZIP':
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            files=z.namelist()
            joined=b'\n'.join(z.read(n) for n in files if n.lower().endswith(('.html','.htm','.xhtml','.xml','.xbrl')))
            text_markers={
                '508632973': b'508632973' in joined,
                '222132581': b'222132581' in joined,
                '147715125': b'147715125' in joined,
                '216067981': b'216067981' in joined,
                '385244745': b'385244745' in joined,
            }
    elif kind=='IXBRL_HTML':
        text_markers={
            '508632973': b'508632973' in b,
            '222132581': b'222132581' in b,
            '147715125': b'147715125' in b,
            '216067981': b'216067981' in b,
            '385244745': b'385244745' in b,
        }
    return {'status_code':r.status_code,'final_url':r.url,'content_type':r.headers.get('content-type'),'content_disposition':r.headers.get('content-disposition'),'bytes':len(b),'sha256':h(b),'kind':kind,'files':files[:50],'known_2330_2023q1_value_markers':text_markers}


def main():
    s=requests.Session(); s.headers.update({'User-Agent':UA,'Accept-Language':'zh-TW,zh;q=0.9'})
    ts=ebook_rows(s,'2330',112)
    ml=ebook_rows(s,'2464',113)
    xd=xbrl_download(s,'2330',2023,1)
    obj={
      'system':'HENGCE','artifact':'IF07_ORIGINAL_FILING_GATE_PROBE','generated_at_utc':now(),
      'contains_price_or_forward_return_data':False,
      'uncorrected_control_2330_2023_ebook':ts,
      'known_correction_case_2464_2024_ebook':ml,
      'xbrl_direct_download_2330_2023q1':xd,
      'decision_rule_under_test':'Only company-quarters whose electronic-book 財務報告更(補)正 field is 無 are eligible for current XBRL extraction; corrected/ambiguous rows fail closed before returns.',
    }
    OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'2330_rows':len(ts['rows']),'2464_rows':len(ml['rows']),'xbrl_kind':xd['kind'],'xbrl_bytes':xd['bytes']},ensure_ascii=False))
if __name__=='__main__': main()
