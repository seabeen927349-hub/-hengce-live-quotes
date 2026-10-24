"""One-command offline V2 audit: no recollection or historical model execution."""
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import v2 as v


def evidence_inventory():
    return {str(p.relative_to(v.HERE)):v.sha(p) for folder in ('results','collection','discovery')
            for p in sorted((v.HERE/folder).glob('*')) if p.is_file() and p.suffix!='.lock'}


def audit():
    v.verify_parent()
    plan=v.read(v.HERE/'PLAN_V2.json')
    v.require(plan['new_model_evaluation_budget']==0 and plan['authority']==v.AUTHORITY,'PLAN_AUTHORITY_DRIFT')
    checkpoint=v.read(v.HERE/'EVIDENCE_CHECKPOINT.json')
    v.require(evidence_inventory()==checkpoint['sha256'],'EVIDENCE_CHECKPOINT_MISMATCH')
    requestset=v.read(v.HERE/'collection/REQUESTS.json')
    v.require(requestset['tasks']==v.collection_tasks(v.original_events(),v.trials_and_windows()),'REQUEST_SELECTION_DRIFT')
    v.require(requestset['plan_sha256']==v.sha(v.HERE/'PLAN_V2.json'),'PLAN_HASH_MISMATCH')
    v.require(requestset['collector_sha256']==v.sha(v.HERE/'collection/COLLECTOR_SOURCE.py'),'COLLECTION_SOURCE_DRIFT')
    for task in requestset['tasks']:
        file=v.HERE/'collection'/(task['id']+'.json')
        if not file.exists():continue # explicit stopped/unattempted task in derived manifest
        receipt=v.read(file)
        v.require(all(receipt[k]==x for k,x in task.items()),'COLLECTION_REQUEST_MISMATCH')
        raw=(v.HERE/'collection'/receipt['raw_path']).read_bytes()
        v.require(hashlib.sha256(raw).hexdigest()==receipt['archive_sha256'] and
                  hashlib.sha256(gzip.decompress(raw)).hexdigest()==receipt['response_sha256'],'COLLECTION_RAW_MISMATCH')
        v.require(receipt['original_first_seen_at'] is None,'INVENTED_FIRST_SEEN')
    discovery=v.read(v.HERE/'discovery/MANIFEST.json')
    review=v.read(v.HERE/'discovery/REVIEW.json')
    v.require(review['original_manifest_sha256']==v.sha(v.HERE/'discovery/MANIFEST.json') and
              review['new_model_evaluations']==0 and review['authority']==v.AUTHORITY,'DISCOVERY_REVIEW_PROVENANCE')
    dp=v.read(v.HERE/'DISCOVERY_PLAN_V2.json')
    v.require(discovery['plan_sha256']==v.sha(v.HERE/'DISCOVERY_PLAN_V2.json') and
              discovery['source_code_sha256']==v.sha(v.HERE/'discovery/DISCOVERY_SOURCE.py'),'DISCOVERY_PROVENANCE_MISMATCH')
    v.require([{k:r[k] for k in ('id','url','family')} for r in discovery['records']]==dp['sources'],'DISCOVERY_INVENTORY_MISMATCH')
    v.require(discovery['terms_promoted_to_ledger'] is False and discovery['new_model_evaluations']==0,'UNVALIDATED_DISCOVERY_AUTHORITY')
    denied=set()
    for receipt in discovery['records']:
        if receipt['family'] in denied:v.require(receipt['status']=='NOT_ATTEMPTED_AFTER_FAMILY_STOP','SOURCE_STOP_BYPASS')
        if receipt['status']=='SOURCE_FAMILY_STOP_NO_BYPASS':denied.add(receipt['family'])
        if 'raw_path' not in receipt:continue
        raw=(v.HERE/'discovery'/receipt['raw_path']).read_bytes()
        v.require(hashlib.sha256(raw).hexdigest()==receipt['archive_sha256'] and
                  hashlib.sha256(gzip.decompress(raw)).hexdigest()==receipt['response_sha256'],'DISCOVERY_RAW_MISMATCH')
        checked=[r for r in review['records'] if r['id']==receipt['id']]
        v.require(len(checked)==1 and checked[0]['source_response_sha256']==receipt['response_sha256'] and
                  checked[0]['entitlement_or_delivery_evidence_obtained'] is False,'UNPROVEN_DISCOVERY_PROMOTION')
    previous='0'*64;ids=set();latest={}
    for record in v.lines(v.OUT/'ENTITLEMENT_LEDGER.jsonl'):
        claimed=record.pop('record_hash')
        v.require(record['previous_hash']==previous and v.digest(record)==claimed and record['record_id'] not in ids,'ENTITLEMENT_CHAIN_CORRUPT')
        v.require(record['supersedes_record_hash']==latest.get(record['event_id']),'ASSERTION_SUPERSESSION_CORRUPT')
        v.require(record['authority']==v.AUTHORITY and record['status'] in ('PROVEN','PARTIAL','UNKNOWN','CONFLICT'),'ENTITLEMENT_AUTHORITY_OR_STATUS')
        ids.add(record['record_id']);latest[record['event_id']]=claimed;previous=claimed
    # Reproduce only mappings/obligation assertions from retained bytes. No
    # features, signals, returns, rankings or model trial are computed here.
    actual=v.OUT
    try:
        with tempfile.TemporaryDirectory() as td:
            v.OUT=Path(td)/'reconstructed'
            v.build()
            expected={p.name:v.sha(p) for p in v.OUT.iterdir() if p.is_file() and p.suffix!='.lock'}
            found={p.name:v.sha(p) for p in actual.iterdir() if p.is_file() and p.suffix!='.lock'}
            v.require(expected==found,'DERIVED_OUTPUT_REPRODUCTION_MISMATCH')
    finally:v.OUT=actual
    readiness=v.read(actual/'READINESS_V2.json')
    v.require(readiness['status']=='BLOCKED_DATA_READINESS' and readiness['new_model_evaluations']==0 and
              readiness['admissible_adjusted_pnl_scope']==[],'UNSUPPORTED_READINESS_PROMOTION')
    print(json.dumps({'audit':'PASS','prior_model_evaluations':8529,'new_model_evaluations':0,
                      'entitlement_assertions':len(ids),'ledger_tip':previous,'status':readiness['status']}))


if __name__=='__main__':audit()
