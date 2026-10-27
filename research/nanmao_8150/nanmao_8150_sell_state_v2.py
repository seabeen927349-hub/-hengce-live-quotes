from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path('research/nanmao_8150/output/8150_3y_twse_canonical.csv')
OUT = Path('research/nanmao_8150/output_sell_v2')
OUT.mkdir(parents=True, exist_ok=True)

SEL_START = pd.Timestamp('2023-10-27')
SEL_END = pd.Timestamp('2025-12-31')
OOS_START = pd.Timestamp('2026-01-01')
END = pd.Timestamp('2026-10-27')

LOOKBACKS = [20, 40, 60, 90]
DAMAGES = [0.06, 0.08, 0.10, 0.12, 0.14]
CONFIRMS = [1, 2, 3]
HORIZONS = [10, 20, 40]


def load_data() -> pd.DataFrame:
    df = pd.read_csv(BASE)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    required = ['Date','Open','High','Low','Close','AdjOpen','AdjHigh','AdjLow','AdjClose']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f'missing columns: {missing}')
    return df


def trigger_events(df: pd.DataFrame, lookback: int, damage: float, confirm: int) -> pd.DataFrame:
    peak = df['AdjClose'].rolling(lookback, min_periods=lookback).max()
    threshold = peak * (1.0 - damage)
    below = df['AdjClose'] <= threshold

    count = 0
    rows = []
    for i in range(len(df)):
        if bool(below.iloc[i]):
            count += 1
        else:
            count = 0
        # transition-only trigger: exactly on the C-th consecutive damaged close
        if count != confirm:
            continue
        if i + 1 >= len(df):
            continue
        signal_date = df.iloc[i].Date
        exec_i = i + 1
        if df.iloc[exec_i].Date > END:
            continue
        exec_open = float(df.iloc[exec_i].Open)
        peak_signal = float(peak.iloc[i])
        if not np.isfinite(exec_open) or not np.isfinite(peak_signal):
            continue

        row = {
            'lookback': lookback,
            'damage': damage,
            'confirm': confirm,
            'SignalDate': str(signal_date.date()),
            'ExecDate': str(df.iloc[exec_i].Date.date()),
            'SignalClose': float(df.iloc[i].Close),
            'PeakAdjClose': peak_signal,
            'DamageAtSignal': float(df.iloc[i].AdjClose / peak_signal - 1.0),
            'ExitOpen': exec_open,
        }
        for h in HORIZONS:
            end_i = exec_i + h
            if end_i >= len(df) or df.iloc[end_i].Date > END:
                row[f'complete{h}'] = False
                continue
            seg = df.iloc[exec_i:end_i+1]
            max_close = float(seg['Close'].max())
            min_close = float(seg['Close'].min())
            max_adj = float(seg['AdjClose'].max())
            terminal = float(df.iloc[end_i].Close)
            row[f'complete{h}'] = True
            row[f'HoldReturn{h}'] = terminal / exec_open - 1.0
            row[f'MAE{h}'] = min_close / exec_open - 1.0
            row[f'MFE{h}'] = max_close / exec_open - 1.0
            row[f'Deep8_{h}'] = min_close <= exec_open * 0.92
            row[f'Rebound10_{h}'] = max_close >= exec_open * 1.10
            row[f'ReclaimPeak98_{h}'] = max_adj >= peak_signal * 0.98
        rows.append(row)
    return pd.DataFrame(rows)


