"""Offline byte, schema and case-corroboration audit; no model evaluation."""
from decimal import Decimal
import csv
import gzip
import json
from pathlib import Path
import sys

import evidence as e
import normalize as n


def audit():
    output = e.HERE/'results'
    e.audit(output)
    additional = json.loads((output/'NORMALIZED_ADDITIONAL_EVIDENCE.json').read_text())
    if n.build(output) != additional:
        raise ValueError('ADDITIONAL_EVIDENCE_DRIFT')
    sys.path.insert(0, str(e.HERE.parent/'continuation_20261023'))
    from audit_checkpoint import verify
    verify(e.HERE)
    probes = json.loads((output/'EXPLORATORY_PROBES.json').read_text())
    if probes['authority'] != e.AUTHORITY or len(probes['records']) != 5:
        raise ValueError('PROBE_INVENTORY_OR_AUTHORITY_MISMATCH')
    for record in probes['records']:
        archived = (output/record['archive']).read_bytes()
        if e.sha(archived) != record['archive_sha256'] or e.sha(gzip.decompress(archived)) != record['response_sha256']:
            raise ValueError('PROBE_HASH_MISMATCH')
    findings = json.loads((output/'CASE_FINDINGS.json').read_text())
    manifest = json.loads((output/'MANIFEST.json').read_text())
    if (findings['authority'] != e.AUTHORITY or findings['new_model_evaluations'] != 0
            or findings['source_manifest_sha256'] != e.sha((output/'MANIFEST.json').read_bytes())
            or findings['old_trial_outcomes_modified'] is not False
            or findings['two_specific_action_terms'] != additional['specific_action_terms']):
        raise ValueError('FINDINGS_PROVENANCE_OR_AUTHORITY_DRIFT')
    records = {r['id']:r for r in manifest['records']}
    for review in findings['document_review']:
        if review['response_sha256'] != records[review['document_id']]['response_sha256']:
            raise ValueError('REVIEW_DOCUMENT_HASH_MISMATCH')
    parent = e.HERE.parent
    mother = parent/'results/stage_b/TWSE_ELECTRONICS_DAILY_2023_2025.csv.gz'
    if e.sha(mother.read_bytes()) != 'e3012612fcf3c38c05f5c7defdf7160a0de481db21ca6381ab53178091ad3f6b':
        raise ValueError('FROZEN_MOTHER_DRIFT')
    with gzip.open(mother, 'rt') as stream:
        rows = {(r['date'],r['ticker']):r for r in csv.DictReader(stream)}
    references = {r['ticker']:r for r in additional['opening_references_20250407']}
    expected = set()
    for file in (parent/'continuation_20261023/results').glob('*_MODEL.json'):
        for event in json.loads(file.read_text())['events']:
            for reason in event.get('reasons', []):
                if reason['date'] == '2025-04-07' and reason['reason'] == 'LIMIT_LOCKED_OR_UNFILLABLE_ENTRY':
                    expected.add(reason['ticker'])
    if {r['ticker'] for r in findings['one_price_lower_limit_cases']} != expected:
        raise ValueError('CASE_INVENTORY_MISMATCH')
    for case in findings['one_price_lower_limit_cases']:
        row, ref = rows[(case['date'],case['ticker'])], references[case['ticker']]
        price = Decimal(row['open'])
        if (any(Decimal(row[k]) != price for k in ('open','high','low','close'))
                or Decimal(str(ref['lower_limit'])) != price
                or Decimal(case['observed_daily_price']) != price
                or Decimal(case['official_lower_limit']) != price
                or case['buy_fill_proven'] is not False or case['sell_fill_proven'] is not False):
            raise ValueError('CASE_PRICE_OR_FILL_CLAIM_DRIFT')
    print(json.dumps({'audit':'PASS', 'validated_dividend_events':len(json.loads((output/'ELECTRONICS_EVENTS.json').read_text())['events']),
                      'validated_reductions':sum(len(r['events']) for r in additional['reduction_projections']),
                      'verified_one_price_lower_limit_cases':len(expected), 'new_model_evaluations':0,
                      'readiness':'BLOCKED_DATA_READINESS'}))


if __name__ == '__main__':
    audit()
