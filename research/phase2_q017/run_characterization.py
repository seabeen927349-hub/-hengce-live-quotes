#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
for p in (str(ROOT), str(SCRIPTS)):
    if p not in sys.path:
        sys.path.insert(0, p)

from research.phase2_q017.guard import authorize_observation
import hengce_q017_observation_lock_v5 as prod


def csha(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def f(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def rank_variant(obs, spec, market_go):
    sox1 = f((obs.get("market_inputs") or {}).get("sox", {}).get("sox_1d"))
    if sox1 is None:
        raise RuntimeError("Q017_SOX1_MISSING")
    models = {str(x["ticker"]): x for x in obs["eligible_models"]}
    quotes = obs["quotes"]
    rows = []
    for ticker, model in models.items():
        q = quotes[ticker]
        op = f(q.get("open"))
        pc = f(q.get("reference_close")) or f(model.get("previous_close"))
        beta = f(model.get("beta"))
        if op is None or pc in (None, 0) or beta is None:
            continue
        gap = op / pc - 1.0
        expected_gap = beta * sox1
        residual = gap - expected_gap
        if residual > float(spec["residual_max"]):
            continue
        score = beta * (1.0 + float(spec["k"]) * max(-residual, 0.0))
        rows.append({
            "ticker": ticker,
            "name": q.get("name") or model.get("name", ""),
            "beta": beta,
            "open": op,
            "previous_close": pc,
            "gap": gap,
            "expected_gap": expected_gap,
            "residual": residual,
            "score": score,
            "qualified": bool(market_go),
        })
    rows.sort(key=lambda x: (-x["score"], x["ticker"]))
    top = rows[: int(spec["top_n"])]
    return {"admitted_count": len(rows), "top3": top}


def overlap_metrics(champion, challenger):
    a = [x["ticker"] for x in champion["top3"]]
    b = [x["ticker"] for x in challenger["top3"]]
    sa, sb = set(a), set(b)
    union = sa | sb
    return {
        "top1_same": bool(a and b and a[0] == b[0]),
        "top3_overlap_count": len(sa & sb),
        "top3_jaccard": len(sa & sb) / len(union) if union else 1.0,
        "ranked_tickers": b,
        "entered_vs_champion": [x for x in b if x not in sa],
        "dropped_vs_champion": [x for x in a if x not in sb],
    }


def exact_champion_check(obs, ours):
    official = prod.build_decision_from_observation(obs)
    expected = official.get("top3") or []
    got = ours.get("top3") or []
    if [x.get("ticker") for x in expected] != [x.get("ticker") for x in got]:
        raise RuntimeError("Q017_CHAMPION_TOP3_REPRODUCTION_MISMATCH")
    if len(expected) != len(got):
        raise RuntimeError("Q017_CHAMPION_LENGTH_MISMATCH")
    for a, b in zip(expected, got):
        for key in ("score", "residual", "gap", "expected_gap", "beta"):
            av, bv = f(a.get(key)), f(b.get(key))
            if av is None or bv is None or not math.isclose(av, bv, rel_tol=1e-12, abs_tol=1e-12):
                raise RuntimeError(f"Q017_CHAMPION_NUMERIC_REPRODUCTION_MISMATCH:{key}")
    return official


def run(observation_path: Path, mode: str):
    obs = json.loads(observation_path.read_text(encoding="utf-8"))
    valid, reason = prod.validate_observation(obs)
    if not valid:
        raise RuntimeError(f"Q017_OBSERVATION_INVALID:{reason}")
    auth, family = authorize_observation(str(obs["trade_date"]), mode)
    sf = (obs.get("market_inputs") or {}).get("sox") or {}
    dxy = (obs.get("market_inputs") or {}).get("dxy") or {}
    market_go, market_checks = prod.v4.evaluate_market_gate(sf, dxy)

    champion_spec = family["champion"]
    champion = rank_variant(obs, champion_spec, market_go)
    official = exact_champion_check(obs, champion)

    variants = [{"spec": champion_spec, "ranking": champion, "vs_champion": None}]
    for spec in family["challengers"]:
        ranking = rank_variant(obs, spec, market_go)
        variants.append({"spec": spec, "ranking": ranking, "vs_champion": overlap_metrics(champion, ranking)})

    result = {
        "schema_version": 1,
        "program": family["program"],
        "trade_date": obs["trade_date"],
        "mode": mode,
        "evidence_class": auth["evidence_class"],
        "observation_file": str(observation_path.relative_to(ROOT)),
        "observation_snapshot_sha256": obs["observation_snapshot_sha256"],
        "family_sha256": auth["family_sha256"],
        "market_gate": {
            "gate_go": market_go,
            "market_state": official.get("market_state"),
            "checks": market_checks,
        },
        "champion_exact_reproduction": True,
        "variant_count": len(variants),
        "variants": variants,
        "selection_or_acceptance_performed": False,
        "historical_backfill": False,
        "historical_signal_regeneration": False,
        "candidate_acceptance_authorized": False,
        "holdout_access_authorized": False,
        "capital_authority_twd": 0,
        "broker_order_execution": False,
        "PROMOTE_TO_PRODUCTION": "FORBIDDEN",
    }
    result["result_sha256"] = csha(result)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--observation", required=True)
    ap.add_argument("--mode", choices=("smoke", "prospective"), required=True)
    ap.add_argument("--output")
    args = ap.parse_args()
    result = run((ROOT / args.observation).resolve(), args.mode)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
