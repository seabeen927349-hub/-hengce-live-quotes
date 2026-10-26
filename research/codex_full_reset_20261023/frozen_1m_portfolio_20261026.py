from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "frozen_3m_to_1y_20261026.py"
OUT = HERE / "results/frozen_1m_portfolio_20261026"
OUT.mkdir(parents=True, exist_ok=True)

CAPITAL = 1_000_000.0
COST = 0.004
LOT = 1000
RECENT_START = pd.Timestamp("2026-07-22")
RECENT_END = pd.Timestamp("2026-10-21")
YEAR_START = pd.Timestamp("2025-10-22")
YEAR_END = pd.Timestamp("2026-10-21")

spec = importlib.util.spec_from_file_location("frozen_signal", BASE_PATH)
base = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(base)


def build_panel() -> pd.DataFrame:
    y26 = base.load_2026()
    hist, _ = base.load_history()
    x = base.build_panel(hist, y26)
    x = x.sort_values(["Ticker", "Date"]).copy()
    g = x.groupby("Ticker", group_keys=False)
    x["entry_date"] = g["Date"].shift(-1)
    x["exit_date"] = g["Date"].shift(-5)
    return x


def candidate_events(panel: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    e = panel.loc[
        panel["signal"]
        & panel["Date"].between(start, end)
        & panel["entry_open_t1"].notna()
        & panel["exit_close_t5"].notna()
        & panel["entry_date"].notna()
        & panel["exit_date"].notna()
    ].copy()
    e["lot_cost"] = e["entry_open_t1"] * LOT
    e["unit_net_ret"] = e["gross_ret"] - COST
    # Deterministic order only for logging; sizing is same-day equal-dollar.
    e = e.sort_values(["entry_date", "Ticker"]).reset_index(drop=True)
    return e


def allocate_equal_floor(day: pd.DataFrame, available: float) -> list[dict]:
    if day.empty or available <= 0:
        return []
    target = available / len(day)
    out = []
    for _, r in day.iterrows():
        lots = int(math.floor(target / r.lot_cost))
        if lots <= 0:
            continue
        notional = lots * r.lot_cost
        out.append({
            "signal_date": r.Date,
            "entry_date": r.entry_date,
            "exit_date": r.exit_date,
            "Ticker": r.Ticker,
            "Name": getattr(r, "Name", ""),
            "entry_price": float(r.entry_open_t1),
            "exit_price": float(r.exit_close_t5),
            "lots": lots,
            "shares": lots * LOT,
            "notional": float(notional),
            "gross_ret": float(r.gross_ret),
            "net_ret": float(r.unit_net_ret),
            "pl": float(notional * r.unit_net_ret),
        })
    return out


def simulate_strict_pool(events: pd.DataFrame) -> pd.DataFrame:
    """Fixed NT$1m notional pool, no leverage, no compounding.

    Existing positions reserve original entry notional until t+5 close. New orders
    enter at the open and therefore cannot reuse notional from positions that exit
    later at the same day's close. Realized P/L is tracked separately and never
    changes future sizing capacity.
    """
    if events.empty:
        return pd.DataFrame()
    entries = {d: g.copy() for d, g in events.groupby("entry_date")}
    all_dates = sorted(set(events.entry_date) | set(events.exit_date))
    active: list[dict] = []
    done: list[dict] = []
    for d in all_dates:
        reserved = sum(p["notional"] for p in active)
        available = max(0.0, CAPITAL - reserved)
        if d in entries:
            new = allocate_equal_floor(entries[d], available)
            active.extend(new)
        # Close exits happen after the open, so release after new allocations.
        still = []
        for p in active:
            if pd.Timestamp(p["exit_date"]) == pd.Timestamp(d):
                done.append(p)
            else:
                still.append(p)
        active = still
    return pd.DataFrame(done)


def simulate_no_overlap(events: pd.DataFrame) -> pd.DataFrame:
    """Conservative basket: while any basket is open, ignore new signals.

    A fresh basket may only enter on an open strictly after the prior basket's
    t+5 close, because that exit cash/notional is unavailable at that day's open.
    """
    if events.empty:
        return pd.DataFrame()
    done = []
    blocked_through = pd.Timestamp.min
    for d, day in events.groupby("entry_date", sort=True):
        d = pd.Timestamp(d)
        if d <= blocked_through:
            continue
        new = allocate_equal_floor(day, CAPITAL)
        if not new:
            continue
        done.extend(new)
        blocked_through = max(pd.Timestamp(p["exit_date"]) for p in new)
    return pd.DataFrame(done)


def pf(s: pd.Series):
    if s.empty:
        return None
    pos = float(s[s > 0].sum())
    neg = float(-s[s < 0].sum())
    if neg == 0:
        return math.inf if pos > 0 else None
    return pos / neg


def max_drawdown_realized(trades: pd.DataFrame):
    if trades.empty:
        return None
    x = trades.groupby("exit_date")["pl"].sum().sort_index().cumsum()
    dd = x - x.cummax().clip(lower=0)
    return float(dd.min())


def summarize(trades: pd.DataFrame, opportunities: pd.DataFrame) -> dict:
    if trades.empty:
        return {
            "trades": 0, "signal_dates_executed": 0, "opportunities": int(len(opportunities)),
            "total_pl": 0.0, "wr": None, "pf": None, "mdd_realized": None,
        }
    pl = trades.pl
    by_sig = trades.groupby("signal_date").pl.sum()
    best_trade = float(pl.max())
    top2 = float(pl.nlargest(min(2, len(pl))).sum())
    best_signal = float(by_sig.max())
    return {
        "trades": int(len(trades)),
        "tickers": int(trades.Ticker.nunique()),
        "signal_dates_executed": int(trades.signal_date.nunique()),
        "entry_dates_executed": int(trades.entry_date.nunique()),
        "opportunities": int(len(opportunities)),
        "opportunity_signal_dates": int(opportunities.Date.nunique()),
        "total_pl": float(pl.sum()),
        "return_on_initial_capital": float(pl.sum() / CAPITAL),
        "wr": float((pl > 0).mean()),
        "pf": pf(pl),
        "avg_trade_pl": float(pl.mean()),
        "median_trade_pl": float(pl.median()),
        "remove_best_trade_pl": float(pl.sum() - best_trade),
        "remove_top2_trades_pl": float(pl.sum() - top2),
        "remove_best_signal_date_pl": float(pl.sum() - best_signal),
        "mdd_realized": max_drawdown_realized(trades),
        "avg_notional_per_trade": float(trades.notional.mean()),
        "max_notional_single_trade": float(trades.notional.max()),
    }


def monthly(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {}
    z = trades.copy()
    z["month"] = pd.to_datetime(z.exit_date).dt.to_period("M").astype(str)
    out = {}
    for m, g in z.groupby("month"):
        out[m] = {"trades": int(len(g)), "pl": float(g.pl.sum()), "wr": float((g.pl > 0).mean()), "pf": pf(g.pl)}
    return out


def portfolio_day_audit(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {}
    dates = sorted(set(pd.to_datetime(trades.entry_date)) | set(pd.to_datetime(trades.exit_date)))
    rows=[]
    for d in dates:
        active = trades[(pd.to_datetime(trades.entry_date) <= d) & (pd.to_datetime(trades.exit_date) >= d)]
        rows.append((d, float(active.notional.sum()), int(len(active))))
    q = pd.DataFrame(rows, columns=["date","reserved_notional","active_positions"])
    return {
        "max_reserved_notional_naive_inclusive": float(q.reserved_notional.max()),
        "max_active_positions": int(q.active_positions.max()),
        "median_active_positions": float(q.active_positions.median()),
    }


def run_window(panel, start, end, label):
    opp = candidate_events(panel, start, end)
    out={}
    for name, fn in [("STRICT_POOL", simulate_strict_pool), ("NO_OVERLAP_BASKET", simulate_no_overlap)]:
        t = fn(opp)
        if not t.empty:
            t.to_csv(OUT / f"{label}_{name.lower()}_trades.csv", index=False)
        out[name] = {
            "summary": summarize(t, opp),
            "monthly_by_exit": monthly(t),
            "concurrency": portfolio_day_audit(t),
        }
    return out


def main():
    panel = build_panel()
    result = {
        "governance": {
            "signal_rule": "unchanged frozen 3M->1Y rule",
            "capital": CAPITAL,
            "compounding": False,
            "leverage": False,
            "round_lot_shares": LOT,
            "allocation": "same-entry-date equal-dollar target, floor to whole 1000-share lots; residual cash left idle",
            "cost": COST,
            "entry_exit_order": "t+1 open entries occur before any same-day t+5 close exits release capacity",
            "strict_pool": "active positions reserve entry notional against fixed NT$1m capacity; realized P/L never changes sizing capacity",
            "no_overlap": "ignore all new signals while a prior basket is open; next basket may enter only after prior exit date",
        },
        "recent_3m": run_window(panel, RECENT_START, RECENT_END, "3m"),
        "one_year": run_window(panel, YEAR_START, YEAR_END, "1y"),
    }
    # Executable survivor gate: both conservative capitalizations must remain profitable at 40bp on 3M and 1Y.
    vals=[]
    for w in ["recent_3m","one_year"]:
        for mode in ["STRICT_POOL","NO_OVERLAP_BASKET"]:
            vals.append(result[w][mode]["summary"]["total_pl"] > 0)
    result["executable_survivor"] = bool(all(vals))
    (OUT / "RESULT.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=True), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=True))

if __name__ == "__main__":
    main()
