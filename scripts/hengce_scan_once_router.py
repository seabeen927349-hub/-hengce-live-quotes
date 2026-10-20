#!/usr/bin/env python3
"""Authoritative router for the literal user command `衡策掃一次`.

This router permanently removes the legacy V3 full-market ranking from scan-once
display authority. Q017 and E2 are independent and are always rendered separately.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Taipei')
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'


def parse_now(value: str | None):
    if not value:
        return datetime.now(TZ)
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def run_step(name: str, argv: list[str], timeout: int = 180):
    try:
        p = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        return {
            'name': name,
            'return_code': p.returncode,
            'ok': p.returncode == 0,
            'stdout_tail': p.stdout[-2000:],
            'stderr_tail': p.stderr[-2000:],
        }
    except subprocess.TimeoutExpired as e:
        return {'name': name, 'return_code': 124, 'ok': False, 'error': f'TIMEOUT:{e}'}
    except Exception as e:
        return {'name': name, 'return_code': 125, 'ok': False, 'error': f'{type(e).__name__}:{e}'}


def refresh(now: datetime):
    attempts = []
    today = now.date().isoformat()
    clock = now.timetz().replace(tzinfo=None)
    if now.weekday() >= 5:
        return attempts
    if clock < time(8, 30):
        return attempts
    if clock < time(9, 1):
        attempts.append(run_step('premarket_gate', [sys.executable, str(SCRIPTS/'hengce_daily_command_center.py'), '--mode', 'premarket', '--date', today]))
        return attempts
    if clock < time(9, 2):
        obs = run_step('q017_0901_observe', [sys.executable, str(SCRIPTS/'hengce_q017_observation_lock_v5.py'), '--mode', 'observe', '--date', today], timeout=90)
        attempts.append(obs)
        if obs['ok']:
            attempts.append(run_step('q017_compute_from_locked_observation', [sys.executable, str(SCRIPTS/'hengce_q017_observation_lock_v5.py'), '--mode', 'compute', '--date', today]))
        attempts.append(run_step('e2_morning', [sys.executable, str(SCRIPTS/'hengce_e2_live.py'), '--mode', 'morning', '--date', today]))
        return attempts
    if clock < time(14, 0):
        attempts.append(run_step('q017_recovery_locked_evidence_only', [sys.executable, str(SCRIPTS/'hengce_q017_recovery_compute_v5.py'), '--mode', 'compute', '--date', today]))
        attempts.append(run_step('q017_authority_guard', [sys.executable, str(SCRIPTS/'hengce_q017_authority_guard_v5.py'), '--mode', 'check-and-repair']))
        attempts.append(run_step('e2_morning', [sys.executable, str(SCRIPTS/'hengce_e2_live.py'), '--mode', 'morning', '--date', today]))
        return attempts
    if clock >= time(15, 0):
        attempts.append(run_step('postclose_three_leg', [sys.executable, str(SCRIPTS/'hengce_daily_command_center.py'), '--mode', 'postclose', '--date', today], timeout=240))
        attempts.append(run_step('e2_postclose', [sys.executable, str(SCRIPTS/'hengce_e2_live.py'), '--mode', 'postclose', '--date', today], timeout=240))
        attempts.append(run_step('q017_authority_guard', [sys.executable, str(SCRIPTS/'hengce_q017_authority_guard_v5.py'), '--mode', 'check-and-repair']))
    return attempts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--now', help='ISO-8601 Taipei time override (testing/replay of routing only)')
    ap.add_argument('--display-only', action='store_true', help='Do not perform network/state refresh; render current authority only')
    args = ap.parse_args()
    now = parse_now(args.now)
    attempts = [] if args.display_only else refresh(now)
    p = subprocess.run([sys.executable, str(SCRIPTS/'hengce_dual_engine_display.py'), '--now', now.isoformat()], cwd=ROOT, text=True, capture_output=True)
    if p.returncode != 0:
        print(json.dumps({'system':'HENGCE','module':'HENGCE_SCAN_ONCE_ROUTER','status':'FAIL_CLOSED','reason':'DUAL_ENGINE_DISPLAY_FAILED','refresh_attempts':attempts,'stderr':p.stderr[-2000:],'legacy_v3_display_authority':False}, ensure_ascii=False, indent=2))
        return 2
    display = json.loads(p.stdout)
    display['scan_once_router'] = {
        'status':'PASS','command':'衡策掃一次','refresh_attempts':attempts,
        'legacy_v3_full_market_ranking_displayed':False,
        'legacy_run_hengce_work_called':False,
        'engine_failure_isolation':True,
    }
    print(json.dumps(display, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
