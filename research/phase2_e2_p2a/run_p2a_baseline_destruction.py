#!/usr/bin/env python3
"""HENGCE E2 Phase-2 P2-A diagnostics with fail-closed evidence boundaries."""
from __future__ import annotations

import base64
import gzip
import importlib.util
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "research/phase2_e2_p2a/p2a_result.json"

from research.phase2_governance import governance as gov

POLICY = gov.metadata(ROOT / "research/phase2_governance/phase2-policy.json")
STAGE = "P2A_BASELINE_DESTRUCTION"
FINAL = ROOT / "research/e2_profit_max/E2_PROFIT_MAX_CANDIDATE_B_FINAL_VALIDATION_20261019.json"
R2 = ROOT / "research/e2_profit_max/round2/run_round2_finite.py"


def permit(op: str, cost_multiplier=None):
    return gov.require_phase2_run(POLICY, engine="E2", stage=STAGE,
                                  operation=op, cost_multiplier=cost_multiplier)


def load_r2_module():
    spec = importlib.util.spec_from_file_location("hengce_round2", R2)
    if spec is None or spec.loader is None:
        raise RuntimeError("ROUND2_MODULE_LOAD_FAILED")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def probe_event_payloads():
    """Probe preserved event-level payloads without repairing or regenerating them."""
    r2 = load_r2_module()
    evidence = {}
    try:
        rows = r2.load_payload()
        evidence["shock_payload"] = {"status": "VALID", "rows": len(rows)}
    except Exception as exc:
        evidence["shock_payload"] = {"status": "INVALID_FAIL_CLOSED", "error": f"{type(exc).__name__}:{exc}"}

    mother_dir = ROOT / "research/e2_profit_max/round2/input"
    try:
        chunks = sorted(mother_dir.glob("r2seg_*.txt"))
        if len(chunks) != 8:
            raise RuntimeError(f"ROUND2_MOTHER_CHUNK_COUNT:{len(chunks)}")
        text = "".join(p.read_text(encoding="utf-8").strip() for p in chunks)
        raw = gzip.decompress(base64.b64decode(text, validate=True))
        obj = json.loads(raw)
        evidence["mother_payload"] = {"status": "VALID", "rows": len(obj.get("r", []))}
    except Exception as exc:
        evidence["mother_payload"] = {"status": "INVALID_FAIL_CLOSED", "error": f"{type(exc).__name__}:{exc}"}
    return evidence


def main():
    permit("BASELINE_REPLAY")
    permit("LEAVE_ONE_YEAR_OUT")
    for mult in (1.0, 1.5, 2.0):
        permit("COST_STRESS", mult)
    permit("LEAVE_BEST_TRADES_OUT")
    permit("REGIME_CHARACTERIZATION")
    permit("PARAMETER_PERTURBATION_ROBUSTNESS")

    frozen = json.loads(FINAL.read_text(encoding="utf-8"))
    pit = frozen["pit_2023_2025"]
    years = pit["years"]
    navs = {y: float(years[y]["nav"]) for y in ("2023", "2024", "2025")}
    product = math.prod(navs.values())
    if not math.isclose(product, float(pit["nav"]), rel_tol=0, abs_tol=1e-12):
        raise RuntimeError("ANNUAL_NAVS_DO_NOT_REPRODUCE_FROZEN_TOTAL")

    leave_year = {}
    for removed in ("2023", "2024", "2025"):
        nav = math.prod(v for y, v in navs.items() if y != removed)
        leave_year[removed] = {"remaining_nav": nav, "remaining_return": nav - 1.0}

    payload = probe_event_payloads()
    event_level_valid = all(x["status"] == "VALID" for x in payload.values())

    if event_level_valid:
        # Current repository is not expected to enter this branch. Even if both
        # archives become readable later, exact trade-level diagnostics require a
        # separately reviewed runner update rather than silently changing evidence.
        trade_level = {
            "status": "STOP_REVIEW_REQUIRED_NEWLY_READABLE_EVENT_PAYLOAD",
            "reason": "PRESERVED_PAYLOAD_STATE_CHANGED; DO_NOT SILENTLY EXPAND THIS RESULT",
        }
        status = "STOP_REVIEW_REQUIRED"
    else:
        trade_level = {
            "cost_stress": "BLOCKED_NO_VALID_EVENT_LEVEL_RETURN_PAYLOAD",
            "leave_best_trades_out": "BLOCKED_NO_VALID_EVENT_LEVEL_RETURN_PAYLOAD",
            "trade_level_regime_characterization": "BLOCKED_NO_VALID_EVENT_LEVEL_RETURN_PAYLOAD",
            "parameter_perturbation": "BLOCKED_PRESELECTION_CROSS_SECTION_NOT_PRESERVED_AND_HISTORICAL_SIGNAL_REGENERATION_FORBIDDEN",
        }
        status = "PARTIAL_RESULT_FAIL_CLOSED_ON_MISSING_EVENT_LEVEL_EVIDENCE"

    result = {
        "schema_version": 1,
        "system": "HENGCE",
        "engine": "E2_PROFIT_MAX",
        "phase": "P2A_BASELINE_DESTRUCTION",
        "authorization_id": gov.AUTHORIZATION_ID,
        "status": status,
        "evidence_class": "DIAGNOSTIC_COMPUTATION_EVIDENCE_NOT_CANDIDATE_ACCEPTANCE",
        "baseline_2023_2025": {
            "nav": float(pit["nav"]),
            "return": float(pit["return"]),
            "trades": int(pit["entries"]),
            "wins": int(pit["wins"]),
            "max_drawdown": float(pit["maxdd"]),
            "annual_nav_product": product,
            "annual_nav_product_matches_frozen_total": True,
        },
        "leave_one_year_out": leave_year,
        "year_characterization": years,
        "event_level_payload_probe": payload,
        "trade_level_diagnostics": trade_level,
        "interpretation": "All leave-one-year-out combinations remain positive; robustness is uneven across years. Exact cost/best-trade/regime trade-level tests are not claimed because preserved event-level evidence is unreadable.",
        "candidate_creation_authorized": False,
        "candidate_acceptance_authorized": False,
        "prospective_holdout_access": False,
        "capital_authority_twd": 0,
        "broker_order_execution": False,
        "PROMOTE_TO_PRODUCTION": "FORBIDDEN",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
