#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

import research.codex_full_reset_20261023.ranking_v41_expanding_regime_ic as v41

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research/codex_full_reset_20261023/ranking_v44_leadership_persistence_result.json'
EVENTS = ROOT / 'research/codex_full_reset_20261023/ranking_v44_events.jsonl'

COSTS = (.008, .012, .016)
CAP = .50
TOPN = 3
LOOKBACK = 60
SUB = 20

V42_REF = {'ret': 2.7751303217562437, 'dd': -0.1624723468868463, 'rem': 1.4999109340753796}
V43_REF = {'ret': 3.4264542481969347, 'dd': -0.1766638170167315, 'rem': 1.9312210257960025}


def product(xs):
    n = 1.0
    for x in xs:
        n *= 1 + x
    return n - 1


def path_components(signal_date):
    """Canonical A-003 price-path family, computed only from data known at signal time.

    Five equal-weighted cross-sectional ranks:
      1) 60D medium-term strength
      2) persistence = minimum return across three non-overlapping 20D subperiods
      3) signed directional efficiency over 60D
      4) 60D return after removing the single best daily return
      5) distance lifted from the 60D low

    Eligibility is frozen to V13/V43's same-day electronics-only feature universe.
    """
    i = v41.DI[signal_date]
    if i < LOOKBACK:
        return {}, {}

    raw = {}
    for t in v41.v13.features.get(signal_date, {}):
        closes = []
        ok = True
        for j in range(i - LOOKBACK, i + 1):
            r = v41.v13.by[v41.v13.dates[j]].get(t)
            if r is None or r.c is None or r.c <= 0 or r.bad:
                ok = False
                break
            closes.append(r.c)
        if not ok:
            continue

        daily = [closes[j] / closes[j - 1] - 1 for j in range(1, len(closes))]
        strength = closes[-1] / closes[0] - 1

        sub_returns = (
            closes[SUB] / closes[0] - 1,
            closes[2 * SUB] / closes[SUB] - 1,
            closes[3 * SUB] / closes[2 * SUB] - 1,
        )
        persistence = min(sub_returns)

        path_len = sum(abs(x) for x in daily)
        directional_efficiency = strength / path_len if path_len > 0 else 0.0

        best_daily_i = max(range(len(daily)), key=lambda k: (daily[k], -k))
        ex_best = product([x for k, x in enumerate(daily) if k != best_daily_i])

        low = min(closes)
        lifted_from_low = closes[-1] / low - 1

        raw[t] = (
            strength,
            persistence,
            directional_efficiency,
            ex_best,
            lifted_from_low,
        )

    if not raw:
        return {}, {}

    component_names = (
        'strength60',
        'persistence_min_3x20',
        'directional_efficiency60',
        'ex_best_day_return60',
        'lifted_from_low60',
    )
    component_ranks = []
    for k in range(5):
        component_ranks.append(v41.v13.ranks({t: vals[k] for t, vals in raw.items()}))

    ranked = {
        t: tuple(component_ranks[k][t] for k in range(5))
        for t in raw
    }
    diag = {
        t: {
            'raw': dict(zip(component_names, raw[t])),
            'ranks': dict(zip(component_names, ranked[t])),
            'equal_weight_score': statistics.mean(ranked[t]),
        }
        for t in raw
    }
    return ranked, diag


