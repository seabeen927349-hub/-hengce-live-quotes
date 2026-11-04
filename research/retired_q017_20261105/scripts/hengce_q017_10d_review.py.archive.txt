#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, hashlib, json, math, tempfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo('Asia/Taipei')
ROOT=Path(__file__).resolve().parents[1]
DECISION_DIR=ROOT/'hengce'/'q017_radar'/'decision'
EOD_ROOT=ROOT/'eod'
OUT=ROOT/'hengce'/'q017_review_10d'
DAILY=OUT/'daily'
LEDGER=OUT/'ledger_latest.json'
LATEST=OUT/'review_latest.json'
HOLD_SESSIONS=10
AUTHORITY='PERFORMANCE_REVIEW_ONLY_NO_CAPITAL_AUTHORITY'


def now_tw(): return datetime.now(TZ)
def csha(o): return hashlib.sha256(json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    tmp.replace(path)
def fnum(x):
    try:
        if x is None or str(x).strip() in ('','--'): return None
        v=float(str(x).replace(',',''))
        return v if math.isfinite(v) else None
    except Exception:return None

def pct(x): return None if x is None else round(x,10)

def validate_decision(d):
    if int(d.get('schema_version') or 0)!=5:return False,'SCHEMA_NOT_V5'
    if d.get('module')!='Q017_SOX_ELECTRONICS_DECISION_LOCK':return False,'MODULE_INVALID'
    if d.get('binding_status')!='PASS':return False,'BINDING_NOT_PASS'
    h=d.get('decision_snapshot_sha256')
    if not h or h!=csha({k:v for k,v in d.items() if k!='decision_snapshot_sha256'}):return False,'DECISION_HASH_INVALID'
    if ((d.get('market_gate') or {}).get('gate_go')) is not True:return False,'GATE_NOT_GO'
    if ((d.get('decision_lock') or {}).get('authority_semantics'))!='OBSERVATION_TIME_LOCK':return False,'OBSERVATION_AUTHORITY_INVALID'
    top=d.get('top3') or []
    if not top:return False,'NO_TOP3'
    if any(x.get('qualified') is not True for x in top):return False,'TOP3_NOT_FORMALLY_QUALIFIED'
    return True,'FORMAL_Q017_SELECTION'

def formal_decisions(root=ROOT):
    dd=root/'hengce'/'q017_radar'/'decision';out=[]
    if not dd.exists():return out
    for p in sorted(dd.glob('*_0901.json')):
        try:d=json.loads(p.read_text(encoding='utf-8'))
        except Exception:continue
        ok,reason=validate_decision(d)
        if ok:out.append((p,d))
    return out

def eod_status(root,ds):
    p=root/'eod'/ds.replace('-','')/'status.json'
    if not p.exists():return None
    try:o=json.loads(p.read_text(encoding='utf-8'))
    except Exception:return None
    keys=('price','institutional','margin')
    if any(o.get(f'{k}_status')!='COMPLETE' for k in keys):return None
    if any(o.get(f'{k}_date')!=ds for k in keys):return None
    if o.get('target_date')!=ds:return None
    return o

def complete_eod_dates(root=ROOT):
    er=root/'eod';out=[]
    if not er.exists():return out
    for p in sorted(er.iterdir()):
        if not p.is_dir() or len(p.name)!=8 or not p.name.isdigit():continue
        ds=f'{p.name[:4]}-{p.name[4:6]}-{p.name[6:8]}'
        if eod_status(root,ds):out.append(ds)
    return out

def load_prices(root,ds):
    d=root/'eod'/ds.replace('-','');rows={}
    if not eod_status(root,ds):raise RuntimeError(f'EOD_NOT_COMPLETE:{ds}')
    for p in sorted(d.glob('price_*.csv')):
        with p.open('r',encoding='utf-8-sig',newline='') as f:
            for r in csv.DictReader(f):
                t=str(r.get('Ticker') or '').strip()
                if not t:continue
                rows[t]={'ticker':t,'name':str(r.get('Name') or '').strip(),'open':fnum(r.get('Open')),'high':fnum(r.get('High')),'low':fnum(r.get('Low')),'close':fnum(r.get('Close'))}
    return rows

def empty_ledger():
    return {'schema_version':1,'system':'HENGCE','module':'Q017_10D_SELECTION_REVIEW_LEDGER','authority':AUTHORITY,'hold_sessions_required':HOLD_SESSIONS,'cohort_key':'SIGNAL_DATE_X_TICKER','same_ticker_on_different_signal_dates_is_separate_cohort':True,'signal_day_is_D1':True,'hypothetical_reconstructions_forbidden':True,'cohorts':{},'ledger_sha256':None}

def load_ledger(root=ROOT):
    p=root/'hengce'/'q017_review_10d'/'ledger_latest.json'
    if not p.exists():return empty_ledger()
    o=json.loads(p.read_text(encoding='utf-8'));h=o.get('ledger_sha256')
    if not h or h!=csha({k:v for k,v in o.items() if k!='ledger_sha256'}):raise RuntimeError('REVIEW_LEDGER_HASH_INVALID')
    return o

def cohort_from_pick(d,x,rank):
    trade=d['trade_date'];t=str(x['ticker']);ref=fnum(x.get('open'))
    if ref is None or ref<=0:raise RuntimeError(f'FORMAL_PICK_REFERENCE_PRICE_INVALID:{trade}:{t}')
    return {'cohort_id':f'Q017-{trade.replace("-","")}-{t}','engine':'Q017','signal_date':trade,'ticker':t,'name':x.get('name') or '','rank':rank,'decision_snapshot_sha256':d['decision_snapshot_sha256'],'observation_snapshot_sha256':d.get('observation_snapshot_sha256'),'selection_reference_price':ref,'selection_reference_type':'Q017_DECISION_OPEN','beta':fnum(x.get('beta')),'residual':fnum(x.get('residual')),'score':fnum(x.get('score')),'hold_sessions_required':HOLD_SESSIONS,'status':'ACTIVE','sessions':[],'current_day':0,'final':None}

def seed_formal_cohorts(ledger,root=ROOT):
    created=[]
    for _,d in formal_decisions(root):
        for rank,x in enumerate(d.get('top3') or [],1):
            c=cohort_from_pick(d,x,rank);cid=c['cohort_id'];old=ledger['cohorts'].get(cid)
            if old is None:ledger['cohorts'][cid]=c;created.append(cid)
            else:
                immutable=('signal_date','ticker','rank','decision_snapshot_sha256','selection_reference_price')
                if any(old.get(k)!=c.get(k) for k in immutable):raise RuntimeError(f'COHORT_IMMUTABLE_CONFLICT:{cid}')
    return created

def append_session(c,ds,row):
    existing={x['date'] for x in c['sessions']}
    if ds in existing:return False
    day=len(c['sessions'])+1
    if day>HOLD_SESSIONS:return False
    ref=c['selection_reference_price']
    if row:
        hi=row.get('high');lo=row.get('low');cl=row.get('close')
        rec={'day':day,'date':ds,'price_status':'OBSERVED','open':row.get('open'),'high':hi,'low':lo,'close':cl,'close_return_from_selection':pct(cl/ref-1) if cl is not None else None,'session_high_return_from_selection':pct(hi/ref-1) if hi is not None else None,'session_low_return_from_selection':pct(lo/ref-1) if lo is not None else None}
    else:
        rec={'day':day,'date':ds,'price_status':'NO_PRICE_ROW','open':None,'high':None,'low':None,'close':None,'close_return_from_selection':None,'session_high_return_from_selection':None,'session_low_return_from_selection':None}
    c['sessions'].append(rec);c['current_day']=day
    obs=[x for x in c['sessions'] if x['price_status']=='OBSERVED']
    closes=[x['close'] for x in obs if x.get('close') is not None];highs=[x['high'] for x in obs if x.get('high') is not None];lows=[x['low'] for x in obs if x.get('low') is not None]
    c['mark_to_close_return']=pct(closes[-1]/ref-1) if closes else None
    c['mfe_to_date']=pct(max(highs)/ref-1) if highs else None
    c['mae_to_date']=pct(min(lows)/ref-1) if lows else None
    if day==HOLD_SESSIONS:
        d10=c['sessions'][-1];c['status']='CLOSED_D10' if d10['price_status']=='OBSERVED' and d10.get('close') is not None else 'CLOSED_D10_NO_D10_PRICE'
        c['final']={'closed_on':ds,'d10_close':d10.get('close'),'d10_return_from_selection':d10.get('close_return_from_selection'),'mfe_10d':c.get('mfe_to_date'),'mae_10d':c.get('mae_to_date'),'observed_price_sessions':len(obs),'missing_price_sessions':HOLD_SESSIONS-len(obs)}
    return True

def update_ledger(root=ROOT):
    ledger=load_ledger(root);created=seed_formal_cohorts(ledger,root);dates=complete_eod_dates(root)
    if not dates:raise RuntimeError('NO_COMPLETE_EOD_ARCHIVE')
    price_cache={};touched=[];closed=[]
    for cid,c in sorted(ledger['cohorts'].items()):
        if c.get('status','').startswith('CLOSED_D10'):continue
        eligible=[d for d in dates if d>=c['signal_date']]
        for ds in eligible:
            if len(c['sessions'])>=HOLD_SESSIONS:break
            price_cache.setdefault(ds,load_prices(root,ds));row=price_cache[ds].get(c['ticker'])
            if append_session(c,ds,row):touched.append(cid)
            if c.get('status','').startswith('CLOSED_D10'):closed.append(cid);break
    latest=dates[-1]
    active=[c for c in ledger['cohorts'].values() if c.get('status')=='ACTIVE']
    closed_today=[c for c in ledger['cohorts'].values() if c.get('final') and c['final'].get('closed_on')==latest]
    new_today=[c for c in ledger['cohorts'].values() if c['signal_date']==latest]
    ledger['generated_at_taipei']=now_tw().isoformat();ledger['latest_complete_eod_date']=latest;ledger['active_cohort_count']=len(active);ledger['closed_cohort_count']=sum(1 for c in ledger['cohorts'].values() if str(c.get('status','')).startswith('CLOSED_D10'));ledger['ledger_sha256']=csha({k:v for k,v in ledger.items() if k!='ledger_sha256'})
    report={'schema_version':1,'system':'HENGCE','module':'Q017_DAILY_10D_REVIEW','authority':AUTHORITY,'review_date':latest,'generated_at_taipei':now_tw().isoformat(),'new_formal_selection_cohorts_today':[x['cohort_id'] for x in new_today],'active_cohorts':[summary(x) for x in sorted(active,key=lambda z:(z['signal_date'],z['rank'],z['ticker']))],'closed_d10_today':[summary(x) for x in sorted(closed_today,key=lambda z:(z['signal_date'],z['rank'],z['ticker']))],'all_active_continue_even_if_next_day_top3_changes':True,'same_ticker_reselected_creates_new_independent_cohort':True,'hypothetical_receipts_included':False,'ledger_sha256':ledger['ledger_sha256']}
    out=root/'hengce'/'q017_review_10d';atomic_json(out/'ledger_latest.json',ledger);atomic_json(out/'review_latest.json',report);atomic_json(out/'daily'/f'{latest.replace("-","")}_review.json',report);write_md(out/'daily'/f'{latest.replace("-","")}_review.md',report)
    return report,ledger,created,touched,closed

def summary(c):
    return {'cohort_id':c['cohort_id'],'signal_date':c['signal_date'],'ticker':c['ticker'],'name':c['name'],'rank':c['rank'],'day':c.get('current_day',0),'status':c['status'],'selection_reference_price':c['selection_reference_price'],'mark_to_close_return':c.get('mark_to_close_return'),'mfe_to_date':c.get('mfe_to_date'),'mae_to_date':c.get('mae_to_date'),'final':c.get('final')}

def write_md(path,report):
    path.parent.mkdir(parents=True,exist_ok=True)
    lines=[f"# HENGCE Q017 10D Review — {report['review_date']}",'',f"Authority: `{AUTHORITY}`",'',f"Active cohorts: **{len(report['active_cohorts'])}**  ",f"D10 closed today: **{len(report['closed_d10_today'])}**",'',"| Signal | D | Ticker | Name | Rank | Ref | Close return | MFE | MAE | Status |","|---|---:|---|---|---:|---:|---:|---:|---:|---|"]
    def fp(v):return '—' if v is None else f'{v*100:.2f}%'
    for x in report['active_cohorts']+report['closed_d10_today']:
        lines.append(f"| {x['signal_date']} | {x['day']} | {x['ticker']} | {x['name']} | {x['rank']} | {x['selection_reference_price']} | {fp(x['mark_to_close_return'])} | {fp(x['mfe_to_date'])} | {fp(x['mae_to_date'])} | {x['status']} |")
    lines+=['', '> Every signal-date × ticker is an independent cohort. New daily Top3 never deletes an older active cohort. D1 is the signal-date close; D10 is the tenth complete market-session close including the signal date. Hypothetical reconstructions never enter this ledger.','']
    path.write_text('\n'.join(lines),encoding='utf-8')

def self_test():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);(root/'hengce/q017_radar/decision').mkdir(parents=True);(root/'eod').mkdir()
        def mkdec(ds,ticker,op):
            d={'schema_version':5,'module':'Q017_SOX_ELECTRONICS_DECISION_LOCK','trade_date':ds,'binding_status':'PASS','decision_lock':{'authority_semantics':'OBSERVATION_TIME_LOCK'},'market_gate':{'gate_go':True},'observation_snapshot_sha256':'obs'+ds,'top3':[{'ticker':ticker,'name':'TEST','rank':1,'open':op,'beta':1.2,'residual':-0.02,'score':1.8,'qualified':True}]};d['decision_snapshot_sha256']=csha(d);return d
        atomic_json(root/'hengce/q017_radar/decision/20261020_0901.json',mkdec('2026-10-20','1111',100))
        atomic_json(root/'hengce/q017_radar/decision/20261021_0901.json',mkdec('2026-10-21','1111',110))
        for i in range(10):
            ds=f'2026-10-{20+i:02d}';dd=root/'eod'/ds.replace('-','');dd.mkdir(parents=True)
            st={'target_date':ds,'price_status':'COMPLETE','price_date':ds,'institutional_status':'COMPLETE','institutional_date':ds,'margin_status':'COMPLETE','margin_date':ds};atomic_json(dd/'status.json',st)
            (dd/'price_1.csv').write_text('Date,Ticker,Name,Open,High,Low,Close\n'+f'{ds},1111,TEST,100,{101+i},{99-i},{100+i}\n',encoding='utf-8')
        report,ledger,created,_,closed=update_ledger(root)
        a=ledger['cohorts']['Q017-20261020-1111'];b=ledger['cohorts']['Q017-20261021-1111']
        assert a['status']=='CLOSED_D10' and a['current_day']==10
        assert b['status']=='ACTIVE' and b['current_day']==9
        assert len(created)==2 and len(ledger['cohorts'])==2
        assert a['selection_reference_price']==100 and b['selection_reference_price']==110
        assert report['hypothetical_receipts_included'] is False
    print('PASS Q017_10D_OVERLAPPING_COHORT_REVIEW_SELF_TEST')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['update','self-test'],default='update');a=ap.parse_args()
    if a.mode=='self-test':self_test();return
    report,ledger,created,touched,closed=update_ledger();print(json.dumps({'status':'PASS','review_date':report['review_date'],'new_cohorts':len(created),'touched':len(set(touched)),'closed_d10':len(set(closed)),'active':ledger['active_cohort_count'],'authority':AUTHORITY},ensure_ascii=False))
if __name__=='__main__':main()
