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
import hengce_twse_calendar as twse_calendar

LEGACY_RADAR_DISABLED_REASON = (
    'LEGACY_RADAR_DISABLED_USE_Q017_IMMUTABLE_0901_DECISION_LOCK_AND_LOCKED_MONITOR'
)


def radar_run(today=None):
    """Permanent kill switch for the pre-decision-lock schema-v1 radar."""
    raise RuntimeError(LEGACY_RADAR_DISABLED_REASON)


def _twse_session(target_date):
    manifest, manifest_path, lineage = twse_calendar.load_manifest()
    trading_day = twse_calendar.is_trading_day(target_date, manifest)
    return trading_day, {
        'market_calendar_date': target_date.isoformat(),
        'market_calendar_trading_day': trading_day,
        'market_calendar_authority': manifest.get('authority'),
        'market_calendar_fingerprint_sha256': twse_calendar.manifest_fingerprint(manifest),
        'market_calendar_lineage_sha256': lineage,
        'market_calendar_manifest': str(manifest_path),
    }


def _closed_session_receipt(mode, target_date, calendar_meta):
    receipt = {
        'system': 'HENGCE',
        'module': 'DAILY_COMMAND_CENTER',
        'mode': mode,
        'target_date': target_date.isoformat(),
        'generated_at_taipei': now_tw().isoformat(),
        'status': 'SKIP_NONTRADING',
        'reason': 'TWSE_EFFECTIVE_CALENDAR_CLOSED',
        'downstream_ready': False,
        'ranking_authority': False,
        'signal_authority': False,
        'capital_authority': False,
        'broker_order_execution': False,
        'policy': 'FAIL_CLOSED_EFFECTIVE_TWSE_CALENDAR_NO_DOWNLOAD_NO_PROMOTION',
        **calendar_meta,
    }
    out = ROOT / 'shadow' / 'command_center' / (
        target_date.strftime('%Y%m%d') + '_' + mode + '_MARKET_CLOSED.json'
    )
    atomic_json(out, receipt)
    return receipt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['self-test', 'premarket', 'radar', 'postclose'], required=True)
    ap.add_argument('--date')
    args = ap.parse_args()
    target = datetime.strptime(args.date, '%Y-%m-%d').date() if args.date else None

    if args.mode == 'self-test':
        self_test()
        closed, _ = _twse_session(datetime.strptime('2026-10-23', '%Y-%m-%d').date())
        opened, _ = _twse_session(datetime.strptime('2026-10-22', '%Y-%m-%d').date())
        manifest, _, _ = twse_calendar.load_manifest()
        assert closed is False
        assert opened is True
        assert twse_calendar.next_trading_day('2026-10-22', manifest) == '2026-10-27'
        print(json.dumps({
            'legacy_radar_kill_switch': 'PASS',
            'legacy_radar_callable': False,
            'formal_q017_path': 'hengce_q017_decision_lock.py',
            'effective_twse_calendar_guard': 'PASS',
            'extraordinary_closure_2026_10_23': 'PASS',
            'next_trading_day_after_2026_10_22': '2026-10-27',
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
        run_date = target or now_tw().date()
        trading_day, calendar_meta = _twse_session(run_date)
        if not trading_day:
            result = _closed_session_receipt(args.mode, run_date, calendar_meta)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        if args.mode == 'premarket':
            result = premarket(run_date)
        else:
            import hengce_eod_incremental_ingest as eod_inc
            today = run_date
            eod = eod_inc.ingest(today)
            if eod.get('status') in {'SKIP_WEEKEND', 'SKIP_NONTRADING'}:
                result = eod
            else:
                downstream_ready = eod.get('downstream_ready') is True
                if downstream_ready:
                    elec = append_electronics_day(today)
                    sox = refresh_sox(today)
                else:
                    elec = {'status':'PENDING','date':today.isoformat(),'reason':'MOTHER_NOT_COMPLETE'}
                    sox = {'status':'PENDING','date':today.isoformat(),'reason':'MOTHER_NOT_COMPLETE'}
                result = {'system':'HENGCE','module':'POSTCLOSE_DATA_GATE','generated_at_taipei':now_tw().isoformat(),'status':'PASS' if eod.get('three_leg_complete') and downstream_ready else 'PARTIAL','downstream_ready':downstream_ready,'eod':eod,'electronics_history_append':elec,'sox':sox,'policy':'MOTHER_FIRST_ORIGINAL_VESSEL_INCREMENTAL_EOD_NO_WAIT_FOR_MARGIN','market_calendar':calendar_meta}
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