def build():
    out = []
    invalid = []
    prior_sigma = []
    ranking_log = []

    for b in sorted(v41.v19.v15.base, key=lambda e: e['signal_date']):
        d = b['signal_date']
        si = v41.DI[d]
        regime = b['regime']

        ranked, diag = path_components(d)
        arr = [
            (statistics.mean(vals), t)
            for t, vals in ranked.items()
        ]
        arr.sort(key=lambda z: (-z[0], z[1]))
        picks = [t for _, t in arr[:TOPN]]

        ranking_log.append({
            'signal_date': d,
            'regime': regime,
            'eligible_path_names': len(ranked),
            'picks': picks,
            'pick_path_diagnostics': {t: diag[t] for t in picks},
        })

        if len(picks) < TOPN:
            invalid.append([d, 'NOT_ENOUGH_PICKS'])
            continue

        cw = v41.v27.uncapped_cov_weights(d, picks)
        if cw is None:
            invalid.append([d, 'COVARIANCE_UNAVAILABLE'])
            continue
        uncapped, cov, shr = cw
        weights = v41.v27.cap_weights(uncapped, CAP)
        if weights is None:
            invalid.append([d, 'CAP_PROJECTION_FAILED'])
            continue

        outs = []
        ok = True
        for t in picks:
            o = v41.v13.outcome(t, si)
            if o is None:
                ok = False
                break
            outs.append(o)
        if not ok:
            invalid.append([d, 'INVALID_OUTCOME'])
            continue

        gross = sum(wi * o[0] for wi, o in zip(weights, outs))
        daily = []
        for k in range(v41.v13.H + 1):
            daily.append([
                outs[0][3][k][0],
                sum(wi * o[3][k][1] for wi, o in zip(weights, outs)),
            ])

        e = {
            'signal_date': d,
            'entry_date': outs[0][1],
            'exit_date': outs[0][2],
            'tickers': picks,
            'uncapped_weights': uncapped,
            'weights': weights,
            'weight_cap': CAP,
            'sample_covariance': cov,
            'shrunk_covariance': shr,
            'gross_return': gross,
            'daily': daily,
            'regime': regime,
            'breadth20': b['breadth20'],
            'year': b['year'],
            'ranking_rule': 'A003_LEADERSHIP_PERSISTENCE_EQUAL_WEIGHT_5_PATH_RANKS',
            'path_diagnostics': {t: diag[t] for t in picks},
        }

        # Freeze V43/V41 execution and risk stack exactly.
        e['exposure'] = v41.v19.exposure(e)
        e['vol_ratio'] = v41.v19.vol_ratio(e)
        sig = v41.v30.predicted_sigma(e)
        q75 = (
            v41.v30.quantile(prior_sigma, v41.v30.TAIL_Q)
            if len(prior_sigma) >= v41.v30.MIN_PRIOR
            else None
        )
        breadth = e.get('breadth20')
        fragile = (
            regime == 'STRONG'
            and breadth is not None
            and v41.v30.BREADTH_LO <= breadth < v41.v30.BREADTH_HI
        )
        tail = q75 is not None and sig > q75 and sig > 0
        mult = (q75 / sig) if fragile and tail else 1.0
        e['predicted_daily_sigma'] = sig
        e['prior_sigma_q75'] = q75
        e['fragile_strong'] = fragile
        e['tail_vol'] = tail
        e['risk_multiplier'] = mult
        e['base_exposure'] = e['exposure']
        e['exposure'] = e['base_exposure'] * mult

        out.append(e)
        prior_sigma.append(sig)

    return out, invalid, ranking_log


def summarize(events, cost):
    nets = []
    nav = 1.0
    peak = 1.0
    mdd = 0.0
    for e in events:
        ex = e['exposure']
        net = ex * (e['gross_return'] - cost)
        nets.append(net)
        base = nav
        for j, (_d, r) in enumerate(e['daily']):
            temp = base * (
                1 + ex * r - (ex * cost if j == len(e['daily']) - 1 else 0)
            )
            peak = max(peak, temp)
            mdd = min(mdd, temp / peak - 1)
        nav = base * (1 + net)

    bi = max(range(len(nets)), key=lambda k: nets[k]) if nets else None
    return {
        'baskets': len(nets),
        'wins': sum(x > 0 for x in nets),
        'win_rate': sum(x > 0 for x in nets) / len(nets) if nets else None,
        'compounded_return': product(nets),
        'max_drawdown': mdd,
        'remove_best_basket_return': (
            product([x for k, x in enumerate(nets) if k != bi])
            if bi is not None and len(nets) > 1
            else None
        ),
        'mean_net_return': statistics.mean(nets) if nets else None,
        'best_basket_net': max(nets) if nets else None,
        'worst_basket_net': min(nets) if nets else None,
        'max_single_name_weight': max(
            (max(e['weights']) for e in events), default=None
        ),
        'mean_exposure': (
            statistics.mean([e['exposure'] for e in events]) if events else None
        ),
    }


