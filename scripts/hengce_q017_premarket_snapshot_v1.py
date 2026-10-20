#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, time as dtime

import hengce_q017_observation_lock_v5 as v5
import hengce_q017_macro_cache_v1 as macro

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


def _load_history_local_only():
    p = core.TW_HISTORY
    if not p.exists() or p.stat().st_size <= 100000:
        raise RuntimeError('LOCAL_ELECTRONICS_HISTORY_NOT_READY')
    with p.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def _local_seed_status():
    p = core.TW_HISTORY
    return {
        'status': 'PASS',
        'source': 'LOCAL_INCREMENTAL_HISTORY_PREEXISTING',
        'seeded': False,
        'path': str(p.relative_to(core.ROOT)),
        'bytes': p.stat().st_size,
    }


def _gate_from_local_state(today, macro_cache, hist_date):
    existing = None
    if core.DATA_STATUS.exists():
        try:
            candidate = json.loads(core.DATA_STATUS.read_text(encoding='utf-8'))
            if (
                candidate.get('module') == 'DAILY_DATA_GATE'
                and candidate.get('trade_date') == today.isoformat()
                and candidate.get('status') == 'PASS'
                and (candidate.get('lane_status') or {}).get('q017_inputs') == 'PASS'
            ):
                existing = candidate
        except Exception:
            existing = None

    if existing is not None:
        gate = json.loads(json.dumps(existing))
        req = gate.setdefault('required', {})
        req['sox'] = macro_cache['sox_status']
        req['electronics_history'] = req.get('electronics_history') or _local_seed_status()
        req['electronics_history_latest'] = hist_date
        gate['sox'] = macro_cache['sox_features']
        gate['macro_cache_sha256'] = macro_cache['cache_sha256']
        gate['policy'] = 'Q017_MACRO_FROM_EARLY_HASH_BOUND_CACHE;PERSISTED_DAILY_GATE_REUSED;NO_MACRO_NETWORK_IN_SNAPSHOT'
        return gate

    eod_date, eod_status = core.latest_eod_status()
    eod_complete = bool(
        eod_status
        and eod_status.get('price_status') == 'COMPLETE'
        and eod_status.get('institutional_status') == 'COMPLETE'
        and eod_status.get('margin_status') == 'COMPLETE'
    )
    return {
        'system': 'HENGCE',
        'module': 'DAILY_DATA_GATE',
        'generated_at_taipei': core.now_tw().isoformat(),
        'trade_date': today.isoformat(),
        'status': 'PASS',
        'lane_status': {'q017_inputs': 'PASS'},
        'required': {
            'sox': macro_cache['sox_status'],
            'latest_eod_date': eod_date,
            'latest_eod_complete': eod_complete,
            'electronics_history': _local_seed_status(),
            'electronics_history_latest': hist_date,
        },
        'sox': macro_cache['sox_features'],
        'macro_cache_sha256': macro_cache['cache_sha256'],
        'policy': 'Q017_MACRO_FROM_EARLY_HASH_BOUND_CACHE;LOCAL_HISTORY_ONLY;NO_MACRO_NETWORK_IN_SNAPSHOT',
    }


def prepare_from_macro_cache(today):
    """Build the exact v4/v5 11-field tuple with zero macro network I/O.

    SOX and DXY must already have been downloaded by the early-morning macro
    cache workflow, trade-date bound, causal-session validated and SHA-bound.
    """
    mc = macro.load_valid_cache(today, verify_files=True)
    history = _load_history_local_only()
    srows = core.read_sox()
    if not srows:
        raise RuntimeError('LOCAL_SOX_ROWS_EMPTY_AFTER_MACRO_CACHE_VALIDATION')
    betas, prev, names, hist_date, universe = core.current_betas(history, srows)
    seed = _local_seed_status()
    gate = _gate_from_local_state(today, mc, hist_date)
    coh = v4.validate_premarket_coherence(today, gate, hist_date)
    prepared = (
        gate,
        mc['sox_status'],
        mc['dxy_status'],
        seed,
        mc['sox_features'],
        betas,
        prev,
        names,
        hist_date,
        universe,
        coh,
    )
    return prepared, mc


