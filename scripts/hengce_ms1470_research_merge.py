#!/usr/bin/env python3
"""Merge independently audited historical MS1470 branch month research artifacts.

No proprietary positions, raw licensed broker rows, or new trading permissions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from datetime import date, timedelta
from hengce_ms1470_historical_research import NONTRADING_2026


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for part in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def csv_data(path: Path, key_col: str):
    with path.open(encoding="utf-8", newline="") as fp:
        for x in csv.DictReader(fp):
            yield (x[key_col], x["Ticker"]), (
                int(x["BuyShares"]),
                int(x["SellShares"]),
                int(x["DaysObserved"]),
            )


def main() -> None:
    cli = argparse.ArgumentParser()
    cli.add_argument("--input-root", required=True)
    cli.add_argument("--output-dir", required=True)
    args = cli.parse_args()
    root = Path(args.input_root).resolve()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    receipt_paths = sorted(root.glob("*/manifest.json"))
    if not receipt_paths:
        raise RuntimeError("NO_MONTHLY_SHARDS")
    periods = {"weekly": defaultdict(lambda: [0, 0, 0]),
               "monthly": defaultdict(lambda: [0, 0, 0])}
    date_set = set()
    month_receipts = []
    problems = []
    for rp in receipt_paths:
        receipt = json.loads(rp.read_text(encoding="utf-8"))
        if receipt["schema"] != "HENGCE_MS1470_HISTORICAL_RESEARCH_BACKFILL_V1":
            raise RuntimeError("INVALID_INPUT_SCHEMA")
        month = rp.parent.name
        month_receipts.append({
            "artifact": month,
            "status": receipt["status"],
            "start": receipt["study_start"],
            "end": receipt["study_end"],
            "expected_weekdays": receipt["weekdays_requested"],
            "downloaded_days": receipt["successful_source_dates"],
            "failed_source_dates": receipt["failed_source_dates"],
        })
        problems.extend(receipt["failed_source_dates"])
        for row in receipt["source_audit"]:
            if row["date"] in date_set:
                raise RuntimeError("DUPLICATE_SOURCE_DATE_BETWEEN_SHARDS")
            date_set.add(row["date"])
        for period, field, name in (
            ("weekly", "WeekEndingFriday", "ms1470_weekly_aggregate.csv"),
            ("monthly", "Month", "ms1470_monthly_aggregate.csv"),
        ):
            p = rp.parent / name
            expected = [o["sha256"] for o in receipt["derived_outputs"] if o["name"] == name]
            if len(expected) != 1 or not p.is_file() or sha256(p) != expected[0]:
                raise RuntimeError("DERIVED_SHARD_HASH_MISMATCH")
            for key, values in csv_data(p, field):
                target = periods[period][key]
                for i, v in enumerate(values):
                    target[i] += v

    outputs = {}
    for period, field in (("weekly", "WeekEndingFriday"), ("monthly", "Month")):
        p = output / ("ms1470_" + period + "_aggregate_2026.csv")
        with p.open("w", encoding="utf-8", newline="") as fp:
            w = csv.writer(fp)
            w.writerow([field, "Ticker", "BuyShares", "SellShares", "NetShares", "DaysObserved"])
            for (label, ticker), (buy, sell, n) in sorted(periods[period].items()):
                w.writerow([label, ticker, buy, sell, buy - sell, n])
        outputs[period] = {"path": p.name, "sha256": sha256(p),
                           "rows": len(periods[period])}

    calendar_start, calendar_end = date(2026, 1, 2), date(2026, 11, 6)
    expected_sessions = set()
    day = calendar_start
    while day <= calendar_end:
        if day.weekday() < 5 and day.isoformat() not in NONTRADING_2026:
            expected_sessions.add(day.isoformat())
        day += timedelta(days=1)
    missing_sessions = sorted(expected_sessions - date_set)
    unexpected_sessions = sorted(date_set - expected_sessions)
    complete = (len(month_receipts) == 11 and not problems and
                not missing_sessions and not unexpected_sessions)

    result = {
        "system": "HENGCE",
        "artifact": "MS1470_2026_RESEARCH_MERGE",
        "status": ("COMPLETE_VERIFIED_2026_YTD_TRADING_SESSIONS" if complete
                   else "PARTIAL_DO_NOT_TREAT_AS_FULL_YEAR"),
        "source_period": "2026-01-02_to_2026-11-06",
        "months_found": len(month_receipts),
        "unique_source_days": len(date_set),
        "twse_trading_calendar_source": "https://www.twse.com.tw/holidaySchedule/holidaySchedule?response=html",
        "expected_trading_days": len(expected_sessions),
        "missing_trading_days": missing_sessions,
        "unexpected_source_days": unexpected_sessions,
        "shards": month_receipts,
        "missing_or_failed_source_dates": problems,
        "outputs": outputs,
        "raw_broker_rows_persisted": False,
        "source_revision_class": "RETROSPECTIVE_VENDOR_SNAPSHOT_NON_PIT",
        "broker_branch_not_proprietary": True,
        "public_repository_updated_with_vendor_rows": False,
        "trading_authority": False,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    with (output / "manifest_merged_2026.json").open("w", encoding="utf-8") as fp:
        json.dump(result, fp, indent=2, sort_keys=True, ensure_ascii=False)
        fp.write("\n")
    print(json.dumps({"status": result["status"], "months": len(month_receipts),
                      "valid_dates": len(date_set), "failed": len(problems)}))


if __name__ == "__main__":
    main()
