#!/usr/bin/env python3
"""HENGCE daily command-center public entrypoint.

The historical command-center implementation is retained as a library because
Q017 decision-lock and EOD ingestion reuse its data helpers. The legacy
post-open radar is intentionally NOT authoritative and is hard-disabled here.
"""

import argparse
import json
from datetime import datetime

from hengce_daily_command_center_core_legacy import *  # noqa: F401,F403

LEGACY_RADAR_DISABLED_REASON = (
    'LEGACY_RADAR_DISABLED_USE_Q017_IMMUTABLE_0901_DECISION_LOCK_AND_LOCKED_MONITOR'
)


def radar_run(today=None):
    """Permanent kill switch for the pre-decision-lock schema-v1 radar."""
    raise RuntimeError(LEGACY_RADAR_DISABLED_REASON)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['self-test', 'premarket', 'radar', 'postclose'], required=True)
    ap.add_argument('--date')
    args = ap.parse_args()
    target = datetime.strptime(args.date, '%Y-%m-%d').date() if args.date else None

    if args.mode == 'self-test':
        self_test()
        print(json.dumps({
            'legacy_radar_kill_switch': 'PASS',
            'legacy_radar_callable': False,
            'formal_q017_path': 'hengce_q017_decision_lock.py',
        }))
        return 0

    if args.mode == 'radar':
        fail = {
            'system': 'HENGCE',
            'module': 'DAILY_COMMAND_CENTER',
            'mode': 'radar',
            'generated_at_taipei': now_tw().isoformat(),
            'status': 'DATA_PENDING',
            'authority': 'NO_FORMAL_SIGNAL',
            'formal_buy_count': 0,
            'error': LEGACY_RADAR_DISABLED_REASON,
            'policy': 'FAIL_CLOSED_NO_FORMAL_SIGNAL',
        }
        atomic_json(DATA_STATUS, fail)
        print(json.dumps(fail, ensure_ascii=False, indent=2))
        return 2

    try:
        if args.mode == 'premarket':
            result = premarket(target)
        else:
            import hengce_eod_incremental_ingest as eod_inc
            today = target or now_tw().date()
            eod = eod_inc.ingest(today)
            if eod.get('status') == 'SKIP_WEEKEND':
                result = eod
            else:
                downstream_ready = eod.get('downstream_ready') is True
                if downstream_ready:
                    elec = append_electronics_day(today)
                    sox = refresh_sox(today)
                else:
                    elec = {'status':'PENDING','date':today.isoformat(),'reason':'MOTHER_NOT_COMPLETE'}
                    sox = {'status':'PENDING','date':today.isoformat(),'reason':'MOTHER_NOT_COMPLETE'}
                result = {'system':'HENGCE','module':'POSTCLOSE_DATA_GATE','generated_at_taipei':now_tw().isoformat(),'status':'PASS' if eod.get('three_leg_complete') and downstream_ready else 'PARTIAL','downstream_ready':downstream_ready,'eod':eod,'electronics_history_append':elec,'sox':sox,'policy':'MOTHER_FIRST_ORIGINAL_VESSEL_INCREMENTAL_EOD_NO_WAIT_FOR_MARGIN'}
                atomic_json(DATA_STATUS,result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        fail = {
            'system': 'HENGCE',
            'module': 'DAILY_COMMAND_CENTER',
            'mode': args.mode,
            'generated_at_taipei': now_tw().isoformat(),
            'status': 'DATA_PENDING',
            'authority': 'NO_FORMAL_SIGNAL',
            'formal_buy_count': 0,
            'error': repr(e),
            'policy': 'FAIL_CLOSED_NO_FORMAL_SIGNAL',
        }
        atomic_json(DATA_STATUS, fail)
        print(json.dumps(fail, ensure_ascii=False, indent=2))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
