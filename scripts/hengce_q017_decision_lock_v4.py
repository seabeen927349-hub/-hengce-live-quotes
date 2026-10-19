#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time as dtime
from pathlib import Path
import hengce_q017_decision_lock as legacy

core=legacy.core; TZ=legacy.TZ; ROOT=legacy.ROOT; RADAR=legacy.RADAR; HISTORY=legacy.HISTORY; LATEST=legacy.LATEST; SIGNAL_LEDGER=legacy.SIGNAL_LEDGER
DECISION_DIR=RADAR/'decision'; DECISION_LATEST=RADAR/'decision_latest.json'; ATTEMPT_DIR=RADAR/'decision_attempts'; ATTEMPT_LATEST=RADAR/'decision_attempt_latest.json'
DECISION_HOUR=9; DECISION_MINUTE=1; DECISION_SECOND=5; MIN_PROVIDER_COVERAGE=1.0; CRITICAL_BETA_TOP_N=50; BATCH_SIZE=40; WORKERS=10; RETRY_SLEEP_SECONDS=1.0
SOX_1D_MAX=0.0; SOX_5D_MAX=-0.03; DXY_5D_MIN=-0.005
canonical_sha=legacy.canonical_sha; fnum=legacy.fnum; mis_batch=legacy.mis_batch; refresh_dxy=legacy.refresh_dxy; current_marks=legacy.current_marks
DECISION_DIR.mkdir(parents=True,exist_ok=True); ATTEMPT_DIR.mkdir(parents=True,exist_ok=True)

def decision_path(today): return DECISION_DIR/f'{today.strftime("%Y%m%d")}_0901.json'
def chunks(xs,n):
    for i in range(0,len(xs),n): yield xs[i:i+n]
def evaluate_market_gate(sf,dxy):
    c={'sox_1d_lte_0':sf['sox_1d']<=SOX_1D_MAX,'sox_5d_lte_minus_3pct':sf['sox_5d']<=SOX_5D_MAX,'dxy_5d_gte_minus_0_5pct':dxy['dxy_5d']>=DXY_5D_MIN}; return all(c.values()),c
def market_state_from_checks(c):
    n=sum(bool(v) for v in c.values()); return 'GO' if n==len(c) else 'WATCH' if n else 'CASH'
def wait_for_decision_minute(today):
    now=core.now_tw(); target=datetime.combine(today,dtime(9,1,5),tzinfo=TZ); end=datetime.combine(today,dtime(9,1,59,999999),tzinfo=TZ)
    if today!=now.date(): raise RuntimeError('DECISION_CAPTURE_ONLY_ALLOWED_FOR_CURRENT_TRADE_DATE')
    if now>end: raise RuntimeError(f'DECISION_WINDOW_MISSED:{now.isoformat()}')
    if now<target: time.sleep((target-now).total_seconds())
    return target,end

def validate_premarket_coherence(today,gate,hist_date):
    req=gate.get('required') or {}; hist=str(hist_date or req.get('electronics_history_latest') or '')
    if len(hist)!=10: raise RuntimeError('ELECTRONICS_HISTORY_DATE_MISSING')
    hd=datetime.strptime(hist,'%Y-%m-%d').date()
    if hd>=today: raise RuntimeError(f'ELECTRONICS_HISTORY_NOT_CAUSAL:{hist}')
    eod=str(req.get('latest_eod_date') or '')
    if eod:
        ed=datetime.strptime(eod,'%Y%m%d').date() if len(eod)==8 else datetime.strptime(eod,'%Y-%m-%d').date()
        if ed>=today: raise RuntimeError(f'EOD_DATE_NOT_CAUSAL:{eod}')
        if hd<ed: raise RuntimeError(f'ELECTRONICS_HISTORY_BEHIND_COMPLETE_EOD:HIST={hist}:EOD={eod}')
    return {'status':'PASS','trade_date':today.isoformat(),'electronics_history_latest':hist,'latest_complete_eod_date':eod or None,'rule':'sources causal; electronics history cannot lag known complete EOD'}
def prepare_model(today):
    gate=core.premarket(today)
    if gate.get('status')!='PASS': raise RuntimeError(f'PREMARKET_GATE_NOT_PASS:{gate.get("status")}')
    req=gate.get('required') or {}; seed=req.get('electronics_history') or core.ensure_tw_history(); sox=req.get('sox') or core.refresh_sox(today); dxy=refresh_dxy(today)
    hist=core.load_tw_history(); srows=core.read_sox(); sf=core.sox_features(today); betas,prev,names,hist_date,universe=core.current_betas(hist,srows); coh=validate_premarket_coherence(today,gate,hist_date)
    return gate,sox,dxy,seed,sf,betas,prev,names,hist_date,universe,coh
