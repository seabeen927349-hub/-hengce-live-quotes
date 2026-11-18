"""Ephemeral FinMind/TWSE-MIS per-ticker audit; publish COUNTS only.

No network calls, per-security persistence, ranking, or trading authority. TWSE
MIS evidence is only the subset already fetched by the parent collector.
Same trade timestamps are candidates for comparison, NOT a formal price feed.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")
SCHEMA = "HENGCE_FINMIND_IN_MEMORY_SAME_TICK_AUDIT_V1"
MAX_AGE_SECONDS = 90
MAX_TRADE_TIME_DIFF_SECONDS = 1


def local_time(value: Any) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(str(value))
        return stamp.replace(tzinfo=TAIPEI) if stamp.tzinfo is None else stamp.astimezone(TAIPEI)
    except (ValueError, TypeError):
        return None


def mis_trade_time(row: dict[str, Any]) -> datetime | None:
    day = str(row.get("d") or "").strip()
    clock = str(row.get("t") or "").strip()
    if len(day) != 8 or not day.isdigit():
        return None
    try:
        parsed = datetime.strptime(day + " " + clock, "%Y%m%d %H:%M:%S")
        return parsed.replace(tzinfo=TAIPEI)
    except ValueError:
        return None


def positive_price(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value).replace(",", "").strip())
        return parsed if parsed.is_finite() and parsed > 0 else None
    except (ValueError, InvalidOperation):
        return None


def audit_snapshot(
    active_codes: set[str],
    finmind_rows: dict[str, dict[str, Any]],
    mis_rows: dict[str, dict[str, Any]],
    session_date: str,
    finmind_received_at: datetime,
    comparison_completed_at: datetime,
) -> dict[str, Any]:
    """One output status per active code, but NEVER emit per-code values or IDs."""
    if (finmind_received_at.tzinfo is None or comparison_completed_at.tzinfo is None
            or comparison_completed_at < finmind_received_at):
        raise ValueError("INVALID_CAPTURE_CLOCK")
    if finmind_received_at.astimezone(TAIPEI).date().isoformat() != session_date:
        raise ValueError("FINMIND_CAPTURE_WRONG_SESSION")
    if not set(mis_rows).issubset(active_codes):
        raise ValueError("MIS_SCOPE_OUTSIDE_ACTIVE_UNIVERSE")

    outcomes: Counter[str] = Counter()
    source_dates: Counter[str] = Counter()
    for ticker in sorted(active_codes):
        vendor = finmind_rows.get(ticker)
        if vendor is None:
            outcomes["FINMIND_MISSING"] += 1
            continue

        stamp = local_time(vendor.get("date"))
        if stamp is None:
            outcomes["FINMIND_TIME_MISSING"] += 1
            continue
        if stamp.date().isoformat() != session_date:
            outcomes["FINMIND_NOT_TODAY"] += 1
            continue

        source_dates["FINMIND_CURRENT_DAY"] += 1
        age = (finmind_received_at - stamp).total_seconds()
        if age < -5:
            outcomes["FINMIND_FUTURE_TIME"] += 1
            continue
        if age > MAX_AGE_SECONDS:
            outcomes["FINMIND_STALE_TRADE_TIME"] += 1
            continue
        vendor_price = positive_price(vendor.get("close"))
        if vendor_price is None:
            outcomes["FINMIND_PRICE_NOT_COMPARABLE"] += 1
            continue

        twse = mis_rows.get(ticker)
        if twse is None:
            outcomes["SECOND_SOURCE_NOT_COLLECTED"] += 1
            continue
        twse_stamp = mis_trade_time(twse)
        if twse_stamp is None or twse_stamp.date().isoformat() != session_date:
            outcomes["TWSE_TRADE_TIME_UNVERIFIED"] += 1
            continue
        if ((comparison_completed_at - twse_stamp).total_seconds() < -5
                or (comparison_completed_at - twse_stamp).total_seconds() > MAX_AGE_SECONDS):
            outcomes["TWSE_NOT_CURRENT_TRADE"] += 1
            continue
        if abs((stamp - twse_stamp).total_seconds()) > MAX_TRADE_TIME_DIFF_SECONDS:
            outcomes["TRADE_TIMESTAMPS_DIFFER"] += 1
            continue
        official_price = positive_price(twse.get("z"))
        if official_price is None:
            outcomes["TWSE_LAST_PRICE_UNAVAILABLE"] += 1
            continue
        outcomes["MATCHED_TRADE_TIME_PRICE_CANDIDATE" if vendor_price == official_price
                 else "DIFFERENT_PRICE_CANDIDATE"] += 1

    total = sum(outcomes.values())
    if total != len(active_codes):
        raise AssertionError("IN_MEMORY_AUDIT_COVERAGE_INVARIANT")
    candidate_count = outcomes["MATCHED_TRADE_TIME_PRICE_CANDIDATE"] + outcomes["DIFFERENT_PRICE_CANDIDATE"]
    return {
        "schema": SCHEMA,
        "role": "RESEARCH_INTRADAY_DIAGNOSTIC_ONLY",
        "status": "CANDIDATES_ONLY" if candidate_count else "BLOCKED_NO_SAME_TIME_SECOND_SOURCE",
        "session_date": session_date,
        "finmind_response_received_at_taipei": finmind_received_at.isoformat(),
        "comparison_completed_at_taipei": comparison_completed_at.isoformat(),
        "active_scope_count": len(active_codes),
        "mis_existing_scope_count": len(mis_rows),
        "finmind_current_day_count": source_dates["FINMIND_CURRENT_DAY"],
        "cross_source_candidate_count": candidate_count,
        "fully_independently_verified_count": 0,
        "reason_counts": dict(sorted(outcomes.items())),
        "raw_vendor_rows_persisted": False,
        "per_security_rows_persisted": False,
        "new_vendor_requests": 0,
        "formal_eod_authority": False,
        "selection_authority": False,
        "model_authority": False,
        "trading_authority": False,
    }
