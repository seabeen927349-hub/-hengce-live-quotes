#!/usr/bin/env python3
"""Proof of a fast no-return IF-07 iXBRL parser.

Reads frozen account-code rows and uses XBRL context periods instead of heavy
pandas.read_html. It ignores market prices and returns.

Control note: the 2454 2024Q2 income-statement controls are YTD Jan-Jun values,
not the single-quarter Apr-Jun values. This follows the already-frozen
HENGCE_IF07_PERIOD_COLUMN_SEMANTICS_PROOF_20261031.md and the V0.1 preregistration.
"""
from __future__ import annotations
import datetime as dt, json, math, re
from pathlib import Path
from typing import Any
import requests
from lxml import html

OUT=Path('research/selection_core_rebuild/generated/IF07_FAST_IXBRL_CONTEXT_PARSER_PROBE.json')
OUT.parent.mkdir(parents=True,exist_ok=True)
BASE='https://mopsov.twse.com.tw/server-java/FileDownLoad'
CODES={'Revenue_YTD':'4000','COGS_YTD':'5000','OperatingIncome_YTD':'6900','CFO_YTD':'AAAA','AR':'1170','Inventory':'130X','Assets':'1XXX','Liabilities':'2XXX'}
FLOW={'Revenue_YTD','COGS_YTD','OperatingIncome_YTD','CFO_YTD'}
QEND={1:'03-31',2:'06-30',3:'09-30',4:'12-31'}
CONTROLS={
 ('2330',2023,1):{'Revenue_YTD':508632973.0,'COGS_YTD':222132581.0,'OperatingIncome_YTD':231238157.0,'CFO_YTD':385244745.0,'AR':147715125.0,'Inventory':216067981.0,'Assets':5045844348.0,'Liabilities':1952946750.0},
 ('2454',2024,2):{'Revenue_YTD':260729268.0,'COGS_YTD':128692316.0,'OperatingIncome_YTD':57135880.0,'CFO_YTD':75144111.0,'AR':45889387.0,'Inventory':53578351.0,'Assets':681374287.0,'Liabilities':290750665.0},
}

def local(tag:Any)->str:
 s=str(tag).lower()
 return s.split('}')[-1].split(':')[-1]

def text(e)->str:
 return ''.join(e.itertext()).replace('\xa0',' ').strip()

def parse_num(s:str, sign:str|None=None)->float|None:
 x=s.strip().replace(',','').replace(' ','')
 if not x or x in {'-','--'}: return None
 neg=False
 if x.startswith('(') and x.endswith(')'): neg=True; x=x[1:-1]
 x=re.sub(r'[^0-9.+-]','',x)
 try: v=float(x)
 except Exception: return None
 if sign=='-' and v>0: v=-v
 if neg and v>0: v=-v
 return v if math.isfinite(v) else None

def contexts(root):
 out={}
 for e in root.iter():
  if local(e.tag)!='context': continue
  cid=e.get('id') or e.get('ID')
  if not cid: continue
  instant=start=end=None; segmented=False
  for d in e.iter():
   k=local(d.tag)
   if k=='instant': instant=(d.text or '').strip()
   elif k=='startdate': start=(d.text or '').strip()
   elif k=='enddate': end=(d.text or '').strip()
   elif k in {'segment','scenario'}: segmented=True
  out[cid]={'instant':instant,'start':start,'end':end,'segmented':segmented}
 return out

def parse(content:bytes,year:int,q:int):
 root=html.fromstring(content)
 ctx=contexts(root)
 end=f'{year}-{QEND[q]}'; start=f'{year}-01-01'
 rows={}
 for tr in root.iter('tr'):
  cells=[c for c in tr if local(c.tag) in {'td','th'}]
  if not cells: continue
  code=re.sub(r'\s+','',text(cells[0]))
  if code not in CODES.values(): continue
  facts=[]
  for d in tr.iter():
   if local(d.tag)!='nonfraction': continue
   cref=d.get('contextref') or d.get('contextRef')
   c=ctx.get(cref or '')
   if not c or c['segmented']: continue
   v=parse_num(text(d),d.get('sign'))
   if v is None: continue
   facts.append({'contextref':cref,'ctx':c,'value':v,'name':d.get('name')})
  rows[code]=facts
 vals={}; evidence={}
 for field,code in CODES.items():
  fs=rows.get(code,[])
  if field in FLOW:
   hits=[f for f in fs if f['ctx']['start']==start and f['ctx']['end']==end]
  else:
   hits=[f for f in fs if f['ctx']['instant']==end]
  uniq=[]; seen=set()
  for f in hits:
   key=(f['contextref'],f['value'],f['name'])
   if key not in seen: seen.add(key); uniq.append(f)
  values=sorted(set(f['value'] for f in uniq))
  if len(values)!=1:
   return None,{'status':'FAIL','reason':f'{field}:{code}:matching_values={values}','matching_facts':uniq[:10],'context_count':len(ctx)}
  vals[field]=values[0]; evidence[field]={'code':code,'matching_fact_count':len(uniq),'contextrefs':sorted(set(f['contextref'] for f in uniq)),'value':values[0]}
 return vals,{'status':'PASS','context_count':len(ctx),'evidence':evidence}

def main():
 s=requests.Session(); s.headers.update({'User-Agent':'Mozilla/5.0 HENGCE-IF07-fast-parser-probe/0.2','Referer':'https://mopsov.twse.com.tw/mops/web/t203sb01'})
 results=[]
 for (ticker,year,q),expected in CONTROLS.items():
  p={'functionName':'t164sb01','step':'9','co_id':ticker,'year':year,'season':q,'report_id':'C'}
  r=s.get(BASE,params=p,timeout=120)
  vals,audit=parse(r.content,year,q) if r.status_code==200 else (None,{'status':'FAIL','reason':f'HTTP_{r.status_code}'})
  checks={k:(vals is not None and vals.get(k)==v) for k,v in expected.items()}
  results.append({'ticker':ticker,'year':year,'quarter':q,'http_status':r.status_code,'bytes':len(r.content),'parser':audit,'values':vals,'expected':expected,'exact_checks':checks,'all_exact':all(checks.values())})
 overall=all(x['all_exact'] for x in results)
 obj={'system':'HENGCE','artifact':'IF07_FAST_IXBRL_CONTEXT_PARSER_PROBE_V0_2','generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'contains_price_or_forward_return_data':False,'control_oracle':'Q2/Q3/Q4 flow fields use explicit Jan-1-to-quarter-end YTD semantics','results':results,'overall':overall,'verdict':'PASS' if overall else 'FAIL'}
 OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'verdict':obj['verdict'],'results':[{'ticker':x['ticker'],'all_exact':x['all_exact'],'parser_status':x['parser']['status'],'values':x['values']} for x in results]},ensure_ascii=False))
if __name__=='__main__': main()
