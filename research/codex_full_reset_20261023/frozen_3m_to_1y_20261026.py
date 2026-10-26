from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research/codex_full_reset_20261023/results/frozen_3m_1y_20261026"
OUT.mkdir(parents=True, exist_ok=True)

RECENT_START = pd.Timestamp("2026-07-22")
RECENT_END = pd.Timestamp("2026-10-21")
YEAR_START = pd.Timestamp("2025-10-22")
YEAR_END = pd.Timestamp("2026-10-21")
COST = 0.004

ALIASES = {
    "Date": ["Date", "date", "日期"],
    "Ticker": ["Ticker", "ticker", "Code", "code", "證券代號", "股票代號", "公司代號"],
    "Name": ["Name", "name", "證券名稱", "股票名稱", "公司名稱"],
    "Open": ["Open", "open", "開盤價"],
    "High": ["High", "high", "最高價"],
    "Low": ["Low", "low", "最低價"],
    "Close": ["Close", "close", "收盤價"],
    "Volume": ["Volume", "volume", "成交股數", "成交量"],
}


def _read_csv(path: Path, nrows=None) -> pd.DataFrame:
    last = None
    for enc in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False, nrows=nrows)
        except Exception as e:
            last = e
    raise RuntimeError(f"cannot read {path}: {last}")


def normalize(df: pd.DataFrame, source: str) -> pd.DataFrame | None:
    rename = {}
    cols = {str(c).strip(): c for c in df.columns}
    for target, aliases in ALIASES.items():
        for alias in aliases:
            if alias in cols:
                rename[cols[alias]] = target
                break
    x = df.rename(columns=rename).copy()
    needed = ["Date", "Ticker", "Open", "High", "Low", "Close"]
    if any(c not in x.columns for c in needed):
        return None
    keep = needed + (["Name"] if "Name" in x.columns else []) + (["Volume"] if "Volume" in x.columns else [])
    x = x[keep]
    x["Date"] = pd.to_datetime(x["Date"], errors="coerce")
    x["Ticker"] = x["Ticker"].astype(str).str.extract(r"(\d{4})", expand=False)
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        if c in x.columns:
            x[c] = pd.to_numeric(x[c].astype(str).str.replace(",", "", regex=False).replace({"--": np.nan, "---": np.nan}), errors="coerce")
    x = x.dropna(subset=["Date", "Ticker", "Open", "High", "Low", "Close"])
    x = x[x["Ticker"].str.fullmatch(r"\d{4}")]
    x["source_file"] = source
    return x


def load_2026() -> pd.DataFrame:
    path = ROOT / "hengce/q017_radar/data/twse_electronics_history_2026.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    x = normalize(_read_csv(path), str(path.relative_to(ROOT)))
    if x is None or x.empty:
        raise RuntimeError("2026 TWSE electronics file could not be normalized")
    return x


def historical_candidates() -> list[Path]:
    roots = [ROOT / "_frozen_artifacts", ROOT / "artifacts", ROOT / "research"]
    out = []
    for r in roots:
        if not r.exists():
            continue
        for p in r.rglob("*.csv"):
            if p.name == "twse_electronics_history_2026.csv":
                continue
            out.append(p)
    return sorted(set(out))


def load_history() -> tuple[pd.DataFrame, list[dict]]:
    pieces = []
    inventory = []
    for p in historical_candidates():
        try:
            head = _read_csv(p, nrows=5)
            h = normalize(head, str(p.relative_to(ROOT)))
            if h is None:
                continue
            full = normalize(_read_csv(p), str(p.relative_to(ROOT)))
            if full is None or full.empty:
                continue
            dmin, dmax = full["Date"].min(), full["Date"].max()
            # Only datasets that actually cover 2025 are candidates for the one-year bridge.
            if dmax < pd.Timestamp("2025-01-01") or dmin > pd.Timestamp("2025-12-31"):
                continue
            # The recovered artifacts are TWSE type13/electronics. Keep files with broad daily cross-sections.
            daily_n = full.groupby("Date")["Ticker"].nunique()
            med_daily = float(daily_n.median()) if len(daily_n) else 0.0
            inventory.append({
                "path": str(p.relative_to(ROOT)),
                "rows": int(len(full)),
                "date_min": str(dmin.date()),
                "date_max": str(dmax.date()),
                "unique_tickers": int(full["Ticker"].nunique()),
                "median_daily_tickers": med_daily,
            })
            if med_daily >= 150:
                pieces.append(full)
        except Exception:
            continue
    if not pieces:
        raise RuntimeError("No recovered 2025 TWSE electronics OHLCV dataset found in downloaded artifacts/repo")
    x = pd.concat(pieces, ignore_index=True)
    x = x.sort_values(["Date", "Ticker", "source_file"]).drop_duplicates(["Date", "Ticker"], keep="last")
    return x, inventory


