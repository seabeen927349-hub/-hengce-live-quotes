#!/usr/bin/env python3
"""TWSE-only FinMind Market State shadow observer for HENGCE.

Active Market State universe = current TWSE-listed ordinary equities only.
TPEx and emerging-board equities are excluded by policy. Official TWSE OpenAPI
is the membership authority; FinMind is used only for realtime snapshot data.
Electronics100 remains a diagnostic sub-scope.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from hengce_finmind_twse_common_snapshot_probe import (
    DEFAULT_EXCEPTION_PATH,
    FINMIND_ENDPOINT,
    _fetch_twse_master,
    _twse_common_universe,
    _date_text,
    _sid,
    build_receipt as build_snapshot_audit,
)
from hengce_market_state_twse_tpex_aux import (
    ROOT,
    LIVE_UNIVERSE,
    _atomic_json,
    _canonical_sha,
    _electronics100,
    _load_status,
    _scope_summary,
    _sha_lines,
    _snapshot,
)

TAIPEI = ZoneInfo("Asia/Taipei")
CONTRACT = "hengce/market_state/HENGCE_MARKET_STATE_FINMIND_ENHANCEMENT_CONTRACT_v0_5_20261103.json"
FORMAL_CLASSIFIER = "hengce/market_state/HENGCE_MARKET_STATE_CLASSIFIER_FREEZE_v1_0_20261102.json"
RECEIPT_NAME = "market_state_finmind_shadow.json"
CONTEXT_NAME = "market_state_finmind_context.json"
COVERAGE_MIN = 0.98
DEFINITION = "TWSE_CURRENT_LISTED_ORDINARY_EQUITIES_ONLY_EXCLUDES_TPEX_AND_EMERGING"


def _membership(target_date: str) -> tuple[list[str], dict[str, Any]]:
    rows, report_date = _fetch_twse_master()
    twse_codes, tdr_codes, tdr_meta = _twse_common_universe(rows)
    twse_codes = sorted(set(str(x).strip() for x in twse_codes))
    if len(twse_codes) < 900:
        raise RuntimeError(f"TWSE_CURRENT_COMMON_UNIVERSE_TOO_SMALL:{len(twse_codes)}")
    meta = {
        "target_date": target_date,
        "membership_authority": "OFFICIAL_TWSE_CURRENT_MASTER",
        "membership_endpoint": "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
        "twse_master_report_date": report_date,
        "market_scope_rule": "twse_only_excludes_tpex_and_emerging",
        "twse_count": len(twse_codes),
        "tdr_excluded_count": len(tdr_codes),
        "tdr_exclusion_meta": tdr_meta,
        "membership_sha256": _sha_lines([f"TWSE|{code}" for code in twse_codes]),
        "raw_membership_rows_persisted": False,
        "finmind_membership_used": False,
        "tpex_included": False,
        "emerging_included": False,
    }
    return twse_codes, meta


def _base(target_date: str, now: datetime) -> dict[str, Any]:
    return {
        "system": "HENGCE",
        "artifact": "MARKET_STATE_FINMIND_SHADOW_AUX_RECEIPT",
        "schema": "HENGCE_MARKET_STATE_FINMIND_SHADOW_AUX_V6",
        "target_date": target_date,
        "observed_at_taipei": now.isoformat(),
        "contract": CONTRACT,
        "primary_scope": "twse_all_listed_equities",
        "market_scope_definition": DEFINITION,
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


def _update_status(status_path: Path, status: dict[str, Any], receipt: dict[str, Any]) -> None:
    status.update({
        "market_state_finmind_shadow_status": receipt["status"],
        "market_state_finmind_shadow_receipt": f"receipts/{RECEIPT_NAME}",
        "market_state_finmind_shadow_observed_at_taipei": receipt["observed_at_taipei"],
        "market_state_finmind_primary_scope": "twse_all_listed_equities",
        "market_state_finmind_market_scope_definition": DEFINITION,
        "market_state_finmind_shadow_blocks_core_three_leg_or_mother": False,
        "market_state_finmind_shadow_formal_classifier_mutated": False,
        "market_state_finmind_shadow_model_authority_created": False,
        "market_state_finmind_shadow_trading_authority_created": False,
    })
    for key in (
        "finmind_latest_lag_seconds",
        "twse_equity_membership_count",
        "twse_snapshot_present_count",
        "twse_current_date_count",
        "twse_snapshot_presence_ratio",
        "twse_current_date_coverage_ratio",
    ):
        if key in receipt:
            status[f"market_state_finmind_{key}"] = receipt[key]
    # Remove stale broad-market aliases from prior experiments.
    for key in list(status):
        if key.startswith("market_state_finmind_all_taiwan") or key.startswith("market_state_finmind_tpex"):
            status.pop(key, None)
    if receipt.get("derived_context_path"):
        status["market_state_finmind_context_status"] = "ATTACHED_RESEARCH_SHADOW"
        status["market_state_finmind_context_path"] = receipt["derived_context_path"]
        status["market_state_finmind_context_sha256"] = receipt["derived_context_sha256"]
    else:
        status["market_state_finmind_context_status"] = "NOT_ATTACHED_CURRENT_RUN"
        status.pop("market_state_finmind_context_path", None)
        status.pop("market_state_finmind_context_sha256", None)
    _atomic_json(status_path, status)


def _build_context(target_date: str, observed_at: datetime, rows: list[dict[str, Any]], source: dict[str, Any]) -> dict[str, Any]:
    twse_codes, membership = _membership(target_date)
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
        "twse_all_listed_equities": _scope_summary(
            snapshot_map, twse_codes, target_date, "TWSE_CURRENT_LISTED_ORDINARY_EQUITIES"
        ),
        "hengce_electronics100_diagnostic": _scope_summary(
            snapshot_map, electronics, target_date, "HENGCE_ELECTRONICS100_DIAGNOSTIC_ONLY"
        ),
    }
    ratio = scopes["twse_all_listed_equities"].get("snapshot_presence_ratio") or 0.0
    if ratio < COVERAGE_MIN:
        raise RuntimeError(f"TWSE_ALL_LISTED_EQUITIES_SNAPSHOT_PRESENCE_TOO_LOW:{ratio}")

    digest = []
    for code in twse_codes:
        row = snapshot_map.get(code)
        digest.append(
            f"{code}|MISSING" if row is None else "|".join([
                code,
                _date_text(row),
                str(row.get("change_rate") or ""),
                str(row.get("total_amount") or ""),
                str(row.get("volume_ratio") or ""),
                str(row.get("close") or ""),
            ])
        )

    ctx = {
        "system": "HENGCE",
        "artifact": "MARKET_STATE_FINMIND_DERIVED_CONTEXT",
        "schema": "HENGCE_MARKET_STATE_FINMIND_DERIVED_CONTEXT_V5",
        "target_date": target_date,
        "observed_at_taipei": observed_at.isoformat(),
        "authority": "RESEARCH_SHADOW_DESCRIPTIVE_CONTEXT_ONLY_NO_MODEL_OR_TRADING_AUTHORITY",
        "primary_scope": "twse_all_listed_equities",
        "market_scope_definition": DEFINITION,
        "data_vessel": "EXISTING_HENGCE_ORIGINAL_EOD_VESSEL",
        "source_revision_class": "FORWARD_COLLECTED_VENDOR_SNAPSHOT",
        "finmind_endpoint": FINMIND_ENDPOINT,
        "membership_authority": "OFFICIAL_TWSE_CURRENT_MASTER",
        "source_snapshot_latest_timestamp": source.get("finmind_latest_timestamp"),
        "source_snapshot_audit_digest_sha256": source.get("finmind_id_date_digest_sha256"),
        "context_snapshot_digest_sha256": _sha_lines(digest),
        "twse_membership": membership,
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
        "coverage_gate": {"twse_snapshot_presence_min": COVERAGE_MIN},
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
        receipt.update({
            "status": "SKIP_NO_HISTORICAL_REALTIME_SNAPSHOT",
            "reason": "target_date_is_not_observation_date",
            "pit_historical_backfill_claim": False,
        })
        _atomic_json(receipt_path, receipt)
        _update_status(status_path, status, receipt)
        return receipt

    try:
        source = asyncio.run(build_snapshot_audit(exception_path))
        if source.get("expected_market_date") != target_date or source.get("status") != "RESEARCH_CAPABILITY_OBSERVED":
            raise RuntimeError(f"FINMIND_CAPABILITY_NOT_PASS:{source.get('status')}")
        ctx = _build_context(target_date, now, asyncio.run(_snapshot()), source)
        _atomic_json(context_path, ctx)
        scope = ctx["scopes"]["twse_all_listed_equities"]
        membership = ctx["twse_membership"]
        receipt.update({
            "status": "OBSERVED_CONTEXT_ATTACHED",
            "finmind_endpoint": source.get("finmind_endpoint"),
            "finmind_row_count": source.get("finmind_row_count"),
            "finmind_latest_timestamp": source.get("finmind_latest_timestamp"),
            "finmind_latest_lag_seconds": source.get("finmind_latest_lag_seconds"),
            "twse_equity_membership_count": membership.get("twse_count"),
            "twse_snapshot_present_count": scope.get("snapshot_present_count"),
            "twse_current_date_count": scope.get("current_date_row_count"),
            "twse_snapshot_presence_ratio": scope.get("snapshot_presence_ratio"),
            "twse_current_date_coverage_ratio": scope.get("current_date_coverage_ratio"),
            "derived_aggregate_context_persisted": True,
            "derived_context_path": CONTEXT_NAME,
            "derived_context_sha256": ctx["payload_sha256"],
            "derived_context_schema": ctx["schema"],
            "derived_context_scopes": sorted(ctx["scopes"]),
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
