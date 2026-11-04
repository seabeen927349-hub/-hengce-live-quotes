#!/usr/bin/env python3
"""Point-in-time equity membership for HENGCE's single-name QUOTE TRANSPORT ONLY.

Consumes FinMind TaiwanStockInfo rows in process. The LIVE quote source remains
the SAME full-market FinMind tick snapshot as the existing HENGCE vessel.
Does not mutate Market State, its TWSE-only membership, selection, or EOD.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Mapping, Sequence

FOUR_DIGIT_EQUITY = re.compile(r"[1-9][0-9]{3}\Z")
SUPPORTED_MARKETS = ("twse", "tpex", "emerging")


def current_equity_membership(rows: Sequence[Mapping[str, Any]], asof: date) -> tuple[dict[str, str], dict[str, int]]:
    """Latest dated record per stock_id is authoritative for listing transfers.

    Fail closed on missing or impossible market metadata. Excludes ETF/ETN/TDR,
    warrants, and non-four-digit securities. No market membership is invented
    from ticker prefixes or FinMind snapshot presence.
    """
    latest: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        ticker = str(row.get("stock_id") or "").strip()
        if not FOUR_DIGIT_EQUITY.fullmatch(ticker):
            continue
        d = str(row.get("date") or "").strip()[:10]
        try:
            row_date = date.fromisoformat(d)
        except ValueError:
            continue
        if row_date > asof:
            continue
        previous = latest.get(ticker)
        if previous is None or d > str(previous.get("date") or "")[:10]:
            latest[ticker] = row

    membership: dict[str, str] = {}
    for ticker, row in latest.items():
        venue = str(row.get("type") or "").strip().lower()
        category = str(row.get("industry_category") or "").strip().upper()
        name = str(row.get("stock_name") or "").strip().upper()
        if venue not in SUPPORTED_MARKETS:
            continue
        if category in {"ETF", "ETN", "TDR"} or "存託" in category or "-DR" in name:
            continue
        membership[ticker] = venue

    counts = {venue: sum(x == venue for x in membership.values()) for venue in SUPPORTED_MARKETS}
    if counts["twse"] < 900 or counts["tpex"] < 700:
        raise RuntimeError("FINMIND_EQUITY_MEMBERSHIP_COVERAGE_UNVERIFIED")
    return membership, counts
