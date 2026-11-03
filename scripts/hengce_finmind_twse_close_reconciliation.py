#!/usr/bin/env python3
"""Research-only FinMind vs official TWSE daily-close reconciliation.

The comparison is performed in runner memory. Neither FinMind per-security raw
snapshot rows nor the full TWSE official price table are persisted by this
probe. Output is aggregate reconciliation counts plus bounded ticker samples.

This probe does not promote FinMind as a formal HENGCE source and creates no
Escape, metric, EOD, selection, model, or trading authority.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from finmind_mcp.client import FinMindClient

from hengce_eod_incremental_ingest import NotReady, _price
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

SCHEMA = "HENGCE_FINMIND_TWSE_CLOSE_RECONCILIATION_V1"


def _decimal(value: Any) -> Decimal | None:
    if value in (None, "", "-", "--", "---"):
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        out = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    return out if out.is_finite() else None


def _base_receipt(now: datetime, target_iso: str, target_ds: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "generated_at_taipei": now.isoformat(),
        "target_date": target_iso,
        "target_date_compact": target_ds,
        "finmind_endpoint": FINMIND_ENDPOINT,
        "twse_price_source": "MI_INDEX ALLBUT0999",
        "raw_finmind_rows_persisted": False,
        "raw_twse_price_rows_persisted": False,
        "per_security_rows_persisted": False,
        "formal_source_promotion_authority": False,
        "formal_metric_authority": False,
        "formal_eod_authority": False,
        "formal_escape_authority": False,
        "selection_authority": False,
        "model_authority": False,
        "trading_authority": False,
    }


async def reconcile(exception_path: Path = DEFAULT_EXCEPTION_PATH) -> dict[str, Any]:
    if not os.environ.get("FINMIND_TOKEN"):
        raise RuntimeError("FINMIND_TOKEN is missing")

    now = datetime.now(TAIPEI)
    target_iso = now.date().isoformat()
    target_ds = now.strftime("%Y%m%d")
    receipt = _base_receipt(now, target_iso, target_ds)

    try:
        twse_rows = _price(target_ds, target_iso)
    except NotReady as exc:
        receipt.update(
            {
                "status": "PENDING_TWSE_MI_INDEX",
                "pending_reason": str(exc),
                "comparison_performed": False,
            }
        )
        return receipt

    if len(twse_rows) < 900:
        raise RuntimeError(f"official TWSE price rows unexpectedly small:{len(twse_rows)}")

    client = FinMindClient()
    finmind_rows = await client.query_endpoint(FINMIND_ENDPOINT, {"data_id": ""})
    if not isinstance(finmind_rows, list) or not finmind_rows:
        raise RuntimeError("FinMind snapshot is empty or malformed")

    master_rows, master_report_date = _fetch_twse_master()
    common_codes, tdr_codes, _ = _twse_common_universe(master_rows)
    common_set = set(common_codes)
    active_exceptions, exception_meta = _active_nontrading_exceptions(exception_path, target_iso)
    active_required = common_set - active_exceptions

    finmind_map: dict[str, dict[str, Any]] = {}
    duplicate_finmind: set[str] = set()
    for row in finmind_rows:
        if not isinstance(row, dict):
            continue
        code = _sid(row)
        if not code:
            continue
        if code in finmind_map:
            duplicate_finmind.add(code)
        finmind_map[code] = row
    if duplicate_finmind:
        raise RuntimeError(f"duplicate FinMind IDs:{sorted(duplicate_finmind)[:20]}")

    twse_map = {str(row.get("Ticker") or "").strip(): row for row in twse_rows}
    missing_finmind = sorted(active_required - set(finmind_map))
    missing_twse = sorted(active_required - set(twse_map))
    if missing_finmind:
        raise RuntimeError(f"active common stocks missing from FinMind:{missing_finmind[:20]}")

    counts: Counter[str] = Counter()
    samples: dict[str, list[str]] = {}
    max_abs_diff: Decimal | None = None

    for code in sorted(active_required):
        fm = finmind_map[code]
        tw = twse_map.get(code)
        fm_current = _date_text(fm).startswith(target_iso)
        fm_close = _decimal(fm.get("close"))
        tw_close = _decimal(tw.get("Close")) if tw else None

        if tw is None:
            klass = "TWSE_ROW_MISSING"
        elif tw_close is None and not fm_current:
            klass = "TWSE_CLOSE_NULL_FINMIND_STALE"
        elif tw_close is None and fm_current:
            klass = "TWSE_CLOSE_NULL_FINMIND_CURRENT"
        elif tw_close is not None and not fm_current:
            klass = "TWSE_CLOSE_PRESENT_FINMIND_STALE"
        elif tw_close is not None and fm_close is None:
            klass = "TWSE_CLOSE_PRESENT_FINMIND_CLOSE_NULL"
        else:
            diff = abs(tw_close - fm_close)  # type: ignore[operator]
            if max_abs_diff is None or diff > max_abs_diff:
                max_abs_diff = diff
            klass = "CURRENT_CLOSE_EXACT_MATCH" if diff == 0 else "CURRENT_CLOSE_MISMATCH"

        counts[klass] += 1
        if len(samples.setdefault(klass, [])) < 20:
            samples[klass].append(code)

    compared_numeric = counts["CURRENT_CLOSE_EXACT_MATCH"] + counts["CURRENT_CLOSE_MISMATCH"]
    exact_ratio = (
        float(counts["CURRENT_CLOSE_EXACT_MATCH"] / compared_numeric)
        if compared_numeric
        else None
    )

    receipt.update(
        {
            "status": "RECONCILIATION_COMPLETE_RESEARCH_ONLY",
            "comparison_performed": True,
            "twse_master_report_date": master_report_date,
            "twse_common_master_count": len(common_codes),
            "excluded_tdr_count": len(tdr_codes),
            "active_nontrading_exception_count": len(active_exceptions),
            "active_required_count": len(active_required),
            "official_twse_price_row_count": len(twse_rows),
            "official_twse_active_row_count": len(active_required & set(twse_map)),
            "finmind_snapshot_row_count": len(finmind_rows),
            "finmind_active_covered_count": len(active_required & set(finmind_map)),
            "missing_finmind_count": len(missing_finmind),
            "missing_finmind_sample": missing_finmind[:20],
            "missing_twse_count": len(missing_twse),
            "missing_twse_sample": missing_twse[:20],
            "classification_counts": dict(sorted(counts.items())),
            "classification_samples": {key: value for key, value in sorted(samples.items())},
            "numeric_close_compared_count": compared_numeric,
            "numeric_close_exact_match_count": counts["CURRENT_CLOSE_EXACT_MATCH"],
            "numeric_close_mismatch_count": counts["CURRENT_CLOSE_MISMATCH"],
            "numeric_close_exact_match_ratio": exact_ratio,
            "max_abs_close_difference": str(max_abs_diff) if max_abs_diff is not None else None,
            "exception_governance": exception_meta,
            "decision": "OBSERVE_SOURCE_QUALITY_ONLY_NO_PROMOTION",
        }
    )
    return receipt


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=None)
    parser.add_argument("--exceptions", type=Path, default=DEFAULT_EXCEPTION_PATH)
    args = parser.parse_args()

    receipt = asyncio.run(reconcile(args.exceptions))
    rendered = json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2)
    print(rendered)
    if args.receipt is not None:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
