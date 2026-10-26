#!/usr/bin/env python3
"""Q017 execution-only structural exit overlay.

Frozen Q017 signal/holding research rules are untouched. This module only
classifies already-held Q017/BOTH positions for the live action board.

State machine (no percentage/ATR/time threshold):
  Lower High + first touch/break of intervening Swing Low -> WARNING only.
  Reclaim the broken level, then break it again               -> EXIT_ALL.
  Fail to reclaim, form a confirmed rebound high below level,
  then break the repair reaction low                           -> EXIT_ALL.

Pivots are strict 1-bar pivots and are causal: a pivot at t is usable only
after t+1 has completed.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from hengce_unified_contracts import ticker as _ticker

HISTORY_PATH = Path(__file__).resolve().parents[1] / "hengce/q017_radar/data/twse_electronics_history_2026.csv"


def _truthy(row: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        if key not in row:
            continue
        value = row.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False


def _num(value: Any) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _entry_date(row: dict[str, Any]) -> str | None:
    for key in ("PositionEntryDate", "position_entry_date", "EntryDate", "entry_date", "FilledAtDate", "filled_at_date"):
        value = row.get(key)
        if value:
            return str(value)[:10]
    return None


def _load_bars(ticker: str, trade_date: str | None, history_path: Path = HISTORY_PATH) -> list[dict[str, Any]]:
    if not trade_date or not history_path.is_file():
        return []
    bars: list[dict[str, Any]] = []
    try:
        with history_path.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                if str(row.get("Ticker", "")).strip() != str(ticker):
                    continue
                day = str(row.get("Date", ""))
                if not day or day >= trade_date:
                    continue
                o, h, l, c = (_num(row.get(k)) for k in ("Open", "High", "Low", "Close"))
                if None in (o, h, l, c):
                    continue
                bars.append({"date": day, "open": o, "high": h, "low": l, "close": c})
    except (OSError, csv.Error):
        return []
    bars.sort(key=lambda x: x["date"])
    return bars


def _pivots(bars: list[dict[str, Any]]) -> tuple[list[int], list[int]]:
    highs: list[int] = []
    lows: list[int] = []
    for i in range(1, len(bars) - 1):
        if bars[i]["high"] > bars[i - 1]["high"] and bars[i]["high"] > bars[i + 1]["high"]:
            highs.append(i)
        if bars[i]["low"] < bars[i - 1]["low"] and bars[i]["low"] < bars[i + 1]["low"]:
            lows.append(i)
    return highs, lows


def _latest_setup(bars: list[dict[str, Any]], entry_date: str | None) -> dict[str, Any] | None:
    highs, lows = _pivots(bars)
    if len(highs) < 2:
        return None
    setups: list[dict[str, Any]] = []
    for n in range(1, len(highs)):
        h1, h2 = highs[n - 1], highs[n]
        if bars[h2]["high"] >= bars[h1]["high"]:
            continue
        between = [i for i in lows if h1 < i < h2]
        if not between:
            continue
        sl = between[-1]
        # h2 is confirmed at h2+1 close; first actionable completed bar is h2+2.
        activation_index = h2 + 2
        activation_date = bars[activation_index]["date"] if activation_index < len(bars) else None
        if entry_date and activation_date and activation_date < entry_date:
            continue
        setups.append({
            "prev_high": bars[h1]["high"],
            "prev_high_date": bars[h1]["date"],
            "lower_high": bars[h2]["high"],
            "lower_high_date": bars[h2]["date"],
            "break_level": bars[sl]["low"],
            "swing_low_date": bars[sl]["date"],
            "activation_index": activation_index,
            "activation_date": activation_date,
        })
    return setups[-1] if setups else None


def classify(src: dict[str, Any], live_row: dict[str, Any], trade_date: str | None,
             history_path: Path = HISTORY_PATH) -> dict[str, Any] | None:
    provenance = str(src.get("SourceProvenance") or "").upper()
    held = _truthy(src, "PositionHeld", "position_held", "Held", "held")
    if provenance not in {"Q017", "BOTH"} or not held:
        return None
    ticker = _ticker(src)
    if not ticker:
        return None

    bars = _load_bars(ticker, trade_date, history_path=history_path)
    if len(bars) < 5:
        return None
    setup = _latest_setup(bars, _entry_date(src))
    if not setup:
        return None

    level = float(setup["break_level"])
    start = int(setup["activation_index"])
    live_price = _num(live_row.get("price") or live_row.get("last") or live_row.get("last_price"))
    live_low = _num(live_row.get("low") or live_row.get("day_low"))
    live_touch = (live_low is not None and live_low <= level) or (live_price is not None and live_price <= level)

    break_idx = next((i for i in range(start, len(bars)) if bars[i]["low"] <= level), None)
    event: dict[str, Any] = {
        **setup,
        "state": "STRUCTURE_CLEAR",
        "alert_required": False,
        "alert_level": None,
        "alert_key": None,
        "first_break_date": bars[break_idx]["date"] if break_idx is not None else None,
        "reclaim_date": None,
        "reaction_low": None,
        "reaction_low_date": None,
    }

    # First touch/break is deliberately NOT an exit.
    if break_idx is None:
        if live_touch:
            event.update(
                state="STRUCTURE_WARNING",
                alert_required=True,
                alert_level="WARNING",
                alert_key=f"STRUCTURE_WARNING:{ticker}:{level:g}:{trade_date or 'LIVE'}",
                first_break_date=trade_date,
            )
        return event

    # Repair is only accepted after a completed close back above the broken level.
    reclaim_idx = next((i for i in range(break_idx + 1, len(bars)) if bars[i]["close"] > level), None)
    if reclaim_idx is not None:
        event["reclaim_date"] = bars[reclaim_idx]["date"]
        rebreak_idx = next((i for i in range(reclaim_idx + 1, len(bars)) if bars[i]["low"] <= level), None)
        if rebreak_idx is not None or live_touch:
            exit_date = bars[rebreak_idx]["date"] if rebreak_idx is not None else trade_date
            event.update(
                state="STRUCTURE_EXIT_REBREAK",
                alert_required=True,
                alert_level="EXIT",
                alert_key=f"STRUCTURE_EXIT_REBREAK:{ticker}:{level:g}:{exit_date}",
            )
        else:
            event["state"] = "STRUCTURE_RECLAIMED"
        return event

    # No reclaim: wait for a confirmed rebound high below the broken level.
    highs, _ = _pivots(bars)
    failed_high = next((i for i in highs if i > break_idx and bars[i]["high"] < level), None)
    if failed_high is None:
        event.update(
            state="STRUCTURE_REPAIR_PENDING",
            alert_required=True,
            alert_level="WARNING",
            alert_key=f"STRUCTURE_WARNING:{ticker}:{level:g}:{event['first_break_date']}",
        )
        return event

    reaction_idx = min(range(break_idx, failed_high + 1), key=lambda i: bars[i]["low"])
    reaction_low = bars[reaction_idx]["low"]
    event["reaction_low"] = reaction_low
    event["reaction_low_date"] = bars[reaction_idx]["date"]

    # failed_high is confirmed at failed_high+1 close; act from failed_high+2 onward.
    after_confirm = failed_high + 2
    failed_idx = next((i for i in range(after_confirm, len(bars)) if bars[i]["low"] < reaction_low), None)
    live_failed = live_low is not None and live_low < reaction_low
    if failed_idx is not None or live_failed:
        exit_date = bars[failed_idx]["date"] if failed_idx is not None else trade_date
        event.update(
            state="STRUCTURE_EXIT_FAILED_RECLAIM",
            alert_required=True,
            alert_level="EXIT",
            alert_key=f"STRUCTURE_EXIT_FAILED_RECLAIM:{ticker}:{reaction_low:g}:{exit_date}",
        )
    else:
        event.update(
            state="STRUCTURE_REPAIR_PENDING",
            alert_required=True,
            alert_level="WARNING",
            alert_key=f"STRUCTURE_WARNING:{ticker}:{level:g}:{event['first_break_date']}",
        )
    return event


def apply(row: dict[str, Any], event: dict[str, Any] | None, binding_ok: bool) -> None:
    if not event:
        return
    row.update({
        "StructureExitOverlay": "Q017_FAILED_RECLAIM_V1",
        "StructureExitState": event["state"],
        "StructurePrevHigh": event.get("prev_high"),
        "StructurePrevHighDate": event.get("prev_high_date"),
        "StructureLowerHigh": event.get("lower_high"),
        "StructureLowerHighDate": event.get("lower_high_date"),
        "StructureBreakLevel": event.get("break_level"),
        "StructureSwingLowDate": event.get("swing_low_date"),
        "StructureFirstBreakDate": event.get("first_break_date"),
        "StructureReclaimDate": event.get("reclaim_date"),
        "StructureReactionLow": event.get("reaction_low"),
        "StructureReactionLowDate": event.get("reaction_low_date"),
        "AlertRequired": bool(event.get("alert_required")),
        "AlertLevel": event.get("alert_level"),
        "AlertKey": event.get("alert_key"),
    })
    if not binding_ok:
        return
    state = event["state"]
    if state in {"STRUCTURE_EXIT_REBREAK", "STRUCTURE_EXIT_FAILED_RECLAIM"}:
        row.update(
            PriceProof=state,
            IntradayActivationState="EXIT_TRIGGERED_STRUCTURE_REPAIR_FAILURE",
            ExecutionEligibility="EXIT_ALLOWED",
            FinalAction="EXIT_ALL",
        )
    elif state in {"STRUCTURE_WARNING", "STRUCTURE_REPAIR_PENDING"} and row.get("FinalAction") != "EXIT_ALL":
        row.update(
            IntradayActivationState=state,
            ExecutionEligibility="HOLD_STRUCTURE_REPAIR_PENDING",
            FinalAction="HOLD",
        )
