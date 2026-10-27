#!/usr/bin/env python3
"""Thin HENGCE action-board wrapper that preserves unified candidate evidence."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import hengce_intraday_action_board as core
import hengce_q017_structure_exit as q017_structure_exit
from hengce_unified_contracts import ticker as _ticker, geometry, digest, atomic, strict_loads, ZERO_AUTHORITY


def _effective_trade_date(base, live, explicit=None):
    if explicit:
        return str(explicit)
    if isinstance(base, dict):
        for key in ("valid_for_trade_date", "trade_date", "TradeDate"):
            if base.get(key):
                return str(base[key])[:10]
    if isinstance(live, dict):
        dates = {
            str(r.get("quote_date"))[:10]
            for r in live.get("data", [])
            if isinstance(r, dict) and r.get("quote_date")
        }
        if len(dates) == 1:
            return next(iter(dates))
    return None


def build(base, live, context, trade_date=None, max_age_seconds=480, now=None):
    if not isinstance(base, dict) or base.get('module') != 'HENGCE_UNIFIED_CANDIDATE_ADAPTER' or base.get('schema_version') != 2:
        raise ValueError('UNSUPPORTED_UNIFIED_BASE_SCHEMA')
    seen = set()
    for row in base.get('rows', []):
        name = _ticker(row)
        if not name or name in seen or row.get('SourceProvenance') not in {'LEGACY', 'Q017', 'BOTH'}:
            raise ValueError('INVALID_UNIFIED_CANDIDATE')
        seen.add(name)
        if row.get('SourceProvenance') == 'Q017' and (geometry(row) is not None or row.get('FormalEntryTrigger') is not False):
            raise ValueError('Q017_GEOMETRY_AUTHORITY_VIOLATION')

    out = core.build(base, live, context, trade_date=trade_date, max_age_seconds=max_age_seconds, now=now)
    base_rows = base.get("rows", []) if isinstance(base, dict) else []
    evidence = {_ticker(r): r for r in base_rows if isinstance(r, dict) and _ticker(r)}
    live_map = {
        _ticker(r): r
        for r in live.get("data", [])
        if isinstance(live, dict) and isinstance(r, dict) and _ticker(r)
    }
    effective_trade_date = _effective_trade_date(base, live, trade_date)
    binding_ok = out.get("binding_status") == "PASS"

    for row in out.get("rows", []):
        src = evidence.get(_ticker(row), {})
        row["SourceProvenance"] = src.get("SourceProvenance", "LEGACY")
        row["LegacyScore"] = src.get("LegacyScore")
        row["Q017Score"] = src.get("Q017Score")
        row["Q017Rank"] = src.get("Q017Rank")
        row["Q017Beta60"] = src.get("Q017Beta60")
        row["Q017Residual1"] = src.get("Q017Residual1")
        row["FormalCandidate"] = bool(src.get("FormalCandidate", True))
        row["GeometryStatus"] = "AVAILABLE" if geometry(src) is not None and src.get("SourceProvenance") != "Q017" else "UNAVAILABLE"
        row["LegacyEvidence"] = src.get("LegacyEvidence")
        row["Q017Evidence"] = src.get("Q017Evidence")

        # Entry geometry remains fail-closed.  The Q017 structural overlay below
        # is exit-only and may never create or upgrade an entry.
        if (row["GeometryStatus"] != "AVAILABLE" or not row["FormalCandidate"]) and row["FinalAction"] != "EXIT_ALL":
            row.update(FinalAction="ABSTAIN", ExecutionEligibility="ABSTAIN_GEOMETRY_UNAVAILABLE")

        event = q017_structure_exit.classify(
            src,
            live_map.get(_ticker(row), {}),
            effective_trade_date,
        )
        q017_structure_exit.apply(row, event, binding_ok)

    out["schema_version"] = max(2, int(out.get("schema_version") or 0))
    out["system"] = "HENGCE"
    out["module"] = "HENGCE_UNIFIED_INTRADAY_ACTION_BOARD"
    out["candidate_union_policy"] = base.get("candidate_union_policy") if isinstance(base, dict) else None
    out["score_fusion"] = False
    out["q017_contract_status"] = base.get("q017_contract_status") if isinstance(base, dict) else None
    out["source_provenance_counts"] = base.get("source_provenance_counts") if isinstance(base, dict) else None
    out.update(ZERO_AUTHORITY)
    out["q017_structural_exit_overlay"] = {
        "version": "Q017_FAILED_RECLAIM_V1",
        "scope": "ALREADY_HELD_Q017_OR_BOTH_ONLY",
        "first_break": "STRUCTURE_WARNING_ALERT_ONLY",
        "exit_states": ["STRUCTURE_EXIT_REBREAK", "STRUCTURE_EXIT_FAILED_RECLAIM"],
        "pivot": "STRICT_ONE_BAR_CONFIRMED_CAUSAL",
        "thresholds": "NONE",
        "frozen_q017_signal_contract_changed": False,
        "fixed_20_sessions_research_benchmark_changed": False,
    }
    out["base_hash"] = digest(base)
    out["input_hashes"] = {"context": digest(context), "live": digest(live)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base")
    ap.add_argument("--live")
    ap.add_argument("--context")
    ap.add_argument("--output")
    ap.add_argument("--trade-date")
    ap.add_argument("--max-age-seconds", type=int, default=480)
    args = ap.parse_args()
    for name in ["base", "live", "context", "output"]:
        if not getattr(args, name):
            ap.error(f"--{name.replace('_','-')} is required")
    base = strict_loads(Path(args.base).read_text(encoding="utf-8"))
    live = strict_loads(Path(args.live).read_text(encoding="utf-8"))
    context = strict_loads(Path(args.context).read_text(encoding="utf-8"))
    out = build(base, live, context, trade_date=args.trade_date, max_age_seconds=args.max_age_seconds)
    path = Path(args.output)
    atomic(path, out)
    print(json.dumps({"binding_status": out.get("binding_status"), "rows": len(out.get("rows", [])), "output": str(path)}, ensure_ascii=False))
    return 0 if out.get("binding_status") == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
