#!/usr/bin/env python3
"""Reviewed producer admission for optional canonical Q017 evidence.

This module grants no capital or geometry authority. It pins the reviewed producer
commit and performs lineage/session checks before the existing unified adapter is
allowed to consider Q017. Invalid reviewed-producer artifacts are isolated as an
unavailable optional source so valid legacy HENGCE can continue.
"""
from __future__ import annotations

from datetime import date

VERIFIED_PRODUCER_NAME = "hengce_q017_canonical_producer"
VERIFIED_PRODUCER_COMMIT = "a60265f29cc57e79873f4fc9e99fa8996e15558c"
EXPECTED_EVIDENCE_COMMIT = "f5abef555d9174e3919a9dca52e9bfb07351e02e"

AUTHORITY_KEYS = {
    "BreakoutLower", "breakout_lower", "BreakoutUpper", "breakout_upper",
    "NoChase", "no_chase", "Invalidation", "InvalidationPrice",
    "FormalEntryTrigger", "EntryTrigger", "PositionHeld", "Held",
}


def _day(value):
    return date.fromisoformat(str(value or "")[:10])


def _ordinary_next_session(signal_date, trade_date):
    gap = (trade_date - signal_date).days
    if gap == 1 and signal_date.weekday() < 4 and trade_date.weekday() == signal_date.weekday() + 1:
        return
    if gap == 3 and signal_date.weekday() == 4 and trade_date.weekday() == 0:
        return
    raise ValueError("Q017_OFFICIAL_TRADING_CALENDAR_REQUIRED_FOR_SESSION_GAP")


def validate(q017):
    if q017 is None:
        return
    if not isinstance(q017, dict):
        raise ValueError("Q017_NOT_OBJECT")
    producer = q017.get("producer")
    if not isinstance(producer, dict):
        raise ValueError("Q017_PRODUCER_LINEAGE_MISSING")
    if producer.get("name") != VERIFIED_PRODUCER_NAME:
        raise ValueError("Q017_PRODUCER_NAME_NOT_VERIFIED")
    if producer.get("code_commit") != VERIFIED_PRODUCER_COMMIT:
        raise ValueError("Q017_PRODUCER_COMMIT_NOT_VERIFIED")
    evidence = producer.get("evidence")
    if not isinstance(evidence, dict) or evidence.get("frozen_validation_commit") != EXPECTED_EVIDENCE_COMMIT:
        raise ValueError("Q017_FROZEN_EVIDENCE_LINEAGE_MISMATCH")
    trade_date = _day(q017.get("trade_date"))
    signal_date = _day(q017.get("signal_date"))
    if signal_date >= trade_date:
        raise ValueError("Q017_SIGNAL_DATE_NOT_PRIOR")
    _ordinary_next_session(signal_date, trade_date)
    state = q017.get("market_state")
    rows = q017.get("candidates")
    if not isinstance(rows, list):
        raise ValueError("Q017_CANDIDATES_NOT_LIST")
    if state == "GO" and len(rows) != 1:
        raise ValueError("Q017_GO_REQUIRES_EXACT_TOP1")
    if state == "CASH" and rows:
        raise ValueError("Q017_CASH_WITH_CANDIDATES")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Q017_CANDIDATE_NOT_OBJECT")
        if row.get("signal_date") != q017.get("signal_date") or row.get("entry_trade_date") != q017.get("trade_date"):
            raise ValueError("Q017_CANDIDATE_SESSION_BINDING_MISMATCH")
        obs = row.get("beta_observations")
        if type(obs) is not int or not 30 <= obs <= 60:
            raise ValueError("Q017_BETA_OBSERVATIONS_OUT_OF_RANGE")
        beta = row.get("beta60")
        if isinstance(beta, bool) or not isinstance(beta, (int, float)) or not beta > 0:
            raise ValueError("Q017_BETA_NOT_POSITIVE")
        if any(key in row for key in AUTHORITY_KEYS):
            raise ValueError("Q017_CANDIDATE_CANNOT_CARRY_GEOMETRY_AUTHORITY")


def admit(adapter, q017):
    """Add reviewed trust without erasing explicit offline synthetic test trust."""
    existing = set(getattr(adapter, "VERIFIED_Q017_PRODUCERS", ()))
    adapter.VERIFIED_Q017_PRODUCERS = frozenset(existing | {VERIFIED_PRODUCER_COMMIT})
    if q017 is None:
        return None
    producer = q017.get("producer") if isinstance(q017, dict) else None
    if not isinstance(producer, dict) or producer.get("name") != VERIFIED_PRODUCER_NAME:
        return q017
    try:
        validate(q017)
        return q017
    except (ValueError, TypeError, OverflowError) as exc:
        return {"input_error": str(exc)}
