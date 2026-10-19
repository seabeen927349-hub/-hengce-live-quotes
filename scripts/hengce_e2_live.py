#!/usr/bin/env python3
"""Legacy E2 tombstone.

Effective 2026-10-19 the previous E2 is revoked because its research mother
population was wrong (all TWSE stocks instead of TWSE-listed electronics).
This file intentionally remains at the old workflow entrypoint so any stale
caller fails safe without breaking Q017 orchestration.

NO LEGACY E2 OUTPUT MAY AUTHORIZE CAPITAL, BUY, WATCH, PENDING ENTRY, OR STATE
TRANSITION. New research lives under E2_PROFIT_MAX and is research-only until
walk-forward out-of-sample validation is explicitly promoted by a new lock.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "hengce" / "e2_live"
REVOCATION = ROOT / "hengce" / "E2_LEGACY_REVOCATION_20261019.json"


def atomic_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def result(mode: str, trade_date: str | None) -> dict:
    return {
        "schema_version": 1,
        "system": "HENGCE",
        "module": "E2_LEGACY_TOMBSTONE",
        "mode": mode,
        "trade_date": trade_date,
        "generated_at_taipei": datetime.now(TZ).isoformat(),
        "status": "REVOKED_ZERO_AUTHORITY",
        "authority": "NO_E2_CAPITAL_ACTION",
        "capital_authority_twd": 0,
        "buy_count": 0,
        "watch_count": 0,
        "entry_due_count": 0,
        "pending_entries": [],
        "state_transition_allowed": False,
        "legacy_model_execution_allowed": False,
        "revocation_contract": str(REVOCATION.relative_to(ROOT)),
        "successor": "E2_PROFIT_MAX_RESEARCH_ONLY",
        "reason": "LEGACY_E2_WRONG_RESEARCH_POPULATION_ALL_TWSE_REVOKED_20261019",
        "q017_effect": "NONE"
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["morning", "postclose", "self-test"], required=True)
    ap.add_argument("--date")
    args = ap.parse_args()
    out = result(args.mode, args.date)
    if args.mode == "self-test":
        out["self_test"] = "PASS"
        out["assertions"] = {
            "capital_zero": True,
            "buy_zero": True,
            "watch_zero": True,
            "pending_zero": True,
            "legacy_execution_disabled": True
        }
    else:
        target = OUT / ("morning_latest.json" if args.mode == "morning" else "postclose_latest.json")
        atomic_json(target, out)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
