#!/usr/bin/env python3
"""Thin HENGCE action-board wrapper that preserves unified candidate evidence."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import hengce_intraday_action_board as core


def _ticker(row):
    return str(row.get("Ticker") or row.get("ticker") or row.get("symbol") or "").strip()


def build(base, live, context, trade_date=None, max_age_seconds=480, now=None):
    out = core.build(base, live, context, trade_date=trade_date, max_age_seconds=max_age_seconds, now=now)
    base_rows = base.get("rows", []) if isinstance(base, dict) else []
    evidence = {_ticker(r): r for r in base_rows if isinstance(r, dict) and _ticker(r)}
    for row in out.get("rows", []):
        src = evidence.get(_ticker(row), {})
        row["SourceProvenance"] = src.get("SourceProvenance", "LEGACY")
        row["LegacyScore"] = src.get("LegacyScore")
        row["Q017Score"] = src.get("Q017Score")
        row["Q017Rank"] = src.get("Q017Rank")
        row["Q017Beta60"] = src.get("Q017Beta60")
        row["Q017Residual1"] = src.get("Q017Residual1")
        row["FormalCandidate"] = bool(src.get("FormalCandidate", True))
        row["GeometryStatus"] = src.get("GeometryStatus", "UNKNOWN")
    out["schema_version"] = max(2, int(out.get("schema_version") or 0))
    out["system"] = "HENGCE"
    out["module"] = "HENGCE_UNIFIED_INTRADAY_ACTION_BOARD"
    out["candidate_union_policy"] = base.get("candidate_union_policy") if isinstance(base, dict) else None
    out["score_fusion"] = False
    out["q017_contract_status"] = base.get("q017_contract_status") if isinstance(base, dict) else None
    out["source_provenance_counts"] = base.get("source_provenance_counts") if isinstance(base, dict) else None
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
    base = json.loads(Path(args.base).read_text(encoding="utf-8"))
    live = json.loads(Path(args.live).read_text(encoding="utf-8"))
    context = json.loads(Path(args.context).read_text(encoding="utf-8"))
    out = build(base, live, context, trade_date=args.trade_date, max_age_seconds=args.max_age_seconds)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"binding_status": out.get("binding_status"), "rows": len(out.get("rows", [])), "output": str(path)}, ensure_ascii=False))
    return 0 if out.get("binding_status") == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
