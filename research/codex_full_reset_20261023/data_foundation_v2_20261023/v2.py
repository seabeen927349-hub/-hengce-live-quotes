"""Issue31 evidence-only inventory. No signal generation, model or PnL code."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE=Path(__file__).resolve().parent
RESET=HERE.parent
ROOT=RESET.parents[1]
sys.path.insert(0,str(RESET))
from reset_ledger import AUTHORITY, TrialLedger, digest
from stage_b_build_twse_year import load_expected
sys.path.insert(0,str(RESET/'data_foundation_20261023'))
import normalize as v1n
import evidence as v1
PARENT='593652df3e414b223eea0d568299084cf5c85c52'
OUT=HERE/'results'


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def lines(path):return [json.loads(x) for x in path.read_text().splitlines()]
def write(path,obj):
    with path.open('x') as f:json.dump(obj,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False);f.write('\n')
def write_lines(path,rows):
    with path.open('x') as f:
        for row in rows:f.write(json.dumps(row,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n')
def require(ok,reason):
    if not ok:raise ValueError(reason)


def assert_hashes(root,inventory):
    for name,h in inventory.items():require(sha(root/name)==h,'PARENT_BYTE_CHANGED:'+name)


def verify_parent():
    inventory=read(HERE/'PARENT_INVENTORY.json')
    require(sha(HERE/'PARENT_INVENTORY.json')==read(HERE/'PLAN_V2.json')['parent_inventory_sha256'],'PARENT_INVENTORY_DRIFT')
    assert_hashes(ROOT,inventory['sha256'])
    require(subprocess.run(['git','merge-base','--is-ancestor',PARENT,'HEAD'],cwd=ROOT).returncode==0,'WRONG_PARENT')


def original_events():
    base=RESET/'data_foundation_20261023/results'
    manifest=read(base/'MANIFEST.json');source={r['id']:r for r in manifest['records']}
    projected=read(base/'ELECTRONICS_EVENTS.json')['events']
    for group in read(base/'NORMALIZED_ADDITIONAL_EVIDENCE.json')['reduction_projections']:projected+=group['events']
    require(len(projected)==1151,'PARENT_EVENT_COUNT')
    result=[]
    for item in projected:
        row=dict(item);kind=row['source_report'];year=int(row['effective_date'][:4]);receipt=source[f'{kind}_{year}']
        raw=json.loads(gzip.decompress((base/receipt['raw_path']).read_bytes()))
        matches=[]
        for i,values in enumerate(raw['data']):
            day=values[0]
            if kind=='TWTAUU':
                m=re.fullmatch(r'(\d{3})/(\d{2})/(\d{2})',day);require(m is not None,'SOURCE_DATE_SCHEMA')
                day=f'{m[1]}年{m[2]}月{m[3]}日'
            if v1.iso(day)==row['effective_date'] and values[1].strip()==row['ticker']:matches.append(i)
        require(len(matches)==1,'SOURCE_ROW_NOT_UNIQUE')
        row.update(event_id=f'{kind}:{row["effective_date"]}:{row["ticker"]}',source_row_index=matches[0],
                   source_sha256=receipt['response_sha256'],source_url=receipt['url'],
                   pit_membership='FROZEN_EXACT_DAILY_MEMBERSHIP',schema_version='V2_EVENT_1')
        result.append(row)
    require(len({r['event_id'] for r in result})==1151,'DUPLICATE_PARENT_EVENT')
    return sorted(result,key=lambda e:(e['effective_date'],e['ticker'],e['source_report']))


def trials_and_windows():
    """Read retained windows only. Missing windows are never reconstructed."""
    ledger=lines(RESET/'results/stage_c/EXPERIMENT_LEDGER.jsonl')
    starts={r['experiment_id']:r for r in ledger if r['status']=='STARTED'}
    terminal={r['experiment_id']:r for r in ledger if r['status'] in ('EVALUATED','NO_TRADE','FAILED','ABORTED') and r.get('experiment_id')}
    require(set(starts)==set(terminal) and len(starts)==8505,'PARENT_TRIAL_ACCOUNTING')
    summary=read(RESET/'results/stage_c/runs/39937394677-1/TRIAL_SUMMARY.json')
    baseline=read(RESET/'results/stage_c/runs/39937394677-1/BASELINE_REPRODUCTION.json')
    bindings=[]
    for family in summary['families'].values():
        for foldname,fold in family['folds'].items():
            for cost_key,events in fold.get('events',{}).items():
                bindings.append((fold['selected_config_id'],fold['validation'][cost_key],float(cost_key[5:]),events,
                                 'TRIAL_SUMMARY.json:'+foldname+':'+fold['selected_config_id']+':'+cost_key))
    output=[]
    for trial_id,start in starts.items():
        term=terminal[trial_id];events=None;binding=None
        if trial_id=='RESET-BASELINE-V2-20261023-001':
            events=read(RESET/'results/BASELINE_REPRODUCTION_V2.json')['events'];binding='BASELINE_REPRODUCTION_V2.json:events'
        elif start.get('options',{}).get('residual_cap')==.04:
            key='strict_quality_event_sample' if start['options'].get('quality_guard') else 'reference_event_sample'
            candidate=baseline[key]
            if len(candidate)==term.get('metrics',{}).get('complete_trades'):events=candidate;binding='BASELINE_REPRODUCTION.json:'+key
        elif int(start.get('evaluation_sequence',99999))<8491:
            # 8491 onward are the explicitly separate stricter-quality calls in
            # the pinned code; they cannot borrow primary-quality windows.
            candidates=[(ev,label) for config,m,cost,ev,label in bindings
                        if config==start.get('config_id') and m==term.get('metrics') and cost==start.get('cost')]
            if len(candidates)==1:events,binding=candidates[0]
        output.append({'trial_id':trial_id,'prior_status':term['status'],'period':start.get('period'),
                       'config_id':start.get('config_id'), 'events':events,'source_binding':binding,
                       'unretained_censored_baskets':term.get('metrics',{}).get('censored_baskets',0),
                       'window_status':'RETAINED_WINDOWS_METADATA_BOUND' if events is not None else 'UNKNOWN_WINDOWS_NOT_RETAINED'})
    child=RESET/'continuation_20261023/results'
    for record in lines(child/'LEDGER.jsonl'):
        if record['status']!='EVALUATED':continue
        retained=read(child/record['result_file'])
        output.append({'trial_id':record['experiment_id'],'prior_status':record['status'],
                       'period':['2023-01-01','2025-12-31'],'config_id':retained['trial'],'events':retained['events'],
                       'source_binding':'continuation_20261023/results/'+record['result_file'],
                       'unretained_censored_baskets':0,'window_status':'RETAINED_WINDOWS_EXACT_FILE'})
    require(len(output)==8529 and len({r['trial_id'] for r in output})==8529,'ALL_TRIAL_COUNT')
    return sorted(output,key=lambda r:r['trial_id'])


def tickers(event):return event.get('tickers',[event['ticker']] if 'ticker' in event else [])
def intersects(event,window):
    if event['ticker'] not in tickers(window):return None
    day=event['effective_date']
    if day==window['entry_date']:return 'ENTRY'
    if day==window['exit_date']:return 'EXIT'
    if window['entry_date']<day<window['exit_date']:return 'HOLDING'
    return None


def collection_tasks(events,trials):
    used=set()
    index=defaultdict(list)
    for trial in trials:
        for window in trial['events'] or []:
            for ticker in tickers(window):index[ticker].append(window)
    for event in events:
        if event['source_report']=='TWT49U' and any(intersects(event,w) for w in index[event['ticker']]):used.add(event['event_id'])
    chosen=[e for e in events if e['event_id'] in used and (e['ticker'],e['effective_date']) not in
            (('6189','2025-07-25'),('2364','2025-08-28'))][:12]
    tasks=[{'id':e['event_id'].replace(':','_'),'event_id':e['event_id'],'ticker':e['ticker'],
            'effective_date':e['effective_date'],'kind':'DETAIL',
            'url':'https://www.twse.com.tw/rwd/zh/exRight/TWT49UDetail?response=json&STK_NO='+e['ticker']+'&T1='+e['effective_date'].replace('-','')} for e in chosen]
    plan=read(HERE/'PLAN_V2.json')
    tasks += [{'id':'SOURCE_DOC_'+str(i),'kind':'DOCUMENT','url':url} for i,url in enumerate(plan['collection']['supporting_documents'])]
    require(len(tasks)<=14,'REQUEST_BUDGET')
    return tasks


def collect():
    verify_parent()
    # The plan must be tracked and the remote branch must contain its commit.
    plan_blob=subprocess.check_output(['git','show','HEAD:'+str((HERE/'PLAN_V2.json').relative_to(ROOT))],cwd=ROOT)
    require(plan_blob==(HERE/'PLAN_V2.json').read_bytes(),'PLAN_NOT_COMMITTED')
    remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/research/codex-full-reset-run-20261023'],cwd=ROOT,text=True).split()[0]
    require(subprocess.run(['git','merge-base','--is-ancestor','e1a43dc',remote],cwd=ROOT).returncode==0,'PLAN_NOT_PUSHED')
    target=HERE/'collection';target.mkdir(exist_ok=False)
    tasks=collection_tasks(original_events(),trials_and_windows())
    (target/'COLLECTOR_SOURCE.py').write_bytes(Path(__file__).read_bytes())
    write(target/'REQUESTS.json',{'tasks':tasks,'authority':AUTHORITY,'plan_sha256':sha(HERE/'PLAN_V2.json'),
                                'collector_sha256':sha(target/'COLLECTOR_SOURCE.py')})
    for task in tasks:
        receipt={**task,'authority':AUTHORITY,'fetch_started_at_utc':datetime.now(timezone.utc).isoformat(),
                 'original_first_seen_at':None,'validation':'RAW_ONLY_NOT_ENTITLEMENT_AUTHORITY'}
        raw=b''
        try:
            with urllib.request.urlopen(task['url'],timeout=25) as response:
                raw=response.read(8388609);receipt['http_status']=response.status
                require(len(raw)<=8388608,'RESPONSE_BODY_LIMIT')
            receipt['transport']='RESPONSE_RETAINED'
        except urllib.error.HTTPError as exc:
            raw=exc.read(8388608);receipt.update(transport='HTTP_ERROR_RETAINED',http_status=exc.code,error=str(exc))
        except Exception as exc:receipt.update(transport='FAILED_RETAINED',error=type(exc).__name__+':'+str(exc))
        archived=gzip.compress(raw,mtime=0);receipt.update(fetch_completed_at_utc=datetime.now(timezone.utc).isoformat(),
                response_sha256=hashlib.sha256(raw).hexdigest(),archive_sha256=hashlib.sha256(archived).hexdigest(),
                raw_path=task['id']+'.gz',bytes=len(raw))
        with (target/receipt['raw_path']).open('xb') as f:f.write(archived)
        write(target/(task['id']+'.json'),receipt)
        print(task['id'],receipt['transport'],flush=True)
        # Access/rate-limit failures stop this source stream; unattempted requests
        # stay visibly unattempted in REQUESTS.json, not fictional empty successes.
        if receipt.get('http_status') in (401,403,429):break
        time.sleep(1.5)


TERM_FIELDS=('old_security_id','new_security_id','last_trading_date','resumption_date','cash_per_old_share',
             'free_shares_per_old_share','paid_subscription_per_old_share','subscription_price',
             'subscription_deadline','cash_payment_date','new_share_saleable_date','fractional_share_treatment')


def classify(symbol,report):
    if report=='TWTAUU':
        if symbol=='退還股款':return 'CAPITAL_REDUCTION_CASH_RETURN'
        if symbol=='彌補虧損':return 'CAPITAL_REDUCTION_LOSS_ABSORPTION'
        return 'UNKNOWN_INSUFFICIENT_SCHEMA'
    return {'息':'CASH_DIVIDEND','權':'RIGHTS_TERMS_UNKNOWN','權息':'MIXED_CASH_AND_UNSPECIFIED_RIGHTS'}.get(symbol,'UNKNOWN_INSUFFICIENT_SCHEMA')


def parse_detail(raw,event):
    obj=json.loads(raw)
    require(obj.get('stat') in ('ok','OK') and obj.get('fields')==v1n.DETAIL_FIELDS,'DETAIL_SCHEMA')
    require(len(obj.get('data',[]))==1 and len(obj['data'][0])==12,'DETAIL_ROW_SCHEMA')
    r=obj['data'][0];require(r[0].strip()==event['ticker'],'DETAIL_EVENT_MISMATCH')
    for value in (r[2],r[4],r[6],r[7],r[11]):require(',, ' not in value and not re.search(r',,',value),'MALFORMED_GROUPING')
    cash=v1n.unit(r[2],'元／股');free=v1n.unit(r[4],'股')/1000
    company_paid=v1n.unit(r[6],'股');price=v1n.unit(r[7],'元／股');paid=v1n.unit(r[11],'股')/1000
    if company_paid==0:
        expected=(Decimal(str(event['prior_close_reported']))-cash)/(1+free)
        require(abs(expected-Decimal(str(event['reference_price_reported'])))<=Decimal('.011'),'CONFLICT_REFERENCE_TERMS')
    category='MIXED_ACTION' if sum((cash>0,free>0,company_paid>0))>1 else (
        'CASH_DIVIDEND' if cash>0 else 'STOCK_DIVIDEND_FREE_SHARES' if free>0 else
        'RIGHTS_PAID_SUBSCRIPTION' if company_paid>0 else 'UNKNOWN_INSUFFICIENT_SCHEMA')
    return {'cash_per_old_share':str(cash),'free_shares_per_old_share':str(free),
            'paid_subscription_per_old_share':str(paid),'subscription_price':str(price),
            'company_paid_issue_shares':str(company_paid),'category_from_detail':category,
            'date_binding':'REQUEST_PLUS_ANNUAL_PARENT_NO_RESPONSE_DATE_ECHO'}


def merge_terms(old,new):
    result=dict(old)
    for key,value in new.items():
        if value is None:continue
        if old.get(key) is not None:
            numeric=key in ('cash_per_old_share','free_shares_per_old_share','paid_subscription_per_old_share','subscription_price')
            same=Decimal(old[key])==Decimal(value) if numeric else old[key]==value
            require(same,'CONFLICTING_OFFICIAL_TERMS:'+key)
        result[key]=value
    return result


def identity_proof(old_id,new_id,source_kind):
    require(source_kind=='HISTORICAL_EFFECTIVE_DATED_DOCUMENT','CURRENT_MASTER_SUBSTITUTION_REJECTED')
    require(bool(old_id) and bool(new_id),'UNKNOWN_SECURITY_IDENTITY')
    return 'PROVEN'


def diagnose(terms,on_date,identity_status='UNKNOWN',suspended=False):
    """Obligation diagnostics ONLY: no prices, positions, NAV or PnL produced."""
    states=[];reasons=[]
    if terms.get('status')=='CONFLICT':reasons.append('CONFLICTING_OFFICIAL_TERMS')
    if identity_status!='PROVEN':reasons.append('IDENTITY_CONTINUITY_UNKNOWN')
    if suspended:states.append('SUSPENSION_NO_TRADABLE_PRICE');reasons.append('SUSPENDED')
    if terms.get('conversion'):
        states.append('OLD_SECURITY_CONVERTED')
        if not terms.get('old_security_id') or not terms.get('new_security_id'):reasons.append('CONVERSION_IDENTITY_MISSING')
        if not terms.get('new_share_saleable_date'):reasons.append('CONVERSION_SALEABLE_DATE_UNKNOWN')
        elif on_date<terms['new_share_saleable_date']:states.append('STOCK_ENTITLEMENT_NOT_SALEABLE')
    for amount,datefield,pending,missing in (
        ('cash_per_old_share','cash_payment_date','CASH_RECEIVABLE_NOT_PAID','PAYMENT_DATE_UNKNOWN'),
        ('free_shares_per_old_share','new_share_saleable_date','STOCK_ENTITLEMENT_NOT_SALEABLE','DELIVERY_DATE_UNKNOWN')):
        value=terms.get(amount)
        if value is None:reasons.append('UNKNOWN_'+amount.upper());continue
        if Decimal(value)>0:
            available=terms.get(datefield)
            if available is None:states.append(pending);reasons.append(missing)
            elif on_date<available:states.append(pending)
    paid=terms.get('paid_subscription_per_old_share')
    if paid is None:reasons.append('SUBSCRIPTION_TERMS_UNKNOWN')
    elif Decimal(paid)>0:
        states.append('SUBSCRIPTION_REQUIRES_CASH_AND_DEADLINE')
        if terms.get('subscription_price') is None or not terms.get('subscription_deadline'):reasons.append('SUBSCRIPTION_TERMS_INCOMPLETE')
    if reasons:states.append('UNRESOLVED_ACTION_BLOCK_OBSERVATION')
    if not states:states=['ORDINARY_PRICE_RETURN_ELIGIBLE_DIAGNOSTIC_ONLY']
    return {'states':states,'block_reasons':reasons,'cash_reinvestment_allowed':not reasons and 'CASH_RECEIVABLE_NOT_PAID' not in states and 'SUBSCRIPTION_REQUIRES_CASH_AND_DEADLINE' not in states,
            'undelivered_share_sale_allowed':not reasons and 'STOCK_ENTITLEMENT_NOT_SALEABLE' not in states,
            'adjusted_pnl_computed':False,'authority':AUTHORITY}


def fill_evidence(direction,one_price,at_lower_limit,volume):
    require(direction in ('BUY','SELL'),'INVALID_SIDE')
    return {'direction':direction,'fill_status':'UNKNOWN','daily_volume':volume,
            'market_state':'ONE_PRICE_LOWER_LIMIT' if one_price and at_lower_limit else 'OTHER_OR_UNKNOWN',
            'interpretation':('LOWER_LIMIT_DOES_NOT_PROVE_BUY_NO_FILL' if direction=='BUY' else
                              'SELL_QUEUE_ALLOCATION_UNPROVEN') if one_price and at_lower_limit else 'NO_ORDER_ALLOCATION_RECORD',
            'opening_auction_matched_volume':None,'order_allocation':None,'queue_position':None,'authority':AUTHORITY}


def build():
    verify_parent();OUT.mkdir(exist_ok=False)
    events=original_events();byid={e['event_id']:e for e in events};trials=trials_and_windows()
    baseline=RESET/'data_foundation_20261023/results'
    normalized=read(baseline/'NORMALIZED_ADDITIONAL_EVIDENCE.json')
    assertions=[];latest={};classes=[]
    for event in events:
        terms={k:None for k in TERM_FIELDS}
        for known in normalized['specific_action_terms']:
            if (known['ticker'],known['effective_date'])==(event['ticker'],event['effective_date']):
                terms.update(cash_per_old_share=known['cash_per_old_share_reported'],
                             free_shares_per_old_share=str(Decimal(known['free_shares_per_1000_old_shares_reported'])/1000),
                             paid_subscription_per_old_share='0') # explicit zero company-paid issue in V1 detail
        assertion={'record_id':event['event_id']+':INITIAL','event_id':event['event_id'],'status':'PARTIAL',
                   'ticker':event['ticker'],'effective_date':event['effective_date'],'terms':terms,
                   'supersedes_record_hash':None,'source_sha256':event['source_sha256'],
                   'source_url':event['source_url'],'source_printed_date':None,'first_seen_at':None,'revision_lineage':None}
        assertions.append(assertion)
        latest[event['event_id']]=assertion
    requests=read(HERE/'collection/REQUESTS.json')['tasks']
    collection=[]
    for task in requests:
        receiptpath=HERE/'collection'/(task['id']+'.json')
        if not receiptpath.exists():collection.append({**task,'status':'NOT_ATTEMPTED_AFTER_SOURCE_STOP'});continue
        receipt=read(receiptpath);record={**receipt,'status':'RETAINED_DOCUMENT_NOT_EXECUTION_PROOF'}
        if task['kind']=='DETAIL':
            event=byid[task['event_id']]
            try:
                require(receipt.get('http_status')==200,'HTTP_NOT_OK')
                parsed=parse_detail(gzip.decompress((HERE/'collection'/receipt['raw_path']).read_bytes()),event)
                require(task['ticker']==event['ticker'] and task['effective_date']==event['effective_date'],'DETAIL_EVENT_MISMATCH')
                newterms=merge_terms(latest[event['event_id']]['terms'],{k:v for k,v in parsed.items() if k in TERM_FIELDS})
                assertion={'record_id':event['event_id']+':DETAIL:'+receipt['response_sha256'],
                    'event_id':event['event_id'],'status':'PARTIAL','ticker':event['ticker'],'effective_date':event['effective_date'],
                    'terms':newterms,'source_sha256':receipt['response_sha256'],'source_url':receipt['url'],
                    'supersedes_record_hash':None,'source_printed_date':None,'first_seen_at':None,'revision_lineage':None,
                    'detail_category':parsed['category_from_detail'],'date_binding':parsed['date_binding']}
                assertions.append(assertion);latest[event['event_id']]=assertion;record['status']='DETAIL_NUMERIC_TERMS_PROVEN_TIMING_PARTIAL'
            except Exception as exc:
                record.update(status='CONFLICT' if 'CONFLICT' in str(exc) else 'UNKNOWN_REJECTED_DETAIL',reason=type(exc).__name__+':'+str(exc))
                if record['status']=='CONFLICT':
                    assertion={**latest[event['event_id']],'record_id':event['event_id']+':CONFLICT:'+receipt['response_sha256'],
                               'status':'CONFLICT','source_sha256':receipt['response_sha256'],'source_url':receipt['url']}
                    assertions.append(assertion);latest[event['event_id']]=assertion
        collection.append(record)
    write(OUT/'COLLECTION_MANIFEST.json',{'requests':collection,'authority':AUTHORITY,'plan_sha256':sha(HERE/'PLAN_V2.json')})
    with TrialLedger(OUT/'ENTITLEMENT_LEDGER.jsonl',{'study':'V2_EVIDENCE_ASSERTIONS_NOT_MODEL_TRIALS','plan_sha256':sha(HERE/'PLAN_V2.json')}) as ledger:
        hashes={}
        for assertion in assertions:
            event_id=assertion['event_id'];assertion['supersedes_record_hash']=hashes.get(event_id)
            ledger.append(assertion);hashes[event_id]=ledger.previous
    identities=[]
    for event in events:
        item=latest[event['event_id']];category=item.get('detail_category',classify(event['event_type_reported'],event['source_report']))
        terms=item['terms']
        if terms['cash_per_old_share'] is not None and terms['free_shares_per_old_share'] is not None:
            cash=Decimal(terms['cash_per_old_share']);shares=Decimal(terms['free_shares_per_old_share'])
            if shares>0:category='MIXED_ACTION' if cash>0 else 'STOCK_DIVIDEND_FREE_SHARES'
        classes.append({**event,'category':category,'classification_status':'DETAIL_TERMS_PARTIAL_TIMING' if item.get('detail_category') else 'REPORTED_SYMBOL_ONLY',
                        'candidate_categories':['STOCK_DIVIDEND_FREE_SHARES','RIGHTS_PAID_SUBSCRIPTION'] if 'UNSPECIFIED_RIGHTS' in category or category=='RIGHTS_TERMS_UNKNOWN' else [category]})
        identities.append({'event_id':event['event_id'],'old_ticker':event['ticker'],'new_ticker':None,
             'old_security_id':None,'new_security_id':None,'economic_continuity_status':'PARTIAL' if item['terms'].get('free_shares_per_old_share') is not None else 'UNKNOWN',
             'listed_instrument_continuity_status':'UNKNOWN','status':'UNKNOWN','current_security_master_used':False,
             'source_sha256':item['source_sha256'],'authority':AUTHORITY})
    supplemental=[{'event_id':'SUPPLEMENTAL:2327:2025-08-25','ticker':'2327','effective_date':'2025-08-25',
                  'category':'SPLIT_SHARE_CONVERSION','new_shares_per_old_share':'4','last_trading_date':'2025-08-13',
                  'suspension_start':'2025-08-14','suspension_end':'2025-08-22','resumption_date':'2025-08-25',
                  'source_sha256':read(baseline/'CASE_FINDINGS.json')['document_review'][1]['response_sha256'],'authority':AUTHORITY},
                 {'event_id':'SUPPLEMENTAL:3090:2025-07-15','ticker':'3090','effective_date':'2025-07-15',
                  'category':'SUSPENSION','suspension_start':'2025-07-15','suspension_end':None,
                  'observed_next_trade_date':'2025-07-16',
                  'source_sha256':read(baseline/'CASE_FINDINGS.json')['document_review'][0]['response_sha256'],'authority':AUTHORITY}]
    for event in supplemental:
        identities.append({**event,'old_ticker':event['ticker'],'new_ticker':None,'old_security_id':None,'new_security_id':None,
                           'status':'UNKNOWN','economic_continuity_status':'PROVEN_RATIO_ONLY' if event['ticker']=='2327' else 'NOT_APPLICABLE',
                           'listed_instrument_continuity_status':'UNKNOWN','current_security_master_used':False})
    write_lines(OUT/'EVENT_CLASSIFICATION.jsonl',classes)
    write_lines(OUT/'IDENTITY_TRANSITIONS.jsonl',identities)
    write_lines(OUT/'SUPPLEMENTAL_EVENTS.jsonl',supplemental)
    by_ticker=defaultdict(list)
    for event in events+supplemental:by_ticker[event['ticker']].append(event)
    with gzip.open(RESET/'results/stage_b/TWSE_ELECTRONICS_DAILY_2023_2025.csv.gz','rt') as f:
        prices={(r['date'],r['ticker']):r for r in csv.DictReader(f)}
    limits={r['ticker']:r for r in normalized['opening_references_20250407']}
    impacts=[];executions=[];counts=Counter()
    for trial in trials:
        observed=trial.pop('events');impacts.append({**trial,'row_type':'TRIAL_INVENTORY','authority':AUTHORITY})
        counts['all_trials']+=1;counts[trial['window_status']]+=1
        for index,window in enumerate(observed or []):
            key=trial['trial_id']+':WINDOW:'+str(index);hits=[]
            for ticker in tickers(window):
                for event in by_ticker[ticker]:
                    phase=intersects(event,window)
                    if phase is None and event.get('suspension_start'):
                        end=event.get('suspension_end') or event.get('observed_next_trade_date')
                        if end and event['suspension_start']<=window['exit_date'] and end>=window['entry_date']:phase='SUSPENSION_WINDOW'
                    if phase:
                        terms=latest.get(event['event_id'],{}).get('terms',{})
                        missing=[k for k in TERM_FIELDS if terms.get(k) is None]
                        hits.append({'event_id':event['event_id'],'ticker':ticker,'phase':phase,'missing_fields':missing,
                                     'entitlement_from_pre_ex_ownership':window['entry_date']<event['effective_date']<=window['exit_date'],
                                     'observation_status':'BLOCKED_MISSING_TERMS_OR_IDENTITY'})
            impacts.append({'row_type':'RETAINED_OBSERVATION','observation_id':key,'trial_id':trial['trial_id'],
                'signal_date':window['signal_date'],'entry_date':window['entry_date'],'exit_date':window['exit_date'],
                'tickers':tickers(window),'original_treatment':window.get('status','COMPLETE_RAW_PRICE'),
                'original_censor_reasons':window.get('reasons',[]),'intersections':hits,
                'action_validity':'BLOCKED' if hits else 'NO_RETAINED_EVENT_INTERSECTION_NOT_COMPLETE_ACTION_CLEARANCE',
                'execution_validity':'UNKNOWN','authority':AUTHORITY})
            counts['retained_observations']+=1
            if hits:counts['observations_with_action_intersections']+=1
            for h in hits:counts['intersections_'+h['phase']]+=1
            for side,day,pricekey in (('BUY',window['entry_date'],'open'),('SELL',window['exit_date'],'close')):
                for ticker in tickers(window):
                    row=prices.get((day,ticker),{});value=row.get(pricekey) or None
                    one=all(row.get(k) for k in ('open','high','low','close')) and len({row[k] for k in ('open','high','low','close')})==1
                    ref=limits.get(ticker) if day=='2025-04-07' else None
                    lower=bool(ref and value and Decimal(value)==Decimal(str(ref['lower_limit'])))
                    counts['intended_constituent_order_legs']+=1
                    if not one and not lower:continue
                    executions.append({**fill_evidence(side,bool(one),lower,row.get('volume_shares')),
                        'observation_id':key,'trial_id':trial['trial_id'],'ticker':ticker,'intended_date':day,
                        'intended_decision_context':'AFTER_SIGNAL_SESSION_CLOSE_FIXED_HORIZON',
                        'decision_timestamp_exact':None,'intended_order_type':'NOT_RETAINED',
                        'price_assumption':'NEXT_SESSION_OPEN' if side=='BUY' else 'FIXED_HORIZON_CLOSE',
                        'observed_daily_price':value,'official_reference':ref,'daily_ohlc':{k:row.get(k) for k in ('open','high','low','close')},
                        'one_price':bool(one),'quantity_or_capital_size':None})
    write_lines(OUT/'HISTORICAL_IMPACT_MAP.jsonl',impacts)
    # Compress the extensive per-ticker execution evidence without dropping rows.
    write_lines(OUT/'EXECUTION_EVIDENCE.jsonl',executions)
    coverage={'authority':AUTHORITY,'global_event_denominator':1151,'classification_records':len(classes),
        'classification_counts':dict(Counter(r['category'] for r in classes)),
        'entitlement_assertions':len(assertions),'latest_entitlement_status_counts':dict(Counter(a['status'] for a in latest.values())),
        'numeric_cash_terms_known':sum(a['terms']['cash_per_old_share'] is not None for a in latest.values()),
        'payment_dates_known':sum(a['terms']['cash_payment_date'] is not None for a in latest.values()),
        'delivery_dates_known':sum(a['terms']['new_share_saleable_date'] is not None for a in latest.values()),
        'listed_security_id_transitions_proven':0,'economic_conversion_ratios_proven_supplemental':1,
        'historical_impact_coverage':dict(counts),'execution_records':len(executions),
        'fill_status_counts':dict(Counter(r['fill_status'] for r in executions)),
        'original_first_seen_proven':0,'revision_lineage_proven':0,'new_model_evaluations':0,'prior_model_evaluations':8529}
    write(OUT/'COVERAGE_V2.json',coverage)
    write(OUT/'READINESS_V2.json',{'status':'BLOCKED_DATA_READINESS','authority':AUTHORITY,'new_model_evaluations':0,
        'coverage':coverage,'block_reasons':['UNRETAINED_HISTORICAL_TRADE_WINDOWS','ENTITLEMENT_PAYMENT_DELIVERY_INCOMPLETE',
            'LISTED_SECURITY_IDENTITIES_UNKNOWN','AUCTION_ORDER_ALLOCATION_UNKNOWN','FIRST_SEEN_REVISION_UNKNOWN'],
        'partial_scope_ready':False,'admissible_adjusted_pnl_scope':[],
        'narrower_future_scope':'Retrospective source-field and corporate-action forensics only; no adjusted-PnL or model study is authorized.',
        'adjusted_return_engine':'BLOCKED_NOT_IMPLEMENTED','diagnostic_obligation_states_only':True,
        'next_action':'STOP_FOR_HUMAN_REVIEW; no model run even if a future scope is made ready'})
    print(json.dumps(coverage,ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('inventory','collect','build'))
    args=parser.parse_args()
    if args.action=='inventory':print(json.dumps({'events':len(original_events()),'trials':len(trials_and_windows())}))
    elif args.action=='collect':collect()
    else:build()
