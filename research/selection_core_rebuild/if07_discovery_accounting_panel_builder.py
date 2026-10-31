#!/usr/bin/env python3
"""Build IF-07 V0.1 Discovery accounting panel WITHOUT market outcomes.

Governance:
- consumes preregistered metadata pairs only;
- 2023-2024 current filings only; 2022-2023 separate original comparators;
- exact correction gate already applied by metadata index;
- downloads official MOPS quarterly bulk iXBRL ZIPs;
- extracts frozen accounting codes and YTD/quarter-end columns;
- computes six preregistered accounting conditions;
- contains NO prices, forward returns, MAE/MFE, null outcomes, winner labels.

PIT electronics membership is intentionally NOT asserted here; it is joined later
against the canonical daily electronics archive before the count-only audit is
eligible to open Discovery returns.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import math
import os
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
import requests

ROOT=Path('research/selection_core_rebuild')
META=ROOT/'generated/IF07_METADATA_INDEX_2022_2026.json'
OUT_PANEL=ROOT/'generated/IF07_DISCOVERY_ACCOUNTING_PANEL_NO_RETURNS.json'
OUT_AUDIT=ROOT/'generated/IF07_DISCOVERY_ACCOUNTING_PANEL_AUDIT_NO_RETURNS.json'
OUT_PANEL.parent.mkdir(parents=True,exist_ok=True)

BULK_URL='https://mopsov.twse.com.tw/server-java/FileDownLoad'
UA='Mozilla/5.0 HENGCE-IF07-discovery-accounting-panel/0.1'
CODES={
 'Revenue_YTD':'4000','COGS_YTD':'5000','OperatingIncome_YTD':'6900','CFO_YTD':'AAAA',
 'AR':'1170','Inventory':'130X','Assets':'1XXX','Liabilities':'2XXX',
}
FLOW_FIELDS={'Revenue_YTD','COGS_YTD','OperatingIncome_YTD'}
BAL_FIELDS={'AR','Inventory','Assets','Liabilities'}
CASH_FIELDS={'CFO_YTD'}
QEND={1:(3,31),2:(6,30),3:(9,30),4:(12,31)}


def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def h(b:bytes): return hashlib.sha256(b).hexdigest()

def norm_code(x:Any)->str:
 s=str(x).strip()
 if re.fullmatch(r'\d+\.0',s): s=s[:-2]
 return s

def flat(c:Any)->str:
 if isinstance(c,tuple):
  return ' | '.join(str(x).strip() for x in c if str(x).strip() and not str(x).startswith('Unnamed'))
 return str(c).strip()

def compact(s:str)->str:
 return re.sub(r'\s+','',str(s)).replace('～','To').replace('至','To')

def numeric(v:Any)->float|None:
 if v is None or (isinstance(v,float) and math.isnan(v)): return None
 if isinstance(v,(int,float)) and math.isfinite(float(v)): return float(v)
 s=str(v).strip().replace(',','').replace(' ','')
 if not s or s in {'--','-','N/A','NA','nan','None'}: return None
 neg=False
 if s.startswith('(') and s.endswith(')'):
  neg=True; s=s[1:-1]
 try: x=float(s)
 except Exception: return None
 if not math.isfinite(x): return None
 return -x if neg else x

def statement_kind(cols:list[str])->str|None:
 joined=' '.join(cols)
 if '資產負債表' in joined or 'Balance Sheet' in joined: return 'balance'
 if '綜合損益表' in joined or 'Comprehensive Income' in joined: return 'income'
 if '現金流量表' in joined or 'Cash Flows' in joined: return 'cashflow'
 return None

def target_column(cols:list[str],kind:str,year:int,q:int)->str|None:
 m,d=QEND[q]
 if kind=='balance':
  needle=f'{year}/{m}/{d}'
  hits=[c for c in cols[2:] if needle in compact(c) and 'To' not in compact(c)]
 elif kind in {'income','cashflow'}:
  needle=f'{year}/1/1To{m}/{d}'
  hits=[c for c in cols[2:] if needle in compact(c)]
 else: hits=[]
 return hits[0] if len(hits)==1 else None

def parse_filing(content:bytes,year:int,q:int)->tuple[dict[str,float]|None,dict[str,Any]]:
 audit={'year':year,'quarter':q,'bytes':len(content),'sha256':h(content),'status':'FAIL','reason':None,'field_evidence':{}}
 try: tabs=pd.read_html(io.BytesIO(content))
 except Exception as e:
  audit['reason']=f'READ_HTML:{type(e).__name__}:{e}'; return None,audit
 tables={}
 for i,df in enumerate(tabs):
  x=df.copy(); x.columns=[flat(c) for c in x.columns]
  k=statement_kind(list(x.columns))
  if k and k not in tables: tables[k]=(i,x)
 needed={'balance','income','cashflow'}
 if not needed.issubset(tables):
  audit['reason']='MISSING_REQUIRED_STATEMENT'; audit['statement_kinds']=sorted(tables); return None,audit
 vals={}
 for field,code in CODES.items():
  kind='income' if field in FLOW_FIELDS else ('balance' if field in BAL_FIELDS else 'cashflow')
  ti,df=tables[kind]
  col=target_column(list(df.columns),kind,year,q)
  if col is None:
   audit['reason']=f'AMBIGUOUS_PERIOD_COLUMN:{kind}:{field}'; return None,audit
  code_col=df.columns[0]
  mask=df[code_col].map(norm_code)==code
  if int(mask.sum())!=1:
   audit['reason']=f'CODE_COUNT:{field}:{code}:{int(mask.sum())}'; return None,audit
  rr=df.loc[mask].iloc[0]
  v=numeric(rr[col])
  if v is None:
   audit['reason']=f'NONNUMERIC:{field}:{code}'; return None,audit
  vals[field]=v
  audit['field_evidence'][field]={'code':code,'table_index':ti,'period_column':col,'value':v,'label':str(rr.iloc[1]) if len(rr)>1 else None}
 audit['status']='PASS'; return vals,audit

def download_bulk(s:requests.Session,year:int,q:int)->tuple[bytes,dict[str,Any]]:
 fn=f'tifrs-{year}Q{q}.zip'
 p={'step':'9','functionName':'show_file2','fileName':fn,'filePath':f'/ifrs/{year}/'}
 r=s.get(BULK_URL,params=p,headers={'Referer':'https://mopsov.twse.com.tw/mops/web/t203sb02'},timeout=240)
 b=r.content
 receipt={'year':year,'quarter':q,'file_name':fn,'http_status':r.status_code,'bytes':len(b),'sha256':h(b),'content_type':r.headers.get('content-type'),'content_disposition':r.headers.get('content-disposition'),'zip_magic':b[:2]==b'PK'}
 if r.status_code!=200 or b[:2]!=b'PK': raise RuntimeError(f'bulk download failed {year}Q{q}: {receipt}')
 return b,receipt

def member_for(z:zipfile.ZipFile,ticker:str,year:int,q:int)->str|None:
 pat=re.compile(rf'^tifrs-fr1-m1-ci-cr-{re.escape(ticker)}-{year}Q{q}\.html$',re.I)
 hits=[n for n in z.namelist() if pat.match(Path(n).name)]
 return hits[0] if len(hits)==1 else None

def derive(cur:dict[str,float],prev:dict[str,float])->tuple[dict[str,float]|None,str|None]:
 den=['Revenue_YTD','COGS_YTD','AR','Inventory','Assets']
 # Current Revenue/Assets must also be positive for ratios.
 if cur['Revenue_YTD']<=0 or cur['Assets']<=0: return None,'NONPOSITIVE_CURRENT_DENOMINATOR'
 if any(prev[x]<=0 for x in den): return None,'NONPOSITIVE_PRIOR_DENOMINATOR'
 cash=cur['CFO_YTD']/cur['Revenue_YTD']; cashp=prev['CFO_YTD']/prev['Revenue_YTD']
 rev=cur['Revenue_YTD']/prev['Revenue_YTD']-1; ar=cur['AR']/prev['AR']-1
 cogs=cur['COGS_YTD']/prev['COGS_YTD']-1; inv=cur['Inventory']/prev['Inventory']-1
 gm=(cur['Revenue_YTD']-cur['COGS_YTD'])/cur['Revenue_YTD']; gmp=(prev['Revenue_YTD']-prev['COGS_YTD'])/prev['Revenue_YTD']
 om=cur['OperatingIncome_YTD']/cur['Revenue_YTD']; omp=prev['OperatingIncome_YTD']/prev['Revenue_YTD']
 lev=cur['Liabilities']/cur['Assets']; levp=prev['Liabilities']/prev['Assets']
 d={'cash_conversion':cash,'cash_conversion_prev':cashp,'D_CASH':cash-cashp,'REV_YOY':rev,'AR_YOY':ar,'AR_GAP':rev-ar,'COGS_YOY':cogs,'INV_YOY':inv,'INV_GAP':cogs-inv,'GM':gm,'GM_prev':gmp,'D_GM':gm-gmp,'OM':om,'OM_prev':omp,'D_OM':om-omp,'LEV':lev,'LEV_prev':levp,'D_LEV':lev-levp}
 return d,None

def main():
 meta=json.loads(META.read_text(encoding='utf-8'))
 pairs=[r for r in meta['current_prior_pairs'] if r['fiscal_year'] in (2023,2024) and r.get('signal_date')]
 # Strictly no validation-period current filings in this build.
 needed_keys=set()
 for r in pairs:
  needed_keys.add((r['ticker'],r['fiscal_year'],r['quarter']))
  needed_keys.add((r['ticker'],r['fiscal_year']-1,r['quarter']))
 by_q=defaultdict(set)
 for t,y,q in needed_keys: by_q[(y,q)].add(t)

 s=requests.Session(); s.headers.update({'User-Agent':UA,'Accept-Language':'zh-TW,zh;q=0.9'})
 parsed={}; parse_audits={}; bulk_receipts=[]; exclusions=Counter()
 for y in (2022,2023,2024):
  for q in (1,2,3,4):
   targets=by_q.get((y,q),set())
   if not targets: continue
   b,rec=download_bulk(s,y,q); bulk_receipts.append(rec)
   with zipfile.ZipFile(io.BytesIO(b)) as z:
    rec['member_count']=len(z.namelist())
    for t in sorted(targets):
     m=member_for(z,t,y,q)
     key=(t,y,q)
     if not m:
      exclusions['BULK_MEMBER_MISSING_OR_AMBIGUOUS']+=1; parse_audits[key]={'status':'FAIL','reason':'BULK_MEMBER_MISSING_OR_AMBIGUOUS'}; continue
     content=z.read(m)
     v,a=parse_filing(content,y,q); a['member']=m
     parse_audits[key]=a
     if v is None: exclusions[a.get('reason') or 'PARSE_FAIL']+=1
     else: parsed[key]=v
   # release ZIP before next quarter

 panel=[]
 for r in pairs:
  t,y,q=r['ticker'],r['fiscal_year'],r['quarter']; ck=(t,y,q); pk=(t,y-1,q)
  base={'ticker':t,'fiscal_year':y,'quarter':q,'current_file_pdf':r['current_file'],'prior_file_pdf':r['prior_file'],'current_upload_ts_taipei':r['current_upload_ts_taipei'],'prior_upload_ts_taipei':r['prior_upload_ts_taipei'],'signal_date':r['signal_date'],'pit_electronics_membership_checked':False,'contains_market_outcome':False}
  if ck not in parsed:
   base.update({'eligible_accounting_pair':False,'exclusion_reason':'CURRENT_PARSE_FAIL','selected_v0_1':False}); panel.append(base); continue
  if pk not in parsed:
   base.update({'eligible_accounting_pair':False,'exclusion_reason':'PRIOR_PARSE_FAIL','selected_v0_1':False}); panel.append(base); continue
  d,err=derive(parsed[ck],parsed[pk])
  if err:
   base.update({'eligible_accounting_pair':False,'exclusion_reason':err,'selected_v0_1':False,'current':parsed[ck],'prior':parsed[pk]}); panel.append(base); exclusions[err]+=1; continue
  cond={'D_CASH_ge_0':d['D_CASH']>=0,'AR_GAP_ge_0':d['AR_GAP']>=0,'INV_GAP_ge_0':d['INV_GAP']>=0,'D_GM_ge_0':d['D_GM']>=0,'D_OM_ge_0':d['D_OM']>=0,'D_LEV_le_0':d['D_LEV']<=0}
  selected=all(cond.values())
  base.update({'eligible_accounting_pair':True,'exclusion_reason':None,'current':parsed[ck],'prior':parsed[pk],'derived':d,'conditions':cond,'selected_v0_1':selected,'current_ixbrl_sha256':parse_audits[ck]['sha256'],'prior_ixbrl_sha256':parse_audits[pk]['sha256']})
  panel.append(base)

 yq=Counter(f"{r['fiscal_year']}Q{r['quarter']}" for r in panel)
 eligible=Counter(f"{r['fiscal_year']}Q{r['quarter']}" for r in panel if r['eligible_accounting_pair'])
 selected=Counter(f"{r['fiscal_year']}Q{r['quarter']}" for r in panel if r['selected_v0_1'])
 months=Counter(r['signal_date'][:7] for r in panel if r['selected_v0_1'] and r.get('signal_date'))
 selected_rows=[r for r in panel if r['selected_v0_1']]
 audit={
  'system':'HENGCE','artifact':'IF07_DISCOVERY_ACCOUNTING_PANEL_AUDIT_NO_RETURNS','generated_at_utc':now(),'challenger':'IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1','contains_price_or_forward_return_data':False,
  'source_metadata_artifact':meta.get('artifact'),'source_metadata_generated_at_utc':meta.get('generated_at_utc'),'source_script_commit':os.getenv('GITHUB_SHA'),
  'discovery_current_years':[2023,2024],'bulk_receipts':bulk_receipts,
  'metadata_pair_input_count':len(pairs),'panel_row_count':len(panel),'rows_by_year_quarter':dict(sorted(yq.items())),
  'eligible_accounting_pair_count':sum(r['eligible_accounting_pair'] for r in panel),'eligible_by_year_quarter':dict(sorted(eligible.items())),
  'selected_v0_1_count_pre_PIT_membership':len(selected_rows),'selected_by_year_quarter_pre_PIT_membership':dict(sorted(selected.items())),'selected_by_signal_month_pre_PIT_membership':dict(sorted(months.items())),
  'selected_unique_ticker_count_pre_PIT_membership':len({r['ticker'] for r in selected_rows}),'selected_signal_date_count_pre_PIT_membership':len({r['signal_date'] for r in selected_rows if r.get('signal_date')}),
  'exclusion_reason_counts':dict(exclusions),
  'required_code_parse_pass_count':len(parsed),'required_company_quarter_key_count':len(needed_keys),
  'pit_electronics_membership_status':'NOT_YET_JOINED_CANONICAL_DAILY_ARCHIVE',
  'discovery_sample_sufficiency_status':'NOT_LEGAL_TO_DECIDE_UNTIL_PIT_MEMBERSHIP_JOIN',
  'return_lock':'NO_DISCOVERY_RETURN_MAY_BE_ATTACHED_FROM_THIS ARTIFACT ALONE',
 }
 OUT_PANEL.write_text(json.dumps({'system':'HENGCE','artifact':'IF07_DISCOVERY_ACCOUNTING_PANEL_NO_RETURNS','generated_at_utc':now(),'contains_price_or_forward_return_data':False,'rows':panel},ensure_ascii=False),encoding='utf-8')
 OUT_AUDIT.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:audit[k] for k in ['metadata_pair_input_count','eligible_accounting_pair_count','selected_v0_1_count_pre_PIT_membership','selected_unique_ticker_count_pre_PIT_membership','selected_signal_date_count_pre_PIT_membership','required_code_parse_pass_count','required_company_quarter_key_count']},ensure_ascii=False))

if __name__=='__main__': main()