def previous_top3(p):
    fs=sorted(x for x in DECISION_DIR.glob('*_0901.json') if x!=p)
    if not fs:return []
    try:return [str(x['ticker']) for x in json.loads(fs[-1].read_text()).get('top3',[])]
    except:return []
def critical_set(eligible,betas,prev_top): return sorted(set(sorted(eligible,key=lambda t:(-(betas.get(t) or 0),t))[:CRITICAL_BETA_TOP_N]).union(prev_top))
def capture_provider_attempt(eligible):
    started=core.now_tw(); rec={}; fail=[]; wins=[]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        fut={ex.submit(mis_batch,b):b for b in chunks(eligible,BATCH_SIZE)}
        for f in as_completed(fut):
            try:r,s,e=f.result();rec.update(r);wins.append((s,e))
            except Exception as x:fail.append({'tickers':fut[f],'error':f'{type(x).__name__}:{x}'})
    return rec,fail,wins,started,core.now_tw()
def attempt_valid(today,eligible,rec,wins,s,e,end,crit):
    iw=s.date()==today and s.hour==9 and s.minute==1 and e.date()==today and e<=end and bool(wins) and all(a.date()==today and a.hour==9 and a.minute==1 and b.date()==today and b<=end for a,b in wins)
    cov=len(rec)/len(eligible) if eligible else 0.0; miss=[t for t in crit if t not in rec]; return iw and cov>=1.0 and not miss,iw,cov,miss
def write_once(path,obj):
    text=json.dumps(obj,ensure_ascii=False,indent=2)+'\n'
    try:path.open('x',encoding='utf-8').write(text);return obj,True
    except FileExistsError:
        old=json.loads(path.read_text());
        if canonical_sha(old)!=canonical_sha(obj):raise RuntimeError(f'IMMUTABLE_DECISION_CONFLICT:{path}')
        return old,False
def validate_existing(d,today):
    if d.get('schema_version')!=4 or d.get('binding_status')!='PASS' or d.get('trade_date')!=today.isoformat():raise RuntimeError('EXISTING_DECISION_SCHEMA_BINDING_DATE_INVALID')
    dl=d.get('decision_lock') or {}; ds=d.get('data_status') or {}
    if dl.get('window_valid') is not True or dl.get('immutable') is not True or dl.get('rerank_after_lock') is not False:raise RuntimeError('EXISTING_DECISION_PROVENANCE_INVALID')
    if float(ds.get('provider_coverage') or 0)<1.0 or ds.get('critical_set_complete') is not True:raise RuntimeError('EXISTING_DECISION_COVERAGE_INVALID')
    if d.get('decision_snapshot_sha256')!=canonical_sha({k:v for k,v in d.items() if k!='decision_snapshot_sha256'}):raise RuntimeError('EXISTING_DECISION_HASH_INVALID')
def fail_closed(today,attempts,reason):
    p={'schema_version':4,'system':'HENGCE','module':'Q017_DECISION_ATTEMPT_FAIL_CLOSED','trade_date':today.isoformat(),'generated_at_taipei':core.now_tw().isoformat(),'binding_status':'DATA_PENDING','market_state':'DATA_PENDING','authority':'NO_FORMAL_SIGNAL','formal_buy_count':0,'top3':[],'reason':reason,'attempts':attempts,'policy':'NO_SCHEMA4_PASS_0901_SNAPSHOT_NO_FORMAL_Q017_SIGNAL'};core.atomic_json(ATTEMPT_LATEST,p);core.atomic_json(LATEST,p);return p

