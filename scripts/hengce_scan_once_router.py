#!/usr/bin/env python3
"""Authoritative router for the literal user command `衡策掃一次`.

There is one user-facing HENGCE system. Q017 is an internal candidate source;
E2 may continue as research/operational state but is never rendered as a
competing engine by this router.
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
ACTION = ROOT / 'work_output' / 'intraday_action_board' / 'HENGCE_INTRADAY_ACTION_BOARD.json'
BASE = ROOT / 'work_output' / 'intraday_action_board' / 'HENGCE_UNIFIED_CANDIDATE_BASE.json'


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
    """Preserve existing data lanes, but do not grant them separate display authority."""
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
        # Retain the existing lane only as legacy evidence. The unified adapter
        # rejects it when its contract is not the frozen canonical Q017 contract.
        obs = run_step('q017_legacy_observation_evidence', [sys.executable, str(SCRIPTS/'hengce_q017_observation_lock_v5.py'), '--mode', 'observe', '--date', today], timeout=90)
        attempts.append(obs)
        if obs['ok']:
            attempts.append(run_step('q017_legacy_compute_evidence', [sys.executable, str(SCRIPTS/'hengce_q017_observation_lock_v5.py'), '--mode', 'compute', '--date', today]))
        return attempts
    if clock < time(14, 0):
        attempts.append(run_step('q017_legacy_evidence_recovery', [sys.executable, str(SCRIPTS/'hengce_q017_recovery_compute_v5.py'), '--mode', 'compute', '--date', today]))
        attempts.append(run_step('q017_legacy_authority_guard', [sys.executable, str(SCRIPTS/'hengce_q017_authority_guard_v5.py'), '--mode', 'check-and-repair']))
        return attempts
    if clock >= time(15, 0):
        attempts.append(run_step('postclose_three_leg', [sys.executable, str(SCRIPTS/'hengce_daily_command_center.py'), '--mode', 'postclose', '--date', today], timeout=240))
        attempts.append(run_step('q017_legacy_authority_guard', [sys.executable, str(SCRIPTS/'hengce_q017_authority_guard_v5.py'), '--mode', 'check-and-repair']))
    return attempts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--now', help='ISO-8601 Taipei time override (testing/replay of routing only)')
    ap.add_argument('--display-only', action='store_true', help='Do not perform network/state refresh; render current unified HENGCE authority only')
    args = ap.parse_args()
    now = parse_now(args.now)
    attempts = [] if args.display_only else refresh(now)

    if not args.display_only:
        attempts.append(run_step('unified_hengce_action_board', ['bash', str(SCRIPTS/'RUN_INTRADAY_ACTION_BOARD.sh')], timeout=240))

    display_cmd = [sys.executable, str(SCRIPTS/'hengce_unified_scan_display.py'), '--now', now.isoformat(), '--no-write']
    if ACTION.exists():
        display_cmd += ['--action', str(ACTION)]
    if BASE.exists():
        display_cmd += ['--base', str(BASE)]
    p = subprocess.run(display_cmd, cwd=ROOT, text=True, capture_output=True)
    try:
        display = json.loads(p.stdout) if p.stdout.strip() else {}
    except Exception:
        display = {}
    if not isinstance(display, dict) or display.get('system') != 'HENGCE':
        display = {
            'schema_version': 1,
            'system': 'HENGCE',
            'module': 'HENGCE_SCAN_ONCE_ROUTER',
            'architecture': 'SINGLE_HENGCE',
            'status': 'DATA_PENDING',
            'binding_status': 'FAIL_CLOSED',
            'authority': 'NO_FORMAL_HENGCE_OUTPUT',
            'rows': [],
            'reason': 'UNIFIED_SCAN_DISPLAY_FAILED',
        }
    display['scan_once_router'] = {
        'status': 'PASS' if display.get('binding_status') == 'PASS' else 'FAIL_CLOSED',
        'command': '衡策掃一次',
        'refresh_attempts': attempts,
        'single_hengce_output': True,
        'q017_separate_ranking_displayed': False,
        'e2_separate_engine_displayed': False,
        'legacy_v3_separate_ranking_displayed': False,
        'score_fusion': False,
    }
    print(json.dumps(display, ensure_ascii=False, indent=2))
    return 0 if display.get('binding_status') == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
