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
import os
import subprocess
from reset_ledger import TrialLedger, AUTHORITY
from stage_b_build_twse_year import load_expected, verify_pinned_file, CORPUS_BASE
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
SCOPE_PATH = RESET / "UNIVERSE_SCOPE_LOCK.json"

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
        if r <= -1: return -1.0
        nav *= 1.0 + r
    return nav - 1.0


def max_drawdown(rets: Iterable[float]) -> float:
    nav = 1.0
    peak = 1.0
    mdd = 0.0
    for r in rets:
        if r <= -1: return -1.0
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
                raise ValueError('MALFORMED_MOTHER_KEY')
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


def prepare_features(dates: list[str], by_date: dict[str, dict[str, Row]], discontinuity=DISCONTINUITY) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, Any]], dict[str, int]]:
    date_index = {d: i for i, d in enumerate(dates)}

    for i, d in enumerate(dates):
        if i == 0:
            continue
        prev = dates[i - 1]
        for ticker, row in by_date[d].items():
            p = by_date[prev].get(ticker)
            if p and p.close and row.close and p.close > 0 and row.close > 0:
                raw = row.close / p.close - 1.0
                row.bad_jump = abs(raw) > discontinuity
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
        context[d] = {
            "market": market[d],
            "sox": prior_macro(sox, d),
            "dxy": prior_macro(dxy, d),
        }
    return market, context, date_index


def regime_pass(regime: str, d: str, context: dict[str, dict[str, Any]]) -> bool:
    c = context[d]
    m = c["market"]
    sox = c["sox"]
    if regime == "ALL": return True
    if regime == "LOCAL_M1_NEG": return m.get("r1") is not None and m["r1"] < 0
    if regime == "LOCAL_M5_LE_-0.02": return m.get("r5") is not None and m["r5"] <= -0.02
    if regime == "LOCAL_M1_NEG_AND_M5_LE_-0.02": return m.get("r1") is not None and m["r1"] < 0 and m.get("r5") is not None and m["r5"] <= -0.02
    if regime == "PRIOR_SOX1_LE_0": return sox is not None and sox.get("ret1") is not None and sox["ret1"] <= 0
    if regime == "PRIOR_SOX5_LE_-0.03": return sox is not None and sox.get("ret5") is not None and sox["ret5"] <= -0.03
    if regime == "LOCAL_SHOCK_AND_PRIOR_SOX_WEAK":
        return m.get("r1") is not None and m["r1"] < 0 and m.get("r5") is not None and m["r5"] <= -0.02 and sox is not None and sox.get("ret1") is not None and sox.get("ret5") is not None and sox["ret1"] <= 0 and sox["ret5"] <= -0.03
    raise RuntimeError(f"UNKNOWN_REGIME:{regime}")


def build_rank_cache(dates: list[str], by_date: dict[str, dict[str, Row]]) -> dict[tuple[str, float, str], list[str]]:
    cache = {}
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
    exit_i = entry_i + horizon
    if exit_i >= len(dates): return None
    entry_d, exit_d = dates[entry_i], dates[exit_i]
    entry = by_date[entry_d].get(ticker)
    exit_row = by_date[exit_d].get(ticker)
    if not entry or not exit_row or entry.open is None or exit_row.close is None or entry.open <= 0 or exit_row.close <= 0:
        return None
    for j in range(entry_i, exit_i + 1):
        rr = by_date[dates[j]].get(ticker)
        if rr is None or rr.bad_jump or rr.close is None or rr.close <= 0:
            return None
    return exit_row.close / entry.open - 1.0, entry_d, exit_d


def configs() -> list[Config]:
    out = []
    for family, scores in FAMILY_SCORES.items():
        for score, turnover, top_n, horizon, regime in itertools.product(scores, TURNOVER_THRESHOLDS, TOP_NS, HORIZONS, REGIMES):
            out.append(Config(family, score, turnover, top_n, horizon, regime))
    return out


