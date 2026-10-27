#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import importlib
import inspect

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = ROOT / '.github/workflows/hengce-q017-primary-observer.yml'
BACKUP = ROOT / '.github/workflows/hengce-q017-backup-observer.yml'
MACRO_WORKFLOW = ROOT / '.github/workflows/hengce-q017-macro-cache.yml'
AUTHORITY_GUARD = ROOT / '.github/workflows/hengce-q017-authority-guard.yml'
SUPERVISOR_V1 = ROOT / 'scripts/hengce_q017_observer_supervisor_v1.py'
SUPERVISOR_V2 = ROOT / 'scripts/hengce_q017_observer_supervisor_v2.py'
MACRO = ROOT / 'scripts/hengce_q017_macro_cache_v1.py'
SNAPSHOT = ROOT / 'scripts/hengce_q017_premarket_snapshot_v1.py'


def must(text: str, needle: str, label: str):
    assert needle in text, f'MISSING:{label}:{needle}'


def must_not(text: str, needle: str, label: str):
    assert needle not in text, f'FORBIDDEN:{label}:{needle}'


def main():
    p = PRIMARY.read_text(encoding='utf-8')
    b = BACKUP.read_text(encoding='utf-8')
    mw = MACRO_WORKFLOW.read_text(encoding='utf-8')
    ag = AUTHORITY_GUARD.read_text(encoding='utf-8')
    s1 = SUPERVISOR_V1.read_text(encoding='utf-8')
    s2 = SUPERVISOR_V2.read_text(encoding='utf-8')
    macro_text = MACRO.read_text(encoding='utf-8')
    snap_text = SNAPSHOT.read_text(encoding='utf-8')

    # Early macro acquisition is independent of the 09:01 observation lane.
    for cron, label in [
        ("cron: '45 21 * * 0-4'", 'MACRO_0545_TAIPEI'),
        ("cron: '15 22 * * 0-4'", 'MACRO_0615_TAIPEI'),
        ("cron: '45 22 * * 0-4'", 'MACRO_0645_TAIPEI'),
        ("cron: '15 23 * * 0-4'", 'MACRO_0715_TAIPEI'),
        ("cron: '35 23 * * 0-4'", 'MACRO_0735_TAIPEI'),
    ]:
        must(mw, cron, label)
    must(mw, 'group: hengce-q017-morning-macro-cache', 'MACRO_CONCURRENCY')
    must(mw, 'hengce_q017_macro_cache_v1.py --mode refresh', 'MACRO_REFRESH_WIRED')
    must(mw, 'hengce_q017_macro_cache_v1.py --mode validate', 'MACRO_VALIDATE_WIRED')
    must(mw, 'hengce/q017_radar/data/macro_cache/', 'MACRO_CACHE_PERSISTED')

    # Current production topology is Q017-only: morning macro cache, then
    # independent 07:45/08:15 observer lanes. The premarket snapshot module
    # remains a self-tested infrastructure helper, not a separate scheduled
    # ranking/authority producer.
    must(p, "cron: '45 23 * * 0-4'", 'PRIMARY_0745_TAIPEI')
    must(b, "cron: '15 0 * * 1-5'", 'BACKUP_0815_TAIPEI')
    must(p, "'scripts/hengce_q017_macro_cache_v1.py'", 'PRIMARY_TESTS_MACRO_CHANGES')
    must(b, "'scripts/hengce_q017_macro_cache_v1.py'", 'BACKUP_TESTS_MACRO_CHANGES')
    must(p, "'scripts/hengce_q017_premarket_snapshot_v1.py'", 'PRIMARY_TESTS_SNAPSHOT_CHANGES')
    must(b, "'scripts/hengce_q017_premarket_snapshot_v1.py'", 'BACKUP_TESTS_SNAPSHOT_CHANGES')
    must(p, 'hengce_q017_premarket_snapshot_v1.py --mode self-test', 'PRIMARY_SNAPSHOT_SELFTEST')
    must(b, 'hengce_q017_premarket_snapshot_v1.py --mode self-test', 'BACKUP_SNAPSHOT_SELFTEST')

    must(p, 'group: hengce-q017-primary-observer', 'PRIMARY_CONCURRENCY')
    must(b, 'group: hengce-q017-backup-observer', 'BACKUP_CONCURRENCY')
    assert 'group: hengce-q017-backup-observer' not in p
    assert 'group: hengce-q017-primary-observer' not in b

    # Production scheduled lanes must use v2 (macro-cache first), never raw observe.
    must(p, 'hengce_q017_observer_supervisor_v2.py --mode observe --lane primary', 'PRIMARY_SUPERVISOR_V2')
    must(b, 'hengce_q017_observer_supervisor_v2.py --mode observe --lane backup', 'BACKUP_SUPERVISOR_V2')
    must_not(p, 'hengce_q017_observer_supervisor_v1.py --mode observe --lane primary', 'PRIMARY_V1_DIRECT_FORBIDDEN')
    must_not(b, 'hengce_q017_observer_supervisor_v1.py --mode observe --lane backup', 'BACKUP_V1_DIRECT_FORBIDDEN')
    must_not(p, 'hengce_q017_observation_lock_v5.py --mode observe', 'PRIMARY_RAW_OBSERVE_FORBIDDEN')
    must_not(b, 'hengce_q017_backup_observer_v5.py --mode observe', 'BACKUP_RAW_OBSERVE_FORBIDDEN')

    # Q017-only production hard lock: no E2 or dual-engine display/output may be
    # wired into any scheduled Q017 production lane or authority guard.
    for name, text in [('primary', p), ('backup', b), ('macro', mw), ('authority_guard', ag)]:
        must_not(text, 'e2_live', f'{name.upper()}_NO_E2_LIVE')
        must_not(text, 'E2_PROFIT_MAX', f'{name.upper()}_NO_E2_ENGINE')
        must_not(text, 'dual_engine', f'{name.upper()}_NO_DUAL_ENGINE')
        must_not(text, 'hengce_dual_engine_display', f'{name.upper()}_NO_DUAL_DISPLAY')

    # Both observers refresh checkout before waiting so they see the latest persisted morning cache.
    must(p, 'git pull --rebase origin main', 'PRIMARY_SYNC_MORNING_CACHE')
    must(b, 'git pull --rebase origin main', 'BACKUP_SYNC_MORNING_CACHE')

    # Failure diagnostics must persist even when capture generation fails.
    must(p, "if: always() && steps.mode.outputs.mode == 'observe'", 'PRIMARY_ALWAYS_PERSIST')
    must(b, "if: always() && steps.mode.outputs.mode == 'observe'", 'BACKUP_ALWAYS_PERSIST')
    must(p, 'observer_supervisor_primary_status.json', 'PRIMARY_STATUS_FILE')
    must(b, 'observer_supervisor_backup_status.json', 'BACKUP_STATUS_FILE')
    must(p, 'observer_supervisor_attempts/', 'PRIMARY_ATTEMPTS')
    must(b, 'observer_supervisor_attempts/', 'BACKUP_ATTEMPTS')

    # No extra 09:03 live-market capture.
    for name, text in [
        ('primary', p), ('backup', b), ('supervisor_v1', s1), ('supervisor_v2', s2),
        ('macro', macro_text), ('snapshot', snap_text),
    ]:
        must_not(text, '09:03', f'{name.upper()}_NO_0903_CAPTURE')
        must_not(text, '9, 3', f'{name.upper()}_NO_0903_CAPTURE_CODE')

    # Normal v2 path must be hash-bound morning macro cache with zero macro network at 09:01.
    must(s2, 'macro.load_valid_cache(trade_date, verify_files=True)', 'V2_MACRO_CACHE_VALIDATE')
    must(s2, 'cache_first_prepared_model', 'V2_CACHE_FIRST')
    must(s2, 'v1.prewarm_and_freeze', 'V2_BOUNDED_V1_FALLBACK')
    must_not(s2, 'prepared, fingerprint = v1.prewarm_and_freeze', 'V2_OLD_TWO_VALUE_FALLBACK_UNPACK_FORBIDDEN')
    must(s2, 'prepared, fingerprint, _ = v1.prewarm_and_freeze', 'V2_THREE_VALUE_FALLBACK_CONTRACT')
    must(s2, "'macro_network_calls_during_0901': 0", 'V2_NO_MACRO_NETWORK_0901')
    must(s2, "'prepare_model_network_calls_during_0901': 0", 'V2_NO_PREPARE_NETWORK_0901')

    # v1 fallback itself stays bounded and pre-09:01 only.
    must(s1, 'PREWARM_START = dtime(8, 30, 0)', 'PREWARM_0830')
    must(s1, 'PREFERRED_REFRESH = dtime(8, 50, 0)', 'PREWARM_REFRESH_0850')
    must(s1, 'PREWARM_HARD_STOP = dtime(9, 0, 45)', 'PREWARM_HARD_STOP_090045')
    must(s1, "mp.get_context('fork' if 'fork' in methods else methods[0])", 'KILLABLE_PREWARM_PROCESS')
    must(s1, 'proc.terminate()', 'PREWARM_TERMINATE')
    must(s1, 'v5.v4.prepare_model = frozen', 'FROZEN_PREPARE')

    # MIS transport is tightly bounded so one hung batch cannot consume the minute.
    must(s1, 'CONNECT_TIMEOUT_SECONDS = 2.5', 'MIS_CONNECT_TIMEOUT')
    must(s1, 'READ_TIMEOUT_SECONDS = 6.0', 'MIS_READ_TIMEOUT')

    # Macro cache is causal, hash-bound and cannot substitute for 09:01 observation.
    must(macro_text, "'cannot_substitute_for_q017_0901_observation': True", 'MACRO_NOT_OBSERVATION')
    must(macro_text, "'sox_csv_sha256'", 'SOX_SHA_BOUND')
    must(macro_text, "'dxy_csv_sha256'", 'DXY_SHA_BOUND')
    must(macro_text, "payload['cache_sha256']", 'MACRO_CACHE_SHA')
    must(snap_text, 'prepare_from_macro_cache', 'SNAPSHOT_USES_MACRO_CACHE')
    must(snap_text, "source = 'MORNING_MACRO_CACHE'", 'SNAPSHOT_CACHE_SOURCE_LABEL')

    # Semantic checks use executable modules.
    v5 = importlib.import_module('hengce_q017_observation_lock_v5')
    v4 = importlib.import_module('hengce_q017_decision_lock_v4')
    sup1 = importlib.import_module('hengce_q017_observer_supervisor_v1')
    importlib.import_module('hengce_q017_observer_supervisor_v2')
    macro = importlib.import_module('hengce_q017_macro_cache_v1')
    snap = importlib.import_module('hengce_q017_premarket_snapshot_v1')

    assert v4.BATCH_SIZE == 40, 'BATCH_SIZE_DRIFT'
    assert v4.WORKERS == 10, 'WORKERS_DRIFT'
    assert v4.RETRY_SLEEP_SECONDS == 1.0, 'RETRY_SLEEP_DRIFT'
    assert v4.MIN_PROVIDER_COVERAGE == 1.0, 'V4_COVERAGE_DRIFT'

    # Formal schema/universe/immutability remain unchanged.
    assert v5.SCHEMA == 5, 'SCHEMA5_DRIFT'
    assert v5.UNIVERSE_SCOPE == 'TWSE_LISTED_ELECTRONICS_ONLY', 'UNIVERSE_SCOPE_DRIFT'
    assert v5.UNIVERSE_SOURCE == 'TWSE_MI_INDEX_TYPE_13_ELECTRONICS_HISTORY', 'UNIVERSE_SOURCE_DRIFT'
    collect_source = inspect.getsource(v5.collect_observation)
    validate_pos = collect_source.find('validate_observation(out)')
    write_pos = collect_source.find('write_once(')
    assert validate_pos >= 0 and write_pos >= 0 and validate_pos < write_pos, 'CANONICAL_WRITE_MUST_FOLLOW_VALIDATION'
    assert 'provider_coverage_required' in collect_source and '1.0' in collect_source, 'COVERAGE_REQUIRED_100PCT'

    wait_source = inspect.getsource(v4.wait_for_decision_minute).replace(' ', '')
    assert 'dtime(9,1,5)' in wait_source, 'CAPTURE_TARGET_090105_DRIFT'
    assert 'dtime(9,1,59,999999)' in wait_source, 'CAPTURE_END_DRIFT'
    attempt_source = inspect.getsource(v4.attempt_valid).replace(' ', '')
    assert 'cov>=1.0' in attempt_source, 'QUOTE_100PCT_ACCEPTANCE_DRIFT'
    capture_source = inspect.getsource(v5.collect_observation).replace(' ', '')
    assert 'RETRY_SLEEP_SECONDS' in capture_source and 'end-core.now_tw()' in capture_source, 'SAME_MINUTE_RETRY_DRIFT'

    # Cache/snapshot can never themselves become a signal.
    assert macro.SCHEMA_VERSION == 1, 'MACRO_SCHEMA_DRIFT'
    assert snap.SCHEMA == 1, 'SNAPSHOT_SCHEMA_DRIFT'
    assert snap.AUTHORITY == 'INFRASTRUCTURE_CACHE_ONLY_NO_SIGNAL_AUTHORITY', 'SNAPSHOT_AUTHORITY_DRIFT'
    assert snap.BUILD_CUTOFF.hour == 9 and snap.BUILD_CUTOFF.minute == 0 and snap.BUILD_CUTOFF.second == 45
    snapshot_build_source = inspect.getsource(snap.build)
    assert 'SNAPSHOT_BUILD_AFTER_0900_45_FORBIDDEN' in snapshot_build_source
    make_source = inspect.getsource(snap.make_payload)
    assert "'formal_buy_count': 0" in make_source
    assert "'late_market_backfill_forbidden': True" in make_source
    assert 'model_fingerprint_sha256' in make_source and 'snapshot_sha256' in make_source

    assert sup1.PREWARM_START.hour == 8 and sup1.PREWARM_START.minute == 30
    assert sup1.PREFERRED_REFRESH.hour == 8 and sup1.PREFERRED_REFRESH.minute == 50
    assert sup1.PREWARM_HARD_STOP.hour == 9 and sup1.PREWARM_HARD_STOP.minute == 0 and sup1.PREWARM_HARD_STOP.second == 45
    assert sup1.CONNECT_TIMEOUT_SECONDS <= 2.5
    assert sup1.READ_TIMEOUT_SECONDS <= 6.0

    print('HENGCE_Q017_OBSERVER_RESILIENCE_HARD_LOCK_V3=PASS')
    print('MACRO_CACHE=05:45/06:15/06:45/07:15/07:35 PRIMARY=07:45 BACKUP=08:15')
    print('Q017_ONLY_PRODUCTION=True E2_PRODUCTION=False DUAL_ENGINE_PRODUCTION=False')
    print('NORMAL_0901_NETWORK=TWSE_MIS_ONLY MACRO_NETWORK_CALLS=0 MIS_BOUNDED=2.5/6.0')
    print('SCHEMA5=True COVERAGE=100PCT NO_0903_CAPTURE=True LATE_BACKFILL_FORBIDDEN=True')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
