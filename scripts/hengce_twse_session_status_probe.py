#!/usr/bin/env python3
"""Research-only TWSE official status probe for noncurrent FinMind quotes.

This probe is deliberately narrow: it queries TWSE public OpenAPI suspension
and current daily-close datasets, then reports only whether target securities
can be located and the matching public rows. Absence from a dataset is NOT
reinterpreted as zero trading, suspension, or a valid metric observation.

No Escape, metric, selection, model, EOD, or trading authority is created.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")
SUSPENSION_URL = "https://openapi.twse.com.tw/v1/exchangeReport/TWTAWU"
DAILY_CLOSE_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
DEFAULT_TARGETS = ["1413", "1423", "1538", "2321", "3593", "5906"]


def fetch(url: str) -> list[dict[str, Any]]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "HENGCE-TWSE-SESSION-STATUS-PROBE/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.load(response)
    if not isinstance(payload, list):
        raise RuntimeError(f"unexpected TWSE payload shape for {url}")
    return [row for row in payload if isinstance(row, dict)]


def row_mentions_target(row: dict[str, Any], target: str) -> bool:
    # Exact scalar-value matching avoids guessing a field name while the probe
    # is still learning the official schema.
    return any(str(value).strip() == target for value in row.values())


def compact(row: dict[str, Any]) -> dict[str, str]:
    # Public TWSE row only. Keep scalar nonempty values; no bulk source dump.
    out: dict[str, str] = {}
    for key, value in row.items():
        text = str(value).strip()
        if text:
            out[str(key)] = text
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--targets", nargs="*", default=DEFAULT_TARGETS)
    args = p.parse_args()
    targets = sorted({str(x).strip() for x in args.targets if str(x).strip()})
    if not targets:
        raise RuntimeError("no target codes")

    suspension_rows = fetch(SUSPENSION_URL)
    close_rows = fetch(DAILY_CLOSE_URL)

    result: dict[str, Any] = {
        "schema": "HENGCE_TWSE_SESSION_STATUS_PROBE_V1",
        "queried_at_taipei": datetime.now(TAIPEI).isoformat(),
        "sources": {
            "suspension": SUSPENSION_URL,
            "daily_close": DAILY_CLOSE_URL,
        },
        "source_row_counts": {
            "suspension": len(suspension_rows),
            "daily_close": len(close_rows),
        },
        "source_field_names": {
            "suspension": sorted({str(k) for row in suspension_rows for k in row.keys()}),
            "daily_close": sorted({str(k) for row in close_rows for k in row.keys()}),
        },
        "targets": {},
        "absence_is_not_zero": True,
        "absence_is_not_suspension": True,
        "formal_metric_authority": False,
        "formal_escape_authority": False,
        "formal_eod_authority": False,
        "trading_authority": False,
    }

    unresolved = []
    for target in targets:
        suspension_matches = [compact(row) for row in suspension_rows if row_mentions_target(row, target)]
        close_matches = [compact(row) for row in close_rows if row_mentions_target(row, target)]
        entry = {
            "suspension_match_count": len(suspension_matches),
            "daily_close_match_count": len(close_matches),
            "suspension_matches": suspension_matches[:5],
            "daily_close_matches": close_matches[:5],
        }
        if suspension_matches:
            entry["evidence_class"] = "TWSE_SUSPENSION_DATA_MATCH"
        elif close_matches:
            entry["evidence_class"] = "TWSE_DAILY_CLOSE_DATA_MATCH"
        else:
            entry["evidence_class"] = "UNRESOLVED_BY_THESE_TWO_SOURCES"
            unresolved.append(target)
        result["targets"][target] = entry

    result["unresolved_targets"] = unresolved
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
