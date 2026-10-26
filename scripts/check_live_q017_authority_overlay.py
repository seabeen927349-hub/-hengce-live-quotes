#!/usr/bin/env python3
"""Backward-compatible HENGCE Q017 authority/coherence checker.

This filename is retained only so old handoff packages and operator commands do
not revive the retired V7 authority-id checker.  This file creates NO trading,
ranking, or capital authority.  It validates the current schema-v5 Q017 lane,
current dual-engine separation, and E2 zero-capital paper state against the
canonical v5 guard and durable infrastructure receipt.
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_layout() -> tuple[Path, Path, Path]:
    root = Path(__file__).resolve().parents[1]
    candidates = [root, root / "LIVE_OPERATIONAL_OVERLAY_20261019"]
    for base in candidates:
        if (base / "hengce/q017_radar/latest.json").is_file() and (base / "scripts/hengce_q017_authority_guard_v5.py").is_file():
            return root, base, base / "scripts"
    raise AssertionError("CURRENT_SCHEMA5_LAYOUT_NOT_FOUND")


def main() -> int:
    root, base, scripts = resolve_layout()

    # Canonical Q017 authority semantics come from the current v5 guard.  Do not
    # copy an authority id into this compatibility checker.
    sys.path.insert(0, str(scripts))
    guard = importlib.import_module("hengce_q017_authority_guard_v5")

    infra = load(base / "hengce/q017_radar/selfverify/infrastructure_latest.json")
    assert infra.get("module") == "Q017_INFRASTRUCTURE_SELFVERIFY"
    assert infra.get("status") == "PASS"
    c = infra.get("contracts") or {}
    assert int(c.get("q017_schema") or 0) == 5
    assert c.get("observation_window") == "09:01:00-09:01:59.999999 Asia/Taipei"
    assert float(c.get("provider_quote_row_coverage_required")) == 1.0
    assert c.get("universe") == "TWSE_LISTED_ELECTRONICS_ONLY"
    assert c.get("late_market_backfill_forbidden") is True
    assert int(c.get("normal_0901_macro_network_calls")) == 0
    assert c.get("primary_start_taipei") == "07:45"
    assert c.get("backup_start_taipei") == "08:15"
    assert float(c.get("mis_connect_timeout_seconds")) == 2.5
    assert float(c.get("mis_read_timeout_seconds")) == 6.0
    tests = infra.get("tests") or {}
    assert set(tests) >= {f"{i:02d}_{name}" for i, name in [
        (1,"observation"),(2,"backup"),(3,"macro_cache"),(4,"snapshot"),
        (5,"supervisor_v1"),(6,"supervisor_v2"),(7,"recovery"),
        (8,"authority"),(9,"resilience")
    ]}
    assert all((tests[k] or {}).get("status") == "PASS" for k in tests if k[:2].isdigit())

    q017 = load(base / "hengce/q017_radar/latest.json")
    ok, reason = guard.validate(q017)
    assert ok, f"Q017_V5_GUARD_REJECTED:{reason}"
    assert int(q017.get("schema_version") or 0) >= 5
    if q017.get("authority") == "NO_FORMAL_SIGNAL":
        assert int(q017.get("formal_buy_count") or 0) == 0
        assert q017.get("top3") in (None, [])

    dual = load(base / "hengce/dual_engine/latest.json")
    assert dual.get("architecture") == "DUAL_ENGINE"
    assert dual.get("rankings_separate") is True
    assert dual.get("mixed_ranking_forbidden") is True
    assert dual.get("legacy_v3_display_authority") is False
    dq = dual.get("q017") or {}
    de = dual.get("e2") or {}
    assert int(dq.get("schema_version") or 0) >= 5
    if q017.get("authority") == "NO_FORMAL_SIGNAL":
        assert dq.get("formal_authority") is False
        assert int(dq.get("formal_buy_count") or 0) == 0
        assert dq.get("top3") in (None, [])

    e2 = load(base / "hengce/e2_live/state_latest.json")
    assert int(e2.get("schema_version") or 0) == 2
    assert e2.get("module") == "E2_PROFIT_MAX_STATE"
    assert e2.get("binding_status") == "PASS"
    assert e2.get("authority") == "VALIDATED_RESEARCH_SIGNAL_DISPLAY"
    assert int(e2.get("capital_authority_twd") or 0) == 0
    assert e2.get("broker_order_execution") is False
    assert e2.get("q017_effect") == "NONE"
    assert de.get("authority") == "RETIRED_RESEARCH_ARTIFACT_ONLY"
    assert de.get("historical_source_authority") == e2.get("authority")
    assert de.get("formal_authority") is False
    assert de.get("research_only") is True
    assert de.get("status") == e2.get("engine_status")
    assert int(de.get("capital_authority_twd") or 0) == 0
    assert de.get("broker_order_execution") is False

    result = {
        "status": "PASS",
        "checker": "Q017_SCHEMA5_CURRENT_AUTHORITY_COMPATIBILITY",
        "compatibility_only": True,
        "authority_created": False,
        "v7_authority_id_dependency": False,
        "q017_guard_reason": reason,
        "q017_schema": q017.get("schema_version"),
        "q017_authority": q017.get("authority"),
        "q017_formal_buy_count": int(q017.get("formal_buy_count") or 0),
        "dual_engine": "PASS",
        "e2_state": e2.get("engine_status"),
        "capital_authority_twd": 0,
        "broker_order_execution": False,
        "layout": "package_overlay" if base != root else "repository",
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    print("PASS Q017_SCHEMA5_CURRENT_AUTHORITY_COMPATIBILITY_NO_V7_DEPENDENCY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
