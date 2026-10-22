"""Append-only schema-v1 audit storage; appender never writes custody anchors."""
import argparse
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import sys
from jsonschema.exceptions import ValidationError

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from research.phase1_audit import ledger as audit
from research.phase2_governance import governance as g


def regular(path):
    path=Path(path)
    g.need(not any(p.is_symlink() for p in (path,*path.parents)),'SYMLINK_STORAGE_FORBIDDEN')
    if path.exists():g.need(path.is_file(),'NON_REGULAR_STORAGE')
    return path


def ledger_path(directory):
    directory=Path(directory).absolute();regular(directory/'experiments.jsonl');directory=directory.resolve()
    path=regular(directory/'experiments.jsonl')
    if directory.is_relative_to(ROOT):
        g.need(directory==g.HERE/'ledger','ONLY_RESEARCH_LEDGER_DESTINATION_ALLOWED')
    g.need(path.exists(),'LEDGER_MUST_BE_EXPLICITLY_INITIALIZED')
    return path


@contextmanager
def locked(directory,name):
    path=regular(Path(directory)/name)
    fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX);yield
    finally:os.close(fd)


def validate_records(records):
    validator=g.schema('experiment');by_id={}
    for record in records:
        validator.validate(record)
        if record['parent_id'] in by_id:
            g.need(by_id[record['parent_id']]['engine']==record['engine'],'CROSS_ENGINE_PARENT_FORBIDDEN')
        by_id[record['experiment_id']]=record
    return audit.validate_ledger(records)


def decode(raw):
    g.need(not raw or raw.endswith(b'\n'),'PARTIAL_LEDGER_TAIL_STOP_NO_AUTOMATIC_TRUNCATION')
    rows=[]
    for line in raw.splitlines():
        row=g.parse(line);g.need(g.canonical(row)==line,'NONCANONICAL_LEDGER_BYTES');rows.append(row)
    validate_records(rows);return rows


def summary(raw):return {**validate_records(decode(raw)),'prefix_sha256':g.sha(raw)}


def external_root(root,directory):
    root=Path(root).absolute();regular(root/'probe');root=root.resolve();directory=Path(directory).resolve()
    g.need(root.is_dir() and not root.is_relative_to(ROOT) and not root.is_relative_to(Path(directory).absolute()) and
           not Path(directory).absolute().is_relative_to(root),'ANCHOR_MUST_BE_OUTSIDE_REPOSITORY_AND_LEDGER_TREE')
    return root


def contract():
    c=g.metadata(g.HERE/'ledger-contract.json');g.zero(c)
    g.need(c['append_only'] is True and c['anchor_required'] is True and c['phase2_authorized'] is False and
           type(c['record_capital_authority']) is int and c['record_capital_authority']==0 and
           c['record_phase2_authorized'] is False and c['ledger_id']=='HENGCE_RESEARCH_GOVERNANCE_V1' and
           c['record_schema_sha256']==g.sha((ROOT/'research/phase1_audit/experiment.schema.json').read_bytes()),'UNKNOWN_LEDGER_CONTRACT')
    return c


def verified(directory,custody_root,expected_checkpoint):
    from research.phase2_governance.checkpoint import read_anchor
    root=external_root(custody_root,directory);anchor=read_anchor(root)
    g.need(anchor['checkpoint_sha256']==expected_checkpoint,'STALE_OR_UNTRUSTED_CHECKPOINT')
    g.need(anchor['ledger_id']==contract()['ledger_id'],'EXTERNAL_ANCHOR_LEDGER_ID_MISMATCH')
    raw=ledger_path(directory).read_bytes()
    g.need(summary(raw)=={k:anchor[k] for k in ('record_count','head_sha256','prefix_sha256')},
           'EXTERNAL_ANCHOR_MISMATCH_OR_UNCHECKPOINTED_TAIL')
    return raw,anchor


def append(directory,custody_root,expected_checkpoint,record):
    """One exact append; separate custodian must checkpoint before another append.

    This logs metadata only. It does not authorize or execute the recorded trial.
    A partial write stays visible and blocks later operations, without rollback.
    """
    directory=Path(directory);path=ledger_path(directory)
    with locked(directory,'.appender.lock'):
        raw,anchor=verified(directory,custody_root,expected_checkpoint)
        rows=decode(raw);next_rows=[*rows,record]
        validate_records(next_rows)
        audit.validate_extension(rows,next_rows,{k:anchor[k] for k in ('record_count','head_sha256')})
        encoded=g.canonical(record)+b'\n'
        fd=os.open(path,os.O_WRONLY|os.O_APPEND|os.O_NOFOLLOW)
        try:
            view=memoryview(encoded)
            while view:
                n=os.write(fd,view);g.need(n>0,'LEDGER_APPEND_FAILED');view=view[n:]
            os.fsync(fd)
        finally:os.close(fd)
        g.need(path.read_bytes()==raw+encoded,'CONCURRENT_OR_PARTIAL_LEDGER_WRITE')
        return dict(status='APPENDED_PENDING_INDEPENDENT_CHECKPOINT',**summary(raw+encoded),**g.ZERO)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('verify','append','check-run'))
    parser.add_argument('--ledger',type=Path,default=g.HERE/'ledger')
    parser.add_argument('--custody-root',type=Path);parser.add_argument('--expected-checkpoint');parser.add_argument('--record',type=Path)
    args=parser.parse_args()
    try:
        g.validate_policy(g.metadata(g.HERE/'phase2-policy.json'))
        if args.mode=='check-run':g.require_phase2_run(g.metadata(g.HERE/'phase2-policy.json'))
        g.need(args.custody_root is not None and bool(args.expected_checkpoint),'INDEPENDENT_CUSTODY_CHECKPOINT_REQUIRED')
        if args.mode=='verify':verified(args.ledger,args.custody_root,args.expected_checkpoint)
        else:
            g.need(args.record is not None,'RECORD_REQUIRED')
            append(args.ledger,args.custody_root,args.expected_checkpoint,g.metadata(args.record))
        return 0
    except (ValueError,OSError,TypeError,KeyError,ValidationError) as exc:
        print(g.canonical(dict(status='BLOCKED',reason=str(exc),**g.ZERO)).decode());return 2


if __name__=='__main__':raise SystemExit(main())
