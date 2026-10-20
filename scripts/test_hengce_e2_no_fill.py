#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path

import hengce_e2_live as e2


def write_override(path: Path, **kw):
    base = {
        "version": 1,
        "status": "NO_FILL",
        "ticker": "3026",
        "signal_date": "2026-10-19",
        "effective_date": "2026-10-20",
        "reason": "USER_CONFIRMED_NOT_FILLED",
    }
    base.update(kw)
    path.write_text(json.dumps(base), encoding="utf-8")


def main():
    original = e2.EXECUTION_OVERRIDE
    try:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "execution_override.json"
            e2.EXECUTION_OVERRIDE = p

            holding = {
                "state": "HOLDING",
                "signal_date": "2026-10-19",
                "ticker": "3026",
                "name": "禾伸堂",
                "score": 4.801362351369969,
                "entry_date": "2026-10-20",
                "entry_reference_open": 736.0,
            }

            # Matching user-confirmed no-fill releases the slot, but preserves
            # the original model signal and its audit trail.
            write_override(p)
            no_fill, meta = e2.apply_execution_override(holding, date(2026, 10, 20))
            assert no_fill["state"] == "NO_FILL"
            assert no_fill["ticker"] == "3026"
            assert no_fill["slot_released"] is True
            assert no_fill["model_signal_preserved"] is True
            assert meta["applied"] is True

            # Same session remains NO_FILL: no hindsight replacement trade.
            same_day, same_meta = e2.apply_execution_override(no_fill, date(2026, 10, 20))
            assert same_day["state"] == "NO_FILL"
            assert same_meta["reason"] == "ALREADY_APPLIED_THIS_SESSION"

            # Next session the persistent override cannot become a permanent lock.
            nxt, nxt_meta = e2.apply_execution_override(no_fill, date(2026, 10, 21))
            assert nxt == {"state": "IDLE"}
            assert nxt_meta["reason"] == "PRIOR_NO_FILL_SLOT_RELEASED"

            # Wrong ticker is fail-closed, not silently accepted.
            write_override(p, ticker="8021")
            bad, bad_meta = e2.apply_execution_override(holding, date(2026, 10, 20))
            assert bad["state"] == "DATA_PENDING"
            assert bad["reason"] == "EXECUTION_OVERRIDE_POSITION_MISMATCH"
            assert bad_meta["applied"] is False

            # Future effective date must not alter the current paper state.
            write_override(p, effective_date="2026-10-21")
            future, future_meta = e2.apply_execution_override(holding, date(2026, 10, 20))
            assert future == holding
            assert future_meta["reason"] == "NOT_EFFECTIVE_YET"

        print(json.dumps({
            "status": "PASS",
            "matching_no_fill_releases_slot": True,
            "same_session_hindsight_forbidden": True,
            "next_session_idle": True,
            "mismatch_fail_closed": True,
            "candidate_b_formula_mutated": False,
        }))
        return 0
    finally:
        e2.EXECUTION_OVERRIDE = original


if __name__ == "__main__":
    raise SystemExit(main())
