#!/usr/bin/env python3
"""Read-only V2.2 Top5 research quote overlay over EXISTING HENGCE transports.

Does not fetch market data, rebuild a universe, rerank Top5, promote intraday
prices to formal EOD, infer per-security FinMind values, or grant order authority.
Unknown, stale, trial-only and missing quotes are explicit rather than zero-filled.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TW = ZoneInfo("Asia/Taipei")
TICKER = re.compile(r"[1-9]\d{3}\Z")
V22 = "hengce_selection_v2_2"
NO_AUTH = "NO_TRADING_AUTHORITY"

SOURCES = (
    ("FROZEN_SINGLE_NAME", "legacy_live/frozen_single_name_status.json", None,
     "QUOTE_TRANSPORT_ONLY_NO_RANKING_SIGNAL_CAPITAL_AUTHORITY"),
    ("ELECTRONICS_100", "legacy_live/status.json", "legacy_live/active.json",
     "INTRADAY_QUOTE_TRANSPORT_ONLY_NO_MODEL_RANKING_AUTHORITY"),
    ("LEGACY_77", "live/status.json", "live/active.json",
     "QUOTE_TRANSPORT_ONLY_NO_RANKING_SIGNAL_CAPITAL_AUTHORITY"),
)


class EvidenceBlocked(ValueError):
    pass


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None


def timestamp(value):
    try:
        result = datetime.fromisoformat(str(value))
        if result.tzinfo is None:
            return None
        return result.astimezone(TW)
    except (TypeError, ValueError):
        return None


def number(value, *, positive=False):
    if isinstance(value, bool) or value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out) or (positive and out <= 0):
        return None
    return out


def _verified_original_vessel_weekly_receipt(root, selection, asof):
    """Consume existing HENGCE weekly research output through the original scan reader.

    Does not create a source or model. The weekly research report must exist
    at its canonical derived path and pass the unchanged scan-once validator.
    """
    if root is None or asof is None or asof.tzinfo is None:
        raise EvidenceBlocked("WEEKLY_RESEARCH_SOURCE_AND_ASOF_REQUIRED")
    committed = read_json(Path(root) / "research/retail_top5/v22_weekly_latest.json")
    if not isinstance(committed, dict) or committed != selection:
        raise EvidenceBlocked("WEEKLY_RESEARCH_NOT_COMMITTED_OR_MISMATCHED")
    path = Path(root) / "scripts" / "hengce_scan_once_router.py"
    if not path.is_file():
        raise EvidenceBlocked("HENGCE_ORIGINAL_SCAN_READER_UNAVAILABLE")
    spec = importlib.util.spec_from_file_location("hengce_scan_reader_for_v22_quote", path)
    if spec is None or spec.loader is None:
        raise EvidenceBlocked("HENGCE_SCAN_READER_UNLOADABLE")
    reader = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(reader)
        verified = reader.weekly_v22_research_observation(asof, root)
    except (OSError, TypeError, ValueError, AttributeError, KeyError) as exc:
        raise EvidenceBlocked("WEEKLY_RESEARCH_SCAN_READER_FAILED") from exc
    if (not isinstance(verified, dict)
        or verified.get("status") not in ("WEEKLY_RESEARCH_TOP5_READY",
                                          "STALE_WEEKLY_RESEARCH_TOP5")
        or verified.get("source_date") != selection.get("decision_date")
        or verified.get("research_only") is not True
        or verified.get("broker_execution") is not False
        or verified.get("authorized_lots") != 0):
        raise EvidenceBlocked("WEEKLY_RESEARCH_SELECTION_NOT_VERIFIED")
    rows = verified.get("top5")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 5:
        raise EvidenceBlocked("WEEKLY_RESEARCH_HAS_NO_QUALIFIED_TOP5")
    if any(not isinstance(r, dict) or r.get("rank") != i
           or r.get("authorized_lots") != 0
           for i, r in enumerate(rows, 1)):
        raise EvidenceBlocked("WEEKLY_TOP5_MEMBERSHIP_INVALID")
    return date.fromisoformat(selection["decision_date"]), rows


def valid_candidate_receipt(selection, *, root=None, asof=None):
    if not isinstance(selection, dict):
        raise EvidenceBlocked("V22_RECEIPT_MISSING")
    if selection.get("schema") == "HENGCE_V22_WEEKLY_RESEARCH_SCREEN_V1":
        return _verified_original_vessel_weekly_receipt(root, selection, asof)
    if (selection.get("version") != V22 or
        selection.get("mode") != "research_selection" or
        selection.get("authority") != NO_AUTH or
        selection.get("official_source_verified") is not False or
        selection.get("verification_scope") != "BUNDLED_REFERENCE_ONLY" or
        selection.get("selected_count") != len(selection.get("candidates") or [])):
        raise EvidenceBlocked("V22_RESEARCH_RECEIPT_CONTRACT_MISMATCH")
    try:
        decision = date.fromisoformat(selection["decision"])
    except (KeyError, TypeError, ValueError):
        raise EvidenceBlocked("V22_DECISION_DATE_INVALID") from None
    if decision.weekday() != 4:
        raise EvidenceBlocked("V22_DECISION_MUST_BE_FRIDAY")
    rows = selection.get("candidates")
    if not isinstance(rows, list) or len(rows) > 5 or not rows:
        raise EvidenceBlocked("V22_TOP5_ROWS_INVALID")
    seen = set()
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict) or row.get("rank") != i:
            raise EvidenceBlocked("V22_RANK_SEQUENCE_INVALID")
        ticker = row.get("ticker")
        if not isinstance(ticker, str) or not TICKER.fullmatch(ticker) or ticker in seen:
            raise EvidenceBlocked("V22_TICKER_DUPLICATED_OR_INVALID")
        seen.add(ticker)
    return decision, rows


def existing_quote_sources(root: Path):
    """Only consume immutable-on-read, existing HENGCE transport JSON artifacts."""
    results = []
    for name, status_path, active_path, expected_role in SOURCES:
        status = read_json(root / status_path)
        source = {"source": name, "status": "ABSENT_OR_INVALID", "entries": {},
                  "generated_at_taipei": None, "cache_expires_at_taipei": None}
        if not isinstance(status, dict):
            results.append(source)
            continue
        actual_role = status.get("authority") if name != "LEGACY_77" else status.get("transport_role")
        if actual_role != expected_role or status.get("broker_order_execution") not in (False, None):
            source["status"] = "AUTHORITY_MISMATCH"
            results.append(source)
            continue
        source.update(generated_at_taipei=status.get("generated_at_taipei"),
                      cache_expires_at_taipei=status.get("cache_expires_at_taipei"),
                      market_phase=status.get("market_phase"),
                      snapshot_id=status.get("snapshot_id"))
        if not (timestamp(source["generated_at_taipei"]) and
                timestamp(source["cache_expires_at_taipei"])):
            source["status"] = "TIMESTAMP_UNVERIFIED"
            results.append(source)
            continue
        if name == "FROZEN_SINGLE_NAME":
            symbols = status.get("symbols")
            if (not isinstance(symbols, list) or
                status.get("requested_count") != len(symbols) or
                len(symbols) != len(set(symbols)) or
                any(not isinstance(s, str) or not TICKER.fullmatch(s) for s in symbols)):
                source["status"] = "FROZEN_UNIVERSE_INVALID"
                results.append(source)
                continue
            for symbol in symbols:
                row = read_json(root / "legacy_live" / "quotes" / (symbol + ".json"))
                if (isinstance(row, dict) and row.get("snapshot_id") == status.get("snapshot_id")
                    and row.get("symbol") == symbol):
                    source["entries"][symbol] = row
        else:
            data = read_json(root / active_path)
            if (not isinstance(data, dict) or data.get("snapshot_id") != status.get("snapshot_id")
                or data.get("requested_count") != status.get("requested_count")
                or not isinstance(data.get("data"), list)):
                source["status"] = "SNAPSHOT_MISMATCH"
                results.append(source)
                continue
            for row in data["data"]:
                if not isinstance(row, dict):
                    source["status"] = "ROW_INVALID"
                    source["entries"].clear()
                    break
                symbol = row.get("symbol")
                if not isinstance(symbol, str) or not TICKER.fullmatch(symbol) or symbol in source["entries"]:
                    source["status"] = "ROW_KEY_INVALID"
                    source["entries"].clear()
                    break
                source["entries"][symbol] = row
        if source["status"] == "ABSENT_OR_INVALID":
            source["status"] = "AVAILABLE_TRANSPORT_SNAPSHOT"
        results.append(source)
    return results


def quote_quality(source, row, asof):
    stamp = timestamp(source.get("generated_at_taipei"))
    expiry = timestamp(source.get("cache_expires_at_taipei"))
    fetched = timestamp(row.get("fetched_at_taipei")) or stamp
    if not stamp or not expiry or not fetched or stamp > asof or fetched > asof:
        return "TIMESTAMP_INVALID", None
    if (row.get("fetch_ok") is not True or row.get("stale_at_publish") is True
        or row.get("source_session_date_mismatch") is True):
        return "INVALID_SOURCE_QUOTE", None
    if row.get("is_trial") is True:
        return "TRIAL_NOT_EXECUTED", None
    if row.get("is_halted") is True:
        return "HALTED_REVIEW", None
    price = number(row.get("price"), positive=True)
    if price is None:
        return "NO_EXECUTED_PRICE", None
    if number(row.get("volume")) is None:
        return "INVALID_VOLUME", None
    try:
        qdate = date.fromisoformat(str(row.get("quote_date")))
    except ValueError:
        return "QUOTE_DATE_INVALID", None
    if qdate > asof.date():
        return "QUOTE_IN_FUTURE", None
    if qdate != asof.date():
        return "PRIOR_SESSION_ONLY", price
    if asof > expiry:
        return "EXPIRED_SESSION_SNAPSHOT", price
    return "CURRENT_SESSION_SNAPSHOT", price


def finmind_aggregate_context(root, asof):
    status = read_json(root / "escape_live" / "finmind_twse_common_status.json")
    if not isinstance(status, dict):
        return {"status": "UNAVAILABLE", "per_ticker_quotes": False}
    if status.get("per_security_rows_persisted") is not False or status.get("formal_eod_authority") is not False:
        return {"status": "AUTHORITY_MISMATCH", "per_ticker_quotes": False}
    stamp = timestamp(status.get("generated_at_taipei"))
    available = bool(stamp and stamp.date() == asof.date() and stamp <= asof)
    return {"status": "SAME_DAY_AGGREGATE_ONLY" if available else "STALE_AGGREGATE_ONLY",
            "per_ticker_quotes": False, "source": "FinMind",
            "observed_at_taipei": status.get("generated_at_taipei"),
            "active_covered_count": status.get("active_covered_count"),
            "current_market_date_count": status.get("current_market_date_count"),
            "market_scope": status.get("monitoring_universe"),
            "note": "Aggregate-only: cannot synthesize any ticker quote or EOD close."}


def original_fugle_fetcher(root):
    """Reuse the HENGCE original Fugle transport function, never another endpoint."""
    source = Path(root) / "scripts" / "hengce_live_quote_transport.py"
    if not source.is_file():
        raise EvidenceBlocked("ORIGINAL_FUGLE_TRANSPORT_UNAVAILABLE")
    spec = importlib.util.spec_from_file_location("hengce_existing_fugle_transport", source)
    if spec is None or spec.loader is None:
        raise EvidenceBlocked("ORIGINAL_FUGLE_TRANSPORT_UNLOADABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "fetch_quote", None)):
        raise EvidenceBlocked("ORIGINAL_FUGLE_FETCH_FUNCTION_MISSING")
    return module.fetch_quote


def refresh_uncovered_from_fugle(root, report, api_key, *, fetcher=None, pause=None, clock=None):
    """Explicit on-demand quote fill for uncovered V2.2 Top5 via EXISTING Fugle function.

    Never fetches the whole market, never changes membership/ranking, no canonical
    writes. This is a source observation, not a new strategy or a trading signal.
    """
    if not isinstance(report, dict) or report.get("schema") != "HENGCE_RETAIL_TOP5_EXISTING_QUOTE_OVERLAY_V1":
        raise EvidenceBlocked("RESEARCH_OVERLAY_RECEIPT_REQUIRED")
    if report.get("broker_execution") is not False or report.get("authorized_lots") != 0:
        raise EvidenceBlocked("NO_TRADING_AUTHORITY_REQUIRED")
    if not api_key:
        raise EvidenceBlocked("FUGLE_API_KEY_MISSING")
    clock = clock or (lambda: datetime.now(TW))
    pause = pause or time.sleep
    observed = clock()
    prior = timestamp(report.get("asof_taipei"))
    if not prior or observed.tzinfo is None or abs((observed.astimezone(TW)-prior).total_seconds()) > 120:
        raise EvidenceBlocked("HISTORICAL_REPLAY_CANNOT_BE_REFETCHED_AS_LIVE")
    fetcher = fetcher or original_fugle_fetcher(root)
    telemetry = {
        "request_attempt_count": 0, "rate_limit_event_count": 0,
        "rate_limit_symbols": set(), "rate_limit_recovered_count": 0,
        "terminal_429_count": 0, "server_retry_event_count": 0,
        "network_retry_event_count": 0, "total_retry_wait_seconds": 0.0,
    }
    attempts = []
    targets = [x for x in report["quotes"] if x.get("session_quote_is_current") is not True]
    if len(targets) > 5:
        raise EvidenceBlocked("TOP5_TARGET_LIMIT")
    for i, item in enumerate(targets):
        if i:
            pause(0.65)
        ticker = item["ticker"]
        error = None
        raw = None
        try:
            raw, meta, error = fetcher(ticker, api_key, telemetry)
        except (ValueError, RuntimeError, OSError, TypeError) as ex:
            error = "FETCH_EXCEPTION_" + type(ex).__name__
        seen = clock()
        if seen.tzinfo is None:
            raise EvidenceBlocked("CLOCK_WITHOUT_TIMEZONE")
        seen = seen.astimezone(TW)
        outcome = "FUGLE_FETCH_FAILED"
        price = None
        previous = None
        pct = None
        volume = None
        trade_time = None
        qdate_text = None
        if error is None and isinstance(raw, dict) and str(raw.get("symbol")) == ticker:
            qdate_text = str(raw.get("date") or "")
            try:
                qdate = date.fromisoformat(qdate_text)
            except ValueError:
                qdate = None
            last = raw.get("lastTrade") if isinstance(raw.get("lastTrade"), dict) else {}
            total = raw.get("total") if isinstance(raw.get("total"), dict) else {}
            is_trial = raw.get("isTrial") is True
            halt = raw.get("tradingHalt") if isinstance(raw.get("tradingHalt"), dict) else {}
            previous = number(raw.get("previousClose"), positive=True)
            volume = number(total.get("tradeVolume"))
            if volume is not None and volume < 0:
                volume = None
            traded = number(last.get("price"), positive=True)
            # The EXISTING Fugle transport may return a numeric Unix timestamp
            # or an offset-aware ISO8601 trade timestamp.
            ts = last.get("time")
            try:
                if isinstance(ts, str) and ("T" in ts or "+" in ts or ts.endswith("Z")):
                    trade_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    trade_dt = trade_dt.astimezone(TW) if trade_dt.tzinfo else None
                else:
                    value = float(ts)
                    if value >= 1e14:
                        value /= 1000000
                    elif value >= 1e11:
                        value /= 1000
                    trade_dt = datetime.fromtimestamp(value, TW)
                trade_time = trade_dt.isoformat() if trade_dt and trade_dt <= seen else None
            except (TypeError, ValueError, OverflowError, OSError):
                trade_time = None
            if is_trial:
                outcome = "TRIAL_NOT_EXECUTED"
            elif halt.get("isHalted") is True:
                outcome = "HALTED_REVIEW"
            elif qdate is None or qdate > seen.date():
                outcome = "QUOTE_DATE_INVALID"
            elif traded is None or trade_time is None or volume is None:
                outcome = "EXECUTED_TRADE_NOT_PROVEN"
            else:
                price = traded
                pct = (traded / previous - 1) * 100 if previous else None
                outcome = "CURRENT_SESSION_SNAPSHOT" if qdate == seen.date() else "PRIOR_SESSION_ONLY"
        elif error is None:
            error = "SYMBOL_OR_PAYLOAD_INVALID"
        attempts.append({"ticker": ticker, "result": outcome, "error_code": error})
        if outcome == "CURRENT_SESSION_SNAPSHOT":
            item.update(
                source="FUGLE_EXISTING_TRANSPORT_ON_DEMAND",
                quote_status=outcome,
                quote_date=qdate_text,
                fetched_at_taipei=seen.isoformat(),
                last_trade_time=trade_time,
                last_executed_price_reference=price,
                previous_close_reference=previous,
                change_percent_reference=pct,
                volume_reference=volume,
                session_quote_is_current=True,
                official_eod_close=None,
                tradable_authority=False,
            )
        elif item.get("session_quote_is_current") is not True:
            item["quote_status"] = outcome
            item["refresh_error_code"] = error
    report["asof_taipei"] = clock().astimezone(TW).isoformat()
    report["current_session_quotes"] = sum(bool(x.get("session_quote_is_current")) for x in report["quotes"])
    report["uncovered_or_stale_tickers"] = [
        x["ticker"] for x in report["quotes"] if not x.get("session_quote_is_current")]
    report["status"] = ("ALL_TOP5_QUOTES_CURRENT" if report["current_session_quotes"] == len(report["quotes"])
                        else "PARTIAL_OR_STALE_TOP5_QUOTES")
    report["on_demand_existing_fugle"] = {
        "used_existing_fetch_function": True, "new_market_data_endpoint": False,
        "attempt_count": len(attempts),
        "current_session_fills": sum(z["result"] == "CURRENT_SESSION_SNAPSHOT" for z in attempts),
        "attempts": attempts,
        "request_attempt_count": telemetry["request_attempt_count"],
        "rate_limit_event_count": telemetry["rate_limit_event_count"],
        "terminal_429_count": telemetry["terminal_429_count"],
        "no_broker_or_signal_authority": True,
    }
    return report


def overlay(root, selection, asof):
    if asof.tzinfo is None:
        raise EvidenceBlocked("ASOF_MUST_BE_TIMEZONE_AWARE")
    asof = asof.astimezone(TW)
    decision, rows = valid_candidate_receipt(selection, root=root, asof=asof)
    weekly_scope = (isinstance(selection, dict) and
                    selection.get("schema") == "HENGCE_V22_WEEKLY_RESEARCH_SCREEN_V1")
    scope = ("HENGCE_EXISTING_EOD_TDCC_WEEKLY_RESEARCH_ONLY" if weekly_scope
             else "BUNDLED_REFERENCE_ONLY")
    if decision > asof.date():
        raise EvidenceBlocked("SELECTION_DECISION_IN_FUTURE")
    sources = existing_quote_sources(Path(root))
    out = []
    for item in rows:
        ticker = item["ticker"]
        options = []
        for priority, source in enumerate(sources):
            row = source["entries"].get(ticker)
            if not row or source["status"] != "AVAILABLE_TRANSPORT_SNAPSHOT":
                continue
            quality, price = quote_quality(source, row, asof)
            stamp = timestamp(row.get("fetched_at_taipei")) or timestamp(source["generated_at_taipei"])
            options.append((quality == "CURRENT_SESSION_SNAPSHOT", stamp, -priority, source, row, quality, price))
        if options:
            options.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
            _, _, _, source, quote, quality, price = options[0]
            rec = {"source": source["source"], "quote_status": quality,
                   "quote_date": quote.get("quote_date"),
                   "fetched_at_taipei": quote.get("fetched_at_taipei"),
                   "last_trade_time": quote.get("last_trade_time"),
                   "last_executed_price_reference": price,
                   "previous_close_reference": number(quote.get("previous_close"), positive=True),
                   "change_percent_reference": number(quote.get("change_percent")),
                   "volume_reference": number(quote.get("volume")),
                   "session_quote_is_current": quality == "CURRENT_SESSION_SNAPSHOT",
                   "official_eod_close": None,
                   "tradable_authority": False}
        else:
            rec = {"source": None, "quote_status": "NO_EXISTING_TICKER_QUOTE",
                   "quote_date": None, "fetched_at_taipei": None,
                   "last_executed_price_reference": None,
                   "session_quote_is_current": False,
                   "official_eod_close": None, "tradable_authority": False}
        out.append({"rank": item["rank"], "ticker": ticker,
                    "ranking_source": "V2.2_ORIGINAL_HENGCE_FRIDAY_RESEARCH" if weekly_scope else "V2.2_FROZEN_FRIDAY_RESEARCH",
                    "selection_reference_close": item.get("reference_close"), **rec})
    fresh = sum(x["session_quote_is_current"] for x in out)
    return {
        "schema": "HENGCE_RETAIL_TOP5_EXISTING_QUOTE_OVERLAY_V1",
        "system": "HENGCE", "model": "V2.2_TOP5",
        "mode": "RESEARCH_QUOTE_OBSERVATION_ONLY",
        "asof_taipei": asof.isoformat(), "selection_decision": decision.isoformat(),
        "selection_scope": scope,
        "status": "ALL_TOP5_QUOTES_CURRENT" if fresh == len(out)
                  else "PARTIAL_OR_STALE_TOP5_QUOTES",
        "top5_rows": len(out), "current_session_quotes": fresh,
        "uncovered_or_stale_tickers": [x["ticker"] for x in out if not x["session_quote_is_current"]],
        "quotes": out,
        "source_receipts": [
            {"name": s["source"], "status": s["status"], "covered_tickers": len(s["entries"]),
             "generated_at_taipei": s["generated_at_taipei"],
             "cache_expires_at_taipei": s["cache_expires_at_taipei"]}
            for s in sources],
        "finmind_aggregate": finmind_aggregate_context(Path(root), asof),
        "ranking_changed": False, "formal_eod_replaced": False,
        "formal_tdcc_replaced": False, "official_selector_active": False,
        "buy_signal": False, "sell_signal": False,
        "capital_authority_twd": 0, "authorized_lots": 0, "broker_execution": False,
        "do_not_infer_quote_coverage_from_market_aggregate": True}


def write_output(root, output, result):
    repo, path = Path(root).resolve(), Path(output).resolve()
    if path == repo or repo in path.parents:
        raise EvidenceBlocked("CANNOT_WRITE_INSIDE_HENGCE_REPOSITORY")
    if path.exists():
        raise EvidenceBlocked("OUTPUT_ALREADY_EXISTS")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--selection", type=Path, required=True, help="Verified V2.2 research selection.json; not a live trade signal")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--asof", help="Offset-aware ISO8601 Taiwan observation time")
    parser.add_argument("--refresh-uncovered", action="store_true",
                        help="Explicitly refresh missing Top5 quotes using the EXISTING Fugle fetch function (requires FUGLE_API_KEY)")
    args = parser.parse_args()
    try:
        s = read_json(args.selection)
        now = timestamp(args.asof) if args.asof else datetime.now(TW)
        if now is None:
            raise EvidenceBlocked("BAD_ASOF")
        report = overlay(args.repo_root, s, now)
        if args.refresh_uncovered:
            if args.asof:
                raise EvidenceBlocked("CANNOT_FETCH_HISTORICAL_ASOF")
            report = refresh_uncovered_from_fugle(
                args.repo_root, report, os.environ.get("FUGLE_API_KEY"))
        write_output(args.repo_root, args.output, report)
        print(json.dumps({"status": report["status"], "top5": report["top5_rows"],
                          "current_quote_count": report["current_session_quotes"],
                          "missing": report["uncovered_or_stale_tickers"],
                          "formal_trade_authority": False}, ensure_ascii=False))
    except (EvidenceBlocked, ValueError, TypeError) as exc:
        parser.exit(2, f"RESEARCH_QUOTE_OVERLAY_BLOCKED:{exc}\n")


if __name__ == "__main__":
    main()