def build_panel(hist: pd.DataFrame, y26: pd.DataFrame) -> pd.DataFrame:
    x = pd.concat([hist, y26], ignore_index=True, sort=False)
    x = x.sort_values(["Ticker", "Date", "source_file"]).drop_duplicates(["Ticker", "Date"], keep="last")
    x = x.sort_values(["Ticker", "Date"]).reset_index(drop=True)
    g = x.groupby("Ticker", group_keys=False)
    x["prev_close"] = g["Close"].shift(1)
    x["ret3"] = x["Close"] / g["Close"].shift(3) - 1
    x["ma10"] = g["Close"].transform(lambda s: s.rolling(10, min_periods=10).mean())
    x["ma20"] = g["Close"].transform(lambda s: s.rolling(20, min_periods=20).mean())
    x["gap"] = x["Open"] / x["prev_close"] - 1
    x["dist_ma10"] = x["Close"] / x["ma10"] - 1
    rng = x["High"] - x["Low"]
    x["lower_wick"] = (np.minimum(x["Open"], x["Close"]) - x["Low"]) / rng.replace(0, np.nan)
    x["above_ma20"] = x["Close"] > x["ma20"]
    x["breadth_ma20"] = x.groupby("Date")["above_ma20"].transform("mean")
    for c in ["ret3", "gap", "dist_ma10"]:
        x[c + "_rank"] = x.groupby("Date")[c].rank(pct=True, method="average")
    base = (
        (x["breadth_ma20"] < 0.50)
        & (x["ret3_rank"] <= 0.20)
        & (x["gap_rank"] <= 0.20)
        & (x["dist_ma10_rank"] <= 0.20)
    )
    x["base_candidate"] = base
    med_lw = x.loc[base].groupby("Date")["lower_wick"].median()
    x["candidate_lw_median"] = x["Date"].map(med_lw)
    x["signal"] = base & (x["lower_wick"] <= x["candidate_lw_median"])
    x["entry_open_t1"] = g["Open"].shift(-1)
    x["exit_close_t5"] = g["Close"].shift(-5)
    x["gross_ret"] = x["exit_close_t5"] / x["entry_open_t1"] - 1
    x["net_ret_40bp"] = x["gross_ret"] - COST
    return x


def pf(s: pd.Series) -> float | None:
    s = s.dropna()
    pos = s[s > 0].sum()
    neg = s[s < 0].sum()
    if neg == 0:
        return None if pos == 0 else math.inf
    return float(pos / abs(neg))


def summarize(events: pd.DataFrame, cost=0.004) -> dict:
    if events.empty:
        return {"n": 0, "signal_dates": 0, "mean": None, "median": None, "wr": None, "pf": None}
    r = events["gross_ret"] - cost
    return {
        "n": int(len(events)),
        "signal_dates": int(events["Date"].nunique()),
        "mean": float(r.mean()),
        "median": float(r.median()),
        "wr": float((r > 0).mean()),
        "pf": pf(r),
    }


def period_eval(panel: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.DataFrame, dict]:
    e = panel.loc[panel["signal"] & panel["Date"].between(start, end)].copy()
    e = e.dropna(subset=["entry_open_t1", "exit_close_t5", "gross_ret"])
    summary = summarize(e, COST)
    monthly = {}
    for m, sub in e.groupby(e["Date"].dt.to_period("M")):
        monthly[str(m)] = summarize(sub, COST)
    dates = sorted(e["Date"].unique())
    half = len(dates) // 2
    first_dates, second_dates = set(dates[:half]), set(dates[half:])
    split = {
        "first_half_dates": summarize(e[e["Date"].isin(first_dates)], COST),
        "second_half_dates": summarize(e[e["Date"].isin(second_dates)], COST),
    }
    date_mean = e.groupby("Date")["net_ret_40bp"].mean().sort_values(ascending=False)
    top3 = set(date_mean.head(3).index)
    robust = {
        "remove_best_3_dates": summarize(e[~e["Date"].isin(top3)], COST),
        "cost_100bp": summarize(e, 0.010),
    }
    return e, {"summary": summary, "monthly": monthly, "time_split": split, "robustness": robust}


def main():
    y26 = load_2026()
    hist, inv = load_history()
    panel = build_panel(hist, y26)

    recent_events, recent = period_eval(panel, RECENT_START, RECENT_END)
    # Governance: only promote to one year if the same-universe 3M result is clearly useful.
    recent_pass = (
        recent["summary"]["n"] >= 30
        and recent["summary"]["mean"] is not None and recent["summary"]["mean"] > 0
        and recent["summary"]["pf"] is not None and recent["summary"]["pf"] > 1
        and recent["time_split"]["first_half_dates"]["mean"] is not None and recent["time_split"]["first_half_dates"]["mean"] > 0
        and recent["time_split"]["second_half_dates"]["mean"] is not None and recent["time_split"]["second_half_dates"]["mean"] > 0
    )

    result = {
        "rule": {
            "universe": "TWSE listed electronics / recovered type13 historical + 2026 formal electronics history",
            "signal_time": "t close",
            "entry": "t+1 open",
            "exit": "t+5 close",
            "roundtrip_cost": COST,
            "conditions": [
                "breadth_ma20 < 0.50",
                "ret3 cross-sectional percentile <= 0.20",
                "gap cross-sectional percentile <= 0.20",
                "dist_ma10 cross-sectional percentile <= 0.20",
                "lower_wick <= same-date base-candidate median",
            ],
        },
        "historical_inventory": inv,
        "recent_3m": recent,
        "recent_3m_pass": bool(recent_pass),
        "one_year": None,
    }

    if recent_pass:
        year_events, year = period_eval(panel, YEAR_START, YEAR_END)
        result["one_year"] = year
        year_events.to_csv(OUT / "events_1y.csv", index=False)
    recent_events.to_csv(OUT / "events_3m.csv", index=False)
    pd.DataFrame(inv).to_csv(OUT / "historical_inventory.csv", index=False)
    with open(OUT / "RESULT.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=True)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=True))


if __name__ == "__main__":
    main()
