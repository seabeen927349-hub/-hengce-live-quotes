#!/usr/bin/env python3
"""HENGCE G1 only: read official TWSE current roster + historical delisting ledger.

This is source and security identity QA, NOT a feature, model, or backtest.
Present company roster alone is never used to disqualify prior-year securities.
No API token, no vendor restricted dataset, no returns downloaded.
"""
from __future__ import annotations
import datetime,hashlib,json,os,re,sys,time,urllib.request,urllib.error
from html.parser import HTMLParser
from pathlib import Path
CURRENT='https://openapi.twse.com.tw/v1/opendata/t187ap03_L'
DELIST='https://www.twse.com.tw/company/suspendListingCsvAndHtml?lang=zh&type=html'
OUT=Path(os.getenv('HENGCE_G1_OUT','/tmp/hengce_g1_official_security_identity'))
TODAY=datetime.datetime.now(datetime.timezone.utc).isoformat()
FOUR=re.compile(r'^[1-9]\d{3}$')
DATE=re.compile(r'^(\d{2,3})年(\d{1,2})月(\d{1,2})日$')

def download(url):
    for i in range(3):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (research; HENGCE data lineage)','Accept':'application/json,text/html,*/*'})
            with urllib.request.urlopen(req,timeout=40) as r:return r.read()
        except Exception as e:
            if i==2:raise RuntimeError(type(e).__name__+':'+str(e)[:160]) from None
            time.sleep(3*(i+1))
def h(a):return hashlib.sha256(a).hexdigest()

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__();self.rows=[];self.cur=[];self.cell=None;self.table_depth=0
    def handle_starttag(self,tag,attrs):
        if tag=='tr':self.cur=[]
        if tag in ('td','th'):self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None:
            self.cur.append(''.join(self.cell).strip());self.cell=None
        if tag=='tr' and self.cur:self.rows.append(self.cur);self.cur=[]

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    receipt={'artifact':'HENGCE_G1_TWSE_OFFICIAL_MARKET_ID_PROBE','queried_at_utc':TODAY,
        'status':'BLOCKED_FAIL_CLOSED','official_sources':[CURRENT,DELIST],
        'not_historical_point_in_time_independent_proof':True,
        'not_a_prediction_or_return_experiment':True,'common_stock_legal_classification_incomplete':True}
    try:
        raw=download(CURRENT);data=json.loads(raw)
        if not isinstance(data,list) or len(data)<700:raise RuntimeError('CURRENT_ROSTER_TOO_SMALL')
        curr={}
        for row in data:
            if not isinstance(row,dict):continue
            t=str(row.get('公司代號','')).strip()
            if FOUR.fullmatch(t):curr[t]=dict(name=str(row.get('公司簡稱','')).strip(),
                  market='TWSE_CURRENT',listing_date=str(row.get('上市日期','')),
                  industry=str(row.get('產業別','')))
        if not (700<=len(curr)<=2000):raise RuntimeError('CURRENT_TWSE_CODE_COUNT_OUT_OF_RANGE')
        if curr.get('1101',{}).get('listing_date')!='19620209':raise RuntimeError('KNOWN_1101_LISTING_DATE_MISMATCH')
        raw_del=download(DELIST)
        p=TableParser();p.feed(raw_del.decode('utf-8','replace'))
        dl={}
        for row in p.rows:
            if len(row)<3:continue
            m=DATE.match(row[0]);t=row[2].strip()
            if not m or not FOUR.fullmatch(t):continue
            y,mon,day=map(int,m.groups());y+=1911
            if y<2018 or y>2026:continue
            d=f'{y:04d}-{mon:02d}-{day:02d}'
            if t in dl and dl[t]['date']!=d:raise RuntimeError('REUSED_CODE_MULTIPLE_DELIST_DATES_'+t)
            dl[t]={'date':d,'name':row[1].strip()}
        if len(dl)<25:raise RuntimeError('HISTORICAL_DELIST_TOO_FEW_'+str(len(dl)))
        # Delisted names are not all bankruptcy: M&A, transfers etc. Do not infer value.
        receipt.update(status='PASS_OFFICIAL_METADATA_NOT_FULL_PIT',current_roster_raw_sha256=h(raw),
          delisting_page_raw_sha256=h(raw_del),current_codes=len(curr),delisted_2018_2026=len(dl),
          historical_delisted_dates_verified=True,
          example_delists={k:dl.get(k) for k in ('2443','2358','2888','2448','2311','2325','1704','3519','6452','6806') if k in dl},
          public_roster_asof_current_not_historical=True,
          public_roster_companies_with_share_type_mixed=True,
          output_sha256_reference='separate manifest only')
        # Public official metadata is allowed to persist for reproducing eligibility.
        (OUT/'TWSE_CURRENT_LISTED_METADATA.json').write_text(json.dumps(curr,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (OUT/'TWSE_HISTORICAL_DELISTED_2018_2026.json').write_text(json.dumps(dl,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    except Exception as exc:
        receipt['status']='BLOCKED_FAIL_CLOSED'
        receipt['blocker']=str(exc).splitlines()[0][:300]
    finally:
        (OUT/'TWSE_OFFICIAL_IDENTITY_SOURCE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('HENGCE_G1_TWSE_IDENTITY',json.dumps(receipt,ensure_ascii=False),flush=True)
    return 0 if receipt['status'].startswith('PASS') else 2
if __name__=='__main__':raise SystemExit(main())
