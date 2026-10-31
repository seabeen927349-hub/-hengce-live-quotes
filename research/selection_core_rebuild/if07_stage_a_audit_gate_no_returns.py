#!/usr/bin/env python3
"""HENGCE IF-07 V0.1 — Stage A no-return integrity gate.

This checker is deliberately OFFLINE and outcome-blind.
It performs no HTTP requests, imports no market data, and does not inspect prices,
forward returns, null outcomes, or post-signal labels.

It mechanizes only already-frozen IF-07 V0.1 / pre-return-erratum rules for the
Stage-A accounting upper-bound artifacts. It has zero authority to retune the
research design or to authorize Discovery returns by itself.

Legal interpretation:
- FAIL_INTEGRITY => stop; repair only an engineering defect against frozen rules.
- INCONCLUSIVE_SAMPLE_INSUFFICIENT_PRE_RETURN_UPPER_BOUND => stop without returns.
- STAGE_A_PASS_TO_EXACT_METADATA_GATE => Stage A count/integrity is sufficient;
  exact t57 metadata, signal-date, and PIT-universe gates are still required.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("research/selection_core_rebuild")
DEFAULT_ROWS = ROOT / "generated/IF07_STAGE_A_ACCOUNTING_UPPER_BOUND_NO_RETURNS.json"
DEFAULT_AUDIT = ROOT / "generated/IF07_STAGE_A_ACCOUNTING_UPPER_BOUND_AUDIT_NO_RETURNS.json"
DEFAULT_OUT = ROOT / "generated/IF07_STAGE_A_INTEGRITY_GATE_NO_RETURNS.json"

CURRENT_PERIODS = [
    "2022Q4",
    "2023Q1", "2023Q2", "2023Q3", "2023Q4",
    "2024Q1", "2024Q2", "2024Q3",
]
REQUIRED_PERIODS = [
    "2021Q4",
    "2022Q1", "2022Q2", "2022Q3", "2022Q4",
    "2023Q1", "2023Q2", "2023Q3", "2023Q4",
    "2024Q1", "2024Q2", "2024Q3",
]

ACCOUNTING_FIELDS = [
    "Revenue_YTD",
    "COGS_YTD",
    "OperatingIncome_YTD",
    "CFO_YTD",
    "AR",
    "Inventory",
    "Assets",
    "Liabilities",
]
CONDITION_FIELDS = [
    "D_CASH_ge_0",
    "AR_GAP_ge_0",
    "INV_GAP_ge_0",
    "D_GM_ge_0",
    "D_OM_ge_0",
    "D_LEV_le_0",
]

MIN_EVENTS = 80
MIN_UNIQUE_TICKERS = 40
# The preregistered 20-signal-date minimum is intentionally NOT evaluated here:
# signal dates do not legally exist until the exact metadata gate has passed.

# Forbidden outcome-bearing keys. Matching is normalized to lowercase and ignores
# spaces/hyphens. We check KEYS, not free-text values, so audit prose containing
# words such as "returns" does not create a false positive.
FORBIDDEN_KEY_FRAGMENTS = (
    "forwardreturn",
    "futurereturn",
    "holdingreturn",
    "entryprice",
    "exitprice",
    "futureprice",
    "postsignalprice",
    "mae",
    "mfe",
    "winnerlabel",
    "outcomelabel",
    "n0return",
    "n1return",
    "n2return",
    "n3return",
    "nullreturn",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_key(s: Any) -> str:
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def walk_forbidden_keys(obj: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            nk = normalize_key(k)
            if any(fragment in nk for fragment in FORBIDDEN_KEY_FRAGMENTS):
                hits.append(f"{path}.{k}")
            hits.extend(walk_forbidden_keys(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(walk_forbidden_keys(v, f"{path}[{i}]"))
    return hits


def extract_rows(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, list):
        rows = obj
    elif isinstance(obj, dict):
        for key in ("rows", "events", "data"):
            if isinstance(obj.get(key), list):
                rows = obj[key]
                break
        else:
            raise ValueError("ROWS_JSON_HAS_NO_LIST_PAYLOAD")
    else:
        raise ValueError("ROWS_JSON_UNSUPPORTED_ROOT")
    if not all(isinstance(x, dict) for x in rows):
        raise ValueError("ROWS_PAYLOAD_CONTAINS_NON_OBJECT")
    return rows


def finite_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def period_key(row: dict[str, Any]) -> str | None:
    for key in ("period", "current_period", "fiscal_period", "company_quarter"):
        v = row.get(key)
        if isinstance(v, str):
            s = v.upper().replace(" ", "").replace("-", "")
            if len(s) == 6 and s[:4].isdigit() and s[4] == "Q" and s[5] in "1234":
                return s
    year = row.get("year", row.get("fiscal_year"))
    q = row.get("quarter", row.get("fiscal_quarter"))
    try:
        y = int(year)
        qq = int(q)
        if 2000 <= y <= 2100 and 1 <= qq <= 4:
            return f"{y}Q{qq}"
    except Exception:
        pass
    return None


def ticker_of(row: dict[str, Any]) -> str:
    return str(row.get("ticker", row.get("stock_id", ""))).strip()


def accepted_bulk_receipt(receipt: Any) -> bool:
    if not isinstance(receipt, dict):
        return False
    # V0.2 requires the hard-validation receipt, not merely HTTP 200 / PK magic.
    return (
        receipt.get("transport_validation_version") == "CENTRAL_DIRECTORY_PLUS_MEMBER_READ_V0_2"
        and receipt.get("central_directory_valid") is True
        and int(receipt.get("matched_consolidated_member_count", 0)) > 100
        and receipt.get("sample_member_reads_pass") is True
        and receipt.get("accepted") is True
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    ap.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    failures: list[str] = []

    if not args.rows.exists():
        failures.append(f"MISSING_ROWS_ARTIFACT:{args.rows}")
    if not args.audit.exists():
        failures.append(f"MISSING_AUDIT_ARTIFACT:{args.audit}")
    if failures:
        result = {
            "challenger": "IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1",
            "gate": "STAGE_A_NO_RETURN_INTEGRITY",
            "verdict": "NOT_RUN_INPUT_ARTIFACTS_MISSING",
            "failures": failures,
            "forward_returns_inspected": False,
            "network_access_performed": False,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    raw_rows = load_json(args.rows)
    audit = load_json(args.audit)
    rows = extract_rows(raw_rows)

    forbidden_hits = walk_forbidden_keys(raw_rows) + walk_forbidden_keys(audit)
    if forbidden_hits:
        failures.append("OUTCOME_BEARING_KEYS_PRESENT:" + ",".join(forbidden_hits[:50]))

    # Frozen fiscal-period geometry from the pre-return erratum.
    audit_required = audit.get("required_bulk_periods") if isinstance(audit, dict) else None
    if audit_required is None:
        failures.append("AUDIT_MISSING_REQUIRED_BULK_PERIODS")
    else:
        got_required = sorted(str(x).upper().replace(" ", "") for x in audit_required)
        if got_required != sorted(REQUIRED_PERIODS):
            failures.append(f"REQUIRED_PERIOD_SET_MISMATCH:{got_required}")

    row_periods = Counter(period_key(r) or "UNRESOLVED" for r in rows)
    extra_current_periods = sorted(p for p in row_periods if p not in CURRENT_PERIODS)
    if "UNRESOLVED" in row_periods:
        failures.append(f"UNRESOLVED_ROW_PERIOD_COUNT:{row_periods['UNRESOLVED']}")
    if extra_current_periods:
        failures.append(f"NONLEGAL_STAGE_A_CURRENT_PERIODS:{extra_current_periods}")
    missing_current_periods = sorted(set(CURRENT_PERIODS) - set(row_periods))
    if missing_current_periods:
        failures.append(f"MISSING_STAGE_A_CURRENT_PERIODS:{missing_current_periods}")

    if isinstance(audit, dict):
        if int(audit.get("pair_attempt_count", -1)) != len(rows):
            failures.append(
                f"PAIR_ATTEMPT_COUNT_MISMATCH:audit={audit.get('pair_attempt_count')}:rows={len(rows)}"
            )
        if int(audit.get("parser_crosscheck_mismatch_count", -1)) != 0:
            failures.append(
                f"PARSER_CROSSCHECK_MISMATCH_COUNT:{audit.get('parser_crosscheck_mismatch_count')}"
            )

        receipts = audit.get("bulk_receipts")
        if not isinstance(receipts, list) or not receipts:
            failures.append("AUDIT_MISSING_BULK_RECEIPTS")
        else:
            bad = [
                f"{r.get('year')}Q{r.get('quarter')}"
                for r in receipts
                if not accepted_bulk_receipt(r)
            ]
            if bad:
                failures.append(f"BULK_RECEIPT_HARD_VALIDATION_FAIL:{bad}")

    recomputed_candidates: list[dict[str, Any]] = []
    condition_shape_fail = 0
    candidate_flag_mismatch = 0
    candidate_with_exclusion_reason = 0
    candidate_accounting_shape_fail = 0
    candidate_denominator_fail = 0

    for row in rows:
        conds = row.get("conditions")
        stored_candidate = row.get("accounting_6of6_pre_metadata_candidate")
        pair_available = row.get("accounting_pair_available") is True

        if pair_available:
            if not isinstance(conds, dict) or any(k not in conds or not isinstance(conds[k], bool) for k in CONDITION_FIELDS):
                condition_shape_fail += 1
                continue
            recomputed = all(conds[k] for k in CONDITION_FIELDS)
            if stored_candidate is not recomputed:
                candidate_flag_mismatch += 1
            if recomputed:
                recomputed_candidates.append(row)
                if row.get("exclusion_reason") not in (None, ""):
                    candidate_with_exclusion_reason += 1

                cur = row.get("current")
                prev = row.get("prior")
                if not isinstance(cur, dict) or not isinstance(prev, dict):
                    candidate_accounting_shape_fail += 1
                    continue
                if any(k not in cur or not finite_number(cur[k]) for k in ACCOUNTING_FIELDS):
                    candidate_accounting_shape_fail += 1
                    continue
                if any(k not in prev or not finite_number(prev[k]) for k in ACCOUNTING_FIELDS):
                    candidate_accounting_shape_fail += 1
                    continue

                # Every denominator used by frozen derived variables must be > 0.
                denominators = [
                    cur["Revenue_YTD"],
                    prev["Revenue_YTD"],
                    prev["AR"],
                    prev["COGS_YTD"],
                    prev["Inventory"],
                    cur["Assets"],
                    prev["Assets"],
                ]
                if not all(finite_number(x) and float(x) > 0 for x in denominators):
                    candidate_denominator_fail += 1
        else:
            if stored_candidate is True:
                candidate_flag_mismatch += 1

    if condition_shape_fail:
        failures.append(f"CONDITION_SHAPE_FAIL:{condition_shape_fail}")
    if candidate_flag_mismatch:
        failures.append(f"CANDIDATE_FLAG_MISMATCH:{candidate_flag_mismatch}")
    if candidate_with_exclusion_reason:
        failures.append(f"CANDIDATE_HAS_EXCLUSION_REASON:{candidate_with_exclusion_reason}")
    if candidate_accounting_shape_fail:
        failures.append(f"CANDIDATE_ACCOUNTING_SHAPE_FAIL:{candidate_accounting_shape_fail}")
    if candidate_denominator_fail:
        failures.append(f"CANDIDATE_DENOMINATOR_FAIL:{candidate_denominator_fail}")

    candidate_count = len(recomputed_candidates)
    candidate_unique = len({ticker_of(r) for r in recomputed_candidates if ticker_of(r)})
    candidate_periods = Counter(period_key(r) or "UNRESOLVED" for r in recomputed_candidates)

    if isinstance(audit, dict):
        if int(audit.get("accounting_6of6_pre_metadata_candidate_count", -1)) != candidate_count:
            failures.append(
                "AUDIT_CANDIDATE_COUNT_MISMATCH:"
                f"audit={audit.get('accounting_6of6_pre_metadata_candidate_count')}:recomputed={candidate_count}"
            )
        if int(audit.get("accounting_6of6_pre_metadata_candidate_unique_tickers", -1)) != candidate_unique:
            failures.append(
                "AUDIT_UNIQUE_TICKER_COUNT_MISMATCH:"
                f"audit={audit.get('accounting_6of6_pre_metadata_candidate_unique_tickers')}:recomputed={candidate_unique}"
            )
        audit_by_period = audit.get("accounting_6of6_pre_metadata_candidate_by_period")
        if isinstance(audit_by_period, dict):
            normalized = {str(k): int(v) for k, v in audit_by_period.items() if int(v) != 0}
            recomputed_period_nonzero = {k: int(v) for k, v in candidate_periods.items() if v != 0}
            if normalized != recomputed_period_nonzero:
                failures.append(
                    f"AUDIT_CANDIDATE_BY_PERIOD_MISMATCH:audit={normalized}:recomputed={recomputed_period_nonzero}"
                )
        else:
            failures.append("AUDIT_MISSING_CANDIDATE_BY_PERIOD")

    if failures:
        verdict = "FAIL_INTEGRITY"
    elif candidate_count < MIN_EVENTS or candidate_unique < MIN_UNIQUE_TICKERS:
        verdict = "INCONCLUSIVE_SAMPLE_INSUFFICIENT_PRE_RETURN_UPPER_BOUND"
    else:
        verdict = "STAGE_A_PASS_TO_EXACT_METADATA_GATE"

    result = {
        "challenger": "IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1",
        "gate": "STAGE_A_NO_RETURN_INTEGRITY",
        "verdict": verdict,
        "forward_returns_inspected": False,
        "network_access_performed": False,
        "research_thresholds_changed": False,
        "row_count": len(rows),
        "current_period_counts": dict(sorted(row_periods.items())),
        "candidate_count_recomputed": candidate_count,
        "candidate_unique_tickers_recomputed": candidate_unique,
        "candidate_by_period_recomputed": dict(sorted(candidate_periods.items())),
        "minimum_required_events": MIN_EVENTS,
        "minimum_required_unique_tickers": MIN_UNIQUE_TICKERS,
        "signal_date_minimum_assessed": False,
        "exact_t57_metadata_assessed": False,
        "pit_electronics_membership_assessed": False,
        "discovery_returns_authorized": False,
        "failures": failures,
        "next_legal_step": (
            "STOP_REPAIR_FROZEN_ENGINEERING_CONTRACT_ONLY"
            if verdict == "FAIL_INTEGRITY"
            else "STOP_IF07_V0_1_INCONCLUSIVE_WITHOUT_RETURNS"
            if verdict == "INCONCLUSIVE_SAMPLE_INSUFFICIENT_PRE_RETURN_UPPER_BOUND"
            else "EXACT_T57_METADATA_THEN_SIGNAL_DATE_AND_PIT_UNIVERSE_GATES_NO_RETURNS"
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if verdict == "STAGE_A_PASS_TO_EXACT_METADATA_GATE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
