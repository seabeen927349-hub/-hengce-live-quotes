#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo('Asia/Taipei')
ENGINE = 'HENGCE_V43_DAILY'
MODEL = 'V43_EXPANDING_REGIME_ICIR'
CANONICAL_OBSERVER_COMMIT = '959f96831fdea65f32bed65ca11011d67328f695'
CANONICAL_CORE_BLOB = '584acac7a78d11440ba08a6c7fcf11cd3293d79a'
FROZEN_V43_SOURCE_BLOB = '60c3ce478c5f88bfce9263739a310ea5f5cf05a6'
FROZEN_EVENTS_SHA256 = 'ed5b0c4caff523525ecafb303e04dc82bc07d7d2fe706733edf4ce0180ecfd6e'
FROZEN_EVENT_COUNT = 30
FROZEN_LAST_EXIT = '2026-09-23'
LOCK_DATE = '2026-10-24'
BASELINE_CUTOFF = '2026-10-22'


def sha256_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load_core(path: Path):
    spec = importlib.util.spec_from_file_location('hengce_v43_frozen_core', path)
    if spec is None or spec.loader is None:
        raise RuntimeError('V43_CORE_IMPORT_SPEC_FAILED')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git_blob_sha_bytes(path: Path) -> str:
    data = path.read_bytes()
    header = f'blob {len(data)}\0'.encode()
    return hashlib.sha1(header + data).hexdigest()


def q(v, digits=6):
    if v is None:
        return None
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return round(float(v), digits)


def markdown(report: dict) -> str:
    s = report.get('screen') or {}
    picks = s.get('top3') or []
    lines = [
        '# 衡策 V43 每日獨立篩選報告',
        '',
        f"- 報告時間（台北）：`{report['generated_at_taipei']}`",
        f"- 資料日期：`{report['data']['max_date']}`",
        f"- Engine：`{ENGINE}`",
        f"- Frozen model：`{MODEL}`",
        f"- 狀態：`{report['status']}`",
        f"- 權限：`{report['authority']['authority']}`",
        '',
        '## 今日市場狀態',
        '',
        f"- Regime：**{s.get('regime', 'N/A')}**",
        f"- Breadth20：`{s.get('breadth20')}`",
        f"- V43 exposure：`{s.get('final_exposure')}`",
        f"- Risk multiplier：`{s.get('risk_multiplier')}`",
        f"- Predicted daily sigma：`{s.get('predicted_daily_sigma')}`",
        '',
        '## 今日 Top 3',
        '',
        '| 排名 | 股票 | V43 score | 組合權重 | 有效曝險權重 |',
        '|---:|---:|---:|---:|---:|',
    ]
    for i, p in enumerate(picks, 1):
        lines.append(f"| {i} | **{p['ticker']}** | {p['score']} | {p['portfolio_weight']} | {p['effective_weight']} |")
    if not picks:
        lines.append('| - | - | - | - | - |')
    lines += [
        '',
        '## Frozen schedule / prospective validation',
        '',
        f"- Schedule 狀態：`{report['schedule']['state']}`",
        f"- Pending candidate：`{json.dumps(report['schedule'].get('pending_candidate'), ensure_ascii=False)}`",
        f"- 今日是否為 frozen schedule signal：`{report['schedule']['today_is_frozen_schedule_signal']}`",
        f"- 完整 post-lock baskets：`{report['validation']['postlock_complete_baskets']}`",
        f"- Prospective 狀態：`{report['validation']['status']}`",
        '',
        '## 完整性',
        '',
        f"- Historical parity：`{report['integrity']['historical_parity_verified']}`",
        f"- Rebuilt events SHA-256：`{report['integrity']['rebuilt_events_sha256']}`",
        f"- Canonical observer commit：`{CANONICAL_OBSERVER_COMMIT}`",
        '',
        '> 這是衡策獨立 V43 篩選引擎的每日研究報告，不是 Q017 輸出，不是券商委託，不建立下單權限。每日 watchlist 不會被當成新的 H20 prospective basket；prospective 證據仍只依 frozen non-overlap schedule 計算。',
        '',
    ]
    return '\n'.join(lines)


