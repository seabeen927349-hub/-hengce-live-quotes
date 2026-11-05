#!/usr/bin/env python3
"""HENGCE pre-event resilience score v0.4: READ-ONLY research utility.

Scores use price and turnover ONLY from dates before the future crash.
No future price/volume, institutional flow, margin flow, brokerage access or
mother/universe promotion. Returns quantitative cross-sectional ranks, NOT
probability of beating the market, trade signals, or backtest authority.

Usage:
  python research/five_day_stress_resilience_20261105/score_resilience_v04.py \
    --repo-root . \
    --trend-anchor 20261007 \
    --dates 20261014 20261015 20261016 20261019 20261020 20261021 20261022 20261027 20261028 \
    --output research/five_day_stress_resilience_20261105/score_latest_research.json
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import re
from pathlib import Path


def read_day(root: Path, day: str) -> dict:
    folder = root / "eod" / day
    status_path = folder / "status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if status.get("price_status") != "COMPLETE":
        raise RuntimeError(f"{day}: price is not formally COMPLETE: {status.get('price_status')}")
    if status.get("price_date", f"{day[:4]}-{day[4:6]}-{day[6:]}") != f"{day[:4]}-{day[4:6]}-{day[6:]}":
        raise RuntimeError(f"{day}: price_date mismatch")
    paths = [folder / f"price_{i}.csv" for i in range(1, 10)]
    if not all(p.is_file() for p in paths):
        raise RuntimeError(f"{day}: nine source CSV segments are required")
    result = {}
    for path in paths:
        with path.open(encoding="utf-8-sig", newline="") as inp:
            for row in csv.DictReader(inp):
                ticker = row.get("Ticker", "")
                if not re.fullmatch(r"[1-9]\d{3}", ticker):
                    continue
                if ticker in result:
                    raise RuntimeError(f"{day}: duplicate stock ticker {ticker}")
                try:
                    close = float(row["Close"])
                    value = float(row["TurnoverTWD"])
                except (ValueError, TypeError, KeyError):
                    continue
                if math.isfinite(close) and close > 0 and math.isfinite(value) and value >= 0:
                    result[ticker] = dict(name=row.get("Name", ""), close=close, value=value)
    return result


def average(xs):
    return sum(xs) / len(xs)


def percentile_rank(rows, feature: str, ascending_good: bool):
    """Return [0,100] value ranks, with midpoint tie ranking."""
    seq = sorted(rows, key=lambda row: row[feature])
    n = len(seq)
    result = {}
    i = 0
    while i < n:
        j = i + 1
        while j < n and seq[j][feature] == seq[i][feature]:
            j += 1
        pct = 100 * (i + j - 1) / (2 * (n - 1)) if n > 1 else 50
        score = pct if ascending_good else 100 - pct
        for k in range(i, j):
            result[seq[k]["ticker"]] = score
        i = j
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--trend-anchor", required=True, help="EOD YYYYMMDD date, before all --dates")
    p.add_argument("--dates", nargs=9, required=True, help="nine completed trading dates before the event, ascending")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    dates = args.dates
    if sorted(set(dates)) != dates:
        raise ValueError("Feature dates must be strictly ascending")
    if args.trend_anchor >= dates[0]:
        raise ValueError("Trend anchor must predate pre-event sessions")
    if len(set(dates)) != 9 or any(not re.fullmatch(r"\d{8}", d) for d in [args.trend_anchor] + dates):
        raise ValueError("Bad or repeated date(s)")
    eod = {d: read_day(args.repo_root, d) for d in [args.trend_anchor] + dates}
    rows = []
    for ticker in eod[dates[-1]]:
        if ticker not in eod[args.trend_anchor] or any(ticker not in eod[d] for d in dates):
            continue
        quotes = [eod[d][ticker] for d in dates]
        values = [q["value"] for q in quotes]
        if average(values) < 20_000_000 or min(values) < 2_000_000:
            continue
        closes = [q["close"] for q in quotes]
        daily_pct = [100 * (closes[i] / closes[i - 1] - 1) for i in range(1, len(closes))]
        avg_daily = average(daily_pct)
        volatility = math.sqrt(average([(d - avg_daily)**2 for d in daily_pct]))
        trend = 100 * (closes[-1] / eod[args.trend_anchor][ticker]["close"] - 1)
        rows.append({
            "ticker": ticker, "name": quotes[-1]["name"],
            "priorVolPct": volatility,
            "priorWorstDayPct": min(daily_pct),
            "priorTrendPct": trend,
            "priorAverageDailyTurnoverM": average(values) / 1_000_000,
            "priorClose": closes[-1],
        })
    if len(rows) < 100:
        raise RuntimeError("Eligible universe too small to run research score")
    ranks_vol = percentile_rank(rows, "priorVolPct", ascending_good=False)
    ranks_worst = percentile_rank(rows, "priorWorstDayPct", ascending_good=True)
    ranks_trend = percentile_rank(rows, "priorTrendPct", ascending_good=True)
    for r in rows:
        ticker = r["ticker"]
        r["score"] = round(.50 * ranks_vol[ticker] +
                           .30 * ranks_worst[ticker] +
                           .20 * ranks_trend[ticker], 3)
        r["scoreComponents"] = {
            "stability_50": round(.50 * ranks_vol[ticker], 3),
            "crash_history_30": round(.30 * ranks_worst[ticker], 3),
            "trend_20": round(.20 * ranks_trend[ticker], 3),
        }
        r["tier"] = ("80-100" if r["score"] >= 80 else
                     "60-79" if r["score"] >= 60 else
                     "40-59" if r["score"] >= 40 else
                     "20-39" if r["score"] >= 20 else "0-19")
    rows.sort(key=lambda r: (-r["score"], r["ticker"]))
    report = {
        "system": "HENGCE", "model": "RESILIENCE_SCORE_V04",
        "status": "EXPLORATORY_RESEARCH_NO_TRADING_AUTHORITY",
        "information_asof": dates[-1],
        "trend_anchor": args.trend_anchor,
        "prior_dates": dates,
        "eligible_count": len(rows),
        "formula": "score = 50% × inverse volatility percentile + 30% × worst-day percentile + 20% × prior-trend percentile",
        "warning": "One historical market episode only. Relative score is not a probability, future return forecast or trading signal.",
        "stocks": rows,
    }
    dest = args.repo_root / args.output
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"model": report["model"], "n": len(rows),
                      "top5": [(r["ticker"], r["score"]) for r in rows[:5]],
                      "out": str(dest)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