EV, INVALID, RANKING_LOG = build()
complete = (not INVALID and len(EV) == len(v41.v19.v15.base))
years = {
    y: {
        str(c): summarize([e for e in EV if e['year'] == y], c)
        for c in COSTS
    }
    for y in v41.v13.PERIODS
}
combined = {str(c): summarize(EV, c) for c in COSTS}

robust = (
    complete
    and all(
        years[y]['0.012']['compounded_return'] > 0
        and years[y]['0.012']['remove_best_basket_return'] > 0
        for y in years
    )
    and all(years[y]['0.016']['compounded_return'] > 0 for y in years)
    and combined['0.012']['max_single_name_weight'] <= CAP + 1e-12
)

c = combined['0.012']


def dominates(ref):
    return (
        robust
        and c['compounded_return'] >= ref['ret']
        and c['max_drawdown'] >= ref['dd']
        and c['remove_best_basket_return'] >= ref['rem']
    )


def ref_dominates(ref):
    return (
        ref['ret'] >= c['compounded_return']
        and ref['dd'] >= c['max_drawdown']
        and ref['rem'] >= c['remove_best_basket_return']
    )


dom43 = dominates(V43_REF)
dom42 = dominates(V42_REF)
new_pareto = robust and not ref_dominates(V43_REF) and not ref_dominates(V42_REF)

if dom43:
    status = 'V44_DOMINATES_V43'
elif new_pareto:
    status = 'V44_NEW_PARETO_FRONTIER'
else:
    status = 'V44_DOES_NOT_IMPROVE_FRONTIER'

with EVENTS.open('w', encoding='utf-8') as fh:
    for e in EV:
        fh.write(json.dumps(e, ensure_ascii=False) + '\n')

res = {
    'status': status,
    'method': (
        'single fixed V44: standalone A-003 Leadership Persistence / low-detachment '
        'price-path ranking. Five canonical same-day path components are converted '
        'to cross-sectional ranks and equally weighted: 60D strength, minimum of '
        'three non-overlapping 20D subperiod returns, signed 60D directional '
        'efficiency, 60D return excluding the single best daily return, and distance '
        'lifted from the 60D low. Same V43 schedule, Top3/H20, cap50 covariance '
        'allocation and V30 fragile-strong risk overlay; no grid or new data.'
    ),
    'component_weights': {
        'strength60': 0.2,
        'persistence_min_3x20': 0.2,
        'directional_efficiency60': 0.2,
        'ex_best_day_return60': 0.2,
        'lifted_from_low60': 0.2,
    },
    'lookback_sessions': LOOKBACK,
    'subperiod_sessions': SUB,
    'ranking_log': RANKING_LOG,
    'complete_common_schedule': complete,
    'invalid': INVALID,
    'robust': robust,
    'years': years,
    'combined': combined,
    'v42_reference': V42_REF,
    'v43_reference': V43_REF,
    'dominates_v42': dom42,
    'dominates_v43': dom43,
    'new_pareto_frontier': new_pareto,
    'events_file': str(EVENTS.relative_to(ROOT)),
    'new_model_evaluations': 1,
    'authority': {
        'research_only': True,
        'capital_authority_twd': 0,
        'broker_order_execution': False,
        'production_promotion': False,
        'merge_authorized': False,
    },
    'caveat': (
        'A-003 is an existing surviving price-layer hypothesis, not a new '
        'fundamental data family. This run is one preregistered equal-weight '
        'structural path test on exposed 2024-2026 history; no retuning is allowed.'
    ),
}

OUT.write_text(
    json.dumps(res, ensure_ascii=False, indent=2) + '\n',
    encoding='utf-8',
)
print(json.dumps(res, ensure_ascii=False, indent=2))
