#!/usr/bin/env python3
"""Zero-authority operational admission/evidence. No model computation or push.

Git trees provide isolated immutable snapshots. Publication remains exclusively
in hengce_publish.py; this module cannot repair a producer artifact.
"""
import argparse
from collections.abc import Mapping
import csv
from datetime import datetime, time
import fnmatch
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid
from zoneinfo import ZoneInfo

TZ=ZoneInfo('Asia/Taipei')
ZERO=dict(signal_authority=False,ranking_authority=False,capital_authority_twd=0,broker_order_execution=False)
LANES={'q017-primary':{'observe','self-test'},'q017-backup':{'observe','self-test'},
 'q017-recovery':{'compute','self-test'},'daily':{'premarket','e2-morning','decision','compute','monitor','postclose','self-test'},
 'e2-morning':{'morning','self-test'},'e2-postclose':{'postclose','self-test'},
 'macro':{'refresh','validate','self-test'},'display':{'refresh','self-test'},
 'eod':{'postclose','self-test'},'review':{'postclose','self-test'}}
STATES={'OBSERVED','INPUTS_VALIDATED','STAGED_COMPLETE','COMMITTED','REMOTE_ACCEPTED','LOCAL_ADOPTED','BLOCKED'}
TRANSITIONS={'OBSERVED':{'INPUTS_VALIDATED','BLOCKED'},'INPUTS_VALIDATED':{'STAGED_COMPLETE','BLOCKED'},
 'STAGED_COMPLETE':{'COMMITTED','BLOCKED'},'COMMITTED':{'REMOTE_ACCEPTED','BLOCKED'},
 'REMOTE_ACCEPTED':{'LOCAL_ADOPTED','BLOCKED'},'LOCAL_ADOPTED':{'BLOCKED'},'BLOCKED':set()}
Q='hengce/q017_radar/';E='hengce/e2_live/';D='hengce/dual_engine/latest.json'
HISTORY=Q+'data/twse_electronics_history_2026.csv'
WRITES={
 'q017-primary':(Q+'observations/**',Q+'observation_latest.json',Q+'history/**',Q+'decision/**',Q+'decision_latest.json',
    Q+'latest.json',Q+'signal_ledger.jsonl',Q+'decision_attempts/**',Q+'decision_attempt_latest.json',Q+'observer_supervisor*',D),
 'q017-backup':(Q+'backup_observations/**',Q+'backup_observation*',Q+'observer_supervisor*'),
 'q017-recovery':(Q+'observations/**',Q+'observation_latest.json',Q+'decision/**',Q+'decision_latest.json',Q+'latest.json',Q+'history/**',Q+'signal_ledger.jsonl',Q+'recovery_receipts/**'),
 'daily':(Q+'**','hengce/q017_review_10d/**',E+'**','eod/**'),
 'e2-morning':(E+'**',D),
 'e2-postclose':(E+'**',D,HISTORY,Q+'data/sox_2026.csv',Q+'data/sox_status.json',Q+'data/data_status.json'),
 'macro':(Q+'data/sox_2026.csv',Q+'data/sox_status.json',Q+'data/dxy_2026.csv',Q+'data/dxy_status.json',Q+'data/macro_cache/**'),
 'display':(D,), 'eod':('eod/**',), 'review':('hengce/q017_review_10d/**',)}
EOD_MIN={'price':900,'institutional':900,'margin':500}
# Exact original-vessel schema/minimums, not model thresholds. Tests pin these
# against the authoritative ingest constants; no schema/expectation is tuned.
EOD_COLUMNS={'price': ['Date', 'Ticker', 'Name', 'VolumeShares', 'Trades', 'TurnoverTWD', 'Open', 'High', 'Low', 'Close', 'ChangeSign', 'Change', 'LastBid', 'LastBidVolume', 'LastAsk', 'LastAskVolume', 'PE', 'Source'], 'institutional': ['Date', 'Ticker', 'Name', 'ForeignBuy', 'ForeignSell', 'ForeignNet', 'ForeignDealerBuy', 'ForeignDealerSell', 'ForeignDealerNet', 'TrustBuy', 'TrustSell', 'TrustNet', 'DealerNet', 'DealerProprietaryBuy', 'DealerProprietarySell', 'DealerProprietaryNet', 'DealerHedgeBuy', 'DealerHedgeSell', 'DealerHedgeNet', 'TotalNet', 'Source'], 'margin': ['Date', 'Ticker', 'Name', 'MarginBuy', 'MarginSell', 'MarginCashRepayment', 'MarginPreviousBalance', 'MarginBalance', 'MarginNextDayLimit', 'ShortBuy', 'ShortSell', 'ShortStockRepayment', 'ShortPreviousBalance', 'ShortBalance', 'ShortNextDayLimit', 'Offset', 'Note', 'Source']}
KEYS={'schema_version','transaction_id','workflow','run_id','run_attempt','lane','mode','trade_date','state',
 'generated_at_taipei','original_base_sha','authoritative_input_hashes','proposal_write_hashes','immutable_write_set',
 'accepted_remote_sha','local_adoption','publication_intent','staged_tree_sha','proposal_sha',
 'evidence_completeness','observed_states','reason_codes','report_dir','read_dependency_contract',*ZERO}


class Blocked(RuntimeError): pass


def need(ok,reason):
    if not ok:raise Blocked(reason)


def clock(now=None):
    value=now or datetime.now(TZ)
    if isinstance(value,str):value=datetime.fromisoformat(value)
    need(value.tzinfo is not None,'NAIVE_OPERATIONAL_CLOCK')
    return value.astimezone(TZ)


