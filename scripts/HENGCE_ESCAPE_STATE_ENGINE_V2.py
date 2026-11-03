#!/usr/bin/env python3
"""HENGCE v2.4.7 escape state engine.
Consumes a precomputed PIT-safe feature packet. It deliberately does not infer institutional independence from TotalNet.
No trading authority.
"""
import json, sys
from pathlib import Path

LEVELS = {
    0: "L0_NORMAL",
    1: "L1_VULNERABLE",
    2: "L2_FIRST_SHOT",
    3: "L3_SECOND_SHOT_PROPAGATION",
    4: "L4_REGIME_CONFIRMATION",
    5: "L5_ABSOLUTE_WITHDRAWAL",
    6: "L6_PRICE_DAMAGE",
}
PRIMITIVE = ("foreign", "trust", "dealer")
REQUIRED_FAMILIES = ("FLOW_PROPAGATION", "FLOW_BREADTH", "PRICE_DAMAGE")


def _bool(d, key, default=False):
    return bool(d.get(key, default))


def _num(d, key):
    v = d.get(key)
    return float(v) if isinstance(v, (int, float)) else None


def _fail(reason, p=None):
    return {
        "status": "UNVERIFIED",
        "escape_level": None,
        "escape_state": "UNVERIFIED",
        "regime_type": "UNRESOLVED",
        "escape_pressure": None,
        "escape_velocity_5d": None,
        "fail_closed_reasons": reason if isinstance(reason, list) else [reason],
        "trading_authority": "NONE",
        "asof_taipei": (p or {}).get("asof_taipei"),
    }


