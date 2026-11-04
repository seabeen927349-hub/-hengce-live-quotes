#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, tempfile
from datetime import datetime
from pathlib import Path

import hengce_q017_observation_lock_v5 as v5
from hengce_recovery_transaction import ZERO, current_request

RADAR=v5.RADAR
BACKUP_DIR=RADAR/'backup_observations'
RECOVERY_DIR=RADAR/'recovery_receipts'
RECOVERY_DIR.mkdir(parents=True,exist_ok=True)


def backup_path(today):return BACKUP_DIR/f'{today.strftime("%Y%m%d")}_0901_observation.json'

def promote_if_needed(today, canonical_path=None, backup=None):
    cp=canonical_path or v5.obs_path(today)
    bp=backup or backup_path(today)
    if cp.exists():
        o=json.loads(cp.read_text(encoding='utf-8'));ok,reason=v5.validate_observation(o)
        if not ok:raise RuntimeError(f'CANONICAL_OBSERVATION_INVALID:{reason}')
        return o,'CANONICAL_ALREADY_PRESENT'
    if not bp.exists():raise RuntimeError('NO_CANONICAL_OR_BACKUP_0901_OBSERVATION')
    o=json.loads(bp.read_text(encoding='utf-8'));ok,reason=v5.validate_observation(o)
    if not ok:raise RuntimeError(f'BACKUP_OBSERVATION_INVALID:{reason}')
    cp.parent.mkdir(parents=True,exist_ok=True)
    text=json.dumps(o,ensure_ascii=False,indent=2)+'\n'
    try:
        cp.open('x',encoding='utf-8').write(text)
    except FileExistsError:
        existing=json.loads(cp.read_text(encoding='utf-8'))
        if existing.get('observation_snapshot_sha256')!=o.get('observation_snapshot_sha256'):
            raise RuntimeError('CANONICAL_OBSERVATION_APPEARED_WITH_DIFFERENT_HASH_DURING_RECOVERY')
        o=existing
    v5.core.atomic_json(v5.OBS_LATEST,o)
    return o,'BACKUP_PROMOTED_TO_CANONICAL'


def existing_decision(today):
    p=v5.decision_path(today)
    if not p.exists():return None
    d=json.loads(p.read_text(encoding='utf-8'))
    v5.validate_decision(d,today)
    return d


def compute(today=None):
    today=today or v5.core.now_tw().date()
    current_request('q017-recovery','compute',today.isoformat(),v5.core.now_tw())
    locked=existing_decision(today)
    if locked is not None:
        receipt={'schema_version':5,'system':'HENGCE','module':'Q017_RECOVERY_COMPUTE_V5','trade_date':today.isoformat(),'generated_at_taipei':v5.core.now_tw().isoformat(),'status':'PASS','observation_source':'DECISION_ALREADY_LOCKED','observation_snapshot_sha256':locked['observation_snapshot_sha256'],'decision_snapshot_sha256':locked['decision_snapshot_sha256'],'late_market_refetch_used':False,'idempotent_no_recompute':True,'policy':'Existing valid immutable decision wins; recovery never recomputes or reranks it.'}
        receipt.update(ZERO)
        v5.core.atomic_json(RECOVERY_DIR/f'{today.strftime("%Y%m%d")}_recovery_compute.json',receipt)
        return locked,receipt
    o,source=promote_if_needed(today)
    out=v5.compute_decision(today)
    receipt={'schema_version':5,'system':'HENGCE','module':'Q017_RECOVERY_COMPUTE_V5','trade_date':today.isoformat(),'generated_at_taipei':v5.core.now_tw().isoformat(),'status':'PASS','observation_source':source,'observation_snapshot_sha256':o['observation_snapshot_sha256'],'decision_snapshot_sha256':out['decision_snapshot_sha256'],'late_market_refetch_used':False,'idempotent_no_recompute':False,'policy':'Recovery computation may occur later, but market inputs remain the immutable 09:01 observation.'}
    receipt.update(ZERO)
    v5.core.atomic_json(RECOVERY_DIR/f'{today.strftime("%Y%m%d")}_recovery_compute.json',receipt)
    return out,receipt


def self_test():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);cp=root/'canonical.json';bp=root/'backup.json'
        payload={'observation_snapshot_sha256':'abc'};bp.write_text(json.dumps(payload),encoding='utf-8')
        original=v5.validate_observation
        original_latest=v5.OBS_LATEST
        try:
            v5.OBS_LATEST=root/'selftest_observation_latest.json'
            v5.validate_observation=lambda o:(o.get('observation_snapshot_sha256')=='abc','TEST')
            o,s=promote_if_needed(datetime(2026,10,20).date(),cp,bp)
            assert s=='BACKUP_PROMOTED_TO_CANONICAL' and cp.exists() and o['observation_snapshot_sha256']=='abc'
            o2,s2=promote_if_needed(datetime(2026,10,20).date(),cp,bp)
            assert s2=='CANONICAL_ALREADY_PRESENT'
            cp.write_text(json.dumps({'observation_snapshot_sha256':'different'}),encoding='utf-8')
            v5.validate_observation=lambda o:(True,'TEST')
            o3,s3=promote_if_needed(datetime(2026,10,20).date(),cp,bp)
            assert s3=='CANONICAL_ALREADY_PRESENT' and o3['observation_snapshot_sha256']=='different'
        finally:
            v5.validate_observation=original
            v5.OBS_LATEST=original_latest
    print(json.dumps({'self_test':'PASS','schema':5,'backup_promotion_only_when_canonical_missing':True,'existing_decision_idempotent':True,'no_market_refetch':True,'no_observation_blending':True}))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['compute','self-test'],required=True);ap.add_argument('--date');a=ap.parse_args()
    if a.mode=='self-test':self_test();return 0
    target=datetime.strptime(a.date,'%Y-%m-%d').date() if a.date else None
    try:
        out,receipt=compute(target);print(json.dumps({'decision':out,'recovery':receipt},ensure_ascii=False,indent=2));return 0
    except Exception as e:
        fail={'schema_version':5,'system':'HENGCE','module':'Q017_RECOVERY_COMPUTE_V5','generated_at_taipei':v5.core.now_tw().isoformat(),'status':'DATA_PENDING','authority':'NO_FORMAL_SIGNAL','formal_buy_count':0,'error':repr(e),'late_market_refetch_used':False,**ZERO};print(json.dumps(fail,ensure_ascii=False,indent=2));return 2

if __name__=='__main__':raise SystemExit(main())
