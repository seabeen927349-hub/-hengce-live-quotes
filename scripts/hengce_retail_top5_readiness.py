#!/usr/bin/env python3
"""Weekly V2.2 research data-readiness checkpoint using existing HENGCE vessels.

This is a DATA/PIT capability audit only. The V2.2 model-first PR has not
passed HENGCE literature-first governance, so this script must never rank
stocks or import/execute the unmerged research selector. It prepares verified
inputs for a separately approved, preregistered research path.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from hengce_retail_top5_vessel_bridge import DataBlocked, audit, validate_output_target
from hengce_twse_calendar import load_manifest, is_trading_day

TW = ZoneInfo("Asia/Taipei")
MODEL_CHOICE = "hengce/HENGCE_SELECTION_MODEL_CHOICE_LATEST.json"
STRATEGY_AUTHORITY = "governance/HENGCE_ACTIVE_STRATEGY_AUTHORITY_20261105.json"


def latest_friday(day: date) -> date:
    return day - timedelta(days=(day.weekday() - 4) % 7)


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None


def expected_sessions(decision: date, calendar: dict, n: int = 21) -> list[str]:
    """Exact official TWSE session sequence, not just 21 arbitrary EOD folders."""
    days = []
    d = decision
    while d.year == 2026 and len(days) < n:
        if is_trading_day(d, calendar):
            days.append(d.isoformat())
        d -= timedelta(days=1)
    return list(reversed(days))


def market_readiness(root: Path, decision: date, *, today: date | None = None,
                     inspector=audit):
    today = today or datetime.now(TW).date()
    status = {
        "schema": "HENGCE_V22_WEEKLY_ORIGINAL_VESSEL_READINESS_V1",
        "model": "HENGCE_SELECTION_MODEL_V2_2_TOP5",
        "mode": "DATA_PREPARATION_ONLY_NO_SELECTION",
        "decision": decision.isoformat(),
        "source_owner": "HENGCE_EXISTING_EOD_AND_TDCC_ONLY",
        "source_status": "BLOCKED",
        "governance_status": "LITERATURE_FIRST_MANDATE_REMOVED_RESEARCH_ONLY",
        "selection_status": "NOT_RUN_UNMERGED_MODEL_AND_NO_PROMOTION",
        "selection_attempted": False,
        "top5": [],
        "model_ranking_authority": False,
        "signal_authority": False,
        "formal_selection_authority": False,
        "capital_authority_twd": 0,
        "authorized_lots": 0,
        "broker_execution": False,
        "formal_eod_replaced": False,
        "formal_tdcc_replaced": False,
        "missing_eod_sessions": [],
        "blockers": [],
        "source_receipt": None,
        "expected_session_count": 21,
        "calendar_lineage": None,
    }
    if decision > today:
        status["blockers"].append("DECISION_IN_FUTURE")
    if decision.weekday() != 4:
        status["blockers"].append("DECISION_NOT_FRIDAY")
    if decision.year != 2026:
        status["blockers"].append("TWSE_PINNED_CALENDAR_YEAR_UNSUPPORTED")
    preference = read_json(root / MODEL_CHOICE)
    # V2.2 remains the original verified weekly BENCHMARK after the user
    # designates V2.2-D daily as primary. Do not treat the preference switch
    # as evidence that the original EOD/TDCC data vessel is broken.
    legacy = (isinstance(preference,dict)
              and preference.get("model_package")=="HENGCE_SELECTION_MODEL_V2_2_TOP5"
              and preference.get("choice_status")=="PREFERRED_PENDING_PROMOTION")
    v22d = (isinstance(preference,dict)
            and preference.get("model_package")=="HENGCE_SELECTION_MODEL_V2_2_D_DAILY_TOP5"
            and preference.get("choice_status")=="PREFERRED_DAILY_RESEARCH_PENDING_PROSPECTIVE"
            and preference.get("model_id")=="v22d_daily_nowcast_liquidity_top5_v1"
            and preference.get("original_v22_weekly_status")=="RETAINED_READ_ONLY_BENCHMARK_NOT_CURRENT_PRIMARY")
    if not isinstance(preference, dict) or (
        not (legacy or v22d)
        or preference.get("formal_selection_authority") is not False
        or preference.get("broker_execution") is not False
        or preference.get("buy_sell_signal_authority") is not False
        or type(preference.get("capital_authority_twd")) is not int
        or preference.get("capital_authority_twd") != 0
    ):
        status["blockers"].append("V22_USER_MODEL_CHOICE_UNVERIFIED")
    formal = read_json(root / STRATEGY_AUTHORITY)
    if not isinstance(formal, dict) or (
        formal.get("active_strategy_count") != 0
        or formal.get("selection_authority") is not False
        or formal.get("broker_order_execution") is not False
    ):
        status["blockers"].append("EXISTING_STRATEGY_AUTHORITY_BOUNDARY_UNVERIFIED")
    try:
        calendar, _, lineage = load_manifest()
        status["calendar_lineage"] = lineage
        if decision.year == 2026 and decision.weekday() == 4:
            expected = expected_sessions(decision, calendar)
            status["expected_sessions"] = expected
            if len(expected) != 21:
                status["blockers"].append("NOT_ENOUGH_OFFICIAL_SESSIONS_WITHIN_YEAR")
            if not is_trading_day(decision, calendar):
                status["blockers"].append("DECISION_NOT_OFFICIAL_TRADING_SESSION")
    except (ValueError, OSError, KeyError, TypeError):
        status["blockers"].append("OFFICIAL_TRADING_CALENDAR_UNVERIFIED")
        expected = []
    if status["blockers"]:
        status["source_status"] = "BLOCKED_BEFORE_SOURCE_AUDIT"
        return status, [], []
    receipt, daily, weekly = inspector(root, decision)
    status["source_receipt"] = {
        "schema": receipt.get("schema"),
        "status": receipt.get("status"),
        "verified_eod_day_count": receipt.get("verified_eod_day_count"),
        "verified_tdcc_week_count": receipt.get("verified_tdcc_week_count"),
        "sources": receipt.get("sources"),
        "auxiliary": receipt.get("auxiliary"),
    }
    status["blockers"].extend(receipt.get("blockers") or [])
    have = {day["date"] for day in receipt.get("sources", {}).get("eod", [])
            if isinstance(day, dict) and isinstance(day.get("date"), str)}
    status["missing_eod_sessions"] = [d for d in expected if d not in have]
    if status["missing_eod_sessions"]:
        status["blockers"].append("OFFICIAL_EOD_SESSION_CONTINUITY_INCOMPLETE")
    if receipt.get("status") != "SOURCE_DATA_PREPARED_RESEARCH_ONLY":
        status["blockers"].append("CANONICAL_INPUT_RECEIPT_NOT_READY")
    status["source_status"] = ("SOURCE_DATA_PREPARED_RESEARCH_ONLY"
                               if not status["blockers"] else "BLOCKED")
    # This is strictly a DATA readiness audit, not a selector.
    # Selection belongs to a separate research pipeline; no broker authority.
    return status, daily if status["source_status"] == "SOURCE_DATA_PREPARED_RESEARCH_ONLY" else [], (
        weekly if status["source_status"] == "SOURCE_DATA_PREPARED_RESEARCH_ONLY" else []
    )


def write_checkpoint(repo: Path, output: Path, status: dict, daily: list, weekly: list):
    target = validate_output_target(repo, output)
    target.mkdir(parents=True, exist_ok=False)
    (target / "readiness.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if status["source_status"] == "SOURCE_DATA_PREPARED_RESEARCH_ONLY":
        fields = [
            ("verified_daily_input.csv", ["Date", "Ticker", "Close", "Volume", "Turnover"], daily),
            ("verified_tdcc_input.csv", ["SnapshotDate", "Ticker", "HolderLe10Lots", "RetailPeopleValid"], weekly)
        ]
        for name, columns, rows in fields:
            with (target / name).open("x", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(rows)
    return target


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    cli.add_argument("--decision", help="Friday YYYY-MM-DD; default latest Friday Taiwan time")
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    now = datetime.now(TW).date()
    try:
        decision = date.fromisoformat(args.decision) if args.decision else latest_friday(now)
        status, daily, weekly = market_readiness(args.repo_root, decision, today=now)
        write_checkpoint(args.repo_root, args.output, status, daily, weekly)
        print(json.dumps({
            "decision": status["decision"], "source_status": status["source_status"],
            "missing_eod_sessions": status["missing_eod_sessions"],
            "blockers": status["blockers"],
            "selection_status": status["selection_status"],
            "research_top5_count": 0,
            "broker_execution": False,
        }, ensure_ascii=False))
        return 0  # Blocked data is an explicit research artifact, not a failed ingestion.
    except (DataBlocked, ValueError, OSError, TypeError) as exc:
        cli.exit(2, "READINESS_PIPELINE_ERROR:" + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