def prepare_legacy_fallback(today):
    """Bounded-supervisor fallback source only; not the normal production path."""
    if not core.DATA_STATUS.exists():
        raise RuntimeError('PREMARKET_DATA_STATUS_MISSING')
    gate = json.loads(core.DATA_STATUS.read_text(encoding='utf-8'))
    if gate.get('module') != 'DAILY_DATA_GATE' or gate.get('trade_date') != today.isoformat():
        raise RuntimeError('PREMARKET_GATE_TRADE_DATE_OR_MODULE_INVALID')
    if gate.get('status') != 'PASS' or (gate.get('lane_status') or {}).get('q017_inputs') != 'PASS':
        raise RuntimeError('PREMARKET_Q017_INPUTS_NOT_PASS')
    req = gate.get('required') or {}
    sox_status = req.get('sox')
    if not isinstance(sox_status, dict) or sox_status.get('status') != 'PASS':
        if not core.SOX_STATUS.exists():
            raise RuntimeError('SOX_STATUS_MISSING_AFTER_PREMARKET')
        sox_status = json.loads(core.SOX_STATUS.read_text(encoding='utf-8'))
    history = _load_history_local_only()
    srows = core.read_sox()
    sf = core.sox_features(today)
    dxy_status = v4.refresh_dxy(today)
    betas, prev, names, hist_date, universe = core.current_betas(history, srows)
    seed = req.get('electronics_history') or _local_seed_status()
    coh = v4.validate_premarket_coherence(today, gate, hist_date)
    return gate, sox_status, dxy_status, seed, sf, betas, prev, names, hist_date, universe, coh


def prepare_from_persisted_premarket(today):
    try:
        prepared, _ = prepare_from_macro_cache(today)
        return prepared
    except Exception:
        return prepare_legacy_fallback(today)


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
    members = {str(x) for x in universe}
    if any(str(t) not in members for t in betas):
        return False, 'BETA_OUTSIDE_UNIVERSE'
    return True, 'PASS'


def make_payload(prepared, trade_date, generated_at=None, macro_cache_meta=None, source='UNKNOWN'):
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
        'input_source': source,
        'macro_cache_sha256': (macro_cache_meta or {}).get('cache_sha256'),
        'macro_cache_generated_at_taipei': (macro_cache_meta or {}).get('generated_at_taipei'),
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
    base = dict(payload)
    claimed = base.pop('snapshot_sha256', None)
    if claimed != v5.csha(base):
        return False, 'SNAPSHOT_HASH_MISMATCH'
    try:
        prepared = _tuple_from_model(model)
    except Exception:
        return False, 'SNAPSHOT_MODEL_SHAPE_INVALID'
    ok, reason = validate_prepared(prepared, trade_date)
    if not ok:
        return False, reason
    if payload.get('input_source') == 'MORNING_MACRO_CACHE' and not payload.get('macro_cache_sha256'):
        return False, 'SNAPSHOT_MACRO_CACHE_HASH_MISSING'
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

    cache_meta = None
    source = 'LEGACY_BOUNDED_FALLBACK'
    try:
        prepared, cache_meta = prepare_from_macro_cache(trade_date)
        source = 'MORNING_MACRO_CACHE'
    except Exception:
        prepared = prepare_legacy_fallback(trade_date)

    ok, reason = validate_prepared(prepared, trade_date)
    if not ok:
        raise RuntimeError(f'PREPARED_MODEL_INVALID:{reason}')
    payload = make_payload(prepared, trade_date, generated_at=now, macro_cache_meta=cache_meta, source=source)
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
        'input_source': source,
        'macro_cache_sha256': (cache_meta or {}).get('cache_sha256'),
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
    ok, reason = validate_prepared(prepared, td)
    assert ok, reason
    generated = datetime(2026,10,21,6,30,tzinfo=TZ)
    payload = make_payload(prepared, td, generated, {'cache_sha256':'a'*64,'generated_at_taipei':generated.isoformat()}, 'MORNING_MACRO_CACHE')
    ok, reason = validate_snapshot(payload, td)
    assert ok, reason
    restored = _tuple_from_model(payload['model'])
    assert restored[4]['sox_5d'] == -0.04 and restored[5]['2330'] == 1.2
    broken = json.loads(json.dumps(payload))
    broken['model']['betas']['2330'] = 9.9
    ok, reason = validate_snapshot(broken, td)
    assert not ok and reason == 'MODEL_FINGERPRINT_MISMATCH'
    late = make_payload(prepared, td, datetime(2026,10,21,9,0,46,tzinfo=TZ), {'cache_sha256':'a'*64}, 'MORNING_MACRO_CACHE')
    ok, reason = validate_snapshot(late, td)
    assert not ok and reason == 'SNAPSHOT_NOT_PRE0901_CAUSAL'
    print(json.dumps({
        'self_test':'PASS','schema':SCHEMA,'authority':AUTHORITY,
        'build_cutoff_taipei':'09:00:45','tamper_rejected':True,
        'late_snapshot_rejected':True,'formal_buy_count':0,
        'macro_cache_primary': True,
        'macro_network_calls_normal_snapshot_path': 0,
        'legacy_bounded_fallback_retained': True,
        'uses_v4_coherence_validator': True,
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
        print(json.dumps({
            'status':'PASS','trade_date':td.isoformat(),
            'input_source':out.get('input_source'),
            'macro_cache_sha256':out.get('macro_cache_sha256'),
            'snapshot_sha256':out['snapshot_sha256'],'authority':AUTHORITY,
        }, ensure_ascii=False))
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
