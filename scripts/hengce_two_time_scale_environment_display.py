#!/usr/bin/env python3
"""HENGCE two-time-scale display projection; NO new classifiers or trading authority.

Purpose:
  TODAY_MARKET_ENVIRONMENT: overseas SOX/VIX preopen model only.
  LONG_TERM_CAPITAL_ENVIRONMENT: independent formally verified capital evidence.

A FinMind tick snapshot is NOT proof of capital accumulation or foreign remittance.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any

TODAY_LABELS = {
    1: "強烈偏空",
    2: "偏空",
    3: "中性",
    4: "偏多",
    5: "強烈偏多",
}
CAPITAL_LABELS = {
    "ACCUMULATION_CONFIRMED": "持續累積",
    "INTERNAL_ROTATION_CONFIRMED": "資金輪動",
    "WITHDRAWAL_CONFIRMED": "資金撤退",
    "RECOVERY_CONFIRMED": "恢復中",
}
UNKNOWN = "資料不足"
FORMAL_CAPITAL_SCHEMA = "HENGCE_CANONICAL_CAPITAL_ENVIRONMENT_DISPLAY_V1"
EXPECTED_WINDOWS = (20, 60, 120)
_SHA = re.compile(r"^[a-f0-9]{64}$")


def _finite_number(x: Any) -> bool:
    import math
    return type(x) in (float, int) and math.isfinite(x)


def _valid_formal_capital(packet: dict[str, Any], source_day: str) -> bool:
    """Validate a future governed canonical display receipt, never synthesize a state."""
    if not isinstance(packet, dict):
        return False
    if packet.get("schema") != FORMAL_CAPITAL_SCHEMA:
        return False
    if (packet.get("status"), packet.get("source_authority"), packet.get("canonical_integrity")) != (
        "PASS", "HENGCE_CANONICAL_EOD_VERIFIED", "PASS"
    ):
        return False
    if packet.get("formal_daily_close_ready") is not True:
        return False
    if packet.get("source_trade_date") != source_day:
        return False
    if packet.get("long_term_capital_state") not in CAPITAL_LABELS:
        return False
    if packet.get("trading_authority") is not False:
        return False
    windows = packet.get("evidence_windows_trading_days")
    if type(windows) is not list or sorted(windows) != list(EXPECTED_WINDOWS):
        return False
    if not isinstance(packet.get("supporting_flow_evidence"), list) or len(packet["supporting_flow_evidence"]) < 1:
        return False
    sha = packet.get("canonical_receipt_sha256")
    if type(sha) is not str or not _SHA.fullmatch(sha) or sha == "0" * 64:
        return False
    try:
        d = dt.date.fromisoformat(source_day)
        d2 = dt.date.fromisoformat(packet.get("source_trade_date", ""))
        if d2 != d:
            return False
    except (ValueError, TypeError):
        return False
    return True


def build_display(
    prediction: dict[str, Any],
    target_tw_date: str,
    reference_tw_date: str,
    formal_capital: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return two independent display conclusions with explicit unknown states.

    Accept overseas grades only as exploratory premarket observation: the
    existing bridge validates chronology/schema, not vendor price authenticity.
    Formal capital remains UNKNOWN until separately governed canonical receipt.
    """
    today: dict[str, Any] = {
        "title": "今日市場環境",
        "label": UNKNOWN,
        "allowed_labels": list(reversed(list(TODAY_LABELS.values()))),
        "status": "UNVERIFIED",
        "source_scope": "SOX_VIX_PREMARKET",
        "grade": None,
        "meaning": "僅反映隔夜海外市場對台股開盤的預報，不代表中長期資金轉向",
    }
    if (isinstance(prediction, dict)
        and prediction.get("status") == "VERIFIED_GOVERNED_OVERSEAS_SOX_VIX"
        and prediction.get("vendor_price_integrity") is True
        and type(prediction.get("source_receipt_sha256")) is str
        and _SHA.fullmatch(prediction["source_receipt_sha256"]) is not None
        and type(prediction.get("grade")) is int
        and prediction["grade"] in TODAY_LABELS
        and _finite_number(prediction.get("expected_gap_log_pct"))):
        today.update(
            label=TODAY_LABELS[prediction["grade"]],
            status="GOVERNED_OVERSEAS_VERIFIED_RESEARCH_ONLY",
            grade=prediction["grade"],
            expected_open_gap_log_pct=prediction["expected_gap_log_pct"],
            caution="已宣告海外資料與時戳經治理血管查驗；仍只作研究環境顯示，無交易授權",
        )

    if (isinstance(prediction, dict) and
        prediction.get("status") == "PIT_SCHEMA_VERIFIED_UPSTREAM"):
        today["status"] = "OVERSEAS_PACKET_SCHEMA_ONLY_NOT_SOURCE_VERIFIED"
    capital: dict[str, Any] = {
        "title": "長期資金環境",
        "label": UNKNOWN,
        "allowed_labels": [*CAPITAL_LABELS.values(), UNKNOWN],
        "status": "NO_GOVERNED_CANONICAL_CAPITAL_RECEIPT",
        "source_scope": "CANONICAL_20_60_120D_FLOWS",
        "meaning": "依已驗證的中長期資金證據判斷；不可用 FinMind 即時漲跌代替",
    }
    if formal_capital is not None:
        if _valid_formal_capital(formal_capital, reference_tw_date):
            state = formal_capital["long_term_capital_state"]
            capital.update(
                label=CAPITAL_LABELS[state],
                status="CANONICAL_DISPLAY_RECEIPT_DECLARED_PASS",
                formal_state=state,
                source_trade_date=reference_tw_date,
                evidence_windows_trading_days=list(EXPECTED_WINDOWS),
                canonical_receipt_sha256=formal_capital["canonical_receipt_sha256"],
                caution="只核對傳入的正式憑證欄位；仍須由既有 canonical 血管查證來源雜湊。非選股或交易授權",
            )
        else:
            capital["status"] = "REJECTED_UNVERIFIED_CAPITAL_RECEIPT"

    return {
        "schema": "HENGCE_TWO_TIME_SCALE_ENVIRONMENT_DISPLAY_V1",
        "target_tw_date": target_tw_date,
        "today_market_environment": today,
        "long_term_capital_environment": capital,
        "decision_policy": {
            "independent_axes": True,
            "no_composite_bullish_score": True,
            "one_day_overseas_rebound_may_not_reset_capital_withdrawal": True,
            "one_day_taiwan_decline_may_not_create_capital_withdrawal": True,
            "missing_input_is_neutral": False,
            "formal_selection_effect": "NONE",
            "formal_escape_effect": "NONE",
            "trading_authority": "NONE",
        },
    }
