"""Resolve pinned corpus and historical refs without consulting moving main."""
import hashlib,json,subprocess
from pathlib import Path
from stage_b_build_twse_year import ROOT,RESET,CORPUS_BASE

def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args])
def audit():
    manifest=json.loads((RESET/'CORPUS_MANIFEST.json').read_text())
    inventory=[]
    for line in git('ls-tree','-r',CORPUS_BASE).decode().splitlines():
        meta,path=line.split('\t',1);mode,kind,oid=meta.split()
        inventory.append({'path':path,'mode':mode,'kind':kind,'git_object':oid})
    references=[]
    for ref in manifest['historical_fixed_refs']:
        sha=ref['head_sha']
        git('cat-file','-e',sha+'^{commit}')
        tree=git('ls-tree','-r',sha)
        references.append({**ref,'resolved_commit':git('rev-parse',sha+'^{commit}').decode().strip(),
                           'tree':git('rev-parse',sha+'^{tree}').decode().strip(),
                           'path_count':len(tree.splitlines()),'inventory_sha256':hashlib.sha256(tree).hexdigest()})
    critical=['research/e2_profit_max/membership','research/e2_profit_max/macro','scripts','hengce','eod','receipts','shadow']
    changes=git('diff','--name-only',CORPUS_BASE,'HEAD','--',*critical).decode().splitlines()
    if changes:raise ValueError('PINNED_DATA_OR_PRODUCTION_CHANGED:'+str(changes))
    result={'status':'PINNED_CORPUS_AND_HISTORY_RESOLVED','frozen_base':CORPUS_BASE,'tree':git('rev-parse',CORPUS_BASE+'^{tree}').decode().strip(),
            'inventory':inventory,'historical_refs':references,'production_and_data_paths_unchanged':True,
            'exposure':'2023-2026 EXPOSED; NOT PRISTINE HOLDOUT',
            'authority':{'research_only':True,'capital_authority_twd':0,'broker_order_execution':False,'production_promotion':False}}
    out=RESET/'results/CORPUS_SNAPSHOT_AUDIT.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':result['status'],'paths':len(inventory),'historical_refs':len(references)}))
if __name__=='__main__':audit()
