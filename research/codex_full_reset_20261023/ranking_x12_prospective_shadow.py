#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/codex_full_reset_20261023/ranking_x12_prospective_shadow_result.json'
X12_SOURCE = ROOT / 'research/codex_full_reset_20261023/ranking_x12_prior_q25_skip.py'
LOCK_COMMIT = 'fc418d51771a2807ebf3af277c3d1892cef3b2f4'
LOCK_TIMESTAMP_UTC = '2026-10-25T06:26:20Z'
LOCK_DATE = '2026-10-25'
EXPECTED_X12_BLOB_SHA = 'facd953a312cf83fd0cd4c979306107d80c6ea58'
EXPECTED_PRELOCK_EVENTS_SHA256 = '1a5dfe097ddd4db9443301c8ca1e6346941d6a84013a769908804b7824319002'
EXPECTED_PRELOCK_EVENT_COUNT = 30
EXPECTED_PRELOCK_LAST_SIGNAL = '2026-08-25'
EXPECTED_PRELOCK_LAST_ENTRY = '2026-08-26'
EXPECTED_PRELOCK_LAST_EXIT = '2026-09-23'
INTERIM_COMPLETE_BASKETS = 6
PRIMARY_COMPLETE_BASKETS = 12
COSTS = (0.008, 0.012, 0.016)


def write_result(payload: dict) -> None:
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def git_blob_sha(path: Path) -> str:
    return subprocess.check_output(
        ['git', 'hash-object', str(path.relative_to(ROOT))], cwd=ROOT, text=True
    ).strip()


def event_bytes(events: list[dict]) -> bytes:
    return ''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in events).encode('utf-8')


def authority() -> dict:
    return {
        'research_only': True,
        'capital_authority_twd': 0,
        'broker_order_execution': False,
        'production_promotion': False,
        'merge_authorized': False,
    }


actual_x12_blob = git_blob_sha(X12_SOURCE)
if actual_x12_blob != EXPECTED_X12_BLOB_SHA:
    result = {
        'status': 'FROZEN_MODEL_DRIFT',
        'lock_commit': LOCK_COMMIT,
        'expected_x12_blob_sha': EXPECTED_X12_BLOB_SHA,
        'actual_x12_blob_sha': actual_x12_blob,
        'authority': authority(),
    }
    write_result(result)
    raise SystemExit(2)

# Import only after the frozen X12 source is verified. X12 recomputes its research
# result/events in the ephemeral runner; this script never writes production paths.
import research.codex_full_reset_20261023.ranking_x12_prior_q25_skip as x12

all_events = sorted(list(x12.EV), key=lambda e: e['signal_date'])
prelock = [e for e in all_events if e['signal_date'] <= LOCK_DATE]
postlock = [e for e in all_events if e['signal_date'] > LOCK_DATE]
prelock_sha256 = hashlib.sha256(event_bytes(prelock)).hexdigest()

# X12 inherits the V43 H20 schedule through X11/X10. Upstream V43 invalid rows
# are the relevant source for a post-lock scheduled basket that is not complete.
upstream_invalid = list(getattr(x12.x11.x10.v43, 'INVALID', []))
postlock_invalid = [x for x in upstream_invalid if x and x[0] > LOCK_DATE]

actual_last_signal = max((e['signal_date'] for e in prelock), default=None)
actual_last_entry = max((e['entry_date'] for e in prelock), default=None)
actual_last_exit = max((e['exit_date'] for e in prelock), default=None)
baseline_ok = (
    len(prelock) == EXPECTED_PRELOCK_EVENT_COUNT
    and prelock_sha256 == EXPECTED_PRELOCK_EVENTS_SHA256
    and actual_last_signal == EXPECTED_PRELOCK_LAST_SIGNAL
    and actual_last_entry == EXPECTED_PRELOCK_LAST_ENTRY
    and actual_last_exit == EXPECTED_PRELOCK_LAST_EXIT
)
if not baseline_ok:
    result = {
        'status': 'HISTORICAL_BASELINE_DRIFT',
        'lock_commit': LOCK_COMMIT,
        'lock_date': LOCK_DATE,
        'expected_prelock_event_count': EXPECTED_PRELOCK_EVENT_COUNT,
        'actual_prelock_event_count': len(prelock),
        'expected_prelock_events_sha256': EXPECTED_PRELOCK_EVENTS_SHA256,
        'actual_prelock_events_sha256': prelock_sha256,
        'expected_prelock_last_signal': EXPECTED_PRELOCK_LAST_SIGNAL,
        'actual_prelock_last_signal': actual_last_signal,
        'expected_prelock_last_entry': EXPECTED_PRELOCK_LAST_ENTRY,
        'actual_prelock_last_entry': actual_last_entry,
        'expected_prelock_last_exit': EXPECTED_PRELOCK_LAST_EXIT,
        'actual_prelock_last_exit': actual_last_exit,
        'authority': authority(),
    }
    write_result(result)
    raise SystemExit(3)

