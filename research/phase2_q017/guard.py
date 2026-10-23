from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from research.phase2_governance import governance as gov

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "research/phase2_governance/phase2-policy.json"
FAMILY_PATH = ROOT / "research/phase2_q017/family-v1.json"
EXPECTED_FAMILY_SHA256 = "1a177925e46233afc1962b9a3286c9e14e62d57830c5aa927a54352e6be9769a"
ACTIVATION_DATE = date(2026, 10, 23)


class Q017Blocked(ValueError):
    pass


def need(ok: bool, reason: str) -> None:
    if not ok:
        raise Q017Blocked(reason)


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def load_and_validate_policy():
    policy = gov.metadata(POLICY_PATH)
    gov.validate_policy(policy)
    need(policy.get("engine_scope", {}).get("Q017") == "PROSPECTIVE_CHARACTERIZATION_ONLY", "Q017_SCOPE_NOT_PROSPECTIVE_CHARACTERIZATION")
    need(policy.get("candidate_acceptance_authorized") is False, "Q017_CANDIDATE_ACCEPTANCE_FORBIDDEN")
    need(policy.get("automated_search_authorized") is False, "Q017_AUTOMATED_SEARCH_FORBIDDEN")
    need(policy.get("historical_signal_regeneration_authorized") is False, "Q017_HISTORICAL_REGEN_FORBIDDEN")
    need(policy.get("holdout_access_authorized") is False, "Q017_HOLDOUT_ACCESS_FORBIDDEN")
    need(policy.get("capital_authority_twd") == 0, "Q017_CAPITAL_FORBIDDEN")
    need(policy.get("broker_order_execution") is False, "Q017_BROKER_FORBIDDEN")
    need(policy.get("PROMOTE_TO_PRODUCTION") == "FORBIDDEN", "Q017_PRODUCTION_FORBIDDEN")
    return policy


def load_and_validate_family():
    family = json.loads(FAMILY_PATH.read_text(encoding="utf-8"))
    digest = hashlib.sha256(canonical(family)).hexdigest()
    need(digest == EXPECTED_FAMILY_SHA256, "Q017_FAMILY_CHANGED_AFTER_PREREGISTRATION")
    need(family.get("program") == "HENGCE_Q017_PHASE2_PROSPECTIVE_V1", "Q017_PROGRAM_INVALID")
    rules = family.get("rules") or {}
    required_false = (
        "historical_backfill",
        "historical_signal_regeneration",
        "prospective_candidate_selection",
        "automated_optimizer",
        "grid_search",
        "random_search",
        "bayesian_search",
        "unrestricted_feature_mining",
    )
    need(rules.get("same_immutable_0901_observation_only") is True, "Q017_SAME_LOCK_REQUIRED")
    need(rules.get("past_locks_smoke_only") is True, "Q017_PAST_LOCKS_MUST_BE_SMOKE_ONLY")
    need(all(rules.get(k) is False for k in required_false), "Q017_FAMILY_EXCEEDS_CHARACTERIZATION_SCOPE")
    need(rules.get("max_challenger_variants") == 6 and len(family.get("challengers") or []) == 6, "Q017_CHALLENGER_BUDGET_DRIFT")
    need(rules.get("capital_authority_twd") == 0 and rules.get("broker_order_execution") is False and rules.get("PROMOTE_TO_PRODUCTION") == "FORBIDDEN", "Q017_FAMILY_AUTHORITY_FORBIDDEN")
    champ = family.get("champion") or {}
    need(champ == {"id":"CHAMPION_K25_R004","k":25,"residual_max":0.04,"top_n":3,"score":"beta*(1+k*max(-residual,0))"}, "Q017_CHAMPION_DRIFT")
    ids = [champ["id"]] + [x.get("id") for x in family["challengers"]]
    need(len(ids) == len(set(ids)), "Q017_DUPLICATE_VARIANT_ID")
    return family, digest


def authorize_observation(trade_date: str, mode: str):
    load_and_validate_policy()
    family, digest = load_and_validate_family()
    try:
        d = date.fromisoformat(trade_date)
    except Exception as exc:
        raise Q017Blocked("Q017_TRADE_DATE_INVALID") from exc
    need(mode in {"smoke", "prospective"}, "Q017_MODE_INVALID")
    if mode == "prospective":
        need(d >= ACTIVATION_DATE, "Q017_PREACTIVATION_LOCK_NOT_RESEARCH_EVIDENCE")
        evidence_class = "PROSPECTIVE_CHARACTERIZATION_EVIDENCE"
    else:
        need(d < ACTIVATION_DATE, "Q017_SMOKE_MODE_ONLY_FOR_PREACTIVATION_LOCKS")
        evidence_class = "SMOKE_ONLY_NOT_RESEARCH_EVIDENCE"
    return {
        "status": "Q017_PROSPECTIVE_CHARACTERIZATION_ALLOWED",
        "mode": mode,
        "evidence_class": evidence_class,
        "family_sha256": digest,
        "activation_date": ACTIVATION_DATE.isoformat(),
        "candidate_acceptance_authorized": False,
        "holdout_access_authorized": False,
        "capital_authority_twd": 0,
        "broker_order_execution": False,
        "PROMOTE_TO_PRODUCTION": "FORBIDDEN",
    }, family
