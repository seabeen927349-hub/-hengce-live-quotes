#!/usr/bin/env python3
"""Read-only V2.2 Top5 research quote overlay over EXISTING HENGCE transports.

Does not fetch market data, rebuild a universe, rerank Top5, promote intraday
prices to formal EOD, infer per-security FinMind values, or grant order authority.
Unknown, stale, trial-only and missing quotes are explicit rather than zero-filled.
"""
from __future__ import annotations

import argparse
import json
import math
import re
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


def valid_candidate_receipt(selection):
    if not isinstance(selection, dict):
        raise EvidenceBlocked("V22_RECEIPT_MISSING")
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


def overlay(root, selection, asof):
    if asof.tzinfo is None:
        raise EvidenceBlocked("ASOF_MUST_BE_TIMEZONE_AWARE")
    asof = asof.astimezone(TW)
    decision, rows = valid_candidate_receipt(selection)
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
                    "ranking_source": "V2.2_FROZEN_FRIDAY_RESEARCH",
                    "selection_reference_close": item.get("reference_close"), **rec})
    fresh = sum(x["session_quote_is_current"] for x in out)
    return {
        "schema": "HENGCE_RETAIL_TOP5_EXISTING_QUOTE_OVERLAY_V1",
        "system": "HENGCE", "model": "V2.2_TOP5",
        "mode": "RESEARCH_QUOTE_OBSERVATION_ONLY",
        "asof_taipei": asof.isoformat(), "selection_decision": decision.isoformat(),
        "selection_scope": "BUNDLED_REFERENCE_ONLY",
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
    args = parser.parse_args()
    try:
        s = read_json(args.selection)
        now = timestamp(args.asof) if args.asof else datetime.now(TW)
        if now is None:
            raise EvidenceBlocked("BAD_ASOF")
        report = overlay(args.repo_root, s, now)
        write_output(args.repo_root, args.output, report)
        print(json.dumps({"status": report["status"], "top5": report["top5_rows"],
                          "current_quote_count": report["current_session_quotes"],
                          "missing": report["uncovered_or_stale_tickers"],
                          "formal_trade_authority": False}, ensure_ascii=False))
    except (EvidenceBlocked, ValueError, TypeError) as exc:
        parser.exit(2, f"RESEARCH_QUOTE_OVERLAY_BLOCKED:{exc}\n")


if __name__ == "__main__":
    main()
