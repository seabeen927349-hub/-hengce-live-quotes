#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import importlib
import inspect

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = ROOT / '.github/workflows/hengce-q017-primary-observer.yml'
BACKUP = ROOT / '.github/workflows/hengce-q017-backup-observer.yml'
SUPERVISOR = ROOT / 'scripts/hengce_q017_observer_supervisor_v1.py'
V4 = ROOT / 'scripts/hengce_q017_decision_lock_v4.py'


def must(text: str, needle: str, label: str):
    assert needle in text, f'MISSING:{label}:{needle}'


def must_not(text: str, needle: str, label: str):
    assert needle not in text, f'FORBIDDEN:{label}:{needle}'


def main():
    p = PRIMARY.read_text(encoding='utf-8')
    b = BACKUP.read_text(encoding='utf-8')
    s = SUPERVISOR.read_text(encoding='utf-8')
    v4_text = V4.read_text(encoding='utf-8')

    # Independent early-start observers. UTC schedules map to Taipei 07:45/08:15.
    must(p, "cron: '45 23 * * 0-4'", 'PRIMARY_0745_TAIPEI')
    must(b, "cron: '15 0 * * 1-5'", 'BACKUP_0815_TAIPEI')
    must(p, 'group: hengce-q017-primary-observer', 'PRIMARY_CONCURRENCY')
    must(b, 'group: hengce-q017-backup-observer', 'BACKUP_CONCURRENCY')
    assert 'group: hengce-q017-backup-observer' not in p
    assert 'group: hengce-q017-primary-observer' not in b

    # Both scheduled lanes must use the resilient supervisor, not direct raw observe.
    must(p, 'hengce_q017_observer_supervisor_v1.py --mode observe --lane primary', 'PRIMARY_SUPERVISOR')
    must(b, 'hengce_q017_observer_supervisor_v1.py --mode observe --lane backup', 'BACKUP_SUPERVISOR')
    must_not(p, 'hengce_q017_observation_lock_v5.py --mode observe', 'PRIMARY_RAW_OBSERVE_FORBIDDEN')
    must_not(b, 'hengce_q017_backup_observer_v5.py --mode observe', 'BACKUP_RAW_OBSERVE_FORBIDDEN')

    # Failure diagnostics must persist even when capture fails.
    must(p, "if: always() && steps.mode.outputs.mode == 'observe'", 'PRIMARY_ALWAYS_PERSIST')
    must(b, "if: always() && steps.mode.outputs.mode == 'observe'", 'BACKUP_ALWAYS_PERSIST')
    must(p, 'observer_supervisor_primary_status.json', 'PRIMARY_STATUS_FILE')
    must(b, 'observer_supervisor_backup_status.json', 'BACKUP_STATUS_FILE')
    must(p, 'observer_supervisor_attempts/', 'PRIMARY_ATTEMPTS')
    must(b, 'observer_supervisor_attempts/', 'BACKUP_ATTEMPTS')

    # No extra 09:03 live-market capture path. Recovery may exist elsewhere but
    # must never be represented here as a new market observation.
    for name, text in [('primary', p), ('backup', b), ('supervisor', s)]:
        must_not(text, '09:03', f'{name.upper()}_NO_0903_CAPTURE')
        must_not(text, '9, 3', f'{name.upper()}_NO_0903_CAPTURE_CODE')

    # Prewarm/freeze protects the legal 09:01 critical section from slow SOX/DXY/history I/O.
    must(s, 'PREWARM_START = dtime(8, 30, 0)', 'PREWARM_0830')
    must(s, 'PREFERRED_REFRESH = dtime(8, 50, 0)', 'PREWARM_REFRESH_0850')
    must(s, 'PREWARM_HARD_STOP = dtime(9, 0, 45)', 'PREWARM_HARD_STOP_090045')
    must(s, "mp.get_context('fork' if 'fork' in methods else methods[0])", 'KILLABLE_PREWARM_PROCESS')
    must(s, 'proc.terminate()', 'PREWARM_TERMINATE')
    must(s, 'v5.v4.prepare_model = frozen', 'FROZEN_PREPARE')
    must(s, "'prepare_model_network_calls_during_0901': 0", 'NO_PREPARE_NETWORK_0901')

    # MIS transport is bounded tightly enough that one hung batch cannot consume the full minute.
    must(s, 'CONNECT_TIMEOUT_SECONDS = 2.5', 'MIS_CONNECT_TIMEOUT')
    must(s, 'READ_TIMEOUT_SECONDS = 6.0', 'MIS_READ_TIMEOUT')

    # Import executable modules for semantic checks instead of formatting-sensitive strings.
    v5 = importlib.import_module('hengce_q017_observation_lock_v5')
    v4 = importlib.import_module('hengce_q017_decision_lock_v4')
    sup = importlib.import_module('hengce_q017_observer_supervisor_v1')

    assert v4.BATCH_SIZE == 40, 'BATCH_SIZE_DRIFT'
    assert v4.WORKERS == 10, 'WORKERS_DRIFT'
    assert v4.RETRY_SLEEP_SECONDS == 1.0, 'RETRY_SLEEP_DRIFT'
    assert v4.MIN_PROVIDER_COVERAGE == 1.0, 'V4_COVERAGE_DRIFT'

    # Formal schema, universe and immutable-after-validation remain core schema-v5 policy.
    assert v5.SCHEMA == 5, 'SCHEMA5_DRIFT'
    assert v5.UNIVERSE_SCOPE == 'TWSE_LISTED_ELECTRONICS_ONLY', 'UNIVERSE_SCOPE_DRIFT'
    assert v5.UNIVERSE_SOURCE == 'TWSE_MI_INDEX_TYPE_13_ELECTRONICS_HISTORY', 'UNIVERSE_SOURCE_DRIFT'
    collect_source = inspect.getsource(v5.collect_observation)
    validate_pos = collect_source.find('validate_observation(out)')
    write_pos = collect_source.find('write_once(')
    assert validate_pos >= 0 and write_pos >= 0 and validate_pos < write_pos, 'CANONICAL_WRITE_MUST_FOLLOW_VALIDATION'
    assert 'provider_coverage_required' in collect_source and '1.0' in collect_source, 'COVERAGE_REQUIRED_100PCT'

    wait_source = inspect.getsource(v4.wait_for_decision_minute)
    assert 'dtime(9,1,5)' in wait_source.replace(' ', ''), 'CAPTURE_TARGET_090105_DRIFT'
    assert 'dtime(9,1,59,999999)' in wait_source.replace(' ', ''), 'CAPTURE_END_DRIFT'
    attempt_source = inspect.getsource(v4.attempt_valid).replace(' ', '')
    assert 'cov>=1.0' in attempt_source, 'QUOTE_100PCT_ACCEPTANCE_DRIFT'
    capture_source = inspect.getsource(v4.capture_decision).replace(' ', '')
    assert 'RETRY_SLEEP_SECONDS' in capture_source and 'end-core.now_tw()' in capture_source, 'SAME_MINUTE_RETRY_DRIFT'

    # Executable supervisor constants/frozen-model behavior.
    assert sup.PREWARM_START.hour == 8 and sup.PREWARM_START.minute == 30
    assert sup.PREFERRED_REFRESH.hour == 8 and sup.PREFERRED_REFRESH.minute == 50
    assert sup.PREWARM_HARD_STOP.hour == 9 and sup.PREWARM_HARD_STOP.minute == 0 and sup.PREWARM_HARD_STOP.second == 45
    assert sup.CONNECT_TIMEOUT_SECONDS <= 2.5
    assert sup.READ_TIMEOUT_SECONDS <= 6.0

    print('HENGCE_Q017_OBSERVER_RESILIENCE_HARD_LOCK_V1=PASS')
    print('PRIMARY=07:45_TAIPEI BACKUP=08:15_TAIPEI PREWARM=08:30 REFRESH=08:50 HARD_STOP=09:00:45')
    print('Q017_CRITICAL_SECTION=09:01:05..09:01:59.999999 PREPARE_NETWORK_CALLS=0 MIS_BOUNDED=2.5/6.0')
    print('NO_0903_LIVE_CAPTURE=True LATE_BACKFILL_FORBIDDEN=True FAILURE_DIAGNOSTICS_ALWAYS_PERSIST=True')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
