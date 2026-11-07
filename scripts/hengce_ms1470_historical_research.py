#!/usr/bin/env python3
"""HENGCE historical branch-1470 research backfill; never changes the EOD vessel.

Historical Sponsor Pro objects are read through the *existing* FinMindClient.
Licensed source parquet is temporary and never committed. Aggregated stock/week
and stock/month research outputs MUST be kept outside the public repository.
This is a retrospective observational dataset, not a proprietary position book.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import math
import os
import re
import tempfile
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SOURCE = "TaiwanStockTradingDailyReportSecIdAgg"
BRANCH = "1470"
FIRST_AVAILABLE = date(2021, 6, 30)
# TWSE 2026 official trading calendar; no-trade settlement dates must NOT be
# misclassified as failed vendor downloads.
# https://www.twse.com.tw/holidaySchedule/holidaySchedule?response=html
NONTRADING_2026 = frozenset({
    "2026-01-01", "2026-02-12", "2026-02-13", "2026-02-16",
    "2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20",
    "2026-02-27", "2026-04-03", "2026-04-06", "2026-05-01",
    "2026-06-19", "2026-09-25", "2026-09-28", "2026-10-09",
    "2026-10-26", "2026-12-25",
})
FIELDS = ("date", "stock_id", "securities_trader_id", "buy_volume", "sell_volume")
SCHEMA = "HENGCE_MS1470_HISTORICAL_RESEARCH_BACKFILL_V1"
REPO_ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def normalize_ticker(value: object) -> str:
    raw = str(value).strip()
    if re.fullmatch(r"\d+(?:\.0+)?", raw):
        raw = raw.split(".")[0]
        if len(raw) <= 4:
            raw = raw.zfill(4)
    return raw


def research_output_dir(value: str) -> Path:
    output = Path(value).expanduser().resolve()
    if output == REPO_ROOT or REPO_ROOT in output.parents:
        raise ValueError("LICENSED_RESEARCH_OUTPUT_MUST_REMAIN_OUTSIDE_PUBLIC_REPOSITORY")
    output.mkdir(parents=True, exist_ok=True)
    return output


def weekdays(start: date, end: date):
    # Do not infer the Taiwan local date from the runner's UTC clock.
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo("Asia/Taipei")).date()
    if start.year != 2026 or end.year != 2026:
        raise ValueError("THIS_CALENDAR_VALIDATED_ONLY_FOR_2026")
    if start < FIRST_AVAILABLE or end >= today or start > end:
        raise ValueError("INVALID_HISTORICAL_DATE_RANGE")
    day = start
    while day <= end:
        if day.weekday() < 5 and day.isoformat() not in NONTRADING_2026:
            yield day
        day += timedelta(days=1)


async def _download(target: str, path: Path) -> None:
    from finmind_mcp.client import FinMindClient
    client = FinMindClient()
    signed_url = await client.storage_object_url(SOURCE, target)
    await client.download(signed_url, path)


def _read_date(day: date):
    """Return (ticker, buy_shares, sell_shares) strictly for the named branch."""
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    iso = day.isoformat()
    with tempfile.TemporaryDirectory(prefix="hengce-finmind-private-ms1470-") as tmp:
        raw = Path(tmp) / "source.parquet"
        asyncio.run(_download(iso, raw))
        if not raw.is_file() or not raw.stat().st_size:
            raise RuntimeError("EMPTY_VENDOR_FILE")
        physical_sha = sha256(raw)
        parquet = pq.ParquetFile(raw)
        missing = set(FIELDS) - set(parquet.schema_arrow.names)
        if missing:
            raise RuntimeError("REQUIRED_SCHEMA_MISSING")
        table = parquet.read(columns=list(FIELDS))
        if table.num_rows <= 0:
            raise RuntimeError("EMPTY_VENDOR_TABLE")
        observed_dates = {str(x)[:10] for x in pc.unique(table["date"]).to_pylist() if x is not None}
        if observed_dates != {iso}:
            raise RuntimeError("VENDOR_DATE_MISMATCH")

        ids = pc.utf8_trim_whitespace(pc.cast(table["securities_trader_id"], pa.string()))
        selected = table.filter(pc.equal(ids, BRANCH))
        if selected.num_rows == 0:
            raise RuntimeError("BRANCH_1470_NOT_FOUND_IN_VENDOR_OBJECT")
        df = selected.to_pandas()
        df["ticker"] = df["stock_id"].map(normalize_ticker)
        # This is a transparent four-digit proxy, NOT a verified common-share master.
        mask = df["ticker"].str.fullmatch(r"[1-9]\d{3}", na=False) & ~df["ticker"].str.startswith("91")
        df = df.loc[mask].copy()
        if df.empty:
            raise RuntimeError("NO_FOUR_DIGIT_STOCK_ROWS")
        if df["ticker"].duplicated().any():
            raise RuntimeError("DUPLICATE_BRANCH_TICKER_DATE")
        for key in ("buy_volume", "sell_volume"):
            values = pd.to_numeric(df[key], errors="coerce").to_numpy(dtype=float)
            if (~np.isfinite(values)).any() or (values < 0).any():
                raise RuntimeError("INVALID_VOLUME")
            if not np.all(np.abs(values - np.rint(values)) < 1e-6):
                raise RuntimeError("NON_INTEGER_VOLUME")
            df[key] = np.rint(values).astype(np.int64)

        items = [(r.ticker, int(r.buy_volume), int(r.sell_volume))
                 for r in df[["ticker", "buy_volume", "sell_volume"]].itertuples(index=False)]
        return items, {
            "date": iso,
            "source_rows": int(table.num_rows),
            "branch_rows": int(selected.num_rows),
            "four_digit_proxy_rows": len(items),
            "source_physical_sha256": physical_sha,
            "status": "VALIDATED",
        }


def _write_csv(path: Path, keys: tuple[str, str], totals: dict) -> dict:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([*keys, "BuyShares", "SellShares", "NetShares", "DaysObserved"])
        for (period, ticker), (buy, sell, days) in sorted(totals.items()):
            writer.writerow([period, ticker, buy, sell, buy - sell, days])
    return {"name": path.name, "rows": len(totals), "sha256": sha256(path)}


def backfill(start: date, end: date, output: Path, *, strict: bool = False) -> dict:
    if not os.environ.get("FINMIND_TOKEN"):
        raise RuntimeError("FINMIND_TOKEN_UNAVAILABLE_IN_RUNTIME")
    dates = list(weekdays(start, end))
    if not dates:
        raise ValueError("NO_WEEKDAYS_IN_RANGE")
    week = defaultdict(lambda: [0, 0, 0])
    month = defaultdict(lambda: [0, 0, 0])
    validated = []
    failed = []
    for day in dates:
        try:
            items, receipt = _read_date(day)
        except Exception as exc:
            # Never log exception messages: upstream errors could contain signed URLs.
            failed.append({"date": day.isoformat(), "error_type": type(exc).__name__})
            print(json.dumps({"date": day.isoformat(), "status": "SOURCE_FAILED",
                              "error_type": type(exc).__name__}), flush=True)
            if strict:
                break
            continue
        friday = (day + timedelta(days=4 - day.weekday())).isoformat()
        monthly = day.strftime("%Y-%m")
        for ticker, buy, sell in items:
            for bucket, label in ((week, friday), (month, monthly)):
                accum = bucket[label, ticker]
                accum[0] += buy
                accum[1] += sell
                accum[2] += 1
        validated.append(receipt)
        print(json.dumps({"date": day.isoformat(), "status": "VALIDATED",
                          "source_rows": receipt["source_rows"],
                          "branch_rows": receipt["branch_rows"]}), flush=True)

    summary = {
        "system": "HENGCE",
        "schema": SCHEMA,
        "source_dataset": SOURCE,
        "source_plan": "SponsorPro",
        "broker_branch_id": BRANCH,
        "broker_owns_trades": False,
        "study_start": start.isoformat(),
        "study_end": end.isoformat(),
        "status": "COMPLETE_REQUESTED_TRADING_DATES" if not failed else "PARTIAL_UNVERIFIED_MISSING_DATES",
        "weekdays_requested": len(dates),
        "expected_trading_sessions": len(dates),
        "twse_trading_calendar_source": "https://www.twse.com.tw/holidaySchedule/holidaySchedule?response=html",
        "excluded_2026_holidays": sorted(x for x in NONTRADING_2026 if start.isoformat() <= x <= end.isoformat()),
        "successful_source_dates": len(validated),
        "failed_source_dates": failed,
        "source_audit": validated,
        "historical_source_revision_class": "RETROSPECTIVE_VENDOR_SNAPSHOT_NON_PIT",
        "volume_unit": "shares_from_vendor_fields; no conversion to lots",
        "stock_universe": "FOUR_DIGIT_NON_91XX_PROXY_NOT_VERIFIED_ORDINARY_SHARES",
        "twse_trading_calendar_audited": True,
        "interpretation": "broker_branch_customer_orders_not_proprietary_holdings",
        "raw_vendor_rows_persisted": False,
        "vendor_raw_storage": "temporary_directory_deleted_per_day",
        "same_governed_eod_modified": False,
        "parallel_production_vessel_created": False,
        "model_authority": False,
        "trading_authority": False,
        "capital_authority": False,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    summary["derived_outputs"] = [
        _write_csv(output / "ms1470_weekly_aggregate.csv", ("WeekEndingFriday", "Ticker"), week),
        _write_csv(output / "ms1470_monthly_aggregate.csv", ("Month", "Ticker"), month),
    ]
    with (output / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
    print(json.dumps({k: summary[k] for k in
                      ("status", "study_start", "study_end", "weekdays_requested",
                       "successful_source_dates", "failed_source_dates")},
                     ensure_ascii=False), flush=True)
    return summary


def self_test() -> None:
    assert normalize_ticker(" 2330 ") == "2330"
    assert normalize_ticker("7") == "0007"
    assert (date(2026, 1, 2) + timedelta(days=4 - date(2026, 1, 2).weekday())).isoformat() == "2026-01-02"
    assert list(weekdays(date(2026, 2, 11), date(2026, 2, 23))) == [date(2026, 2, 11), date(2026, 2, 23)]
    assert BRANCH == "1470"
    assert SOURCE == "TaiwanStockTradingDailyReportSecIdAgg"
    print('{"self_test":"PASS","production_eod_changed":false}')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=("self-test", "backfill"))
    parser.add_argument("--start", default="2026-01-02")
    parser.add_argument("--end", default="2026-11-06")
    parser.add_argument("--output-dir")
    parser.add_argument("--strict", action="store_true",
                        help="Fail fast on first unavailable vendor object; useful for probe")
    args = parser.parse_args()
    if args.mode == "self-test":
        self_test()
        return 0
    if not args.output_dir:
        parser.error("--output-dir is required for backfill")
    output = research_output_dir(args.output_dir)
    result = backfill(date.fromisoformat(args.start), date.fromisoformat(args.end),
                      output, strict=args.strict)
    return 0 if not result["failed_source_dates"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
