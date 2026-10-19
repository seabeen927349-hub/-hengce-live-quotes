#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo('Asia/Taipei')
Q017 = ROOT / 'hengce' / 'q017_radar' / 'latest.json'
E2 = ROOT / 'hengce' / 'e2_live' / 'state_latest.json'
OUT = ROOT / 'hengce' / 'dual_engine' / 'latest.json'


def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def atomic(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def q017_view(x: dict):
    schema = int(x.get('schema_version') or 0)
    formal = schema >= 5 and x.get('authority') not in ('NO_FORMAL_SIGNAL', None)
    top = x.get('top3') or []
    return {
        'engine': 'Q017',
        'status': x.get('market_state') or x.get('binding_status') or 'DATA_PENDING',
        'binding_status': x.get('binding_status'),
        'authority': x.get('authority'),
        'formal_authority': bool(formal),
        'formal_buy_count': int(x.get('formal_buy_count') or (len(top) if formal else 0)),
        'trade_date': x.get('trade_date'),
        'top3': top if formal else [],
        'reason': x.get('reason') or x.get('error'),
        'source_module': x.get('module'),
        'schema_version': schema,
    }


def e2_view(x: dict):
    if x.get('module') != 'E2_PROFIT_MAX_STATE' or int(x.get('schema_version') or 0) < 2:
        return {
            'engine': 'E2_PROFIT_MAX', 'status': 'DATA_PENDING', 'authority': 'NO_E2_SIGNAL',
            'top1': None, 'action': 'OFF', 'reason': 'E2_PROFIT_MAX_STATE_NOT_AVAILABLE'
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
        'broker_order_execution': False,
        'dxy_used': False,
        'source_module': x.get('module'),
        'schema_version': x.get('schema_version'),
    }


def main():
    if not Q017.exists():
        q = {'schema_version': 5, 'module': 'Q017_MISSING', 'binding_status': 'DATA_PENDING', 'market_state': 'DATA_PENDING', 'authority': 'NO_FORMAL_SIGNAL', 'formal_buy_count': 0}
    else:
        q = load(Q017)
    if not E2.exists():
        e = {}
    else:
        e = load(E2)
    out = {
        'schema_version': 1,
        'system': 'HENGCE',
        'module': 'HENGCE_DUAL_ENGINE_DISPLAY',
        'generated_at_taipei': datetime.now(TZ).isoformat(),
        'architecture': 'DUAL_ENGINE',
        'rankings_separate': True,
        'q017': q017_view(q),
        'e2': e2_view(e),
        'display_policy': 'ALWAYS_SHOW_Q017_AND_E2_SEPARATELY; NEVER_MIX_RANKINGS',
    }
    atomic(OUT, out)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
