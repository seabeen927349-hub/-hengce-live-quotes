#!/usr/bin/env python3
"""Unify legacy HENGCE and canonical frozen Q017 candidates without score fusion.

Q017 is a candidate source only.  This adapter never recomputes the frozen Q017
score and never invents legacy entry geometry.  A Q017-only ticker enters the
single HENGCE candidate set with geometry_status=UNAVAILABLE and therefore must
fail closed downstream until an existing legal geometry builder supplies it.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any
from hengce_unified_contracts import ticker as _ticker, geometry, finite, strict_loads, atomic, digest, ZERO_AUTHORITY, aware

# No verified canonical producer was found in repository/history/handoff.
# Admission requires a reviewed code-commit allowlist change; artifact fields
# alone cannot certify that PIT inputs or canonical mathematics were used.
VERIFIED_Q017_PRODUCERS = frozenset()

CANONICAL_Q017 = {
    "universe": "TWSE_LISTED_ELECTRONICS_PIT_DAILY",
    "beta_history_max": 60,
    "beta_history_min": 30,
    "signal_day_excluded_from_beta": True,
    "k": 25,
    "score": "beta60*(1+25*max(-residual1,0))",
    "top_n": 1,
    "avg_turnover20_min": 20_000_000,
    "residual1_max": 0.04,
    "electronics_m1_max_exclusive": 0.0,
    "electronics_m5_max": -0.02,
    "sox_1d_max": 0.0,
    "sox_5d_max": -0.03,
    "dxy_used": False,
    "entry": "NEXT_TWSE_OPEN",
    "exit": "FIXED_20_SESSIONS",
    "roundtrip_cost": 0.008,
    "overlap_allowed": False,
}


def _first(d: dict[str, Any], names: list[str], default=None):
    for name in names:
        if name in d and d[name] is not None:
            return d[name]
    return default


def _extract_rows(base: Any) -> list[dict[str, Any]]:
    if isinstance(base, list):
        return [x for x in base if isinstance(x, dict)]
    if not isinstance(base, dict):
        return []
    for key in ["rows", "data", "rankings", "candidates", "results", "table", "stocks"]:
        value = base.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    out = []
    for key, value in base.items():
        if isinstance(value, dict) and (str(key).isdigit() or _ticker(value)):
            row = dict(value)
            row.setdefault("Ticker", key)
            out.append(row)
    return out


def _geometry_available(row):
    return geometry(row) is not None


def _legacy_score(row: dict[str, Any]):
    return _first(row, ["LegacyScore", "AlphaScore", "alpha_score", "CompositeScore", "composite_score", "score"])


def _rules(q017: dict[str, Any]) -> dict[str, Any]:
    value = q017.get("canonical_q017_contract") or q017.get("rules") or {}
    return value if isinstance(value, dict) else {}


def _norm_score_rule(value: Any) -> str:
    return str(value or "").replace(" ", "")


def validate_q017_contract(q017: Any) -> tuple[bool, list[str]]:
    if not isinstance(q017, dict):
        return False, ["Q017_NOT_OBJECT"]
    if str(q017.get("system") or "").upper() != "HENGCE":
        return False, ["Q017_SYSTEM_NOT_HENGCE"]
    rules = _rules(q017)
    errors: list[str] = []
    if q017.get('schema_version') != 1 or q017.get('module') != 'HENGCE_CANONICAL_Q017_CANDIDATES':
        errors.append('Q017_UNSUPPORTED_SCHEMA_OR_MODULE')
    producer = q017.get('producer')
    import re
    if not isinstance(producer, dict) or not re.fullmatch(r'[0-9a-f]{40}', str(producer.get('code_commit', ''))):
        errors.append('Q017_PRODUCER_LINEAGE_MISSING')
    if not isinstance(producer, dict) or producer.get('code_commit') not in VERIFIED_Q017_PRODUCERS:
        errors.append('Q017_PRODUCER_NOT_VERIFIED')
    hashes = producer.get('input_hashes') if isinstance(producer, dict) else None
    if not isinstance(hashes, dict) or not hashes or any(not re.fullmatch(r'[0-9a-f]{64}', str(h)) for h in hashes.values()):
        errors.append('Q017_INPUT_LINEAGE_MISSING')
    try:
        generated = aware(q017.get('generated_at'))
        if generated.date().isoformat() != q017.get('trade_date'):
            errors.append('Q017_GENERATION_SESSION_MISMATCH')
    except (ValueError, TypeError):
        errors.append('Q017_TIMESTAMP_MISSING_OR_INVALID')
    if q017.get('binding_status') != 'PASS' or q017.get('market_state') not in {'GO', 'CASH'}:
        errors.append('Q017_STATE_NOT_EXPLICIT')

    aliases = {
        "universe": ["universe", "universe_scope"],
        "beta_history_max": ["beta_history_max", "beta_max_observations"],
        "beta_history_min": ["beta_history_min", "beta_min_observations"],
        "signal_day_excluded_from_beta": ["signal_day_excluded_from_beta", "signal_day_excluded"],
        "k": ["k", "K"],
        "top_n": ["top_n", "selection_top_n"],
        "avg_turnover20_min": ["avg_turnover20_min", "turnover20_min", "avg_turnover_20d_min"],
        "residual1_max": ["residual1_max", "residual_max"],
        "electronics_m1_max_exclusive": ["electronics_m1_max_exclusive"],
        "electronics_m5_max": ["electronics_m5_max"],
        "sox_1d_max": ["sox_1d_max"],
        "sox_5d_max": ["sox_5d_max"],
        "dxy_used": ["dxy_used"],
        "entry": ["entry", "entry_rule"],
        "exit": ["exit", "exit_rule"],
        "roundtrip_cost": ["roundtrip_cost", "round_trip_cost"],
        "overlap_allowed": ["overlap_allowed"],
    }
    for key, expected in CANONICAL_Q017.items():
        if key == "score":
            got = _norm_score_rule(_first(rules, ["score", "score_formula"]))
            if got != _norm_score_rule(expected):
                errors.append(f"Q017_RULE_MISMATCH:score:{got!r}")
            continue
        got = _first(rules, aliases[key])
        if isinstance(expected, float):
            try:
                equal = not isinstance(got, bool) and isinstance(got, (float, int)) and finite(got) == expected
            except Exception:
                equal = False
        elif isinstance(expected, int) and not isinstance(expected, bool):
            try:
                equal = type(got) is int and got == expected
            except Exception:
                equal = False
        else:
            equal = type(got) is type(expected) and got == expected
        if not equal:
            errors.append(f"Q017_RULE_MISMATCH:{key}:{got!r}")
    return not errors, errors


def _q017_candidates(q017: dict[str, Any]) -> list[dict[str, Any]]:
    if str(q017.get("binding_status") or "").upper() not in {"PASS", "BOUND"}:
        return []
    state = str(q017.get("market_state") or q017.get("state") or "UNAVAILABLE").upper()
    if state not in {"GO", "ELIGIBLE", "ACTIVE"}:
        if q017.get('candidates'):
            raise ValueError('Q017_CASH_WITH_CANDIDATES')
        return []
    rows = q017.get("candidates")
    if not isinstance(rows, list):
        rows = q017.get("top1")
        if isinstance(rows, dict):
            rows = [rows]
        elif not isinstance(rows, list):
            rows = []
    if len(rows) != 1:
        raise ValueError("Q017_TOP1_CARDINALITY")
    selected = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Q017_CANDIDATE_NOT_OBJECT")
        rank = _first(row, ["q017_rank", "rank", "Rank"])
        score = finite(_first(row, ["q017_score", "score"]))
        beta = finite(_first(row, ["beta60", "beta"]))
        residual = finite(_first(row, ["residual1", "residual"]))
        if type(rank) is not int or rank != 1 or row.get("qualified") is not True:
            raise ValueError("Q017_INVALID_RANK_OR_QUALIFICATION")
        if None in (score, beta, residual) or residual > .04:
            raise ValueError("Q017_INVALID_NUMERIC_EVIDENCE")
        # Validate the explicitly frozen identity; never compute a new signal.
        import math
        if not math.isclose(score, beta * (1 + 25 * max(-residual, 0)), rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("Q017_SCORE_EVIDENCE_MISMATCH")
        evidence = row.get('filter_evidence', {})
        checks = {'avg_turnover20': lambda x: x >= 20_000_000,
                  'electronics_m1': lambda x: x < 0, 'electronics_m5': lambda x: x <= -.02,
                  'sox_1d': lambda x: x <= 0, 'sox_5d': lambda x: x <= -.03}
        if not isinstance(evidence, dict) or any(finite(evidence.get(k)) is None or not check(finite(evidence[k])) for k, check in checks.items()):
            raise ValueError('Q017_FILTER_EVIDENCE_UNAVAILABLE_OR_INVALID')
        if not _ticker(row):
            raise ValueError("Q017_MISSING_TICKER")
        selected.append(row)
    return selected


def build(legacy_base: Any, q017: Any | None = None) -> dict[str, Any]:
    if not isinstance(legacy_base, dict):
        raise ValueError("LEGACY_BASE_NOT_OBJECT")
    if 'schema_version' in legacy_base and (type(legacy_base['schema_version']) is not int or legacy_base['schema_version'] not in {1, 2}):
        raise ValueError('UNSUPPORTED_LEGACY_SCHEMA')
    # strict JSON round trip also rejects non-finite in-memory input.
    strict_loads(json.dumps(legacy_base, allow_nan=False))
    collections = [legacy_base[k] for k in ["rows", "data", "rankings", "candidates", "results", "table", "stocks"] if k in legacy_base]
    if not collections or any(value != collections[0] for value in collections):
        raise ValueError("MISSING_OR_AMBIGUOUS_LEGACY_ROWS")
    legacy_rows = _extract_rows(legacy_base)
    for key in ["rows", "data", "rankings", "candidates", "results", "table", "stocks"]:
        if key in legacy_base and (not isinstance(legacy_base[key], list) or
                                  any(not isinstance(r, dict) for r in legacy_base[key])):
            raise ValueError("MALFORMED_LEGACY_ROWS")
    rows: list[dict[str, Any]] = []
    by_ticker: dict[str, dict[str, Any]] = {}

    for original in legacy_rows:
        for keys in [('FormalEntryTrigger', 'formal_entry_trigger', 'EntryTrigger', 'entry_trigger'),
                     ('PositionHeld', 'position_held', 'Held', 'held'), ('FormalCandidate',)]:
            values = [original[k] for k in keys if k in original]
            if any(type(v) is not bool for v in values) or len(set(values)) > 1:
                raise ValueError('INVALID_OR_CONFLICTING_ACTIVATION_FLAGS')
        for key in ('rank', 'Rank', 'LegacyRank'):
            if key in original and (type(original[key]) is not int or original[key] < 1):
                raise ValueError('INVALID_LEGACY_RANK')
        score_value = _legacy_score(original)
        if score_value is not None and finite(score_value) is None:
            raise ValueError('INVALID_LEGACY_SCORE')
        ticker = _ticker(original)
        if not ticker:
            raise ValueError("LEGACY_MISSING_TICKER")
        if ticker in by_ticker:
            previous = by_ticker[ticker]["LegacyEvidence"]
            comparable = copy.deepcopy(original)
            for key in ("Ticker", "ticker", "Symbol", "symbol", "StockNo", "stock_no", "證券代號"):
                comparable.pop(key, None)
            comparable["Ticker"] = ticker
            if previous != comparable:
                raise ValueError("CONFLICTING_DUPLICATE_LEGACY_TICKER:" + ticker)
            continue
        row = copy.deepcopy(original)
        for key in ("Ticker", "ticker", "Symbol", "symbol", "StockNo", "stock_no", "證券代號"):
            row.pop(key, None)
        row["Ticker"] = ticker
        evidence = copy.deepcopy(row)
        for key in list(row):
            if key.startswith("Q017") or key in {"UnifiedScore", "CombinedScore", "SourceProvenance"}:
                row.pop(key)
        row["LegacyEvidence"] = evidence
        row["Q017Evidence"] = None
        row["SourceProvenance"] = "LEGACY"
        row["LegacyScore"] = _legacy_score(row)
        row.setdefault("Q017Score", None)
        row.setdefault("Q017Rank", None)
        row.setdefault("Q017Beta60", None)
        row.setdefault("Q017Residual1", None)
        row["GeometryStatus"] = "AVAILABLE" if _geometry_available(row) else "UNAVAILABLE"
        row["FormalCandidate"] = original.get("FormalCandidate", True) is True
        rows.append(row)
        by_ticker[ticker] = row

    q017_hash = None
    if q017 is not None:
        try:
            q017_hash = digest(q017)
        except (ValueError, TypeError):
            q017 = {"input_error": "Q017_NONFINITE_OR_UNSERIALIZABLE"}
    q017_status = "NOT_PROVIDED"
    q017_errors: list[str] = []
    q017_trade_date = None
    q017_added = 0
    q017_merged = 0
    if q017 is not None:
        valid, q017_errors = validate_q017_contract(q017)
        q017_trade_date = q017.get("trade_date") if isinstance(q017, dict) else None
        if not valid:
            q017_status = "FAIL_CLOSED_CONTRACT_MISMATCH"
        else:
            q017_status = "PASS"
            try:
                candidates = _q017_candidates(q017)
                if q017.get("trade_date") != legacy_base.get("valid_for_trade_date", legacy_base.get("trade_date", q017.get("trade_date"))):
                    raise ValueError("Q017_SESSION_MISMATCH")
            except (ValueError, TypeError) as exc:
                q017_status = "FAIL_CLOSED_INVALID_CANDIDATE"
                q017_errors.append(str(exc))
                candidates = []
            for candidate in candidates:
                ticker = _ticker(candidate)
                score = _first(candidate, ["q017_score", "score"])
                beta = _first(candidate, ["beta60", "beta"])
                residual = _first(candidate, ["residual1", "residual"])
                name = _first(candidate, ["Name", "name", "company_name"])
                if ticker in by_ticker:
                    row = by_ticker[ticker]
                    row["SourceProvenance"] = "BOTH"
                    row["Q017Score"] = score
                    row["Q017Rank"] = 1
                    row["Q017Beta60"] = beta
                    row["Q017Residual1"] = residual
                    row["FormalCandidate"] = True
                    row["Q017Evidence"] = copy.deepcopy(candidate)
                    q017_merged += 1
                else:
                    row = {
                        "Ticker": ticker,
                        "Name": name,
                        "SourceProvenance": "Q017",
                        "LegacyScore": None,
                        "Q017Score": score,
                        "Q017Rank": 1,
                        "Q017Beta60": beta,
                        "Q017Residual1": residual,
                        "FormalCandidate": True,
                        "GeometryStatus": "UNAVAILABLE",
                        "FormalEntryTrigger": False,
                        "ActivationState": "Q017_CANDIDATE_GEOMETRY_PENDING",
                    }
                    row["LegacyEvidence"] = None
                    row["Q017Evidence"] = copy.deepcopy(candidate)
                    rows.append(row)
                    by_ticker[ticker] = row
                    q017_added += 1

    counts = {"LEGACY": 0, "Q017": 0, "BOTH": 0}
    for row in rows:
        counts[row["SourceProvenance"]] += 1

    rows.sort(key=lambda row: row["Ticker"])
    base_dict = legacy_base if isinstance(legacy_base, dict) else {}
    return {
        "schema_version": 2,
        **ZERO_AUTHORITY,
        "source_hashes": {"legacy": digest(legacy_base), "q017": q017_hash},
        "trade_date": base_dict.get("valid_for_trade_date", base_dict.get("trade_date")),
        "generated_at": base_dict.get("generated_at_taipei", base_dict.get("generated_at")),
        "system": "HENGCE",
        "module": "HENGCE_UNIFIED_CANDIDATE_ADAPTER",
        "run_id": str(_first(base_dict, ["run_id", "RunId", "scan_id", "ScanId"], "UNKNOWN")) + ":UNIFIED_Q017",
        "candidate_union_policy": "UNION_DEDUP_BY_TICKER_NO_SCORE_FUSION",
        "score_fusion": False,
        "q017_is_internal_candidate_source": True,
        "q017_contract_status": q017_status,
        "q017_contract_errors": q017_errors,
        "q017_trade_date": q017_trade_date,
        "legacy_candidate_count": len(legacy_rows),
        "q017_added_count": q017_added,
        "q017_merged_existing_count": q017_merged,
        "candidate_count": len(rows),
        "source_provenance_counts": counts,
        "geometry_policy": "REUSE_EXISTING_LEGAL_GEOMETRY_OR_MARK_UNAVAILABLE_FAIL_CLOSED",
        "rows": rows,
    }


def _self_test_cases() -> None:
    legacy = {
        "run_id": "LEGACY_TEST",
        "rows": [
            {"Ticker": "2330", "AlphaScore": 0.91, "BreakoutLower": 100, "BreakoutUpper": 105, "NoChase": 110, "InvalidationPrice": 90, "FormalEntryTrigger": True},
            {"Ticker": "2454", "AlphaScore": 0.73, "FormalEntryTrigger": False},
        ],
    }
    rules = dict(CANONICAL_Q017)
    q = {
        "schema_version": 1, "module": "HENGCE_CANONICAL_Q017_CANDIDATES",
        "producer": {"code_commit": "0" * 40, "input_hashes": {"synthetic": "0" * 64}},
        "generated_at": "2026-10-23T10:00:00+08:00",
        "system": "HENGCE", "binding_status": "PASS", "market_state": "GO", "trade_date": "2026-10-23",
        "canonical_q017_contract": rules,
        "candidates": [{"ticker": "2330", "name": "台積電", "rank": 1, "beta60": 1.2, "residual1": -0.03, "score": 2.1, "qualified": True, "filter_evidence": {"avg_turnover20": 30000000, "electronics_m1": -.01, "electronics_m5": -.03, "sox_1d": -.01, "sox_5d": -.04}}],
    }
    out = build(legacy, q)
    assert out["candidate_count"] == 2
    assert out["source_provenance_counts"] == {"LEGACY": 1, "Q017": 0, "BOTH": 1}
    tsmc = next(r for r in out["rows"] if r["Ticker"] == "2330")
    assert tsmc["SourceProvenance"] == "BOTH" and tsmc["Q017Score"] == 2.1
    assert tsmc["LegacyScore"] == 0.91 and tsmc["GeometryStatus"] == "AVAILABLE"

    q2 = copy.deepcopy(q)
    q2["candidates"][0]["ticker"] = "3008"
    out2 = build(legacy, q2)
    lasertek = next(r for r in out2["rows"] if r["Ticker"] == "3008")
    assert lasertek["SourceProvenance"] == "Q017"
    assert lasertek["GeometryStatus"] == "UNAVAILABLE"
    assert lasertek["FormalEntryTrigger"] is False

    q_bad = copy.deepcopy(q)
    q_bad["canonical_q017_contract"]["top_n"] = 3
    q_bad["canonical_q017_contract"]["dxy_used"] = True
    out3 = build(legacy, q_bad)
    assert out3["q017_contract_status"] == "FAIL_CLOSED_CONTRACT_MISMATCH"
    assert out3["candidate_count"] == 2 and out3["q017_added_count"] == 0
    assert any("top_n" in e for e in out3["q017_contract_errors"])
    assert any("dxy_used" in e for e in out3["q017_contract_errors"])

    q_cash = copy.deepcopy(q)
    q_cash["market_state"] = "CASH"
    q_cash["candidates"] = []
    out4 = build(legacy, q_cash)
    assert out4["q017_contract_status"] == "PASS"
    assert out4["q017_added_count"] == 0 and out4["q017_merged_existing_count"] == 0

    print("SELF_TEST_PASS: unified Q017 candidate union, dedupe, provenance and fail-closed contract")


def _self_test():
    # Synthetic trust injection is restricted to this explicit offline self-test.
    from unittest.mock import patch
    with patch(__name__ + '.VERIFIED_Q017_PRODUCERS', frozenset({'0' * 40})):
        _self_test_cases()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--legacy-base")
    ap.add_argument("--q017")
    ap.add_argument("--output")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        _self_test()
        return 0
    if not args.legacy_base or not args.output:
        ap.error("--legacy-base and --output are required unless --self-test")
    legacy = strict_loads(Path(args.legacy_base).read_text(encoding="utf-8"))
    q017 = None
    if args.q017:
        qpath = Path(args.q017)
        try:
            q017 = strict_loads(qpath.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            q017 = {"input_error": "Q017_UNREADABLE_OR_MALFORMED"}
    out = build(legacy, q017)
    out_path = Path(args.output)
    atomic(out_path, out)
    print(json.dumps({
        "system": "HENGCE",
        "candidate_count": out["candidate_count"],
        "provenance": out["source_provenance_counts"],
        "q017_contract_status": out["q017_contract_status"],
        "output": str(out_path),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