def capture_decision(today=None):
    today=today or core.now_tw().date(); p=decision_path(today)
    if p.exists():
        d=json.loads(p.read_text());validate_existing(d,today);core.atomic_json(DECISION_LATEST,d);core.atomic_json(LATEST,d);return d
    gate,sox,dxy,seed,sf,betas,prev,names,hist_date,universe,coh=prepare_model(today); eligible=[str(t) for t in universe if betas.get(t) is not None and betas.get(t)>0 and prev.get(t)]
    if not eligible:raise RuntimeError('NO_ELIGIBLE_BETA_UNIVERSE')
    _,end=wait_for_decision_minute(today); prev_top=previous_top3(p); crit=critical_set(eligible,betas,prev_top); attempts=[]; accepted=None;n=0
    while core.now_tw()<=end:
        n+=1;rec,fail,wins,s,e=capture_provider_attempt(eligible);ok,iw,cov,miss=attempt_valid(today,eligible,rec,wins,s,e,end,crit);sm={'attempt':n,'started_at_taipei':s.isoformat(),'finished_at_taipei':e.isoformat(),'window_valid':iw,'provider_returned_count':len(rec),'eligible_beta_count':len(eligible),'provider_coverage':cov,'critical_missing':miss,'batch_failure_count':len(fail)};attempts.append(sm);core.atomic_json(ATTEMPT_DIR/f'{today.strftime("%Y%m%d")}_0901_attempt_{n:02d}.json',sm);core.atomic_json(ATTEMPT_LATEST,sm)
        if ok:accepted=(rec,fail,s,e,cov);break
        if e>=end:break
        time.sleep(min(RETRY_SLEEP_SECONDS,max(0,(end-core.now_tw()).total_seconds())))
    if accepted is None:fail_closed(today,attempts,'DECISION_WINDOW_EXHAUSTED_WITHOUT_100PCT_PROVIDER_COVERAGE_AND_CRITICAL_COMPLETENESS');raise RuntimeError('DECISION_LOCK_DATA_PENDING_NO_VALID_ATTEMPT')
    rec,fail,s,e,cov=accepted;go,checks=evaluate_market_gate(sf,dxy);state=market_state_from_checks(checks);cand=[];opened=0
    for t in eligible:
        q=rec[t];op=q.get('open');pc=q.get('reference_close') or prev[t]
        if op is None or pc in (None,0):continue
        opened+=1;b=betas[t];gap=op/pc-1;exp=b*sf['sox_1d'];res=gap-exp
        if res>0.04:continue
        score=b*(1+25*max(-res,0));cand.append({'ticker':t,'name':q.get('name') or names.get(t,''),'beta':b,'open':op,'previous_close':pc,'gap':gap,'expected_gap':exp,'residual':res,'score':score,'qualified':go,'decision_observed_at_taipei':q.get('fetched_at_taipei')})
    cand.sort(key=lambda x:x['score'],reverse=True);top=cand[:3];cur=[x['ticker'] for x in top]
    for x in top:x['new']=x['ticker'] not in prev_top
    out={'schema_version':4,'system':'HENGCE','module':'Q017_SOX_ELECTRONICS_DECISION_LOCK','trade_date':today.isoformat(),'generated_at_taipei':e.isoformat(),'binding_status':'PASS','market_state':state,'authority':'FORMAL_Q017_DECISION_INPUT_NOT_BROKER_ORDER','decision_lock':{'cutoff_label':'09:01','capture_window_taipei':'09:01:00-09:01:59.999999','capture_started_at_taipei':s.isoformat(),'capture_finished_at_taipei':e.isoformat(),'window_valid':True,'immutable':True,'rerank_after_lock':False,'attempt_count':n,'accepted_attempt':n,'retry_policy':'same 09:01 minute only; never backfill later','observable_rule':'open must be present in a returned row inside accepted attempt','missing_open_semantics':'NOT_OPENED_BY_DECISION_CUTOFF_NOT_DATA_FAILURE'},'data_status':{'premarket_gate':gate,'premarket_coherence':coh,'sox':sox,'dxy':dxy,'tw_history':seed,'tw_history_latest_date':hist_date,'eligible_beta_count':len(eligible),'provider_returned_count':len(rec),'provider_coverage':cov,'provider_coverage_required':1.0,'opened_by_decision_count':opened,'critical_set_rule':'top 50 positive Beta60 plus previous locked Top3','critical_set_count':len(crit),'critical_set_complete':True,'critical_missing':[],'batch_failures':fail[:20],'attempts':attempts},'market_gate':{'gate_go':go,'checks':checks,'sox_1d':sf['sox_1d'],'sox_5d':sf['sox_5d'],'dxy_5d':dxy['dxy_5d'],'source_lock':'Q017_LOCK_20261018.json'},'sox':sf,'dxy':{'session':dxy['latest_session'],'five_sessions_back':dxy['five_sessions_back'],'dxy_5d':dxy['dxy_5d']},'rules':{'sox_1d_max':0.0,'sox_5d_max':-0.03,'dxy_5d_min':-0.005,'residual_max':0.04,'score':'beta*(1+25*max(-residual,0))','top_n':3,'research_hold_days':10,'authority':'Q017_LOCK_20261018.json'},'top3':top,'new':[x['ticker'] for x in top if x.get('new')],'dropped':[t for t in prev_top if t not in cur],'note':'Schema-v4: immutable only after accepted 09:01 attempt with 100% eligible provider coverage; later monitors cannot rerank.'};out['decision_snapshot_sha256']=canonical_sha({k:v for k,v in out.items() if k!='decision_snapshot_sha256'});stored,created=write_once(p,out);core.atomic_json(DECISION_LATEST,stored);core.atomic_json(LATEST,stored)
    if created:
        core.atomic_json(HISTORY/f'{e.strftime("%Y%m%dT%H%M%S")}_DECISION_LOCK.json',stored)
        with SIGNAL_LEDGER.open('a',encoding='utf-8') as f:f.write(json.dumps({'time':stored['generated_at_taipei'],'date':stored['trade_date'],'event':'Q017_DECISION_LOCK_V4','market_state':state,'gate_go':go,'top3':cur,'decision_snapshot_sha256':stored['decision_snapshot_sha256']},ensure_ascii=False)+'\n')
    return stored

