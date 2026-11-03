#!/usr/bin/env python3
"""Research-only FinMind -> TWSE listed-common snapshot audit.

Purpose
-------
Validate that the paid FinMind real-time snapshot can cover the current TWSE
listed-company universe without treating every four-digit FinMind instrument as
a TWSE common stock.

Governance
----------
- TWSE listed-company basic data is the universe source for this audit.
- FinMind raw snapshot rows are ephemeral and are never written to disk.
- Only a non-raw receipt is emitted.
- This script grants no Escape, selection, model, or trading authority.
- Operational authority thresholds are intentionally NOT introduced here; they
  must be preregistered separately before promotion beyond research capability.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from finmind_mcp.client import FinMindClient

TAIPEI = ZoneInfo("Asia/Taipei")
MASTER_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
FINMIND_ENDPOINT = "taiwan_stock_tick_snapshot"
FOUR_DIGIT = re.compile(r"[1-9]\d{3}")


def _sha256_lines(values: list[str]) -> str:
    body = "\n".join(values).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _sid(row: dict[str, Any]) -> str:
    return str(row.get("stock_id") or "").strip()


def _date_text(row: dict[str, Any]) -> str:
    return str(row.get("date") or "").strip()


def _parse_local_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=TAIPEI)
    return dt.astimezone(TAIPEI)


def _fetch_twse_master() -> tuple[list[dict[str, Any]], str | None]:
    req = urllib.request.Request(
        MASTER_URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "HENGCE-TWSE-COMMON-AUDIT/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        rows = json.load(response)
    if not isinstance(rows, list):
        raise RuntimeError("TWSE master response is not a list")
    report_dates = sorted(
        {
            str(row.get("出表日期") or "").strip()
            for row in rows
            if isinstance(row, dict) and str(row.get("出表日期") or "").strip()
        }
    )
    report_date = report_dates[-1] if report_dates else None
    return rows, report_date


def _twse_common_codes(master_rows: list[dict[str, Any]]) -> list[str]:
    codes: list[str] = []
    for row in master_rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get("公司代號") or "").strip()
        issued = str(row.get("已發行普通股數或TDR原股發行股數") or "").strip()
        if FOUR_DIGIT.fullmatch(code) and issued not in ("", "0"):
            codes.append(code)
    if len(codes) != len(set(codes)):
        raise RuntimeError("duplicate TWSE company codes in official master")
    return sorted(codes)


async def build_receipt() -> dict[str, Any]:
    if not os.environ.get("FINMIND_TOKEN"):
        raise RuntimeError("FINMIND_TOKEN is missing")

    queried_at = datetime.now(TAIPEI)
    market_date = queried_at.date().isoformat()

    client = FinMindClient()
    snapshot_rows = await client.query_endpoint(FINMIND_ENDPOINT, {"data_id": ""})
    if not isinstance(snapshot_rows, list) or not snapshot_rows:
        raise RuntimeError("FinMind snapshot is empty or malformed")

    master_rows, master_report_date = _fetch_twse_master()
    master_codes = _twse_common_codes(master_rows)
    if not master_codes:
        raise RuntimeError("TWSE master produced an empty common-stock universe")

    master_set = set(master_codes)
    snapshot_map: dict[str, dict[str, Any]] = {}
    duplicate_snapshot_ids: set[str] = set()
    for row in snapshot_rows:
        if not isinstance(row, dict):
            continue
        code = _sid(row)
        if not code:
            continue
        if code in snapshot_map:
            duplicate_snapshot_ids.add(code)
        snapshot_map[code] = row

    covered = sorted(master_set & set(snapshot_map))
    missing = sorted(master_set - set(snapshot_map))
    current = sorted(
        code
        for code in covered
        if _date_text(snapshot_map[code]).startswith(market_date)
    )
    stale = sorted(set(covered) - set(current))
    four_digit_snapshot = sorted(code for code in snapshot_map if FOUR_DIGIT.fullmatch(code))
    extra_four_digit = sorted(set(four_digit_snapshot) - master_set)

    date_values = sorted(
        {_date_text(row) for row in snapshot_map.values() if _date_text(row)}
    )
    latest_text = date_values[-1] if date_values else None
    latest_dt = _parse_local_timestamp(latest_text or "")
    latest_lag_seconds = (
        round((queried_at - latest_dt).total_seconds(), 3) if latest_dt else None
    )

    id_date_digest_lines = sorted(
        f"{code}|{_date_text(row)}" for code, row in snapshot_map.items()
    )
    field_names = sorted(
        {key for row in snapshot_rows if isinstance(row, dict) for key in row.keys()}
    )

    receipt = {
        "schema": "HENGCE_FINMIND_TWSE_COMMON_SNAPSHOT_AUDIT_V1",
        "status": "RESEARCH_CAPABILITY_OBSERVED",
        "queried_at_taipei": queried_at.isoformat(),
        "expected_market_date": market_date,
        "finmind_endpoint": FINMIND_ENDPOINT,
        "finmind_row_count": len(snapshot_rows),
        "finmind_unique_id_count": len(snapshot_map),
        "finmind_four_digit_count": len(four_digit_snapshot),
        "finmind_duplicate_id_count": len(duplicate_snapshot_ids),
        "finmind_field_names": field_names,
        "finmind_latest_timestamp": latest_text,
        "finmind_latest_lag_seconds": latest_lag_seconds,
        "finmind_id_date_digest_sha256": _sha256_lines(id_date_digest_lines),
        "twse_master_endpoint": MASTER_URL,
        "twse_master_report_date": master_report_date,
        "twse_master_definition": (
            "official TWSE listed-company basic data; four-digit company code; "
            "positive issued common/TDR-underlying share field"
        ),
        "twse_master_count": len(master_codes),
        "twse_master_codes_sha256": _sha256_lines(master_codes),
        "twse_master_covered_count": len(covered),
        "twse_master_current_date_count": len(current),
        "twse_master_stale_count": len(stale),
        "twse_master_missing_count": len(missing),
        "twse_master_coverage_ratio": round(len(covered) / len(master_codes), 6),
        "twse_master_current_date_ratio": round(len(current) / len(master_codes), 6),
        "extra_four_digit_not_in_twse_master_count": len(extra_four_digit),
        "missing_master_sample": missing[:20],
        "stale_master_sample": stale[:20],
        "extra_four_digit_sample": extra_four_digit[:20],
        "raw_snapshot_retained": False,
        "raw_twse_master_retained": False,
        "operational_thresholds_preregistered": False,
        "formal_escape_authority": False,
        "selection_authority": False,
        "model_authority": False,
        "trading_authority": False,
    }

    # Structural fail-closed checks only. These are transport/schema invariants,
    # not post-observation operational promotion thresholds.
    if len(master_codes) < 900:
        raise RuntimeError("TWSE master unexpectedly small")
    if not date_values or not latest_text or not latest_text.startswith(market_date):
        raise RuntimeError("FinMind snapshot has no current-market-date observation")
    if len(covered) < 900:
        raise RuntimeError("FinMind/TWSE intersection unexpectedly small")

    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=None)
    args = parser.parse_args()

    receipt = asyncio.run(build_receipt())
    rendered = json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2)
    print(rendered)
    if args.receipt is not None:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
