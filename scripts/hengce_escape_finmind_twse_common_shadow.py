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
from typing import Any, Callable

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
from hengce_twse_session_status_probe import current_mis
from hengce_finmind_single_name_bridge import lookup as lookup_single_name, public_status as single_name_public_status
from hengce_finmind_single_name_membership import fetch_current_equity_membership

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


async def collect(
    exception_path: Path,
    private_quote_consumer: Callable[[Callable[[str], tuple[Any, str]]], None] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not os.environ.get("FINMIND_TOKEN"):
        raise RuntimeError("FINMIND_TOKEN is missing")

    generated = datetime.now(TAIPEI)
    market_date = generated.date().isoformat()
    market_date_compact = generated.strftime("%Y%m%d")
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

    # SINGLE-NAME QUOTE-ONLY membership is broader than Market State scope.
    # Reuse FinMind TaiwanStockInfo in this governed runner, NOT a new collector.
    # Errors affect ONLY this optional quote capability, not existing TWSE
    # Market State coverage or its approved 0.5 research-shadow contract.
    quote_membership = {}
    quote_membership_counts = {}
    quote_membership_status = "BLOCKED_MEMBERSHIP_UNVERIFIED"
    try:
        quote_membership, quote_membership_counts = fetch_current_equity_membership(
            generated.date()
        )
        quote_membership_status = "VALIDATED_CURRENT_EQUITIES"
    except Exception:
        # Never log tokens, vendor records, or silently infer listing venues.
        quote_membership_status = "BLOCKED_MEMBERSHIP_UNVERIFIED"

    # These quote values exist only during THIS SAME pre-existing snapshot run.
    # No live price, OHLC, turnover or per-stock licensed value is serialized.
    private_consumer_called = False
    if private_quote_consumer is not None and quote_membership_status.startswith("VALIDATED"):
        private_quote_consumer(
            lambda ticker: lookup_single_name(
                snapshot_map, ticker, datetime.now(TAIPEI), set(quote_membership)
            )
        )
        private_consumer_called = True

    # Public diagnostic is deliberately aggregate-only, without ticker IDs.
    watch_codes = [
        str(item.get("Ticker") or "")
        for item in json.loads(
            Path("hengce/frozen/live_symbols.json").read_text(encoding="utf-8")
        ).get("symbols", [])
    ]
    bridge_local = single_name_public_status(
        snapshot_map, watch_codes, generated, set(quote_membership)
    )
    bridge_public = {key: val for key, val in bridge_local.items() if key != "watch_status"}
    bridge_public.update({
        "membership_status": quote_membership_status,
        "market_scope": "TWSE_TPEX_EMERGING_QUOTE_ONLY",
        "membership_market_counts": quote_membership_counts,
        "membership_rows_persisted": False,
        "private_quote_consumer_connected": private_consumer_called,
        "public_market_data_relay": False,
    })

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

    mis_status = "NOT_NEEDED_NO_STALE_FINMIND_ROWS"
    mis_session_verified: list[str] = []
    mis_session_unresolved: list[str] = []
    mis_meta: dict[str, Any] = {}
    if stale_codes:
        try:
            mis_meta, mis_matches = current_mis(market_date_compact, stale_codes)
            mis_session_verified = sorted(
                code
                for code in stale_codes
                if code in mis_matches and str(mis_matches[code].get("d") or "").strip() == market_date_compact
            )
            mis_session_unresolved = sorted(set(stale_codes) - set(mis_session_verified))
            mis_status = "PASS_CURRENT_SESSION_CONTEXT" if not mis_session_unresolved else "PARTIAL_CURRENT_SESSION_CONTEXT"
        except Exception as exc:
            mis_status = f"ERROR:{type(exc).__name__}:{exc}"
            mis_session_unresolved = sorted(stale_codes)

    by_industry: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in derived_rows:
        by_industry[row["industry"]].append(row)

    market_summary = _summarize(derived_rows)
    metric_observation_count = int(market_summary["current_market_date_count"])
    metric_unknown_count = len(stale_codes)
    session_context_count = metric_observation_count + len(mis_session_verified)
    session_context_ratio = round(session_context_count / len(active_required), 8) if active_required else None

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
    session_boundary = {
        "session_context_count": session_context_count,
        "session_context_ratio": session_context_ratio,
        "finmind_metric_observation_count": metric_observation_count,
        "metric_unknown_count": metric_unknown_count,
        "metric_unknown_sample": stale_codes[:20],
        "twse_mis_secondary_session_status": mis_status,
        "twse_mis_session_verified_count": len(mis_session_verified),
        "twse_mis_session_verified_sample": mis_session_verified[:20],
        "twse_mis_session_unresolved_count": len(mis_session_unresolved),
        "twse_mis_session_unresolved_sample": mis_session_unresolved[:20],
        "twse_mis_metric_values_used": False,
        "session_context_may_substitute_metric_observation": False,
    }
    context = {
        "schema": "HENGCE_ESCAPE_FINMIND_TWSE_COMMON_AGGREGATE_SHADOW_V3",
        "generated_at_taipei": generated.isoformat(),
        "market_date": market_date,
        "source": "FinMind taiwan_stock_tick_snapshot + TWSE listed-company master + TWSE MIS session-context check",
        "authority": AUTHORITY,
        **authority_boundary,
        **session_boundary,
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
        "current_market_date_count": metric_observation_count,
        "current_market_date_ratio": market_summary["current_market_date_ratio"],
        "stale_or_noncurrent_count": len(stale_codes),
        "stale_or_noncurrent_sample": stale_codes[:20],
        "latest_source_timestamp": latest_timestamp,
        "market": market_summary,
        "industry": {key: _summarize(by_industry[key]) for key in sorted(by_industry)},
        "per_security_rows_persisted": False,
        "raw_finmind_rows_persisted": False,
        "raw_twse_mis_rows_persisted": False,
        "stale_rows_neutralized_as_zero": False,
        "single_name_bridge": bridge_public,
        "formal_eod_state_creation": False,
        "formal_escape_state_creation": False,
        "selection_authority": False,
        "model_authority": False,
        "trading_authority": False,
    }

    context_bytes = json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    context["payload_sha256"] = hashlib.sha256(context_bytes).hexdigest()

    status = {
        "schema": "HENGCE_ESCAPE_FINMIND_TWSE_COMMON_SHADOW_STATUS_V3",
        "generated_at_taipei": generated.isoformat(),
        "state": "SHADOW_CONTEXT_READY_NO_FORMAL_AUTHORITY",
        "healthy_transport": True,
        "current_market_date_observed": True,
        "active_universe_transport_full_coverage": True,
        **authority_boundary,
        **session_boundary,
        "current_market_date_count": metric_observation_count,
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
        "twse_mis_meta": {
            "current_date_target_count": mis_meta.get("current_date_target_count"),
            "target_match_count": mis_meta.get("target_match_count"),
            "query_time": mis_meta.get("query_time"),
        } if mis_meta else {},
        "context_payload_sha256": context["payload_sha256"],
        "raw_finmind_rows_persisted": False,
        "raw_twse_mis_rows_persisted": False,
        "per_security_rows_persisted": False,
        "single_name_bridge": bridge_public,
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
