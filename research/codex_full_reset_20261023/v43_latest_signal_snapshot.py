#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

# Import the locked V43 stack without flooding the snapshot log with historical reports.
with contextlib.redirect_stdout(io.StringIO()):
    import research.codex_full_reset_20261023.ranking_v43_expanding_regime_icir as v43

v41 = v43.v41
v13 = v41.v13
v27 = v41.v27

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research/codex_full_reset_20261023/v43_latest_signal_snapshot_result.json"
YEAR = "2026"
START, END = v13.PERIODS[YEAR]
CAPITAL_TWD = 10_000_000.0

# Reproduce the frozen V6 non-overlapping H20 schedule used upstream by V15/V19/V41/V43.
# Historical slots advance only after a valid 3-name signal. A slot whose H20 outcome is
# fully observable is classified REALIZED/CENSORED exactly as v13.simulate; the first slot
# whose H20 outcome is not yet observable is the current prospective schedule signal.
cache = v13.make_cache(v13.V6)
next_free = -1
history = []
current = None

for i, d in enumerate(v13.dates):
    if d < START or d > END or i < next_free:
        continue
    frozen_picks = cache.get(d, [])[:v13.TOPN]
    if len(frozen_picks) < v13.TOPN:
        continue
    xi = i + 1 + v13.H
    if xi >= len(v13.dates) or v13.dates[xi] > END:
        current = {"index": i, "signal_date": d, "frozen_v6_schedule_picks": frozen_picks}
        break
    outs = [(t, v13.outcome(t, i)) for t in frozen_picks]
    state = "CENSORED" if any(o is None for _, o in outs) else "REALIZED"
    history.append({
        "signal_date": d,
        "entry_date": v13.dates[i + 1],
        "exit_date": v13.dates[xi],
        "schedule_state": state,
        "frozen_v6_schedule_picks": frozen_picks,
    })
    next_free = xi + 1

if current is None:
    raise RuntimeError("No prospective V43 schedule signal found within current data window")

i = current["index"]
d = current["signal_date"]
F = v13.features.get(d, {})
if not F:
    raise RuntimeError(f"No V13 features on prospective signal date {d}")

breadth = v13.breadth[d]
regime = "STRONG" if breadth >= v13.BREADTH_CUTOFF else "WEAK"
factor_weights, factor_diag, prior, fallback = v43.weights_at(d, regime)
arr = [(sum(factor_weights[k] * vals[k] for k in range(5)), t) for t, vals in F.items()]
arr.sort(key=lambda z: (-z[0], z[1]))
top3 = [t for _, t in arr[:v43.TOPN]]
scores = {t: s for s, t in arr[:v43.TOPN]}
if len(top3) != v43.TOPN:
    raise RuntimeError(f"Only {len(top3)} V43 picks on {d}")

cw = v27.uncapped_cov_weights(d, top3)
if cw is None:
    raise RuntimeError(f"V43 covariance unavailable for {d} {top3}")
uncapped, sample_cov, shrunk_cov = cw
portfolio_weights = v27.cap_weights(uncapped, v43.CAP)
if portfolio_weights is None:
    raise RuntimeError(f"V43 cap projection failed for {d} {top3}")

entry_date = v13.dates[i + 1] if i + 1 < len(v13.dates) else None
last_completed = history[-1] if history else None
latest_date = v13.dates[-1]
entry_index = i + 1
required_exit_index = entry_index + v13.H
remaining_trading_sessions_after_data_asof = max(0, required_exit_index - (len(v13.dates) - 1))

allocation = {}
for t, w in zip(top3, portfolio_weights):
    erow = v13.by.get(entry_date, {}).get(t) if entry_date else None
    lrow = v13.by.get(latest_date, {}).get(t)
    entry_open = erow.o if erow else None
    latest_close = lrow.c if lrow else None
    target_twd = CAPITAL_TWD * w
    shares = int(target_twd // entry_open) if entry_open and entry_open > 0 else None
    deployed_twd = shares * entry_open if shares is not None else None
    cash_left_vs_target = target_twd - deployed_twd if deployed_twd is not None else None
    mtm_value = shares * latest_close if shares is not None and latest_close is not None else None
    mtm_return = latest_close / entry_open - 1 if entry_open and latest_close else None
    allocation[t] = {
        "portfolio_weight": w,
        "target_twd": target_twd,
        "entry_open": entry_open,
        "integer_shares_at_or_below_target": shares,
        "board_lots_1000": shares // 1000 if shares is not None else None,
        "odd_lot_shares": shares % 1000 if shares is not None else None,
        "deployed_twd": deployed_twd,
        "cash_left_vs_target": cash_left_vs_target,
        "latest_mark_date": latest_date,
        "latest_close": latest_close,
        "mtm_value": mtm_value,
        "mtm_return": mtm_return,
    }

result = {
    "status": "V43_LATEST_SCHEDULE_SIGNAL_SNAPSHOT",
    "data_asof": latest_date,
    "signal_date": d,
    "entry_date_if_observed": entry_date,
    "horizon_trading_days": v13.H,
    "required_exit_index_offset_from_entry": v13.H,
    "remaining_trading_sessions_after_data_asof": remaining_trading_sessions_after_data_asof,
    "exit_execution_rule": "close on the H20 scheduled exit trading date; no fixed target price and no early take-profit rule",
    "schedule": "frozen V6 non-overlapping H20 schedule; first not-yet-fully-realized slot",
    "regime": regime,
    "breadth20": breadth,
    "top3": top3,
    "ranking_scores": scores,
    "factor_names": list(v41.FACTORS),
    "factor_weights": dict(zip(v41.FACTORS, factor_weights)),
    "prior_same_regime_anchors": len(prior),
    "factor_weight_fallback": fallback,
    "portfolio_weights": dict(zip(top3, portfolio_weights)),
    "uncapped_portfolio_weights": dict(zip(top3, uncapped)),
    "capital_example_twd": CAPITAL_TWD,
    "allocation_at_entry_open": allocation,
    "last_completed_or_censored_schedule_slot": last_completed,
    "historical_schedule_slots_before_current": len(history),
    "authority": {
        "research_only": True,
        "capital_authority_twd": 0,
        "broker_order_execution": False,
        "production_promotion": False,
        "merge_authorized": False,
    },
    "caveat": "Snapshot only. Locked V43 ranking and schedule reproduced without retuning; current H20 outcome is intentionally unavailable.",
}
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("V43_LATEST_SIGNAL_JSON=" + json.dumps(result, ensure_ascii=False, separators=(",", ":")))