def evaluate(p):
    gate = p.get("data_gate", {})
    required_gate = ("freshness_pass", "integrity_pass", "pit_pass", "universe_pass")
    gate_fail = [f"GATE_FAIL:{k}" for k in required_gate if not gate.get(k, False)]
    if gate_fail:
        return _fail(gate_fail, p)

    phase = p.get("phase")
    if phase not in {"INTRADAY", "CLOSE_PRELIM", "EOD_FORMAL", "OWNERSHIP_WEEKLY", "NEXT_DAY_RECONCILIATION"}:
        return _fail("INVALID_PHASE", p)

    # Intraday may warn on price/liquidity only; it may never create a formal flow state.
    formal_flow_allowed = phase in {"EOD_FORMAL", "OWNERSHIP_WEEKLY", "NEXT_DAY_RECONCILIATION"}

    det = p.get("detector_output", {})
    if det.get("status") != "PASS_DETECTOR" or det.get("detector_version") != "HENGCE_ESCAPE_FEATURE_DETECTOR_V1":
        return _fail("DETECTOR_NOT_VERIFIED", p)
    if det.get("metric_contract_version") != "HENGCE_ESCAPE_METRIC_CONTRACT_V1" or det.get("metric_contract_sha256") != "1d93c171b0b06d49eef19e0bf63e3b086fc366052d6bbc45516928c672f47281":
        return _fail("METRIC_CONTRACT_NOT_VERIFIED", p)
    fam = det.get("family_scores", {})
    valid_scores = {k: float(v) for k, v in fam.items() if isinstance(v, (int, float)) and 0 <= float(v) <= 100}
    if not all(k in valid_scores for k in REQUIRED_FAMILIES):
        return _fail([f"MISSING_REQUIRED_FAMILY:{k}" for k in REQUIRED_FAMILIES if k not in valid_scores], p)
    if len(valid_scores) < 6:
        return _fail(f"INSUFFICIENT_VALID_FAMILIES:{len(valid_scores)}", p)
    escape_pressure = sum(valid_scores.values()) / len(valid_scores)

    ev = det.get("events", {})
    vulnerability_count = sum(bool(ev.get(k, False)) for k in (
        "vulnerability_crowding_confirmed", "vulnerability_leverage_confirmed",
        "internal_structure_confirmed", "price_flow_divergence_confirmed"))
    vulnerable = vulnerability_count >= 2

    primitive_confirmed = {c: _bool(ev, f"{c}_negative_flow_confirmed") for c in PRIMITIVE}
    n_primitive = sum(primitive_confirmed.values())
    first = formal_flow_allowed and n_primitive >= 1

    aggregate = formal_flow_allowed and _bool(ev, "totalnet_negative_flow_confirmed")
    flow_breadth = formal_flow_allowed and _bool(ev, "flow_breadth_confirmed")
    migration = formal_flow_allowed and _bool(ev, "capital_migration_confirmed")
    # TotalNet is not independent: either a second primitive channel confirms, or aggregate needs two independent non-channel families.
    second = first and (n_primitive >= 2 or (aggregate and flow_breadth and migration))

    medium = formal_flow_allowed and _bool(ev, "medium_window_flow_confirmed")
    no_reentry = not _bool(ev, "flow_reentry_confirmed")
    regime = second and medium and flow_breadth and no_reentry

    source_abs = formal_flow_allowed and _bool(ev, "source_absolute_withdrawal_confirmed")
    broad_abs = formal_flow_allowed and _bool(ev, "broad_market_absolute_withdrawal_confirmed")
    destination = formal_flow_allowed and _bool(ev, "destination_absorption_confirmed")
    absolute = regime and (source_abs or broad_abs)

    price_damage = _bool(ev, "broad_price_damage_confirmed")
    damage = absolute and price_damage

    internal_rotation = absolute and source_abs and destination and not broad_abs
    broad_riskoff = absolute and broad_abs and not destination
    mixed = absolute and broad_abs and destination
    regime_type = "MIXED" if mixed else "BROAD_RISK_OFF" if broad_riskoff else "INTERNAL_ROTATION" if internal_rotation else "UNRESOLVED"

    if damage:
        level = 6
    elif absolute:
        level = 5
    elif regime:
        level = 4
    elif second:
        level = 3
    elif first:
        level = 2
    elif vulnerable:
        level = 1
    else:
        level = 0

    rebound_without_reentry = bool(p.get("prior_level", 0) >= 3 and _bool(ev, "price_recovery_confirmed") and not _bool(ev, "flow_reentry_confirmed"))
    recovery_confirmed = _bool(ev, "recovery_5_consecutive_confirmed") and _bool(ev, "flow_reentry_confirmed")
    prior = p.get("prior_level")
    if isinstance(prior, int) and prior > level and not recovery_confirmed:
        # Hysteresis: do not silently de-escalate on a single cleaner print.
        level = prior

    prev_pressure = _num(p, "escape_pressure_5d_ago")
    velocity = None if prev_pressure is None else escape_pressure - prev_pressure
    prev_velocity = _num(p, "escape_velocity_5d_ago")
    acceleration = None if velocity is None or prev_velocity is None else velocity - prev_velocity

    return {
        "status": "PASS_ADVISORY_ONLY",
        "phase": phase,
        "asof_taipei": p.get("asof_taipei"),
        "trade_date": p.get("trade_date"),
        "escape_level": level,
        "escape_state": LEVELS[level],
        "regime_type": regime_type,
        "escape_pressure": round(escape_pressure, 4),
        "escape_velocity_5d": None if velocity is None else round(velocity, 4),
        "escape_acceleration_5d": None if acceleration is None else round(acceleration, 4),
        "primitive_channels_confirmed": [c for c, v in primitive_confirmed.items() if v],
        "primitive_channel_count": n_primitive,
        "totalnet_is_independent_channel": False,
        "first_shot": first,
        "second_shot": second,
        "regime_confirmation": regime,
        "absolute_withdrawal": absolute,
        "broad_price_damage": damage,
        "rebound_without_reentry": rebound_without_reentry,
        "recovery_confirmed": recovery_confirmed,
        "deescalation_hysteresis_applied": isinstance(prior, int) and prior > level and not recovery_confirmed,
        "formal_flow_state_allowed": formal_flow_allowed,
        "trading_authority": "NONE",
        "notes": [
            "PRECONDITION is not an exit signal.",
            "TotalNet is aggregate corroboration, never an independent second institutional channel.",
            "Institutional net flow is not automatically equivalent to AUM allocation change.",
            "State is primary; Escape Pressure is secondary diagnostic only.",
            "Event booleans are accepted only from HENGCE_ESCAPE_FEATURE_DETECTOR_V1, not manual input.",
            "Detector metrics must match HENGCE_ESCAPE_METRIC_CONTRACT_V1 hash 1d93c171b0b06d49eef19e0bf63e3b086fc366052d6bbc45516928c672f47281."
        ]
    }


def main():
    if len(sys.argv) != 2:
        print(json.dumps({"status":"USAGE","usage":"HENGCE_ESCAPE_STATE_ENGINE_V2.py INPUT.json"}, ensure_ascii=False))
        return 2
    p = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(json.dumps(evaluate(p), ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