def summarize(events: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    if events.empty:
        return {'n20': 0}
    e = events.copy()
    e['SignalDateTS'] = pd.to_datetime(e['SignalDate'])
    e = e[(e.SignalDateTS >= start) & (e.SignalDateTS <= end) & (e['complete20'] == True)].copy()
    if e.empty:
        return {'n20': 0}
    hold20 = e['HoldReturn20'].astype(float)
    out = {
        'n20': int(len(e)),
        'median_hold20': float(hold20.median()),
        'mean_hold20': float(hold20.mean()),
        'sell_better20_share': float((hold20 < 0).mean()),
        'deep8_20_share': float(e['Deep8_20'].astype(bool).mean()),
        'rebound10_20_share': float(e['Rebound10_20'].astype(bool).mean()),
        'reclaim_peak98_20_share': float(e['ReclaimPeak98_20'].astype(bool).mean()),
        'median_mae20': float(e['MAE20'].median()),
        'median_mfe20': float(e['MFE20'].median()),
    }
    for yr in [2023, 2024, 2025, 2026]:
        y = e[e.SignalDateTS.dt.year == yr]
        out[f'n_{yr}'] = int(len(y))
        out[f'sell_better20_share_{yr}'] = float((y.HoldReturn20 < 0).mean()) if len(y) else np.nan
        out[f'median_hold20_{yr}'] = float(y.HoldReturn20.median()) if len(y) else np.nan
    return out


def eligible_pre(m: dict) -> bool:
    # Selection is deliberately strict and pre-2026 only.
    if m.get('n20', 0) < 6:
        return False
    if m['sell_better20_share'] < 0.60:
        return False
    if m['median_hold20'] > -0.02:
        return False
    if m['deep8_20_share'] < 0.35:
        return False
    if m['reclaim_peak98_20_share'] > 0.40:
        return False
    for yr in [2024, 2025]:
        n = m.get(f'n_{yr}', 0)
        if n >= 2 and m.get(f'sell_better20_share_{yr}', 0) < 0.50:
            return False
    return True


def main():
    df = load_data()
    rows = []
    all_events = []
    for lb in LOOKBACKS:
        for d in DAMAGES:
            for c in CONFIRMS:
                ev = trigger_events(df, lb, d, c)
                if not ev.empty:
                    all_events.append(ev)
                pre = summarize(ev, SEL_START, SEL_END)
                rows.append({'lookback':lb,'damage':d,'confirm':c,**pre})

    grid = pd.DataFrame(rows)
    grid['eligible_pre'] = [eligible_pre(r) for r in grid.to_dict('records')]

    # Plateau support: same confirmation, adjacent damage OR adjacent lookback also eligible.
    plateau_counts = []
    for _, r in grid.iterrows():
        nbr = grid[
            (grid.index != r.name) &
            (grid.confirm == r.confirm) &
            (
                ((grid.lookback == r.lookback) & (np.isclose(grid.damage, r.damage - 0.02) | np.isclose(grid.damage, r.damage + 0.02))) |
                ((np.isclose(grid.damage, r.damage)) & (grid.lookback.isin([r.lookback - 20, r.lookback + 20, r.lookback - 30, r.lookback + 30])))
            )
        ]
        plateau_counts.append(int(nbr.eligible_pre.sum()))
    grid['eligible_neighbor_count'] = plateau_counts
    grid['plateau_pre'] = grid.eligible_pre & (grid.eligible_neighbor_count >= 1)

    candidates = grid[grid.plateau_pre].copy()
    if not candidates.empty:
        candidates['score'] = (
            candidates.sell_better20_share * 3.0
            + candidates.deep8_20_share * 1.5
            - candidates.reclaim_peak98_20_share * 2.0
            - candidates.rebound10_20_share * 1.0
            - candidates.median_hold20 * 2.0
        )
        selected = candidates.sort_values(['score','eligible_neighbor_count','n20'], ascending=False).iloc[0]
        selection_status = 'PRE2026_ELIGIBLE_PLATEAU'
    else:
        # Descriptive fallback only; cannot be frozen.
        fallback = grid[grid.n20 >= 6].copy()
        if fallback.empty:
            fallback = grid.copy()
        fallback['score'] = (
            fallback.sell_better20_share.fillna(0) * 3.0
            + fallback.deep8_20_share.fillna(0) * 1.5
            - fallback.reclaim_peak98_20_share.fillna(1) * 2.0
            - fallback.rebound10_20_share.fillna(1) * 1.0
            - fallback.median_hold20.fillna(0) * 2.0
        )
        selected = fallback.sort_values(['score','n20'], ascending=False).iloc[0]
        selection_status = 'NO_PRE2026_ELIGIBLE_RULE'

    lb, d, c = int(selected.lookback), float(selected.damage), int(selected.confirm)
    selected_events = trigger_events(df, lb, d, c)
    pre = summarize(selected_events, SEL_START, SEL_END)
    oos = summarize(selected_events, OOS_START, END)

    # OOS confirmation is diagnostic only, never used to change selected params.
    oos_ok = (
        oos.get('n20',0) >= 3
        and oos.get('sell_better20_share',0) >= 0.50
        and oos.get('median_hold20',1) < 0
        and oos.get('reclaim_peak98_20_share',1) <= 0.50
    )
    freeze_candidate = selection_status == 'PRE2026_ELIGIBLE_PLATEAU' and oos_ok
    authority = 'FREEZE_CANDIDATE' if freeze_candidate else 'NOT_FREEZE'

    # preregistered earlier idea, now tested as a structural state at 60-day peak.
    pre12 = grid[(grid.lookback==60) & np.isclose(grid.damage,0.12) & (grid.confirm==2)]
    pre12_record = pre12.iloc[0].to_dict() if len(pre12) else {}

    # Current state for selected rule as of END.
    peak = df['AdjClose'].rolling(lb, min_periods=lb).max()
    threshold = peak * (1-d)
    below = df['AdjClose'] <= threshold
    cnt = 0
    for v in below:
        cnt = cnt + 1 if bool(v) else 0
    last = df.iloc[-1]
    current = {
        'date': str(last.Date.date()),
        'close': float(last.Close),
        'lookback': lb,
        'peak_adj_close': float(peak.iloc[-1]),
        'damage_from_peak': float(last.AdjClose/peak.iloc[-1]-1),
        'sell_line': float(threshold.iloc[-1]),
        'consecutive_damaged_closes': int(cnt),
        'confirmed_sell_state': bool(cnt >= c),
    }

    grid.to_csv(OUT/'SELL_STATE_GRID_PRE2026.csv', index=False)
    selected_events.to_csv(OUT/'SELECTED_SELL_EVENTS_FULL3Y.csv', index=False)
    if all_events:
        pd.concat(all_events, ignore_index=True).to_csv(OUT/'ALL_SELL_EVENTS_FULL3Y.csv', index=False)

    result = {
        'ticker':'8150','name':'南茂','method':'buy-independent rolling-peak structural damage',
        'selection_window':[str(SEL_START.date()),str(SEL_END.date())],
        'oos_window':[str(OOS_START.date()),str(END.date())],
        'selected':{'lookback':lb,'damage':d,'confirm':c,'selection_status':selection_status},
        'pre2026':pre,'oos2026':oos,
        'preregistered_60d_12pct_2close':pre12_record,
        'current':current,'authority':authority,
        'notes':[
            'SELL selection does not use BUY entries or trade P/L.',
            'A signal is evaluated by what price does after the next-open exit over 20 sessions.',
            '2026 is not used to select parameters.',
            'NOT_FREEZE means do not use this as production execution authority.'
        ]
    }
    (OUT/'SELL_STATE_SPEC.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=True),encoding='utf-8')

    report = f'''# HENGCE 8150 南茂 — BUY-independent SELL State V2\n\n## Verdict\n**{authority}**\n\n## Selected pre-2026 structural state\n- Rolling peak lookback: **{lb} sessions**\n- Damage: **{d:.0%}**\n- Confirmation: **{c} consecutive closes**\n- Selection status: **{selection_status}**\n\n## Pre-2026\n```json\n{json.dumps(pre,ensure_ascii=False,indent=2,allow_nan=True)}\n```\n\n## 2026 untouched OOS\n```json\n{json.dumps(oos,ensure_ascii=False,indent=2,allow_nan=True)}\n```\n\n## Earlier 12% x 2-close idea, standardized to 60-day peak\n```json\n{json.dumps(pre12_record,ensure_ascii=False,indent=2,default=str,allow_nan=True)}\n```\n\n## Current state through 2026-10-27\n```json\n{json.dumps(current,ensure_ascii=False,indent=2)}\n```\n'''
    (OUT/'SELL_STATE_SUMMARY.md').write_text(report,encoding='utf-8')
    print(report)


if __name__ == '__main__':
    main()
