"""Separate custody actor: retain immutable independent ledger checkpoints.

Requires independently controlled storage outside the repository/ledger tree.
Deployment identity, ACL/WORM and retention need human approval. No key, custody
service or independent identity is provisioned by this implementation.
"""
import argparse
from datetime import datetime,timezone
import os
from pathlib import Path
import re
import sys
import tempfile
from jsonschema.exceptions import ValidationError

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from research.phase2_governance import governance as g
from research.phase2_governance import ledger_store as store
from research.phase1_audit import ledger as audit

FIELDS={'schema_version','ledger_id','generation','record_count','head_sha256','prefix_sha256',
 'previous_checkpoint_sha256','checkpoint_sha256','custodian_id','recorded_at',*g.ZERO}


def read_anchor(root):
    previous=audit.GENESIS;last=None
    files=sorted(Path(root).glob('*.json'))
    g.need(bool(files),'INDEPENDENT_ANCHOR_MISSING')
    for generation,path in enumerate(files):
        store.regular(path);row=g.metadata(path);g.zero(row)
        g.need(path.name==f'{generation:012d}.json' and set(row)==FIELDS and type(row['schema_version']) is int and row['schema_version']==1 and
               type(row['generation']) is int and row['generation']==generation and
               type(row['record_count']) is int and row['record_count']==generation,'UNKNOWN_OR_TRUNCATED_CHECKPOINT_CONTRACT')
        for key in ('head_sha256','prefix_sha256','previous_checkpoint_sha256','checkpoint_sha256'):
            g.need(isinstance(row[key],str) and re.fullmatch('[0-9a-f]{64}',row[key]),'MALFORMED_CHECKPOINT_HASH')
        g.need(row['previous_checkpoint_sha256']==previous and
               row['checkpoint_sha256']==g.sha(g.canonical({k:v for k,v in row.items() if k!='checkpoint_sha256'})),
               'INDEPENDENT_CHECKPOINT_CORRUPTED')
        g.need(bool(row['custodian_id']) and row['ledger_id']==store.contract()['ledger_id'],'UNKNOWN_CUSTODIAN_OR_LEDGER')
        g.need(datetime.fromisoformat(row['recorded_at']).tzinfo is not None,'NAIVE_CHECKPOINT_TIME')
        if last:g.need(row['recorded_at']>=last['recorded_at'],'CHECKPOINT_TIME_REGRESSION')
        previous=row['checkpoint_sha256'];last=row
    return last


def retain(root,row):
    """Atomic write-once checkpoint; neither a mutable latest nor ledger rewrite."""
    row={**row,**g.ZERO};row['checkpoint_sha256']=g.sha(g.canonical(row))
    path=Path(root)/f"{row['generation']:012d}.json"
    with tempfile.NamedTemporaryFile(dir=root,prefix='.pending-',delete=False) as f:
        f.write(g.canonical(row)+b'\n');f.flush();os.fsync(f.fileno());temp=Path(f.name)
    try:os.link(temp,path)  # atomic create-if-absent; existing checkpoints cannot be replaced
    finally:temp.unlink()
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return row


def checkpoint(directory,custody_root,expected_checkpoint,custodian_id,initialize=False):
    root=store.external_root(custody_root,directory);g.need(isinstance(custodian_id,str) and bool(custodian_id.strip()),'CUSTODIAN_ID_REQUIRED')
    with store.locked(root,'.custodian.lock'),store.locked(directory,'.appender.lock'):
        raw=store.ledger_path(directory).read_bytes();rows=store.decode(raw)
        if initialize:
            g.need(not list(root.glob('*.json')) and raw==b'' and expected_checkpoint==audit.GENESIS,'ONLY_EMPTY_GENESIS_INITIALIZATION_ALLOWED')
            generation=0;previous=audit.GENESIS
        else:
            old=read_anchor(root);g.need(old['checkpoint_sha256']==expected_checkpoint,'CHECKPOINT_CAS_REJECTED')
            g.need(len(rows)==old['record_count']+1,'CHECKPOINT_REQUIRES_EXACTLY_ONE_APPEND')
            prefix=b''.join(g.canonical(x)+b'\n' for x in rows[:old['record_count']])
            g.need(store.summary(prefix)=={k:old[k] for k in ('record_count','head_sha256','prefix_sha256')},'INDEPENDENT_ANCHOR_PREFIX_MISMATCH')
            audit.validate_extension(rows[:-1],rows,{k:old[k] for k in ('record_count','head_sha256')})
            generation=old['generation']+1;previous=old['checkpoint_sha256']
        return retain(root,dict(schema_version=1,ledger_id=store.contract()['ledger_id'],generation=generation,
            **store.summary(raw),previous_checkpoint_sha256=previous,custodian_id=custodian_id,
            recorded_at=datetime.now(timezone.utc).isoformat()))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('initialize-empty','checkpoint'))
    p.add_argument('--ledger',type=Path,required=True);p.add_argument('--custody-root',type=Path,required=True)
    p.add_argument('--expected-checkpoint',required=True);p.add_argument('--custodian-id',required=True);a=p.parse_args()
    try:
        result=checkpoint(a.ledger,a.custody_root,a.expected_checkpoint,a.custodian_id,a.mode=='initialize-empty')
        print(g.canonical(result).decode());return 0
    except (ValueError,OSError,TypeError,KeyError,ValidationError) as exc:
        print(g.canonical(dict(status='BLOCKED',reason=str(exc),**g.ZERO)).decode());return 2


if __name__=='__main__':raise SystemExit(main())
