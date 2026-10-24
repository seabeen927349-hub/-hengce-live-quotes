#!/usr/bin/env python3
"""Offline verification of completed evidence. Does not run any model trial."""
from collections import Counter
import csv,gzip,hashlib,io,json,math,zipfile
from pathlib import Path
from reset_ledger import AUTHORITY,digest
from stage_b_build_twse_year import RESET,load_expected,validate_daily,decode

RESULTS=RESET/'results'
def sha(data):return hashlib.sha256(data).hexdigest()
def read(path):return json.loads(path.read_text())
def require(condition,reason):
    if not condition:raise ValueError(reason)

def audit():
    manifest=read(RESULTS/'ARTIFACT_MANIFEST.json')
    for item in manifest['artifacts']:
        require(sha((RESULTS/item['path']).read_bytes())==item['zip_sha256'],'ARTIFACT_ZIP_SHA_MISMATCH')
    stage_b=RESULTS/'stage_b'
    receipt=read(stage_b/'TWSE_MOTHER_RECEIPT.json')
    require(receipt['status']=='PASS_EXACT_MEMBERSHIP_SET' and receipt['failed_dates']==0,'MOTHER_NOT_PASS')
    mother=stage_b/receipt['mother_path'];qa=stage_b/receipt['qa_path']
    require(sha(mother.read_bytes())==receipt['mother_sha256'],'MOTHER_SHA_MISMATCH')
    require(sha(qa.read_bytes())==receipt['qa_sha256'],'QA_SHA_MISMATCH')
    expected={}
    for year in (2023,2024,2025):
        daily,_,_=load_expected(year);expected.update(daily)
    with gzip.open(mother,'rt') as stream:
        rows=list(csv.DictReader(stream))
    keys=[(r['date'],r['ticker']) for r in rows]
    require(len(keys)==len(set(keys)) and set(keys)=={(d,t) for d,ts in expected.items() for t in ts},'EXACT_MEMBERSHIP_FAILED')
    by_key={(r['date'],r['ticker']):r for r in rows}
    qa_rows=[json.loads(line) for line in qa.read_text().splitlines()]
    require(len(qa_rows)==len(expected) and {q['date'] for q in qa_rows}==set(expected),'QA_DATE_SET_MISMATCH')
    with zipfile.ZipFile(RESULTS/'artifacts/stage_b_39936974870.zip') as archive:
        for q in qa_rows:
            require(q['status']=='PASS','NONPASS_DATE')
            compressed=archive.read(q['raw_source_path'])
            require(sha(compressed)==q['raw_archive_sha256'],'RAW_ARCHIVE_SHA_MISMATCH')
            raw=gzip.decompress(compressed)
            require(sha(raw)==q['response_sha256'],'RAW_RESPONSE_SHA_MISMATCH')
            records,checked=validate_daily(decode(raw),q['date'],expected[q['date']])
            require(checked['status']=='PASS','RAW_REVALIDATION_FAILED')
            for r in records:
                actual=by_key[(q['date'],r['ticker'])]
                require(all(actual[k]==r[k] for k in ('ticker','open','high','low','close','volume_shares','turnover_ntd')),'MOTHER_RAW_VALUE_MISMATCH')
    output=RESULTS/'stage_c';attempt=output/'runs/39937394677-1'
    search_receipt=read(attempt/'SEARCH_RUN_RECEIPT.json')
    for key,name in [('trial_summary_sha256','TRIAL_SUMMARY.json'),('baseline_sha256','BASELINE_REPRODUCTION.json'),('pareto_sha256','PARETO_FRONTIER.json'),('winner_sha256','WINNER_OR_NO_WINNER.json')]:
        require(sha((attempt/name).read_bytes())==search_receipt[key],'SEARCH_OUTPUT_SHA_MISMATCH:'+name)
    ledger=output/'EXPERIMENT_LEDGER.jsonl'
    with zipfile.ZipFile(RESULTS/'artifacts/stage_c_39937394677.zip') as archive:
        prefix=archive.read('runs/39937394677-1/EXPERIMENT_LEDGER.jsonl')
        require(sha(prefix)==search_receipt['ledger_sha256'],'LEDGER_PREFIX_RECEIPT_MISMATCH')
        require(ledger.read_bytes().startswith(archive.read('EXPERIMENT_LEDGER.jsonl')) and ledger.read_bytes().startswith(prefix),'LEDGER_ARCHIVE_OR_PREFIX_MISMATCH')
    previous='0'*64;ids=set();started=set();terminal=set();counts=Counter()
    for line in ledger.read_text().splitlines():
        record=json.loads(line);claimed=record.pop('record_hash')
        require(record['record_id'] not in ids and record['previous_hash']==previous and digest(record)==claimed,'LEDGER_CHAIN_OR_DUPLICATE_FAILURE')
        require(record['authority']==AUTHORITY,'LEDGER_AUTHORITY_DRIFT')
        provenance=record['provenance']
        if provenance.get('study')=='PINNED_E2_BASELINE_V2':
            require(provenance['diagnostic_code_sha256']==sha((RESET/'baseline_reproduction_v2.py').read_bytes()),'BASELINE_DIAGNOSTIC_CODE_DRIFT')
            require(provenance['plan_sha256']==sha((RESET/'BASELINE_REPRODUCTION_V2_PLAN.json').read_bytes()),'BASELINE_PLAN_DRIFT')
            if record['status']=='EVALUATED':
                require(record['result_sha256']==sha((RESULTS/'BASELINE_REPRODUCTION_V2.json').read_bytes()),'BASELINE_RESULT_SHA_MISMATCH')
        else:
            require(provenance['code_sha256']==sha((RESET/'stage_c_rule_search.py').read_bytes()),'SEARCH_CODE_DRIFT')
            require(provenance['method_corrections_sha256']==sha((RESET/'METHOD_CORRECTIONS_V1.json').read_bytes()),'PREREGISTERED_METHOD_DRIFT')
        previous=claimed;ids.add(record['record_id']);counts[record['status']]+=1
        if record['status']=='STARTED':started.add(record['experiment_id'])
        if record['status'] in {'EVALUATED','NO_TRADE','FAILED','ABORTED'} and record.get('experiment_id'):terminal.add(record['experiment_id'])
    require(started==terminal and len(started)==8505,'INCOMPLETE_EVALUATION_JOURNAL')
    summary=read(attempt/'TRIAL_SUMMARY.json')
    require(summary['selection_trial_count']==8400 and summary['all_evaluation_count']==8504,'TRIAL_COUNTS_MISMATCH')
    require(summary['mother_sha256']==receipt['mother_sha256'],'SEARCH_MOTHER_BINDING_MISMATCH')
    for family in summary['families'].values():
        for name,fold in family['folds'].items():
            if fold['status']!='SELECTED_AND_VALIDATED':continue
            start,end=('2024-01-01','2024-12-31') if name=='F1' else ('2025-01-01','2025-12-31')
            for cost_key,events in fold['events'].items():
                cost=float(cost_key[5:]);nav=1.;wins=0
                for event in events:
                    require(start<=event['signal_date']<event['entry_date']<=event['exit_date']<=end,'FOLD_LEAKAGE')
                    require(all(t in expected[event['signal_date']] for t in event['tickers']),'SIGNAL_SCOPE_LEAKAGE')
                    require(len(event['tickers'])==fold['selected_config']['top_n'],'PARTIAL_BASKET')
                    nav*=1+event['gross_return']-cost;wins+=event['gross_return']-cost>0
                metrics=fold['validation'][cost_key]
                require(math.isclose(nav-1,metrics['compounded_return'],abs_tol=1e-12) and wins==metrics['wins'],'COST_OR_EVENT_METRIC_MISMATCH')
    decision=read(attempt/'WINNER_OR_NO_WINNER.json')
    require(decision['status']=='NO_ROBUST_WINNER' and decision['winner'] is None and not any(r['eligible'] for r in summary['summary']),'DECISION_MISMATCH')
    result={'status':'PASS_OFFLINE_COMPLETED_EVIDENCE_AUDIT','stage_b_run_id':39936974870,'stage_c_run_id':39937394677,
            'verified_dates':len(expected),'verified_rows':len(rows),'raw_responses_revalidated':len(qa_rows),
            'selection_evaluations':8400,'search_model_evaluations':8504,'additional_pinned_baseline_evaluations':1,'all_model_evaluations':8505,'ledger_records':len(ids),'ledger_status_counts':dict(counts),
            'ledger_tip_hash':previous,'decision':decision['status'],'authority':AUTHORITY}
    (RESULTS/'EVIDENCE_AUDIT.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))
    return result
if __name__=='__main__':audit()
