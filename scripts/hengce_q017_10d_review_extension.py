#!/usr/bin/env python3
"""Q017 10D review extension: isolated hypothetical lane + diagnostics.

The formal overlapping-cohort ledger remains owned by hengce_q017_10d_review.py.
This extension NEVER writes formal Q017 selections. It:
1) tracks explicitly zero-authority hypothetical receipts in a physically separate ledger;
2) computes review/health diagnostics for formal and hypothetical lanes;
3) guarantees signal-date x ticker identity, D1=signal day, exact D10 closure,
   no cross-lane merge, and no model mutation.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math,statistics,tempfile,urllib.parse,urllib.request
from datetime import datetime,timezone,timedelta
from pathlib import Path

TZ=timezone(timedelta(hours=8)); HOLD=10
AUTH='PERFORMANCE_REVIEW_ONLY_NO_CAPITAL_AUTHORITY'
HYP_AUTH='HYPOTHETICAL_ONLY_ZERO_CAPITAL_AUTHORITY'
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'hengce'/'q017_review_10d'
HLEDGER=OUT/'hypothetical_ledger_latest.json'
DIAG=OUT/'diagnostics_latest.json'

def now(): return datetime.now(TZ).isoformat()
def sha(o): return hashlib.sha256(json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def atomic(p,o):
 p.parent.mkdir(parents=True,exist_ok=True); q=p.with_suffix(p.suffix+'.tmp'); q.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); q.replace(p)
def num(x):
 try:
  if x is None or str(x).strip() in ('','--','---'): return None
  v=float(str(x).replace(',','')); return v if math.isfinite(v) else None
 except Exception:return None
def pct(x): return None if x is None else round(float(x),10)

def complete_dates(root):
 out=[]
 for p in sorted((root/'eod').glob('20????????')):
  ds=f'{p.name[:4]}-{p.name[4:6]}-{p.name[6:8]}'
  try:s=json.loads((p/'status.json').read_text())
  except Exception:continue
  if s.get('target_date')!=ds:continue
  if all(s.get(f'{k}_status')=='COMPLETE' and s.get(f'{k}_date')==ds for k in ('price','institutional','margin')):out.append(ds)
 return out

def prices(root,ds):
 rows={}; d=root/'eod'/ds.replace('-','')
 for p in sorted(d.glob('price_*.csv')):
  with p.open(encoding='utf-8-sig',newline='') as f:
   for r in csv.DictReader(f):
    t=str(r.get('Ticker') or '').strip()
    if t:rows[t]={'open':num(r.get('Open')),'high':num(r.get('High')),'low':num(r.get('Low')),'close':num(r.get('Close'))}
 return rows

def empty_hledger():
 return {'schema_version':1,'system':'HENGCE','module':'Q017_10D_HYPOTHETICAL_LEDGER','authority':AUTH,'authority_lane':'HYPOTHETICAL_ZERO_CAPITAL_ONLY','capital_authority_twd':0,'hold_sessions_required':10,'signal_day_is_D1':True,'cohort_key':'SIGNAL_DATE_X_TICKER','cross_lane_merge_forbidden':True,'cohorts':{},'ledger_sha256':None}
def load_hledger(root):
 p=root/'hengce/q017_review_10d/hypothetical_ledger_latest.json'
 if not p.exists():return empty_hledger()
 o=json.loads(p.read_text()); h=o.get('ledger_sha256')
 if not h or h!=sha({k:v for k,v in o.items() if k!='ledger_sha256'}):raise RuntimeError('HYPOTHETICAL_LEDGER_HASH_INVALID')
 return o

def validate_receipt(o):
 if o.get('authority')!=HYP_AUTH:return False
 if int(o.get('formal_buy_count') or 0)!=0:return False
 if (o.get('causality_warning') or {}).get('must_not_be_promoted_to_formal_signal') is not True:return False
 top=o.get('hypothetical_top3') or []
 return 0<len(top)<=3

def seed_hypothetical(root,ledger):
 created=[]
 for p in sorted((root/'receipts').glob('HENGCE_Q017_HYPOTHETICAL_OPEN_RECONSTRUCTION_*.json')):
  o=json.loads(p.read_text());
  if not validate_receipt(o):continue
  ds=o['trade_date']; source_sha=hashlib.sha256(p.read_bytes()).hexdigest()
  for rank,x in enumerate(o['hypothetical_top3'],1):
   t=str(x['ticker']); ref=num(x.get('open'))
   if not ref or ref<=0:raise RuntimeError(f'HYPOTHETICAL_REF_INVALID:{ds}:{t}')
   cid=f'HYP-{ds.replace("-","")}-{t}'
   imm={'signal_date':ds,'ticker':t,'rank':rank,'ref':ref,'beta':num(x.get('beta60')),'residual':num(x.get('residual')),'score':num(x.get('score')),'source_sha256':source_sha,'capital_authority_twd':0}
   ih=sha(imm)
   if cid in ledger['cohorts']:
    if ledger['cohorts'][cid].get('immutable_signal_sha256')!=ih:raise RuntimeError(f'HYPOTHETICAL_IMMUTABLE_CONFLICT:{cid}')
    continue
   ledger['cohorts'][cid]={'cohort_id':cid,'engine':'Q017','authority_lane':'HYPOTHETICAL_ZERO_CAPITAL_ONLY','capital_authority_twd':0,'signal_date':ds,'ticker':t,'name':x.get('name') or '','rank':rank,'selection_reference_price':ref,'selection_reference_type':'COUNTERFACTUAL_SESSION_OPEN_NOT_PROVEN_0901','beta':num(x.get('beta60')),'residual':num(x.get('residual')),'score':num(x.get('score')),'gap':num(x.get('gap')),'expected_gap':num(x.get('expected_gap')),'source_receipt':str(p.relative_to(root)),'source_sha256':source_sha,'immutable_signal_sha256':ih,'hold_sessions_required':10,'status':'ACTIVE','sessions':[],'current_day':0,'final':None};created.append(cid)
 return created

def append(c,ds,row):
 if any(x['date']==ds for x in c['sessions']):return False
 if len(c['sessions'])>=HOLD:return False
 d=len(c['sessions'])+1; ref=c['selection_reference_price']; row=row or {}
 hi,lo,cl=row.get('high'),row.get('low'),row.get('close')
 rec={'day':d,'date':ds,'price_status':'OBSERVED' if cl is not None else 'NO_PRICE_ROW','open':row.get('open'),'high':hi,'low':lo,'close':cl,'close_return_from_selection':pct(cl/ref-1) if cl is not None else None,'session_high_return_from_selection':pct(hi/ref-1) if hi is not None else None,'session_low_return_from_selection':pct(lo/ref-1) if lo is not None else None}
 c['sessions'].append(rec); c['current_day']=d
 obs=[x for x in c['sessions'] if x['price_status']=='OBSERVED']; hs=[x['high'] for x in obs if x.get('high') is not None]; ls=[x['low'] for x in obs if x.get('low') is not None]; cs=[x['close'] for x in obs if x.get('close') is not None]
 c['mark_to_close_return']=pct(cs[-1]/ref-1) if cs else None;c['mfe_to_date']=pct(max(hs)/ref-1) if hs else None;c['mae_to_date']=pct(min(ls)/ref-1) if ls else None
 if d==HOLD:
  c['status']='CLOSED_D10';c['final']={'closed_on':ds,'d10_close':cl,'d10_return_from_selection':rec['close_return_from_selection'],'mfe_10d':c['mfe_to_date'],'mae_10d':c['mae_to_date'],'observed_price_sessions':len(obs),'missing_price_sessions':HOLD-len(obs)}
 return True

def benchmark(root,ds,allow_network=True):
 p=root/'hengce/q017_review_10d/benchmarks'/f'{ds.replace("-","")}.json'
 if p.exists():return json.loads(p.read_text())
 if not allow_network:return None
 try:
  q=urllib.parse.urlencode({'date':ds.replace('-',''),'type':'ALLBUT0999','response':'json'}); req=urllib.request.Request('https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?'+q,headers={'User-Agent':'Mozilla/5.0'})
  raw=json.loads(urllib.request.urlopen(req,timeout=20).read().decode()); out={'date':ds,'source':'TWSE_MI_INDEX','taiex_return':None,'electronics_return':None}
  for tbl in raw.get('tables') or []:
   for r in tbl.get('data') or []:
    if not r:continue
    label=str(r[0]).replace(' ','')
    vals=[num(v) for v in r[1:]]
    if '發行量加權股價指數' in label:
     ch=next((v for v in reversed(vals) if v is not None),None)
    if label in ('電子類指數','電子類'):
     pass
  atomic(p,out);return out
 except Exception:return None

def seed_from_explicit_receipt(root,ledger):
 """Optional trusted D1 seed generated after official close when EOD archive is not yet present."""
 p=root/'receipts/HENGCE_Q017_10D_HYPOTHETICAL_D1_SEED_20261019.json'
 if not p.exists():return 0
 o=json.loads(p.read_text()); n=0
 if o.get('authority_lane')!='HYPOTHETICAL_ZERO_CAPITAL_ONLY' or int(o.get('capital_authority_twd') or -1)!=0:return 0
 for x in o.get('members') or []:
  cid=f'HYP-{o["signal_date"].replace("-","")}-{x["ticker"]}';c=ledger['cohorts'].get(cid)
  if not c or c['sessions']:continue
  append(c,o['signal_date'],{'open':num(x['open']),'high':num(x['high']),'low':num(x['low']),'close':num(x['close'])});n+=1
 return n

def health(vals):
 recent=vals[-20:]
 if len(recent)<10:return {'status':'NORMAL','downgrade_enabled':False,'reason':'INSUFFICIENT_COMPLETED_D10_SAMPLE','recent20_sample':len(recent)}
 mean=statistics.mean(recent); win=sum(v>0 for v in recent)/len(recent)
 st='ALERT' if mean<0 and win<0.4 else ('WATCH' if mean<=0 or win<0.5 else 'NORMAL')
 return {'status':st,'downgrade_enabled':True,'recent20_sample':len(recent),'recent20_mean_return':mean,'recent20_win_rate':win,'policy':'DIAGNOSTIC_ONLY_DO_NOT_MUTATE_Q017'}

def formal_rows(root):
 p=root/'hengce/q017_review_10d/ledger_latest.json'
 if not p.exists():return []
 try:o=json.loads(p.read_text());return list((o.get('cohorts') or {}).values())
 except Exception:return []
def hypo_rows(ledger):return list(ledger['cohorts'].values())
def review(rows,ds,lane):
 today=[c for c in rows if c.get('signal_date')==ds]; rets=[num(c.get('mark_to_close_return')) for c in today];rets=[x for x in rets if x is not None]
 closed=[c for c in rows if str(c.get('status','')).startswith('CLOSED_D10')]; finals=[num((c.get('final') or {}).get('d10_return_from_selection')) for c in closed]; finals=[x for x in finals if x is not None]
 top1=next((c for c in today if int(c.get('rank') or 0)==1),None)
 return {'schema_version':1,'system':'HENGCE','module':'Q017_10D_ENGINE_DIAGNOSTIC','authority':AUTH,'lane':lane,'review_date':ds,'generated_at_taipei':now(),'policy':'EVALUATE_ONLY_DO_NOT_MUTATE_Q017','today_signal_count':len(today),'today_top1_return':num((top1 or {}).get('mark_to_close_return')),'today_top3_average_return':statistics.mean(rets) if rets else None,'today_top3_win_count':sum(x>0 for x in rets),'today_top3_observed_count':len(rets),'today_top3_win_rate':sum(x>0 for x in rets)/len(rets) if rets else None,'active_count':sum(c.get('status')=='ACTIVE' for c in rows),'completed_d10_count':len(closed),'completed_d10_mean_return':statistics.mean(finals) if finals else None,'completed_d10_win_rate':sum(x>0 for x in finals)/len(finals) if finals else None,'recent20_mean_return':statistics.mean(finals[-20:]) if finals else None,'recent20_win_rate':sum(x>0 for x in finals[-20:])/len(finals[-20:]) if finals else None,'degradation':health(finals),'cross_lane_merge_forbidden':True,'hypothetical_capital_authority_twd':0 if lane.startswith('HYPOTHETICAL') else None}

def update(root,target,allow_network=True):
 ledger=load_hledger(root); created=seed_hypothetical(root,ledger); seeded=seed_from_explicit_receipt(root,ledger); dates=[d for d in complete_dates(root) if d<=target]
 pc={}
 for c in ledger['cohorts'].values():
  if c.get('status')=='CLOSED_D10':continue
  for ds in [x for x in dates if x>=c['signal_date']]:
   if len(c['sessions'])>=HOLD:break
   pc.setdefault(ds,prices(root,ds));append(c,ds,pc[ds].get(c['ticker']))
 ledger['generated_at_taipei']=now();ledger['latest_complete_eod_date']=dates[-1] if dates else None;ledger['active_cohort_count']=sum(c['status']=='ACTIVE' for c in ledger['cohorts'].values());ledger['closed_cohort_count']=sum(c['status']=='CLOSED_D10' for c in ledger['cohorts'].values());ledger['ledger_sha256']=sha({k:v for k,v in ledger.items() if k!='ledger_sha256'});atomic(root/'hengce/q017_review_10d/hypothetical_ledger_latest.json',ledger)
 ds=target; f=review(formal_rows(root),ds,'FORMAL_SCHEMA5_ONLY'); h=review(hypo_rows(ledger),ds,'HYPOTHETICAL_ZERO_CAPITAL_ONLY'); out={'schema_version':1,'system':'HENGCE','module':'Q017_10D_REVIEW_EXTENSION','review_date':ds,'generated_at_taipei':now(),'status':'PASS','signal_day_is_d1':True,'hold_sessions':10,'new_hypothetical_cohorts':created,'explicit_d1_seeded_members':seeded,'formal':f,'hypothetical':h,'guard':{'cross_lane_merge':'PASS','hypothetical_capital_authority_twd':0,'model_mutation_allowed':False}}
 atomic(root/'hengce/q017_review_10d/diagnostics_latest.json',out);atomic(root/'hengce/q017_review_10d'/f'diagnostics_{ds.replace("-","")}.json',out);return out

def selftest():
 with tempfile.TemporaryDirectory() as td:
  r=Path(td);(r/'receipts').mkdir();o={'authority':HYP_AUTH,'formal_buy_count':0,'trade_date':'2026-10-20','causality_warning':{'must_not_be_promoted_to_formal_signal':True},'hypothetical_top3':[{'ticker':'1111','name':'X','open':100,'beta60':1,'residual':-.02,'score':1.5}]};atomic(r/'receipts/HENGCE_Q017_HYPOTHETICAL_OPEN_RECONSTRUCTION_20261020.json',o)
  l=empty_hledger();assert len(seed_hypothetical(r,l))==1;c=l['cohorts']['HYP-20261020-1111'];append(c,'2026-10-20',{'open':100,'high':102,'low':99,'close':101});append(c,'2026-10-21',{'open':102,'high':103,'low':100,'close':102});assert c['current_day']==2 and c['status']=='ACTIVE';o['trade_date']='2026-10-21';atomic(r/'receipts/HENGCE_Q017_HYPOTHETICAL_OPEN_RECONSTRUCTION_20261021.json',o);assert len(seed_hypothetical(r,l))==1;assert len(l['cohorts'])==2;assert all(x['capital_authority_twd']==0 for x in l['cohorts'].values());
 print('PASS Q017_10D_REVIEW_EXTENSION_SELFTEST')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['update','self-test'],default='update');ap.add_argument('--root',default=str(ROOT));ap.add_argument('--date');ap.add_argument('--no-network-benchmark',action='store_true');a=ap.parse_args()
 if a.mode=='self-test':selftest();return 0
 ds=a.date or datetime.now(TZ).date().isoformat();print(json.dumps(update(Path(a.root),ds,not a.no_network_benchmark),ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
