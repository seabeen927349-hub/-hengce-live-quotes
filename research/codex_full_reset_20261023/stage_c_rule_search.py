#!/usr/bin/env python3
"""HENGCE full reset Stage C/D: preregistered rule-family chronological search.

Consumes the Stage-B official TWSE mother plus frozen repo macro/membership evidence.
This is research-only and cannot create production, signal, capital, or broker authority.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import itertools
import json
import math
import statistics
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
RESET = ROOT / "research" / "codex_full_reset_20261023"
OUT = RESET / "results" / "stage_c"
MACRO = ROOT / "research" / "e2_profit_max" / "macro"
BASELINE_PATH = ROOT / "research" / "e2_profit_max" / "E2_PROFIT_MAX_CANDIDATE_B_FINAL_VALIDATION_20261019.json"
PLAN_PATH = RESET / "SEARCH_PLAN_V1.json"
NEIGHBOR_PATH = RESET / "SEARCH_PLAN_V1_NEIGHBOR_RULE.json"
QUALITY_PATH = RESET / "DATA_QUALITY_RULE_V1.json"
MANIFEST_PATH = RESET / "CORPUS_MANIFEST.json"

COSTS = (0.008, 0.012, 0.016)
SELECTION_COST = 0.012
DISCONTINUITY = 0.15
HORIZONS = (1, 3, 5, 10, 20)
TURNOVER_THRESHOLDS = (0.0, 20_000_000.0, 50_000_000.0)
TOP_NS = (1, 3)
REGIMES = (
    "ALL",
    "LOCAL_M1_NEG",
    "LOCAL_M5_LE_-0.02",
    "LOCAL_M1_NEG_AND_M5_LE_-0.02",
    "PRIOR_SOX1_LE_0",
    "PRIOR_SOX5_LE_-0.03",
    "LOCAL_SHOCK_AND_PRIOR_SOX_WEAK",
)
FAMILY_SCORES = {
    "RAW_REVERSAL": ("NEG_R1", "NEG_R3", "NEG_R5"),
    "RAW_MOMENTUM": ("R5", "R10", "R20"),
    "RESIDUAL_REVERSAL": ("NEG_RESID1", "NEG_RESID3", "NEG_RESID5"),
    "RESIDUAL_MOMENTUM": ("RESID5", "RESID10", "RESID20"),
    "VOLATILITY_NORMALIZED": ("NEG_RESID1_DIV_VOL20", "R20_DIV_VOL20"),
    "BETA_WEIGHTED_RESIDUAL_REVERSAL": (
        "BETA_TIMES_NEG_RESID1", "BETA_K10_RESID_REV", "BETA_K25_RESID_REV", "BETA_K50_RESID_REV"
    ),
    "SIMPLE_RANK_ENSEMBLE": ("RESID_REV1_PLUS_MOM20_RANK", "RESID_REV1_PLUS_LIQUIDITY_RANK"),
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def finite_float(value: Any) -> float | None:
    if value in (None, "", "--", "---"):
        return None
    try:
        x = float(str(value).replace(",", ""))
    except Exception:
        return None
    return x if math.isfinite(x) else None


def product_return(rets: Iterable[float]) -> float:
    nav = 1.0
    for r in rets:
        nav *= 1.0 + r
    return nav - 1.0


def max_drawdown(rets: Iterable[float]) -> float:
    nav = 1.0
    peak = 1.0
    mdd = 0.0
    for r in rets:
        nav *= 1.0 + r
        peak = max(peak, nav)
        if peak > 0:
            mdd = min(mdd, nav / peak - 1.0)
    return mdd


def percentile_ranks(values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(values.items(), key=lambda kv: (kv[1], kv[0]))
    n = len(ordered)
    if n <= 1:
        return {ticker: 0.5 for ticker, _ in ordered}
    out: dict[str, float] = {}
    i = 0
    while i < n:
        j = i + 1
        while j < n and ordered[j][1] == ordered[i][1]:
            j += 1
        avg_rank = ((i + 1) + j) / 2.0
        pct = (avg_rank - 1.0) / (n - 1.0)
        for k in range(i, j):
            out[ordered[k][0]] = pct
        i = j
    return out


@dataclass
class Row:
    date: str
    ticker: str
    name: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: float | None
    turnover: float | None
    bad_jump: bool = False
    r1: float | None = None
    r3: float | None = None
    r5: float | None = None
    r10: float | None = None
    r20: float | None = None
    turnover20: float | None = None
    vol20: float | None = None
    beta60: float | None = None
    resid1: float | None = None
    resid3: float | None = None
    resid5: float | None = None
    resid10: float | None = None
    resid20: float | None = None
    scores: dict[str, float] | None = None


@dataclass(frozen=True)
class Config:
    family: str
    score: str
    turnover_min: float
    top_n: int
    horizon: int
    regime: str

    @property
    def id(self) -> str:
        turn = int(self.turnover_min)
        return f"{self.family}|{self.score}|TO{turn}|N{self.top_n}|H{self.horizon}|{self.regime}"

    @property
    def parameter_count(self) -> int:
        return 5


def load_mother(path: Path) -> tuple[list[str], dict[str, dict[str, Row]]]:
    if not path.exists():
        raise RuntimeError(f"MOTHER_NOT_FOUND:{path}")
    opener = gzip.open if path.suffix == ".gz" else open
    by_date: dict[str, dict[str, Row]] = defaultdict(dict)
    with opener(path, "rt", encoding="utf-8-sig", newline="") as f:
        for rec in csv.DictReader(f):
            d = (rec.get("date") or "").strip()
            ticker = (rec.get("ticker") or "").strip()
            if not d or not ticker:
                continue
            row = Row(
                date=d,
                ticker=ticker,
                name=(rec.get("name") or "").strip(),
                open=finite_float(rec.get("open")),
                high=finite_float(rec.get("high")),
                low=finite_float(rec.get("low")),
                close=finite_float(rec.get("close")),
                volume=finite_float(rec.get("volume_shares")),
                turnover=finite_float(rec.get("turnover_ntd")),
                scores={},
            )
            if ticker in by_date[d]:
                raise RuntimeError(f"DUPLICATE_MOTHER_KEY:{d}:{ticker}")
            by_date[d][ticker] = row
    dates = sorted(by_date)
    if not dates:
        raise RuntimeError("EMPTY_MOTHER")
    return dates, by_date


def load_macro(path: Path) -> list[dict[str, Any]]:
    out = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for rec in csv.DictReader(f):
            d = (rec.get("date") or "").strip()
            if not d:
                continue
            out.append({"date": d, "ret1": finite_float(rec.get("ret1")), "ret5": finite_float(rec.get("ret5"))})
    return sorted(out, key=lambda x: x["date"])


def prior_macro(series: list[dict[str, Any]], signal_date: str) -> dict[str, Any] | None:
    lo, hi = 0, len(series)
    while lo < hi:
        mid = (lo + hi) // 2
        if series[mid]["date"] < signal_date:
            lo = mid + 1
        else:
            hi = mid
    return series[lo - 1] if lo else None


def prepare_features(dates: list[str], by_date: dict[str, dict[str, Row]]) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, Any]], dict[str, int]]:
    date_index = {d: i for i, d in enumerate(dates)}

    # Mark unverified close-to-close discontinuities first.
    for i, d in enumerate(dates):
        if i == 0:
            continue
        prev = dates[i - 1]
        for ticker, row in by_date[d].items():
            p = by_date[prev].get(ticker)
            if p and p.close and row.close and p.close > 0 and row.close > 0:
                raw = row.close / p.close - 1.0
                row.bad_jump = abs(raw) > DISCONTINUITY
                if not row.bad_jump:
                    row.r1 = raw

    market: dict[str, dict[str, float]] = defaultdict(dict)
    horizons = (1, 3, 5, 10, 20)
    for i, d in enumerate(dates):
        for ticker, row in by_date[d].items():
            for h in horizons:
                if i < h:
                    continue
                start_d = dates[i - h]
                start = by_date[start_d].get(ticker)
                if not start or not start.close or not row.close or start.close <= 0 or row.close <= 0:
                    continue
                ok = True
                for j in range(i - h + 1, i + 1):
                    rr = by_date[dates[j]].get(ticker)
                    if rr is None or rr.bad_jump:
                        ok = False
                        break
                if not ok:
                    continue
                value = row.close / start.close - 1.0
                setattr(row, f"r{h}", value)

            # turnover20 includes signal day, requires 20 consecutive PIT sessions.
            if i >= 19:
                vals = []
                for j in range(i - 19, i + 1):
                    rr = by_date[dates[j]].get(ticker)
                    if rr is None or rr.turnover is None or rr.turnover < 0:
                        vals = []
                        break
                    vals.append(rr.turnover)
                if len(vals) == 20:
                    row.turnover20 = statistics.mean(vals)

            # vol20 excludes signal-day daily return and uses 20 consecutive prior sessions.
            if i >= 21:
                vals = []
                for j in range(i - 20, i):
                    rr = by_date[dates[j]].get(ticker)
                    if rr is None or rr.r1 is None:
                        vals = []
                        break
                    vals.append(rr.r1)
                if len(vals) == 20:
                    row.vol20 = statistics.stdev(vals)

        for h in horizons:
            values = [getattr(row, f"r{h}") for row in by_date[d].values() if getattr(row, f"r{h}") is not None]
            if values:
                market[d][f"r{h}"] = statistics.median(values)

    beta_hist: dict[str, deque[tuple[float, float]]] = defaultdict(lambda: deque(maxlen=60))
    for d in dates:
        m1 = market[d].get("r1")
        for ticker, row in by_date[d].items():
            hist = beta_hist[ticker]
            if len(hist) >= 30:
                xs = [x for x, _ in hist]
                ys = [y for _, y in hist]
                xbar = statistics.mean(xs)
                ybar = statistics.mean(ys)
                den = sum((x - xbar) ** 2 for x in xs)
                if den > 0:
                    row.beta60 = sum((x - xbar) * (y - ybar) for x, y in hist) / den
            if row.beta60 is not None:
                for h in horizons:
                    rv = getattr(row, f"r{h}")
                    mv = market[d].get(f"r{h}")
                    if rv is not None and mv is not None:
                        setattr(row, f"resid{h}", rv - row.beta60 * mv)
            if m1 is not None and row.r1 is not None:
                hist.append((m1, row.r1))

    # Base scores.
    for d in dates:
        for ticker, row in by_date[d].items():
            s = row.scores if row.scores is not None else {}
            if row.r1 is not None: s["NEG_R1"] = -row.r1
            if row.r3 is not None: s["NEG_R3"] = -row.r3
            if row.r5 is not None:
                s["NEG_R5"] = -row.r5
                s["R5"] = row.r5
            if row.r10 is not None: s["R10"] = row.r10
            if row.r20 is not None: s["R20"] = row.r20
            for h in (1, 3, 5, 10, 20):
                rv = getattr(row, f"resid{h}")
                if rv is not None:
                    s[f"NEG_RESID{h}"] = -rv
                    s[f"RESID{h}"] = rv
            if row.resid1 is not None and row.vol20 is not None and row.vol20 > 0:
                s["NEG_RESID1_DIV_VOL20"] = -row.resid1 / row.vol20
            if row.r20 is not None and row.vol20 is not None and row.vol20 > 0:
                s["R20_DIV_VOL20"] = row.r20 / row.vol20
            if row.beta60 is not None and row.resid1 is not None:
                s["BETA_TIMES_NEG_RESID1"] = row.beta60 * (-row.resid1)
                for k in (10, 25, 50):
                    s[f"BETA_K{k}_RESID_REV"] = row.beta60 * (1.0 + k * max(-row.resid1, 0.0))
            row.scores = s

        # Rank ensembles use only same-day observable values.
        resid_vals = {t: r.scores["NEG_RESID1"] for t, r in by_date[d].items() if r.scores and "NEG_RESID1" in r.scores}
        mom_vals = {t: r.scores["R20"] for t, r in by_date[d].items() if r.scores and "R20" in r.scores}
        liq_vals = {t: r.turnover20 for t, r in by_date[d].items() if r.turnover20 is not None}
        rr = percentile_ranks(resid_vals)
        mr = percentile_ranks(mom_vals)
        lr = percentile_ranks(liq_vals)
        for ticker, row in by_date[d].items():
            if ticker in rr and ticker in mr:
                row.scores["RESID_REV1_PLUS_MOM20_RANK"] = (rr[ticker] + mr[ticker]) / 2.0
            if ticker in rr and ticker in lr:
                row.scores["RESID_REV1_PLUS_LIQUIDITY_RANK"] = (rr[ticker] + lr[ticker]) / 2.0

    sox = load_macro(MACRO / "sox_daily_202212_202610.csv")
    dxy = load_macro(MACRO / "dxy_exact_DX-Y.NYB_202212_202610.csv")
    context: dict[str, dict[str, Any]] = {}
    for d in dates:
        ps = prior_macro(sox, d)
        px = prior_macro(dxy, d)
        context[d] = {
            "market_r1": market[d].get("r1"),
            "market_r5": market[d].get("r5"),
            "sox_date": ps.get("date") if ps else None,
            "sox1": ps.get("ret1") if ps else None,
            "sox5": ps.get("ret5") if ps else None,
            "dxy_date": px.get("date") if px else None,
            "dxy1": px.get("ret1") if px else None,
            "dxy5": px.get("ret5") if px else None,
        }
    return market, context, date_index


def regime_ok(name: str, ctx: dict[str, Any]) -> bool:
    m1, m5, s1, s5 = ctx.get("market_r1"), ctx.get("market_r5"), ctx.get("sox1"), ctx.get("sox5")
    if name == "ALL": return True
    if name == "LOCAL_M1_NEG": return m1 is not None and m1 < 0
    if name == "LOCAL_M5_LE_-0.02": return m5 is not None and m5 <= -0.02
    if name == "LOCAL_M1_NEG_AND_M5_LE_-0.02": return m1 is not None and m1 < 0 and m5 is not None and m5 <= -0.02
    if name == "PRIOR_SOX1_LE_0": return s1 is not None and s1 <= 0
    if name == "PRIOR_SOX5_LE_-0.03": return s5 is not None and s5 <= -0.03
    if name == "LOCAL_SHOCK_AND_PRIOR_SOX_WEAK":
        return m1 is not None and m1 < 0 and m5 is not None and m5 <= -0.02 and s1 is not None and s1 <= 0 and s5 is not None and s5 <= -0.03
    raise KeyError(name)


def build_rank_cache(dates: list[str], by_date: dict[str, dict[str, Row]]) -> dict[tuple[str, float, str], list[str]]:
    cache: dict[tuple[str, float, str], list[str]] = {}
    all_scores = sorted({score for scores in FAMILY_SCORES.values() for score in scores})
    for d in dates:
        rows = by_date[d]
        for score in all_scores:
            for threshold in TURNOVER_THRESHOLDS:
                eligible = []
                for ticker, row in rows.items():
                    if row.scores is None or score not in row.scores:
                        continue
                    if row.turnover20 is None or row.turnover20 < threshold:
                        continue
                    value = row.scores[score]
                    if not math.isfinite(value):
                        continue
                    eligible.append((value, ticker))
                eligible.sort(key=lambda x: (-x[0], x[1]))
                cache[(score, threshold, d)] = [ticker for _, ticker in eligible]
    return cache


def outcome_for_ticker(ticker: str, signal_i: int, horizon: int, dates: list[str], by_date: dict[str, dict[str, Row]]) -> tuple[float, str, str] | None:
    entry_i = signal_i + 1
    exit_i = signal_i + horizon
    if entry_i >= len(dates) or exit_i >= len(dates) or exit_i < entry_i:
        return None
    entry_d, exit_d = dates[entry_i], dates[exit_i]
    entry = by_date[entry_d].get(ticker)
    exit_row = by_date[exit_d].get(ticker)
    if entry is None or exit_row is None or entry.open is None or exit_row.close is None or entry.open <= 0 or exit_row.close <= 0:
        return None
    for j in range(entry_i, exit_i + 1):
        rr = by_date[dates[j]].get(ticker)
        if rr is None or rr.bad_jump or rr.close is None or rr.close <= 0:
            return None
    return exit_row.close / entry.open - 1.0, entry_d, exit_d


def summarize_events(events: list[dict[str, Any]], cost: float) -> dict[str, Any]:
    nets = [event["gross_return"] - cost for event in events]
    wins = sum(x > 0 for x in nets)
    return {
        "complete_trades": len(nets),
        "wins": wins,
        "win_rate": wins / len(nets) if nets else None,
        "compounded_return": product_return(nets) if nets else 0.0,
        "mean_net_return": statistics.mean(nets) if nets else None,
        "median_net_return": statistics.median(nets) if nets else None,
        "max_drawdown": max_drawdown(nets) if nets else 0.0,
        "worst_trade": min(nets) if nets else None,
        "best_trade": max(nets) if nets else None,
        "unavailable_signals": None,
    }


def simulate(config: Config, start: str, end: str, cost: float, dates: list[str], date_index: dict[str, int], by_date: dict[str, dict[str, Row]], context: dict[str, dict[str, Any]], rank_cache: dict[tuple[str, float, str], list[str]], residual_cap: float | None = None, quality_guard: bool = True) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    blocked_exit_i: int | None = None
    unavailable = 0
    for i, d in enumerate(dates):
        if d < start or d > end:
            continue
        if blocked_exit_i is not None and i <= blocked_exit_i:
            continue
        if not regime_ok(config.regime, context[d]):
            continue
        ranked = rank_cache.get((config.score, config.turnover_min, d), [])
        if residual_cap is not None:
            ranked = [t for t in ranked if by_date[d][t].resid1 is not None and by_date[d][t].resid1 <= residual_cap]
        chosen = ranked[: config.top_n]
        if len(chosen) < config.top_n:
            continue
        exit_i = i + config.horizon
        if exit_i >= len(dates) or dates[exit_i] > end:
            continue
        gross_parts = []
        entry_d = None
        exit_d = None
        valid = True
        for ticker in chosen:
            if quality_guard:
                outcome = outcome_for_ticker(ticker, i, config.horizon, dates, by_date)
            else:
                entry_i = i + 1
                if entry_i >= len(dates) or exit_i >= len(dates):
                    outcome = None
                else:
                    er = by_date[dates[entry_i]].get(ticker)
                    xr = by_date[dates[exit_i]].get(ticker)
                    outcome = None if er is None or xr is None or er.open is None or xr.close is None or er.open <= 0 or xr.close <= 0 else (xr.close / er.open - 1.0, dates[entry_i], dates[exit_i])
            if outcome is None:
                valid = False
                break
            gross, ed, xd = outcome
            gross_parts.append(gross)
            entry_d, exit_d = ed, xd
        if not valid:
            unavailable += 1
            continue
        gross_basket = statistics.mean(gross_parts)
        events.append({
            "signal_date": d,
            "entry_date": entry_d,
            "exit_date": exit_d,
            "tickers": chosen,
            "gross_return": gross_basket,
            "net_return": gross_basket - cost,
        })
        blocked_exit_i = exit_i
    metrics = summarize_events(events, cost)
    metrics["unavailable_signals"] = unavailable
    return metrics, events


def configs() -> list[Config]:
    out = []
    for family, scores in FAMILY_SCORES.items():
        for score, threshold, top_n, horizon, regime in itertools.product(scores, TURNOVER_THRESHOLDS, TOP_NS, HORIZONS, REGIMES):
            out.append(Config(family, score, threshold, top_n, horizon, regime))
    return out


def selection_key(metrics: dict[str, Any], config: Config) -> tuple[Any, ...]:
    wr = metrics["win_rate"] if metrics["win_rate"] is not None else -1.0
    return (
        metrics["compounded_return"],
        wr,
        metrics["max_drawdown"],
        metrics["complete_trades"],
        -config.parameter_count,
        tuple(-ord(c) for c in config.id),
    )


def adjacent_values(value: Any, grid: tuple[Any, ...]) -> list[Any]:
    idx = grid.index(value)
    out = []
    if idx > 0: out.append(grid[idx - 1])
    if idx + 1 < len(grid): out.append(grid[idx + 1])
    return out


def neighbors(config: Config) -> list[Config]:
    out = []
    for v in adjacent_values(config.turnover_min, TURNOVER_THRESHOLDS):
        out.append(Config(config.family, config.score, v, config.top_n, config.horizon, config.regime))
    for v in adjacent_values(config.top_n, TOP_NS):
        out.append(Config(config.family, config.score, config.turnover_min, v, config.horizon, config.regime))
    for v in adjacent_values(config.horizon, HORIZONS):
        out.append(Config(config.family, config.score, config.turnover_min, config.top_n, v, config.regime))
    return out


def neighbor_check(config: Config, start: str, end: str, dates: list[str], date_index: dict[str, int], by_date: dict[str, dict[str, Row]], context: dict[str, dict[str, Any]], rank_cache: dict[tuple[str, float, str], list[str]]) -> dict[str, Any]:
    results = []
    for n in neighbors(config):
        metrics, _ = simulate(n, start, end, SELECTION_COST, dates, date_index, by_date, context, rank_cache)
        results.append({"config_id": n.id, "return": metrics["compounded_return"], "trades": metrics["complete_trades"]})
    valid = [r for r in results if r["trades"] >= 1]
    positives = [r for r in valid if r["return"] > 0]
    median_ret = statistics.median([r["return"] for r in valid]) if valid else None
    passed = len(valid) >= 2 and len(positives) / len(valid) >= 0.6 and median_ret is not None and median_ret > 0
    return {"pass": passed, "valid_neighbors": len(valid), "positive_neighbors": len(positives), "median_return": median_ret, "neighbors": results}


def concentration(events: list[dict[str, Any]], cost: float) -> dict[str, Any]:
    if not events:
        return {"max_ticker_event_share": None, "max_positive_trade_pnl_share": None}
    counts = Counter()
    for event in events:
        for ticker in set(event["tickers"]):
            counts[ticker] += 1
    max_ticker_share = max(counts.values()) / len(events) if counts else None
    positives = [event["gross_return"] - cost for event in events if event["gross_return"] - cost > 0]
    max_positive_share = max(positives) / sum(positives) if positives and sum(positives) > 0 else None
    return {"max_ticker_event_share": max_ticker_share, "max_positive_trade_pnl_share": max_positive_share, "ticker_event_counts": counts.most_common(10)}


def remove_best_return(events: list[dict[str, Any]], cost: float) -> float:
    nets = [event["gross_return"] - cost for event in events]
    if not nets:
        return 0.0
    best_i = max(range(len(nets)), key=lambda i: nets[i])
    return product_return([r for i, r in enumerate(nets) if i != best_i])


def combine_event_metrics(event_groups: list[list[dict[str, Any]]], cost: float) -> dict[str, Any]:
    events = sorted([event for group in event_groups for event in group], key=lambda x: (x["signal_date"], x["entry_date"]))
    metrics = summarize_events(events, cost)
    metrics.update(concentration(events, cost))
    metrics["remove_best_trade_return"] = remove_best_return(events, cost)
    return metrics


def dominates(a: dict[str, Any], b: dict[str, Any]) -> bool:
    av = (a["return_012"], a["win_rate_012"], a["worst_fold_return_016"], a["max_drawdown_012"])
    bv = (b["return_012"], b["win_rate_012"], b["worst_fold_return_016"], b["max_drawdown_012"])
    return all(x >= y for x, y in zip(av, bv)) and any(x > y for x, y in zip(av, bv))


def candidate_b_reproduction(dates: list[str], date_index: dict[str, int], by_date: dict[str, dict[str, Row]], context: dict[str, dict[str, Any]], rank_cache: dict[tuple[str, float, str], list[str]]) -> dict[str, Any]:
    old = json_load(BASELINE_PATH)
    config = Config("CANDIDATE_B_REFERENCE", "BETA_K25_RESID_REV", 20_000_000.0, 1, 20, "LOCAL_SHOCK_AND_PRIOR_SOX_WEAK")
    strict_metrics, strict_events = simulate(config, "2023-01-01", "2025-12-31", 0.008, dates, date_index, by_date, context, rank_cache, residual_cap=0.04, quality_guard=True)
    legacy_metrics, legacy_events = simulate(config, "2023-01-01", "2025-12-31", 0.008, dates, date_index, by_date, context, rank_cache, residual_cap=0.04, quality_guard=False)
    expected = old["pit_2023_2025"]
    exact_aggregate_match = bool(
        legacy_metrics["complete_trades"] == expected["entries"]
        and legacy_metrics["wins"] == expected["wins"]
        and abs(legacy_metrics["compounded_return"] - expected["return"]) <= 1e-10
        and abs(legacy_metrics["max_drawdown"] - expected["maxdd"]) <= 1e-10
    )
    return {
        "reference_artifact": str(BASELINE_PATH.relative_to(ROOT)),
        "reference_sha256": sha256_file(BASELINE_PATH),
        "expected_aggregate": expected,
        "new_official_mother_legacy_semantics": legacy_metrics,
        "new_official_mother_strict_reset_quality_guard": strict_metrics,
        "legacy_semantics_event_sample": legacy_events[:20],
        "strict_quality_event_sample": strict_events[:20],
        "exact_aggregate_match": exact_aggregate_match,
        "status": "AGGREGATE_REPRODUCED_FROM_NEW_MOTHER" if exact_aggregate_match else "BASELINE_REPRODUCTION_FAILED_OR_DIFFERS",
        "caveat": "Preserved historical event payload is corrupt, so old event identity cannot be proven even if aggregate metrics match."
    }


def historical_ledger_records(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for i, ref in enumerate(manifest.get("historical_fixed_refs", []), start=1):
        records.append({
            "experiment_id": f"HIST-{i:03d}",
            "record_type": "HISTORICAL_REFERENCE",
            "source_ref": ref,
            "result": ref.get("outcome") or ref.get("class") or "REFERENCE",
            "capital_authority_twd": 0,
            "broker_order_execution": False,
        })
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mother", required=True)
    parser.add_argument("--mother-receipt")
    args = parser.parse_args()
    mother = Path(args.mother)
    receipt_path = Path(args.mother_receipt) if args.mother_receipt else None

    OUT.mkdir(parents=True, exist_ok=True)
    for required in (PLAN_PATH, NEIGHBOR_PATH, QUALITY_PATH, MANIFEST_PATH, BASELINE_PATH):
        if not required.exists():
            raise RuntimeError(f"REQUIRED_FILE_MISSING:{required}")
    plan = json_load(PLAN_PATH)
    if plan.get("status") != "FROZEN_BEFORE_SEARCH_RESULTS" or plan.get("authority", {}).get("capital_authority_twd") != 0:
        raise RuntimeError("SEARCH_PLAN_NOT_FROZEN_OR_AUTHORITY_INVALID")
    if abs(json_load(QUALITY_PATH)["rule"]["unverified_discontinuity_if_abs_close_to_close_return_gt"] - DISCONTINUITY) > 1e-12:
        raise RuntimeError("QUALITY_RULE_DRIFT")
    if receipt_path and receipt_path.exists():
        receipt = json_load(receipt_path)
        if receipt.get("status") != "PASS_EXACT_MEMBERSHIP_SET" or receipt.get("failed_dates") != 0:
            raise RuntimeError("MOTHER_RECEIPT_NOT_PASS")
        if receipt.get("mother_sha256") != sha256_file(mother):
            raise RuntimeError("MOTHER_SHA_MISMATCH")

    dates, by_date = load_mother(mother)
    market, context, date_index = prepare_features(dates, by_date)
    rank_cache = build_rank_cache(dates, by_date)
    all_configs = configs()
    manifest = json_load(MANIFEST_PATH)

    ledger_path = OUT / "EXPERIMENT_LEDGER.jsonl"
    ledger = historical_ledger_records(manifest)
    family_results: dict[str, Any] = {}
    trial_seq = 0
    folds = [
        ("F1", "2023-01-01", "2023-12-31", "2024-01-01", "2024-12-31"),
        ("F2", "2023-01-01", "2024-12-31", "2025-01-01", "2025-12-31"),
    ]

    for family in FAMILY_SCORES:
        family_results[family] = {"folds": {}}
        family_configs = [c for c in all_configs if c.family == family]
        for fold_name, sel_start, sel_end, val_start, val_end in folds:
            best: tuple[tuple[Any, ...], Config, dict[str, Any]] | None = None
            for config in family_configs:
                metrics, _ = simulate(config, sel_start, sel_end, SELECTION_COST, dates, date_index, by_date, context, rank_cache)
                trial_seq += 1
                eligible = metrics["complete_trades"] >= 6
                ledger.append({
                    "experiment_id": f"RESET-{trial_seq:06d}",
                    "record_type": "RESET_SELECTION_TRIAL",
                    "fold": fold_name,
                    "family": family,
                    "config_id": config.id,
                    "selection_period": [sel_start, sel_end],
                    "cost": SELECTION_COST,
                    "metrics": metrics,
                    "eligible_for_family_selection": eligible,
                    "result": "EVALUATED",
                    "capital_authority_twd": 0,
                    "broker_order_execution": False,
                })
                if eligible:
                    key = selection_key(metrics, config)
                    if best is None or key > best[0]:
                        best = (key, config, metrics)
            if best is None:
                family_results[family]["folds"][fold_name] = {"status": "NO_ELIGIBLE_SELECTION_CONFIG"}
                continue
            selected = best[1]
            validation = {}
            event_by_cost = {}
            for cost in COSTS:
                vm, ve = simulate(selected, val_start, val_end, cost, dates, date_index, by_date, context, rank_cache)
                validation[f"cost_{cost:.3f}"] = vm
                event_by_cost[f"cost_{cost:.3f}"] = ve
            ncheck = neighbor_check(selected, val_start, val_end, dates, date_index, by_date, context, rank_cache)
            family_results[family]["folds"][fold_name] = {
                "status": "SELECTED_AND_VALIDATED",
                "selected_config": selected.__dict__,
                "selected_config_id": selected.id,
                "selection_metrics_cost_0.012": best[2],
                "validation": validation,
                "neighbor_check_cost_0.012": ncheck,
                "events": event_by_cost,
            }

    summary_rows = []
    for family, fr in family_results.items():
        f1 = fr["folds"].get("F1", {})
        f2 = fr["folds"].get("F2", {})
        if f1.get("status") != "SELECTED_AND_VALIDATED" or f2.get("status") != "SELECTED_AND_VALIDATED":
            summary_rows.append({"family": family, "eligible": False, "reason": "MISSING_FOLD_SELECTION"})
            continue
        combined_by_cost = {}
        for cost in COSTS:
            key = f"cost_{cost:.3f}"
            combined_by_cost[key] = combine_event_metrics([f1["events"][key], f2["events"][key]], cost)
        c012 = combined_by_cost["cost_0.012"]
        f1_016 = f1["validation"]["cost_0.016"]["compounded_return"]
        f2_016 = f2["validation"]["cost_0.016"]["compounded_return"]
        eligibility = {
            "minimum_total_validation_trades": c012["complete_trades"] >= 8,
            "minimum_each_fold": f1["validation"]["cost_0.012"]["complete_trades"] >= 3 and f2["validation"]["cost_0.012"]["complete_trades"] >= 3,
            "positive_each_fold_at_0.016": f1_016 > 0 and f2_016 > 0,
            "positive_total_all_costs": all(combined_by_cost[f"cost_{cost:.3f}"]["compounded_return"] > 0 for cost in COSTS),
            "remove_best_trade_positive_0.012": c012["remove_best_trade_return"] > 0,
            "ticker_concentration": c012["max_ticker_event_share"] is not None and c012["max_ticker_event_share"] <= 0.5,
            "positive_pnl_concentration": c012["max_positive_trade_pnl_share"] is not None and c012["max_positive_trade_pnl_share"] <= 0.6,
            "neighbor_f1": f1["neighbor_check_cost_0.012"]["pass"],
            "neighbor_f2": f2["neighbor_check_cost_0.012"]["pass"],
        }
        eligible = all(eligibility.values())
        row = {
            "family": family,
            "eligible": eligible,
            "eligibility": eligibility,
            "f1_selected_config_id": f1["selected_config_id"],
            "f2_selected_config_id": f2["selected_config_id"],
            "future_frozen_config": f2["selected_config"],
            "return_008": combined_by_cost["cost_0.008"]["compounded_return"],
            "return_012": c012["compounded_return"],
            "return_016": combined_by_cost["cost_0.016"]["compounded_return"],
            "win_rate_012": c012["win_rate"] if c012["win_rate"] is not None else -1.0,
            "trades_012": c012["complete_trades"],
            "max_drawdown_012": c012["max_drawdown"],
            "worst_fold_return_016": min(f1_016, f2_016),
            "remove_best_trade_return_012": c012["remove_best_trade_return"],
            "max_ticker_event_share": c012["max_ticker_event_share"],
            "max_positive_trade_pnl_share": c012["max_positive_trade_pnl_share"],
        }
        row["combined"] = combined_by_cost
        summary_rows.append(row)
        fr["combined"] = combined_by_cost
        fr["eligibility"] = eligibility
        fr["eligible"] = eligible

    numeric_rows = [r for r in summary_rows if "return_012" in r]
    pareto = [r for r in numeric_rows if not any(dominates(other, r) for other in numeric_rows if other is not r)]
    eligible_rows = [r for r in numeric_rows if r.get("eligible")]
    winner = None
    if eligible_rows:
        winner = sorted(
            eligible_rows,
            key=lambda r: (
                -r["worst_fold_return_016"],
                -r["return_012"],
                -r["win_rate_012"],
                -r["max_drawdown_012"],
                r["family"],
            ),
        )[0]

    baseline = candidate_b_reproduction(dates, date_index, by_date, context, rank_cache)

    with ledger_path.open("w", encoding="utf-8") as f:
        for record in ledger:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True, default=str) + "\n")

    trial_summary = {
        "schema_version": 1,
        "stage": "C_D_CHRONOLOGICAL_RULE_SEARCH",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "search_plan_sha256": sha256_file(PLAN_PATH),
        "neighbor_rule_sha256": sha256_file(NEIGHBOR_PATH),
        "quality_rule_sha256": sha256_file(QUALITY_PATH),
        "mother_sha256": sha256_file(mother),
        "config_count": len(all_configs),
        "selection_trial_count": trial_seq,
        "ledger_record_count": len(ledger),
        "families": family_results,
        "summary": summary_rows,
        "authority": {"research_only": True, "capital_authority_twd": 0, "broker_order_execution": False, "production_promotion": False},
    }
    (OUT / "TRIAL_SUMMARY.json").write_text(json.dumps(trial_summary, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    (OUT / "BASELINE_REPRODUCTION.json").write_text(json.dumps(baseline, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    (OUT / "PARETO_FRONTIER.json").write_text(json.dumps({"schema_version": 1, "pareto": pareto}, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    winner_doc = {
        "schema_version": 1,
        "status": "HISTORICAL_RESEARCH_WINNER_NOT_PROSPECTIVE_VALIDATED" if winner else "NO_ROBUST_WINNER",
        "winner": winner,
        "pareto_families": [r["family"] for r in pareto],
        "historical_exposure_warning": "2023-2025 was previously exposed and is not pristine OOS. Future prospective shadow validation is mandatory before any production discussion.",
        "baseline_candidate_b": {"status": baseline["status"], "exact_aggregate_match": baseline["exact_aggregate_match"]},
        "authority": {"research_only": True, "capital_authority_twd": 0, "broker_order_execution": False, "production_promotion": False, "merge_authorized": False},
    }
    (OUT / "WINNER_OR_NO_WINNER.json").write_text(json.dumps(winner_doc, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    receipt = {
        "stage": "C_D_CHRONOLOGICAL_RULE_SEARCH",
        "status": "COMPLETE",
        "winner_status": winner_doc["status"],
        "winner_family": winner["family"] if winner else None,
        "config_count": len(all_configs),
        "selection_trial_count": trial_seq,
        "ledger_sha256": sha256_file(ledger_path),
        "trial_summary_sha256": sha256_file(OUT / "TRIAL_SUMMARY.json"),
        "baseline_sha256": sha256_file(OUT / "BASELINE_REPRODUCTION.json"),
        "pareto_sha256": sha256_file(OUT / "PARETO_FRONTIER.json"),
        "winner_sha256": sha256_file(OUT / "WINNER_OR_NO_WINNER.json"),
        "authority": winner_doc["authority"],
    }
    (OUT / "SEARCH_RUN_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
