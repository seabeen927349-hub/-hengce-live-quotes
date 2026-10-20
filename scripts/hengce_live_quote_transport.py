#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Taipei")
CACHE_TTL_SECONDS = 600
TRADE_IDLE_SECONDS = 900
UNIVERSE_PATH = Path("hengce/live_universe.json")
CONTRACT_PATH = Path("hengce/HENGCE_LIVE_QUOTE_TRANSPORT_CONTRACT_v1_0_20261020.json")
LIFECYCLE_PATH = Path("hengce/live_market_lifecycle.json")
QUOTE_DIR = Path("live/quotes")
BASE = "https://api.fugle.tw/marketdata/v1.0/stock/intraday/quote/"

ROLE = "QUOTE_TRANSPORT_ONLY_NO_RANKING_SIGNAL_CAPITAL_AUTHORITY"
LINEAGE = "LINEAGE_ONLY_NOT_AUTHORITY"
LIFECYCLE_ROLE = "OBSERVABILITY_ONLY_NO_RANKING_SIGNAL_CAPITAL_AUTHORITY"
MAX_ATTEMPTS = 6
BASE_SPACING_SECONDS = 0.65
BACKOFF_CAP_SECONDS = 20.0


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def now_tw():
    return datetime.now(TZ)


def phase(dt):
    if dt.weekday() >= 5:
        return "closed"
    minute = dt.hour * 60 + dt.minute
    if minute < 540:
        return "preopen"
    if minute <= 810:
        return "open"
    return "closed"


def parse_ts(value):
    if value in (None, ""):
        return None
    try:
        value = float(value)
        if value >= 1e14:
            value /= 1_000_000
        elif value >= 1e11:
            value /= 1_000
        return datetime.fromtimestamp(value, TZ)
    except Exception:
        return None


def parse_date(value):
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


def age(now, dt):
    return None if dt is None else max(0, int((now - dt).total_seconds()))


def level(value):
    return value[0] if isinstance(value, list) and value and isinstance(value[0], dict) else {}


def authority_fields():
    return {
        "transport_role": ROLE,
        "source_run_id_semantics": LINEAGE,
        "ranking_authority": False,
        "signal_authority": False,
        "capital_authority": False,
        "broker_order_execution": False,
        "legacy_v3_rank_authority": False,
    }


def validate_contract(contract):
    if contract.get("module") != "HENGCE_LIVE_QUOTE_TRANSPORT":
        raise SystemExit("TRANSPORT_CONTRACT_MODULE_MISMATCH")
    if contract.get("role") != ROLE:
        raise SystemExit("TRANSPORT_CONTRACT_ROLE_MISMATCH")
    if contract.get("universe_source_run_id_semantics") != LINEAGE:
        raise SystemExit("TRANSPORT_CONTRACT_LINEAGE_MISMATCH")
    if contract.get("legacy_v3_source_label_confers_authority") is not False:
        raise SystemExit("TRANSPORT_CONTRACT_V3_AUTHORITY_MUST_BE_FALSE")
    for key in ("ranking", "signal", "capital", "broker_execution"):
        if (contract.get("authority") or {}).get(key) is not False:
            raise SystemExit("TRANSPORT_CONTRACT_AUTHORITY_MUST_BE_FALSE:" + key)


