#!/usr/bin/env python3
"""FinMind -> TWSE listed-common aggregate shadow vessel.

The paid FinMind full snapshot is held only in runner memory. The persistent
output is aggregate/derived market context plus coverage/freshness receipts; no
per-security licensed quote rows are written.

Authority: provisional intraday price/liquidity shadow context only. No formal
metric, detector-input, EOD, Escape-state, selection, model, source-promotion,
or trading authority is created by this script.
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
METRIC_CONTRACT_SHA256 = "1d93c171b0b06d49eef19e0bf63e3b086fc366052d6bbc45516928c672f47281"
INTRADAY_METRIC_ROLE = "PROVISIONAL_PRICE_LIQUIDITY_CONTEXT_ONLY"


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
    current = sum(bool(r["current_market_date"]) for r in rows)
    return {
        "constituent_count": len(rows),
        "current_market_date_count": current,
        "current_market_date_ratio": round(current / len(rows), 8) if rows else None,
        "stale_or_noncurrent_count": len(rows) - current,
        "return_observed_count": len(returns),
        "advance_count": adv,
        "decline_count": dec,
        "flat_count": flat,
        "advance_share_directional": round(adv / directional, 8) if directional else None,
        "net_breadth": adv - dec,
        "equal_weight_change_rate": round(fmean(returns), 8) if returns else None,
        "total_amount_observed_count": len(trade_values),
        "total_volume_observed_count": len(trade_volumes),
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
    stale_codes: list[str] = []
    latest_timestamp: str | None = None
    for code in sorted(active_required):
        row = snapshot_map[code]
        stamp = _date_text(row)
        if stamp and (latest_timestamp is None or stamp > latest_timestamp):
            latest_timestamp = stamp
        current_market_date = stamp.startswith(market_date)
        if not current_market_date:
            stale_codes.append(code)
        # Frozen governance: never reinterpret a stale per-security row as
        # today's zero return or zero turnover. Until a second PIT-safe source
        # proves its session status, it remains unknown and contributes NULL.
        derived_rows.append(
            {
                "industry": industries.get(code, "UNKNOWN"),
                "current_market_date": current_market_date,
                "today_change_rate": _num(row.get("change_rate")) if current_market_date else None,
                "today_total_amount": _num(row.get("total_amount")) if current_market_date else None,
                "today_total_volume": _num(row.get("total_volume")) if current_market_date else None,
            }
        )

    if not latest_timestamp or not latest_timestamp.startswith(market_date):
        raise RuntimeError("FinMind packet has no current-market-date observation")

    by_industry: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in derived_rows:
        by_industry[row["industry"]].append(row)

    market_summary = _summarize(derived_rows)
    authority_boundary = {
        "metric_contract_sha256": METRIC_CONTRACT_SHA256,
        "intraday_metric_role": INTRADAY_METRIC_ROLE,
        "price_liquidity_shadow_only": True,
        "feature_detector_input_authority": False,
        "formal_metric_authority": False,
        "rolling_metric_authority": False,
        "one_day_change_rate_may_substitute_locked_ew_return": False,
        "missing_as_zero_forbidden": True,
        "source_binding_promotion_authority": False,
    }
    context = {
        "schema": "HENGCE_ESCAPE_FINMIND_TWSE_COMMON_AGGREGATE_SHADOW_V2",
        "generated_at_taipei": generated.isoformat(),
        "market_date": market_date,
        "source": "FinMind taiwan_stock_tick_snapshot + TWSE listed-company master",
        "authority": AUTHORITY,
        **authority_boundary,
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
        "current_market_date_count": market_summary["current_market_date_count"],
        "current_market_date_ratio": market_summary["current_market_date_ratio"],
        "stale_or_noncurrent_count": len(stale_codes),
        "stale_or_noncurrent_sample": stale_codes[:20],
        "latest_source_timestamp": latest_timestamp,
        "market": market_summary,
        "industry": {key: _summarize(by_industry[key]) for key in sorted(by_industry)},
        "per_security_rows_persisted": False,
        "raw_finmind_rows_persisted": False,
        "stale_rows_neutralized_as_zero": False,
        "formal_eod_state_creation": False,
        "formal_escape_state_creation": False,
        "selection_authority": False,
        "model_authority": False,
        "trading_authority": False,
    }

    context_bytes = json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    context["payload_sha256"] = hashlib.sha256(context_bytes).hexdigest()

    status = {
        "schema": "HENGCE_ESCAPE_FINMIND_TWSE_COMMON_SHADOW_STATUS_V2",
        "generated_at_taipei": generated.isoformat(),
        "state": "SHADOW_CONTEXT_READY_NO_FORMAL_AUTHORITY",
        "healthy_transport": True,
        "current_market_date_observed": True,
        "active_universe_transport_full_coverage": True,
        **authority_boundary,
        "current_market_date_count": market_summary["current_market_date_count"],
        "current_market_date_ratio": market_summary["current_market_date_ratio"],
        "stale_or_noncurrent_count": len(stale_codes),
        "stale_or_noncurrent_sample": stale_codes[:20],
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
        "stale_rows_neutralized_as_zero": False,
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
