#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo('Asia/Taipei')
Q017 = ROOT / 'hengce' / 'q017_radar' / 'latest.json'
E2 = ROOT / 'hengce' / 'e2_live' / 'state_latest.json'
ELECTRONICS_HISTORY = ROOT / 'hengce' / 'q017_radar' / 'data' / 'twse_electronics_history_2026.csv'
OUT = ROOT / 'hengce' / 'dual_engine' / 'latest.json'


def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def atomic(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def _parse_now(value: str | None):
    if not value:
        return datetime.now(TZ)
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def _electronics_members(asof_date: str):
    if not ELECTRONICS_HISTORY.exists():
        return None, None
    rows = []
    with ELECTRONICS_HISTORY.open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            d = str(r.get('date') or '')
            t = str(r.get('ticker') or '')
            if d and d <= asof_date and t:
                rows.append((d, t))
    if not rows:
        return set(), None
    latest = max(d for d, _ in rows)
    return {t for d, t in rows if d == latest}, latest


def _formal_q017(x: dict):
    schema = int(x.get('schema_version') or 0)
    return schema >= 5 and x.get('authority') not in ('NO_FORMAL_SIGNAL', None)


def q017_view(x: dict, now: datetime):
    today = now.date().isoformat()
    schema = int(x.get('schema_version') or 0)
    source_trade_date = x.get('trade_date')
    top = x.get('top3') or []

    # A previous-session artifact must never masquerade as today's Q017 scan.
    if source_trade_date != today:
        if now.weekday() >= 5:
            status, reason = 'NO_TWSE_SESSION_EXPECTED', 'NON_WEEKDAY_LOCAL_CALENDAR'
        elif now.timetz().replace(tzinfo=None) < time(9, 1):
            status, reason = 'AWAITING_0901_OBSERVATION', 'AWAITING_IMMUTABLE_0901_OBSERVATION'
        elif now.timetz().replace(tzinfo=None) < time(9, 2):
            status, reason = 'CAPTURE_WINDOW', '0901_CAPTURE_WINDOW_IN_PROGRESS_OR_NOT_YET_PERSISTED'
        else:
            status, reason = 'DATA_PENDING', 'TODAY_VALID_0901_OBSERVATION_NOT_AVAILABLE_IN_LOCAL_AUTHORITY_STATE'
        return {
            'engine': 'Q017', 'status': status, 'binding_status': 'DATA_PENDING',
            'authority': 'NO_FORMAL_SIGNAL', 'formal_authority': False, 'formal_buy_count': 0,
            'trade_date': today, 'top3': [], 'reason': reason,
            'source_trade_date': source_trade_date, 'source_module': x.get('module'), 'schema_version': schema,
            'ranking_universe': 'TWSE_LISTED_ELECTRONICS_ONLY',
        }

    formal = _formal_q017(x)
    reason = x.get('reason') or x.get('error')
    membership_date = None
    if formal:
        members, membership_date = _electronics_members(today)
        if members is None:
            formal = False
            top = []
            reason = 'ELECTRONICS_UNIVERSE_HISTORY_MISSING_FAIL_CLOSED'
        else:
            bad = [str(r.get('ticker')) for r in top if str(r.get('ticker')) not in members]
            if bad:
                formal = False
                top = []
                reason = 'Q017_TOP3_OUTSIDE_TWSE_ELECTRONICS_UNIVERSE:' + ','.join(bad)

    return {
        'engine': 'Q017',
        'status': x.get('market_state') or x.get('binding_status') or 'DATA_PENDING',
        'binding_status': x.get('binding_status'),
        'authority': x.get('authority') if formal else 'NO_FORMAL_SIGNAL',
        'formal_authority': bool(formal),
        'formal_buy_count': int(x.get('formal_buy_count') or (len(top) if formal else 0)) if formal else 0,
        'trade_date': source_trade_date,
        'top3': top if formal else [],
        'reason': reason,
        'source_module': x.get('module'),
        'schema_version': schema,
        'universe_membership_date': membership_date,
        'ranking_universe': 'TWSE_LISTED_ELECTRONICS_ONLY',
    }


def e2_view(x: dict):
    if x.get('module') != 'E2_PROFIT_MAX_STATE' or int(x.get('schema_version') or 0) < 2:
        return {
            'engine': 'E2_PROFIT_MAX', 'status': 'DATA_PENDING', 'authority': 'NO_E2_SIGNAL',
            'top1': None, 'action': 'OFF', 'reason': 'E2_PROFIT_MAX_STATE_NOT_AVAILABLE',
            'broker_order_execution': False,
        }
    return {
        'engine': 'E2_PROFIT_MAX',
        'status': x.get('engine_status'),
        'binding_status': x.get('binding_status'),
        'authority': x.get('authority'),
        'signal_asof': x.get('signal_asof'),
        'local_gate': x.get('local_gate'),
        'macro_gate': x.get('macro_gate'),
        'top1': x.get('top1'),
        'action': x.get('action'),
        'paper_position': x.get('paper_position'),
        'research_capital_twd': 3000000,
        'capital_authority_twd': 0,
        'broker_order_execution': False,
        'dxy_used': False,
        'source_module': x.get('module'),
        'schema_version': x.get('schema_version'),
    }


def build(now: datetime):
    q = load(Q017) if Q017.exists() else {
        'schema_version': 5, 'module': 'Q017_MISSING', 'binding_status': 'DATA_PENDING',
        'market_state': 'DATA_PENDING', 'authority': 'NO_FORMAL_SIGNAL', 'formal_buy_count': 0,
    }
    e = load(E2) if E2.exists() else {}
    return {
        'schema_version': 2,
        'system': 'HENGCE',
        'module': 'HENGCE_DUAL_ENGINE_DISPLAY',
        'generated_at_taipei': now.isoformat(),
        'architecture': 'DUAL_ENGINE',
        'rankings_separate': True,
        'mixed_ranking_forbidden': True,
        'legacy_v3_display_authority': False,
        'q017': q017_view(q, now),
        'e2': e2_view(e),
        'display_policy': 'ALWAYS_SHOW_Q017_AND_E2_SEPARATELY; NEVER_MIX_RANKINGS; NEVER_PROMOTE_STALE_Q017_TO_TODAY',
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--now', help='ISO-8601 Taipei test/display time override')
    ap.add_argument('--no-write', action='store_true')
    args = ap.parse_args()
    now = _parse_now(args.now)
    out = build(now)
    if not args.no_write:
        atomic(OUT, out)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
