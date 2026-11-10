#!/usr/bin/env python3
"""Fixed-date HENGCE V2.2 original-code research replay over canonical-mother recovery.

This is retrospective ONLY. The model's model-first literature gate remains
unpassed and the 2026-11-07 research mothers were not signed by 2026-11-06.
The original PR#64 screen.py function is imported unmodified, pinned to its
immutable Git commit, never copied as a second selection strategy.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from hengce_retail_top5_vessel_bridge import DataBlocked, validate_output_target
from hengce_retail_top5_g1_retail_recovery import verified_panel
from hengce_retail_top5_mother_price_recovery import assemble

TW = ZoneInfo("Asia/Taipei")
DECISION = date(2026, 11, 6)
ORIGINAL_MODEL_COMMIT = "4a0f98fd2bd2a65deb2ebaf61e15e77c6a7893d6"
MODEL_DIR = Path("research/selection_models/retail_top5_v2_2")


def original_screen_module(repo: Path):
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        raise DataBlocked("ORIGINAL_V22_GIT_PROVENANCE_UNAVAILABLE") from exc
    if r.stdout.strip() != ORIGINAL_MODEL_COMMIT:
        raise DataBlocked("ORIGINAL_V22_IMMUTABLE_COMMIT_MISMATCH")
    src = repo / MODEL_DIR
    if not all((src / name).is_file() for name in ("screen.py", "validation.py", "strategy.py")):
        raise DataBlocked("ORIGINAL_V22_SCREEN_SOURCE_ABSENT")
    sys.path.insert(0, str(src))
    try:
        import screen
        import strategy
    except (ImportError, OSError) as exc:
        raise DataBlocked("ORIGINAL_V22_READONLY_IMPORT_FAILED") from exc
    if (strategy.PARAMETERS.get("lag") != 14 or
        strategy.PARAMETERS.get("r20_min") != 0.05 or
        strategy.PARAMETERS.get("r5_min") != 0 or
        strategy.PARAMETERS.get("retail_delta_max") != -0.01 or
        strategy.PARAMETERS.get("turnover_min") != 10_000_000 or
        strategy.PARAMETERS.get("ranking") != "liquidity_desc_ticker_asc" or
        strategy.TOP_N != 5):
        raise DataBlocked("ORIGINAL_V22_PARAMETERS_DIFFER")
    return screen


def replay(root: Path, original_repo: Path, decision=DECISION, *, today=None):
    if decision != DECISION:
        raise DataBlocked("RETROSPECTIVE_V22_DECISION_MUST_BE_20261106")
    today = today or datetime.now(TW).date()
    if today < DECISION:
        raise DataBlocked("DECISION_IN_FUTURE")
    raw_prices, price_receipt = assemble(root, decision, today=today)
    retail_rows, retail_manifest = verified_panel(root, decision)
    if (not price_receipt and not raw_prices):
        raise DataBlocked("RESEARCH_PRICE_UNAVAILABLE")
    if not price_receipt["research_price_continuity"] or len(price_receipt["origin_by_day"]) != 21:
        raise DataBlocked("RESEARCH_PRICE_21_DAY_RECOVERY_BLOCKED")
    if price_receipt["historical_pit_certified"] is not False:
        raise DataBlocked("PIT_CLASSIFICATION_INVALID")
    if len(retail_rows) != 3248 or retail_manifest["parent_source_generated_as_of"] != "2026-11-07":
        raise DataBlocked("G1_RETAIL_SOURCE_REPLAY_INVALID")
    screen = original_screen_module(original_repo)
    import pandas as pd
    # Read the same records through ORIGINAL V2.2 parsing/validation functions.
    import io
    daily_out = io.StringIO()
    writer = csv.writer(daily_out)
    writer.writerow(("Date","Ticker","Close","Volume","Turnover"))
    writer.writerows(raw_prices)
    chip_out = io.StringIO()
    writer = csv.writer(chip_out)
    writer.writerow(("SnapshotDate","Ticker","HolderLe10Lots","RetailPeopleValid"))
    writer.writerows(retail_rows)
    # V2.2 pd.read_csv uses usecols, so path-like string buffers are accepted.
    daily_out.seek(0)
    chip_out.seek(0)
    daily = screen.read_daily(daily_out)
    chips = screen.read_chips(chip_out)
    if (daily.Date.max().date() != DECISION or
        len(daily.Date.unique()) != 21 or
        chips.Date.max().date() != date(2026, 10, 22)):
        raise DataBlocked("RETRO_INPUT_PERIOD_INVALID")
    candidates = screen.eligible_stocks(
        daily, chips, lag=14, decision=pd.Timestamp(DECISION))
    candidates = candidates.sort_values(
        ["liquidity","ticker"], ascending=[False,True],kind="stable")
    if candidates.ticker.duplicated().any():
        raise DataBlocked("ORIGINAL_V22_RANK_DUPLICATED")
    reference = daily[daily.Date.eq(pd.Timestamp(DECISION))].set_index("Ticker")
    top = []
    for rank, r in enumerate(candidates.head(5).itertuples(index=False),1):
        c = reference.loc[r.ticker, "Close"]
        if not (c > 0):
            raise DataBlocked("V22_RANKED_STOCK_MISSING_DECISION_CLOSE")
        top.append({
            "rank": rank, "ticker": r.ticker,
            "reference_close": float(c),
            "r20_pct": round(float(r.r20)*100,4),
            "r5_pct": round(float(r.r5)*100,4),
            "retail_2week_pct": round(float(r.retail_delta)*100,4),
            "median_20d_turnover_twd": int(round(float(r.liquidity))),
            "chip_date": r.chip_date.strftime("%Y-%m-%d") if hasattr(r.chip_date, "strftime") else str(r.chip_date),
            "source": "ORIGINAL_V22_SCREEN_P64_AT_PINNED_COMMIT",
        })
    report = {
        "schema": "HENGCE_V22_RETROSPECTIVE_ORIGINAL_SCREEN_REPLAY_V1",
        "system": "HENGCE",
        "decision": DECISION.isoformat(),
        "research_scope": "POSTFACTO_RESEARCH_BACKFILL_ONLY_NO_CLEAN_PIT",
        "original_unmerged_model_commit": ORIGINAL_MODEL_COMMIT,
        "model_method": "ORIGINAL_V22_SCREEN_ELIGIBLE_STOCKS_LAG14",
        "original_model_parameters_unchanged": True,
        "model_literature_gate": "NOT_PASSED",
        "price_parent_sha256": price_receipt["canonical_parent_mother_sha256"],
        "retail_parent_sha256": retail_manifest["parent_sha256"],
        "price_original_eod_days": price_receipt["canonical_eod_days"],
        "price_mother_recovered_days": price_receipt["mother_research_recovered_days"],
        "retail_snapshot_count": 3,
        "retail_input_rows": len(retail_rows),
        "price_input_rows": len(raw_prices),
        "qualified_count": len(candidates),
        "historical_research_top5": top,
        "formal_selection_performed": False,
        "official_pit_certified": False,
        "trading_signal": False,
        "authorized_lots": 0,
        "capital_authority_twd": 0,
        "broker_execution": False,
        "new_canonical_data_written": False,
        "action": "RESEARCH_ONLY_NO_TRADING_AUTHORITY",
    }
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    cli.add_argument("--original-model-checkout", type=Path, required=True)
    cli.add_argument("--decision", default="2026-11-06")
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    try:
        d = date.fromisoformat(args.decision)
        result = replay(args.repo_root, args.original_model_checkout, d)
        out = validate_output_target(args.repo_root, args.output)
        out.mkdir(parents=True, exist_ok=False)
        (out / "historical_research_replay.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")
        print(json.dumps({
            "decision": result["decision"], "research_qualified": result["qualified_count"],
            "research_top5": [z["ticker"] for z in result["historical_research_top5"]],
            "official_pit_certified": False,
            "broker_execution": False,
        }, ensure_ascii=False))
    except (DataBlocked, ValueError, OSError, TypeError, KeyError, ImportError) as exc:
        cli.exit(2,"V22_RETROSPECTIVE_REPLAY_BLOCKED:"+str(exc)+"\n")


if __name__ == "__main__":
    main()
