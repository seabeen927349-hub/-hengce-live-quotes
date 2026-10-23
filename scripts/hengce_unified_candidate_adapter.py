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


def _ticker(row: dict[str, Any]) -> str:
    value = _first(row, ["Ticker", "ticker", "Symbol", "symbol", "StockNo", "stock_no", "證券代號"])
    return str(value).strip() if value is not None else ""


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


def _geometry_available(row: dict[str, Any]) -> bool:
    def present(names: list[str]) -> bool:
        return _first(row, names) not in (None, "")
    return all([
        present(["BreakoutLower", "breakout_lower", "breakout_low", "BreakoutLow", "breakout_zone_low", "BreakoutZoneLow"]),
        present(["BreakoutUpper", "breakout_upper", "breakout_high", "BreakoutHigh", "breakout_zone_high", "BreakoutZoneHigh"]),
        present(["NoChase", "no_chase", "NoChasePrice", "no_chase_price"]),
        present(["Invalidation", "InvalidationPrice", "invalid", "invalid_price", "StructureInvalidation"]),
    ])


def _legacy_score(row: dict[str, Any]):
    return _first(row, ["LegacyScore", "AlphaScore", "alpha_score", "CompositeScore", "composite_score", "score"])


def _rules(q017: dict[str, Any]) -> dict[str, Any]:
    value = q017.get("canonical_q017_contract") or q017.get("rules") or {}
    return value if isinstance(value, dict) else {}


def _norm_score_rule(value: Any) -> str:
    return str(value or "").replace(" ", "").replace("beta*", "beta60*")


def validate_q017_contract(q017: Any) -> tuple[bool, list[str]]:
    if not isinstance(q017, dict):
        return False, ["Q017_NOT_OBJECT"]
    if str(q017.get("system") or "HENGCE").upper() != "HENGCE":
        return False, ["Q017_SYSTEM_NOT_HENGCE"]
    rules = _rules(q017)
    errors: list[str] = []

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
                equal = abs(float(got) - expected) <= 1e-12
            except Exception:
                equal = False
        elif isinstance(expected, int) and not isinstance(expected, bool):
            try:
                equal = int(got) == expected
            except Exception:
                equal = False
        else:
            equal = got == expected
        if not equal:
            errors.append(f"Q017_RULE_MISMATCH:{key}:{got!r}")
    return not errors, errors


def _q017_candidates(q017: dict[str, Any]) -> list[dict[str, Any]]:
    if str(q017.get("binding_status") or "").upper() not in {"PASS", "BOUND"}:
        return []
    state = str(q017.get("market_state") or q017.get("state") or "GO").upper()
    if state not in {"GO", "ELIGIBLE", "ACTIVE"}:
        return []
    rows = q017.get("candidates")
    if not isinstance(rows, list):
        rows = q017.get("top1")
        if isinstance(rows, dict):
            rows = [rows]
        elif not isinstance(rows, list):
            rows = []
    selected = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        rank = _first(row, ["q017_rank", "rank", "Rank"], 1)
        try:
            rank = int(rank)
        except Exception:
            continue
        if rank != 1:
            continue
        if row.get("qualified") is False or row.get("eligible") is False:
            continue
        if _ticker(row):
            selected.append(row)
    return selected[:1]


def build(legacy_base: Any, q017: Any | None = None) -> dict[str, Any]:
    legacy_rows = _extract_rows(legacy_base)
    rows: list[dict[str, Any]] = []
    by_ticker: dict[str, dict[str, Any]] = {}

    for original in legacy_rows:
        ticker = _ticker(original)
        if not ticker or ticker in by_ticker:
            continue
        row = copy.deepcopy(original)
        row["Ticker"] = ticker
        row["SourceProvenance"] = "LEGACY"
        row["LegacyScore"] = _legacy_score(row)
        row.setdefault("Q017Score", None)
        row.setdefault("Q017Rank", None)
        row.setdefault("Q017Beta60", None)
        row.setdefault("Q017Residual1", None)
        row["GeometryStatus"] = "AVAILABLE" if _geometry_available(row) else "UNAVAILABLE"
        row["FormalCandidate"] = True
        rows.append(row)
        by_ticker[ticker] = row

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
            for candidate in _q017_candidates(q017):
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
                    rows.append(row)
                    by_ticker[ticker] = row
                    q017_added += 1

    counts = {"LEGACY": 0, "Q017": 0, "BOTH": 0}
    for row in rows:
        counts[row["SourceProvenance"]] += 1

    base_dict = legacy_base if isinstance(legacy_base, dict) else {}
    return {
        "schema_version": 1,
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


def _self_test() -> None:
    legacy = {
        "run_id": "LEGACY_TEST",
        "rows": [
            {"Ticker": "2330", "AlphaScore": 0.91, "BreakoutLower": 100, "BreakoutUpper": 105, "NoChase": 110, "InvalidationPrice": 90, "FormalEntryTrigger": True},
            {"Ticker": "2454", "AlphaScore": 0.73, "FormalEntryTrigger": False},
        ],
    }
    rules = dict(CANONICAL_Q017)
    q = {
        "system": "HENGCE", "binding_status": "PASS", "market_state": "GO", "trade_date": "2026-10-23",
        "canonical_q017_contract": rules,
        "candidates": [{"ticker": "2330", "name": "台積電", "rank": 1, "beta60": 1.2, "residual1": -0.03, "score": 2.1, "qualified": True}],
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
    out4 = build(legacy, q_cash)
    assert out4["q017_contract_status"] == "PASS"
    assert out4["q017_added_count"] == 0 and out4["q017_merged_existing_count"] == 0

    print("SELF_TEST_PASS: unified Q017 candidate union, dedupe, provenance and fail-closed contract")


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
    legacy = json.loads(Path(args.legacy_base).read_text(encoding="utf-8"))
    q017 = None
    if args.q017:
        qpath = Path(args.q017)
        if qpath.exists():
            q017 = json.loads(qpath.read_text(encoding="utf-8"))
    out = build(legacy, q017)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(out_path)
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
