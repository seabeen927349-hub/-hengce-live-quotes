#!/usr/bin/env python3
"""HENGCE IF-07 V0.1 — Stage B candidate-manifest admission gate (NO NETWORK).

Purpose
-------
Prepare the already-frozen Stage A 6/6 candidates for the exact t57 metadata
stage without reacquiring data, inferring identities, inspecting market outcomes,
or changing any research rule.

This program performs ZERO HTTP/network access. It accepts only a Stage A rows
artifact whose internal candidate population matches the frozen, already-produced
Stage A V0.2 result:
  - 3,560 company-quarter rows
  - 187 accounting 6/6 pre-metadata candidates
  - 128 unique candidate tickers
  - candidate period counts 41/23/27/23/19/17/22/15

It then emits a deterministic, outcome-blind request manifest containing only
identity/provenance fields needed by the future exact-metadata executor.

It DOES NOT query t57, map signal dates, test PIT electronics membership, inspect
prices/returns, or authorize Discovery returns.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

EXPECTED_TOTAL_ROWS = 3560
EXPECTED_CANDIDATES = 187
EXPECTED_UNIQUE_TICKERS = 128
EXPECTED_CANDIDATES_BY_PERIOD = {
    "2022Q4": 41,
    "2023Q1": 23,
    "2023Q2": 27,
    "2023Q3": 23,
    "2023Q4": 19,
    "2024Q1": 17,
    "2024Q2": 22,
    "2024Q3": 15,
}
EXPECTED_CURRENT_PERIODS = tuple(EXPECTED_CANDIDATES_BY_PERIOD)
CHALLENGER = "IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1"

# These Stage A invariants are part of the frozen handoff. A candidate must have
# no market outcome and no timestamp/signal/PIT membership applied yet.
CONDITION_FIELDS = (
    "D_CASH_ge_0",
    "AR_GAP_ge_0",
    "INV_GAP_ge_0",
    "D_GM_ge_0",
    "D_OM_ge_0",
    "D_LEV_le_0",
)

# Key-level guard against accidentally admitting an outcome-contaminated artifact.
FORBIDDEN_KEY_FRAGMENTS = (
    "forwardreturn",
    "futurereturn",
    "holdingreturn",
    "entryprice",
    "exitprice",
    "futureprice",
    "postsignalprice",
    "nullreturn",
    "winnerlabel",
    "outcomelabel",
    "mae",
    "mfe",
)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def norm_key(value: Any) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def scan_forbidden_keys(obj: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            nk = norm_key(k)
            if any(fragment in nk for fragment in FORBIDDEN_KEY_FRAGMENTS):
                hits.append(f"{path}.{k}")
            hits.extend(scan_forbidden_keys(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(scan_forbidden_keys(v, f"{path}[{i}]"))
    return hits


def period_of(row: dict[str, Any]) -> str | None:
    try:
        y = int(row["fiscal_year"])
        q = int(row["quarter"])
    except Exception:
        return None
    if 2000 <= y <= 2100 and q in (1, 2, 3, 4):
        return f"{y}Q{q}"
    return None


def ticker_of(row: dict[str, Any]) -> str:
    return str(row.get("ticker", "")).strip()


def is_finite_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def load_rows(path: Path) -> tuple[bytes, dict[str, Any], list[dict[str, Any]]]:
    raw = path.read_bytes()
    doc = json.loads(raw.decode("utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("ROOT_MUST_BE_OBJECT")
    if doc.get("artifact") != "IF07_STAGE_A_ACCOUNTING_UPPER_BOUND_NO_RETURNS":
        raise ValueError("WRONG_STAGE_A_ARTIFACT_ID")
    if doc.get("contains_price_or_forward_return_data") is not False:
        raise ValueError("STAGE_A_ARTIFACT_NOT_EXPLICITLY_OUTCOME_BLIND")
    rows = doc.get("rows")
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise ValueError("ROWS_MISSING_OR_INVALID")
    return raw, doc, rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage_a_rows", type=Path)
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(
            "research/selection_core_rebuild/generated/"
            "IF07_STAGE_B_EXACT_METADATA_REQUEST_MANIFEST_NO_RETURNS.json"
        ),
    )
    args = ap.parse_args()

    failures: list[str] = []
    try:
        raw, doc, rows = load_rows(args.stage_a_rows)
    except Exception as e:
        result = {
            "system": "HENGCE",
            "artifact": "IF07_STAGE_B_CANDIDATE_MANIFEST_ADMISSION_NO_NETWORK",
            "challenger": CHALLENGER,
            "verdict": "FAIL_CANDIDATE_MANIFEST_ADMISSION",
            "network_access_performed": False,
            "forward_returns_inspected": False,
            "failures": [f"LOAD_ERROR:{type(e).__name__}:{e}"],
            "discovery_returns_authorized": False,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    input_sha256 = sha256_bytes(raw)

    forbidden = scan_forbidden_keys(doc)
    if forbidden:
        failures.append("OUTCOME_BEARING_KEYS_PRESENT:" + ",".join(forbidden[:50]))

    if len(rows) != EXPECTED_TOTAL_ROWS:
        failures.append(f"TOTAL_ROW_COUNT_MISMATCH:{len(rows)}!={EXPECTED_TOTAL_ROWS}")

    candidates: list[dict[str, Any]] = []
    seen_all_pairs: set[tuple[str, str]] = set()
    duplicate_all_pairs: list[str] = []
    unresolved_periods = 0

    for row in rows:
        ticker = ticker_of(row)
        period = period_of(row)
        if not ticker or period is None:
            unresolved_periods += 1
            continue
        pair = (ticker, period)
        if pair in seen_all_pairs:
            duplicate_all_pairs.append(f"{ticker}:{period}")
        seen_all_pairs.add(pair)

        if row.get("accounting_6of6_pre_metadata_candidate") is True:
            candidates.append(row)

    if unresolved_periods:
        failures.append(f"UNRESOLVED_TICKER_OR_PERIOD_ROWS:{unresolved_periods}")
    if duplicate_all_pairs:
        failures.append("DUPLICATE_TICKER_PERIOD_ROWS:" + ",".join(duplicate_all_pairs[:50]))

    by_period = Counter(period_of(r) or "UNRESOLVED" for r in candidates)
    unique_tickers = {ticker_of(r) for r in candidates if ticker_of(r)}

    if len(candidates) != EXPECTED_CANDIDATES:
        failures.append(f"CANDIDATE_COUNT_MISMATCH:{len(candidates)}!={EXPECTED_CANDIDATES}")
    if len(unique_tickers) != EXPECTED_UNIQUE_TICKERS:
        failures.append(
            f"UNIQUE_CANDIDATE_TICKERS_MISMATCH:{len(unique_tickers)}!={EXPECTED_UNIQUE_TICKERS}"
        )
    if dict(sorted(by_period.items())) != dict(sorted(EXPECTED_CANDIDATES_BY_PERIOD.items())):
        failures.append(
            "CANDIDATE_PERIOD_COUNTS_MISMATCH:"
            f"actual={dict(sorted(by_period.items()))}:expected={EXPECTED_CANDIDATES_BY_PERIOD}"
        )

    request_rows: list[dict[str, Any]] = []
    for row in candidates:
        ticker = ticker_of(row)
        period = period_of(row)
        conds = row.get("conditions")

        if row.get("accounting_pair_available") is not True:
            failures.append(f"CANDIDATE_WITHOUT_ACCOUNTING_PAIR:{ticker}:{period}")
            continue
        if row.get("contains_market_outcome") is not False:
            failures.append(f"CANDIDATE_MARKET_OUTCOME_FLAG_INVALID:{ticker}:{period}")
        if row.get("upload_ts_known") is not False:
            failures.append(f"STAGE_A_UPLOAD_TS_ALREADY_APPLIED:{ticker}:{period}")
        if row.get("signal_date_known") is not False:
            failures.append(f"STAGE_A_SIGNAL_DATE_ALREADY_APPLIED:{ticker}:{period}")
        if row.get("pit_electronics_membership_checked") is not False:
            failures.append(f"STAGE_A_PIT_MEMBERSHIP_ALREADY_APPLIED:{ticker}:{period}")
        if row.get("current_correction_listed") is not False:
            failures.append(f"CANDIDATE_CURRENT_BULK_CORRECTION_LISTED:{ticker}:{period}")
        if row.get("prior_correction_listed") is not False:
            failures.append(f"CANDIDATE_PRIOR_BULK_CORRECTION_LISTED:{ticker}:{period}")

        if not isinstance(conds, dict) or any(conds.get(k) is not True for k in CONDITION_FIELDS):
            failures.append(f"CANDIDATE_NOT_TRUE_6OF6:{ticker}:{period}")
            continue

        cur = row.get("current")
        prior = row.get("prior")
        if not isinstance(cur, dict) or not isinstance(prior, dict):
            failures.append(f"CANDIDATE_ACCOUNTING_PAYLOAD_MISSING:{ticker}:{period}")
            continue
        required_accounting = (
            "Revenue_YTD", "COGS_YTD", "OperatingIncome_YTD", "CFO_YTD",
            "AR", "Inventory", "Assets", "Liabilities",
        )
        if any(k not in cur or not is_finite_number(cur[k]) for k in required_accounting):
            failures.append(f"CURRENT_ACCOUNTING_INVALID:{ticker}:{period}")
            continue
        if any(k not in prior or not is_finite_number(prior[k]) for k in required_accounting):
            failures.append(f"PRIOR_ACCOUNTING_INVALID:{ticker}:{period}")
            continue

        y = int(row["fiscal_year"])
        q = int(row["quarter"])
        prior_year = int(row.get("prior_year", y - 1))
        if prior_year != y - 1:
            failures.append(f"PRIOR_YEAR_MISMATCH:{ticker}:{period}:{prior_year}!={y-1}")
            continue

        request_rows.append({
            "ticker": ticker,
            "fiscal_year": y,
            "quarter": q,
            "current_period": f"{y}Q{q}",
            "prior_period": f"{y-1}Q{q}",
            "required_current_metadata": {
                "report_type": "IFRSs合併財報",
                "exact_upload_timestamp": True,
                "correction_field_exact": "無",
                "exactly_one_usable_row": True,
            },
            "required_prior_metadata": {
                "report_type": "IFRSs合併財報",
                "parseable_upload_timestamp": True,
                "correction_field_exact": "無",
                "exactly_one_usable_row": True,
            },
            "stage_a_candidate": True,
        })

    # Deterministic ordering. No ranking or alpha information is introduced.
    request_rows.sort(key=lambda x: (x["fiscal_year"], x["quarter"], x["ticker"]))

    if len(request_rows) != EXPECTED_CANDIDATES and not failures:
        failures.append(
            f"REQUEST_ROW_COUNT_INTERNAL_MISMATCH:{len(request_rows)}!={EXPECTED_CANDIDATES}"
        )

    verdict = "PASS_STAGE_B_MANIFEST_ADMISSION_NO_NETWORK" if not failures else "FAIL_CANDIDATE_MANIFEST_ADMISSION"

    result = {
        "system": "HENGCE",
        "artifact": "IF07_STAGE_B_EXACT_METADATA_REQUEST_MANIFEST_NO_RETURNS",
        "challenger": CHALLENGER,
        "verdict": verdict,
        "network_access_performed": False,
        "forward_returns_inspected": False,
        "market_prices_inspected": False,
        "research_thresholds_changed": False,
        "input_stage_a_rows_sha256": input_sha256,
        "input_stage_a_artifact_id": doc.get("artifact"),
        "input_stage_a_generated_at_utc": doc.get("generated_at_utc"),
        "expected_candidate_count": EXPECTED_CANDIDATES,
        "candidate_count": len(candidates),
        "expected_unique_candidate_tickers": EXPECTED_UNIQUE_TICKERS,
        "unique_candidate_tickers": len(unique_tickers),
        "candidate_by_period": dict(sorted(by_period.items())),
        "request_count": len(request_rows),
        "metadata_authority": "TWSE_DOC_T57SB01",
        "current_upload_ts_authority": "CURRENT_PERIOD_OFFICIAL_上傳日期_ASIA_TAIPEI",
        "prior_upload_ts_role": "PARSEABILITY_AND_ORIGINAL_FILING_GATE_ONLY_NOT_SIGNAL_TIME",
        "correction_gate": "CURRENT_AND_PRIOR_FINAL_財務報告更(補)正_EXACT_無",
        "duplicate_ambiguity_policy": "FAIL_CLOSED",
        "signal_date_mapping_performed": False,
        "pit_electronics_membership_performed": False,
        "discovery_returns_authorized": False,
        "request_rows": request_rows if not failures else [],
        "failures": failures,
        "next_legal_step": (
            "EXACT_T57_METADATA_EXECUTION_FOR_THIS_REQUEST_MANIFEST_ONLY"
            if not failures
            else "STOP_DO_NOT_QUERY_T57_FROM_THIS_MANIFEST"
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "verdict": verdict,
        "candidate_count": len(candidates),
        "unique_candidate_tickers": len(unique_tickers),
        "request_count": len(request_rows),
        "network_access_performed": False,
        "forward_returns_inspected": False,
        "failure_count": len(failures),
    }, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
