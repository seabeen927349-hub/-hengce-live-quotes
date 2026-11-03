#!/usr/bin/env python3
"""Attach FinMind-derived Market State context to the original HENGCE EOD vessel.

The FinMind snapshot stays ephemeral. Only bounded, descriptive aggregates are
persisted inside the existing eod/YYYYMMDD vessel. These aggregates are shadow
observations only: they do not alter the frozen S5 classifier, Selection,
Escape, trading, or capital authority.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import numpy as np
from finmind_mcp.client import FinMindClient

from hengce_finmind_twse_common_snapshot_probe import (
    DEFAULT_EXCEPTION_PATH,
    FINMIND_ENDPOINT,
    _active_nontrading_exceptions,
    _date_text,
    _fetch_twse_master,
    _sid,
    _twse_common_universe,
    build_receipt as build_snapshot_audit,
)

TAIPEI = ZoneInfo("Asia/Taipei")
ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "hengce/market_state/HENGCE_MARKET_STATE_FINMIND_ENHANCEMENT_CONTRACT_v0_2_20261103.json"
FORMAL_CLASSIFIER = "hengce/market_state/HENGCE_MARKET_STATE_CLASSIFIER_FREEZE_v1_0_20261102.json"
LIVE_UNIVERSE = ROOT / "hengce" / "legacy" / "live_universe.json"
RECEIPT_NAME = "market_state_finmind_shadow.json"
CONTEXT_NAME = "market_state_finmind_context.json"

PERSISTED_VENDOR_FIELDS = (
    "change_rate",
    "total_amount",
    "volume_ratio",
    "close",
    "open",
    "average_price",
)


def _canonical_sha(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _atomic_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _load_status(path: Path, target_date: str) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError("ORIGINAL_EOD_STATUS_MISSING")
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
        "schema": "HENGCE_MARKET_STATE_FINMIND_SHADOW_AUX_V2",
        "target_date": target_date,
        "observed_at_taipei": now.isoformat(),
        "contract": CONTRACT,
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
    status_obj.update(
        {
            "market_state_finmind_shadow_status": receipt["status"],
            "market_state_finmind_shadow_receipt": f"receipts/{RECEIPT_NAME}",
            "market_state_finmind_shadow_observed_at_taipei": receipt["observed_at_taipei"],
            "market_state_finmind_shadow_blocks_core_three_leg_or_mother": False,
            "market_state_finmind_shadow_formal_classifier_mutated": False,
            "market_state_finmind_shadow_model_authority_created": False,
            "market_state_finmind_shadow_trading_authority_created": False,
        }
    )
    if "twse_active_coverage_ratio" in receipt:
        status_obj["market_state_finmind_shadow_twse_active_coverage_ratio"] = receipt["twse_active_coverage_ratio"]
    if "finmind_latest_lag_seconds" in receipt:
        status_obj["market_state_finmind_shadow_latest_lag_seconds"] = receipt["finmind_latest_lag_seconds"]
    if receipt.get("derived_context_path"):
        status_obj["market_state_finmind_context_status"] = "ATTACHED_RESEARCH_SHADOW"
        status_obj["market_state_finmind_context_path"] = receipt["derived_context_path"]
        status_obj["market_state_finmind_context_sha256"] = receipt["derived_context_sha256"]
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


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    return float(np.quantile(np.asarray(values, dtype=float), q))


def _ratio(num: int | float, den: int | float) -> float | None:
    if not den:
        return None
    return float(num) / float(den)


def _scope_summary(
    snapshot_map: dict[str, dict[str, Any]],
    codes: Iterable[str],
    market_date: str,
    scope_name: str,
    scope_authority: str,
) -> dict[str, Any]:
    unique_codes = sorted(set(str(x) for x in codes))
    current_rows: list[dict[str, Any]] = []
    stale_codes: list[str] = []
    missing_codes: list[str] = []

    for code in unique_codes:
        row = snapshot_map.get(code)
        if row is None:
            missing_codes.append(code)
            continue
        if _date_text(row).startswith(market_date):
            current_rows.append(row)
        else:
            stale_codes.append(code)

    changes = [x for row in current_rows if (x := _num(row, "change_rate")) is not None]
    turnover = [x for row in current_rows if (x := _num(row, "total_amount")) is not None and x >= 0]
    volume_ratio = [x for row in current_rows if (x := _num(row, "volume_ratio")) is not None and x >= 0]

    advancing = sum(1 for x in changes if x > 0)
    declining = sum(1 for x in changes if x < 0)
    unchanged = sum(1 for x in changes if x == 0)
    total_change = len(changes)

    top10_turnover_share = None
    if turnover:
        denom = float(sum(turnover))
        if denom > 0:
            top10_turnover_share = float(sum(sorted(turnover, reverse=True)[:10]) / denom)

    close_vs_avg: list[bool] = []
    close_vs_open: list[bool] = []
    for row in current_rows:
        close = _num(row, "close")
        avg = _num(row, "average_price")
        open_ = _num(row, "open")
        if close is not None and avg is not None and avg > 0:
            close_vs_avg.append(close >= avg)
        if close is not None and open_ is not None and open_ > 0:
            close_vs_open.append(close >= open_)

    return {
        "scope": scope_name,
        "scope_authority": scope_authority,
        "requested_code_count": len(unique_codes),
        "current_date_row_count": len(current_rows),
        "current_date_coverage_ratio": _ratio(len(current_rows), len(unique_codes)),
        "stale_code_count": len(stale_codes),
        "missing_code_count": len(missing_codes),
        "change_rate_eligible_count": total_change,
        "advancing_count": advancing,
        "declining_count": declining,
        "unchanged_count": unchanged,
        "advancing_share": _ratio(advancing, total_change),
        "declining_share": _ratio(declining, total_change),
        "breadth_balance": _ratio(advancing - declining, total_change),
        "change_rate_mean_vendor_units": float(np.mean(changes)) if changes else None,
        "change_rate_median_vendor_units": float(np.median(changes)) if changes else None,
        "change_rate_q25_vendor_units": _quantile(changes, 0.25),
        "change_rate_q75_vendor_units": _quantile(changes, 0.75),
        "abs_change_rate_median_vendor_units": float(np.median(np.abs(changes))) if changes else None,
        "turnover_total_vendor_units": float(sum(turnover)) if turnover else None,
        "turnover_top10_share": top10_turnover_share,
        "volume_ratio_eligible_count": len(volume_ratio),
        "volume_ratio_median": float(np.median(volume_ratio)) if volume_ratio else None,
        "volume_ratio_q75": _quantile(volume_ratio, 0.75),
        "volume_ratio_q90": _quantile(volume_ratio, 0.90),
        "close_at_or_above_average_price_share": _ratio(sum(close_vs_avg), len(close_vs_avg)) if close_vs_avg else None,
        "close_at_or_above_open_share": _ratio(sum(close_vs_open), len(close_vs_open)) if close_vs_open else None,
        "raw_rows_persisted": False,
    }


def _load_electronics100() -> tuple[list[str], dict[str, Any]]:
    obj = json.loads(LIVE_UNIVERSE.read_text(encoding="utf-8"))
    if obj.get("policy") != "TWSE_LISTED_ELECTRONICS_100_HARD_BIND":
        raise RuntimeError("ELECTRONICS100_POLICY_MISMATCH")
    if obj.get("scope") != "TWSE_LISTED_ELECTRONICS_ONLY":
        raise RuntimeError("ELECTRONICS100_SCOPE_MISMATCH")
    symbols = [str(x).strip() for x in obj.get("symbols", [])]
    if len(symbols) != 100 or len(set(symbols)) != 100:
        raise RuntimeError("ELECTRONICS100_MEMBERSHIP_COUNT_MISMATCH")
    return symbols, {
        "path": str(LIVE_UNIVERSE.relative_to(ROOT)),
        "version": obj.get("version"),
        "target_date": obj.get("target_date"),
        "authority": obj.get("authority"),
        "payload_sha256": obj.get("payload_sha256"),
    }


async def _query_context_snapshot() -> list[dict[str, Any]]:
    client = FinMindClient()
    rows = await client.query_endpoint(FINMIND_ENDPOINT, {"data_id": ""})
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("FINMIND_CONTEXT_SNAPSHOT_EMPTY_OR_MALFORMED")
    return rows


def _build_derived_context(
    target_date: str,
    observed_at: datetime,
    snapshot_rows: list[dict[str, Any]],
    exception_path: Path,
    source_receipt: dict[str, Any],
) -> dict[str, Any]:
    master_rows, master_report_date = _fetch_twse_master()
    common_codes, _, _ = _twse_common_universe(master_rows)
    active_exceptions, exception_meta = _active_nontrading_exceptions(exception_path, target_date)
    required_common = sorted(set(common_codes) - active_exceptions)

    snapshot_map: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    for row in snapshot_rows:
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
    unexpected_missing = sorted(set(required_common) - set(snapshot_map))
    if unexpected_missing:
        raise RuntimeError(f"FINMIND_CONTEXT_UNEXPECTED_MISSING:{unexpected_missing[:20]}")

    electronics100, electronics_meta = _load_electronics100()
    noncommon_electronics = sorted(set(electronics100) - set(common_codes))
    if noncommon_electronics:
        raise RuntimeError(f"ELECTRONICS100_NOT_IN_TWSE_COMMON:{noncommon_electronics[:20]}")

    digest_lines = []
    for code in required_common:
        row = snapshot_map[code]
        digest_lines.append("|".join([
            code,
            _date_text(row),
            str(row.get("change_rate") or ""),
            str(row.get("total_amount") or ""),
            str(row.get("volume_ratio") or ""),
            str(row.get("close") or ""),
        ]))
    snapshot_digest = hashlib.sha256("\n".join(sorted(digest_lines)).encode("utf-8")).hexdigest()

    context = {
        "system": "HENGCE",
        "artifact": "MARKET_STATE_FINMIND_DERIVED_CONTEXT",
        "schema": "HENGCE_MARKET_STATE_FINMIND_DERIVED_CONTEXT_V1",
        "target_date": target_date,
        "observed_at_taipei": observed_at.isoformat(),
        "authority": "RESEARCH_SHADOW_DESCRIPTIVE_CONTEXT_ONLY_NO_MODEL_OR_TRADING_AUTHORITY",
        "data_vessel": "EXISTING_HENGCE_ORIGINAL_EOD_VESSEL",
        "source_revision_class": "FORWARD_COLLECTED_VENDOR_SNAPSHOT",
        "finmind_endpoint": FINMIND_ENDPOINT,
        "source_snapshot_latest_timestamp": source_receipt.get("finmind_latest_timestamp"),
        "source_snapshot_audit_digest_sha256": source_receipt.get("finmind_id_date_digest_sha256"),
        "context_snapshot_digest_sha256": snapshot_digest,
        "twse_master_report_date": master_report_date,
        "nontrading_exception_governance": {
            "path": exception_meta.get("path"),
            "sha256": exception_meta.get("sha256"),
            "active_exception_count": len(active_exceptions),
        },
        "persisted_vendor_fields_used_for_aggregation": list(PERSISTED_VENDOR_FIELDS),
        "raw_vendor_snapshot_persisted": False,
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
        "scopes": {
            "twse_listed_common": _scope_summary(
                snapshot_map,
                required_common,
                target_date,
                "TWSE_LISTED_COMMON_ACTIVE_REQUIRED",
                "OFFICIAL_TWSE_MASTER_WITH_DATE_BOUNDED_NONTRADING_EXCEPTIONS",
            ),
            "hengce_electronics100": _scope_summary(
                snapshot_map,
                electronics100,
                target_date,
                "HENGCE_TWSE_ELECTRONICS100",
                "QUOTE_TRANSPORT_MEMBERSHIP_ONLY_NO_MODEL_RANKING_AUTHORITY",
            ),
        },
    }
    context["payload_sha256"] = _canonical_sha(context)
    return context


def run(target_date: str, eod_dir: Path, exception_path: Path) -> dict[str, Any]:
    target = date.fromisoformat(target_date)
    now = datetime.now(TAIPEI)
    status_path = eod_dir / "status.json"
    status_obj = _load_status(status_path, target_date)
    receipt_path = eod_dir / "receipts" / RECEIPT_NAME
    context_path = eod_dir / CONTEXT_NAME

    # Never destroy a historically collected forward snapshot/context just
    # because a later manual replay targets that old date.
    if target != now.date() and receipt_path.exists():
        try:
            existing = json.loads(receipt_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
        if existing.get("target_date") == target_date and existing.get("status") == "OBSERVED_CONTEXT_ATTACHED" and context_path.exists():
            return existing

    receipt = _base(target_date, now)

    if target != now.date():
        receipt.update({
            "status": "SKIP_NO_HISTORICAL_REALTIME_SNAPSHOT",
            "reason": "target_date_is_not_observation_date",
            "pit_historical_backfill_claim": False,
        })
        _atomic_json(receipt_path, receipt)
        _update_status(status_path, status_obj, receipt)
        return receipt

    try:
        source = asyncio.run(build_snapshot_audit(exception_path))
        if source.get("expected_market_date") != target_date:
            raise RuntimeError("FINMIND_SNAPSHOT_DATE_MISMATCH")
        if source.get("status") != "RESEARCH_CAPABILITY_OBSERVED":
            raise RuntimeError(f"FINMIND_CAPABILITY_NOT_PASS:{source.get('status')}")

        context_snapshot_rows = asyncio.run(_query_context_snapshot())
        context = _build_derived_context(
            target_date=target_date,
            observed_at=now,
            snapshot_rows=context_snapshot_rows,
            exception_path=exception_path,
            source_receipt=source,
        )
        _atomic_json(context_path, context)

        receipt.update({
            "status": "OBSERVED_CONTEXT_ATTACHED",
            "source_schema": source.get("schema"),
            "finmind_endpoint": source.get("finmind_endpoint"),
            "finmind_row_count": source.get("finmind_row_count"),
            "finmind_unique_id_count": source.get("finmind_unique_id_count"),
            "finmind_four_digit_count": source.get("finmind_four_digit_count"),
            "finmind_field_names": source.get("finmind_field_names"),
            "finmind_latest_timestamp": source.get("finmind_latest_timestamp"),
            "finmind_latest_lag_seconds": source.get("finmind_latest_lag_seconds"),
            "finmind_id_date_digest_sha256": source.get("finmind_id_date_digest_sha256"),
            "twse_master_report_date": source.get("twse_master_report_date"),
            "twse_common_master_count": source.get("twse_common_master_count"),
            "twse_common_covered_count": source.get("twse_common_covered_count"),
            "twse_common_unexpected_missing_count": source.get("twse_common_unexpected_missing_count"),
            "twse_active_required_count": source.get("twse_active_required_count"),
            "twse_active_covered_count": source.get("twse_active_covered_count"),
            "twse_active_coverage_ratio": source.get("twse_active_coverage_ratio"),
            "twse_common_current_date_count": source.get("twse_common_current_date_count"),
            "twse_common_stale_count": source.get("twse_common_stale_count"),
            "derived_aggregate_context_persisted": True,
            "derived_context_path": CONTEXT_NAME,
            "derived_context_sha256": context["payload_sha256"],
            "derived_context_schema": context["schema"],
            "derived_context_scopes": sorted(context["scopes"].keys()),
            "pit_historical_backfill_claim": False,
        })
    except Exception as exc:
        receipt.update({
            "status": "SHADOW_BLOCKED_FAIL_CLOSED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "pit_historical_backfill_claim": False,
        })

    _atomic_json(receipt_path, receipt)
    _update_status(status_path, status_obj, receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Target TWSE date YYYY-MM-DD")
    parser.add_argument("--eod-dir", type=Path, required=True)
    parser.add_argument("--exceptions", type=Path, default=DEFAULT_EXCEPTION_PATH)
    args = parser.parse_args()
    result = run(args.date, args.eod_dir, args.exceptions)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
