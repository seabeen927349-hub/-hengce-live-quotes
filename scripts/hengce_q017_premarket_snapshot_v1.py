#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, time as dtime
from pathlib import Path

import hengce_q017_observation_lock_v5 as v5

core = v5.core
v4 = v5.v4
TZ = v5.TZ
RADAR = v5.RADAR
SNAP_DIR = RADAR / 'prewarm_snapshots'
SNAP_LATEST = RADAR / 'prewarm_snapshot_latest.json'
STATUS = RADAR / 'prewarm_snapshot_status.json'
SCHEMA = 1
BUILD_CUTOFF = dtime(9, 0, 45)
AUTHORITY = 'INFRASTRUCTURE_CACHE_ONLY_NO_SIGNAL_AUTHORITY'


def path_for(trade_date):
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    return SNAP_DIR / f'{trade_date.strftime("%Y%m%d")}_q017_model.json'


def _iso_dt(x):
    try:
        d = datetime.fromisoformat(str(x))
        return d if d.tzinfo else None
    except Exception:
        return None


def _coherence(today, hist_date, sf, dxy_status):
    return v4._coherence_status(today, hist_date, sf, dxy_status)


def prepare_from_persisted_premarket(today):
    """Build the same 11-field prepare_model tuple without re-downloading SOX.

    The 06:30 command-center premarket gate has already refreshed SOX and the
    electronics history. This step adds DXY and computes beta/previous-close so
    a complete causal fallback model is persisted well before 09:01.
    """
    if not core.DATA_STATUS.exists():
        raise RuntimeError('PREMARKET_DATA_STATUS_MISSING')
    gate = json.loads(core.DATA_STATUS.read_text(encoding='utf-8'))
    if gate.get('module') != 'DAILY_DATA_GATE' or gate.get('trade_date') != today.isoformat():
        raise RuntimeError('PREMARKET_GATE_TRADE_DATE_OR_MODULE_INVALID')
    if (gate.get('lane_status') or {}).get('q017_inputs') != 'PASS':
        raise RuntimeError('PREMARKET_Q017_INPUTS_NOT_PASS')
    if not core.SOX_STATUS.exists():
        raise RuntimeError('SOX_STATUS_MISSING_AFTER_PREMARKET')
    sox_status = json.loads(core.SOX_STATUS.read_text(encoding='utf-8'))
    seed = ((gate.get('required') or {}).get('electronics_history') or {'status': 'PASS', 'source': 'PERSISTED_PREMARKET'})
    history = core.load_tw_history()
    srows = core.read_sox()
    sf = core.sox_features(today)
    dxy_status = v4.fetch_dxy_5d(today)
    betas, prev, names, hist_date, universe = core.current_betas(history, srows)
    coh = _coherence(today, hist_date, sf, dxy_status)
    return gate, sox_status, dxy_status, seed, sf, betas, prev, names, hist_date, universe, coh


def _model_from_tuple(prepared):
    gate, sox_status, dxy_status, seed, sf, betas, prev, names, hist_date, universe, coh = prepared
    return {
        'gate': gate,
        'sox_status': sox_status,
        'dxy_status': dxy_status,
        'seed': seed,
        'sox_features': sf,
        'betas': betas,
        'previous_close': prev,
        'names': names,
        'history_date': str(hist_date),
        'universe': list(universe),
        'coherence': coh,
    }


def _tuple_from_model(m):
    return (
        m['gate'], m['sox_status'], m['dxy_status'], m['seed'], m['sox_features'],
        m['betas'], m['previous_close'], m['names'], m['history_date'], m['universe'], m['coherence'],
    )