def build_report(core, hist: Path, current: Path) -> dict:
    now = datetime.now(TAIPEI)
    core_blob = git_blob_sha_bytes(Path(core.__file__))
    if core_blob != CANONICAL_CORE_BLOB:
        raise RuntimeError(f'CANONICAL_CORE_BLOB_MISMATCH:{core_blob}')

    by, dates, mkt, features, breadth, market_vol, vol_hist = core.build_state(hist, current)
    if not dates:
        raise RuntimeError('V43_NO_DATES')
    di = {d: i for i, d in enumerate(dates)}
    max_date = dates[-1]
    cache = core.make_v6_cache(features)
    anchors = core.make_anchors(features, breadth, by, dates, di)

    s24, _, _ = core.simulate_schedule(cache, '2024-01-01', '2024-12-31', by, dates, breadth)
    s25, _, _ = core.simulate_schedule(cache, '2025-01-01', '2025-12-31', by, dates, breadth)
    s26f, _, _ = core.simulate_schedule(cache, '2026-01-01', BASELINE_CUTOFF, by, dates, breadth)
    frozen_rebuilt, frozen_invalid, _ = core.build_v43(
        s24 + s25 + s26f, features, anchors, by, dates, di, breadth, mkt, market_vol, vol_hist
    )
    rebuilt_sha = hashlib.sha256(core.event_bytes(frozen_rebuilt)).hexdigest()
    last_exit = max((e['exit_date'] for e in frozen_rebuilt), default=None)
    parity = (
        len(frozen_rebuilt) == FROZEN_EVENT_COUNT
        and rebuilt_sha == FROZEN_EVENTS_SHA256
        and last_exit == FROZEN_LAST_EXIT
        and not frozen_invalid
    )
    if not parity:
        raise RuntimeError(
            f'V43_HISTORICAL_PARITY_FAILURE:count={len(frozen_rebuilt)}:sha={rebuilt_sha}:last_exit={last_exit}:invalid={frozen_invalid}'
        )

    s26, _, pending = core.simulate_schedule(cache, '2026-01-01', max_date, by, dates, breadth)
    dynamic_events, dynamic_invalid, _ = core.build_v43(
        s24 + s25 + s26, features, anchors, by, dates, di, breadth, mkt, market_vol, vol_hist
    )
    frozen_signals = {e['signal_date'] for e in frozen_rebuilt}
    frozen_subset = [e for e in dynamic_events if e['signal_date'] in frozen_signals]
    dynamic_frozen_sha = hashlib.sha256(core.event_bytes(frozen_subset)).hexdigest()
    if dynamic_frozen_sha != FROZEN_EVENTS_SHA256:
        raise RuntimeError(f'V43_DYNAMIC_HISTORY_DRIFT:{dynamic_frozen_sha}')

    post_invalid = [x for x in dynamic_invalid if x[0] > LOCK_DATE]
    if post_invalid:
        raise RuntimeError(f'V43_POSTLOCK_RULE_EXECUTION_FAILURE:{post_invalid}')
    post = [e for e in dynamic_events if e['signal_date'] > LOCK_DATE]

    if max_date not in features or max_date not in breadth:
        raise RuntimeError(f'V43_LATEST_DATE_NOT_SCREENABLE:{max_date}')
    regime = 'STRONG' if breadth[max_date] >= core.BREADTH_CUTOFF else 'WEAK'
    weights, factor_diag, prior, fallback = core.weights_at(
        max_date, regime, anchors, for_prospective=(max_date > LOCK_DATE)
    )
    F = features[max_date]
    ranked = [(sum(weights[i] * vals[i] for i in range(5)), t) for t, vals in F.items()]
    ranked.sort(key=lambda z: (-z[0], z[1]))
    picks = [t for _, t in ranked[:core.TOPN]]
    if len(picks) != core.TOPN:
        raise RuntimeError('V43_NOT_ENOUGH_DAILY_PICKS')

    cw = core.uncapped_cov_weights(max_date, picks, dates, di, by)
    if cw is None:
        raise RuntimeError('V43_DAILY_COVARIANCE_UNAVAILABLE')
    uncapped, sample_cov, shrunk_cov = cw
    portfolio_weights = core.cap_weights(uncapped, core.CAP)
    if portfolio_weights is None:
        raise RuntimeError('V43_DAILY_CAP_PROJECTION_FAILED')

    pseudo = {
        'signal_date': max_date,
        'regime': regime,
        'breadth20': breadth[max_date],
        'weights': portfolio_weights,
        'shrunk_covariance': shrunk_cov,
    }
    base_exposure = core.exposure(pseudo, dates, di, breadth, mkt, market_vol, vol_hist)
    vol_ratio = core.vol_ratio(pseudo, dates, di, breadth, mkt, market_vol, vol_hist)
    sigma = core.predicted_sigma(pseudo)
    prior_sigmas = [
        e['predicted_daily_sigma'] for e in dynamic_events
        if e['signal_date'] < max_date and e.get('predicted_daily_sigma') is not None
    ]
    q75 = core.quantile(prior_sigmas, core.TAIL_Q) if len(prior_sigmas) >= core.MIN_PRIOR_SIGMA else None
    fragile = regime == 'STRONG' and core.BREADTH_LO <= breadth[max_date] < core.BREADTH_HI
    tail = q75 is not None and sigma > q75 and sigma > 0
    risk_mult = (q75 / sigma) if fragile and tail else 1.0
    final_exposure = base_exposure * risk_mult

    score_map = dict(ranked)
    top3 = []
    for t, pw in zip(picks, portfolio_weights):
        vals = F[t]
        top3.append({
            'ticker': t,
            'score': q(score_map[t], 8),
            'portfolio_weight': q(pw, 8),
            'effective_weight': q(pw * final_exposure, 8),
            'factor_percentiles': {core.FACTORS[i]: q(vals[i], 8) for i in range(len(core.FACTORS))},
        })

    pending_date = pending.get('signal_date') if pending else None
    if pending_date == max_date:
        schedule_state = 'FROZEN_SCHEDULE_SIGNAL_TODAY_PENDING_H20'
    elif pending_date and pending_date < max_date:
        schedule_state = 'FROZEN_BASKET_ACTIVE_OR_AWAITING_COMPLETION'
    elif pending_date:
        schedule_state = 'FUTURE_PENDING_CANDIDATE'
    else:
        schedule_state = 'NO_PENDING_FROZEN_SCHEDULE_CANDIDATE'

    n = len(post)
    if n == 0:
        validation_status = 'WAITING_FOR_POST_LOCK_DATA'
    elif n < core.INTERIM_N:
        validation_status = 'ACCUMULATING_POST_LOCK_BASKETS'
    elif n < core.PRIMARY_N:
        validation_status = 'INTERIM_REVIEW_ELIGIBLE'
    else:
        validation_status = 'PRIMARY_REVIEW_ELIGIBLE'

    return {
        'schema_version': 1,
        'system': 'HENGCE',
        'engine': ENGINE,
        'model': MODEL,
        'lane': 'INDEPENDENT_DAILY_SCREENING_ENGINE',
        'status': 'PASS',
        'generated_at_taipei': now.isoformat(),
        'report_date_taipei': now.date().isoformat(),
        'authority': {
            'authority': 'SCREENING_ONLY_NO_ORDER_AUTHORITY',
            'capital_authority_twd': 0,
            'broker_order_execution': False,
            'production_promotion': False,
            'q017_engine_integration': False,
            'q017_write': False,
            'e2_write': False,
            'm1_write': False,
            'pr_30_merge': False,
        },
        'data': {
            'max_date': max_date,
            'current_history_sha256': sha256_path(current),
            'historical_frozen_sha256': sha256_path(hist),
            'current_history_role': 'READ_ONLY_EXISTING_ELECTRONICS_HISTORY_CACHE',
            'daily_report_is_independent_of_q017_decision_authority': True,
        },
        'integrity': {
            'canonical_observer_commit': CANONICAL_OBSERVER_COMMIT,
            'canonical_core_blob_expected': CANONICAL_CORE_BLOB,
            'canonical_core_blob_actual': core_blob,
            'frozen_v43_source_blob': FROZEN_V43_SOURCE_BLOB,
            'historical_parity_verified': parity,
            'rebuilt_event_count': len(frozen_rebuilt),
            'rebuilt_events_sha256': rebuilt_sha,
            'expected_events_sha256': FROZEN_EVENTS_SHA256,
            'last_frozen_exit': last_exit,
            'dynamic_frozen_subset_sha256': dynamic_frozen_sha,
            'new_model_evaluations': 0,
            'parameters_searched': 0,
            'historical_challenger_selection_rerun': False,
        },
        'screen': {
            'signal_date': max_date,
            'report_kind': 'DAILY_WATCHLIST_NOT_A_NEW_H20_BASKET',
            'research_entry_semantics': 'NEXT_SESSION_OPEN_IF_AND_ONLY_IF_FROZEN_SCHEDULE_SELECTS_SIGNAL;NO_ORDER_AUTHORITY',
            'regime': regime,
            'breadth20': q(breadth[max_date], 8),
            'factor_weights': {core.FACTORS[i]: q(weights[i], 8) for i in range(len(core.FACTORS))},
            'factor_icir': factor_diag,
            'prior_same_regime_realized_anchors': len(prior),
            'fallback_used': bool(fallback),
            'base_exposure': q(base_exposure, 8),
            'vol_ratio': q(vol_ratio, 8),
            'predicted_daily_sigma': q(sigma, 8),
            'prior_sigma_q75': q(q75, 8),
            'fragile_strong': fragile,
            'tail_vol': tail,
            'risk_multiplier': q(risk_mult, 8),
            'final_exposure': q(final_exposure, 8),
            'top3': top3,
            'sample_covariance': sample_cov,
            'shrunk_covariance': shrunk_cov,
        },
        'schedule': {
            'state': schedule_state,
            'pending_candidate': pending,
            'today_is_frozen_schedule_signal': bool(pending_date == max_date),
            'daily_watchlist_does_not_increment_validation_baskets': True,
        },
        'validation': {
            'lock_date': LOCK_DATE,
            'status': validation_status,
            'postlock_complete_baskets': n,
            'postlock_signal_dates': [e['signal_date'] for e in post],
            'first_6_role': 'INTERIM_NON_DECISIONAL',
            'first_12_role': 'PRIMARY_REGISTERED_READ',
        },
        'notes': [
            'V43 is an independent HENGCE screening engine, not a Q017 submodule.',
            'The existing electronics history cache is read-only input data and creates no Q017 decision dependency or authority.',
            'Daily reports are informational watchlists; frozen H20 schedule remains the only prospective basket clock.',
            'No parameter tuning, V45, broker order, or automatic production promotion is authorized.',
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--core', type=Path, required=True)
    ap.add_argument('--historical-gz', type=Path, required=True)
    ap.add_argument('--current-csv', type=Path, required=True)
    ap.add_argument('--out-dir', type=Path, default=Path('hengce/v43_daily'))
    args = ap.parse_args()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / 'history').mkdir(parents=True, exist_ok=True)
    core = load_core(args.core)
    report = build_report(core, args.historical_gz, args.current_csv)
    report_date = report['report_date_taipei'].replace('-', '')
    data_date = report['data']['max_date'].replace('-', '')
    stem = f'{report_date}_data_{data_date}'
    text = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    md = markdown(report)
    (out / 'latest.json').write_text(text, encoding='utf-8')
    (out / 'LATEST_REPORT.md').write_text(md, encoding='utf-8')
    (out / 'history' / f'{stem}.json').write_text(text, encoding='utf-8')
    (out / 'history' / f'{stem}.md').write_text(md, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