def validate_lifecycle(lifecycle):
    if lifecycle.get("module") != "HENGCE_LIVE_MARKET_LIFECYCLE":
        raise SystemExit("LIFECYCLE_MODULE_MISMATCH")
    if lifecycle.get("role") != LIFECYCLE_ROLE:
        raise SystemExit("LIFECYCLE_ROLE_MISMATCH")
    for key in ("ranking", "signal", "capital", "broker_execution"):
        if (lifecycle.get("authority") or {}).get(key) is not False:
            raise SystemExit("LIFECYCLE_AUTHORITY_MUST_BE_FALSE:" + key)

    seen = set()
    for row in lifecycle.get("entries") or []:
        symbol = str(row.get("symbol") or "")
        if not re.fullmatch(r"[1-9]\d{3}", symbol):
            raise SystemExit("LIFECYCLE_BAD_SYMBOL:" + symbol)
        if symbol in seen:
            raise SystemExit("LIFECYCLE_DUPLICATE_SYMBOL:" + symbol)
        seen.add(symbol)
        start = parse_date(row.get("trading_suspended_from"))
        through = parse_date(row.get("trading_suspended_through"))
        resume = parse_date(row.get("resume_date"))
        if None in (start, through, resume) or not (start <= through < resume):
            raise SystemExit("LIFECYCLE_BAD_DATE_RANGE:" + symbol)
        if row.get("transport_fetch_required") is not True:
            raise SystemExit("LIFECYCLE_MUST_KEEP_TRANSPORT_FETCH:" + symbol)
        if row.get("expected_current_session_quote") is not False:
            raise SystemExit("LIFECYCLE_EXPECTED_QUOTE_FLAG_INVALID:" + symbol)
        for key in ("ranking_authority", "signal_authority", "capital_authority"):
            if row.get(key) is not False:
                raise SystemExit("LIFECYCLE_ROW_AUTHORITY_MUST_BE_FALSE:" + symbol + ":" + key)


def load_inputs():
    if not UNIVERSE_PATH.exists():
        raise SystemExit("LIVE_UNIVERSE_MISSING_FAIL_CLOSED")
    if not CONTRACT_PATH.exists():
        raise SystemExit("LIVE_TRANSPORT_CONTRACT_MISSING_FAIL_CLOSED")
    if not LIFECYCLE_PATH.exists():
        raise SystemExit("LIVE_MARKET_LIFECYCLE_MISSING_FAIL_CLOSED")

    universe_raw = UNIVERSE_PATH.read_bytes()
    contract_raw = CONTRACT_PATH.read_bytes()
    lifecycle_raw = LIFECYCLE_PATH.read_bytes()

    universe = json.loads(universe_raw.decode("utf-8"))
    contract = json.loads(contract_raw.decode("utf-8"))
    lifecycle = json.loads(lifecycle_raw.decode("utf-8"))
    validate_contract(contract)
    validate_lifecycle(lifecycle)

    symbols = [str(x).strip() for x in universe.get("symbols", [])]
    if not symbols:
        raise SystemExit("LIVE_UNIVERSE_EMPTY_FAIL_CLOSED")
    if len(symbols) != len(set(symbols)):
        raise SystemExit("LIVE_UNIVERSE_DUPLICATE_SYMBOLS")
    bad = [x for x in symbols if not re.fullmatch(r"[1-9]\d{3}", x)]
    if bad:
        raise SystemExit("LIVE_UNIVERSE_BAD_SYMBOLS:" + str(bad[:10]))
    if int(universe.get("requested_count", len(symbols))) != len(symbols):
        raise SystemExit("LIVE_UNIVERSE_COUNT_MISMATCH")

    return (
        universe,
        sha256(universe_raw),
        contract,
        sha256(contract_raw),
        lifecycle,
        sha256(lifecycle_raw),
        symbols,
    )


def lifecycle_state(symbol, trade_date, lifecycle):
    trade_date = trade_date if isinstance(trade_date, date) else parse_date(trade_date)
    for row in lifecycle.get("entries") or []:
        if str(row.get("symbol")) != str(symbol):
            continue
        start = parse_date(row.get("trading_suspended_from"))
        resume = parse_date(row.get("resume_date"))
        if trade_date is not None and start <= trade_date < resume:
            return {
                "market_lifecycle_state": row.get("state"),
                "market_lifecycle_reason": row.get("reason"),
                "market_lifecycle_expected_inactive": True,
                "market_lifecycle_resume_date": row.get("resume_date"),
                "market_lifecycle_source": row.get("source"),
            }
        return {
            "market_lifecycle_state": "ACTIVE_OUTSIDE_PINNED_EXCEPTION",
            "market_lifecycle_reason": None,
            "market_lifecycle_expected_inactive": False,
            "market_lifecycle_resume_date": row.get("resume_date"),
            "market_lifecycle_source": row.get("source"),
        }
    return {
        "market_lifecycle_state": "ACTIVE_OR_UNCLASSIFIED",
        "market_lifecycle_reason": None,
        "market_lifecycle_expected_inactive": False,
        "market_lifecycle_resume_date": None,
        "market_lifecycle_source": None,
    }