def validate_prepared(prepared, trade_date):
    if not isinstance(prepared, tuple) or len(prepared) != 11:
        return False, 'PREPARED_TUPLE_SHAPE_INVALID'
    gate, sox_status, dxy_status, seed, sf, betas, prev, names, hist_date, universe, coh = prepared
    if (gate or {}).get('status') != 'PASS':
        return False, 'GATE_NOT_PASS'
    if (sox_status or {}).get('status') != 'PASS':
        return False, 'SOX_STATUS_NOT_PASS'
    if sf.get('sox_1d') is None or sf.get('sox_5d') is None:
        return False, 'SOX_FEATURES_MISSING'
    if (dxy_status or {}).get('status') != 'PASS' or (dxy_status or {}).get('dxy_5d') is None:
        return False, 'DXY_NOT_PASS'
    if not universe or not betas or not prev:
        return False, 'MODEL_EMPTY'
    try:
        hd = datetime.strptime(str(hist_date), '%Y-%m-%d').date()
    except Exception:
        return False, 'HISTORY_DATE_INVALID'
    if hd >= trade_date:
        return False, 'HISTORY_NOT_CAUSAL'
    if (coh or {}).get('status') != 'PASS':
        return False, 'COHERENCE_NOT_PASS'
    if any(str(t) not in set(str(x) for x in universe) for t in betas):
        return False, 'BETA_OUTSIDE_UNIVERSE'
    return True, 'PASS'


def make_payload(prepared, trade_date, generated_at=None):
    generated_at = generated_at or core.now_tw()
    model = _model_from_tuple(prepared)
    payload = {
        'schema_version': SCHEMA,
        'system': 'HENGCE',
        'module': 'Q017_PREMARKET_MODEL_SNAPSHOT',
        'trade_date': trade_date.isoformat(),
        'generated_at_taipei': generated_at.isoformat(),
        'authority': AUTHORITY,
        'formal_buy_count': 0,
        'late_market_backfill_forbidden': True,
        'intended_use': 'FALLBACK_PREPARE_MODEL_ONLY_BEFORE_OR_DURING_LEGAL_0901_OBSERVATION_WINDOW',
        'model': model,
    }
    payload['model_fingerprint_sha256'] = v5.csha(model)
    base = dict(payload)
    payload['snapshot_sha256'] = v5.csha(base)
    return payload


def validate_snapshot(payload, trade_date):
    if int(payload.get('schema_version') or 0) != SCHEMA:
        return False, 'SNAPSHOT_SCHEMA_INVALID'
    if payload.get('module') != 'Q017_PREMARKET_MODEL_SNAPSHOT':
        return False, 'SNAPSHOT_MODULE_INVALID'
    if payload.get('authority') != AUTHORITY or int(payload.get('formal_buy_count') or -1) != 0:
        return False, 'SNAPSHOT_AUTHORITY_INVALID'
    if payload.get('trade_date') != trade_date.isoformat():
        return False, 'SNAPSHOT_TRADE_DATE_MISMATCH'
    generated = _iso_dt(payload.get('generated_at_taipei'))
    if generated is None:
        return False, 'SNAPSHOT_GENERATED_AT_INVALID'
    local = generated.astimezone(TZ)
    if local.date() != trade_date or local.time().replace(tzinfo=None) > BUILD_CUTOFF:
        return False, 'SNAPSHOT_NOT_PRE0901_CAUSAL'
    model = payload.get('model') or {}
    if payload.get('model_fingerprint_sha256') != v5.csha(model):
        return False, 'MODEL_FINGERPRINT_MISMATCH'
    base = dict(payload); claimed = base.pop('snapshot_sha256', None)
    if claimed != v5.csha(base):
        return False, 'SNAPSHOT_HASH_MISMATCH'
    try:
        prepared = _tuple_from_model(model)
    except Exception:
        return False, 'SNAPSHOT_MODEL_SHAPE_INVALID'
    ok, reason = validate_prepared(prepared, trade_date)
    if not ok:
        return False, reason
    return True, 'PASS'


def load_snapshot(trade_date):
    p = path_for(trade_date)
    if not p.exists():
        raise FileNotFoundError(str(p))
    payload = json.loads(p.read_text(encoding='utf-8'))
    ok, reason = validate_snapshot(payload, trade_date)
    if not ok:
        raise RuntimeError(f'PREWARM_SNAPSHOT_INVALID:{reason}')
    return _tuple_from_model(payload['model']), payload