if any(e['entry_date'] <= LOCK_DATE or e['exit_date'] <= LOCK_DATE for e in postlock):
    result = {
        'status': 'POST_LOCK_DATE_VIOLATION',
        'lock_date': LOCK_DATE,
        'violations': [
            {
                'signal_date': e['signal_date'],
                'entry_date': e['entry_date'],
                'exit_date': e['exit_date'],
            }
            for e in postlock
            if e['entry_date'] <= LOCK_DATE or e['exit_date'] <= LOCK_DATE
        ],
        'authority': authority(),
    }
    write_result(result)
    raise SystemExit(4)

n = len(postlock)
if n == 0:
    status = 'WAITING_FOR_COMPLETE_POST_LOCK_OUTCOME' if postlock_invalid else 'WAITING_FOR_POST_LOCK_DATA'
elif n < INTERIM_COMPLETE_BASKETS:
    status = 'ACCUMULATING_POST_LOCK_BASKETS'
elif n < PRIMARY_COMPLETE_BASKETS:
    status = 'INTERIM_REVIEW_ELIGIBLE'
else:
    status = 'PRIMARY_REVIEW_ELIGIBLE'

monitoring = {str(c): x12.summarize(postlock, c) for c in COSTS} if postlock else None
interim_window = postlock[:INTERIM_COMPLETE_BASKETS]
primary_window = postlock[:PRIMARY_COMPLETE_BASKETS]
interim = (
    {str(c): x12.summarize(interim_window, c) for c in COSTS}
    if len(interim_window) == INTERIM_COMPLETE_BASKETS
    else None
)
primary = (
    {str(c): x12.summarize(primary_window, c) for c in COSTS}
    if len(primary_window) == PRIMARY_COMPLETE_BASKETS
    else None
)
primary_gate_pass = None
if primary is not None:
    c12 = primary['0.012']
    c16 = primary['0.016']
    remove_best = c12['remove_best_active_trade_return']
    primary_gate_pass = bool(
        c12['compounded_return'] > 0
        and remove_best is not None
        and remove_best > 0
        and c12['max_drawdown'] >= -0.30
        and c16['compounded_return'] > 0
    )

result = {
    'status': status,
    'protocol': 'X12_PROSPECTIVE_SHADOW_V1',
    'lock_commit': LOCK_COMMIT,
    'lock_timestamp_utc': LOCK_TIMESTAMP_UTC,
    'lock_date': LOCK_DATE,
    'frozen_x12_blob_sha': actual_x12_blob,
    'prelock_baseline_verified': True,
    'prelock_event_count': len(prelock),
    'prelock_events_sha256': prelock_sha256,
    'prelock_last_signal': EXPECTED_PRELOCK_LAST_SIGNAL,
    'prelock_last_entry': EXPECTED_PRELOCK_LAST_ENTRY,
    'prelock_last_exit': EXPECTED_PRELOCK_LAST_EXIT,
    'postlock_complete_baskets': n,
    'postlock_invalid': postlock_invalid,
    'interim_complete_baskets_required': INTERIM_COMPLETE_BASKETS,
    'primary_complete_baskets_required': PRIMARY_COMPLETE_BASKETS,
    'first_postlock_signal_date': postlock[0]['signal_date'] if postlock else None,
    'last_postlock_signal_date': postlock[-1]['signal_date'] if postlock else None,
    'last_postlock_exit_date': postlock[-1]['exit_date'] if postlock else None,
    'monitoring_all_postlock': monitoring,
    'registered_interim_first_6': interim,
    'registered_primary_first_12': primary,
    'registered_primary_gate_pass': primary_gate_pass,
    'registered_primary_gate': {
        'window': 'first 12 complete post-lock scheduled baskets only',
        'cost_0.012_compounded_return_gt': 0,
        'cost_0.012_remove_best_active_trade_return_gt': 0,
        'cost_0.012_max_drawdown_gte': -0.30,
        'cost_0.016_compounded_return_gt': 0,
    },
    'authority': authority(),
    'production_untouched': True,
    'q017_write': False,
    'e2_write': False,
    'm1_write': False,
    'pr_30_merge_authorized': False,
    'caveat': 'A passing shadow gate is evidence only. It never auto-promotes X12, changes Q017/E2/M1 production, merges PR #30, or authorizes capital/orders. X12 skip decisions remain prior-only and skipped scheduled baskets retain zero exposure.',
}
write_result(result)