def monitor(today=None):
    today=today or core.now_tw().date();p=decision_path(today)
    if not p.exists():
        x={'schema_version':4,'system':'HENGCE','module':'Q017_SOX_ELECTRONICS_RADAR_LOCKED','trade_date':today.isoformat(),'generated_at_taipei':core.now_tw().isoformat(),'binding_status':'DATA_PENDING','market_state':'DATA_PENDING','authority':'NO_FORMAL_SIGNAL','formal_buy_count':0,'top3':[],'monitor':{'status':'NO_DECISION_SNAPSHOT','rerank_performed':False,'ranking_frozen':True},'policy':'NO_SCHEMA4_0901_DECISION_LOCK_NO_FORMAL_SIGNAL'};core.atomic_json(LATEST,x);raise RuntimeError('NO_IMMUTABLE_0901_DECISION_SNAPSHOT')
    d=json.loads(p.read_text());validate_existing(d,today);x=dict(d);x['module']='Q017_SOX_ELECTRONICS_RADAR_LOCKED';x['generated_at_taipei']=core.now_tw().isoformat();x['decision_source_file']=str(p.relative_to(ROOT));x['monitor']={'status':'PASS','rerank_performed':False,'ranking_frozen':True,'marks':current_marks(d.get('top3',[]))};core.atomic_json(LATEST,x);core.atomic_json(HISTORY/f'{core.now_tw().strftime("%Y%m%dT%H%M%S")}_MONITOR.json',x);return x
def self_test():
    assert MIN_PROVIDER_COVERAGE==1.0 and SOX_5D_MAX==-0.03 and DXY_5D_MIN==-0.005
    g,c=evaluate_market_gate({'sox_1d':-0.01,'sox_5d':-0.03},{'dxy_5d':-0.004});assert g and all(c.values())
    assert not evaluate_market_gate({'sox_1d':-0.01,'sox_5d':-0.025},{'dxy_5d':-0.004})[0]
    print(json.dumps({'self_test':'PASS','schema':4,'provider_coverage_required':1.0,'same_minute_retry':True,'provenance':'09:01 only','rerank_after_lock':False}))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['decision','monitor','self-test','dxy-smoke'],required=True);ap.add_argument('--date');a=ap.parse_args();target=datetime.strptime(a.date,'%Y-%m-%d').date() if a.date else None
    if a.mode=='self-test':self_test();return 0
    if a.mode=='dxy-smoke':
        try:print(json.dumps(refresh_dxy(target),ensure_ascii=False,indent=2));return 0
        except Exception as e:print(json.dumps({'status':'DATA_PENDING','authority':'NO_FORMAL_SIGNAL','error':repr(e)},ensure_ascii=False));return 2
    try:print(json.dumps(capture_decision(target) if a.mode=='decision' else monitor(target),ensure_ascii=False,indent=2));return 0
    except Exception as e:
        fail={'system':'HENGCE','module':'Q017_DECISION_LOCK_V4','mode':a.mode,'generated_at_taipei':core.now_tw().isoformat(),'status':'DATA_PENDING','authority':'NO_FORMAL_SIGNAL','formal_buy_count':0,'error':repr(e),'policy':'FAIL_CLOSED_NO_FORMAL_SIGNAL'};core.atomic_json(core.DATA_STATUS,fail);print(json.dumps(fail,ensure_ascii=False,indent=2));return 2
if __name__=='__main__':raise SystemExit(main())
