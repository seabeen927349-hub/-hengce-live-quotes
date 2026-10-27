from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import requests

TICKER = "8150"
NAME = "南茂"
START = pd.Timestamp("2023-10-27")
PRE_END = pd.Timestamp("2025-12-31")
OOS_START = pd.Timestamp("2026-01-01")
END = pd.Timestamp("2026-10-27")
WARMUP_START = pd.Timestamp("2023-07-01")
CAPITAL = 1_000_000.0
HALF_COST = 0.002  # 20bp each side => 40bp round trip benchmark
OUT = Path("research/nanmao_8150/output")
OUT.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 HENGCE/8150-3Y-research"})


def month_iter(start: pd.Timestamp, end: pd.Timestamp):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m == 13:
            y += 1
            m = 1


def num(x):
    if x is None:
        return np.nan
    s = str(x).replace(",", "").strip()
    if s in {"", "--", "---", "----", "除權", "除息", "除權息"}:
        return np.nan
    try:
        return float(s)
    except Exception:
        s2 = "".join(ch for ch in s if ch in "0123456789.-")
        try:
            return float(s2)
        except Exception:
            return np.nan


def roc_to_ts(s: str) -> pd.Timestamp:
    a, b, c = s.strip().split("/")
    return pd.Timestamp(int(a) + 1911, int(b), int(c))


def fetch_twse() -> pd.DataFrame:
    rows = []
    receipts = []
    for y, m in month_iter(WARMUP_START, END):
        url = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
        params = {"date": f"{y}{m:02d}01", "stockNo": TICKER, "response": "json"}
        last_err = None
        payload = None
        for attempt in range(5):
            try:
                r = SESSION.get(url, params=params, timeout=30)
                r.raise_for_status()
                payload = r.json()
                break
            except Exception as e:
                last_err = repr(e)
                time.sleep(1.2 * (attempt + 1))
        if payload is None:
            raise RuntimeError(f"TWSE fetch failed {y}-{m:02d}: {last_err}")
        receipts.append({"month": f"{y}-{m:02d}", "stat": payload.get("stat"), "rows": len(payload.get("data", []) or [])})
        for r in payload.get("data", []) or []:
            if len(r) < 9:
                continue
            d = roc_to_ts(r[0])
            rows.append({
                "Date": d,
                "Volume": num(r[1]),
                "Turnover": num(r[2]),
                "Open": num(r[3]),
                "High": num(r[4]),
                "Low": num(r[5]),
                "Close": num(r[6]),
                "Change": num(r[7]),
                "Transactions": num(r[8]),
            })
        time.sleep(0.12)
    df = pd.DataFrame(rows).drop_duplicates("Date").sort_values("Date").reset_index(drop=True)
    df = df[(df.Date >= WARMUP_START) & (df.Date <= END)].copy()
    if df.empty or df.Date.max() < END:
        raise RuntimeError(f"TWSE data incomplete: max={df.Date.max() if not df.empty else None}")
    (OUT / "twse_fetch_receipt.json").write_text(json.dumps(receipts, ensure_ascii=False, indent=2), encoding="utf-8")
    return df


