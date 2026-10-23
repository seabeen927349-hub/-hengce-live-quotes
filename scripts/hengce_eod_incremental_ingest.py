#!/usr/bin/env python3
"""HENGCE EOD incremental ingest through the original eod/YYYYMMDD vessel only.

Official TWSE price / institutional / margin legs are independent. A valid leg
is persisted immediately; a not-yet-published leg stays PENDING. No synthetic
leg, parallel EOD tree, second mother, Q017 authority, or E2 authority exists
here. The existing downstream EOD->canonical Historical Mother bridge consumes
these same eod/YYYYMMDD files.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, re
from datetime import date
from pathlib import Path
import hengce_daily_command_center_core_legacy as core

LEGS=('price','institutional','margin')
MIN={'price':900,'institutional':900,'margin':500}
COLS={
'price':['Date','Ticker','Name','VolumeShares','Trades','TurnoverTWD','Open','High','Low','Close','ChangeSign','Change','LastBid','LastBidVolume','LastAsk','LastAskVolume','PE','Source'],
'institutional':['Date','Ticker','Name','ForeignBuy','ForeignSell','ForeignNet','ForeignDealerBuy','ForeignDealerSell','ForeignDealerNet','TrustBuy','TrustSell','TrustNet','DealerNet','DealerProprietaryBuy','DealerProprietarySell','DealerProprietaryNet','DealerHedgeBuy','DealerHedgeSell','DealerHedgeNet','TotalNet','Source'],
'margin':['Date','Ticker','Name','MarginBuy','MarginSell','MarginCashRepayment','MarginPreviousBalance','MarginBalance','MarginNextDayLimit','ShortBuy','ShortSell','ShortStockRepayment','ShortPreviousBalance','ShortBalance','ShortNextDayLimit','Offset','Note','Source']}
SRC={'price':core.TWSE_PRICE,'institutional':core.TWSE_INST,'margin':core.TWSE_MARGIN}

class NotReady(RuntimeError): pass

def _files(out,leg): return sorted(out.glob(f'{leg}_[1-9].csv'))
def _digest(files):
 h=hashlib.sha256()
 for p in sorted(files,key=lambda x:x.name): h.update(p.name.encode());h.update(b'\0');h.update(p.read_bytes());h.update(b'\0')
 return h.hexdigest()
def _read(out,leg,iso):
 fs=_files(out,leg)
 if not fs:return None
 rows=[]
 for p in fs:
  with p.open(encoding='utf-8-sig',newline='') as f:
   r=csv.DictReader(f); miss=[c for c in COLS[leg] if c not in (r.fieldnames or [])]
   if miss:raise RuntimeError(f'{leg.upper()}_MISSING_COLUMNS:{p.name}:{",".join(miss)}')
   rows += list(r)
 keys=[(x.get('Date',''),x.get('Ticker','')) for x in rows]
 if len(rows)<MIN[leg]:raise RuntimeError(f'{leg.upper()}_ROWS_TOO_SMALL:{len(rows)}')
 if {d for d,_ in keys}!={iso}:raise RuntimeError(f'{leg.upper()}_WRONG_DATE')
 if any(not re.fullmatch(r'[1-9]\d{3}',t) for _,t in keys):raise RuntimeError(f'{leg.upper()}_BAD_TICKER')
 if len(keys)!=len(set(keys)):raise RuntimeError(f'{leg.upper()}_DUPLICATE_DATE_TICKER')
 return {'rows':len(rows),'sha256':_digest(fs),'files':[p.name for p in fs]}
def _write(out,leg,iso,rows):
 if len(rows)<MIN[leg]:raise RuntimeError(f'{leg.upper()}_ROWS_TOO_SMALL:{len(rows)}<{MIN[leg]}')
 keys=[(str(x.get('Date','')),str(x.get('Ticker',''))) for x in rows]
 if {d for d,_ in keys}!={iso}:raise RuntimeError(f'{leg.upper()}_PARSED_DATE_MISMATCH')
 if len(keys)!=len(set(keys)):raise RuntimeError(f'{leg.upper()}_DUPLICATE_DATE_TICKER')
 by={str(i):[] for i in range(1,10)}
 for x in rows:
  t=str(x.get('Ticker',''))
  if not re.fullmatch(r'[1-9]\d{3}',t):raise RuntimeError(f'{leg.upper()}_BAD_TICKER:{t}')
  by[t[0]].append(x)
 written=set()
 for k,rs in by.items():
  if not rs:continue
  p=out/f'{leg}_{k}.csv';tmp=p.with_suffix('.csv.tmp')
  with tmp.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=COLS[leg]);w.writeheader();w.writerows(sorted(rs,key=lambda x:x['Ticker']))
  tmp.replace(p);written.add(p.name)
 for p in _files(out,leg):
  if p.name not in written:p.unlink()
 info=_read(out,leg,iso)
 rec={'system':'HENGCE','artifact':'EOD_ORIGINAL_VESSEL_LEG_RECEIPT','target_date':iso,'leg':leg,'status':'COMPLETE','rows':info['rows'],'sha256':info['sha256'],'source':SRC[leg],'files':info['files'],'promoted_at_taipei':core.now_tw().isoformat(),'policy':'ORIGINAL_VESSEL_INDEPENDENT_LEG_PROMOTION_NO_WAIT_FOR_MARGIN','model_authority_created':False}
 core.atomic_json(out/'receipts'/f'{leg}.json',rec);return info

def _mother_receipt(out,iso,st):
 p=out/'receipts'/'mother.json'
 if not p.exists():return None
 try:r=json.loads(p.read_text(encoding='utf-8'))
 except Exception:return None
 if r.get('target_date')!=iso or str(r.get('status')).upper() not in ('PASS','COMPLETE'):return None
 if r.get('second_mother') is not False:return None
 hashes=r.get('promoted_leg_sha256') or {}
 available=[x for x in LEGS if st.get(f'{x}_status')=='COMPLETE']
 if any(hashes.get(x)!=st.get(f'{x}_sha256') for x in available):return None
 if r.get('mother_latest_date')!=iso:return None
 return r

def _price(ds,iso):
 p=core.get_json(core.TWSE_PRICE,{'date':ds,'type':'ALLBUT0999','response':'json'})
 if str(p.get('stat')).upper()!='OK':raise NotReady(f'PRICE_NOT_READY:{p.get("stat")}')
 if str(p.get('date'))!=ds:raise RuntimeError(f'PRICE_RESPONSE_DATE_MISMATCH:{p.get("date")}')
 t=next((x for x in p.get('tables') or [] if '證券代號' in (x.get('fields') or []) and '收盤價' in (x.get('fields') or [])),None)
 if not t:raise RuntimeError('PRICE_TABLE_NOT_FOUND')
 fs=t.get('fields') or [];idx={x:i for i,x in enumerate(fs)}
 def v(r,*ns):
  for n in ns:
   i=idx.get(n)
   if i is not None and i<len(r):return core.clean(r[i])
  return ''
 out=[]
 for r in t.get('data') or t.get('records') or []:
  s=v(r,'證券代號').replace('=','').replace('"','')
  if re.fullmatch(r'[1-9]\d{3}',s):out.append({'Date':iso,'Ticker':s,'Name':v(r,'證券名稱'),'VolumeShares':v(r,'成交股數','成交量'),'Trades':v(r,'成交筆數'),'TurnoverTWD':v(r,'成交金額'),'Open':v(r,'開盤價'),'High':v(r,'最高價'),'Low':v(r,'最低價'),'Close':v(r,'收盤價'),'ChangeSign':v(r,'漲跌(+/-)','漲跌'),'Change':v(r,'漲跌價差'),'LastBid':v(r,'最後揭示買價'),'LastBidVolume':v(r,'最後揭示買量'),'LastAsk':v(r,'最後揭示賣價'),'LastAskVolume':v(r,'最後揭示賣量'),'PE':v(r,'本益比'),'Source':core.TWSE_PRICE})
 return out
def _inst(ds,iso):
 q=core.get_json(core.TWSE_INST,{'date':ds,'selectType':'ALLBUT0999','response':'json'})
 if str(q.get('stat')).upper()!='OK':raise NotReady(f'INST_NOT_READY:{q.get("stat")}')
 if str(q.get('date'))!=ds:raise RuntimeError(f'INST_RESPONSE_DATE_MISMATCH:{q.get("date")}')
 fs=q.get('fields') or [];data=q.get('data') or q.get('records') or []
 if not data:
  for t in q.get('tables') or []:
   z=t.get('fields') or []
   if '證券代號' in z and any('外陸資買賣超股數' in str(x) for x in z):fs=z;data=t.get('data') or t.get('records') or [];break
 if not data:raise RuntimeError('INST_TABLE_NOT_FOUND')
 idx={x:i for i,x in enumerate(fs)}
 def v(r,e=None,c=None):
  if e in idx and idx[e]<len(r):return core.clean(r[idx[e]])
  if c:
   for f,i in idx.items():
    if c in f and i<len(r):return core.clean(r[i])
  return ''
 out=[]
 for r in data:
  s=v(r,e='證券代號').replace('=','').replace('"','')
  if re.fullmatch(r'[1-9]\d{3}',s):out.append({'Date':iso,'Ticker':s,'Name':v(r,e='證券名稱'),'ForeignBuy':v(r,c='外陸資買進股數(不含外資自營商)'),'ForeignSell':v(r,c='外陸資賣出股數(不含外資自營商)'),'ForeignNet':v(r,c='外陸資買賣超股數(不含外資自營商)'),'ForeignDealerBuy':v(r,e='外資自營商買進股數'),'ForeignDealerSell':v(r,e='外資自營商賣出股數'),'ForeignDealerNet':v(r,e='外資自營商買賣超股數'),'TrustBuy':v(r,e='投信買進股數'),'TrustSell':v(r,e='投信賣出股數'),'TrustNet':v(r,e='投信買賣超股數'),'DealerNet':v(r,e='自營商買賣超股數'),'DealerProprietaryBuy':v(r,e='自營商買進股數(自行買賣)'),'DealerProprietarySell':v(r,e='自營商賣出股數(自行買賣)'),'DealerProprietaryNet':v(r,e='自營商買賣超股數(自行買賣)'),'DealerHedgeBuy':v(r,e='自營商買進股數(避險)'),'DealerHedgeSell':v(r,e='自營商賣出股數(避險)'),'DealerHedgeNet':v(r,e='自營商買賣超股數(避險)'),'TotalNet':v(r,e='三大法人買賣超股數'),'Source':core.TWSE_INST})
 return out
def _margin(ds,iso):
 m=core.get_json(core.TWSE_MARGIN,{'date':ds,'selectType':'ALL','response':'json'})
 if str(m.get('stat')).upper()!='OK':raise NotReady(f'MARGIN_NOT_READY:{m.get("stat")}')
 if str(m.get('date'))!=ds:raise RuntimeError(f'MARGIN_RESPONSE_DATE_MISMATCH:{m.get("date")}')
 cs=list(m.get('tables') or [])
 if isinstance(m.get('fields'),list) and isinstance(m.get('data'),list):cs.append({'fields':m['fields'],'data':m['data']})
 for k,v in m.items():
  z=re.fullmatch(r'fields(\d+)',str(k))
  if z and isinstance(v,list) and isinstance(m.get('data'+z.group(1)),list):cs.append({'fields':v,'data':m['data'+z.group(1)]})
 data=None
 for t in cs:
  fs=[core.clean(x).replace(' ','') for x in t.get('fields') or []];d=t.get('data') or t.get('records') or []
  if len(fs)>=15 and len(d)>=MIN['margin'] and any('現金償還' in x for x in fs) and any('現券償還' in x for x in fs):data=d;break
 if data is None:raise RuntimeError('MARGIN_TABLE_NOT_FOUND')
 out=[]
 for r in data:
  if not isinstance(r,(list,tuple)) or len(r)<15:continue
  s=core.clean(r[0]).replace('=','').replace('"','')
  if re.fullmatch(r'[1-9]\d{3}',s):out.append(dict(zip(COLS['margin'],[iso,s,core.clean(r[1])]+[core.clean(x) for x in r[2:15]]+[core.clean(r[15]) if len(r)>15 else '',core.TWSE_MARGIN])))
 return out
FETCH={'price':_price,'institutional':_inst,'margin':_margin}

def ingest(target=None):
 target=target or core.now_tw().date()
 if target.weekday()>=5:return {'status':'SKIP_WEEKEND','target_date':target.isoformat()}
 ds=target.strftime('%Y%m%d');iso=target.isoformat();out=core.ROOT/'eod'/ds;out.mkdir(parents=True,exist_ok=True);sp=out/'status.json'
 try:st=json.loads(sp.read_text()) if sp.exists() else {}
 except Exception:st={}
 if st.get('target_date') not in (None,iso):raise RuntimeError('EOD_STATUS_DATE_MISMATCH')
 st.update({'system':'HENGCE','artifact':'EOD_ORIGINAL_VESSEL_INCREMENTAL_INGEST','target_date':iso,'policy':'ORIGINAL_VESSEL_INDEPENDENT_LEG_PROMOTION_NO_WAIT_FOR_MARGIN','mother_promotion_route':'EXISTING_EOD_TO_CANONICAL_HISTORICAL_MOTHER_BRIDGE','parallel_eod_tree':False,'second_mother':False,'model_authority_created':False})
 results=[];fatal=[];promoted=[]
 for leg in LEGS:
  try:
   old=_read(out,leg,iso)
   if old:info=old;result='ALREADY_COMPLETE'
   else:
    info=_write(out,leg,iso,FETCH[leg](ds,iso));result='PROMOTED';promoted.append(leg)
   st.update({f'{leg}_status':'COMPLETE',f'{leg}_date':iso,f'{leg}_rows':info['rows'],f'{leg}_sha256':info['sha256'],f'{leg}_source':SRC[leg]});st.pop(f'{leg}_pending_reason',None);st.pop(f'{leg}_error',None);results.append({'leg':leg,'result':result,'rows':info['rows'],'sha256':info['sha256']})
  except NotReady as e:st[f'{leg}_status']='PENDING';st[f'{leg}_pending_reason']=str(e);results.append({'leg':leg,'result':'PENDING','reason':str(e)})
  except Exception as e:st[f'{leg}_status']='ERROR';st[f'{leg}_error']=f'{type(e).__name__}:{e}';fatal.append({'leg':leg,'error':st[f'{leg}_error']});results.append({'leg':leg,'result':'ERROR','error':st[f'{leg}_error']})
 done=[x for x in LEGS if st.get(f'{x}_status')=='COMPLETE'];pending=[x for x in LEGS if st.get(f'{x}_status')=='PENDING'];errs=[x for x in LEGS if st.get(f'{x}_status')=='ERROR']
 mr=_mother_receipt(out,iso,st)
 if mr:
  mother_status='COMPLETE';mother_pending=[];st.pop('mother_pending_reason',None)
  st.update({'mother_receipt':'receipts/mother.json','mother_sha256':mr.get('mother_sha256'),'mother_latest_date':mr.get('mother_latest_date'),'mother_promoted_legs':mr.get('promoted_legs',done)})
 else:
  mother_status='PENDING' if done else 'NOT_READY';mother_pending=list(done)
  if done:st['mother_pending_reason']='AVAILABLE_LEGS_REQUIRE_CANONICAL_MOTHER_PROMOTION'
  for k in ('mother_receipt','mother_sha256','mother_latest_date','mother_promoted_legs'):st.pop(k,None)
 downstream_ready=st.get('price_status')=='COMPLETE' and mother_status=='COMPLETE'
 st.update({'available_legs':done,'pending_legs':pending,'error_legs':errs,'mother_status':mother_status,'mother_promotion_required':bool(done),'mother_pending_legs':mother_pending,'downstream_ready':downstream_ready,'three_leg_complete':len(done)==3,'formal_complete_day':len(done)==3,'status':'ERROR' if errs else ('COMPLETE' if len(done)==3 else 'PARTIAL'),'last_run_results':results,'updated_at_taipei':core.now_tw().isoformat()});core.atomic_json(sp,st)
 if fatal:raise RuntimeError('EOD_INTEGRITY_REJECTION:'+json.dumps(fatal,ensure_ascii=False))
 return st

def self_test():
 print(json.dumps({'self_test':'PASS','original_eod_tree_only':True,'second_mother':False,'no_wait_for_margin':True,'mother_gate':True,'q017_model_change':False,'e2_model_change':False},ensure_ascii=False))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=('ingest','self-test'),required=True);ap.add_argument('--date');a=ap.parse_args()
 if a.mode=='self-test':self_test();return 0
 x=ingest(date.fromisoformat(a.date) if a.date else None);print(json.dumps(x,ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
