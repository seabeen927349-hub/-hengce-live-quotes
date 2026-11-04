#!/usr/bin/env python3
"""Quote-only Taiwan equity membership, reusing the governed FinMind credential.

The same HENGCE FinMind runner already uses TaiwanStockInfo for membership in
its legacy market-state auxiliary capability. This module is for **single-name
quote transport ONLY**; it never changes frozen Market State TWSE-only scope.
No ticker membership vendor rows are persisted, published or logged.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date
from typing import Any, Mapping, Sequence

FOUR_DIGIT_EQUITY = re.compile(r"[1-9][0-9]{3}\Z")
SUPPORTED_MARKETS = ("twse", "tpex", "emerging")
FINMIND_STOCK_INFO_ENDPOINT = "https://api.finmindtrade.com/api/v4/data"


def current_equity_membership(
    rows: Sequence[Mapping[str, Any]], asof: date,
) -> tuple[dict[str, str], dict[str, int]]:
    """Use latest record per ID as of date to respect listing transfers.

    Reject ETF/ETN/TDR, non-4-digit IDs and unsupported market labels.
    Do not invent stock membership from its symbol prefix or price snapshot.
    """
    latest: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        ticker = str(row.get("stock_id") or "").strip()
        if not FOUR_DIGIT_EQUITY.fullmatch(ticker):
            continue
        stamp = str(row.get("date") or "").strip()[:10]
        try:
            row_date = date.fromisoformat(stamp)
        except ValueError:
            continue
        if row_date > asof:
            continue
        previous = latest.get(ticker)
        if previous is None or stamp > str(previous.get("date") or "")[:10]:
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


def fetch_current_equity_membership(
    asof: date, token: str | None = None,
) -> tuple[dict[str, str], dict[str, int]]:
    """Reuse existing governed FinMind token in the same already-run vessel.

    Fetches ONLY listing metadata, never an additional price snapshot.
    No credential/row content is logged, persisted, or sent to a public API.
    """
    credential = token or os.environ.get("FINMIND_TOKEN")
    if not credential:
        raise RuntimeError("FINMIND_TOKEN_MISSING")
    query = urllib.parse.urlencode({"dataset": "TaiwanStockInfo"})
    req = urllib.request.Request(
        FINMIND_STOCK_INFO_ENDPOINT + "?" + query,
        headers={"Authorization": "Bearer " + credential, "Accept": "application/json",
                 "User-Agent": "HENGCE-GOVERNED-SINGLE-NAME-MEMBERSHIP/1"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.load(response)
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("FINMIND_MEMBERSHIP_EMPTY_OR_MALFORMED")
    return current_equity_membership(rows, asof)
