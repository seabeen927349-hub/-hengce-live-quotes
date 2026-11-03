#!/usr/bin/env python3
"""FinMind -> TWSE listed-common aggregate shadow vessel.

The paid FinMind full snapshot is held only in runner memory. The persistent
output is aggregate/derived market context plus coverage/freshness receipts; no
per-security licensed quote rows are written.

Authority: shadow intraday context only. No formal EOD, Escape-state, selection,
model, or trading authority is created by this script.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import fmean
from typing import Any

from finmind_mcp.client import FinMindClient

from hengce_finmind_twse_common_snapshot_probe import (
    DEFAULT_EXCEPTION_PATH,
    FINMIND_ENDPOINT,
    TAIPEI,
    _active_nontrading_exceptions,
    _date_text,
    _fetch_twse_master,
    _sid,
    _twse_common_universe,
)

AUTHORITY = "SHADOW_INTRADAY_CONTEXT_ONLY_NO_FORMAL_EOD_ESCAPE_SELECTION_MODEL_OR_TRADING_AUTHORITY"
SCOPE = "ALL_TWSE_LISTED_COMMON_STOCKS"


def _num(value: Any) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _sha_lines(values: list[str]) -> str:
    return hashlib.sha256(("\n".join(values) + "\n").encode("utf-8")).hexdigest()


def _industry_map(master_rows: list[dict[str, Any]], common_set: set[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in master_rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get("公司代號") or "").strip()
        if code in common_set:
            out[code] = str(row.get("產業別") or "UNKNOWN").strip() or "UNKNOWN"
    return out


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    returns = [float(r["today_change_rate"]) for r in rows if r["today_change_rate"] is not None]
    adv = sum(x > 0 for x in returns)
    dec = sum(x < 0 for x in returns)
    flat = sum(x == 0 for x in returns)
    directional = adv + dec
    trade_values = [float(r["today_total_amount"]) for r in rows if r["today_total_amount"] is not None]
    trade_volumes = [float(r["today_total_volume"]) for r in rows if r["today_total_volume"] is not None]
    return {
        "constituent_count": len(rows),
        "return_observed_count": len(returns),
        "advance_count": adv,
        "decline_count": dec,
        "flat_count": flat,
        "advance_share_directional": round(adv / directional, 8) if directional else None,
        "net_breadth": adv - dec,
        "equal_weight_change_rate": round(fmean(returns), 8) if returns else None,
        "trade_today_count": sum(bool(r["trade_today"]) for r in rows),
        "no_trade_today_count": sum(not bool(r["trade_today"]) for r in rows),
        "total_amount": round(sum(trade_values), 4),
        "total_volume": round(sum(trade_volumes), 4),
    }


async def collect(exception_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if not os.environ.get("FINMIND_TOKEN"):
        raise RuntimeError("FINMIND_TOKEN is missing")

    generated = datetime.now(TAIPEI)
    market_date = generated.date().isoformat()
    active_exceptions, exception_meta = _active_nontrading_exceptions(exception_path, market_date)

    client = FinMindClient()
    raw_rows = await client.query_endpoint(FINMIND_ENDPOINT, {"data_id": ""})
    if not isinstance(raw_rows, list) or not raw_rows:
        raise RuntimeError("FinMind snapshot is empty or malformed")

    master_rows, master_report_date = _fetch_twse_master()
    common_codes, tdr_codes, _ = _twse_common_universe(master_rows)
    common_set = set(common_codes)
    active_required = common_set - active_exceptions
    industries = _industry_map(master_rows, common_set)

    snapshot_map: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        code = _sid(row)
        if not code:
            continue
        if code in snapshot_map:
            duplicates.add(code)
        snapshot_map[code] = row
    if duplicates:
        raise RuntimeError(f"duplicate FinMind IDs:{sorted(duplicates)[:20]}")

    snapshot_set = set(snapshot_map)
    missing = common_set - snapshot_set
    unexpected_missing = sorted(missing - active_exceptions)
    exempt_missing = sorted(missing & active_exceptions)
    if unexpected_missing:
        raise RuntimeError(f"unexpected TWSE common-stock coverage gaps:{unexpected_missing}")
    if not active_required.issubset(snapshot_set):
        raise RuntimeError("active TWSE common-stock universe is not fully covered")

    derived_rows: list[dict[str, Any]] = []
    latest_timestamp: str | None = None
    for code in sorted(active_required):
        row = snapshot_map[code]
        stamp = _date_text(row)
        if stamp and (latest_timestamp is None or stamp > latest_timestamp):
            latest_timestamp = stamp
        trade_today = stamp.startswith(market_date)
        raw_change = _num(row.get("change_rate"))
        # A stale per-security row describes its last trading session. Never carry
        # that old return or turnover into today's breadth/flow context.
        today_change = raw_change if trade_today else 0.0
        today_amount = _num(row.get("total_amount")) if trade_today else 0.0
        today_volume = _num(row.get("total_volume")) if trade_today else 0.0
        derived_rows.append(
            {
                "industry": industries.get(code, "UNKNOWN"),
                "trade_today": trade_today,
                "today_change_rate": today_change,
                "today_total_amount": today_amount,
                "today_total_volume": today_volume,
            }
        )

    if not latest_timestamp or not latest_timestamp.startswith(market_date):
        raise RuntimeError("FinMind packet has no current-market-date observation")

    by_industry: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in derived_rows:
        by_industry[row["industry"]].append(row)

    context = {
        "schema": "HENGCE_ESCAPE_FINMIND_TWSE_COMMON_AGGREGATE_SHADOW_V1",
        "generated_at_taipei": generated.isoformat(),
        "market_date": market_date,
        "source": "FinMind taiwan_stock_tick_snapshot + TWSE listed-company master",
        "authority": AUTHORITY,
        "monitoring_universe": SCOPE,
        "exchange": "TWSE",
        "security_scope": "COMMON_STOCK_EX_TDR",
        "tpex_included": False,
        "universe_count": len(common_codes),
        "active_required_count": len(active_required),
        "active_universe_sha256": _sha_lines(sorted(active_required)),
        "excluded_tdr_count": len(tdr_codes),
        "active_nontrading_exception_count": len(active_exceptions),
        "exempt_missing_count": len(exempt_missing),
        "exempt_missing": exempt_missing,
        "latest_source_timestamp": latest_timestamp,
        "market": _summarize(derived_rows),
        "industry": {key: _summarize(by_industry[key]) for key in sorted(by_industry)},
        "per_security_rows_persisted": False,
        "raw_finmind_rows_persisted": False,
        "formal_eod_state_creation": False,
        "formal_escape_state_creation": False,
        "selection_authority": False,
        "model_authority": False,
        "trading_authority": False,
    }

    context_bytes = json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    context["payload_sha256"] = hashlib.sha256(context_bytes).hexdigest()

    status = {
        "schema": "HENGCE_ESCAPE_FINMIND_TWSE_COMMON_SHADOW_STATUS_V1",
        "generated_at_taipei": generated.isoformat(),
        "state": "SHADOW_CONTEXT_READY_NO_FORMAL_AUTHORITY",
        "healthy_transport": True,
        "current_market_date_observed": True,
        "active_universe_full_coverage": True,
        "monitoring_universe": SCOPE,
        "source": "FinMind",
        "finmind_endpoint": FINMIND_ENDPOINT,
        "twse_master_report_date": master_report_date,
        "twse_common_master_count": len(common_codes),
        "active_required_count": len(active_required),
        "active_covered_count": len(active_required),
        "unexpected_missing_count": 0,
        "exempt_missing": exempt_missing,
        "latest_source_timestamp": latest_timestamp,
        "exception_governance": exception_meta,
        "context_payload_sha256": context["payload_sha256"],
        "raw_finmind_rows_persisted": False,
        "per_security_rows_persisted": False,
        "formal_escape_authority": False,
        "formal_eod_authority": False,
        "trading_authority": False,
    }
    return context, status


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--context", type=Path, required=True)
    p.add_argument("--status", type=Path, required=True)
    p.add_argument("--exceptions", type=Path, default=DEFAULT_EXCEPTION_PATH)
    args = p.parse_args()

    context, status = asyncio.run(collect(args.exceptions))
    args.context.parent.mkdir(parents=True, exist_ok=True)
    args.status.parent.mkdir(parents=True, exist_ok=True)
    args.context.write_text(json.dumps(context, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    args.status.write_text(json.dumps(status, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
