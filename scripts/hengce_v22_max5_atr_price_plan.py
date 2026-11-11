#!/usr/bin/env python3
"""Read-only V2.2 + MAX5 ATR price plan on HENGCE's EXISTING canonical EOD.

This is not a new selector, vendor collector, execution engine or broker.
A price is printed only after independently checking official original EOD
shards against their immutable SHA receipts AND the canonical mother receipt.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from hengce_twse_calendar import (
    _effective, _validate_base_manifest, validate_extraordinary_manifest,
    is_trading_day, next_trading_day,
)

TW = ZoneInfo("Asia/Taipei")
LOCK = "governance/HENGCE_V22_ATR_MAX5_PRICE_PLAN_RESEARCH_v1_20261111.json"
BASE_CAL = "governance/TWSE_TRADING_CALENDAR_2026_v1.json"
EXTRA_CAL = "governance/TWSE_EXTRAORDINARY_CLOSURES_2026_v1.json"
WEEKLY = "research/retail_top5/v22_weekly_latest.json"


class PriceEvidenceBlocked(ValueError):
    pass


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as e:
        raise PriceEvidenceBlocked("SOURCE_UNREADABLE:" + path.name) from e


def _calendar(root: Path):
    try:
        return _effective(
            _validate_base_manifest(_json(root / BASE_CAL)),
            validate_extraordinary_manifest(_json(root / EXTRA_CAL)))
    except (ValueError, OSError, KeyError, TypeError) as e:
        raise PriceEvidenceBlocked("EXISTING_TWSE_CALENDAR_UNVERIFIED") from e


def _sessions_ending(cal, end: date, count: int) -> list[date]:
    if end.year != 2026 or not is_trading_day(end, cal):
        raise PriceEvidenceBlocked("OFFICIAL_SESSION_NOT_VERIFIED")
    found = []
    day = end
    while day.year == 2026 and len(found) < count:
        if is_trading_day(day, cal):
            found.append(day)
        day -= timedelta(days=1)
    if len(found) != count:
        raise PriceEvidenceBlocked("NOT_ENOUGH_OFFICIAL_2026_SESSIONS")
    return list(reversed(found))


def _number(text: str, *, allow_missing: bool = False):
    value = str(text or "").strip().replace(",", "")
    if allow_missing and value == "--":
        return None
    try:
        x = float(value)
    except ValueError as e:
        raise PriceEvidenceBlocked("INVALID_OR_MISSING_OFFICIAL_OHLC") from e
    if not math.isfinite(x) or x <= 0:
        raise PriceEvidenceBlocked("INVALID_OR_MISSING_OFFICIAL_OHLC")
    return x


class OriginalPriceVessel:
    """Only reads old original EOD: no network, no second mother, no backfills."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.cache: dict[date, dict[str, dict | None]] = {}
        self.proofs: dict[date, str] = {}

    def day(self, d: date) -> dict[str, dict | None]:
        if d in self.cache:
            return self.cache[d]
        folder = self.root / "eod" / d.strftime("%Y%m%d")
        status = _json(folder / "status.json")
        mother = _json(folder / "receipts/mother.json")
        receipt = _json(folder / "receipts/price.json")
        if not (
            status.get("target_date") == d.isoformat()
            and status.get("status") == "COMPLETE"
            and status.get("three_leg_complete") is True
            and status.get("formal_complete_day") is True
            and status.get("downstream_ready") is True
            and status.get("mother_status") == "COMPLETE"
            and status.get("mother_receipt_status") == "PASS"
            and status.get("second_mother") is False
            and all(status.get(leg + "_status") == "COMPLETE" and
                    status.get(leg + "_date") == d.isoformat()
                    for leg in ("price", "institutional", "margin"))
            and mother.get("target_date") == d.isoformat()
            and mother.get("status") == "PASS"
            and mother.get("integrity_status") == "PASS"
            and mother.get("three_leg_complete") is True
            and mother.get("second_mother") is False
            and mother.get("mother_sha256") == status.get("mother_sha256")
            and mother.get("promoted_leg_sha256", {}).get("price") == status.get("price_sha256")
            and receipt.get("target_date") == d.isoformat()
            and receipt.get("leg") == "price"
            and receipt.get("status") == "COMPLETE"
            and receipt.get("sha256") == status.get("price_sha256")
        ):
            raise PriceEvidenceBlocked("ORIGINAL_EOD_CANONICAL_RECEIPT_UNVERIFIED:" + d.isoformat())
        filenames = receipt.get("files")
        expected = sorted("price_" + str(i) + ".csv" for i in range(1, 10))
        if not isinstance(filenames, list) or sorted(filenames) != expected:
            raise PriceEvidenceBlocked("ORIGINAL_EOD_SHARD_SET_UNVERIFIED:" + d.isoformat())
        shards = [folder / n for n in expected]
        h = hashlib.sha256()
        rows = {}
        count = 0
        for path in shards:
            try:
                blob = path.read_bytes()
                h.update(path.name.encode("utf-8"))
                h.update(b"\0")
                h.update(blob)
                h.update(b"\0")
                with path.open(encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    if not {"Date", "Ticker", "Open", "High", "Low", "Close"}.issubset(reader.fieldnames or []):
                        raise PriceEvidenceBlocked("ORIGINAL_EOD_OHLC_COLUMNS_MISSING")
                    for row in reader:
                        code = str(row.get("Ticker", "")).strip()
                        if (row.get("Date") != d.isoformat() or len(code) != 4
                            or not code.isdigit() or code.startswith("0") or code in rows):
                            raise PriceEvidenceBlocked("ORIGINAL_EOD_PRICE_ROW_INVALID")
                        values = {x: _number(row[x], allow_missing=True)
                                  for x in ("Open", "High", "Low", "Close")}
                        if all(v is None for v in values.values()):
                            rows[code] = None
                        elif any(v is None for v in values.values()):
                            raise PriceEvidenceBlocked("PARTIAL_OFFICIAL_OHLC_NOT_ALLOWED")
                        elif (values["High"] < max(values["Open"], values["Close"])
                              or values["Low"] > min(values["Open"], values["Close"])):
                            raise PriceEvidenceBlocked("OFFICIAL_OHLC_RANGE_INVALID")
                        else:
                            rows[code] = values
                        count += 1
            except OSError as e:
                raise PriceEvidenceBlocked("ORIGINAL_EOD_SHARD_UNREADABLE") from e
        digest = h.hexdigest()
        if (count < 900 or count != receipt.get("rows")
                or digest != receipt["sha256"]):
            raise PriceEvidenceBlocked("ORIGINAL_EOD_SHARD_HASH_OR_COUNT_MISMATCH:" + d.isoformat())
        self.proofs[d] = digest
        self.cache[d] = rows
        return rows

    def ticker_day(self, d: date, ticker: str) -> dict:
        row = self.day(d).get(ticker)
        if row is None:
            raise PriceEvidenceBlocked("OFFICIAL_OHLC_NOT_AVAILABLE:" + ticker + ":" + d.isoformat())
        return row

    def atr20(self, decision: date, ticker: str, cal) -> dict:
        days = _sessions_ending(cal, decision, 21)
        observations = [(d, self.ticker_day(d, ticker)) for d in days]
        tr = []
        for (_, prev), (_, today) in zip(observations, observations[1:]):
            tr.append(max(
                today["High"] - today["Low"],
                abs(today["High"] - prev["Close"]),
                abs(today["Low"] - prev["Close"])))
        atr = sum(tr) / 20
        if not math.isfinite(atr) or atr <= 0:
            raise PriceEvidenceBlocked("ATR20_NONPOSITIVE_OR_UNVERIFIED")
        return {
            "atr20": round(atr, 6),
            "method": "SMA20_OF_TRUE_RANGE",
            "observation_sessions": 21,
            "start_session": days[0].isoformat(),
            "through_session": days[-1].isoformat(),
            "official_close": observations[-1][1]["Close"],
            "verified_source_sha256": {d.isoformat(): self.proofs[d] for d in days},
            "corporate_action_adjustment_verified": False,
            "historical_gap_fill_used": False,
        }


def advance_atr_floor(fill: float, initial: float, prior: float, peak: float,
                      close: float, atr20_today: float, pending_exit=False) -> dict:
    if any(not math.isfinite(v) for v in (fill, initial, prior, peak, close, atr20_today)):
        raise PriceEvidenceBlocked("RISK_INPUT_NOT_FINITE")
    if min(fill, initial, prior, peak, close, atr20_today) <= 0:
        raise PriceEvidenceBlocked("RISK_INPUT_NOT_POSITIVE")
    peak = max(fill, peak, close)
    active = peak >= fill * 1.20
    trailing = peak - 4 * atr20_today if active else None
    floor = max(initial, prior, trailing if trailing is not None else initial)
    triggered = pending_exit or close <= floor
    return {
        "peak_close": round(peak, 6),
        "trail_active": active,
        "trailing_floor": round(trailing, 6) if trailing is not None else None,
        "effective_risk_floor": round(floor, 6),
        "exit_triggered": triggered,
        "exit_signal_new_today": not pending_exit and close <= floor,
    }


def _safe_float(value, name):
    try:
        x = float(value)
    except (TypeError, ValueError) as e:
        raise PriceEvidenceBlocked("INVALID_HOLDING_" + name) from e
    if not math.isfinite(x) or x <= 0:
        raise PriceEvidenceBlocked("INVALID_HOLDING_" + name)
    return x


def _holding_plan(holding: dict, asof: date, cal, vessel: OriginalPriceVessel) -> dict:
    code = str(holding.get("ticker", "")).strip()
    out = {"ticker": code, "status": "BLOCKED", "buy_price_source": "ACCOUNT_USER_SUPPLIED"}
    try:
        if len(code) != 4 or not code.isdigit() or code.startswith("0"):
            raise PriceEvidenceBlocked("HOLDING_TICKER_INVALID")
        entry = date.fromisoformat(str(holding["entry_date"]))
        fill = _safe_float(holding["entry_fill"], "FILL")
        qty = _safe_float(holding["quantity"], "QUANTITY")
        if entry > asof or entry.year != 2026 or asof.year != 2026:
            raise PriceEvidenceBlocked("HOLDING_ENTRY_OUTSIDE_VERIFIED_2026_RANGE")
        if not is_trading_day(entry, cal):
            raise PriceEvidenceBlocked("HOLDING_ENTRY_NOT_OFFICIAL_SESSION")
        prev = entry - timedelta(days=1)
        while prev.year == 2026 and not is_trading_day(prev, cal):
            prev -= timedelta(days=1)
        atr = vessel.atr20(prev, code, cal)
        initial = fill - 2 * atr["atr20"]
        if initial <= 0:
            raise PriceEvidenceBlocked("INITIAL_ATR_RISK_FLOOR_INVALID")
        peak = fill
        floor = initial
        pending = False
        first_trigger = None
        days = []
        d = entry
        while d <= asof:
            if is_trading_day(d, cal):
                days.append(d)
            d += timedelta(days=1)
        for d in days:
            c = vessel.ticker_day(d, code)["Close"]
            a = vessel.atr20(d, code, cal)["atr20"]
            step = advance_atr_floor(fill, initial, floor, peak, c, a, pending)
            peak = step["peak_close"]
            floor = step["effective_risk_floor"]
            if step["exit_signal_new_today"] and first_trigger is None:
                first_trigger = d.isoformat()
            pending = step["exit_triggered"]
        # Never lower a previously recorded floor from the account worklist.
        if holding.get("risk_floor") not in (None, ""):
            manual = _safe_float(holding["risk_floor"], "CARRIED_RISK_FLOOR")
            floor = max(floor, manual)
            pending = pending or c <= floor
        out.update(status=("EXIT_PENDING_ACCOUNT_RECONCILIATION" if pending
                           else "ATR_RISK_WATCH_RESEARCH_ONLY"),
                   entry_date=entry.isoformat(), entry_fill=fill, shares=qty,
                   initial_atr20=atr["atr20"], initial_risk_floor=round(initial, 6),
                   effective_risk_floor=round(floor, 6), peak_close=round(peak, 6),
                   last_verified_close=c, last_verified_eod_date=days[-1].isoformat(),
                   first_exit_trigger_date=first_trigger,
                   next_exit_pricing="NEXT_ACTUAL_TRADABLE_OPEN_UNKNOWN_IN_ADVANCE",
                   no_account_execution_confirmation=True)
    except (KeyError, ValueError, PriceEvidenceBlocked) as e:
        out["block_reason"] = str(e)
    return out


def build_price_plan(asof: datetime | None = None, root: Path | None = None,
                     verified_v22: dict | None = None,
                     holdings: list[dict] | None = None) -> dict:
    """Post-filter-only: source Top5 from existing original scan reader."""
    asof = asof or datetime.now(TW)
    asof = (asof if asof.tzinfo else asof.replace(tzinfo=TW)).astimezone(TW)
    root = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    out = {
        "schema": "HENGCE_V22_MAX5_ATR_PRICE_PLAN_RESEARCH_V1",
        "model": "HENGCE_SELECTION_MODEL_V2_2_TOP5",
        "role": "READ_ONLY_ENTRY_AND_EXIT_PRICE_RESEARCH",
        "as_of_taipei": asof.isoformat(),
        "status": "BLOCKED_UNVERIFIED_PRICE_POLICY",
        "v22_selection_unchanged": True,
        "selection_is_not_executed_here": True,
        "no_new_data_vessel": True,
        "max_positions": 5, "max_new_entries_per_week": 1,
        "capital_unlimited_research_only": True,
        "reference_close_is_not_buy_price": True,
        "next_open_price_known_in_advance": False,
        "buy_signal": False, "sell_signal": False,
        "formal_selection_authority": False,
        "broker_execution": False, "capital_authority_twd": 0,
        "candidate_price_plans": [], "existing_position_risk": [],
        "portfolio_input_status": "NOT_PROVIDED",
    }
    try:
        spec = _json(root / LOCK)
        safety = spec.get("safety", {})
        if not (spec.get("schema") == "HENGCE_V22_ATR_MAX5_PRICE_RESEARCH_V1"
                and spec.get("model") == out["model"]
                and isinstance(spec.get("no_complete_data_behavior"), str)
                and spec["no_complete_data_behavior"].startswith("BLOCK_")
                and isinstance(safety, dict)
                and all(safety.get(k) is False for k in
                        ("broker_execution", "formal_selection_authority",
                         "buy_signal", "sell_signal", "capital_authority_twd"))
                and all(safety.get(k) is True for k in
                        ("no_new_market_data_vessels", "no_second_mother",
                         "no_synthetic_ATR",
                         "cannot_use_unverified_retrospective_weekly_top5_for_current_entry",
                         "needs_21_consecutive_official_OHLC_sessions"))):
            raise PriceEvidenceBlocked("MAX5_PRICE_POLICY_UNVERIFIED")
        out["policy_version"] = spec["schema"]
        cal = _calendar(root)
        vessel = OriginalPriceVessel(root)
    except PriceEvidenceBlocked as e:
        out["reason"] = str(e)
        return out
    # Account positions are NEVER read from a simulated historical trading ledger.
    if holdings is not None:
        if not isinstance(holdings, list):
            out["portfolio_input_status"] = "INVALID_HOLDINGS_INPUT"
            out["status"] = "BLOCKED_HOLDING_INPUT"
            return out
        keys = [str(h.get("ticker", "")).strip() for h in holdings if isinstance(h, dict)]
        if len(keys) != len(holdings) or len(keys) > 5 or len(set(keys)) != len(keys):
            out["portfolio_input_status"] = "MAX5_OR_DUPLICATE_HOLDINGS_VIOLATION"
            out["status"] = "BLOCKED_HOLDING_INPUT"
            return out
        out["portfolio_input_status"] = "USER_SUPPLIED_NOT_BROKER_VERIFIED"
        out["existing_position_risk"] = [
            _holding_plan(h, asof.date(), cal, vessel) for h in holdings]
    if verified_v22 is None:
        out["status"] = "WAITING_EXISTING_VERIFIED_V22_WEEKLY_READER"
        out["reason"] = "No weekly receipt passed to this price layer; no independent ranking."
        return out
    if (not isinstance(verified_v22, dict)
        or verified_v22.get("status") != "WEEKLY_RESEARCH_TOP5_READY"
        or verified_v22.get("formal_selection_authority") is not False
        or verified_v22.get("broker_execution") is not False
        or verified_v22.get("buy_signal") is not False
        or verified_v22.get("source_kind") != "HENGCE_ORIGINAL_EOD_TDCC_RESEARCH_ONLY"):
        out["status"] = "WAITING_VERIFIED_WEEKLY_V22_TOP5"
        out["reason"] = "Historical or unverified V2.2 Top5 may NOT be upgraded to current entry prices."
        return out
    try:
        decision = date.fromisoformat(verified_v22["source_date"])
        target = date.fromisoformat(next_trading_day(decision, cal))
        if decision > asof.date() or decision.weekday() != 4:
            raise PriceEvidenceBlocked("WEEKLY_DECISION_DATE_INVALID")
        top = verified_v22["top5"]
        if not isinstance(top, list) or len(top) > 5:
            raise PriceEvidenceBlocked("WEEKLY_TOP5_STRUCTURE_INVALID")
    except (KeyError, ValueError, PriceEvidenceBlocked) as e:
        out["status"] = "BLOCKED_WEEKLY_DECISION_UNVERIFIED"
        out["reason"] = str(e)
        return out
    out["decision_date"] = decision.isoformat()
    out["planned_next_session"] = target.isoformat()
    out["candidate_count"] = len(top)
    for item in top:
        code = str(item.get("ticker", "")).strip() if isinstance(item, dict) else ""
        row = {
            "ticker": code, "status": "BLOCKED_ATR_EVIDENCE",
            "entry_rule": "NEXT_OFFICIAL_MARKET_OPEN_IF_POSITION_CAPACITY_CONFIRMED",
            "buy_price_known": False,
            "sell_price_known": False,
        }
        try:
            if len(code) != 4 or not code.isdigit() or code.startswith("0"):
                raise PriceEvidenceBlocked("CANDIDATE_TICKER_INVALID")
            atr = vessel.atr20(decision, code, cal)
            row.update({
                "decision_date": decision.isoformat(),
                "reference_close": atr["official_close"],
                "signal_atr20": atr["atr20"],
                "atr_method": atr["method"],
                "atr_window_start": atr["start_session"],
                "atr_window_end": atr["through_session"],
                "initial_risk_floor_formula": "ACTUAL_FILL_PRICE_MINUS_2_TIMES_SIGNAL_ATR20",
                "trail_activation_formula": "PEAK_CLOSE_AT_LEAST_120_PERCENT_OF_FILL",
                "trail_floor_formula": "MAX_PREVIOUS_RISK_FLOOR_AND_PEAK_CLOSE_MINUS_4_TIMES_DAILY_ATR20",
                "fixed_take_profit": None,
                "atr_input_corporate_actions_not_independently_certified": True,
            })
            if target > asof.date():
                row["status"] = "ATR_READY_WAITING_NEXT_OPEN_AND_ACCOUNT_CAPACITY"
            else:
                official_open = vessel.ticker_day(target, code)["Open"]
                floor = official_open - 2 * atr["atr20"]
                if floor <= 0:
                    raise PriceEvidenceBlocked("OFFICIAL_OPEN_ATR_INITIAL_FLOOR_NONPOSITIVE")
                row.update(
                    research_observed_next_open=official_open,
                    observed_next_open_date=target.isoformat(),
                    research_initial_floor_from_observed_open=round(floor, 6),
                    research_buy_fill_not_verified=True,
                    status=("HISTORICAL_NEXT_OPEN_REFERENCE_NOT_CURRENT_BUY"
                            if target < asof.date()
                            else "OFFICIAL_OPEN_RESEARCH_REFERENCE_NOT_BROKER_FILL"),
                )
        except (PriceEvidenceBlocked, ValueError) as e:
            row["block_reason"] = str(e)
        out["candidate_price_plans"].append(row)
    # Never issue five simultaneous buy recommendations from the Top5 list.
    # A single weekly entry candidate can be determined only with a supplied,
    # structurally valid actual holdings list; exits do not release capacity
    # until the user confirms them in the subsequent account snapshot.
    selected_code = None
    if holdings is None:
        capacity = "ACTUAL_ACCOUNT_HOLDINGS_REQUIRED"
    elif len(holdings) >= 5:
        capacity = "MAX5_FULL_NO_NEW_ENTRY"
    else:
        held_codes = {str(h["ticker"]).strip() for h in holdings}
        eligible = [r for r in out["candidate_price_plans"]
                    if r["ticker"] not in held_codes
                    and r["status"] != "BLOCKED_ATR_EVIDENCE"]
        if eligible:
            selected_code = eligible[0]["ticker"]
            capacity = "ONE_WEEKLY_RESEARCH_ENTRY_SLOT_AVAILABLE"
        else:
            capacity = "NO_VERIFIED_ELIGIBLE_RESEARCH_ENTRY"
    out["entry_capacity_status"] = capacity
    out["one_research_entry_candidate"] = selected_code
    for row in out["candidate_price_plans"]:
        row["within_one_weekly_entry_limit"] = row["ticker"] == selected_code
        row["account_order_approval_required"] = True
    if not top:
        out["status"] = "VERIFIED_V22_NO_QUALIFIED_CANDIDATES"
    elif all(r["status"] == "BLOCKED_ATR_EVIDENCE" for r in out["candidate_price_plans"]):
        out["status"] = "BLOCKED_MISSING_VERIFIED_ATR_EOD"
    elif any(r["status"] == "BLOCKED_ATR_EVIDENCE" for r in out["candidate_price_plans"]):
        out["status"] = "PARTIAL_PRICE_EVIDENCE_NO_TRADE_AUTHORITY"
    else:
        out["status"] = "ATR_PRICE_RESEARCH_READY_NO_TRADE_AUTHORITY"
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asof", help="Asia/Taipei ISO timestamp")
    parser.add_argument("--holdings", help="CSV with ticker,entry_date,entry_fill,quantity")
    parser.add_argument("--output", help="write derived research JSON only")
    args = parser.parse_args()
    now = datetime.fromisoformat(args.asof) if args.asof else datetime.now(TW)
    try:
        from hengce_scan_once_router import research_top5_observation
        selection = research_top5_observation(now)
        holdings = None
        if args.holdings:
            with open(args.holdings, encoding="utf-8-sig", newline="") as f:
                holdings = list(csv.DictReader(f))
        result = build_price_plan(now, verified_v22=selection, holdings=holdings)
        payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            target = Path(args.output)
            if (target.resolve().is_relative_to(Path(__file__).resolve().parents[1] / "eod")
                or target.resolve().is_relative_to(Path(__file__).resolve().parents[1] / "ownership")):
                raise PriceEvidenceBlocked("MAY_NOT_WRITE_EXISTING_ORIGINAL_VESSEL")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(payload, encoding="utf-8")
        else:
            print(payload, end="")
    except (OSError, ValueError, PriceEvidenceBlocked) as e:
        print(json.dumps({"status": "BLOCKED", "reason": str(e)}, ensure_ascii=False))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
