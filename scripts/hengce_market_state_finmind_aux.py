#!/usr/bin/env python3
"""Attach a FinMind Market State shadow receipt to the original HENGCE EOD vessel.

This module is deliberately descriptive/capability-only. It reuses the existing
FinMind snapshot transport/audit, persists no raw vendor snapshot, creates no
parallel mother/universe, and cannot change the frozen Market State classifier.
A FinMind failure blocks only this shadow auxiliary, never the core three-leg
EOD vessel or the formal frozen Market State output.
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
    build_receipt as build_snapshot_audit,
)

TAIPEI = ZoneInfo("Asia/Taipei")
CONTRACT = "hengce/market_state/HENGCE_MARKET_STATE_FINMIND_ENHANCEMENT_CONTRACT_v0_1_20261103.json"
FORMAL_CLASSIFIER = "hengce/market_state/HENGCE_MARKET_STATE_CLASSIFIER_FREEZE_v1_0_20261102.json"
RECEIPT_NAME = "market_state_finmind_shadow.json"


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
        "schema": "HENGCE_MARKET_STATE_FINMIND_SHADOW_AUX_V1",
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
    _atomic_json(status_path, status_obj)


def run(target_date: str, eod_dir: Path, exception_path: Path) -> dict[str, Any]:
    target = date.fromisoformat(target_date)
    now = datetime.now(TAIPEI)
    status_path = eod_dir / "status.json"
    status_obj = _load_status(status_path, target_date)
    receipt = _base(target_date, now)

    # A realtime snapshot observed today cannot be silently used to backfill a
    # historical target date. Historical enrichment requires a separately
    # audited PIT-capable dataset and explicit governance.
    if target != now.date():
        receipt.update(
            {
                "status": "SKIP_NO_HISTORICAL_REALTIME_SNAPSHOT",
                "reason": "target_date_is_not_observation_date",
                "pit_historical_backfill_claim": False,
            }
        )
        _atomic_json(eod_dir / "receipts" / RECEIPT_NAME, receipt)
        _update_status(status_path, status_obj, receipt)
        return receipt

    try:
        source = asyncio.run(build_snapshot_audit(exception_path))
        if source.get("expected_market_date") != target_date:
            raise RuntimeError("FINMIND_SNAPSHOT_DATE_MISMATCH")
        if source.get("status") != "RESEARCH_CAPABILITY_OBSERVED":
            raise RuntimeError(f"FINMIND_CAPABILITY_NOT_PASS:{source.get('status')}")

        receipt.update(
            {
                "status": "OBSERVED_CAPABILITY_ONLY",
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
                "pit_historical_backfill_claim": False,
            }
        )
    except Exception as exc:
        # Shadow fails closed but does not mask/alter formal HENGCE EOD state.
        receipt.update(
            {
                "status": "SHADOW_BLOCKED_FAIL_CLOSED",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "pit_historical_backfill_claim": False,
            }
        )

    _atomic_json(eod_dir / "receipts" / RECEIPT_NAME, receipt)
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