def simulate(config: Config, start: str, end: str, cost: float, dates: list[str], date_index: dict[str, int], by_date: dict[str, dict[str, Row]], context: dict[str, dict[str, Any]], rank_cache: dict[tuple[str, float, str], list[str]], residual_cap: float | None = None, quality_guard: bool = True) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    events = []
    censored = 0
    next_free_i = -1
    for i, d in enumerate(dates):
        if d < start or d > end: continue
        if i < next_free_i: continue
        if not regime_pass(config.regime, d, context): continue
        ranked = rank_cache.get((config.score, config.turnover_min, d), [])
        selected = []
        for ticker in ranked:
            row = by_date[d][ticker]
            if residual_cap is not None and (row.resid1 is None or row.resid1 > residual_cap):
                continue
            if quality_guard and row.bad_jump:
                continue
            selected.append(ticker)
            if len(selected) == config.top_n: break
        if len(selected) != config.top_n: continue
        exit_i = i + 1 + config.horizon
        if exit_i >= len(dates) or dates[exit_i] > end:
            continue  # purge entire incomplete outcome, never force-close it
        picks = [(ticker, outcome_for_ticker(ticker,i,config.horizon,dates,by_date)) for ticker in selected]
        if any(outcome is None for _,outcome in picks):
            censored += 1
            next_free_i = exit_i + 1
            continue  # retain a censored-basket count; never replace with rank+1
        gross = statistics.mean([p[1][0] for p in picks])
        entry_d = picks[0][1][1]
        exit_d = picks[0][1][2]
        daily_path = []
        for j in range(i+1, exit_i+1):
            daily_path.append([dates[j], statistics.mean(by_date[dates[j]][t].close / by_date[entry_d][t].open for t,_ in picks)])
        events.append({"signal_date": d, "entry_date": entry_d, "exit_date": exit_d, "tickers": [p[0] for p in picks], "gross_return": gross, "daily_gross_nav":daily_path})
        next_free_i = date_index[exit_d] + 1
    metrics = summarize_events(events, cost)
    metrics['censored_baskets'] = censored
    duration=(date.fromisoformat(end)-date.fromisoformat(start)).days+1
    metrics['evaluation_period']=[start,end]
    metrics['cagr']=((1+metrics['compounded_return'])**(365.25/duration)-1) if duration>=365 and metrics['compounded_return']>-1 else 'INSUFFICIENT_DURATION_OR_INSOLVENT'
    return metrics, events


def summarize_events(events: list[dict[str, Any]], cost: float) -> dict[str, Any]:
    nets = [event["gross_return"] - cost for event in events]
    wins = sum(r > 0 for r in nets)
    capital=1.0;peak=1.0;daily_mdd=0.0
    for event in events:
        path=event.get('daily_gross_nav',[[event['exit_date'],1+event['gross_return']]])
        for j,(_,value) in enumerate(path):
            nav=max(0,capital*(value-(cost if j==len(path)-1 else 0)))
            peak=max(peak,nav);daily_mdd=min(daily_mdd,nav/peak-1)
        capital=max(0,capital*(1+event['gross_return']-cost))
    return {
        "complete_trades": len(nets),
        "insolvent":any(r<=-1 for r in nets),
        "tail_cvar_5pct":statistics.mean(sorted(nets)[:max(1,math.ceil(len(nets)*.05))]) if len(nets)>=20 else 'INSUFFICIENT_SAMPLE',
        "mean_holding_sessions":statistics.mean(len(e.get('daily_gross_nav',[])) for e in events) if events else None,
        "wins": wins,
        "losses_or_zero": len(nets) - wins,
        "win_rate": wins / len(nets) if nets else None,
        "mean_net_return": statistics.mean(nets) if nets else None,
        "median_net_return": statistics.median(nets) if nets else None,
        "compounded_return": product_return(nets),
        "max_drawdown": daily_mdd,
        "trade_endpoint_max_drawdown": max_drawdown(nets),
        "worst_trade": min(nets) if nets else None,
        "best_trade": max(nets) if nets else None,
    }