def classify_freshness(symbol, quote_date, snap_date, lifecycle):
    life = lifecycle_state(symbol, snap_date, lifecycle)
    mismatch = str(quote_date or "") != snap_date.isoformat()
    expected_inactive = bool(life["market_lifecycle_expected_inactive"])
    life.update(
        {
            "source_session_date_mismatch": mismatch,
            "expected_inactive_at_publish": mismatch and expected_inactive,
            "unexpected_stale_at_publish": mismatch and not expected_inactive,
        }
    )
    return life


def retry_after(headers):
    if not headers:
        return None
    raw = headers.get("Retry-After")
    if raw in (None, ""):
        return None
    raw = str(raw).strip()
    if raw.isdigit():
        return min(float(raw), BACKOFF_CAP_SECONDS)
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, min((dt - datetime.now(timezone.utc)).total_seconds(), BACKOFF_CAP_SECONDS))
    except Exception:
        return None


def backoff(attempt, retry=None):
    wait = min(BACKOFF_CAP_SECONDS, 1.25 * (2 ** max(0, attempt - 1)))
    wait += random.uniform(0.15, 0.55)
    if retry is not None:
        wait = max(wait, float(retry))
    return min(wait, BACKOFF_CAP_SECONDS)


def fetch_quote(symbol, api_key, telemetry):
    request = urllib.request.Request(
        BASE + symbol,
        headers={
            "X-API-KEY": api_key,
            "Accept": "application/json",
            "User-Agent": "HENGCE-LIVE/3.1-TRANSPORT-LIFECYCLE",
        },
    )
    meta = {
        "attempts": 0,
        "rate_limit_events": 0,
        "server_retry_events": 0,
        "network_retry_events": 0,
        "retry_wait_seconds": 0.0,
    }

    for attempt in range(1, MAX_ATTEMPTS + 1):
        meta["attempts"] = attempt
        telemetry["request_attempt_count"] += 1
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                row = json.load(response)
            if meta["rate_limit_events"]:
                telemetry["rate_limit_recovered_count"] += 1
            return row, meta, None
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                return None, meta, f"AUTH_OR_PLAN_HTTP_{exc.code}"
            if exc.code == 429:
                meta["rate_limit_events"] += 1
                telemetry["rate_limit_event_count"] += 1
                telemetry["rate_limit_symbols"].add(symbol)
                if attempt == MAX_ATTEMPTS:
                    telemetry["terminal_429_count"] += 1
                    return None, meta, "RATE_LIMIT_HTTP_429"
                wait = backoff(attempt, retry_after(exc.headers))
            elif 500 <= exc.code <= 599:
                meta["server_retry_events"] += 1
                telemetry["server_retry_event_count"] += 1
                if attempt == MAX_ATTEMPTS:
                    return None, meta, f"SERVER_HTTP_{exc.code}"
                wait = backoff(attempt)
            else:
                return None, meta, f"HTTP_{exc.code}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            meta["network_retry_events"] += 1
            telemetry["network_retry_event_count"] += 1
            if attempt == MAX_ATTEMPTS:
                return None, meta, "NETWORK_ERROR_" + type(exc).__name__
            wait = backoff(attempt)
        except Exception as exc:
            return None, meta, "UNEXPECTED_" + type(exc).__name__ + ":" + str(exc)

        meta["retry_wait_seconds"] += wait
        telemetry["total_retry_wait_seconds"] += wait
        time.sleep(wait)

    return None, meta, "UNREACHABLE_FETCH_STATE"