def build(trade_date):
    now = core.now_tw()
    if trade_date != now.date():
        raise RuntimeError('SNAPSHOT_BUILD_ONLY_FOR_CURRENT_TRADE_DATE')
    if now.time().replace(tzinfo=None) > BUILD_CUTOFF:
        raise RuntimeError('SNAPSHOT_BUILD_AFTER_0900_45_FORBIDDEN')
    prepared = prepare_from_persisted_premarket(trade_date)
    ok, reason = validate_prepared(prepared, trade_date)
    if not ok:
        raise RuntimeError(f'PREPARED_MODEL_INVALID:{reason}')
    payload = make_payload(prepared, trade_date, generated_at=now)
    ok, reason = validate_snapshot(payload, trade_date)
    if not ok:
        raise RuntimeError(f'SNAPSHOT_SELF_VALIDATE_FAIL:{reason}')
    core.atomic_json(path_for(trade_date), payload)
    core.atomic_json(SNAP_LATEST, payload)
    core.atomic_json(STATUS, {
        'schema_version': 1,
        'module': 'Q017_PREMARKET_SNAPSHOT_STATUS',
        'trade_date': trade_date.isoformat(),
        'generated_at_taipei': now.isoformat(),
        'status': 'PASS',
        'authority': AUTHORITY,
        'snapshot_sha256': payload['snapshot_sha256'],
        'model_fingerprint_sha256': payload['model_fingerprint_sha256'],
        'formal_buy_count': 0,
    })
    return payload


def self_test():
    td = datetime(2026, 10, 21).date()
    prepared = (
        {'status':'PASS','module':'DAILY_DATA_GATE','trade_date':'2026-10-21'},
        {'status':'PASS','latest_session':'2026-10-20'},
        {'status':'PASS','dxy_5d':0.001,'latest_session':'2026-10-20','five_sessions_back':'2026-10-13'},
        {'status':'PASS'},
        {'sox_1d':-0.01,'sox_5d':-0.04,'latest_session':'2026-10-20'},
        {'2330':1.2}, {'2330':1000.0}, {'2330':'台積電'}, '2026-10-20', ['2330'], {'status':'PASS'},
    )
    ok, reason = validate_prepared(prepared, td); assert ok, reason
    generated = datetime(2026,10,21,6,30,tzinfo=TZ)
    payload = make_payload(prepared, td, generated)
    ok, reason = validate_snapshot(payload, td); assert ok, reason
    restored = _tuple_from_model(payload['model'])
    assert restored[4]['sox_5d'] == -0.04 and restored[5]['2330'] == 1.2
    broken = json.loads(json.dumps(payload)); broken['model']['betas']['2330'] = 9.9
    ok, reason = validate_snapshot(broken, td); assert not ok and reason == 'MODEL_FINGERPRINT_MISMATCH'
    late = make_payload(prepared, td, datetime(2026,10,21,9,0,46,tzinfo=TZ))
    ok, reason = validate_snapshot(late, td); assert not ok and reason == 'SNAPSHOT_NOT_PRE0901_CAUSAL'
    print(json.dumps({
        'self_test':'PASS','schema':SCHEMA,'authority':AUTHORITY,
        'build_cutoff_taipei':'09:00:45','tamper_rejected':True,
        'late_snapshot_rejected':True,'formal_buy_count':0,
    }, ensure_ascii=False))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['build','self-test'], required=True)
    args = ap.parse_args()
    if args.mode == 'self-test':
        return self_test()
    td = core.now_tw().date()
    try:
        out = build(td)
        print(json.dumps({'status':'PASS','trade_date':td.isoformat(),'snapshot_sha256':out['snapshot_sha256'],'authority':AUTHORITY}, ensure_ascii=False))
        return 0
    except Exception as exc:
        core.atomic_json(STATUS, {
            'schema_version':1,'module':'Q017_PREMARKET_SNAPSHOT_STATUS','trade_date':td.isoformat(),
            'generated_at_taipei':core.now_tw().isoformat(),'status':'DATA_PENDING','authority':AUTHORITY,
            'formal_buy_count':0,'error':repr(exc),'policy':'FAIL_CLOSED_NO_SNAPSHOT_NO_SIGNAL_AUTHORITY',
        })
        print(json.dumps({'status':'DATA_PENDING','error':repr(exc),'authority':AUTHORITY}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