def fetch_dividends() -> List[dict]:
    # External fallback solely for cash-distribution event dates/amounts; price is TWSE canonical.
    p1 = int(datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp())
    p2 = int(datetime(2026, 10, 28, tzinfo=timezone.utc).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{TICKER}.TW"
    params = {"period1": p1, "period2": p2, "interval": "1d", "events": "div,splits", "includeAdjustedClose": "true"}
    try:
        r = SESSION.get(url, params=params, timeout=30)
        r.raise_for_status()
        j = r.json()
        result = j["chart"]["result"][0]
        divs = []
        for _, ev in (result.get("events", {}).get("dividends", {}) or {}).items():
            dt = pd.Timestamp(datetime.fromtimestamp(int(ev["date"]), tz=timezone.utc)).tz_convert("Asia/Taipei").tz_localize(None).normalize()
            divs.append({"Date": str(dt.date()), "Amount": float(ev["amount"]), "Source": "Yahoo corporate-action event; TWSE remains canonical OHLC"})
        divs.sort(key=lambda x: x["Date"])
        return divs
    except Exception as e:
        return [{"error": repr(e), "Source": "Yahoo dividend event fetch failed"}]


def add_signal_adjusted(df: pd.DataFrame, dividends: List[dict]) -> pd.DataFrame:
    out = df.copy()
    for c in ["Open", "High", "Low", "Close"]:
        out[f"Adj{c}"] = out[c].astype(float)
    valid = [x for x in dividends if "Date" in x and "Amount" in x]
    audit = []
    for ev in valid:
        d = pd.Timestamp(ev["Date"])
        amount = float(ev["Amount"])
        prev = out[out.Date < d].tail(1)
        if prev.empty:
            continue
        pc = float(prev.iloc[0].Close)
        if pc <= amount or pc <= 0:
            audit.append({**ev, "status": "SKIP_BAD_FACTOR", "prev_close": pc})
            continue
        f = (pc - amount) / pc
        mask = out.Date < d
        for c in ["Open", "High", "Low", "Close"]:
            out.loc[mask, f"Adj{c}"] *= f
        audit.append({**ev, "status": "APPLIED_BACK_ADJUST", "prev_close": pc, "factor": f})
    (OUT / "corporate_action_adjustment_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def dividend_cash(dividends: List[dict], entry_date: pd.Timestamp, exit_date: pd.Timestamp, shares: int) -> float:
    total = 0.0
    for ev in dividends:
        if "Date" not in ev:
            continue
        d = pd.Timestamp(ev["Date"])
        if entry_date < d <= exit_date:
            total += float(ev["Amount"]) * shares
    return total


def make_buy_signal(df: pd.DataFrame, lookback: int, dd: float) -> pd.Series:
    prior_high = df["AdjClose"].shift(1).rolling(lookback, min_periods=lookback).max()
    draw = df["AdjClose"] / prior_high - 1.0
    state = draw.le(-dd)
    armed = state | state.shift(1, fill_value=False)
    recovery = df["AdjClose"] > df["AdjHigh"].shift(1)
    sig = armed & recovery & (df.Date >= START)
    return sig.fillna(False)


def run_model(df: pd.DataFrame, dividends: List[dict], buy_lookback: int, buy_dd: float,
              sell_damage: float, sell_confirm: int, start: pd.Timestamp, end: pd.Timestamp,
              f0: float | None = None):
    sig = make_buy_signal(df, buy_lookback, buy_dd)
    n = len(df)
    trades = []
    holding = False
    pending_entry = None
    pending_exit = None
    entry_i = None
    entry_price = None
    shares = 0
    peak_adj_close = None
    below_count = 0
    exit_reason = None

    for i in range(n):
        d = df.iloc[i].Date
        if d < start:
            continue
        if d > end:
            break

        # execute pending exit at today's raw open
        if pending_exit is not None and i == pending_exit and holding:
            exit_price = float(df.iloc[i].Open)
            exit_date = d
            gross = (exit_price - entry_price) * shares
            divcash = dividend_cash(dividends, df.iloc[entry_i].Date, exit_date, shares)
            costs = (entry_price + exit_price) * shares * HALF_COST
            pnl = gross + divcash - costs
            trades.append({
                "EntryDate": str(df.iloc[entry_i].Date.date()), "Entry": entry_price,
                "ExitDate": str(exit_date.date()), "Exit": exit_price, "Shares": shares,
                "Gross": gross, "DividendCash": divcash, "Costs": costs, "PnL": pnl,
                "ExitReason": exit_reason,
            })
            holding = False
            pending_exit = None
            entry_i = None
            entry_price = None
            shares = 0
            peak_adj_close = None
            below_count = 0
            exit_reason = None

        # execute pending entry at today's raw open
        if pending_entry is not None and i == pending_entry and not holding:
            px = float(df.iloc[i].Open)
            lots = math.floor(CAPITAL / (px * 1000.0))
            if lots >= 1:
                holding = True
                entry_i = i
                entry_price = px
                shares = int(lots * 1000)
                peak_adj_close = float(df.iloc[i].AdjClose)
                below_count = 0
            pending_entry = None

        if holding:
            ac = float(df.iloc[i].AdjClose)
            if ac > peak_adj_close:
                peak_adj_close = ac
                below_count = 0
            threshold = peak_adj_close * (1.0 - sell_damage)
            if ac <= threshold:
                below_count += 1
            else:
                below_count = 0

            # optional entry-day nonstarter challenger
            if f0 is not None and i == entry_i and float(df.iloc[i].Close) <= float(df.iloc[i].Open) * (1.0 - f0):
                if i + 1 < n and df.iloc[i + 1].Date <= end:
                    pending_exit = i + 1
                    exit_reason = f"F0_{f0:.3f}"
            elif below_count >= sell_confirm and pending_exit is None:
                if i + 1 < n and df.iloc[i + 1].Date <= end:
                    pending_exit = i + 1
                    exit_reason = f"S1_D{sell_damage:.2f}_C{sell_confirm}"

        if (not holding) and pending_entry is None and bool(sig.iloc[i]):
            if i + 1 < n and df.iloc[i + 1].Date <= end:
                pending_entry = i + 1

    state = {
        "holding": holding,
        "pending_exit": pending_exit is not None,
        "pending_entry": pending_entry is not None,
        "entry_date": str(df.iloc[entry_i].Date.date()) if holding and entry_i is not None else None,
        "entry_price": entry_price,
        "shares": shares,
        "peak_adj_close": peak_adj_close,
        "last_date": str(df[df.Date <= end].iloc[-1].Date.date()),
        "last_close": float(df[df.Date <= end].iloc[-1].Close),
    }
    return pd.DataFrame(trades), state


def metrics(trades: pd.DataFrame) -> dict:
    if trades is None or trades.empty:
        return {"n": 0, "pnl": 0.0, "wr": np.nan, "pf": np.nan, "mdd": 0.0, "remove_best1": np.nan, "best": np.nan, "worst": np.nan,
                "pnl_2023": 0.0, "pnl_2024": 0.0, "pnl_2025": 0.0, "pnl_2026": 0.0}
    p = trades.PnL.astype(float)
    wins = p[p > 0].sum()
    losses = -p[p < 0].sum()
    pf = wins / losses if losses > 0 else (float("inf") if wins > 0 else np.nan)
    cum = p.cumsum()
    dd = cum - cum.cummax()
    years = pd.to_datetime(trades.ExitDate).dt.year
    y = {int(k): float(v) for k, v in p.groupby(years).sum().items()}
    return {
        "n": int(len(p)), "pnl": float(p.sum()), "wr": float((p > 0).mean()), "pf": float(pf),
        "mdd": float(dd.min()), "remove_best1": float(p.sum() - p.max()) if len(p) >= 2 else np.nan,
        "best": float(p.max()), "worst": float(p.min()),
        "pnl_2023": y.get(2023, 0.0), "pnl_2024": y.get(2024, 0.0), "pnl_2025": y.get(2025, 0.0), "pnl_2026": y.get(2026, 0.0),
    }


def finite_pf(x):
    if pd.isna(x): return np.nan
    if math.isinf(float(x)): return 99.0
    return float(x)


def main():
    raw = fetch_twse()
    divs = fetch_dividends()
    (OUT / "dividend_events.json").write_text(json.dumps(divs, ensure_ascii=False, indent=2), encoding="utf-8")
    df = add_signal_adjusted(raw, divs)
    three = df[(df.Date >= START) & (df.Date <= END)].copy()
    three.to_csv(OUT / "8150_3y_twse_canonical.csv", index=False, encoding="utf-8-sig")

    data_receipt = {
        "ticker": TICKER, "name": NAME,
        "requested_start": str(START.date()), "requested_end": str(END.date()),
        "rows_3y": int(len(three)), "min_date": str(three.Date.min().date()), "max_date": str(three.Date.max().date()),
        "duplicate_dates": int(three.Date.duplicated().sum()), "missing_ohlc_rows": int(three[["Open","High","Low","Close"]].isna().any(axis=1).sum()),
        "pre_selection_end": str(PRE_END.date()), "oos_start": str(OOS_START.date()),
        "selection_policy": "2026 OOS excluded from parameter selection",
        "price_source": "TWSE STOCK_DAY official",
        "corporate_action_policy": "Signal OHLC back-adjusted for cash dividends; execution uses raw TWSE open plus dividend cash while held",
    }
    (OUT / "DATA_RECEIPT.json").write_text(json.dumps(data_receipt, ensure_ascii=False, indent=2), encoding="utf-8")

    buy_family = [(lb, dd) for lb in [20, 40, 60] for dd in [0.10, 0.15, 0.20, 0.25, 0.30]]
    sell_family = [(d, c) for d in [0.08, 0.10, 0.12, 0.14, 0.16, 0.18] for c in [1, 2, 3]]

    sell_rows = []
    combo_rows = []
    for sd, sc in sell_family:
        variants = []
        for lb, bd in buy_family:
            tr, _ = run_model(df, divs, lb, bd, sd, sc, START, PRE_END)
            m = metrics(tr)
            row = {"sell_damage": sd, "sell_confirm": sc, "buy_lookback": lb, "buy_dd": bd, **m}
            combo_rows.append(row)
            if m["n"] >= 2:
                variants.append(row)
        v = pd.DataFrame(variants)
        if v.empty:
            agg = {"valid_buy_variants": 0}
        else:
            agg = {
                "valid_buy_variants": int(len(v)),
                "positive_share": float((v.pnl > 0).mean()),
                "median_pnl": float(v.pnl.median()),
                "mean_pnl": float(v.pnl.mean()),
                "median_mdd": float(v.mdd.median()),
                "median_pf": float(v.pf.map(finite_pf).median()),
                "median_trades": float(v.n.median()),
                "year24_positive_share": float((v.pnl_2024 > 0).mean()),
                "year25_positive_share": float((v.pnl_2025 > 0).mean()),
                "median_remove_best1": float(v.remove_best1.dropna().median()) if v.remove_best1.notna().any() else np.nan,
            }
        sell_rows.append({"sell_damage": sd, "sell_confirm": sc, **agg})
    sell_grid = pd.DataFrame(sell_rows)
    combo_grid = pd.DataFrame(combo_rows)
    sell_grid.to_csv(OUT / "SELL_GRID_PRE2026.csv", index=False)
    combo_grid.to_csv(OUT / "SELL_X_BUY_COMBO_PRE2026.csv", index=False)

    sell_grid["eligible"] = (
        (sell_grid.valid_buy_variants >= 8) & (sell_grid.positive_share >= 0.60) & (sell_grid.median_pnl > 0) &
        (sell_grid.year24_positive_share >= 0.50) & (sell_grid.year25_positive_share >= 0.50)
    )
    elig = sell_grid[sell_grid.eligible].copy()
    plateau_ids = []
    for idx, r in elig.iterrows():
        d, c = round(float(r.sell_damage), 2), int(r.sell_confirm)
        lo = sell_grid[(sell_grid.sell_confirm == c) & np.isclose(sell_grid.sell_damage, d - 0.02)]
        hi = sell_grid[(sell_grid.sell_confirm == c) & np.isclose(sell_grid.sell_damage, d + 0.02)]
        if len(lo) and len(hi) and bool(lo.iloc[0].eligible) and bool(hi.iloc[0].eligible):
            plateau_ids.append(idx)
    plateau = elig.loc[plateau_ids].copy() if plateau_ids else pd.DataFrame()
    selection_note = ""
    if not plateau.empty:
        maxmed = float(plateau.median_pnl.max())
        near = plateau[plateau.median_pnl >= 0.80 * maxmed].copy()
        near["risk_abs"] = near.median_mdd.abs()
        sel_sell = near.sort_values(["risk_abs", "median_remove_best1"], ascending=[True, False]).iloc[0]
        selection_note = "selected pre-2026 from eligible interior plateau; among >=80% max median P/L chose smallest median MDD"
    elif not elig.empty:
        prereg = elig[np.isclose(elig.sell_damage, 0.12) & (elig.sell_confirm == 2)]
        if not prereg.empty:
            sel_sell = prereg.iloc[0]
            selection_note = "no complete interior plateau; pre-registered 12% x 2-close challenger survived eligibility"
        else:
            sel_sell = elig.sort_values(["positive_share", "median_remove_best1", "median_pnl"], ascending=False).iloc[0]
            selection_note = "no complete interior plateau; chose strongest eligible pre-2026 robustness"
    else:
        sel_sell = sell_grid.sort_values(["positive_share", "median_pnl"], ascending=False).iloc[0]
        selection_note = "NO eligible sell rule; best shown for research only"
    SD, SC = float(sel_sell.sell_damage), int(sel_sell.sell_confirm)

    # BUY / RESET selection with SELL frozen from pre-2026 only
    buy_rows = []
    for lb, bd in buy_family:
        tr, _ = run_model(df, divs, lb, bd, SD, SC, START, PRE_END)
        m = metrics(tr)
        buy_rows.append({"buy_lookback": lb, "buy_dd": bd, **m})
    buy_grid = pd.DataFrame(buy_rows)
    buy_grid["robust"] = (
        (buy_grid.n >= 4) & (buy_grid.pnl > 0) & (buy_grid.remove_best1 > 0) &
        (buy_grid.pf.map(finite_pf) > 1.0) & (buy_grid.pnl_2024 > 0) & (buy_grid.pnl_2025 > 0)
    )
    # neighborhood support: at least two adjacent candidates same lookback/dd or adjacent lookback positive after removing best
    neigh_support = []
    for _, r in buy_grid.iterrows():
        lb, bd = int(r.buy_lookback), float(r.buy_dd)
        nbr = buy_grid[
            (((buy_grid.buy_lookback == lb) & (np.isclose(buy_grid.buy_dd, bd - 0.05) | np.isclose(buy_grid.buy_dd, bd + 0.05)))) |
             ((np.isclose(buy_grid.buy_dd, bd)) & (buy_grid.buy_lookback.isin([lb - 20, lb + 20]))))
        ]
        good = ((nbr.pnl > 0) & (nbr.remove_best1 > 0) & (nbr.pf.map(finite_pf) > 1.0)).sum()
        neigh_support.append(int(good))
    buy_grid["neighbor_good_count"] = neigh_support
    buy_grid["plateau_robust"] = buy_grid.robust & (buy_grid.neighbor_good_count >= 2)
    buy_grid.to_csv(OUT / "BUY_RESET_GRID_PRE2026.csv", index=False)
    bsel = buy_grid[buy_grid.plateau_robust].copy()
    if not bsel.empty:
        sel_buy = bsel.sort_values(["remove_best1", "mdd", "pnl"], ascending=[False, False, False]).iloc[0]
        buy_note = "selected pre-2026 by robust remove-best performance with neighborhood support"
    else:
        bsel = buy_grid[buy_grid.robust].copy()
        if not bsel.empty:
            sel_buy = bsel.sort_values(["remove_best1", "pnl"], ascending=False).iloc[0]
            buy_note = "robust pre-2026 but no full neighborhood plateau; NOT FREEZE"
        else:
            sel_buy = buy_grid.sort_values(["remove_best1", "pnl"], ascending=False).iloc[0]
            buy_note = "no robust BUY candidate; research-only best"
    BL, BD = int(sel_buy.buy_lookback), float(sel_buy.buy_dd)

    # OOS 2026: fixed selected rules, no retune
    pre_trades, pre_state = run_model(df, divs, BL, BD, SD, SC, START, PRE_END)
    oos_trades, oos_state = run_model(df, divs, BL, BD, SD, SC, OOS_START, END)
    full_trades, full_state = run_model(df, divs, BL, BD, SD, SC, START, END)
    pre_m, oos_m, full_m = metrics(pre_trades), metrics(oos_trades), metrics(full_trades)
    pre_trades.to_csv(OUT / "SELECTED_TRADES_PRE2026.csv", index=False)
    oos_trades.to_csv(OUT / "SELECTED_TRADES_OOS2026.csv", index=False)
    full_trades.to_csv(OUT / "SELECTED_TRADES_FULL3Y.csv", index=False)

    # OOS neighborhoods to detect a needle without selecting on OOS
    oos_neighbors = []
    for lb, bd in buy_family:
        if abs(lb - BL) <= 20 and abs(bd - BD) <= 0.05 + 1e-9:
            tr, _ = run_model(df, divs, lb, bd, SD, SC, OOS_START, END)
            oos_neighbors.append({"buy_lookback": lb, "buy_dd": bd, **metrics(tr)})
    pd.DataFrame(oos_neighbors).to_csv(OUT / "OOS_BUY_NEIGHBORHOOD_2026.csv", index=False)

    # F0 bounded challenger: only report, never select base parameters around it.
    f0_rows = []
    for f0 in [0.01, 0.02, 0.03, 0.04]:
        trp, _ = run_model(df, divs, BL, BD, SD, SC, START, PRE_END, f0=f0)
        tro, _ = run_model(df, divs, BL, BD, SD, SC, OOS_START, END, f0=f0)
        f0_rows.append({"f0": f0, **{f"pre_{k}": v for k, v in metrics(trp).items()}, **{f"oos_{k}": v for k, v in metrics(tro).items()}})
    f0df = pd.DataFrame(f0_rows)
    f0df.to_csv(OUT / "F0_CHALLENGER.csv", index=False)
    f0_promote = False
    if not f0df.empty:
        base_pre, base_oos = pre_m["pnl"], oos_m["pnl"]
        good = f0df[(f0df.pre_pnl > base_pre) & (f0df.pre_mdd >= pre_m["mdd"]) & (f0df.pre_remove_best1 >= pre_m["remove_best1"])]
        if len(good) >= 3 and (good.oos_pnl > base_oos).mean() >= 0.75:
            f0_promote = True

    neigh = pd.DataFrame(oos_neighbors)
    oos_neigh_pos = float((neigh.pnl > 0).mean()) if not neigh.empty else 0.0
    sell_pre_ok = bool(sel_sell.get("eligible", False))
    buy_pre_ok = bool(sel_buy.get("robust", False)) and int(sel_buy.get("neighbor_good_count", 0)) >= 2
    oos_ok = bool(oos_m["pnl"] > 0 and finite_pf(oos_m["pf"]) > 1.0 and oos_neigh_pos >= 0.60)
    freeze = sell_pre_ok and buy_pre_ok and oos_ok
    authority = "FREEZE_CANDIDATE" if freeze else "SURVIVE_PROVISIONAL_NOT_FREEZE"

    selected = {
        "system": "HENGCE",
        "ticker": TICKER, "name": NAME,
        "scope": "single-stock-only",
        "window": [str(START.date()), str(END.date())],
        "governance": {"2026_used_for_selection": False, "append_only_research": True, "no_other_ticker_tuning": True},
        "sell": {"damage": SD, "confirm_closes": SC, "rule": f"while holding, after peak adjusted Close, {SC} consecutive closes <= peak*(1-{SD:.2f}); exit next trading-day raw Open", "selection_note": selection_note},
        "buy_reset": {"lookback": BL, "drawdown": BD, "rule": f"prior {BL} completed sessions highest adjusted Close; current or previous day drawdown <= -{BD:.0%}; today adjusted Close > prior day adjusted High; enter next trading-day raw Open", "selection_note": buy_note},
        "f0": {"promoted": f0_promote, "status": "NOT_PROMOTED" if not f0_promote else "CHALLENGER_SURVIVED_BUT_REQUIRES_SEPARATE_VERSION"},
        "performance": {"pre2026": pre_m, "oos2026": oos_m, "full3y": full_m, "oos_neighbor_positive_share": oos_neigh_pos},
        "current_model_state": full_state,
        "authority": authority,
    }
    (OUT / "SELECTED_SPEC.json").write_text(json.dumps(selected, ensure_ascii=False, indent=2, allow_nan=True), encoding="utf-8")

    # Human-readable report
    def fmtm(m):
        pf = m["pf"]
        pfs = "∞" if isinstance(pf, float) and math.isinf(pf) else (f"{pf:.2f}" if not pd.isna(pf) else "NA")
        return f"n={m['n']}, P/L={m['pnl']:,.0f}, WR={m['wr']:.1% if not pd.isna(m['wr']) else 0}, PF={pfs}, MDD={m['mdd']:,.0f}, remove-best1={m['remove_best1']:,.0f if not pd.isna(m['remove_best1']) else 0}"

    # Avoid nested conditional format quirks
    def mline(m):
        wr = "NA" if pd.isna(m["wr"]) else f"{m['wr']:.1%}"
        pf = "NA" if pd.isna(m["pf"]) else ("∞" if math.isinf(m["pf"]) else f"{m['pf']:.2f}")
        rb = "NA" if pd.isna(m["remove_best1"]) else f"{m['remove_best1']:,.0f}"
        return f"n={m['n']} | P/L={m['pnl']:,.0f} | WR={wr} | PF={pf} | MDD={m['mdd']:,.0f} | remove-best1={rb}"

    prereg = sell_grid[np.isclose(sell_grid.sell_damage, 0.12) & (sell_grid.sell_confirm == 2)]
    prereg_line = prereg.iloc[0].to_dict() if not prereg.empty else {}
    report = f"""# HENGCE 8150 南茂 — Three-Year Single-Stock Validation

## Verdict
**{authority}**

## Governance
- Exact research window: {START.date()} → {END.date()}
- Selection window: {START.date()} → {PRE_END.date()}
- Untouched OOS: {OOS_START.date()} → {END.date()}
- Only 8150 was used. No cross-stock tuning.
- TWSE STOCK_DAY is canonical OHLC. Corporate actions are used only to build a continuous signal series; execution remains raw TWSE next-open with cash dividends credited while held.

## Data receipt
- Rows in exact 3Y window: {len(three)}
- First / last: {three.Date.min().date()} / {three.Date.max().date()}
- Duplicates: {int(three.Date.duplicated().sum())}
- Missing OHLC rows: {int(three[['Open','High','Low','Close']].isna().any(axis=1).sum())}

## SELL selected without seeing 2026
- Damage: **{SD:.0%}** from peak adjusted closing price
- Confirmation: **{SC} consecutive closes** below the damage line
- Execution: next trading-day raw open
- Selection: {selection_note}

Pre-registered NM-S1 12% × 2-close challenger stats across BUY-family (pre-2026):
```json
{json.dumps(prereg_line, ensure_ascii=False, indent=2, default=str)}
```

## BUY / RESET selected without seeing 2026
- Prior completed-session close-high lookback: **{BL}**
- Required drawdown state: **-{BD:.0%}** or worse on current/previous day
- Recovery proof: adjusted Close > previous adjusted High
- Execution: next trading-day raw open
- Selection: {buy_note}

## Performance
### Pre-2026 selection period
{mline(pre_m)}

### 2026 OOS
{mline(oos_m)}

### Full 3Y descriptive only
{mline(full_m)}

OOS nearby BUY variants positive share: **{oos_neigh_pos:.0%}**

## F0
F0 1%–4% was tested only as a bounded challenger. Promotion result: **{f0_promote}**. It is not part of the selected base unless a separate version is explicitly approved.

## Current model state through {END.date()}
```json
{json.dumps(full_state, ensure_ascii=False, indent=2)}
```

## Interpretation
- FREEZE_CANDIDATE means the rule was selected on pre-2026 data and then independently survived 2026 OOS plus neighborhood checks.
- SURVIVE_PROVISIONAL_NOT_FREEZE means something material failed; do not promote it to production merely because the full-period backtest looks attractive.
"""
    (OUT / "VALIDATION_SUMMARY.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
