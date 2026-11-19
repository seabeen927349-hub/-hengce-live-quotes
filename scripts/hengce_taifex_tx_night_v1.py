#!/usr/bin/env python3
"""Official TAIFEX TX after-hours EOD observation. Research-only, not a stock signal.

TAIFEX attributes the after-hours session begun at 15:00 to the NEXT regular
trading date. Never equate it to TWSE cash closing, daytime TX settlement,
or an intraday quote. Data may not be available immediately at 05:00.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Taipei")
URL = "https://openapi.taifex.com.tw/v1/DailyMarketReportFut"
SCHEMA = "HENGCE_TAIFEX_TX_NIGHT_EOD_OBSERVATION_V1"
SESSION = "盤後"
SHA = re.compile(r"^[0-9a-f]{64}$")
MONTH = re.compile(r"^\d{6}$")


def canonical(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode("utf-8")).hexdigest()


def numeric(value, *, allow_zero=False):
    if isinstance(value, bool):
        raise ValueError("TX_NIGHT_BOOLEAN_PRICE")
    try:
        number = float(str(value).strip().replace(",", "").replace("%", ""))
    except (ValueError, TypeError):
        raise ValueError("TX_NIGHT_BAD_NUMBER") from None
    if not math.isfinite(number) or number < 0 or (number == 0 and not allow_zero):
        raise ValueError("TX_NIGHT_BAD_NUMBER")
    return number


def trading_date(value):
    s = str(value).strip()
    for fmt in ("%Y%m%d", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError("TX_NIGHT_BAD_TRADING_DATE")


def parse(raw, asof, *, source_url=URL):
    """Only finalized TX night rows; near month determined within the SAME date."""
    if not 20 < len(raw) <= 5_000_000:
        raise ValueError("TX_NIGHT_BAD_SOURCE_SIZE")
    data = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError("TX_NIGHT_API_SCHEMA_CHANGED")
    if asof.tzinfo is None:
        raise ValueError("TX_NIGHT_ASOF_TIMEZONE_REQUIRED")
    now = asof.astimezone(TZ)
    if urlsplit(source_url).hostname != "openapi.taifex.com.tw":
        raise ValueError("TX_NIGHT_SOURCE_NOT_TAIFEX")
    # Do not take a live/unfinished night-market row or guess a completed 05:00.
    closed_cutoff = dt.time(5, 15)
    records = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        if str(item.get("Contract", "")).strip() != "TX":
            continue
        if str(item.get("TradingSession", "")).strip() not in ("盤後", "After Hours"):
            continue
        day = trading_date(item.get("Date"))
        expiry = str(item.get("ContractMonth(Week)", "")).strip()
        if not MONTH.fullmatch(expiry):
            continue
        if day > now.date():
            raise ValueError("TX_NIGHT_FUTURE_SESSION")
        if day == now.date() and now.time() < closed_cutoff:
            continue
        # Contract-expiry crossover: only a live calendar/near month may qualify.
        # The prior contract can still be the front month before its expiry day,
        # but on the 3rd Wednesday it expires in the regular daytime session.
        yearmonth = int(day.strftime("%Y%m"))
        if int(expiry) < yearmonth:
            continue
        third_wednesday = 1 + (2 - day.replace(day=1).weekday()) % 7 + 14
        if int(expiry) == yearmonth and day.day >= third_wednesday:
            continue
        last = numeric(item.get("Last"))
        volume_float = numeric(item.get("Volume"), allow_zero=True)
        if not volume_float.is_integer():
            raise ValueError("TX_NIGHT_VOLUME_NOT_INTEGER")
        volume = int(volume_float)
        if volume <= 0:
            continue
        record = {
            "session_date": day.isoformat(), "contract_month": expiry,
            "night_last": last,
            "night_open": numeric(item.get("Open")),
            "night_high": numeric(item.get("High")),
            "night_low": numeric(item.get("Low")),
            "night_volume_contracts": volume
        }
        if not (record["night_low"] <= record["night_last"] <= record["night_high"] and
                record["night_low"] <= record["night_open"] <= record["night_high"]):
            raise ValueError("TX_NIGHT_OHLC_CONFLICT")
        key = (day, expiry)
        if key in records and records[key] != record:
            raise ValueError("TX_NIGHT_DUPLICATE_CONFLICT")
        records[key] = record
    if not records:
        raise ValueError("TX_NIGHT_NO_COMPLETED_TX_ROW")
    latest_day = max(day for day, expiry in records)
    months = sorted(expiry for day, expiry in records if day == latest_day)
    result = dict(records[(latest_day, months[0])])
    result.update({
        "schema": SCHEMA,
        "status": ("OFFICIAL_TX_NIGHT_ASOF_TW_SESSION" if latest_day == now.date()
                   else "OFFICIAL_TX_NIGHT_HISTORICAL_NOT_CURRENT"),
        "source": "TAIFEX", "source_url": source_url,
        "source_raw_sha256": hashlib.sha256(raw).hexdigest(),
        "observed_at_taipei": now.isoformat(),
        "product": "TX", "trading_session": SESSION,
        "session_label_semantics": "TAIFEX_NEXT_REGULAR_TRADING_DATE",
        "session_clock_taipei": "PREVIOUS_TRADING_DAY_15:00_TO_FOLLOWING_05:00",
        "night_last_is_cash_close": False,
        "night_last_is_day_settlement": False,
        "intraday_realtime": False, "formal_forecast": False,
        "model_score_authority": False, "selection_authority": False,
        "trading_authority": False, "broker_execution": False,
    })
    result["receipt_sha256"] = canonical(result)
    return result


def fetch():
    req = urllib.request.Request(URL, headers={
        "User-Agent": "HENGCE-TAIFEX-TX-NIGHT-RESEARCH/1.0",
        "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as response:
        if urlsplit(response.geturl()).hostname != "openapi.taifex.com.tw":
            raise ValueError("TX_NIGHT_UNTRUSTED_REDIRECT")
        raw = response.read(5_000_001)
    return raw


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--history-dir", type=Path, required=True)
    args = p.parse_args()
    now = dt.datetime.now(TZ)
    result = parse(fetch(), now)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists():
        prior = json.loads(args.out.read_text(encoding="utf-8"))
        if (prior.get("schema") == SCHEMA and
            prior.get("receipt_sha256") == canonical({k: v for k, v in prior.items()
                                                     if k != "receipt_sha256"}) and
            all(prior.get(k) == result.get(k) for k in
                ("session_date", "contract_month", "night_last", "night_open",
                 "night_high", "night_low", "night_volume_contracts"))):
            print(json.dumps({"status": "TX_NIGHT_SOURCE_UNCHANGED",
                "session_date": result["session_date"]}))
            return
    output = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    history = args.history_dir / (result["session_date"].replace("-", "") + "_" +
                                  result["receipt_sha256"][:16] + ".json")
    history.parent.mkdir(parents=True, exist_ok=True)
    if history.exists() and history.read_text(encoding="utf-8") != output:
        raise ValueError("TX_NIGHT_IMMUTABLE_HISTORY_CONFLICT")
    history.write_text(output, encoding="utf-8")
    args.out.write_text(output, encoding="utf-8")
    print(json.dumps({"status": result["status"],
        "session_date": result["session_date"],
        "night_last": result["night_last"],
        "contract_month": result["contract_month"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