def selection_key(metrics: dict[str, Any], config: Config) -> tuple[Any, ...]:
    return (
        metrics["compounded_return"],
        metrics["win_rate"] if metrics["win_rate"] is not None else -1.0,
        metrics["max_drawdown"],
        metrics["complete_trades"],
        -config.parameter_count,
        config.id,
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
        and abs(legacy_metrics["trade_endpoint_max_drawdown"] - expected["maxdd"]) <= 1e-10
    )
    return {
        "reference_artifact": str(BASELINE_PATH.relative_to(ROOT)),
        "reference_sha256": sha256_file(BASELINE_PATH),
        "expected_aggregate": expected,
        "new_mother_without_signal_jump_guard_reference_only": legacy_metrics,
        "new_official_mother_strict_reset_quality_guard": strict_metrics,
        "reference_event_sample": legacy_events[:20],
        "strict_quality_event_sample": strict_events[:20],
        "exact_aggregate_match": exact_aggregate_match,
        "status": "AGGREGATE_REPRODUCED_FROM_NEW_MOTHER" if exact_aggregate_match else "BASELINE_REPRODUCTION_FAILED_OR_DIFFERS",
        "caveat": "This new-mother reset simulation is not a proof of legacy event semantics. Preserved historical event payload is corrupt, so old event identity cannot be proven even if aggregate metrics match. Only like-for-like trade-end drawdown is used for the aggregate comparison."
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
    records.append({'experiment_id':'HIST-CANDIDATE-B','record_type':'HISTORICAL_REFERENCE',
                    'source':str(BASELINE_PATH.relative_to(ROOT)),'source_sha256':sha256_file(BASELINE_PATH),
                    'result':'AGGREGATE_SUCCESS_EVENT_IDENTITY_UNPROVEN'})
    failures_path=RESET/'results/DATA_QUALITY_FAILURES.json'
    if failures_path.exists():
        for i,failure in enumerate(json_load(failures_path).get('historical_evidence_failures',[])):
            records.append({'experiment_id':'HIST-DATA-FAIL-'+str(i),'record_type':'HISTORICAL_REFERENCE','result':'DATA_QUALITY_REJECT','evidence':failure})
    records.append({'experiment_id':'HIST-STAGE-B-39915764325','record_type':'HISTORICAL_REFERENCE','result':'FAILED_ALL_724_DATES','run_id':39915764325})
    records.append({'experiment_id':'HIST-STAGE-C-39915801452','record_type':'HISTORICAL_REFERENCE','result':'ABORTED_AT_DATA_GATE_ZERO_MODEL_TRIALS','run_id':39915801452})
    return records


def quarterly_signflip(events, cost=.012):
    blocks={f'{year}-Q{q}':0.0 for year in (2024,2025) for q in (1,2,3,4)}
    for event in events:
        net=event['gross_return']-cost
        if net<=-1:return {'status':'INSOLVENT','p_value':1.0}
        key=event['exit_date'][:4]+'-Q'+str((int(event['exit_date'][5:7])-1)//3+1)
        blocks[key]+=math.log1p(net)
    values=list(blocks.values());active=sum(abs(v)>1e-15 for v in values)
    if active<6:return {'status':'INSUFFICIENT_SAMPLE','p_value':1.0,'active_quarters':active,'blocks':blocks}
    observed=sum(values)
    null=[sum(sign*x for sign,x in zip(signs,values)) for signs in itertools.product((-1,1),repeat=len(values))]
    return {'status':'EXPLORATORY_BLOCK_SIGNFLIP','p_value':sum(v>=observed-1e-15 for v in null)/len(null),
            'active_quarters':active,'blocks':blocks,'assumption':'Symmetric independent quarter blocks; historical exploratory evidence, not pristine or guaranteed inference'}


def holm_adjust(items):
    previous=0.0
    for i,(name,item) in enumerate(sorted(items.items(),key=lambda x:(x[1]['p_value'],x[0]))):
        previous=max(previous,min(1.0,(len(items)-i)*item['p_value']))
        item['holm_adjusted_p']=previous
    return items


def validate_mother_receipt(mother, receipt_path):
    if receipt_path is None or not receipt_path.is_file():
        raise ValueError('MOTHER_RECEIPT_REQUIRED')
    receipt = json_load(receipt_path)
    if receipt.get('status') != 'PASS_EXACT_MEMBERSHIP_SET' or type(receipt.get('failed_dates')) is not int or receipt['failed_dates'] != 0:
        raise ValueError('MOTHER_RECEIPT_NOT_PASS')
    if receipt.get('universe') != 'TWSE_LISTED_ELECTRONICS_PIT_DAILY':
        raise ValueError('MOTHER_SCOPE_MISMATCH')
    years=receipt.get('year_receipts',[])
    if len(years)!=3 or {r.get('year') for r in years}!={2023,2024,2025}:
        raise ValueError('MOTHER_YEAR_BINDING_INCOMPLETE')
    for r in years:
        _,_,source=load_expected(r['year'])
        if r.get('membership_source',{}).get('sha256') != source['sha256']:
            raise ValueError('MOTHER_FROZEN_MEMBERSHIP_HASH_MISMATCH')
    if receipt.get('mother_sha256') != sha256_file(mother):
        raise ValueError('MOTHER_SHA_MISMATCH')
    return receipt


def verify_mother_membership(dates, by_date):
    expected = {}
    for year in (2023,2024,2025):
        daily,_,_ = load_expected(year);expected.update(daily)
    if dates != sorted(expected):
        raise ValueError('MOTHER_DATE_SET_MISMATCH')
    for d in dates:
        if set(by_date[d]) != expected[d]:
            raise ValueError('MOTHER_TICKER_SET_MISMATCH:'+d)


def _main(ledger) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mother", required=True)
    parser.add_argument("--mother-receipt", required=True)
    args = parser.parse_args()
    mother = Path(args.mother)
    receipt_path = Path(args.mother_receipt) if args.mother_receipt else None

    OUT.mkdir(parents=True, exist_ok=True)
    for required in (PLAN_PATH, NEIGHBOR_PATH, QUALITY_PATH, MANIFEST_PATH, BASELINE_PATH, SCOPE_PATH):
        if not required.exists():
            raise RuntimeError(f"REQUIRED_FILE_MISSING:{required}")
    plan = json_load(PLAN_PATH)
    if plan.get("status") != "FROZEN_BEFORE_SEARCH_RESULTS" or plan.get("authority", {}).get("capital_authority_twd") != 0:
        raise RuntimeError("SEARCH_PLAN_NOT_FROZEN_OR_AUTHORITY_INVALID")
    scope = json_load(SCOPE_PATH)
    if scope.get("status") != "HARD_SCOPE_LOCK" or scope.get("universe") != "TWSE_LISTED_ELECTRONICS_PIT_DAILY":
        raise RuntimeError("UNIVERSE_SCOPE_LOCK_INVALID")
    enforcement = scope.get("enforcement", {})
    if enforcement.get("signal_date_ticker_must_exist_in_pit_membership") is not True or enforcement.get("no_full_market_fallback") is not True:
        raise RuntimeError("UNIVERSE_SCOPE_ENFORCEMENT_INVALID")
    if abs(json_load(QUALITY_PATH)["rule"]["unverified_discontinuity_if_abs_close_to_close_return_gt"] - DISCONTINUITY) > 1e-12:
        raise RuntimeError("QUALITY_RULE_DRIFT")
    receipt = validate_mother_receipt(mother, receipt_path)
    for source in (BASELINE_PATH, MACRO/'sox_daily_202212_202610.csv', MACRO/'dxy_exact_DX-Y.NYB_202212_202610.csv'):
        verify_pinned_file(source)
    dates, by_date = load_mother(mother)
    verify_mother_membership(dates, by_date)
    market, context, date_index = prepare_features(dates, by_date)
    rank_cache = build_rank_cache(dates, by_date)
    all_configs = configs()
    manifest = json_load(MANIFEST_PATH)
    authorization = json_load(RESET/'RESET_AUTHORIZATION.json')
    if authorization.get('research_authorized') is not True or authorization.get('automated_model_search_authorized') is not True or authorization.get('production_changes_authorized') is not False:
        raise ValueError('RESET_RESEARCH_AUTHORIZATION_INVALID')
    if manifest['frozen_base']['base_commit'] != CORPUS_BASE:
        raise ValueError('CORPUS_MANIFEST_DRIFT')

    ledger_path = OUT / "EXPERIMENT_LEDGER.jsonl"
    run_prefix = str(os.environ.get('GITHUB_RUN_ID', datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')))+':'+str(os.environ.get('GITHUB_RUN_ATTEMPT','1'))
    for record in historical_ledger_records(manifest):
        ledger.append({**record,'record_id':run_prefix+':'+record['experiment_id'],'status':'HISTORICAL_REFERENCE'})
    sequence = 0
    global simulate
    original_simulate = simulate
    def journaled(*args, **kwargs):
        nonlocal sequence
        sequence += 1
        experiment_id = run_prefix+':EVAL:'+str(sequence)
        config,start,end,cost = args[:4]
        detail = {'experiment_id':experiment_id,'config_id':config.id,'period':[start,end],'cost':cost,
                  'evaluation_sequence':sequence,'options':kwargs}
        ledger.append({**detail,'record_id':experiment_id+':STARTED','status':'STARTED'})
        try:
            result = original_simulate(*args,**kwargs)
        except BaseException as exc:
            ledger.append({**detail,'record_id':experiment_id+':FAILED','status':'ABORTED' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'FAILED','error':type(exc).__name__+':'+str(exc)})
            raise
        ledger.append({**detail,'record_id':experiment_id+':RESULT','status':'EVALUATED' if result[0]['complete_trades'] else 'NO_TRADE','metrics':result[0]})
        return result
    simulate = journaled
    baseline = candidate_b_reproduction(dates,date_index,by_date,context,rank_cache)
    print('Baseline comparison status='+baseline['status']+'; event identity is not proven',flush=True)
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
            print('Selection family='+family+' fold='+fold_name+' configs='+str(len(family_configs)),flush=True)
            for config in family_configs:
                metrics, _ = simulate(config, sel_start, sel_end, SELECTION_COST, dates, date_index, by_date, context, rank_cache)
                trial_seq += 1
                eligible = metrics["complete_trades"] >= 6
                ledger.append({
                    'record_id':run_prefix+':SELECTION:'+str(trial_seq), 'status':'SELECTED_SAMPLE_ELIGIBLE' if eligible else 'REJECTED_SAMPLE_SIZE',
                    "experiment_id": run_prefix+':SELECTION:'+str(trial_seq),
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
            "no_insolvency": not any(m['insolvent'] for m in combined_by_cost.values()),
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

    print('Primary selection/validation completed; running preregistered destruction checks',flush=True)
    alt_dates,alt_rows=load_mother(mother)
    _,alt_context,alt_index=prepare_features(alt_dates,alt_rows,discontinuity=.10)
    alt_cache=build_rank_cache(alt_dates,alt_rows)
    statistical={}
    quality_results={}
    for family,fr in family_results.items():
        events=[];attacks=[]
        for fold_name,_,_,val_start,val_end in folds:
            fold=fr['folds'].get(fold_name,{})
            if fold.get('status')!='SELECTED_AND_VALIDATED':continue
            events+=fold['events']['cost_0.012']
            selected=Config(**fold['selected_config'])
            metrics,_=simulate(selected,val_start,val_end,.016,alt_dates,alt_index,alt_rows,alt_context,alt_cache)
            attacks.append({'fold':fold_name,'config_id':selected.id,'metrics':metrics})
        statistical[family]=quarterly_signflip(events)
        quality_results[family]={'alternative_discontinuity':.10,'folds':attacks,
            'pass':len(attacks)==2 and all(a['metrics']['complete_trades']>=3 and a['metrics']['compounded_return']>0 and not a['metrics']['insolvent'] for a in attacks)}
    holm_adjust(statistical)
    for row in summary_rows:
        family=row['family'];row['statistical_evidence']=statistical[family];row['quality_sensitivity']=quality_results[family]
        if 'eligibility' in row:
            row['eligibility']['holm_quarter_block_p_le_0.05']=statistical[family]['holm_adjusted_p']<=.05
            row['eligibility']['alternative_quality_survives']=quality_results[family]['pass']
            row['eligible']=all(row['eligibility'].values())
            family_results[family]['eligibility']=row['eligibility'];family_results[family]['eligible']=row['eligible']
    robustness={'method':'PREREGISTERED_QUARTER_BLOCK_SIGNFLIP_HOLM_7_FAMILIES_AND_STRICTER_QUALITY',
                'statistical':statistical,'quality_sensitivity':quality_results,'authority':AUTHORITY}
    (OUT/'ROBUSTNESS_REPORT.json').write_text(json.dumps(robustness,indent=2,sort_keys=True)+'\n')

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

    characterization={}
    for family,fr in family_results.items():
        events=[event for fold in fr['folds'].values() for event in fold.get('events',{}).get('cost_0.012',[])]
        groups=defaultdict(list)
        for event in events:
            d=event['signal_date'];state=context[d];m1=state['market'].get('r1');sox=state['sox']
            label=('LOCAL_NEG' if m1 is not None and m1<0 else 'LOCAL_OTHER_OR_MISSING')+'|'+('SOX5_WEAK' if sox and sox.get('ret5') is not None and sox['ret5']<=-.03 else 'SOX_OTHER_OR_MISSING')
            groups[label].append(event)
        characterization[family]={'regimes':{k:summarize_events(v,.012) for k,v in groups.items()},
                                  'concentration':concentration(events,.012)}
    (OUT/'REGIME_AND_CONCENTRATION_REPORT.json').write_text(json.dumps({'families':characterization,'authority':AUTHORITY},indent=2,sort_keys=True)+'\n')
    # Immutable per-attempt prefix snapshot; the shared journal stays append-only.
    with ledger_path.open('xb') as snapshot:
        snapshot.write(ledger.path.read_bytes())
    trial_summary = {
        "schema_version": 1,
        "stage": "C_D_CHRONOLOGICAL_RULE_SEARCH",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "search_plan_sha256": sha256_file(PLAN_PATH),
        "neighbor_rule_sha256": sha256_file(NEIGHBOR_PATH),
        "quality_rule_sha256": sha256_file(QUALITY_PATH),
        "scope_lock_sha256": sha256_file(SCOPE_PATH),
        "universe": scope["universe"],
        "mother_sha256": sha256_file(mother),
        "stage_b_run_id": os.environ.get('STAGE_B_RUN_ID'),
        "method_corrections_sha256":sha256_file(RESET/'METHOD_CORRECTIONS_V1.json'),
        "config_count": len(all_configs),
        "selection_trial_count": trial_seq,
        "ledger_record_count": ledger.count,
        "all_evaluation_count": sequence,
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
        "universe": scope["universe"],
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
        "universe": scope["universe"],
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
    simulate = original_simulate
    return 0


def main():
    global OUT
    root_output=OUT
    run_id=str(os.environ.get('GITHUB_RUN_ID',datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')))+'-'+str(os.environ.get('GITHUB_RUN_ATTEMPT','1'))
    OUT=root_output/'runs'/run_id
    OUT.mkdir(parents=True,exist_ok=False)
    provenance={'code_commit':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),
                'code_sha256':sha256_file(Path(__file__)),
                'frozen_corpus_base':CORPUS_BASE,'search_plan_sha256':sha256_file(PLAN_PATH),
                'method_corrections_sha256':sha256_file(RESET/'METHOD_CORRECTIONS_V1.json')}
    with TrialLedger(root_output/'EXPERIMENT_LEDGER.jsonl',provenance) as ledger:
        ledger.append({'record_id':run_id+':RUN_STARTED','status':'RUN_STARTED'})
        try:
            result=_main(ledger)
        except BaseException as exc:
            status='ABORTED' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'FAILED'
            ledger.append({'record_id':run_id+':RUN_'+status,'status':status,'error':type(exc).__name__+':'+str(exc)})
            failure={'status':'NO_ROBUST_WINNER','execution_status':'BLOCKED_'+status,
                     'reason':type(exc).__name__+':'+str(exc),'authority':AUTHORITY}
            (OUT/'WINNER_OR_NO_WINNER.json').write_text(json.dumps(failure,indent=2)+'\n')
            (OUT/'SEARCH_RUN_RECEIPT.json').write_text(json.dumps(failure,indent=2)+'\n')
            raise
        ledger.append({'record_id':run_id+':RUN_COMPLETED','status':'RUN_COMPLETED'})
        return result


if __name__ == "__main__":
    raise SystemExit(main())
