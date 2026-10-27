from __future__ import annotations

import importlib.util
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BASE_PATH = Path(__file__).with_name("frozen_3m_to_1y_20261026.py")
OUT = ROOT / "research/codex_full_reset_20261023/results/frozen_fixed_capital_roundlot_20261026"
OUT.mkdir(parents=True, exist_ok=True)

INITIAL_CAPITAL = 1_000_000.0
LOT_SIZE = 1000
COST = 0.004
RECENT_START = pd.Timestamp("2026-07-22")
RECENT_END = pd.Timestamp("2026-10-21")
YEAR_START = pd.Timestamp("2025-10-22")
YEAR_END = pd.Timestamp("2026-10-21")


def load_base_module():
    spec = importlib.util.spec_from_file_location("frozen_base", BASE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def profit_factor(pnls: pd.Series) -> float | None:
    if pnls.empty:
        return None
    pos = float(pnls[pnls > 0].sum())
    neg = float(pnls[pnls < 0].sum())
    if neg == 0:
        return None if pos == 0 else math.inf
    return pos / abs(neg)


def max_drawdown(equity: pd.Series) -> tuple[float, float]:
    if equity.empty:
        return 0.0, 0.0
    peak = equity.cummax()
    dd = equity - peak
    dd_pct = equity / peak - 1.0
    return float(dd.min()), float(dd_pct.min())


def make_event_frame(panel: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    x = panel.copy()
    g = x.groupby("Ticker", group_keys=False)
    x["entry_date"] = g["Date"].shift(-1)
    x["exit_date"] = g["Date"].shift(-5)
    e = x.loc[x["signal"] & x["Date"].between(start, end)].copy()
    e = e.dropna(subset=["entry_date", "exit_date", "entry_open_t1", "exit_close_t5", "gross_ret"])
    e["entry_date"] = pd.to_datetime(e["entry_date"])
    e["exit_date"] = pd.to_datetime(e["exit_date"])
    e = e.sort_values(["entry_date", "Ticker", "Date"]).reset_index(drop=True)
    return e


def simulate(panel: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, label: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    events = make_event_frame(panel, start, end)
    if events.empty:
        return pd.DataFrame(), pd.DataFrame(), {"label": label, "error": "no events"}

    all_dates = sorted(pd.to_datetime(panel["Date"].dropna().unique()))
    dmin = events["entry_date"].min()
    dmax = events["exit_date"].max()
    calendar = [pd.Timestamp(d) for d in all_dates if dmin <= pd.Timestamp(d) <= dmax]

    close_lookup = {(pd.Timestamp(r.Date), str(r.Ticker)): float(r.Close) for r in panel[["Date", "Ticker", "Close"]].itertuples(index=False) if pd.notna(r.Close)}
    entry_groups = {pd.Timestamp(d): z.copy() for d, z in events.groupby("entry_date")}

    cash = INITIAL_CAPITAL
    swept_profit = 0.0
    open_pos: list[dict] = []
    trades: list[dict] = []
    daily: list[dict] = []
    skipped_zero_lot = 0
    selected_signals = 0
    max_concurrent = 0
    max_deployed_basis = 0.0

    for dt in calendar:
        # Morning entries. Same-day signals get one frozen equal-cash target.
        new = entry_groups.get(dt)
        if new is not None and len(new):
            n = int(len(new))
            target_cash = cash / n if n else 0.0
            allocations = []
            for r in new.itertuples(index=False):
                px = float(r.entry_open_t1)
                lot_cost = px * LOT_SIZE
                lots = int(math.floor((target_cash + 1e-9) / lot_cost)) if lot_cost > 0 else 0
                shares = lots * LOT_SIZE
                notional = shares * px
                if shares <= 0:
                    skipped_zero_lot += 1
                    continue
                allocations.append((r, px, shares, notional))

            # Equal targets guarantee aggregate cost <= starting cash, but guard rounding explicitly.
            total_need = float(sum(a[3] for a in allocations))
            if total_need > cash + 1e-6:
                raise RuntimeError(f"allocation exceeded cash on {dt.date()}: need={total_need} cash={cash}")

            for r, px, shares, notional in allocations:
                cash -= notional
                selected_signals += 1
                open_pos.append({
                    "signal_date": pd.Timestamp(r.Date),
                    "entry_date": pd.Timestamp(r.entry_date),
                    "exit_date": pd.Timestamp(r.exit_date),
                    "ticker": str(r.Ticker),
                    "name": getattr(r, "Name", None),
                    "entry_price": px,
                    "exit_price": float(r.exit_close_t5),
                    "shares": int(shares),
                    "entry_notional": float(notional),
                    "last_mark": px,
                })

        # Mark at today's close before exits.
        for p in open_pos:
            mark = close_lookup.get((dt, p["ticker"]))
            if mark is not None and np.isfinite(mark):
                p["last_mark"] = float(mark)

        # Close positions at t+5 close. Profits can restore prior capital loss, but deployable
        # basis (cash + remaining entry basis) is capped at the original NT$1m; excess is swept.
        exiting = [p for p in open_pos if p["exit_date"] == dt]
        if exiting:
            exiting_ids = {id(p) for p in exiting}
            remaining = [p for p in open_pos if id(p) not in exiting_ids]
            for p in exiting:
                gross_pnl = p["shares"] * (p["exit_price"] - p["entry_price"])
                cost_amt = COST * p["entry_notional"]
                pnl = gross_pnl - cost_amt
                cash += p["entry_notional"] + pnl
                trades.append({
                    **p,
                    "gross_pnl": float(gross_pnl),
                    "cost": float(cost_amt),
                    "pnl": float(pnl),
                    "net_return": float(pnl / p["entry_notional"]),
                })
            open_pos = remaining

            open_basis = float(sum(p["entry_notional"] for p in open_pos))
            excess = max(0.0, cash + open_basis - INITIAL_CAPITAL)
            if excess > 0:
                cash -= excess
                swept_profit += excess

        open_basis = float(sum(p["entry_notional"] for p in open_pos))
        max_concurrent = max(max_concurrent, len(open_pos))
        max_deployed_basis = max(max_deployed_basis, open_basis)

        # Economic equity is mark-to-market, including swept profits. Reserve the frozen 40bp
        # round-trip cost on every still-open position so drawdown is not understated.
        marked_value = float(sum(p["shares"] * p["last_mark"] for p in open_pos))
        reserved_cost = float(sum(COST * p["entry_notional"] for p in open_pos))
        equity = cash + swept_profit + marked_value - reserved_cost
        daily.append({
            "date": dt,
            "cash": float(cash),
            "swept_profit": float(swept_profit),
            "open_positions": int(len(open_pos)),
            "open_entry_basis": open_basis,
            "marked_value": marked_value,
            "reserved_cost": reserved_cost,
            "equity": float(equity),
            "utilization": float(open_basis / INITIAL_CAPITAL),
        })

    tdf = pd.DataFrame(trades)
    ddf = pd.DataFrame(daily)
    if tdf.empty:
        return tdf, ddf, {"label": label, "error": "no round-lot trades", "raw_signals": int(len(events)), "skipped_zero_lot": int(skipped_zero_lot)}

    pnls = tdf["pnl"].astype(float)
    total_pnl = float(pnls.sum())
    mdd_amt, mdd_pct = max_drawdown(ddf["equity"].astype(float))
    best = sorted(pnls.tolist(), reverse=True)
    by_signal_date = tdf.groupby("signal_date")["pnl"].sum().sort_values(ascending=False)
    by_exit_date = tdf.groupby("exit_date")["pnl"].sum().sort_values(ascending=False)

    monthly_signal = tdf.assign(month=tdf["signal_date"].dt.to_period("M").astype(str)).groupby("month")["pnl"].agg(["count", "sum"]).reset_index()
    monthly_exit = tdf.assign(month=tdf["exit_date"].dt.to_period("M").astype(str)).groupby("month")["pnl"].agg(["count", "sum"]).reset_index()

    summary = {
        "label": label,
        "signal_window": [str(start.date()), str(end.date())],
        "governance": {
            "signal_rule": "unchanged frozen rule imported from frozen_3m_to_1y_20261026.py",
            "initial_capital": INITIAL_CAPITAL,
            "compounding": False,
            "lot_size": LOT_SIZE,
            "roundtrip_cost": COST,
            "same_entry_day_allocation": "equal cash target = available cash / number of signals; floor each target to whole 1000-share lots; no reallocation of unused target cash",
            "entry_timing": "t+1 open",
            "exit_timing": "t+5 close",
            "positive_profit_policy": "profits first restore any capital deficit; deployable cash + open entry basis capped at NT$1m; excess swept and never reinvested",
        },
        "raw_signals": int(len(events)),
        "selected_roundlot_trades": int(len(tdf)),
        "skipped_zero_lot": int(skipped_zero_lot),
        "unique_signal_dates": int(tdf["signal_date"].nunique()),
        "unique_entry_dates": int(tdf["entry_date"].nunique()),
        "total_pnl": total_pnl,
        "final_economic_equity": float(INITIAL_CAPITAL + total_pnl),
        "wins": int((pnls > 0).sum()),
        "losses": int((pnls <= 0).sum()),
        "win_rate": float((pnls > 0).mean()),
        "profit_factor": profit_factor(pnls),
        "mean_trade_pnl": float(pnls.mean()),
        "median_trade_pnl": float(pnls.median()),
        "max_drawdown_amount": mdd_amt,
        "max_drawdown_pct": mdd_pct,
        "max_concurrent_positions": int(max_concurrent),
        "max_deployed_entry_basis": float(max_deployed_basis),
        "max_utilization": float(max_deployed_basis / INITIAL_CAPITAL),
        "avg_daily_utilization": float(ddf["utilization"].mean()),
        "remove_best_trade_pnl": float(total_pnl - best[0]) if best else total_pnl,
        "remove_top2_trades_pnl": float(total_pnl - sum(best[:2])) if best else total_pnl,
        "remove_best_signal_date_pnl": float(total_pnl - by_signal_date.iloc[0]) if len(by_signal_date) else total_pnl,
        "remove_best_3_signal_dates_pnl": float(total_pnl - by_signal_date.head(3).sum()) if len(by_signal_date) else total_pnl,
        "remove_best_exit_date_pnl": float(total_pnl - by_exit_date.iloc[0]) if len(by_exit_date) else total_pnl,
        "monthly_by_signal_date": monthly_signal.to_dict(orient="records"),
        "monthly_by_exit_date": monthly_exit.to_dict(orient="records"),
    }
    return tdf, ddf, summary


def main():
    base = load_base_module()
    y26 = base.load_2026()
    hist, inventory = base.load_history()
    panel = base.build_panel(hist, y26)

    t3, d3, s3 = simulate(panel, RECENT_START, RECENT_END, "recent_3m")
    t1, d1, s1 = simulate(panel, YEAR_START, YEAR_END, "one_year")

    result = {
        "frozen_rule": {
            "conditions": [
                "breadth_ma20 < 0.50",
                "ret3 cross-sectional percentile <= 0.20",
                "gap cross-sectional percentile <= 0.20",
                "dist_ma10 cross-sectional percentile <= 0.20",
                "lower_wick <= same-date base-candidate median",
            ],
            "universe": "TWSE listed electronics / recovered type13 historical + 2026 formal electronics history",
        },
        "historical_inventory": inventory,
        "recent_3m": s3,
        "one_year": s1,
    }

    t3.to_csv(OUT / "trades_recent_3m.csv", index=False)
    d3.to_csv(OUT / "equity_recent_3m.csv", index=False)
    t1.to_csv(OUT / "trades_1y.csv", index=False)
    d1.to_csv(OUT / "equity_1y.csv", index=False)
    with open(OUT / "RESULT.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=True)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=True))


if __name__ == "__main__":
    main()
