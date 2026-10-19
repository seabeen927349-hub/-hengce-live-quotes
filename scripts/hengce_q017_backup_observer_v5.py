#!/usr/bin/env python3
from __future__ import annotations

import argparse, json
from datetime import datetime
from pathlib import Path

import hengce_q017_observation_lock_v5 as v5

ROOT=v5.ROOT
RADAR=v5.RADAR
BACKUP_DIR=RADAR/'backup_observations'
BACKUP_HISTORY=RADAR/'backup_observation_history'
BACKUP_LATEST=RADAR/'backup_observation_latest.json'
BACKUP_STATUS=RADAR/'backup_observation_status.json'
BACKUP_ATTEMPTS=RADAR/'backup_observation_attempts'
for p in (BACKUP_DIR,BACKUP_HISTORY,BACKUP_ATTEMPTS):p.mkdir(parents=True,exist_ok=True)


def activate_backup_lane():
    # Keep this lane physically separate from formal latest/decision outputs.
    v5.OBS_DIR=BACKUP_DIR
    v5.OBS_LATEST=BACKUP_LATEST
    v5.HISTORY=BACKUP_HISTORY
    v5.v4.ATTEMPT_DIR=BACKUP_ATTEMPTS
    v5.v4.ATTEMPT_LATEST=RADAR/'backup_observation_attempt_latest.json'
    v5.v4.LATEST=BACKUP_STATUS


def observe(today=None):
    activate_backup_lane()
    out=v5.collect_observation(today)
    ok,reason=v5.validate_observation(out)
    if not ok:raise RuntimeError(f'BACKUP_OBSERVATION_INVALID:{reason}')
    receipt={
        'schema_version':5,
        'system':'HENGCE',
        'module':'Q017_0901_BACKUP_OBSERVER',
        'trade_date':out['trade_date'],
        'generated_at_taipei':v5.core.now_tw().isoformat(),
        'status':'BACKUP_OBSERVATION_READY',
        'authority':'RECOVERY_EVIDENCE_ONLY_NO_DIRECT_RANKING_AUTHORITY',
        'observation_snapshot_sha256':out['observation_snapshot_sha256'],
        'universe_sha256':(out.get('universe_lock') or {}).get('universe_sha256'),
        'provider_coverage':(out.get('data_status') or {}).get('provider_coverage'),
        'policy':'May be promoted only if canonical 09:01 observation is absent and this artifact passes schema-v5 validation.'
    }
    v5.core.atomic_json(BACKUP_STATUS,receipt)
    return out


def self_test():
    activate_backup_lane()
    assert v5.OBS_DIR==BACKUP_DIR
    assert v5.OBS_LATEST==BACKUP_LATEST
    assert v5.v4.LATEST==BACKUP_STATUS
    assert BACKUP_DIR!=RADAR/'observations'
    assert BACKUP_STATUS!=v5.LATEST
    print(json.dumps({'self_test':'PASS','schema':5,'separate_backup_lane':True,'direct_capital_authority':False,'canonical_observation_untouched':True}))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['observe','self-test'],required=True);ap.add_argument('--date');a=ap.parse_args()
    if a.mode=='self-test':self_test();return 0
    target=datetime.strptime(a.date,'%Y-%m-%d').date() if a.date else None
    try:
        out=observe(target);print(json.dumps(out,ensure_ascii=False,indent=2));return 0
    except Exception as e:
        activate_backup_lane()
        fail={'schema_version':5,'system':'HENGCE','module':'Q017_0901_BACKUP_OBSERVER','generated_at_taipei':v5.core.now_tw().isoformat(),'status':'DATA_PENDING','authority':'NO_FORMAL_SIGNAL','formal_buy_count':0,'error':repr(e)}
        v5.core.atomic_json(BACKUP_STATUS,fail);print(json.dumps(fail,ensure_ascii=False,indent=2));return 2

if __name__=='__main__':raise SystemExit(main())
