"""CI uses independently retained base commit bytes, never a self-declared tip."""
import argparse
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from research.phase2_governance import governance as g
from research.phase2_governance import ledger_store as store

WORKFLOW='.github/workflows/hengce-governance-freeze.yml'
LEDGER='research/phase2_governance/ledger/experiments.jsonl'


def git(*args):return subprocess.check_output(['git','-C',str(g.ROOT),*args])


def check_paths(paths):
    for p in paths:
        g.need(p.startswith('research/phase2_governance/') or p==WORKFLOW,'PRODUCTION_OR_OUT_OF_SCOPE_CHANGE:'+p)


def prefix(old,new):
    store.decode(old);store.decode(new)
    g.need(new.startswith(old),'APPEND_PREFIX_BYTES_CHANGED')


def verify(base=g.BASE):
    # The default is the issue's exact base. CI additionally passes GitHub's
    # trusted PR base SHA, never a checkpoint supplied by the proposed ledger.
    # Production may legitimately advance main while this exact-base branch is
    # reviewed. Audit the PR delta from its merge base, not a tip-to-tip diff
    # that would mistake unrelated remote artifacts for branch deletions.
    ancestor=git('merge-base',base,'HEAD').decode().strip()
    changed=git('diff','--name-only',ancestor).decode().splitlines()
    untracked=git('ls-files','--others','--exclude-standard').decode().splitlines()
    check_paths(changed+untracked)
    exists=subprocess.run(['git','-C',str(g.ROOT),'cat-file','-e',base+':'+LEDGER],capture_output=True).returncode==0
    if exists:old=git('show',base+':'+LEDGER)
    else:
        known=subprocess.run(['git','-C',str(g.ROOT),'merge-base','--is-ancestor',g.BASE,base],capture_output=True).returncode==0
        g.need(known,'UNKNOWN_LEDGER_GENESIS_BASE');old=b''
    current=(g.ROOT/LEDGER).read_bytes();prefix(old,current)
    # Readiness CI must not invent even one genuine trial at this bootstrap.
    if not exists:g.need(current==b'','NO_REAL_TRIALS_IN_GOVERNANCE_BOOTSTRAP')
    g.verify_environment(runtime=False)
    g.validate_policy(g.metadata(g.HERE/'phase2-policy.json'))
    h=g.metadata(g.HERE/'holdout-state.json');g.holdout_metadata(h)
    g.need(h['state']=='UNALLOCATED' and h['open_count']==0 and h['exposed'] is False,'HOLDOUT_MUST_REMAIN_UNALLOCATED')
    return dict(status='PASS',trusted_base=base,ledger_record_count=len(store.decode(current)),
        NO_OPTIMIZER_WAS_RUN=True,phase2_authorized=False,**g.ZERO)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',default=g.BASE);a=p.parse_args()
    print(g.canonical(verify(a.base)).decode())
