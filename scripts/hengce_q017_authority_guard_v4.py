#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math
from datetime import datetime, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo
TZ=ZoneInfo('Asia/Taipei'); ROOT=Path(__file__).resolve().parents[1]; RADAR=ROOT/'hengce/q017_radar'; LATEST=RADAR/'latest.json'; DECISION_DIR=RADAR/'decision'
FORMAL_SCHEMA_MIN=4; MIN_PROVIDER_COVERAGE=1.0; SOX_1D_MAX=0.0; SOX_5D_MAX=-0.03; DXY_5D_MIN=-0.005
ALLOWED_MODULES={'Q017_SOX_ELECTRONICS_DECISION_LOCK','Q017_SOX_ELECTRONICS_RADAR_LOCKED','Q017_AUTHORITY_GUARD_FAIL_CLOSED','Q017_DECISION_ATTEMPT_FAIL_CLOSED'}; FORBIDDEN_MODULES={'Q017_SOX_ELECTRONICS_RADAR'}
def now_tw():return datetime.now(TZ)
def canonical_sha(o):return hashlib.sha256(json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def read_json(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def atomic_json(p,o):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');t.replace(p)
def decision_path_for(d):return DECISION_DIR/f'{d.replace("-","")}_0901.json'
def _f(x):
 try:return float(x)
 except:return None
def _close(a,b,tol=1e-10):return a is not None and b is not None and math.isfinite(a) and math.isfinite(b) and abs(a-b)<=tol*max(1.0,abs(a),abs(b))
def _dt(x):
 try:
  d=datetime.fromisoformat(str(x));return d if d.tzinfo else None
 except:return None
def _state(c):
 n=sum(bool(v) for v in c.values());return 'GO' if n==len(c) else 'WATCH' if n else 'CASH'
def _premarket(d,trade):
 pc=((d.get('data_status') or {}).get('premarket_coherence') or {})
 if pc.get('status')!='PASS':return False,'PREMARKET_COHERENCE_NOT_PASS'
 if pc.get('trade_date')!=trade:return False,'PREMARKET_COHERENCE_TRADE_DATE_MISMATCH'
 hist=str(pc.get('electronics_history_latest') or '')
 try:hd=datetime.strptime(hist,'%Y-%m-%d').date();td=datetime.strptime(trade,'%Y-%m-%d').date()
 except:return False,'PREMARKET_DATE_PARSE_FAIL'
 if hd>=td:return False,'PREMARKET_HISTORY_NOT_CAUSAL'
 eod=pc.get('latest_complete_eod_date')
 if eod:
  try:ed=datetime.strptime(str(eod),'%Y%m%d').date() if len(str(eod))==8 else datetime.strptime(str(eod),'%Y-%m-%d').date()
  except:return False,'PREMARKET_EOD_DATE_PARSE_FAIL'
  if ed>=td:return False,'PREMARKET_EOD_NOT_CAUSAL'
  if hd<ed:return False,'PREMARKET_HISTORY_BEHIND_COMPLETE_EOD'
 return True,'PREMARKET_COHERENCE_VALID'
def _provenance(d,trade):
 if d.get('binding_status')!='PASS':return False,'DECISION_BINDING_STATUS_NOT_PASS'
 if d.get('trade_date')!=trade:return False,'DECISION_TRADE_DATE_MISMATCH'
 dl=d.get('decision_lock') or {}
 if dl.get('cutoff_label')!='09:01':return False,'DECISION_CUTOFF_LABEL_INVALID'
 if dl.get('capture_window_taipei')!='09:01:00-09:01:59.999999':return False,'DECISION_CAPTURE_WINDOW_LABEL_INVALID'
 if dl.get('window_valid') is not True:return False,'DECISION_WINDOW_VALID_NOT_TRUE'
 if dl.get('immutable') is not True:return False,'DECISION_NOT_IMMUTABLE'
 if dl.get('rerank_after_lock') is not False:return False,'DECISION_RERANK_FLAG_INVALID'
 if int(dl.get('attempt_count') or 0)<1 or int(dl.get('accepted_attempt') or 0)<1:return False,'DECISION_ATTEMPT_PROVENANCE_MISSING'
 s=_dt(dl.get('capture_started_at_taipei'));f=_dt(dl.get('capture_finished_at_taipei'))
 if not s or not f:return False,'DECISION_CAPTURE_TIMESTAMP_INVALID'
 td=datetime.strptime(trade,'%Y-%m-%d').date();sl=s.astimezone(TZ);fl=f.astimezone(TZ);end=datetime.combine(td,dtime(9,1,59,999999),tzinfo=TZ)
 if sl.date()!=td or fl.date()!=td:return False,'DECISION_CAPTURE_DATE_MISMATCH'
 if sl.hour!=9 or sl.minute!=1 or fl.hour!=9 or fl.minute!=1 or fl<sl or fl>end:return False,'DECISION_CAPTURE_NOT_INSIDE_0901_MINUTE'
 return True,'DECISION_PROVENANCE_VALID'
def _coverage(d):
 ds=d.get('data_status') or {};eligible=int(ds.get('eligible_beta_count') or 0);returned=int(ds.get('provider_returned_count') or 0);opened=int(ds.get('opened_by_decision_count') or 0);cov=_f(ds.get('provider_coverage'));req=_f(ds.get('provider_coverage_required'))
 if eligible<=0:return False,'ELIGIBLE_COUNT_INVALID'
 if returned!=eligible:return False,'PROVIDER_RETURNED_COUNT_NOT_100PCT'
 if cov is None or cov<1.0 or not _close(cov,returned/eligible):return False,'PROVIDER_COVERAGE_NOT_100PCT'
 if req!=1.0:return False,'PROVIDER_COVERAGE_REQUIREMENT_DRIFT'
 if opened<0 or opened>returned:return False,'OPENED_COUNT_INVALID'
 if ds.get('critical_set_complete') is not True:return False,'CRITICAL_SET_NOT_COMPLETE'
 if ds.get('critical_missing') not in ([],None):return False,'CRITICAL_SET_MISSING_NONEMPTY'
 if int(ds.get('critical_set_count') or 0)<=0:return False,'CRITICAL_SET_COUNT_INVALID'
 return True,'COVERAGE_VALID'
def _gate(d):
 if int(d.get('schema_version') or 0)<4:return False,'DECISION_REQUIRES_SCHEMA_V4'
 if d.get('module')!='Q017_SOX_ELECTRONICS_DECISION_LOCK':return False,'DECISION_MODULE_NOT_FORMAL_LOCK'
 r=d.get('rules') or {}
 if _f(r.get('sox_1d_max'))!=0.0:return False,'Q017_GATE_DRIFT_SOX1D'
 if _f(r.get('sox_5d_max'))!=-0.03:return False,'Q017_GATE_DRIFT_SOX5D'
 if _f(r.get('dxy_5d_min'))!=-0.005:return False,'Q017_GATE_DRIFT_DXY5D'
 if _f(r.get('residual_max'))!=0.04:return False,'Q017_RESIDUAL_RULE_DRIFT'
 if r.get('authority')!='Q017_LOCK_20261018.json':return False,'Q017_GATE_AUTHORITY_LOCK_MISSING'
 mg=d.get('market_gate') or {};s1=_f(mg.get('sox_1d'));s5=_f(mg.get('sox_5d'));d5=_f(mg.get('dxy_5d'))
 if None in (s1,s5,d5):return False,'Q017_GATE_VALUES_MISSING'
 if mg.get('source_lock')!='Q017_LOCK_20261018.json':return False,'Q017_MARKET_GATE_SOURCE_LOCK_MISSING'
 checks={'sox_1d_lte_0':s1<=0.0,'sox_5d_lte_minus_3pct':s5<=-0.03,'dxy_5d_gte_minus_0_5pct':d5>=-0.005}
 if mg.get('checks')!=checks:return False,'Q017_GATE_CHECKS_INCONSISTENT'
 go=all(checks.values())
 if mg.get('gate_go') is not go:return False,'Q017_GATE_BOOLEAN_INCONSISTENT'
 if d.get('market_state')!=_state(checks):return False,'Q017_MARKET_STATE_INCONSISTENT'
 ds=((d.get('data_status') or {}).get('dxy') or {})
 if ds.get('status')!='PASS':return False,'DXY_DATA_STATUS_NOT_PASS'
 if ds.get('symbol')!='DX-Y.NYB':return False,'DXY_SYMBOL_DRIFT'
 if not _close(_f(ds.get('dxy_5d')),d5):return False,'DXY_VALUE_MISMATCH'
 return True,'FROZEN_Q017_GATE_VALID'
def _top3(d):
 mg=d.get('market_gate') or {};s1=_f(mg.get('sox_1d'));go=bool(mg.get('gate_go'));top=d.get('top3') or []
 if len(top)>3:return False,'TOP3_TOO_MANY_ROWS'
 seen=[];last=None;td=datetime.strptime(d['trade_date'],'%Y-%m-%d').date()
 for x in top:
  t=str(x.get('ticker') or '')
  if not t or t in seen:return False,'TOP3_TICKER_DUPLICATE_OR_MISSING'
  seen.append(t);b=_f(x.get('beta'));op=_f(x.get('open'));pc=_f(x.get('previous_close'));gap=_f(x.get('gap'));exp=_f(x.get('expected_gap'));res=_f(x.get('residual'));score=_f(x.get('score'))
  if None in (b,op,pc,gap,exp,res,score) or b<=0 or op<=0 or pc<=0:return False,'TOP3_NUMERIC_FIELDS_INVALID'
  cg=op/pc-1;ce=b*s1;cr=cg-ce;cs=b*(1+25*max(-cr,0))
  if not _close(gap,cg) or not _close(exp,ce) or not _close(res,cr) or not _close(score,cs):return False,'TOP3_SCORE_MATH_INVALID'
  if res>0.04+1e-12:return False,'TOP3_RESIDUAL_RULE_VIOLATION'
  if bool(x.get('qualified')) is not go:return False,'TOP3_QUALIFIED_FLAG_INCONSISTENT'
  obs=_dt(x.get('decision_observed_at_taipei'))
  if not obs or obs.astimezone(TZ).date()!=td or obs.astimezone(TZ).hour!=9 or obs.astimezone(TZ).minute!=1:return False,'TOP3_OBSERVATION_NOT_0901_CAUSAL'
  if last is not None and score>last+1e-12:return False,'TOP3_NOT_SCORE_SORTED'
  last=score
 return True,'TOP3_MATH_VALID'
def validate_decision(d,trade):
 for fn,args in [(_provenance,(d,trade)),(_coverage,(d,)),(_premarket,(d,trade)),(_gate,(d,)),(_top3,(d,))]:
  ok,reason=fn(*args)
  if not ok:return False,reason
 h=d.get('decision_snapshot_sha256');exp=canonical_sha({k:v for k,v in d.items() if k!='decision_snapshot_sha256'})
 if not h or h!=exp:return False,'DECISION_SNAPSHOT_HASH_INVALID'
 return True,'VALID_SCHEMA4_0901_DECISION_AUTHORITY'
def validate(p):
 m=p.get('module')
 if m in FORBIDDEN_MODULES:return False,'LEGACY_RADAR_MODULE_FORBIDDEN'
 if m not in ALLOWED_MODULES:return False,f'UNKNOWN_OR_UNAUTHORIZED_MODULE:{m}'
 if m in {'Q017_AUTHORITY_GUARD_FAIL_CLOSED','Q017_DECISION_ATTEMPT_FAIL_CLOSED'}:
  if int(p.get('schema_version') or 0)<4:return False,'FAIL_CLOSED_SCHEMA_TOO_OLD'
  if p.get('binding_status')!='DATA_PENDING' or p.get('market_state')!='DATA_PENDING' or p.get('authority')!='NO_FORMAL_SIGNAL' or p.get('top3') not in ([],None) or int(p.get('formal_buy_count') or 0)!=0:return False,'FAIL_CLOSED_PLACEHOLDER_INVALID'
  return True,'VALID_FAIL_CLOSED_PLACEHOLDER'
 if int(p.get('schema_version') or 0)<4:return False,'FORMAL_Q017_REQUIRES_SCHEMA_V4'
 trade=str(p.get('trade_date') or '')
 if len(trade)!=10:return False,'TRADE_DATE_MISSING'
 path=decision_path_for(trade)
 if not path.exists():return False,'NO_IMMUTABLE_0901_DECISION_SNAPSHOT'
 d=read_json(path);ok,reason=validate_decision(d,trade)
 if not ok:return False,reason
 if p.get('decision_snapshot_sha256')!=d.get('decision_snapshot_sha256'):return False,'LATEST_NOT_BOUND_TO_DECISION_HASH'
 if p.get('trade_date')!=d.get('trade_date'):return False,'LATEST_TRADE_DATE_DIFFERS_FROM_DECISION'
 if [str(x.get('ticker')) for x in p.get('top3') or []]!=[str(x.get('ticker')) for x in d.get('top3') or []]:return False,'LATEST_TOP3_DIFFERS_FROM_LOCKED_DECISION'
 if m=='Q017_SOX_ELECTRONICS_RADAR_LOCKED':
  mon=p.get('monitor') or {}
  if mon.get('rerank_performed') is not False:return False,'MONITOR_RERANK_FLAG_NOT_FALSE'
  if mon.get('ranking_frozen') is not True:return False,'MONITOR_RANKING_NOT_FROZEN'
 return True,'VALID_LOCKED_Q017_AUTHORITY_SCHEMA_V4_PROVENANCE_HARDENED'
def quarantine_payload(r,reason):
 trade=str(r.get('trade_date') or now_tw().date().isoformat());tops=[]
 for x in r.get('top3') or []:
  if isinstance(x,dict) and x.get('ticker'):tops.append(str(x['ticker']))
  elif isinstance(x,str):tops.append(x)
 return {'schema_version':4,'system':'HENGCE','module':'Q017_AUTHORITY_GUARD_FAIL_CLOSED','generated_at_taipei':now_tw().isoformat(),'trade_date':trade,'binding_status':'DATA_PENDING','market_state':'DATA_PENDING','authority':'NO_FORMAL_SIGNAL','top3':[],'formal_buy_count':0,'reason':reason,'rejected_artifact':{'module':r.get('module'),'schema_version':r.get('schema_version'),'generated_at_taipei':r.get('generated_at_taipei'),'top3':tops},'policy':'NO_VALID_SCHEMA4_0901_PROVENANCE_NO_FORMAL_Q017_SIGNAL','required':{'provider_coverage':1.0,'binding_status':'PASS','capture_minute':'09:01','immutable':True,'rerank_after_lock':False,'gate':{'sox_1d_max':0.0,'sox_5d_max':-0.03,'dxy_5d_min':-0.005}},'repair_note':'Late, partial, wrong-date, non-binding, gate-drifted, or mathematically inconsistent Q017 output is zero authority.'}
def check_and_repair():
 if not LATEST.exists():print(json.dumps({'status':'PASS','latest':'ABSENT','authority':'NO_FORMAL_SIGNAL'}));return 0
 p=read_json(LATEST);ok,reason=validate(p)
 if ok:print(json.dumps({'status':'PASS','reason':reason,'module':p.get('module')},ensure_ascii=False));return 0
 q=quarantine_payload(p,reason);atomic_json(LATEST,q);print(json.dumps({'status':'REPAIRED_FAIL_CLOSED','reason':reason,'rejected_module':p.get('module'),'formal_buy_count':0},ensure_ascii=False));return 0
def self_test():
 assert FORMAL_SCHEMA_MIN==4 and MIN_PROVIDER_COVERAGE==1.0
 good={'schema_version':4,'module':'Q017_AUTHORITY_GUARD_FAIL_CLOSED','binding_status':'DATA_PENDING','market_state':'DATA_PENDING','authority':'NO_FORMAL_SIGNAL','formal_buy_count':0,'top3':[]};assert validate(good)[0]
 bad={'schema_version':1,'module':'Q017_SOX_ELECTRONICS_RADAR','binding_status':'PASS','market_state':'GO','top3':[]};assert validate(bad)==(False,'LEGACY_RADAR_MODULE_FORBIDDEN')
 bad3={'schema_version':3,'module':'Q017_SOX_ELECTRONICS_DECISION_LOCK','trade_date':'2026-10-19','top3':[]};assert validate(bad3)[1]=='FORMAL_Q017_REQUIRES_SCHEMA_V4'
 print(json.dumps({'self_test':'PASS','formal_schema_minimum':4,'provider_coverage_required':1.0,'provenance_hard_validation':True,'top3_math_validation':True,'fail_closed_buy_count':0}));return 0
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['check-and-repair','self-test'],required=True);a=ap.parse_args();return self_test() if a.mode=='self-test' else check_and_repair()
if __name__=='__main__':raise SystemExit(main())
