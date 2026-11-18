#!/usr/bin/env python3
"""TAIFEX Taiwan VIX official daily 13:45 observation (research-only sidecar).

Never substitutes Cboe VIX, changes a stock score, or confers order authority.
The official monthly text file is NOT a verified live/intraday feed.
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
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Taipei")
SCHEMA = "HENGCE_TAIFEX_TAIWAN_VIX_CLOSE_OBSERVATION_V1"
BASE = "https://www.taifex.com.tw/file/taifex/Dailydownload/vix/log2data/"
ROW = re.compile(r"^(\d{8})\s+(\d{8})\s+(\d{1,3}(?:\.\d{1,4})?)\s+(\d{1,3}(?:\.\d{1,4})?)$")
SHA = re.compile(r"^[0-9a-f]{64}$")


def canonical(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def month_url(year, month):
    return BASE + f"{year:04d}{month:02d}new.txt"


def parse_month(raw, year, month):
    """Only TAIFEX 13:45 new-VIX rows, never last-minute average column."""
    if not 100 <= len(raw) <= 2000000:
        raise ValueError("TAIFEX_SOURCE_SIZE_INVALID")
    try:
        data = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        data = raw.decode("cp950")
    rows = {}
    for line in data.splitlines():
        match = ROW.fullmatch(line.strip())
        if not match:
            continue
        day = dt.datetime.strptime(match.group(1), "%Y%m%d").date()
        if (day.year, day.month) != (year, month) or day.weekday() >= 5:
            raise ValueError("TAIFEX_ROW_DATE_INVALID")
        if match.group(2) != "13450000":
            raise ValueError("TAIFEX_NOT_OFFICIAL_1345_ROW")
        close, minute_average = (float(match.group(3)), float(match.group(4)))
        if not all(math.isfinite(x) and 0 < x < 1000 for x in (close, minute_average)):
            raise ValueError("TAIFEX_BAD_VOLATILITY")
        if day in rows and rows[day] != close:
            raise ValueError("TAIFEX_CONFLICTING_DUPLICATE_DATE")
        rows[day] = close
    if not rows:
        raise ValueError("TAIFEX_NO_VALID_1345_DAILY_ROWS")
    return rows


def download_month(year, month):
    url = month_url(year, month)
    req = urllib.request.Request(url, headers={"User-Agent": "HENGCE-TAIFEX-VIX-RESEARCH/1.0",
                                               "Accept": "text/plain,*/*"})
    with urllib.request.urlopen(req, timeout=20) as response:
        from urllib.parse import urlsplit
        host = urlsplit(response.geturl()).hostname
        if host not in ("www.taifex.com.tw", "taifex.com.tw"):
            raise ValueError("TAIFEX_UNTRUSTED_REDIRECT")
        raw = response.read(2000001)
    return parse_month(raw, year, month), hashlib.sha256(raw).hexdigest(), url


def build(asof, monthly):
    """monthly = [(year, month, rows, raw_sha, url)], with verified bytes."""
    if asof.tzinfo is None:
        raise ValueError("TAIPEI_TIMEZONE_REQUIRED")
    now = asof.astimezone(TZ)
    all_rows, proof = {}, {}
    for year, month, rows, raw_sha, url in monthly:
        if not SHA.fullmatch(raw_sha) or url != month_url(year, month):
            raise ValueError("TAIFEX_SOURCE_PROOF_INVALID")
        proof[(year, month)] = (raw_sha, url)
        for day, price in rows.items():
            if (day.year, day.month) != (year, month) or not math.isfinite(price) or not (0 < price < 1000):
                raise ValueError("TAIFEX_ROW_INVALID")
            if day in all_rows and all_rows[day] != price:
                raise ValueError("TAIFEX_DUPLICATE_CONFLICT")
            if day < now.date() or (day == now.date() and now.time() >= dt.time(14, 0)):
                all_rows[day] = price
    ordered = sorted(all_rows)
    if not ordered:
        raise ValueError("TAIFEX_NO_PIT_ELIGIBLE_OBSERVATION")
    latest = ordered[-1]
    # Avoid using an ancient month as if it were an active risk observation.
    if (now.date() - latest).days > 10:
        raise ValueError("TAIFEX_OBSERVATION_TOO_OLD")
    previous = ordered[-2] if len(ordered) > 1 else None
    prior3 = ordered[-4] if len(ordered) >= 4 else None
    prior5 = ordered[-6] if len(ordered) >= 6 else None
    sha, url = proof[(latest.year, latest.month)]
    item = {
        "schema": SCHEMA, "status": "OFFICIAL_DAILY_SOURCE_VERIFIED_NOT_FRESHNESS_CLAIM",
        "source": "TAIFEX", "index": "TAIWAN_VIX",
        "source_role": "LOCAL_RISK_OBSERVATION_ONLY_NO_OVERSEAS_MODEL_INPUT",
        "source_url": url, "source_raw_sha256": sha,
        "source_month": f"{latest.year:04d}{latest.month:02d}",
        "observed_at_taipei": now.isoformat(),
        "vix_session_date": latest.isoformat(), "observation_time_taipei": "13:45:00",
        "vix_1345": all_rows[latest],
        "prior_session_date": previous.isoformat() if previous else None,
        "prior_1345": all_rows[previous] if previous else None,
        "change_1d_points": round(all_rows[latest] - all_rows[previous], 4) if previous else None,
        "change_3d_points": round(all_rows[latest] - all_rows[prior3], 4) if prior3 else None,
        "change_5d_points": round(all_rows[latest] - all_rows[prior5], 4) if prior5 else None,
        "intraday_realtime": False, "formal_forecast": False,
        "model_score_authority": False, "selection_authority": False,
        "trading_authority": False, "broker_execution": False,
    }
    item["receipt_sha256"] = canonical(item)
    return item


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--history-dir", type=Path, required=True)
    args = a.parse_args()
    now = dt.datetime.now(TZ)
    previous_month_end = now.date().replace(day=1) - dt.timedelta(days=1)
    periods = ((previous_month_end.year, previous_month_end.month), (now.year, now.month))
    sources = []
    for year, month in periods:
        rows, raw_sha, url = download_month(year, month)
        sources.append((year, month, rows, raw_sha, url))
    receipt = build(now, sources)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists():
        old = json.loads(args.out.read_text(encoding="utf-8"))
        if (old.get("schema") == SCHEMA and old.get("receipt_sha256") ==
                canonical({k: v for k, v in old.items() if k != "receipt_sha256"}) and
                all(old.get(k) == receipt.get(k) for k in
                    ("vix_session_date", "vix_1345", "prior_session_date",
                     "prior_1345", "source_raw_sha256"))):
            print(json.dumps({"status": "TAIFEX_SOURCE_UNCHANGED",
                              "date": receipt["vix_session_date"]}))
            return
    text = json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    history = args.history_dir / (
        receipt["vix_session_date"].replace("-", "") + "_" +
        receipt["receipt_sha256"][:16] + ".json")
    history.parent.mkdir(parents=True, exist_ok=True)
    if history.exists() and history.read_text(encoding="utf-8") != text:
        raise ValueError("TAIFEX_IMMUTABLE_HISTORY_CONFLICT")
    history.write_text(text, encoding="utf-8")
    args.out.write_text(text, encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "date": receipt["vix_session_date"],
                      "close": receipt["vix_1345"], "sha256": receipt["receipt_sha256"]}))


if __name__ == "__main__":
    main()
