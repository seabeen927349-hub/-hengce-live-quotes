#!/usr/bin/env python3
"""Research-only FinMind Market State shadow observer for TWSE + TPEx equities.

HENGCE definition of "all Taiwan equities" in this module is deliberately
limited to current TWSE-listed and TPEx-listed ordinary equities. Emerging-board
equities are excluded by policy. Electronics100 is retained only as a diagnostic
sub-scope. No forward outcomes, selection, Escape, trading, or capital authority
is created here.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import numpy as np
import requests
from finmind_mcp.client import FinMindClient

from hengce_finmind_twse_common_snapshot_probe import (
    DEFAULT_EXCEPTION_PATH,
    FINMIND_ENDPOINT,
    _date_text,
    _sid,
    build_receipt as build_snapshot_audit,
)

TAIPEI = ZoneInfo("Asia/Taipei")
ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "hengce/market_state/HENGCE_MARKET_STATE_FINMIND_ENHANCEMENT_CONTRACT_v0_4_20261103.json"
FORMAL_CLASSIFIER = "hengce/market_state/HENGCE_MARKET_STATE_CLASSIFIER_FREEZE_v1_0_20261102.json"
LIVE_UNIVERSE = ROOT / "hengce" / "legacy" / "live_universe.json"
RECEIPT_NAME = "market_state_finmind_shadow.json"
CONTEXT_NAME = "market_state_finmind_context.json"
FINMIND_DATA_URL = "https://api.finmindtrade.com/api/v4/data"
FOUR_DIGIT_EQUITY = re.compile(r"[1-9]\d{3}")
MARKET_TYPES = {"twse", "tpex"}
COVERAGE_MIN = 0.98


def _canonical_sha(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sha_lines(values: Iterable[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def _atomic_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _load_status(path: Path, target_date: str) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("artifact") != "EOD_ORIGINAL_VESSEL_INCREMENTAL_INGEST":
        raise RuntimeError("NOT_ORIGINAL_HENGCE_EOD_VESSEL")
    if obj.get("target_date") != target_date:
        raise RuntimeError("EOD_STATUS_TARGET_DATE_MISMATCH")
    if obj.get("parallel_eod_tree") is not False or obj.get("second_mother") is not False:
        raise RuntimeError("EOD_VESSEL_GOVERNANCE_MISMATCH")
    return obj


def _base(target_date: str, now: datetime) -> dict[str, Any]:
    return {
        "system": "HENGCE",
        "artifact": "MARKET_STATE_FINMIND_SHADOW_AUX_RECEIPT",
        "schema": "HENGCE_MARKET_STATE_FINMIND_SHADOW_AUX_V5",
        "target_date": target_date,
        "observed_at_taipei": now.isoformat(),
        "contract": CONTRACT,
        "primary_scope": "all_taiwan_equities",
        "all_taiwan_definition": "TWSE_PLUS_TPEX_ORDINARY_EQUITIES_ONLY_EXCLUDES_EMERGING",
        "formal_market_state_classifier": FORMAL_CLASSIFIER,
        "authority": "RESEARCH_SHADOW_ONLY_DESCRIPTIVE_NO_TRADING_AUTHORITY",
        "data_vessel": "EXISTING_HENGCE_ORIGINAL_EOD_VESSEL",
        "parallel_eod_tree": False,
        "second_mother": False,
        "parallel_universe": False,
        "raw_vendor_snapshot_persisted": False,
        "derived_aggregate_context_persisted": False,
        "formal_classifier_mutated": False,
        "forward_outcomes_used": False,
        "selection_authority": False,
        "escape_authority": False,
        "model_authority": False,
        "trading_authority": False,
        "capital_authority": False,
        "blocks_core_three_leg_or_mother": False,
        "usable_for_formal_market_state": False,
    }


def _update_status(status_path: Path, status_obj: dict[str, Any], receipt: dict[str, Any]) -> None:
    status_obj.update({
        "market_state_finmind_shadow_status": receipt["status"],
        "market_state_finmind_shadow_receipt": f"receipts/{RECEIPT_NAME}",
        "market_state_finmind_shadow_observed_at_taipei": receipt["observed_at_taipei"],
        "market_state_finmind_primary_scope": "all_taiwan_equities",
        "market_state_finmind_all_taiwan_definition": "TWSE_PLUS_TPEX_ORDINARY_EQUITIES_ONLY_EXCLUDES_EMERGING",
        "market_state_finmind_shadow_blocks_core_three_leg_or_mother": False,
        "market_state_finmind_shadow_formal_classifier_mutated": False,
        "market_state_finmind_shadow_model_authority_created": False,
        "market_state_finmind_shadow_trading_authority_created": False,
    })
    for key in (
        "finmind_latest_lag_seconds",
        "all_taiwan_equity_membership_count",
        "all_taiwan_snapshot_present_count",
        "all_taiwan_current_date_count",
        "all_taiwan_snapshot_presence_ratio",
        "all_taiwan_current_date_coverage_ratio",
        "twse_equity_membership_count",
        "tpex_equity_membership_count",
    ):
        if key in receipt:
            status_obj[f"market_state_finmind_{key}"] = receipt[key]
    if receipt.get("derived_context_path"):
        status_obj["market_state_finmind_context_status"] = "ATTACHED_RESEARCH_SHADOW"
        status_obj["market_state_finmind_context_path"] = receipt["derived_context_path"]
        status_obj["market_state_finmind_context_sha256"] = receipt["derived_context_sha256"]
    else:
        status_obj["market_state_finmind_context_status"] = "NOT_ATTACHED_CURRENT_RUN"
        status_obj.pop("market_state_finmind_context_path", None)
        status_obj.pop("market_state_finmind_context_sha256", None)
    _atomic_json(status_path, status_obj)


def _num(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value in (None, "", "--"):
        return None
    try:
        out = float(str(value).replace(",", "").strip())
    except Exception:
        return None
    return out if math.isfinite(out) else None


def _ratio(num: int | float, den: int | float) -> float | None:
    return float(num) / float(den) if den else None


def _scope_summary(snapshot_map: dict[str, dict[str, Any]], codes: Iterable[str], market_date: str, name: str) -> dict[str, Any]:
    codes = sorted(set(str(x) for x in codes))
    present = [snapshot_map[c] for c in codes if c in snapshot_map]
    current = [r for r in present if _date_text(r).startswith(market_date)]
    missing = [c for c in codes if c not in snapshot_map]
    stale = [c for c in codes if c in snapshot_map and not _date_text(snapshot_map[c]).startswith(market_date)]
    changes = [x for r in current if (x := _num(r, "change_rate")) is not None]
    turnover = [x for r in current if (x := _num(r, "total_amount")) is not None and x >= 0]
    volume_ratio = [x for r in current if (x := _num(r, "volume_ratio")) is not None and x >= 0]
    adv = sum(x > 0 for x in changes)
    dec = sum(x < 0 for x in changes)
    flat = sum(x == 0 for x in changes)
    close_vs_avg: list[bool] = []
    close_vs_open: list[bool] = []
    for r in current:
        close, avg, op = _num(r, "close"), _num(r, "average_price"), _num(r, "open")
        if close is not None and avg is not None and avg > 0:
            close_vs_avg.append(close >= avg)
        if close is not None and op is not None and op > 0:
            close_vs_open.append(close >= op)
    top10_share = None
    if turnover and sum(turnover) > 0:
        top10_share = float(sum(sorted(turnover, reverse=True)[:10]) / sum(turnover))
    return {
        "scope": name,
        "requested_code_count": len(codes),
        "snapshot_present_count": len(present),
        "snapshot_presence_ratio": _ratio(len(present), len(codes)),
        "current_date_row_count": len(current),
        "current_date_coverage_ratio": _ratio(len(current), len(codes)),
        "missing_code_count": len(missing),
        "stale_code_count": len(stale),
        "missing_code_sample": missing[:20],
        "stale_code_sample": stale[:20],
        "change_rate_eligible_count": len(changes),
        "advancing_count": adv,
        "declining_count": dec,
        "unchanged_count": flat,
        "advancing_share": _ratio(adv, len(changes)),
        "declining_share": _ratio(dec, len(changes)),
        "breadth_balance": _ratio(adv - dec, len(changes)),
        "change_rate_mean_vendor_units": float(np.mean(changes)) if changes else None,
        "change_rate_median_vendor_units": float(np.median(changes)) if changes else None,
        "change_rate_q25_vendor_units": float(np.quantile(changes, 0.25)) if changes else None,
        "change_rate_q75_vendor_units": float(np.quantile(changes, 0.75)) if changes else None,
        "abs_change_rate_median_vendor_units": float(np.median(np.abs(changes))) if changes else None,
        "turnover_total_vendor_units": float(sum(turnover)) if turnover else None,
        "turnover_top10_share": top10_share,
        "volume_ratio_eligible_count": len(volume_ratio),
        "volume_ratio_median": float(np.median(volume_ratio)) if volume_ratio else None,
        "volume_ratio_q75": float(np.quantile(volume_ratio, 0.75)) if volume_ratio else None,
        "volume_ratio_q90": float(np.quantile(volume_ratio, 0.90)) if volume_ratio else None,
        "close_at_or_above_average_price_share": _ratio(sum(close_vs_avg), len(close_vs_avg)),
        "close_at_or_above_open_share": _ratio(sum(close_vs_open), len(close_vs_open)),
        "raw_rows_persisted": False,
    }


def _is_equity(row: dict[str, Any]) -> bool:
    code = str(row.get("stock_id") or "").strip()
    market = str(row.get("type") or "").strip().lower()
    category = str(row.get("industry_category") or "").strip().upper()
    name = str(row.get("stock_name") or "").strip().upper()
    return (
        FOUR_DIGIT_EQUITY.fullmatch(code) is not None
        and market in MARKET_TYPES
        and category not in {"ETF", "ETN"}
        and "存託" not in category
        and "-DR" not in name
    )


def _membership(target_date: str) -> tuple[dict[str, list[str]], dict[str, Any]]:
    token = os.environ.get("FINMIND_TOKEN")
    if not token:
        raise RuntimeError("FINMIND_TOKEN_IS_MISSING_FOR_STOCK_INFO")
    r = requests.get(FINMIND_DATA_URL, headers={"Authorization": f"Bearer {token}"}, params={"dataset": "TaiwanStockInfo"}, timeout=30)
    r.raise_for_status()
    payload = r.json()
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("FINMIND_TAIWAN_STOCK_INFO_EMPTY_OR_MALFORMED")
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        code, d = str(row.get("stock_id") or "").strip(), str(row.get("date") or "").strip()
        if code and d and (code not in latest or d > str(latest[code].get("date") or "")):
            latest[code] = row
    current = [row for row in latest.values() if _is_equity(row)]
    twse = sorted({str(r["stock_id"]).strip() for r in current if str(r.get("type") or "").lower() == "twse"})
    tpex = sorted({str(r["stock_id"]).strip() for r in current if str(r.get("type") or "").lower() == "tpex"})
    all_codes = sorted(set(twse) | set(tpex))
    if len(twse) < 900:
        raise RuntimeError(f"FINMIND_CURRENT_TWSE_EQUITY_UNIVERSE_TOO_SMALL:{len(twse)}")
    if len(tpex) < 700:
        raise RuntimeError(f"FINMIND_CURRENT_TPEX_EQUITY_UNIVERSE_TOO_SMALL:{len(tpex)}")
    if len(all_codes) < 1700:
        raise RuntimeError(f"FINMIND_CURRENT_ALL_TAIWAN_EQUITY_UNIVERSE_TOO_SMALL:{len(all_codes)}")
    lines = [f"{r.get('stock_id')}|{r.get('type')}|{r.get('date')}|{r.get('industry_category')}|{r.get('stock_name')}" for r in current]
    meta = {
        "dataset": "TaiwanStockInfo",
        "target_date": target_date,
        "latest_row_rule": "MAX_DATE_PER_STOCK_ID",
        "market_type_rule": "twse+tpex_only_excludes_emerging",
        "twse_count": len(twse),
        "tpex_count": len(tpex),
        "all_taiwan_equity_count": len(all_codes),
        "membership_sha256": _sha_lines(lines),
        "raw_membership_rows_persisted": False,
    }
    return {"twse": twse, "tpex": tpex, "all": all_codes}, meta


def _electronics100() -> tuple[list[str], dict[str, Any]]:
    obj = json.loads(LIVE_UNIVERSE.read_text(encoding="utf-8"))
    symbols = [str(x).strip() for x in obj.get("symbols", [])]
    if len(symbols) != 100 or len(set(symbols)) != 100:
        raise RuntimeError("ELECTRONICS100_MEMBERSHIP_COUNT_MISMATCH")
    return symbols, {"path": str(LIVE_UNIVERSE.relative_to(ROOT)), "version": obj.get("version"), "role": "DIAGNOSTIC_ONLY"}


async def _snapshot() -> list[dict[str, Any]]:
    rows = await FinMindClient().query_endpoint(FINMIND_ENDPOINT, {"data_id": ""})
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("FINMIND_CONTEXT_SNAPSHOT_EMPTY_OR_MALFORMED")
    return rows


def _build_context(target_date: str, observed_at: datetime, rows: list[dict[str, Any]], source: dict[str, Any]) -> dict[str, Any]:
    markets, membership = _membership(target_date)
    snapshot_map: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = _sid(row)
        if not code:
            continue
        if code in snapshot_map:
            duplicates.add(code)
        snapshot_map[code] = row
    if duplicates:
        raise RuntimeError(f"FINMIND_CONTEXT_DUPLICATE_IDS:{sorted(duplicates)[:20]}")
    electronics, electronics_meta = _electronics100()
    scopes = {
        "all_taiwan_equities": _scope_summary(snapshot_map, markets["all"], target_date, "TWSE_PLUS_TPEX_CURRENT_EQUITIES"),
        "twse_equities": _scope_summary(snapshot_map, markets["twse"], target_date, "TWSE_CURRENT_EQUITIES"),
        "tpex_equities": _scope_summary(snapshot_map, markets["tpex"], target_date, "TPEX_CURRENT_EQUITIES"),
        "hengce_electronics100_diagnostic": _scope_summary(snapshot_map, electronics, target_date, "HENGCE_ELECTRONICS100_DIAGNOSTIC_ONLY"),
    }
    for key in ("twse_equities", "tpex_equities", "all_taiwan_equities"):
        ratio = scopes[key].get("snapshot_presence_ratio") or 0.0
        if ratio < COVERAGE_MIN:
            raise RuntimeError(f"{key.upper()}_SNAPSHOT_PRESENCE_TOO_LOW:{ratio}")
    digest = []
    for code in markets["all"]:
        row = snapshot_map.get(code)
        digest.append(f"{code}|MISSING" if row is None else "|".join([code, _date_text(row), str(row.get("change_rate") or ""), str(row.get("total_amount") or ""), str(row.get("volume_ratio") or ""), str(row.get("close") or "")]))
    ctx = {
        "system": "HENGCE",
        "artifact": "MARKET_STATE_FINMIND_DERIVED_CONTEXT",
        "schema": "HENGCE_MARKET_STATE_FINMIND_DERIVED_CONTEXT_V4",
        "target_date": target_date,
        "observed_at_taipei": observed_at.isoformat(),
        "authority": "RESEARCH_SHADOW_DESCRIPTIVE_CONTEXT_ONLY_NO_MODEL_OR_TRADING_AUTHORITY",
        "primary_scope": "all_taiwan_equities",
        "all_taiwan_definition": "TWSE_PLUS_TPEX_ORDINARY_EQUITIES_ONLY_EXCLUDES_EMERGING",
        "data_vessel": "EXISTING_HENGCE_ORIGINAL_EOD_VESSEL",
        "source_revision_class": "FORWARD_COLLECTED_VENDOR_SNAPSHOT",
        "finmind_endpoint": FINMIND_ENDPOINT,
        "finmind_membership_dataset": "TaiwanStockInfo",
        "source_snapshot_latest_timestamp": source.get("finmind_latest_timestamp"),
        "source_snapshot_audit_digest_sha256": source.get("finmind_id_date_digest_sha256"),
        "context_snapshot_digest_sha256": _sha_lines(digest),
        "all_taiwan_membership": membership,
        "raw_vendor_snapshot_persisted": False,
        "raw_membership_rows_persisted": False,
        "per_ticker_vendor_rows_persisted": False,
        "forward_outcomes_used": False,
        "formal_market_state_classifier": FORMAL_CLASSIFIER,
        "formal_classifier_effect": "NONE",
        "selection_effect": "NONE",
        "escape_effect": "NONE",
        "trading_effect": "NONE",
        "capital_effect": "NONE",
        "promotion_required_before_formal_use": True,
        "electronics100_membership": electronics_meta,
        "coverage_gate": {"twse_snapshot_presence_min": COVERAGE_MIN, "tpex_snapshot_presence_min": COVERAGE_MIN, "all_taiwan_snapshot_presence_min": COVERAGE_MIN},
        "scopes": scopes,
    }
    ctx["payload_sha256"] = _canonical_sha(ctx)
    return ctx


def run(target_date: str, eod_dir: Path, exception_path: Path) -> dict[str, Any]:
    target = date.fromisoformat(target_date)
    now = datetime.now(TAIPEI)
    status_path = eod_dir / "status.json"
    status = _load_status(status_path, target_date)
    receipt_path = eod_dir / "receipts" / RECEIPT_NAME
    context_path = eod_dir / CONTEXT_NAME
    receipt = _base(target_date, now)
    if target != now.date():
        receipt.update({"status": "SKIP_NO_HISTORICAL_REALTIME_SNAPSHOT", "reason": "target_date_is_not_observation_date", "pit_historical_backfill_claim": False})
        _atomic_json(receipt_path, receipt)
        _update_status(status_path, status, receipt)
        return receipt
    try:
        source = asyncio.run(build_snapshot_audit(exception_path))
        if source.get("expected_market_date") != target_date or source.get("status") != "RESEARCH_CAPABILITY_OBSERVED":
            raise RuntimeError(f"FINMIND_CAPABILITY_NOT_PASS:{source.get('status')}")
        ctx = _build_context(target_date, now, asyncio.run(_snapshot()), source)
        _atomic_json(context_path, ctx)
        scope = ctx["scopes"]["all_taiwan_equities"]
        membership = ctx["all_taiwan_membership"]
        receipt.update({
            "status": "OBSERVED_CONTEXT_ATTACHED",
            "finmind_endpoint": source.get("finmind_endpoint"),
            "finmind_row_count": source.get("finmind_row_count"),
            "finmind_latest_timestamp": source.get("finmind_latest_timestamp"),
            "finmind_latest_lag_seconds": source.get("finmind_latest_lag_seconds"),
            "twse_equity_membership_count": membership.get("twse_count"),
            "tpex_equity_membership_count": membership.get("tpex_count"),
            "all_taiwan_equity_membership_count": membership.get("all_taiwan_equity_count"),
            "all_taiwan_snapshot_present_count": scope.get("snapshot_present_count"),
            "all_taiwan_current_date_count": scope.get("current_date_row_count"),
            "all_taiwan_snapshot_presence_ratio": scope.get("snapshot_presence_ratio"),
            "all_taiwan_current_date_coverage_ratio": scope.get("current_date_coverage_ratio"),
            "derived_aggregate_context_persisted": True,
            "derived_context_path": CONTEXT_NAME,
            "derived_context_sha256": ctx["payload_sha256"],
            "derived_context_schema": ctx["schema"],
            "derived_context_scopes": sorted(ctx["scopes"]),
            "pit_historical_backfill_claim": False,
        })
    except Exception as exc:
        receipt.update({"status": "SHADOW_BLOCKED_FAIL_CLOSED", "error_type": type(exc).__name__, "error": str(exc), "pit_historical_backfill_claim": False})
    _atomic_json(receipt_path, receipt)
    _update_status(status_path, status, receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--eod-dir", type=Path, required=True)
    parser.add_argument("--exceptions", type=Path, default=DEFAULT_EXCEPTION_PATH)
    args = parser.parse_args()
    print(json.dumps(run(args.date, args.eod_dir, args.exceptions), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
