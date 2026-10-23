#!/usr/bin/env python3
"""Build the frozen daily Q017 candidate artifact from causal PIT daily inputs.

This is an independent Q017 producer. It does not import or relabel E2 runtime
authority. Its mathematics are reproduced from the frozen Candidate-B evidence
that matches the later Q017 handoff contract; lineage is emitted explicitly.

The producer is intended to run on the entry/action session *before* that
session's TWSE type-13 close has been appended. It scores the latest completed
TWSE electronics session strictly before --trade-date and uses the latest
completed U.S. SOX session strictly before that signal date.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

from hengce_unified_contracts import ZERO_AUTHORITY, atomic

TZ = ZoneInfo("Asia/Taipei")
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ELECTRONICS = ROOT / "hengce/q017_radar/data/twse_electronics_history_2026.csv"
DEFAULT_SOX = ROOT / "hengce/q017_radar/data/sox_2026.csv"
DEFAULT_OUTPUT = ROOT / "hengce/q017_canonical/latest.json"

BETA_HISTORY_MAX = 60
BETA_HISTORY_MIN = 30
K = 25
TOP_N = 1
TURNOVER20_MIN = 20_000_000
TURNOVER20_MIN_FINITE = 10
RESIDUAL1_MAX = 0.04
ELECTRONICS_M1_MAX_EXCLUSIVE = 0.0
ELECTRONICS_M5_MAX = -0.02
SOX_1D_MAX = 0.0
SOX_5D_MAX = -0.03
MIN_PRODUCTION_DAILY_MEMBERS = 150

CANONICAL_CONTRACT = {
    "universe": "TWSE_LISTED_ELECTRONICS_PIT_DAILY",
    "beta_history_max": BETA_HISTORY_MAX,
    "beta_history_min": BETA_HISTORY_MIN,
    "signal_day_excluded_from_beta": True,
    "k": K,
    "score": "beta60*(1+25*max(-residual1,0))",
    "top_n": TOP_N,
    "avg_turnover20_min": TURNOVER20_MIN,
    "residual1_max": RESIDUAL1_MAX,
    "electronics_m1_max_exclusive": ELECTRONICS_M1_MAX_EXCLUSIVE,
    "electronics_m5_max": ELECTRONICS_M5_MAX,
    "sox_1d_max": SOX_1D_MAX,
    "sox_5d_max": SOX_5D_MAX,
    "dxy_used": False,
    "entry": "NEXT_TWSE_OPEN",
    "exit": "FIXED_20_SESSIONS",
    "roundtrip_cost": 0.008,
    "overlap_allowed": False,
}

EVIDENCE = {
    "frozen_validation_commit": "f5abef555d9174e3919a9dca52e9bfb07351e02e",
    "frozen_validation_path": "research/e2_profit_max/E2_PROFIT_MAX_CANDIDATE_B_FINAL_VALIDATION_20261019.json",
    "frozen_validation_blob": "4b583972f662cbf040b0705f5c5e51806c708e03",
    "implementation_evidence_path": "scripts/hengce_e2_live.py",
    "implementation_evidence_blob": "5dd05969ace4175ffcbecd8f381404f17ab873dd",
    "authority_note": "E2_RESEARCH_EVIDENCE_ONLY_NOT_Q017_RUNTIME_AUTHORITY",
}


def finite(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def iso_day(value) -> str:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError("INVALID_DATE:" + text) from exc


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def raw_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def producer_commit(root: Path = ROOT) -> str:
    """Return the commit that last changed this producer, not arbitrary branch HEAD."""
    relative = Path(__file__).resolve().relative_to(root)
    try:
        value = subprocess.check_output(
            ["git", "-C", str(root), "log", "-1", "--format=%H", "--", str(relative)],
            text=True,
            timeout=10,
        ).strip()
    except Exception as exc:
        raise ValueError("Q017_PRODUCER_COMMIT_UNRESOLVED") from exc
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("Q017_PRODUCER_COMMIT_INVALID")
    return value


def load_electronics(path: Path) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"date", "ticker", "close", "turnover_ntd"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("ELECTRONICS_COLUMNS_MISSING")
        for raw in reader:
            ds = iso_day(raw.get("date"))
            ticker = str(raw.get("ticker") or "").strip()
            if not re.fullmatch(r"[1-9]\d{3}", ticker):
                continue
            key = (ds, ticker)
            if key in seen:
                raise ValueError("DUPLICATE_ELECTRONICS_DATE_TICKER:" + ds + ":" + ticker)
            seen.add(key)
            close = finite(raw.get("close"))
            turnover = finite(raw.get("turnover_ntd"))
            if close is None or close <= 0:
                continue
            rows.append({"date": ds, "ticker": ticker, "name": str(raw.get("name") or ""),
                         "close": close, "turnover": turnover})
    if not rows:
        raise ValueError("ELECTRONICS_HISTORY_EMPTY")
    rows.sort(key=lambda row: (row["date"], row["ticker"]))
    return rows


def load_sox(path: Path) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {"date", "close"}.issubset(reader.fieldnames):
            raise ValueError("SOX_COLUMNS_MISSING")
        for raw in reader:
            ds = iso_day(raw.get("date"))
            if ds in seen:
                raise ValueError("DUPLICATE_SOX_DATE:" + ds)
            seen.add(ds)
            close = finite(raw.get("close"))
            if close is None or close <= 0:
                raise ValueError("INVALID_SOX_CLOSE:" + ds)
            rows.append({"date": ds, "close": close})
    rows.sort(key=lambda row: row["date"])
    if len(rows) < 6:
        raise ValueError("SOX_HISTORY_INSUFFICIENT")
    return rows


def prepare_features(rows: list[dict], signal_date: str, *, min_daily_members: int) -> tuple[dict, list[dict], dict]:
    by_ticker: dict[str, list[dict]] = defaultdict(list)
    by_date_r1: dict[str, list[float]] = defaultdict(list)
    for source in rows:
        if source["date"] <= signal_date:
            by_ticker[source["ticker"]].append(dict(source))

    for ticker, history in by_ticker.items():
        history.sort(key=lambda row: row["date"])
        previous_close = None
        turnovers: list[float | None] = []
        for row in history:
            r1 = row["close"] / previous_close - 1.0 if previous_close not in (None, 0) else None
            turnovers.append(row["turnover"])
            window = [v for v in turnovers[-20:] if v is not None and math.isfinite(v)]
            avg_turnover20 = sum(window) / len(window) if len(window) >= TURNOVER20_MIN_FINITE else None
            row["r1"] = r1
            row["avg_turnover20"] = avg_turnover20
            if r1 is not None and math.isfinite(r1):
                by_date_r1[row["date"]].append(r1)
            previous_close = row["close"]

    signal_members = sum(1 for row in rows if row["date"] == signal_date)
    if signal_members < min_daily_members:
        raise ValueError(f"SIGNAL_UNIVERSE_TOO_SMALL:{signal_members}")

    market: dict[str, dict] = {}
    market_dates = sorted(by_date_r1)
    for index, ds in enumerate(market_dates):
        values = by_date_r1[ds]
        if not values:
            continue
        m1 = median(values)
        market[ds] = {"m1": m1, "m5": None, "return_count": len(values)}
        if index >= 4:
            days = market_dates[index - 4:index + 1]
            if all(day in market for day in days):
                compounded = 1.0
                for day in days:
                    compounded *= 1.0 + market[day]["m1"]
                market[ds]["m5"] = compounded - 1.0

    current_market = market.get(signal_date)
    if not current_market or current_market["m5"] is None:
        raise ValueError("LOCAL_MARKET_FEATURES_MISSING")

    candidates: list[dict] = []
    for ticker, history in by_ticker.items():
        history.sort(key=lambda row: row["date"])
        index = next((i for i, row in enumerate(history) if row["date"] == signal_date), None)
        if index is None:
            continue
        current = history[index]
        if current.get("r1") is None or current.get("avg_turnover20") is None:
            continue
        if current["avg_turnover20"] < TURNOVER20_MIN:
            continue
        prior = history[max(0, index - BETA_HISTORY_MAX):index]
        observations: list[tuple[float, float]] = []
        for row in prior:
            market_r1 = market.get(row["date"], {}).get("m1")
            if row.get("r1") is not None and market_r1 is not None:
                observations.append((row["r1"], market_r1))
        if len(observations) < BETA_HISTORY_MIN:
            continue
        n = len(observations)
        stock_mean = sum(stock_r1 for stock_r1, _ in observations) / n
        market_mean = sum(market_r1 for _, market_r1 in observations) / n
        covariance = sum((stock_r1-stock_mean)*(market_r1-market_mean)
                         for stock_r1, market_r1 in observations) / n
        variance = sum((market_r1-market_mean)**2 for _, market_r1 in observations) / n
        if abs(variance) <= 1e-18:
            continue
        beta60 = covariance / variance
        if not math.isfinite(beta60) or beta60 <= 0:
            continue
        residual1 = current["r1"] - beta60 * current_market["m1"]
        if not math.isfinite(residual1) or residual1 > RESIDUAL1_MAX:
            continue
        score = beta60 * (1.0 + K * max(-residual1, 0.0))
        candidates.append({"ticker": ticker, "name": current.get("name", ""),
                           "beta60": beta60, "beta_observations": n,
                           "stock_r1": current["r1"], "residual1": residual1,
                           "q017_score": score, "avg_turnover20": current["avg_turnover20"],
                           "signal_close": current["close"]})
    candidates.sort(key=lambda row: (-row["q017_score"], row["ticker"]))
    diagnostics = {"signal_universe_members": signal_members,
                   "signal_market_return_count": current_market["return_count"],
                   "eligible_before_global_gates": len(candidates)}
    return current_market, candidates, diagnostics


def sox_features(rows: list[dict], signal_date: str) -> dict:
    usable = [row for row in rows if row["date"] < signal_date]
    if len(usable) < 6:
        raise ValueError("SOX_PRIOR_HISTORY_INSUFFICIENT")
    last = usable[-1]; previous = usable[-2]
    if (date.fromisoformat(signal_date) - date.fromisoformat(last["date"])).days > 7:
        raise ValueError("SOX_STALE_FOR_SIGNAL:" + last["date"])
    return {"session": last["date"], "sox_1d": last["close"] / previous["close"] - 1.0,
            "sox_5d": last["close"] / usable[-6]["close"] - 1.0}


def build_artifact(electronics_rows: list[dict], sox_rows: list[dict], *, trade_date: str,
                   generated_at: datetime, code_commit: str, input_hashes: dict[str, str],
                   min_daily_members: int = MIN_PRODUCTION_DAILY_MEMBERS) -> dict:
    trade_date = iso_day(trade_date)
    if generated_at.tzinfo is None:
        raise ValueError("GENERATED_AT_NAIVE")
    generated_at = generated_at.astimezone(TZ)
    if generated_at.date().isoformat() != trade_date:
        raise ValueError("GENERATED_AT_TRADE_DATE_MISMATCH")
    if not re.fullmatch(r"[0-9a-f]{40}", code_commit):
        raise ValueError("PRODUCER_COMMIT_INVALID")
    if not input_hashes or any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in input_hashes.values()):
        raise ValueError("INPUT_HASH_INVALID")
    available_dates = sorted({row["date"] for row in electronics_rows})
    if not available_dates:
        raise ValueError("ELECTRONICS_HISTORY_EMPTY")
    if available_dates[-1] >= trade_date:
        raise ValueError("NONCAUSAL_HISTORY_CONTAINS_TRADE_DATE_OR_LATER")
    signal_date = available_dates[-1]
    local, ranked, diagnostics = prepare_features(electronics_rows, signal_date,
                                                   min_daily_members=min_daily_members)
    macro = sox_features(sox_rows, signal_date)
    local_checks = {"electronics_m1_lt_0": local["m1"] < ELECTRONICS_M1_MAX_EXCLUSIVE,
                    "electronics_m5_lte_minus_2pct": local["m5"] <= ELECTRONICS_M5_MAX}
    macro_checks = {"sox_1d_lte_0": macro["sox_1d"] <= SOX_1D_MAX,
                    "sox_5d_lte_minus_3pct": macro["sox_5d"] <= SOX_5D_MAX}
    gate_go = all(local_checks.values()) and all(macro_checks.values())
    top1 = ranked[0] if ranked else None
    market_state = "GO" if gate_go and top1 is not None else "CASH"
    candidates = []
    if market_state == "GO":
        candidates = [{"ticker": top1["ticker"], "name": top1["name"], "q017_rank": 1,
                       "q017_score": top1["q017_score"], "beta60": top1["beta60"],
                       "beta_observations": top1["beta_observations"], "stock_r1": top1["stock_r1"],
                       "residual1": top1["residual1"], "signal_close": top1["signal_close"],
                       "qualified": True, "signal_date": signal_date, "entry_trade_date": trade_date,
                       "filter_evidence": {"avg_turnover20": top1["avg_turnover20"],
                                           "electronics_m1": local["m1"], "electronics_m5": local["m5"],
                                           "sox_1d": macro["sox_1d"], "sox_5d": macro["sox_5d"]}}]
    return {"schema_version": 1, "system": "HENGCE", "module": "HENGCE_CANONICAL_Q017_CANDIDATES",
            **ZERO_AUTHORITY, "generated_at": generated_at.isoformat(), "trade_date": trade_date,
            "signal_date": signal_date, "binding_status": "PASS", "market_state": market_state,
            "canonical_q017_contract": dict(CANONICAL_CONTRACT),
            "producer": {"name": "hengce_q017_canonical_producer", "code_commit": code_commit,
                         "input_hashes": dict(sorted(input_hashes.items())), "evidence": dict(EVIDENCE)},
            "local_gate": {"go": all(local_checks.values()), "checks": local_checks,
                           "electronics_m1": local["m1"], "electronics_m5": local["m5"]},
            "macro_gate": {"go": all(macro_checks.values()), "checks": macro_checks,
                           "sox_session": macro["session"], "sox_1d": macro["sox_1d"],
                           "sox_5d": macro["sox_5d"], "dxy_used": False},
            "selection": {"ranked_eligible_count": len(ranked),
                          "top1_ticker": top1["ticker"] if top1 else None,
                          "top1_score": top1["q017_score"] if top1 else None, "gate_go": gate_go},
            "diagnostics": diagnostics, "candidates": candidates}


def failure_artifact(*, trade_date: str, generated_at: datetime, code_commit: str | None,
                     input_hashes: dict[str, str], reason: str) -> dict:
    return {"schema_version": 1, "system": "HENGCE", "module": "HENGCE_CANONICAL_Q017_CANDIDATES",
            **ZERO_AUTHORITY, "generated_at": generated_at.astimezone(TZ).isoformat(),
            "trade_date": trade_date, "binding_status": "FAIL_CLOSED", "market_state": "CASH",
            "canonical_q017_contract": dict(CANONICAL_CONTRACT),
            "producer": {"name": "hengce_q017_canonical_producer", "code_commit": code_commit,
                         "input_hashes": dict(sorted(input_hashes.items())), "evidence": dict(EVIDENCE)},
            "candidates": [], "reason": reason}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--electronics-history", type=Path, default=DEFAULT_ELECTRONICS)
    parser.add_argument("--sox-history", type=Path, default=DEFAULT_SOX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--generated-at")
    args = parser.parse_args()
    now = datetime.fromisoformat(args.generated_at) if args.generated_at else datetime.now(TZ)
    if now.tzinfo is None:
        print("FAIL_CLOSED: GENERATED_AT_NAIVE", file=sys.stderr); return 2
    hashes: dict[str, str] = {}; commit = None
    try:
        trade_date = iso_day(args.trade_date)
        hashes = {"electronics_history": raw_hash(args.electronics_history),
                  "sox_history": raw_hash(args.sox_history)}
        commit = producer_commit()
        artifact = build_artifact(load_electronics(args.electronics_history), load_sox(args.sox_history),
                                  trade_date=trade_date, generated_at=now, code_commit=commit,
                                  input_hashes=hashes)
        atomic(args.output, artifact)
        print(json.dumps({"binding_status": artifact["binding_status"], "market_state": artifact["market_state"],
                          "signal_date": artifact["signal_date"], "trade_date": artifact["trade_date"],
                          "candidate_count": len(artifact["candidates"]), "output": str(args.output)},
                         ensure_ascii=False))
        return 0
    except Exception as exc:
        reason = f"{type(exc).__name__}:{exc}"
        try:
            atomic(args.output, failure_artifact(trade_date=iso_day(args.trade_date), generated_at=now,
                                                 code_commit=commit, input_hashes=hashes, reason=reason))
        except Exception:
            pass
        print("FAIL_CLOSED: " + reason, file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
