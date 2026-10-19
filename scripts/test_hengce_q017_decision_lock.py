#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from datetime import date, datetime
from pathlib import Path

import hengce_q017_decision_lock as lock


def expect_raises(fn, text):
    try:
        fn()
    except Exception as e:
        if text not in repr(e):
            raise AssertionError(f'expected {text!r}, got {e!r}')
        return
    raise AssertionError(f'expected exception containing {text!r}')


def install_temp_paths(tmp: Path):
    lock.ROOT = tmp
    lock.DECISION_DIR = tmp / 'decision'
    lock.DECISION_DIR.mkdir(parents=True, exist_ok=True)
    lock.DECISION_LATEST = tmp / 'decision_latest.json'
    lock.LATEST = tmp / 'latest.json'
    lock.HISTORY = tmp / 'history'
    lock.HISTORY.mkdir(parents=True, exist_ok=True)
    lock.SIGNAL_LEDGER = tmp / 'signal_ledger.jsonl'


def test_immutable_write(tmp: Path):
    p = tmp / 'immutable.json'
    a = {'x': 1}
    b = {'x': 2}
    stored, created = lock.write_once(p, a)
    assert created and stored == a
    stored2, created2 = lock.write_once(p, a)
    assert not created2 and stored2 == a
    expect_raises(lambda: lock.write_once(p, b), 'IMMUTABLE_DECISION_CONFLICT')


def test_capture_and_monitor_freeze(tmp: Path):
    orig_root = lock.ROOT
    install_temp_paths(tmp)
    today = date(2026, 10, 20)
    fixed = datetime(2026, 10, 20, 9, 1, 10, tzinfo=lock.TZ)
    decision_end = datetime(2026, 10, 20, 9, 1, 59, 999999, tzinfo=lock.TZ)

    orig_prepare = lock.prepare_model
    orig_wait = lock.wait_for_decision_minute
    orig_mis = lock.mis_batch
    orig_now = lock.core.now_tw
    orig_marks = lock.current_marks
    try:
        lock.core.now_tw = lambda: fixed
        lock.wait_for_decision_minute = lambda _today: (fixed, decision_end)
        lock.prepare_model = lambda _today: (
            {'status': 'PASS'},
            {'status': 'PASS'},
            {'status': 'PASS'},
            {'sox_1d': -0.01, 'sox_5d': -0.03},
            {'1111': 1.0, '2222': 2.0, '3333': 3.0, '4444': 4.0},
            {'1111': 100.0, '2222': 100.0, '3333': 100.0, '4444': 100.0},
            {'1111': 'A', '2222': 'B', '3333': 'C', '4444': 'D'},
            '2026-10-19',
            ['1111', '2222', '3333', '4444'],
        )

        def fake_mis(_batch):
            rows = {
                '1111': {'ticker': '1111', 'name': 'A', 'open': 99.0, 'reference_close': 100.0, 'fetched_at_taipei': fixed.isoformat()},
                '2222': {'ticker': '2222', 'name': 'B', 'open': None, 'reference_close': 100.0, 'fetched_at_taipei': fixed.isoformat()},
                '3333': {'ticker': '3333', 'name': 'C', 'open': 98.0, 'reference_close': 100.0, 'fetched_at_taipei': fixed.isoformat()},
                '4444': {'ticker': '4444', 'name': 'D', 'open': 97.0, 'reference_close': 100.0, 'fetched_at_taipei': fixed.isoformat()},
            }
            return rows, fixed, fixed

        lock.mis_batch = fake_mis
        snap = lock.capture_decision(today)
        assert snap['binding_status'] == 'PASS'
        assert snap['decision_lock']['immutable'] is True
        assert snap['decision_lock']['rerank_after_lock'] is False
        assert snap['data_status']['provider_coverage'] == 1.0
        assert snap['data_status']['opened_by_decision_count'] == 3
        assert '2222' not in [x['ticker'] for x in snap['top3']], 'missing-open ticker leaked into 09:01 candidates'
        locked_top3 = [x['ticker'] for x in snap['top3']]

        # Simulate 09:03 prices reversing violently. Monitor may mark, never rerank.
        lock.core.now_tw = lambda: datetime(2026, 10, 20, 9, 3, 10, tzinfo=lock.TZ)
        lock.current_marks = lambda _top3: [
            {'ticker': t, 'price': p, 'return_from_locked_open': None, 'source': 'TEST', 'quote_time_taipei': '09:03'}
            for t, p in [('1111', 200.0), ('3333', 50.0), ('4444', 40.0)]
        ]
        monitored = lock.monitor(today)
        assert [x['ticker'] for x in monitored['top3']] == locked_top3
        assert monitored['monitor']['rerank_performed'] is False
        assert monitored['monitor']['ranking_frozen'] is True

        # A second capture must return the already-locked snapshot, not rewrite it.
        lock.core.now_tw = lambda: datetime(2026, 10, 20, 9, 10, 0, tzinfo=lock.TZ)
        second = lock.capture_decision(today)
        assert second['decision_snapshot_sha256'] == snap['decision_snapshot_sha256']
        assert [x['ticker'] for x in second['top3']] == locked_top3

        # Tampering must be detected before monitoring.
        p = lock.decision_path(today)
        tampered = json.loads(p.read_text(encoding='utf-8'))
        tampered['top3'][0]['score'] += 999
        p.write_text(json.dumps(tampered, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        expect_raises(lambda: lock.monitor(today), 'DECISION_SNAPSHOT_HASH_MISMATCH')
    finally:
        lock.ROOT = orig_root
        lock.prepare_model = orig_prepare
        lock.wait_for_decision_minute = orig_wait
        lock.mis_batch = orig_mis
        lock.core.now_tw = orig_now
        lock.current_marks = orig_marks


def test_no_snapshot_fail_closed(tmp: Path):
    orig_root = lock.ROOT
    try:
        install_temp_paths(tmp)
        today = date(2026, 10, 20)
        expect_raises(lambda: lock.monitor(today), 'NO_IMMUTABLE_0901_DECISION_SNAPSHOT')
    finally:
        lock.ROOT = orig_root


def main():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        test_immutable_write(root / 'a')
    with tempfile.TemporaryDirectory() as td:
        test_capture_and_monitor_freeze(Path(td))
    with tempfile.TemporaryDirectory() as td:
        test_no_snapshot_fail_closed(Path(td))
    print(json.dumps({
        'deterministic_replay_test': 'PASS',
        'checks': [
            'immutable_snapshot_write',
            '09:01_missing_open_excluded_without_data_failure',
            '09:03_price_reversal_does_not_rerank',
            'second_capture_does_not_rewrite',
            'snapshot_hash_tamper_detected',
            'missing_snapshot_fail_closed',
        ],
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
