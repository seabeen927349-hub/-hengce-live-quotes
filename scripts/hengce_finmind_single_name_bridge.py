#!/usr/bin/env python3
"""Ephemeral single-name lookups inside HENGCE's existing paid FinMind snapshot.

This module DOES NOT perform any data fetch or write any licensed quote to disk.
An authorized private consumer in the same process can read an EphemeralQuote.
Only redacted, quote-free status may be persisted in the PUBLIC HENGCE repository.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")
HENGCE_LIVE_TTL_SECONDS = 480
TICKER = re.compile(r"[1-9][0-9]{3}\Z")


@dataclass(frozen=True, repr=False)
class EphemeralQuote:
    ticker: str
    asof: datetime
    price: float
    open: float | None
    high: float | None
    low: float | None
    average_price: float | None
    total_volume: float | None
    total_amount: float | None

    def __repr__(self) -> str:
        return f"EphemeralQuote(ticker={self.ticker!r}, values=REDACTED)"


def _number(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        n = float(v)
    except (ValueError, TypeError):
        return None
    return n if math.isfinite(n) else None


def _time(v: Any) -> datetime | None:
    if not isinstance(v, str) or not v.strip():
        return None
    try:
        dt = datetime.fromisoformat(v.strip())
    except ValueError:
        return None
    return dt.replace(tzinfo=TAIPEI) if dt.tzinfo is None else dt.astimezone(TAIPEI)


def lookup(
    snapshot_map: Mapping[str, Mapping[str, Any]],
    ticker: str,
    now: datetime,
    allowed_tickers: set[str],
) -> tuple[EphemeralQuote | None, str]:
    """Lookup ANY approved TWSE stock without a second FinMind request.

    Validation is fail-closed. No price fallback; no trading-model authority.
    """
    if not isinstance(ticker, str) or not TICKER.fullmatch(ticker):
        return None, "INVALID_TICKER"
    if ticker not in allowed_tickers:
        return None, "OUTSIDE_GOVERNED_TWSE_UNIVERSE"
    if now.tzinfo is None:
        return None, "NOW_MISSING_TIMEZONE"
    row = snapshot_map.get(ticker)
    if not isinstance(row, Mapping):
        return None, "NOT_IN_SNAPSHOT"
    if str(row.get("stock_id") or "").strip() != ticker:
        return None, "SOURCE_TICKER_MISMATCH"
    dt = _time(row.get("date"))
    if dt is None:
        return None, "SOURCE_TIMESTAMP_INVALID"
    local_now = now.astimezone(TAIPEI)
    age = (local_now - dt).total_seconds()
    if dt.date() != local_now.date():
        return None, "NOT_CURRENT_MARKET_DATE"
    if age < -30:
        return None, "FUTURE_TIMESTAMP"
    if age > HENGCE_LIVE_TTL_SECONDS:
        return None, "STALE_GT_480_SECONDS"
    price = _number(row.get("close"))
    if price is None or price <= 0:
        return None, "LAST_PRICE_UNAVAILABLE"
    return EphemeralQuote(
        ticker=ticker, asof=dt, price=price, open=_number(row.get("open")),
        high=_number(row.get("high")), low=_number(row.get("low")),
        average_price=_number(row.get("average_price")),
        total_volume=_number(row.get("total_volume")),
        total_amount=_number(row.get("total_amount")),
    ), "READY_IN_RUNNER_MEMORY_ONLY"


def public_status(
    snapshot_map: Mapping[str, Mapping[str, Any]],
    watch_tickers: Sequence[str],
    now: datetime,
    allowed_tickers: set[str],
) -> dict[str, Any]:
    """Price-free diagnostics only. No raw vendor fields, no redistributable quotes."""
    statuses: dict[str, str] = {}
    for ticker in watch_tickers:
        if ticker in statuses:
            raise ValueError("DUPLICATE_WATCH_TICKER")
        _, state = lookup(snapshot_map, ticker, now, allowed_tickers)
        statuses[ticker] = state
    return {
        "schema": "HENGCE_FINMIND_SINGLE_NAME_IN_MEMORY_V1",
        "source": "EXISTING_FINMIND_TAIWAN_STOCK_TICK_SNAPSHOT_VESSEL",
        "single_fetch_reused": True,
        "query_capability": "ANY_GOVERNED_TWSE_COMMON_STOCK",
        "ttl_seconds": HENGCE_LIVE_TTL_SECONDS,
        "watch_status": statuses,
        "ready_count": sum(s == "READY_IN_RUNNER_MEMORY_ONLY" for s in statuses.values()),
        "raw_finmind_rows_persisted": False,
        "per_security_quote_values_persisted": False,
        "paid_quote_values_in_public_repo": False,
        "private_quote_consumer_connected": False,
        "model_authority_created": False,
        "trading_authority_created": False,
    }
