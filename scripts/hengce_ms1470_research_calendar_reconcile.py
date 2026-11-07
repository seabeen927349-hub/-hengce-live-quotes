#!/usr/bin/env python3
"""Reclassify TWSE 2026 closed-market dates in already downloaded research shards.

Do NOT re-download a costly/large licensed dataset just to account for holidays.
Never delete or silently absorb an actual trading-day failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

from hengce_ms1470_historical_research import NONTRADING_2026

OFFICIAL = "https://www.twse.com.tw/holidaySchedule/holidaySchedule?response=html"


def trading_dates(start: date, end: date) -> set[str]:
    d = start
    result = set()
    while d <= end:
        if d.weekday() < 5 and d.isoformat() not in NONTRADING_2026:
            result.add(d.isoformat())
        d += timedelta(days=1)
    return result


def main() -> None:
    cli = argparse.ArgumentParser()
    cli.add_argument("--input-root", required=True)
    args = cli.parse_args()
    root = Path(args.input_root)
    manifests = sorted(root.glob("*/manifest.json"))
    if not manifests:
        raise RuntimeError("NO_MONTH_ARTIFACTS_TO_RECONCILE")

    for path in manifests:
        original_bytes = path.read_bytes()
        rec = json.loads(original_bytes)
        if rec.get("schema") != "HENGCE_MS1470_HISTORICAL_RESEARCH_BACKFILL_V1":
            raise RuntimeError("RECEIPT_SCHEMA_MISMATCH")
        start, end = date.fromisoformat(rec["study_start"]), date.fromisoformat(rec["study_end"])
        if start.year != 2026 or end.year != 2026:
            raise RuntimeError("RECEIPT_OUTSIDE_OFFICIAL_2026_CALENDAR")

        expected = trading_dates(start, end)
        observed = {x["date"] for x in rec["source_audit"]}
        if len(observed) != len(rec["source_audit"]) or not observed <= expected:
            raise RuntimeError("DUPLICATE_OR_OUT_OF_CALENDAR_SOURCE_DATE")
        failed = rec["failed_source_dates"]
        skipped = sorted({row["date"] for row in failed if row["date"] in NONTRADING_2026})
        remaining = [row for row in failed if row["date"] not in NONTRADING_2026]
        missing = sorted(expected - observed)
        if set(row["date"] for row in remaining) != set(missing):
            # Partial audits can still be preserved, but must not be certified.
            rec["calendar_unexplained_missing_dates"] = missing
            rec["status"] = "PARTIAL_UNVERIFIED_MISSING_DATES"
        elif not missing:
            rec["status"] = "COMPLETE_REQUESTED_TRADING_DATES"
        else:
            rec["status"] = "PARTIAL_UNVERIFIED_MISSING_DATES"

        rec["original_receipt_sha256_before_calendar_reconciliation"] = hashlib.sha256(original_bytes).hexdigest()
        rec["original_receipt_status_before_calendar_reconciliation"] = json.loads(original_bytes)["status"]
        rec["calendar_reconciled_closed_market_dates"] = skipped
        rec["calendar_reconciliation_method"] = "OFFICIAL_TWSE_2026_NO_TRADE_DATES"
        rec["twse_trading_calendar_source"] = OFFICIAL
        rec["twse_trading_calendar_audited"] = True
        rec["expected_trading_sessions"] = len(expected)
        rec["weekdays_requested"] = len(expected)
        rec["failed_source_dates"] = remaining
        rec["successful_source_dates"] = len(observed)
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=2, sort_keys=True)+"\n",encoding="utf-8")
        print(json.dumps({"shard":path.parent.name,"status":rec["status"],
                          "expected_trading_sessions":len(expected),
                          "observed":len(observed),"holidays_reclassified":len(skipped),
                          "missing_trading_sessions":missing},ensure_ascii=False),flush=True)


if __name__ == "__main__":
    main()