def old_quote(symbol):
    path = QUOTE_DIR / f"{symbol}.json"
    if not path.exists():
        return None
    try:
        return load_json(path)
    except Exception:
        return None


def apply_transport_meta(record, meta):
    record.update(authority_fields())
    record["transport_fetch_attempts"] = meta["attempts"]
    record["transport_rate_limit_events"] = meta["rate_limit_events"]
    record["transport_server_retry_events"] = meta["server_retry_events"]
    record["transport_network_retry_events"] = meta["network_retry_events"]
    record["transport_retry_wait_seconds"] = round(meta["retry_wait_seconds"], 3)
    return record


def run_fetch():
    api_key = os.environ.get("FUGLE_API_KEY")
    if not api_key:
        raise SystemExit("FUGLE_API_KEY missing")

    universe, universe_sha, contract, contract_sha, lifecycle, lifecycle_sha, symbols = load_inputs()
    universe_version = universe.get("version")
    universe_target_date = universe.get("target_date")
    universe_source_run_id = universe.get("source_run_id")
    action_board_version = universe.get("source_action_board_version")
    legacy_source = "HENGCE_V3" in str(universe_source_run_id or "")

    print("HENGCE LIVE UNIVERSE", len(symbols), universe_version, universe_source_run_id, "provenance_scope=transport-only")

    QUOTE_DIR.mkdir(parents=True, exist_ok=True)
    snap = now_tw()
    snapshot_id = snap.strftime("%Y%m%dT%H%M%S%z")
    expires = snap + timedelta(seconds=CACHE_TTL_SECONDS)
    records = []
    failures = []
    successful = 0
    telemetry = {
        "request_attempt_count": 0,
        "rate_limit_event_count": 0,
        "rate_limit_symbols": set(),
        "rate_limit_recovered_count": 0,
        "terminal_429_count": 0,
        "server_retry_event_count": 0,
        "network_retry_event_count": 0,
        "total_retry_wait_seconds": 0.0,
    }

    for symbol in symbols:
        row, meta, error = fetch_quote(symbol, api_key, telemetry)
        if error is None:
            try:
                if not isinstance(row, dict):
                    raise RuntimeError("INVALID_RESPONSE")
                if str(row.get("symbol")) != symbol:
                    raise RuntimeError("SYMBOL_MISMATCH")
                name = row.get("name")
                if not name:
                    raise RuntimeError("NAME_MISSING")

                total = row.get("total") or {}
                last = row.get("lastTrade") or {}
                trial = row.get("lastTrial") or {}
                halt = row.get("tradingHalt") or {}
                bid = level(row.get("bids"))
                ask = level(row.get("asks"))
                quote_ts = parse_ts(row.get("lastUpdated"))
                trade_ts = parse_ts(last.get("time"))
                price = last.get("price")
                if price is None:
                    price = row.get("lastPrice")
                previous_close = row.get("previousClose")
                change = change_percent = None
                if price is not None and previous_close not in (None, 0):
                    change = round(float(price) - float(previous_close), 4)
                    change_percent = round((float(price) / float(previous_close) - 1) * 100, 4)

                quote_date = row.get("date")
                is_trial = bool(row.get("isTrial", False))
                trade_age = age(snap, trade_ts)
                fresh = classify_freshness(symbol, quote_date, snap.date(), lifecycle)

                record = {
                    "schema_version": 2,
                    "snapshot_id": snapshot_id,
                    "symbol": symbol,
                    "company_name": name,
                    "price": price,
                    "previous_close": previous_close,
                    "reference_price": row.get("referencePrice"),
                    "open": row.get("openPrice"),
                    "high": row.get("highPrice"),
                    "low": row.get("lowPrice"),
                    "avg_price": row.get("avgPrice"),
                    "change": change,
                    "change_percent": change_percent,
                    "volume": total.get("tradeVolume"),
                    "trade_value": total.get("tradeValue"),
                    "transactions": total.get("transaction"),
                    "volume_at_bid": total.get("tradeVolumeAtBid"),
                    "volume_at_ask": total.get("tradeVolumeAtAsk"),
                    "best_bid": bid.get("price"),
                    "best_bid_size": bid.get("size"),
                    "best_ask": ask.get("price"),
                    "best_ask_size": ask.get("size"),
                    "last_trade_time": trade_ts.isoformat() if trade_ts else None,
                    "trade_age_seconds": trade_age,
                    "trade_idle_warning": trade_age is not None and trade_age > TRADE_IDLE_SECONDS,
                    "source_last_price": row.get("lastPrice"),
                    "source_last_updated": quote_ts.isoformat() if quote_ts else None,
                    "quote_age_seconds": age(snap, quote_ts),
                    "is_trial": is_trial,
                    "trial_price": row.get("lastPrice") if is_trial else None,
                    "last_trial_price": trial.get("price"),
                    "is_halted": bool(halt.get("isHalted", False)),
                    "is_limit_up_price": bool(row.get("isLimitUpPrice", False)),
                    "is_limit_down_price": bool(row.get("isLimitDownPrice", False)),
                    "is_delayed_open": bool(row.get("isDelayedOpen", False)),
                    "is_delayed_close": bool(row.get("isDelayedClose", False)),
                    "quote_date": quote_date,
                    "stale_at_publish": fresh["source_session_date_mismatch"],
                    "fetch_ok": True,
                    "fetched_at_taipei": snap.isoformat(),
                    "cache_expires_at_taipei": expires.isoformat(),
                    "market_phase": phase(snap),
                    "source": "Fugle MarketData",
                    "universe_version": universe_version,
                    "universe_source_run_id": universe_source_run_id,
                    "source_action_board_version": action_board_version,
                    **fresh,
                }
                apply_transport_meta(record, meta)
                records.append(record)
                successful += 1
                (QUOTE_DIR / f"{symbol}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
                print("OK", symbol, name, price, "attempts", meta["attempts"], "lifecycle", fresh["market_lifecycle_state"])
            except Exception as exc:
                error = str(exc)

        if error is not None:
            failures.append({"symbol": symbol, "error": error, "attempts": meta["attempts"], "rate_limit_events": meta["rate_limit_events"], "retry_wait_seconds": round(meta["retry_wait_seconds"], 3)})
            old = old_quote(symbol)
            if old:
                fresh = classify_freshness(symbol, old.get("quote_date"), snap.date(), lifecycle)
                old.update(fresh)
                old["stale_at_publish"] = True
                old["fetch_ok"] = False
                old["fetch_error"] = error
                old["last_fetch_attempt_taipei"] = snap.isoformat()
                old["cache_expires_at_taipei"] = expires.isoformat()
                apply_transport_meta(old, meta)
                records.append(old)
            print("FAIL", symbol, error, "attempts", meta["attempts"])

        time.sleep(BASE_SPACING_SECONDS)

    if successful == 0:
        raise SystemExit("ALL_REQUESTS_FAILED")

    failure_count = len(failures)
    transport_health = "PASS" if failure_count == 0 else "DEGRADED"
    rate_limit_symbols = sorted(telemetry["rate_limit_symbols"])
    source_mismatch_count = sum(bool(row.get("source_session_date_mismatch")) for row in records)
    expected_inactive_count = sum(bool(row.get("expected_inactive_at_publish")) for row in records)
    unexpected_stale_count = sum(bool(row.get("unexpected_stale_at_publish")) for row in records)
    current_session_count = sum(not bool(row.get("source_session_date_mismatch")) for row in records)

    expected_inactive_symbols = sorted(symbol for symbol in symbols if lifecycle_state(symbol, snap.date(), lifecycle)["market_lifecycle_expected_inactive"])
    expected_active_count = len(symbols) - len(expected_inactive_symbols)
    expected_active_current_count = sum(1 for row in records if row.get("symbol") not in expected_inactive_symbols and not row.get("source_session_date_mismatch") and row.get("fetch_ok") is True)
    expected_active_ratio = expected_active_current_count / expected_active_count if expected_active_count else 1.0
    freshness_status = "PASS" if unexpected_stale_count == 0 else "DEGRADED"

    payload = {
        "schema_version": 2,
        "service": "HENGCE LIVE QUOTES",
        "snapshot_id": snapshot_id,
        "generated_at_taipei": snap.isoformat(),
        "cache_expires_at_taipei": expires.isoformat(),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "market_phase": phase(snap),
        **authority_fields(),
        "transport_contract_version": contract.get("contract_version"),
        "transport_contract_sha256": contract_sha,
        "market_lifecycle_schema_version": lifecycle.get("schema_version"),
        "market_lifecycle_sha256": lifecycle_sha,
        "market_lifecycle_role": lifecycle.get("role"),
        "transport_health_status": transport_health,
        "data_freshness_status": freshness_status,
        "fully_healthy": failure_count == 0 and unexpected_stale_count == 0,
        "degraded": failure_count > 0 or unexpected_stale_count > 0,
        "fresh_success_ratio": round(successful / len(symbols), 6),
        "current_session_quote_ratio": round(current_session_count / len(symbols), 6),
        "expected_active_count": expected_active_count,
        "expected_inactive_symbol_count": len(expected_inactive_symbols),
        "expected_inactive_symbols": expected_inactive_symbols,
        "expected_active_current_session_count": expected_active_current_count,
        "expected_active_current_session_ratio": round(expected_active_ratio, 6),
        "source_session_date_mismatch_count": source_mismatch_count,
        "stale_count": source_mismatch_count,
        "expected_inactive_count": expected_inactive_count,
        "unexpected_stale_count": unexpected_stale_count,
        "retry_policy": {"max_attempts": MAX_ATTEMPTS, "base_spacing_seconds": BASE_SPACING_SECONDS, "respect_retry_after": True, "backoff_cap_seconds": BACKOFF_CAP_SECONDS},
        "request_attempt_count": telemetry["request_attempt_count"],
        "rate_limit_event_count": telemetry["rate_limit_event_count"],
        "rate_limit_symbol_count": len(rate_limit_symbols),
        "rate_limit_symbols": rate_limit_symbols,
        "rate_limit_recovered_count": telemetry["rate_limit_recovered_count"],
        "terminal_429_count": telemetry["terminal_429_count"],
        "server_retry_event_count": telemetry["server_retry_event_count"],
        "network_retry_event_count": telemetry["network_retry_event_count"],
        "total_retry_wait_seconds": round(telemetry["total_retry_wait_seconds"], 3),
        "universe_policy": "DAILY_ACTION_BOARD_ROWS_HARD_BIND",
        "universe_version": universe_version,
        "universe_target_date": universe_target_date,
        "universe_source_run_id": universe_source_run_id,
        "source_action_board_version": action_board_version,
        "legacy_source_label_detected": legacy_source,
        "universe_sha256": universe_sha,
        "requested_count": len(symbols),
        "success_count": successful,
        "failure_count": failure_count,
        "trial_count": sum(bool(row.get("is_trial")) for row in records),
        "halted_count": sum(bool(row.get("is_halted")) for row in records),
        "failures": failures,
        "data": records,
    }
    status = {key: value for key, value in payload.items() if key != "data"}
    status["healthy"] = successful > 0

    Path("latest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("live/active.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("live/status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    print("HENGCE SNAPSHOT", transport_health, "freshness", freshness_status, successful, "/", len(symbols), "expected_inactive", expected_inactive_count, "unexpected_stale", unexpected_stale_count, "429_events", telemetry["rate_limit_event_count"], "429_recovered", telemetry["rate_limit_recovered_count"], "terminal_429", telemetry["terminal_429_count"])


def validate_latest():
    universe, universe_sha, contract, contract_sha, lifecycle, lifecycle_sha, symbols = load_inputs()
    latest = load_json("latest.json")
    actual = [str(row.get("symbol")) for row in latest.get("data", [])]
    failed = {str(row.get("symbol")) for row in latest.get("failures", [])}

    if latest.get("requested_count") != len(symbols):
        raise SystemExit("requested_count mismatch")
    if latest.get("universe_source_run_id") != universe.get("source_run_id"):
        raise SystemExit("universe source run mismatch")
    if latest.get("universe_sha256") != universe_sha:
        raise SystemExit("universe sha mismatch")
    if latest.get("transport_contract_sha256") != contract_sha:
        raise SystemExit("transport contract sha mismatch")
    if latest.get("transport_contract_version") != contract.get("contract_version"):
        raise SystemExit("transport contract version mismatch")
    if latest.get("market_lifecycle_sha256") != lifecycle_sha:
        raise SystemExit("market lifecycle sha mismatch")
    if latest.get("market_lifecycle_schema_version") != lifecycle.get("schema_version"):
        raise SystemExit("market lifecycle schema mismatch")
    if latest.get("market_lifecycle_role") != LIFECYCLE_ROLE:
        raise SystemExit("market lifecycle role mismatch")
    if latest.get("transport_role") != ROLE or latest.get("source_run_id_semantics") != LINEAGE:
        raise SystemExit("transport provenance mismatch")

    for key in ("ranking_authority", "signal_authority", "capital_authority", "broker_order_execution", "legacy_v3_rank_authority"):
        if latest.get(key) is not False:
            raise SystemExit(key + " must remain false")

    if "HENGCE_V3" in str(universe.get("source_run_id") or "") and latest.get("legacy_source_label_detected") is not True:
        raise SystemExit("legacy V3 lineage detection missing")
    if "2033" not in symbols or "6415" not in symbols:
        raise SystemExit("continuity/reentry regression symbol absent")

    silent = [symbol for symbol in symbols if symbol not in actual and symbol not in failed]
    if silent:
        raise SystemExit("silent missing symbols:" + str(silent[:10]))

    terminal_429_failures = sum(1 for row in latest.get("failures", []) if row.get("error") == "RATE_LIMIT_HTTP_429")
    if latest.get("terminal_429_count") != terminal_429_failures:
        raise SystemExit("terminal 429 telemetry mismatch")
    if int(latest.get("rate_limit_recovered_count", 0)) > int(latest.get("rate_limit_symbol_count", 0)):
        raise SystemExit("429 recovered count invalid")
    if int(latest.get("rate_limit_event_count", 0)) < int(latest.get("terminal_429_count", 0)):
        raise SystemExit("429 event count invalid")

    transport_health = "PASS" if int(latest.get("failure_count", 0)) == 0 else "DEGRADED"
    if latest.get("transport_health_status") != transport_health:
        raise SystemExit("transport health status mismatch")

    rows = latest.get("data", [])
    source_mismatch_count = sum(bool(row.get("source_session_date_mismatch")) for row in rows)
    expected_inactive_count = sum(bool(row.get("expected_inactive_at_publish")) for row in rows)
    unexpected_stale_count = sum(bool(row.get("unexpected_stale_at_publish")) for row in rows)
    if latest.get("stale_count") != source_mismatch_count:
        raise SystemExit("legacy stale_count alias mismatch")
    if latest.get("source_session_date_mismatch_count") != source_mismatch_count:
        raise SystemExit("source mismatch telemetry mismatch")
    if latest.get("expected_inactive_count") != expected_inactive_count:
        raise SystemExit("expected inactive telemetry mismatch")
    if latest.get("unexpected_stale_count") != unexpected_stale_count:
        raise SystemExit("unexpected stale telemetry mismatch")

    freshness_status = "PASS" if unexpected_stale_count == 0 else "DEGRADED"
    if latest.get("data_freshness_status") != freshness_status:
        raise SystemExit("data freshness status mismatch")

    generated_date = parse_date(str(latest.get("generated_at_taipei"))[:10])
    expected_inactive_symbols = sorted(symbol for symbol in symbols if lifecycle_state(symbol, generated_date, lifecycle)["market_lifecycle_expected_inactive"])
    if latest.get("expected_inactive_symbols") != expected_inactive_symbols:
        raise SystemExit("expected inactive symbol set mismatch")

    expected_active_count = len(symbols) - len(expected_inactive_symbols)
    if latest.get("expected_active_count") != expected_active_count:
        raise SystemExit("expected active count mismatch")

    expected_active_current_count = sum(1 for row in rows if row.get("symbol") not in expected_inactive_symbols and not row.get("source_session_date_mismatch") and row.get("fetch_ok") is True)
    if latest.get("expected_active_current_session_count") != expected_active_current_count:
        raise SystemExit("expected active current-session count mismatch")

    expected_fully_healthy = int(latest.get("failure_count", 0)) == 0 and unexpected_stale_count == 0
    if latest.get("fully_healthy") is not expected_fully_healthy:
        raise SystemExit("fully healthy semantics mismatch")

    for row in rows:
        for key in ("ranking_authority", "signal_authority", "capital_authority", "broker_order_execution", "legacy_v3_rank_authority"):
            if row.get(key) is not False:
                raise SystemExit("row authority violation " + str(row.get("symbol")) + ":" + key)

    print("HENGCE LIVE TRANSPORT HARD-LOCK VERIFIED", latest.get("requested_count"), latest.get("success_count"), latest.get("failure_count"), transport_health, "freshness", freshness_status, "expected_inactive", expected_inactive_count, "unexpected_stale", unexpected_stale_count, "429_events", latest.get("rate_limit_event_count"), "429_recovered", latest.get("rate_limit_recovered_count"), "terminal_429", latest.get("terminal_429_count"))


def self_test():
    _, _, contract, _, lifecycle, _, symbols = load_inputs()
    validate_contract(contract)
    validate_lifecycle(lifecycle)
    assert len(symbols) == len(set(symbols))
    assert retry_after({"Retry-After": "3"}) == 3.0
    assert retry_after({"Retry-After": "999"}) == BACKOFF_CAP_SECONDS

    auth = authority_fields()
    assert all(auth[key] is False for key in ("ranking_authority", "signal_authority", "capital_authority", "broker_order_execution", "legacy_v3_rank_authority"))

    during = lifecycle_state("1516", date(2026, 10, 20), lifecycle)
    after = lifecycle_state("1516", date(2026, 10, 27), lifecycle)
    assert during["market_lifecycle_expected_inactive"] is True
    assert during["market_lifecycle_state"] == "SUSPENDED_CORPORATE_ACTION"
    assert after["market_lifecycle_expected_inactive"] is False

    classified = classify_freshness("1516", "2026-10-15", date(2026, 10, 20), lifecycle)
    assert classified["expected_inactive_at_publish"] is True
    assert classified["unexpected_stale_at_publish"] is False

    print(json.dumps({"self_test": "PASS", "transport_role": ROLE, "source_run_id_semantics": LINEAGE, "legacy_v3_rank_authority": False, "max_attempts": MAX_ATTEMPTS, "respect_retry_after": True, "backoff_cap_seconds": BACKOFF_CAP_SECONDS, "lifecycle_classification": True, "suspended_1516_on_20261020": True, "resume_1516_on_20261027": True}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("fetch", "validate", "self-test"), default="fetch")
    mode = parser.parse_args().mode
    {"fetch": run_fetch, "validate": validate_latest, "self-test": self_test}[mode]()


if __name__ == "__main__":
    main()
