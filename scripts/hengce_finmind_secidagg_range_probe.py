#!/usr/bin/env python3
"""Outcome-blind FinMind SecIdAgg range transport probe.

This script inspects only transport/schema/coverage metadata. It does not compute
broker features, does not load forward returns, and has no model authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ENDPOINT = "https://api.finmindtrade.com/api/v4/taiwan_stock_trading_daily_report_secid_agg"
REQUIRED = {
    "date",
    "stock_id",
    "securities_trader_id",
    "buy_volume",
    "sell_volume",
    "buy_price",
    "sell_price",
}


def logical_hash(rows: list[dict]) -> str:
    h = hashlib.sha256()
    keys = sorted(REQUIRED)
    for row in sorted(rows, key=lambda r: tuple(str(r.get(k, "")) for k in ("date", "stock_id", "securities_trader_id"))):
        h.update(json.dumps({k: row.get(k) for k in keys}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--stock", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--expected-first")
    p.add_argument("--expected-last")
    p.add_argument("--expected-date-count", type=int)
    a = p.parse_args()

    token = os.environ.get("FINMIND_TOKEN", "").strip()
    if not token:
        raise SystemExit("FINMIND_TOKEN_MISSING")

    receipt = {
        "schema_version": 1,
        "authority": "DATA_TRANSPORT_FEASIBILITY_ONLY_NO_MODEL_NO_FORWARD_RETURN_AUTHORITY",
        "dataset": "TaiwanStockTradingDailyReportSecIdAgg",
        "endpoint": ENDPOINT,
        "stock_id": a.stock,
        "requested_start": a.start,
        "requested_end": a.end,
        "retrieved_at_taipei": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
        "forward_returns_inspected": False,
        "broker_feature_computed": False,
        "raw_rows_persisted": False,
        "status": "FAIL_CLOSED",
        "errors": [],
    }

    try:
        r = requests.get(
            ENDPOINT,
            params={"data_id": a.stock, "start_date": a.start, "end_date": a.end},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=180,
        )
        receipt["http_status"] = r.status_code
        r.raise_for_status()
        obj = r.json()
        receipt["api_status"] = obj.get("status") if isinstance(obj, dict) else None
        receipt["api_msg"] = obj.get("msg") if isinstance(obj, dict) else None
        rows = obj.get("data") if isinstance(obj, dict) else None
        if not isinstance(rows, list):
            raise ValueError("API_DATA_NOT_LIST")

        fields = sorted({str(k) for row in rows if isinstance(row, dict) for k in row})
        missing = sorted(REQUIRED - set(fields))
        dates = sorted({str(row.get("date")) for row in rows if isinstance(row, dict) and row.get("date")})
        stocks = sorted({str(row.get("stock_id")) for row in rows if isinstance(row, dict) and row.get("stock_id")})
        brokers = {str(row.get("securities_trader_id")) for row in rows if isinstance(row, dict) and row.get("securities_trader_id") not in (None, "")}
        receipt.update({
            "row_count": len(rows),
            "field_list": fields,
            "missing_required_fields": missing,
            "unique_date_count": len(dates),
            "first_returned_date": dates[0] if dates else None,
            "last_returned_date": dates[-1] if dates else None,
            "unique_stock_ids": stocks,
            "unique_broker_id_count": len(brokers),
            "logical_content_sha256": logical_hash(rows),
        })
        checks = {
            "nonempty": bool(rows),
            "required_schema": not missing,
            "single_requested_stock": stocks == [a.stock],
            "expected_first": (not a.expected_first) or (dates and dates[0] == a.expected_first),
            "expected_last": (not a.expected_last) or (dates and dates[-1] == a.expected_last),
            "expected_date_count": (a.expected_date_count is None) or (len(dates) == a.expected_date_count),
        }
        receipt["checks"] = checks
        receipt["status"] = "PASS_TRANSPORT_RANGE" if all(checks.values()) else "FAIL_CLOSED"
    except Exception as exc:
        receipt["errors"].append(f"{type(exc).__name__}:{exc}")

    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0 if receipt["status"] == "PASS_TRANSPORT_RANGE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
