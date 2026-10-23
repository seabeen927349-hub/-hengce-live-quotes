#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RESET = ROOT / "research" / "codex_full_reset_20261023"
sys.path.insert(0, str(RESET))

from stage_c_rule_search import (  # noqa: E402
    Config,
    build_rank_cache,
    concentration,
    load_macro,
    load_mother,
    prepare_features,
    prior_macro,
    regime_pass,
    remove_best_return,
    simulate,
)

OUT = RESET / "rr_v1_20261023" / "simulation_20261023"
OUT.mkdir(parents=True, exist_ok=True)

MOTHER_2023_2025 = RESET / "results" / "stage_b" / "TWSE_ELECTRONICS_DAILY_2023_2025.csv.gz"
HIST_2026 = ROOT / "hengce" / "q017_radar" / "data" / "twse_electronics_history_2026.csv"
SOX_LIVE = ROOT / "hengce" / "q017_radar" / "data" / "sox_2026.csv"
SOX_FROZEN = ROOT / "research" / "e2_profit_max" / "macro" / "sox_daily_202212_202610.csv"

START = "2026-01-01"
END = "2026-10-22"
COSTS = (0.008, 0.012, 0.016)
CONFIG = Config("RESIDUAL_REVERSAL", "NEG_RESID1", 50_000_000.0, 1, 20, "PRIOR_SOX5_LE_-0.03")


def four_digit_only(by_date):
    dropped = 0
    out = {}
    for d, rows in by_date.items():
        kept = {}
        for ticker, row in rows.items():
            if len(ticker) == 4 and ticker.isdigit():
                kept[ticker] = row
            else:
                dropped += 1
        out[d] = kept
    return out, dropped


def load_live_sox_with_returns(path: Path):
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for rec in csv.DictReader(f):
            d = (rec.get("date") or "").strip()
            try:
                close = float(str(rec.get("close") or "").replace(",", ""))
            except Exception:
                continue
            if d and math.isfinite(close) and close > 0:
                rows.append((d, close))
    rows.sort()
    out = []
    for i, (d, close) in enumerate(rows):
        ret1 = close / rows[i - 1][1] - 1.0 if i >= 1 else None
        ret5 = close / rows[i - 5][1] - 1.0 if i >= 5 else None
        out.append({"date": d, "ret1": ret1, "ret5": ret5})
    return out


def verify_sox_semantics(live):
    frozen = {r["date"]: r for r in load_macro(SOX_FROZEN)}
    compared = 0
    max_d1 = 0.0
    max_d5 = 0.0
    for r in live:
        f = frozen.get(r["date"])
        if not f:
            continue
        if r["ret1"] is not None and f.get("ret1") is not None:
            max_d1 = max(max_d1, abs(r["ret1"] - f["ret1"]))
        if r["ret5"] is not None and f.get("ret5") is not None:
            max_d5 = max(max_d5, abs(r["ret5"] - f["ret5"]))
        compared += 1
    # This is a schema continuation, not a feature rewrite. Stop if overlap disagrees materially.
    if compared < 100 or max(max_d1, max_d5) > 1e-8:
        raise RuntimeError(f"SOX_RETURN_SEMANTICS_MISMATCH compared={compared} max_d1={max_d1} max_d5={max_d5}")
    return {"overlap_rows_compared": compared, "max_abs_ret1_diff": max_d1, "max_abs_ret5_diff": max_d5}


def main():
    dates_old, by_old = load_mother(MOTHER_2023_2025)
    dates_26, by_26_raw = load_mother(HIST_2026)
    by_26, dropped = four_digit_only(by_26_raw)

    # Frozen Stage-B universe semantics are four-digit TWSE electronics. Use 2025 only as causal warmup.
    by_date = {d: rows for d, rows in by_old.items() if d >= "2025-01-01"}
    for d in dates_26:
        if d in by_date:
            raise RuntimeError(f"DUPLICATE_DATE_ACROSS_SOURCES:{d}")
        by_date[d] = by_26[d]
    dates = sorted(by_date)

    market, context, date_index = prepare_features(dates, by_date)

    live_sox = load_live_sox_with_returns(SOX_LIVE)
    sox_check = verify_sox_semantics(live_sox)
    for d in dates:
        if d >= START:
            context[d]["sox"] = prior_macro(live_sox, d)

    rank_cache = build_rank_cache(dates, by_date)
    regime_occurrences = sum(1 for d in dates if START <= d <= END and regime_pass(CONFIG.regime, d, context))

    metrics_by_cost = {}
    events_ref = None
    for cost in COSTS:
        metrics, events = simulate(CONFIG, START, END, cost, dates, date_index, by_date, context, rank_cache)
        metrics_by_cost[f"{cost:.3f}"] = metrics
        if abs(cost - 0.012) < 1e-12:
            events_ref = events

    if events_ref is None:
        raise RuntimeError("MISSING_REFERENCE_EVENTS")

    conc = concentration(events_ref, 0.012)
    remove_best = remove_best_return(events_ref, 0.012)

    result = {
        "status": "HISTORICAL_SIMULATION_COMPLETE",
        "authority": {
            "research_only": True,
            "broker_order_execution": False,
            "capital_authority_twd": 0,
            "signal_authority": False,
            "ranking_authority": False,
            "production_promotion": False,
            "merge_authorized": False,
            "main_write_authorized": False,
        },
        "claim": "historical simulation only; actual historical auction allocation/fill is not claimed",
        "config_id": CONFIG.id,
        "evaluation_period": [START, END],
        "source_2026": str(HIST_2026.relative_to(ROOT)),
        "source_2026_dates": [min(dates_26), max(dates_26)],
        "source_2026_rows_four_digit": sum(len(rows) for rows in by_26.values()),
        "non_four_digit_rows_excluded_to_match_frozen_stage_b_universe": dropped,
        "warmup_source": str(MOTHER_2023_2025.relative_to(ROOT)),
        "warmup_used": [min(d for d in dates if d.startswith("2025-")), max(d for d in dates if d.startswith("2025-"))],
        "sox_extension": {
            "source": str(SOX_LIVE.relative_to(ROOT)),
            "method": "ret1/ret5 recomputed mechanically from retained closes; overlap must match frozen Stage-C macro within 1e-8",
            **sox_check,
        },
        "regime_occurrences": regime_occurrences,
        "metrics_by_cost": metrics_by_cost,
        "cost_0.012_extra": {
            **conc,
            "remove_best_trade_return": remove_best,
        },
        "new_configurations_evaluated": 1,
        "parameter_tuning": 0,
        "family_search": 0,
        "market_downloads": 0,
        "production_bytes_modified": False,
    }

    (OUT / "RR_V1_SIM_RESULT.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (OUT / "RR_V1_SIM_EVENTS.jsonl").open("w", encoding="utf-8") as f:
        for event in events_ref:
            e = dict(event)
            e["net_return_cost_0.012"] = event["gross_return"] - 0.012
            f.write(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n")

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