def digest(o):
    return hashlib.sha256(json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def git(repo,*args):
    p=subprocess.run(['git','-C',str(repo),*args],capture_output=True,timeout=60)
    need(p.returncode==0,'GIT_OPERATION_FAILED:'+args[0])
    return p.stdout


class Snapshot(Mapping):
    def __init__(self,repo,ref):
        self.repo=repo;self.ref=ref;self.entries={};self.cache={}
        for row in git(repo,'ls-tree','-rz',ref).split(b'\0'):
            if row:
                meta,path=row.split(b'\t',1);self.entries[path.decode()]=tuple(meta.decode().split())
    def __iter__(self):return iter(self.entries)
    def __len__(self):return len(self.entries)
    def __getitem__(self,path):
        mode,kind,blob=self.entries[path];need(mode=='100644' and kind=='blob','NON_REGULAR_ARTIFACT:'+path)
        if path not in self.cache:self.cache[path]=git(self.repo,'cat-file','blob',blob)
        return self.cache[path]


def text(files,path):
    need(path in files,'REQUIRED_ARTIFACT_MISSING:'+path)
    value=files[path]
    return value.decode('utf-8-sig') if isinstance(value,bytes) else value


def obj(files,path):
    try:
        value=json.loads(text(files,path),parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
        need(isinstance(value,dict),'ARTIFACT_NOT_OBJECT:'+path);return value
    except (ValueError,UnicodeError,TypeError) as exc:raise Blocked('MALFORMED_ARTIFACT:'+path) from exc


def same_hash(o,key):
    need(o.get(key)==digest({k:v for k,v in o.items() if k!=key}),'ARTIFACT_HASH_MISMATCH:'+key)


def observed(o,day):
    need(o.get('schema_version')==5 and o.get('module')=='Q017_0901_OBSERVATION_LOCK' and
         o.get('trade_date')==day and o.get('binding_status')=='PASS','Q017_OBSERVATION_SCHEMA_DATE_BINDING')
    same_hash(o,'observation_snapshot_sha256');lock=o['observation_lock']
    need(lock.get('immutable') is True and lock.get('window_valid') is True and lock.get('cutoff_label')=='09:01','Q017_IMMUTABLE_WINDOW_FLAGS')
    times=[clock(lock[k]) for k in ('capture_started_at_taipei','capture_finished_at_taipei')]
    times += [clock(q['fetched_at_taipei']) for q in o['quotes'].values()]
    need(bool(o['quotes']) and all(x.date().isoformat()==day and (x.hour,x.minute)==(9,1) for x in times) and times[0]<=times[1],'Q017_CLOSED_WINDOW_NO_REFETCH_RECONSTRUCT_OR_BLEND')
    u=o['universe_lock'];members=u['members']
    need(u.get('scope')=='TWSE_LISTED_ELECTRONICS_ONLY' and u.get('source')=='TWSE_MI_INDEX_TYPE_13_ELECTRONICS_HISTORY' and
         u.get('membership_date','')<day and len(set(members))==len(members)==u.get('member_count') and
         u.get('universe_sha256')==digest(sorted(str(x) for x in members)),'Q017_UNIVERSE_BINDING_INVALID')


def history_contains(files,prefix,o,day):
    compact=day.replace('-','')
    return any(obj(files,p)==o for p in files if p.startswith(prefix) and p.endswith('.json') and
               (compact in Path(p).name or 'synthetic' in Path(p).name))


def qclosure(files,day,decision=False,backup=False):
    compact=day.replace('-','');folder='backup_observations/' if backup else 'observations/'
    alias='backup_observation_latest.json' if backup else 'observation_latest.json'
    o=obj(files,Q+folder+compact+'_0901_observation.json');observed(o,day)
    need(obj(files,Q+alias)==o,'Q017_CANONICAL_ALIAS_MISMATCH')
    hp=Q+('backup_observation_history/' if backup else 'history/')
    evidence=history_contains(files,hp,o,day)
    if not backup:
        evidence=evidence or history_contains(files,Q+'backup_observation_history/',o,day)
    need(evidence,'NEEDS_RECONCILIATION:OBSERVATION_HISTORY_UNKNOWN')
    if backup:
        need(obj(files,Q+'backup_observation_status.json').get('observation_snapshot_sha256')==o['observation_snapshot_sha256'],'BACKUP_STATUS_BINDING')
    if decision:
        d=obj(files,Q+'decision/'+compact+'_0901.json');same_hash(d,'decision_snapshot_sha256')
        need(d.get('schema_version')==5 and d.get('module')=='Q017_SOX_ELECTRONICS_DECISION_LOCK' and
             d.get('trade_date')==day and d.get('binding_status')=='PASS' and
             d.get('observation_snapshot_sha256')==o['observation_snapshot_sha256'],'Q017_DECISION_BINDING')
        need(obj(files,Q+'decision_latest.json')==d,'Q017_DECISION_ALIAS_MISMATCH')
        latest=obj(files,Q+'latest.json')
        need(all(latest.get(k)==v for k,v in d.items() if k not in ('module','generated_at_taipei','monitor')),'Q017_LATEST_CANONICAL_MISMATCH')
        need(history_contains(files,Q+'history/',d,day),'NEEDS_RECONCILIATION:DECISION_HISTORY_UNKNOWN')
        events=[json.loads(line) for line in text(files,Q+'signal_ledger.jsonl').splitlines() if line.strip()]
        events=[x for x in events if x.get('event')=='Q017_DECISION_FROM_0901_OBSERVATION_V5' and x.get('date')==day]
        need(len(events)==1 and events[0].get('decision_snapshot_sha256')==d['decision_snapshot_sha256'] and
             events[0].get('observation_snapshot_sha256')==o['observation_snapshot_sha256'],'NEEDS_RECONCILIATION:LEDGER_MISSING_DUPLICATE_OR_DIFFERENT')


def estate(files,day=None):
    s=obj(files,E+'state_latest.json')
    need(s.get('module')=='E2_PROFIT_MAX_STATE' and s.get('schema_version')==2 and s.get('binding_status')=='PASS','E2_STATE_LINEAGE_UNPROVEN_NO_RESET')
    need(type(s.get('capital_authority_twd')) is int and s['capital_authority_twd']==0 and s.get('broker_order_execution') is False,'E2_AUTHORITY_INVALID')
    need(isinstance(s.get('paper_position'),dict) and s['paper_position'].get('state') in ('IDLE','ENTRY_PENDING','HOLDING','EXITED','NO_FILL'),'E2_POSITION_UNPROVEN_NO_RESET')
    if E+'execution_override.json' in files:
        ov=obj(files,E+'execution_override.json')
        need(not ov or ov.get('version')==1 and ov.get('status')=='NO_FILL' and all(ov.get(k) for k in ('ticker','signal_date','effective_date')),'E2_OVERRIDE_SCHEMA_UNPROVEN')
        pos=s['paper_position']
        if ov and pos['state'] in ('ENTRY_PENDING','HOLDING') and (day is None or ov['effective_date'][:10]<=day):
            need(str(ov['ticker'])==str(pos.get('ticker')) and ov['signal_date']==pos.get('signal_date'),'E2_OVERRIDE_POSITION_MISMATCH')
    return s


def display(files,day):
    d=obj(files,D)
    need(d.get('architecture')=='DUAL_ENGINE' and d.get('rankings_separate') is True and
         d.get('mixed_ranking_forbidden') is True and d.get('legacy_v3_display_authority') is False,'DISPLAY_AUTHORITY_ISOLATION')
    s=estate(files,day);view=d['e2']
    need(view.get('signal_asof')==s.get('signal_asof') and view.get('paper_position')==s['paper_position'] and
         view.get('status')==s.get('engine_status') and view.get('capital_authority_twd')==0 and view.get('broker_order_execution') is False,'DISPLAY_E2_SOURCE_LINEAGE')
    q=d.get('q017',{})
    if q.get('formal_authority') is True or q.get('formal_buy_count',0):qclosure(files,day,decision=True)
    return d


def eclosure(files,day,mode,now,require_display=True):
    s=estate(files,day);d=display(files,day) if require_display else None
    if mode in ('morning','e2-morning','decision','compute','monitor'):
        m=obj(files,E+'morning_latest.json')
        need(m.get('module')=='E2_PROFIT_MAX_MORNING_BRIDGE' and m.get('trade_date')==day and m.get('binding_status')=='PASS' and
             m.get('capital_authority_twd')==0 and m.get('broker_order_execution') is False,'E2_MORNING_HEADER_AUTHORITY')
        need(m.get('paper_position')==s['paper_position'] and m.get('source_signal_asof')==s.get('signal_asof'),'E2_PARTIAL_STATE_MORNING_LINEAGE')
        generated=clock(m['generated_at_taipei'])
        need(generated.date().isoformat()==day and generated<=clock(now),'E2_GENERATION_DATE_FUTURE_OR_BACKDATED')
        # The original generation timestamp is never rewritten by this boundary.
    elif mode=='postclose':
        need(s.get('signal_asof')==day and obj(files,E+'history/'+day.replace('-','')+'_postclose.json')==s,'E2_STATE_HISTORY_CLOSURE')
    if d:need(clock(d['generated_at_taipei'])>=clock(s['generated_at_taipei']),'DISPLAY_PRECEDES_E2_SOURCE')


def eod_closure(files,day):
    folder='eod/'+day.replace('-','')+'/';st=obj(files,folder+'status.json')
    need(st.get('target_date')==day,'EOD_STATUS_DATE_MISMATCH');verified={}
    for leg in EOD_MIN:
        names=sorted(Path(p).name for p in files if p.startswith(folder) and re.fullmatch(leg+r'_[1-9]\.csv',p[len(folder):]))
        if not names:
            need(st.get(leg+'_status') in ('PENDING','ERROR','NOT_READY',None),'EOD_COMPLETE_WITHOUT_SHARDS:'+leg);continue
        rec=obj(files,folder+'receipts/'+leg+'.json');rows=[];h=hashlib.sha256()
        for name in names:
            value=files[folder+name];b=value if isinstance(value,bytes) else value.encode()
            h.update(name.encode()+b'\0'+b+b'\0');reader=csv.DictReader(io.StringIO(b.decode('utf-8-sig')))
            need(set(EOD_COLUMNS[leg])<=set(reader.fieldnames or []),'EOD_SCHEMA:'+leg);rows.extend(reader)
        keys=[(x.get('Date'),x.get('Ticker')) for x in rows]
        need(len(rows)>=EOD_MIN[leg] and len(keys)==len(set(keys)) and all(d==day and re.fullmatch(r'[1-9]\d{3}',t or '') for d,t in keys),'EOD_DATE_COUNT_UNIQUE_KEYS:'+leg)
        need(all(None not in row and all(v is not None for v in row.values()) for row in rows),'EOD_TORN_SHARD:'+leg)
        need(rec.get('artifact')=='EOD_ORIGINAL_VESSEL_LEG_RECEIPT' and rec.get('target_date')==day and rec.get('leg')==leg and
             rec.get('status')=='COMPLETE' and rec.get('files')==names and rec.get('rows')==len(rows) and rec.get('sha256')==h.hexdigest(),'EOD_SHARD_RECEIPT_MISMATCH:'+leg)
        need(st.get(leg+'_status')=='COMPLETE' and st.get(leg+'_date')==day and st.get(leg+'_rows')==len(rows) and st.get(leg+'_sha256')==h.hexdigest(),'EOD_LEG_STATUS_MISMATCH:'+leg)
        verified[leg]=h.hexdigest()
    mother=False
    if folder+'receipts/mother.json' in files:
        mr=obj(files,folder+'receipts/mother.json')
        mother=(mr.get('target_date')==day and mr.get('mother_latest_date')==day and mr.get('status') in ('PASS','COMPLETE') and
                mr.get('second_mother') is False and bool(mr.get('mother_sha256')) and
                all(mr.get('promoted_leg_sha256',{}).get(k)==v for k,v in verified.items()))
    need((st.get('mother_status')=='COMPLETE')==mother,'EOD_MOTHER_BINDING_MISMATCH')
    if mother:
        need(st.get('mother_sha256')==mr['mother_sha256'] and st.get('mother_latest_date')==day and
             st.get('mother_receipt')=='receipts/mother.json','EOD_STATUS_MOTHER_RECEIPT_MISMATCH')
    need(st.get('downstream_ready') is ('price' in verified and mother),'EOD_FALSE_DOWNSTREAM_READY')
    need(st.get('three_leg_complete') is (len(verified)==3) and st.get('formal_complete_day') is (len(verified)==3),'EOD_FALSE_THREE_LEG_COMPLETE')
    return 'PASS' if len(verified)==3 and mother else 'PENDING_DATA'


def history_closure(files,before,day):
    def rows(source):
        reader=csv.DictReader(io.StringIO(text(source,HISTORY)))
        need({'date','ticker','open','close'}<=set(reader.fieldnames or []),'HISTORY_SCHEMA')
        out={}
        for row in reader:
            need(None not in row and all(v is not None for v in row.values()),'TORN_HISTORY_ROW')
            key=(row['date'],row['ticker']);need(key not in out and re.fullmatch(r'[1-9]\d{3}',key[1]) and key[0]<=day,'HISTORY_KEYS_OR_FUTURE_DATE')
            out[key]=row
        need(bool(out),'EMPTY_HISTORY');return out
    current=rows(files)
    if HISTORY in before:
        old=rows(before)
        need({k:v for k,v in current.items() if k[0]<day}=={k:v for k,v in old.items() if k[0]<day},'HISTORICAL_REGENERATION_FORBIDDEN')


def review_closure(files,before,day):
    root='hengce/q017_review_10d/';p=root+'ledger_latest.json';ledger=obj(files,p);same_hash(ledger,'ledger_sha256')
    old=obj(before,p).get('cohorts',{}) if p in before else {}
    for key,c in ledger['cohorts'].items():
        dates=[x['date'] for x in c['sessions']]
        need(len(dates)==len(set(dates))<=10 and all(x<=day for x in dates),'REVIEW_DUPLICATED_OR_FUTURE_SESSION')
        if key not in old:need(c.get('signal_date')==day,'HISTORICAL_REVIEW_SEED_BLOCKED')
        else:need(all(c.get(k)==old[key].get(k) for k in ('signal_date','ticker','rank','decision_snapshot_sha256','selection_reference_price')),'REVIEW_IMMUTABLE_COHORT_CHANGED')
    report=obj(files,root+'review_latest.json');need(report.get('ledger_sha256')==ledger['ledger_sha256'],'REVIEW_LEDGER_SUMMARY_MISMATCH')
    date=report['review_date'];daily=root+'daily/'+date.replace('-','')+'_review.json'
    need(obj(files,daily)==report and daily.removesuffix('.json')+'.md' in files,'REVIEW_DAILY_CLOSURE')
    hp=root+'hypothetical_ledger_latest.json'
    if hp in files:
        h=obj(files,hp);same_hash(h,'ledger_sha256');prior=obj(before,hp).get('cohorts',{}) if hp in before else {}
        for key,c in h['cohorts'].items():
            dates=[s['date'] for s in c['sessions']];need(len(dates)==len(set(dates))<=10,'REVIEW_HYPOTHETICAL_DUPLICATE_SESSION')
            if key not in prior:need(c.get('signal_date')==day,'HISTORICAL_HYPOTHETICAL_SEED_BLOCKED')
        diag=obj(files,root+'diagnostics_latest.json');need(diag.get('guard',{}).get('model_mutation_allowed') is False,'REVIEW_DIAGNOSTIC_AUTHORITY')
        need(obj(files,root+'diagnostics_'+diag['review_date'].replace('-','')+'.json')==diag,'REVIEW_DIAGNOSTIC_CLOSURE')


def macro_closure(files,day):
    root=Q+'data/macro_cache/';m=obj(files,root+'latest.json');same_hash(m,'cache_sha256')
    need(m.get('schema_version')==1 and m.get('trade_date')==day and m.get('status')=='PASS','MACRO_SCHEMA_DATE_STATUS')
    need(obj(files,root+day.replace('-','')+'.json')==m and history_contains(files,root+'history/',m,day),'MACRO_DATED_LATEST_HISTORY')
    for leg in ('sox','dxy'):
        p=Q+'data/'+leg+'_2026.csv';b=files[p];b=b if isinstance(b,bytes) else b.encode()
        need(m['files'].get(leg+'_csv_sha256')==hashlib.sha256(b).hexdigest(),'MACRO_SOURCE_HASH_BINDING')
        need(m[leg+'_status'].get('latest_session','9999')<day,'MACRO_NONCAUSAL_SESSION')


def validate_closure(files,lane,mode,day,changed,before,now):
    try:
        need(lane in LANES and mode in LANES[lane],'UNKNOWN_RECOVERY_CONTRACT')
        compact=day.replace('-','');decision=Q+'decision/'+compact+'_0901.json'
        if lane=='q017-recovery':qclosure(files,day,decision=True)
        elif lane=='q017-backup' and any(p.startswith(Q+'backup_observations/') for p in changed):qclosure(files,day,backup=True)
        elif any(p.startswith(Q+'observations/') for p in changed):qclosure(files,day)
        formal=any(p.startswith(Q+'decision/') or p==Q+'decision_latest.json' for p in changed)
        formal=formal or Q+'signal_ledger.jsonl' in changed
        for p in changed:
            if p.startswith(Q+'history/') and p.endswith('.json'):
                h=obj(files,p)
                if h.get('binding_status')=='PASS' and h.get('decision_snapshot_sha256'):formal=True
                elif h.get('module')=='Q017_0901_OBSERVATION_LOCK':qclosure(files,day)
        if Q+'latest.json' in changed:
            latest=obj(files,Q+'latest.json')
            formal=formal or (latest.get('binding_status')=='PASS' and bool(latest.get('decision_snapshot_sha256')))
            if not formal:need(latest.get('authority')=='NO_FORMAL_SIGNAL' and not latest.get('formal_buy_count') and not latest.get('top3'),'Q017_PARTIAL_DIAGNOSTIC_AUTHORITY')
        if formal:qclosure(files,day,decision=True)
        ledger=Q+'signal_ledger.jsonl'
        if ledger in changed:
            old=text(before,ledger).splitlines() if ledger in before else []
            new=text(files,ledger).splitlines()
            need(new[:len(old)]==old and all(json.loads(x).get('date')==day for x in new[len(old):]),'HISTORICAL_LEDGER_REWRITE_OR_BACKFILL_BLOCKED')
        echanged=any(p.startswith(E) for p in changed)
        if echanged or lane in ('e2-morning','e2-postclose'):eclosure(files,day,mode,now,require_display=lane!='daily' or D in changed)
        elif D in changed:display(files,day)
        if lane=='eod' or any(p.startswith('eod/'+compact+'/') for p in changed):eod_closure(files,day)
        if HISTORY in changed:history_closure(files,before,day)
        if lane=='review' or any(p.startswith('hengce/q017_review_10d/') for p in changed):review_closure(files,before,day)
        if lane=='macro' or any(p.startswith(Q+'data/macro_cache/') for p in changed):macro_closure(files,day)
        return 'STAGED_COMPLETE'
    except Blocked:raise
    except (KeyError,ValueError,TypeError,AttributeError,UnicodeError) as exc:raise Blocked('INCOMPLETE_OR_INVALID_TRANSACTION:'+type(exc).__name__) from exc


def current_request(lane,mode,requested,now):
    now=clock(now);day=now.date().isoformat()
    need(lane in LANES and mode in LANES[lane],'UNKNOWN_RECOVERY_CONTRACT')
    need(not requested or requested==day,'HISTORICAL_OR_FUTURE_RECOVERY_BLOCKED')
    if mode!='self-test':
        need(now.weekday()<5,'NON_DUE_RECOVERY_BLOCKED')
        if mode=='postclose':need(now.time()>=time(15),'POSTCLOSE_NOT_DUE')
        if mode in ('morning','e2-morning'):need(now.time()>=time(8,50),'MORNING_NOT_DUE')
        if mode in ('premarket','refresh') and lane!='display':need(now.time()<time(9,1),'PREMARKET_REFRESH_WINDOW_CLOSED')
    return day


def validate_inputs(files,lane,mode,day,now):
    try:
        compact=day.replace('-','')
        if lane in ('q017-primary','q017-backup'):
            folder='backup_observations/' if lane=='q017-backup' else 'observations/'
            p=Q+folder+compact+'_0901_observation.json'
            if p in files:observed(obj(files,p),day)
            else:need(clock(now).time()<time(9,2),'Q017_CAPTURE_CLOSED_MISSING_EVIDENCE_NO_REFETCH')
        elif lane=='q017-recovery':
            primary=Q+'observations/'+compact+'_0901_observation.json';backup=Q+'backup_observations/'+compact+'_0901_observation.json'
            observed(obj(files,primary if primary in files else backup),day)
            if Q+'decision/'+compact+'_0901.json' in files:qclosure(files,day,decision=True)
        elif lane in ('e2-morning','e2-postclose'):estate(files,day)
        elif lane=='eod' and 'eod/'+compact+'/status.json' in files:eod_closure(files,day)
        elif lane=='display':
            # Existing producers still own pending-source display semantics.
            if E+'state_latest.json' in files:estate(files,day)
        elif lane=='review':
            p='hengce/q017_review_10d/ledger_latest.json';need(p in files,'REVIEW_RECOVERY_SEED_NOT_AUTHORIZED');same_hash(obj(files,p),'ledger_sha256')
        return True
    except Blocked:raise
    except (ValueError,TypeError,KeyError,AttributeError) as exc:raise Blocked('INPUT_VALIDATION_FAILED:'+type(exc).__name__) from exc


def location(repo):
    return Path(git(repo,'rev-parse','--absolute-git-dir').decode().strip())/'hengce-recovery/active.json'


def validate_record(record):
    need(set(record)==KEYS and record['schema_version']==1 and record['state'] in STATES,'UNKNOWN_TRANSACTION_CONTRACT_OR_STATE')
    need(record['lane'] in LANES and record['mode'] in LANES[record['lane']],'UNKNOWN_TRANSACTION_LANE')
    need(all(type(record[k]) is type(v) and record[k]==v for k,v in ZERO.items()),'TRANSACTION_AUTHORITY_FORBIDDEN')
    need(record['local_adoption'] in ('UNKNOWN','PENDING','SUCCESS','FAILED') and type(record['publication_intent']) is bool,'UNKNOWN_ADOPTION_STATE')
    need(isinstance(record['observed_states'],list) and all(s in STATES for s in record['observed_states']),'UNKNOWN_EVIDENCE_STATE')
    need(set(record['evidence_completeness'])=={'inputs','staged_closure','commit','remote_acceptance','local_adoption'},'UNKNOWN_EVIDENCE_CONTRACT_FIELD')
    need(set(record['read_dependency_contract'])=={'mode','excluded_patterns','unknown_paths'} and
         record['read_dependency_contract']['mode']=='ALL_PATHS_EXCEPT_PROVEN_UNRELATED' and
         record['read_dependency_contract']['unknown_paths']=='READ_DEPENDENCY_FAIL_CLOSED','UNKNOWN_READ_DEPENDENCY_CONTRACT')
    if record['state'] in ('REMOTE_ACCEPTED','LOCAL_ADOPTED'):
        need(bool(re.fullmatch(r'[0-9a-f]{40}',record['accepted_remote_sha'])),'UNPROVEN_ACCEPTED_REMOTE')
    return record


def load(repo):
    try:return validate_record(json.loads(location(repo).read_text()))
    except (OSError,ValueError,KeyError,TypeError) as exc:raise Blocked('TRANSACTION_EVIDENCE_MISSING_OR_MALFORMED') from exc


def save(repo,record):
    validate_record(record);path=location(repo);path.parent.mkdir(parents=True,exist_ok=True)
    value=json.dumps(record,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n'
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as f:f.write(value);tmp=Path(f.name)
    tmp.replace(path)
    out=Path(record['report_dir'])/'transactions';out.mkdir(parents=True,exist_ok=True)
    with (out/(record['transaction_id']+'-'+uuid.uuid4().hex+'.json')).open('x',encoding='utf-8') as f:f.write(value)


def advance(repo,record,state,reason,**facts):
    need(state in TRANSITIONS[record['state']] or state==record['state'],'ILLEGAL_RECOVERY_STATE_TRANSITION')
    record.update(facts,state=state);record['reason_codes'].append(reason);record['observed_states'].append(state)
    save(repo,record);return record


def blocked(repo,reason):
    if location(repo).exists():
        record=load(repo)
        adoption=record['local_adoption']
        if record['state']=='REMOTE_ACCEPTED' and adoption!='SUCCESS':adoption='FAILED'
        advance(repo,record,'BLOCKED',reason,local_adoption=adoption)


def clean(repo):
    need(not git(repo,'status','--porcelain').strip(),'CLEAN_CHECKOUT_REQUIRED_NO_RESET_OR_STASH')


def _prepare(repo,lane,mode,requested,now=None,report_dir=None):
    now=clock(now);day=current_request(lane,mode,requested,now);clean(repo)
    git(repo,'fetch','--no-tags','origin','refs/heads/main');remote=git(repo,'rev-parse','FETCH_HEAD').decode().strip()
    head=git(repo,'rev-parse','HEAD').decode().strip()
    prior=None
    if location(repo).exists():
        prior=load(repo)
        if prior['publication_intent'] or prior['state'] in ('BLOCKED','REMOTE_ACCEPTED','COMMITTED'):
            need(head==remote,'UNRESOLVED_LOCAL_ADOPTION_CLEAN_REMOTE_CHECKOUT_REQUIRED')
            if prior['proposal_write_hashes']:
                snap=Snapshot(repo,remote)
                need(all(snap.entries.get(p)==(tuple(h) if h is not None else None) for p,h in prior['proposal_write_hashes'].items()),'REMOTE_ACCEPTANCE_UNPROVEN_MANUAL_REVIEW_REQUIRED')
    # Clean pre-computation synchronization only; never transplant computed output.
    if head!=remote:
        delta=git(repo,'diff','--name-only',head,remote).decode().splitlines()
        need(not any(p.startswith(('scripts/','.github/','config/')) for p in delta),'CODE_OR_CONTRACT_DRIFT_REQUIRES_REVIEW')
        git(repo,'merge-base','--is-ancestor',head,remote)
        git(repo,'read-tree','-u','-m',head,remote);git(repo,'update-ref','HEAD',remote,head)
    snap=Snapshot(repo,remote);validate_inputs(snap,lane,mode,day,now)
    if prior and (prior['publication_intent'] or prior['state'] in ('BLOCKED','REMOTE_ACCEPTED','COMMITTED')):
        validate_closure(snap,prior['lane'],prior['mode'],prior['trade_date'],set(prior['proposal_write_hashes']),Snapshot(repo,prior['original_base_sha']),now)
        # A fresh clean checkout plus fetched matching bytes is new evidence,
        # not a retroactively fabricated acknowledgement or computation step.
        prior['accepted_remote_sha']=remote;prior['local_adoption']='SUCCESS';prior['publication_intent']=False
        prior['evidence_completeness']['remote_acceptance']='PROVEN_BY_FRESH_FETCH_IDENTICAL_BYTES'
        prior['evidence_completeness']['local_adoption']='PROVEN_CLEAN_REMOTE_CHECKOUT_AND_INPUT_REVALIDATION'
        advance(repo,prior,prior['state'],'REMOTE_AUTHORITY_RECONCILED_BEFORE_NEW_COMPUTATION')
    record=dict(schema_version=1,transaction_id=uuid.uuid4().hex,workflow=os.environ.get('GITHUB_WORKFLOW','SYNTHETIC_OR_MANUAL'),
        run_id=os.environ.get('GITHUB_RUN_ID','LOCAL'),run_attempt=os.environ.get('GITHUB_RUN_ATTEMPT','LOCAL'),
        lane=lane,mode=mode,trade_date=day,state='OBSERVED',generated_at_taipei=now.isoformat(),original_base_sha=remote,
        authoritative_input_hashes=snap.entries,proposal_write_hashes={},immutable_write_set=[],accepted_remote_sha='UNKNOWN',
        local_adoption='UNKNOWN',publication_intent=False,staged_tree_sha='UNKNOWN',proposal_sha='UNKNOWN',
        evidence_completeness=dict(inputs='FRESH_GIT_TREE_AND_LANE_VALIDATION',staged_closure='UNKNOWN',commit='UNKNOWN',remote_acceptance='UNKNOWN',local_adoption='UNKNOWN'),
        observed_states=['OBSERVED'],reason_codes=['FRESH_REMOTE_OBSERVED'],report_dir=str(report_dir or Path(os.environ.get('RUNNER_TEMP',tempfile.gettempdir()))/'hengce-publication'),
        read_dependency_contract=dict(mode='ALL_PATHS_EXCEPT_PROVEN_UNRELATED',excluded_patterns=[],unknown_paths='READ_DEPENDENCY_FAIL_CLOSED'),**ZERO)
    save(repo,record);return advance(repo,record,'INPUTS_VALIDATED','CURRENT_DATE_INPUTS_REVALIDATED')


def prepare(repo,lane,mode,requested,now=None,report_dir=None):
    try:return _prepare(repo,lane,mode,requested,now,report_dir)
    except (Blocked,OSError,subprocess.TimeoutExpired) as exc:
        try:blocked(repo,str(exc))
        except (Blocked,OSError):pass
        raise


def fence(repo,now=None,scope=None):
    record=load(repo);need(record['state'] in ('INPUTS_VALIDATED','LOCAL_ADOPTED') and not record['publication_intent'],'COMPUTATION_FENCED_PENDING_REMOTE_RECONCILIATION_AND_CLEAN_REVALIDATION')
    current_request(record['lane'],record['mode'],record['trade_date'],now)
    if record['state']=='LOCAL_ADOPTED':
        need(git(repo,'rev-parse','HEAD').decode().strip()==record['accepted_remote_sha'],'ACCEPTED_CHECKOUT_HEAD_MISMATCH')
        # This is a new phase, observed before computation, never retroactive proof.
        record=prepare(repo,record['lane'],record['mode'],record['trade_date'],now,record['report_dir'])
    if scope:
        if scope=='eod-ready':
            # Post-ingest boundary: absent status cannot mean ready. Valid
            # PENDING is retained, including the original no-wait-margin rule.
            eod_closure(WorkingFiles(repo),record['trade_date'])
            return record
        mode={'q017-primary':'observe','q017-backup':'observe','q017-recovery':'compute','e2-morning':'morning',
              'e2-postclose':'postclose','eod':'postclose','review':'postclose','display':'refresh','macro':'refresh'}[scope]
        # Domain-only failure blocks this subtask; publication/adoption uncertainty
        # blocks the entire checkout. Independent sibling engine checks can run.
        validate_inputs(WorkingFiles(repo),scope,mode,record['trade_date'],clock(now))
    return record


class WorkingFiles(Mapping):
    def __init__(self,root):
        self.root=Path(root)
        self.paths=set(git(root,'ls-files','-z').decode().split('\0'))|set(git(root,'ls-files','--others','--exclude-standard','-z').decode().split('\0'))
        self.paths.discard('')
    def __iter__(self):return iter(self.paths)
    def __len__(self):return len(self.paths)
    def __getitem__(self,p):
        if p not in self.paths or not (self.root/p).is_file():raise KeyError(p)
        need(not (self.root/p).is_symlink(),'NON_REGULAR_ARTIFACT:'+p);return (self.root/p).read_bytes()


def _stage(repo,now=None):
    record=fence(repo,now=now);head=git(repo,'rev-parse','HEAD').decode().strip()
    need(head==record['original_base_sha'],'COMPUTATION_BASE_CHANGED_REVALIDATION_REQUIRED')
    staged=git(repo,'write-tree').decode().strip();before=Snapshot(repo,head);after=Snapshot(repo,staged)
    changed={p for p in before.entries.keys()|after.entries.keys() if before.entries.get(p)!=after.entries.get(p)}
    need(bool(changed),'NO_STAGED_TRANSACTION')
    need(all(any(fnmatch.fnmatchcase(p,pattern) for pattern in WRITES[record['lane']]) for p in changed),'WRITE_OUTSIDE_OPERATIONAL_LANE_CONTRACT')
    need(E+'execution_override.json' not in changed,'PRODUCER_OVERRIDE_FABRICATION_FORBIDDEN')
    from hengce_publish import IMMUTABLE_PREFIXES
    immutable=[p for p in changed if p.startswith(IMMUTABLE_PREFIXES)]
    need(all(p not in before and after.entries.get(p,('',))[0]=='100644' for p in immutable),'IMMUTABLE_PRECOMMIT_CONFLICT')
    need(not git(repo,'diff','--name-only').strip(),'UNSTAGED_AUTHORITATIVE_INPUT_OR_OUTPUT')
    need(not git(repo,'ls-files','--others','--exclude-standard').strip(),'UNDECLARED_UNTRACKED_INPUT_OR_OUTPUT')
    validate_closure(after,record['lane'],record['mode'],record['trade_date'],changed,before,clock(now))
    for p in (E+'morning_latest.json',E+'state_latest.json'):
        if p in changed:
            need(clock(obj(after,p)['generated_at_taipei'])>=clock(record['generated_at_taipei']),'BACKDATED_E2_RECOVERY_TIMESTAMP')
    record['evidence_completeness']['staged_closure']='PROVEN_FOR_DECLARED_PROPOSAL'
    return advance(repo,record,'STAGED_COMPLETE','OUTPUT_CLOSURE_VALIDATED',staged_tree_sha=staged,immutable_write_set=immutable,
        proposal_write_hashes={p:after.entries.get(p) for p in sorted(changed)})


def stage(repo,now=None):
    try:return _stage(repo,now)
    except (Blocked,OSError,subprocess.TimeoutExpired) as exc:
        try:blocked(repo,str(exc))
        except (Blocked,OSError):pass
        raise


def committed(repo,lane,now=None,immutable_paths=(),unrelated=()):
    record=load(repo);need(record['state']=='STAGED_COMPLETE' and record['lane']==lane,'UNPROVEN_STAGED_TRANSACTION')
    current_request(lane,record['mode'],record['trade_date'],now)
    head=git(repo,'rev-parse','HEAD').decode().strip()
    need(git(repo,'rev-parse',head+'^').decode().strip()==record['original_base_sha'] and
         git(repo,'rev-parse',head+'^{tree}').decode().strip()==record['staged_tree_sha'],'COMMIT_NOT_EXACT_VALIDATED_PROPOSAL')
    need(not git(repo,'diff','--name-only','HEAD').strip(),'POST_STAGE_TRACKED_INPUT_OR_OUTPUT_CHANGED')
    validate_closure(Snapshot(repo,head),lane,record['mode'],record['trade_date'],set(record['proposal_write_hashes']),Snapshot(repo,record['original_base_sha']),clock(now))
    record['evidence_completeness']['commit']='PROVEN'
    record['immutable_write_set']=sorted(immutable_paths)
    record['read_dependency_contract']['excluded_patterns']=list(unrelated)
    record['authoritative_input_hashes']={p:h for p,h in record['authoritative_input_hashes'].items()
                                         if not any(fnmatch.fnmatchcase(p,pattern) for pattern in unrelated)}
    return advance(repo,record,'COMMITTED','EXACT_COMMIT_VALIDATED',proposal_sha=head)


def intent(repo,record,candidate):
    return advance(repo,record,'COMMITTED','EXACT_LEASE_PUBLICATION_INTENT',publication_intent=True,proposal_sha=candidate,local_adoption='PENDING')


def accepted(repo,record,sha,reason):
    record['evidence_completeness']['remote_acceptance']='PROVEN_BY_ACK_OR_FETCHED_IDENTICAL_BYTES'
    return advance(repo,record,'REMOTE_ACCEPTED',reason,accepted_remote_sha=sha,local_adoption='PENDING',publication_intent=True)


def adopted(repo,record):
    need(git(repo,'rev-parse','HEAD').decode().strip()==record['accepted_remote_sha'],'LOCAL_HEAD_NOT_ACCEPTED_REMOTE')
    record['evidence_completeness']['local_adoption']='PROVEN'
    return advance(repo,record,'LOCAL_ADOPTED','ACCEPTED_CHECKOUT_ADOPTED',local_adoption='SUCCESS',publication_intent=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=('prepare','fence','stage'))
    parser.add_argument('--repo',type=Path,default=Path.cwd());parser.add_argument('--lane');parser.add_argument('--mode');parser.add_argument('--scope')
    args=parser.parse_args()
    try:
        if args.phase=='prepare':prepare(args.repo,args.lane,args.mode,os.environ.get('HENGCE_REQUEST_DATE',''))
        elif args.phase=='fence':fence(args.repo,scope=args.scope)
        else:stage(args.repo)
        return 0
    except (Blocked,ValueError,KeyError,OSError,subprocess.TimeoutExpired) as exc:
        # Domain rejection cannot fabricate intermediate states or repair files.
        try:report=dict(load(args.repo))
        except (Blocked,OSError):report=dict(schema_version=1,lane=args.lane or 'UNKNOWN',mode=args.mode or 'UNKNOWN',
            workflow=os.environ.get('GITHUB_WORKFLOW','LOCAL'),run_id=os.environ.get('GITHUB_RUN_ID','LOCAL'),
            run_attempt=os.environ.get('GITHUB_RUN_ATTEMPT','LOCAL'),accepted_remote_sha='UNKNOWN',local_adoption='UNKNOWN',
            evidence_completeness='UNKNOWN')
        report.update(state='BLOCKED',reason_codes=[str(exc)],generated_at_taipei=clock().isoformat(),**ZERO)
        out=Path(os.environ.get('RUNNER_TEMP',tempfile.gettempdir()))/'hengce-publication/transactions';out.mkdir(parents=True,exist_ok=True)
        (out/(uuid.uuid4().hex+'.json')).write_text(json.dumps(report)+'\n');print(json.dumps(report));return 2


if __name__=='__main__':raise SystemExit(main())
