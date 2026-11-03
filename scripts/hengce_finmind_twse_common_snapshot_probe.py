#!/usr/bin/env python3
"""Research-only FinMind -> TWSE listed-common snapshot audit.

Purpose
-------
Validate that the paid FinMind real-time snapshot can cover the current TWSE
listed-common-stock universe without treating every four-digit FinMind instrument
as a TWSE common stock.

Governance
----------
- TWSE listed-company basic data is the issuer-universe source for this audit.
- TDR rows are explicitly excluded from that issuer universe before coverage is
  assessed; they are not silently treated as common stock.
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
TDR_INDUSTRY_CODE = "91"


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
            "User-Agent": "HENGCE-TWSE-COMMON-AUDIT/1.1",
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


def _is_tdr(row: dict[str, Any]) -> tuple[bool, dict[str, bool]]:
    industry = str(row.get("產業別") or "").strip()
    short_name = str(row.get("公司簡稱") or "").strip().upper()
    full_name = str(row.get("公司名稱") or "").strip().upper()

    markers = {
        "industry_91": industry == TDR_INDUSTRY_CODE,
        "short_name_dr": "-DR" in short_name,
        "full_name_depositary_receipt": "存託憑證" in full_name,
    }
    return any(markers.values()), markers


def _twse_common_universe(
    master_rows: list[dict[str, Any]],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    common_codes: list[str] = []
    tdr_codes: list[str] = []
    tdr_marker_rows: list[dict[str, Any]] = []

    for row in master_rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get("公司代號") or "").strip()
        issued = str(row.get("已發行普通股數或TDR原股發行股數") or "").strip()
        if not FOUR_DIGIT.fullmatch(code) or issued in ("", "0"):
            continue

        is_tdr, markers = _is_tdr(row)
        if is_tdr:
            tdr_codes.append(code)
            tdr_marker_rows.append(
                {
                    "code": code,
                    "short_name": str(row.get("公司簡稱") or "").strip(),
                    "industry": str(row.get("產業別") or "").strip(),
                    "markers": markers,
                }
            )
            continue
        common_codes.append(code)

    all_codes = common_codes + tdr_codes
    if len(all_codes) != len(set(all_codes)):
        raise RuntimeError("duplicate TWSE company codes in official master")
    if not tdr_codes:
        raise RuntimeError("TWSE master unexpectedly produced zero TDR rows")

    # The official issuer table has multiple independent TDR indicators. A
    # disagreement is surfaced in the receipt rather than silently ignored.
    return sorted(common_codes), sorted(tdr_codes), sorted(
        tdr_marker_rows, key=lambda x: x["code"]
    )


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
    common_codes, tdr_codes, tdr_marker_rows = _twse_common_universe(master_rows)
    if not common_codes:
        raise RuntimeError("TWSE master produced an empty common-stock universe")

    common_set = set(common_codes)
    tdr_set = set(tdr_codes)
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

    covered = sorted(common_set & set(snapshot_map))
    missing = sorted(common_set - set(snapshot_map))
    current = sorted(
        code
        for code in covered
        if _date_text(snapshot_map[code]).startswith(market_date)
    )
    stale = sorted(set(covered) - set(current))
    four_digit_snapshot = sorted(code for code in snapshot_map if FOUR_DIGIT.fullmatch(code))
    extra_four_digit = sorted(set(four_digit_snapshot) - common_set)
    tdr_present_in_snapshot = sorted(tdr_set & set(snapshot_map))

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
    tdr_marker_disagreements = [
        row
        for row in tdr_marker_rows
        if len({bool(v) for v in row["markers"].values()}) > 1
    ]

    receipt = {
        "schema": "HENGCE_FINMIND_TWSE_COMMON_SNAPSHOT_AUDIT_V2",
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
            "positive issued common/TDR-underlying share field; TDR excluded by "
            "official industry/name markers before common-stock coverage audit"
        ),
        "twse_tdr_excluded_count": len(tdr_codes),
        "twse_tdr_excluded_codes": tdr_codes,
        "twse_tdr_marker_disagreement_count": len(tdr_marker_disagreements),
        "twse_tdr_marker_disagreement_sample": tdr_marker_disagreements[:20],
        "twse_tdr_present_in_finmind_count": len(tdr_present_in_snapshot),
        "twse_common_master_count": len(common_codes),
        "twse_common_master_codes_sha256": _sha256_lines(common_codes),
        "twse_common_covered_count": len(covered),
        "twse_common_current_date_count": len(current),
        "twse_common_stale_count": len(stale),
        "twse_common_missing_count": len(missing),
        "twse_common_coverage_ratio": round(len(covered) / len(common_codes), 6),
        "twse_common_current_date_ratio": round(len(current) / len(common_codes), 6),
        "extra_four_digit_not_in_twse_common_count": len(extra_four_digit),
        "missing_common_sample": missing[:20],
        "stale_common_sample": stale[:20],
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
    if len(common_codes) < 900:
        raise RuntimeError("TWSE common-stock master unexpectedly small")
    if not date_values or not latest_text or not latest_text.startswith(market_date):
        raise RuntimeError("FinMind snapshot has no current-market-date observation")
    if len(covered) < 900:
        raise RuntimeError("FinMind/TWSE common-stock intersection unexpectedly small")

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
