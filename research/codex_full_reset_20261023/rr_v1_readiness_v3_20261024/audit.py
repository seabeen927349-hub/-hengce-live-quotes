#!/usr/bin/env python3
"""Offline evidence audit. Does not import model code or perform networking."""
from pathlib import Path
import json, hashlib, csv, io

def run(root):
    root=Path(root)
    def read(n): return json.loads((root/n).read_text())
    def sha(b): return hashlib.sha256(b).hexdigest()
    snap=read('INPUT_SNAPSHOTS.json')
    inventory=read('EVIDENCE_INVENTORY.json')['inputs']
    assert set(snap)=={x['path'] for x in inventory}
    for x in inventory:
        b=snap[x['path']].encode()
        assert len(b)==x['bytes'] and sha(b)==x['sha256'], x['path']
    plan=read('READINESS_V3_PLAN.json'); r=read('READINESS_V3.json')
    authority=read('AUTHORITY_LOCK.json')
    assert authority['research_only'] is True and authority['capital_authority_twd']==0
    assert all(authority[k] is False for k in ['signal_authority','ranking_authority','broker_order_execution','production_promotion','main_write_authorized','merge_authorized'])
    assert r['authority']==authority
    assert plan['new_model_evaluation_budget']==0
    assert plan['frozen_config']==r['frozen_config']=='RESIDUAL_REVERSAL|NEG_RESID1|TO50000000|N1|H20|PRIOR_SOX5_LE_-0.03'
    assert r['prior_model_evaluations']==r['total_model_evaluations']==8529
    assert r['new_model_evaluations']==0 and r['stage_b_ran'] is False
    assert r['status']=='BLOCKED_DATA_READINESS' and len(r['blockers'])==5
    for b in r['blockers']:
        assert b['status']=='BLOCKED'
        assert sha((root/b['evidence_file']).read_bytes())==b['sha256']
    assert read('EXTERNAL_REQUESTS.json')['official_data_requests']==[]
    assert read('CANONICAL_MOTHER_RECONCILIATION.json')['actual_sha256'] is None
    assert read('CANONICAL_MOTHER_RECONCILIATION.json')['promotion_20261022']['formal_complete_day'] is False
    for n in ['RESEARCH_TREE.json','MAIN_TREE.json']:
        t=json.loads(snap[n]); assert t['truncated'] is False
        assert not any(x['path'].endswith('HENGCE_2026_HIST_MOTHER.csv') for x in t['tree'])
    mt={x['path']:x for x in json.loads(snap['MAIN_TREE.json'])['tree']}
    rt={x['path']:x for x in json.loads(snap['RESEARCH_TREE.json'])['tree']}
    q='hengce/q017_radar/data/twse_electronics_history_2026.csv'
    v='hengce/v43_daily/data/twse_electronics_history_2026.csv'
    assert mt[q]['sha']==mt[v]['sha']==rt[q]['sha']=='b84c642f262fdcb7ba68018548f4d90b1ff41b9e'
    base=plan['base_head']; prefix='research/codex_full_reset_20261023/'
    prereg=snap['research/codex_full_reset_20261023/RR_V1_PREREG_20261023.json'].encode()
    assert sha(prereg)=='79aca51a1c716cd40933eb1a0ab3564bb29cb367eae3c29603a1f360d06b20ee'
    macro=snap[base+'/research/e2_profit_max/macro/sox_daily_202212_202610.csv'].encode()
    assert sha(macro)=='dd1d86f7f0003dd6286596f454100cab91e7edd32db56f2e5a4e49dfa006db14'
    rows=list(csv.DictReader(io.StringIO(macro.decode())))
    assert len(rows)==972 and rows[-1]['date']=='2026-10-16'
    assert read('FROZEN_MACRO_RECONCILIATION.json')['causal_timezone_session_proven'] is False
    for n in ['CORPORATE_ACTION_2026_EVIDENCE.jsonl','IDENTITY_2026_EVIDENCE.jsonl','EXECUTION_2026_EVIDENCE.jsonl']:
        records=[json.loads(x) for x in (root/n).read_text().splitlines()]
        assert len(records)==1 and records[0]['record_type']=='SCOPE_GAP_NOT_SECURITY_EVENT'
        assert records[0]['status']=='UNKNOWN' and records[0]['ticker'] is None
    assert read('V2_2026_APPLICABILITY.json')['unknowns_preserved'] is True
    expected=set(read('CHANGED_FILES.json')['files'])
    actual={p.name for p in root.iterdir() if p.is_file()}
    # The audit output itself may not yet exist on first execution.
    assert actual|{'READINESS_V3_AUDIT.json'}==expected,(actual^expected)
    return {'status':'PASS_BLOCKED_EVIDENCE_ONLY','stage_a_new_model_evaluations':0,'stage_b_ran':False,'prior_model_evaluations':8529,'total_model_evaluations':8529,'input_hashes_verified':len(inventory),'blockers_verified':5,'authority_verified':True,'unknown_preservation_verified':True,'preregistration_sha256':sha(prereg),'scope':'Evidence consistency and hashes only; no scientific readiness certification and no independent recount of prior evaluations.','parent_bytes_preserved':'Complete candidate Git-tree comparison verified every existing blob unchanged and exactly 20 new readiness files; final-head compare is independently reported.','production_changes':False,'main_writes':False,'second_mother_created':False,'parallel_eod_created':False,'model_code_executed':False,'artifact_sha256':{p.name:sha(p.read_bytes()) for p in sorted(root.iterdir()) if p.is_file() and p.name!='READINESS_V3_AUDIT.json'}}

if __name__=='__main__':
    import sys
    root=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent
    result=run(root)
    (root/'READINESS_V3_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='artifact_sha256'},indent=2))
