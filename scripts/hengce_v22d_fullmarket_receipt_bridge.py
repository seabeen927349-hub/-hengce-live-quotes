#!/usr/bin/env python3
"""Convert one verified PRIVATE V2.2D all-TWSE inference into one research receipt.

This bridge never loads/retrains model weights, acquires new market data, or
grants selection/order authority. Existing EOD and HBA TDCC vessels only.
The post-decision ownership overlay is research-only, NEVER a model feature.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path

CLASSIFIER = "db47b6f2276150610972d50a8f2b1a9d816eb89fc415d41db5c81b12c1c94a97"
REGRESSOR = "8e6931fa9b4ca4324db3b24feb47312bbcbdb9030388e00ab5e8f2e36b014c06"
SCHEMA = "HENGCE_UNIFIED_V22D_TWSE_10LOT_RESEARCH_V1"


class BridgeBlocked(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise BridgeBlocked(reason)


def as_date(value, fmt="%Y-%m-%d"):
    try:
        return dt.datetime.strptime(value, fmt).date()
    except (TypeError, ValueError):
        raise BridgeBlocked("INVALID_SOURCE_DATE")


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def verified_receipt(model):
    require(model.get("schema") == "HENGCE_V22D_PRIVATE_ORIGINAL_CHECKPOINT_REPLAY_V1",
            "INVALID_MODEL_RECEIPT_SCHEMA")
    require(model.get("status") == "RESEARCH_REPLAY_NOT_PIT_CERTIFIED"
            and model.get("universe_mode") == "ALL_TWSE_10LOT_RESEARCH",
            "NOT_ORIGINAL_ALL_TWSE_MODEL")
    for key in ("trading_authority", "formal_selection_authority",
                "buy_signal", "sell_signal", "broker_execution"):
        require(model.get(key) is False, "MODEL_AUTHORITY_VIOLATION")
    require(model.get("authorized_lots") == 0 and model.get("capital_authority_twd") == 0,
            "MODEL_ORDER_AUTHORITY_VIOLATION")
    source = model.get("source_sha256") or {}
    require(source.get("classifier") == CLASSIFIER and source.get("regressor") == REGRESSOR,
            "ORIGINAL_CHECKPOINT_NOT_VERIFIED")
    r = dict(model)
    digest = r.pop("receipt_sha256", None)
    sha = hashlib.sha256(json.dumps(r, ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":")).encode()).hexdigest()
    require(digest == sha, "MODEL_RECEIPT_SHA_MISMATCH")
    require(model.get("historical_tdcc_first_observed_pit_certified") is False,
            "FALSE_PIT_CERTIFICATION")
    return source


def reason_for_exit(row):
    if row is None:
        return "INPUT_MISSING_CANNOT_VERIFY_EXIT"
    parts = []
    if not finite(row.get("ret20")) or row["ret20"] < .05:
        parts.append("RET20_BELOW_GATE_OR_MISSING")
    if not finite(row.get("ret5")) or row["ret5"] < 0:
        parts.append("RET5_BELOW_GATE_OR_MISSING")
    if not finite(row.get("volatility20")) or row["volatility20"] <= 0:
        parts.append("VOLATILITY20_INVALID")
    if not finite(row.get("turnover20_median")) or row["turnover20_median"] < 1e7:
        parts.append("TURNOVER20_BELOW_GATE_OR_MISSING")
    if not finite(row.get("close")) or row["close"] <= 0:
        parts.append("INVALID_CLOSE")
    if finite(row.get("score")) and row["score"] < .5:
        parts.append("SCORE_BELOW_0_50")
    return "_AND_".join(parts) if parts else "INELIGIBILITY_UNRESOLVED"


def bridge(model, eod, integrated, names, previous=None, now=None):
    """All args are existing verified data receipts (not a model replacement)."""
    now = now or dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    require(now.tzinfo is not None, "NAIVE_OBSERVATION_TIMESTAMP")
    original = verified_receipt(model)
    decision = as_date(model.get("decision_date"))
    require(decision <= now.date(), "FUTURE_DECISION")
    require(model.get("friday_shadow_only") is (decision.weekday() == 4),
            "ORIGINAL_DECISION_WEEKDAY_FLAG_INVALID")
    require(decision.weekday() <= 4, "WEEKEND_MODEL_DECISION")
    require(eod.get("status") == "COMPLETE" and
            eod.get("three_leg_complete") is True and
            eod.get("formal_complete_day") is True and
            eod.get("downstream_ready") is True and
            eod.get("mother_status") == "COMPLETE" and
            eod.get("target_date") == decision.isoformat(),
            "EXISTING_ORIGINAL_EOD_NOT_VERIFIED")
    # This version requires the identical canonical mother bytes. A future
    # derived rolling cache must prove its per-day EOD chain in a new contract.
    cache_mode = model.get("source_canonical_input_kind")
    if cache_mode == "DERIVED_VERIFIED_ROLLING_CACHE_FROM_ORIGINAL_MOTHER":
        # Parent is the original EOD canonical mother, never the derived
        # rolling subset. The model's own SHA is the verified private input.
        require(model.get("source_canonical_parent_sha256") ==
                eod.get("mother_sha256"),
                "CANONICAL_MOTHER_PARENT_HASH_MISMATCH")
        require(model.get("source_seed_full_canonical_sha256_20261113") ==
                "76db96b5b9d52027b954ef6088d37d1f644e53ceb32466dbef721f290c87cd63",
                "ORIGINAL_PARENT_SEED_UNVERIFIED")
        proofs=model.get("source_eod_proofs")
        require(isinstance(proofs,list) and proofs and
                proofs[-1].get("date")==model.get("decision_date") and
                proofs[-1].get("mother_sha256")==eod.get("mother_sha256"),
                "ORIGINAL_EOD_SHA_PROOF_MISSING")
    else:
        require(eod.get("mother_sha256") == original.get("original_2026_canonical"),
                "CANONICAL_MOTHER_HASH_MISMATCH")
    tdcc_known = as_date(model.get("last_assumed_tdcc_snapshot"))
    require(tdcc_known <= decision - dt.timedelta(days=14), "TDCC_MODEL_LOOKAHEAD")
    require(integrated.get("observed_eod_date") == decision.isoformat(),
            "HBA_EOD_DATE_MISMATCH")
    research = integrated.get("two_group_research") or {}
    require(research.get("status") == "VERIFIED_TWO_GROUP_RESEARCH" and
            research.get("other_definition") == "grade 17 total minus grades 1-3 shares",
            "HBA_TWO_GROUP_NOT_VERIFIED")
    overlay = as_date(research.get("last_tdcc_date"), "%Y%m%d")
    require(overlay <= decision, "POST_DECISION_TDCC_NOT_PERMITTED_AS_ASOF")
    first = dt.datetime.fromisoformat(research.get("first_observed_taipei", ""))
    require(first.tzinfo is not None and first <= now, "TDCC_NOT_YET_OBSERVED")
    obs = integrated.get("two_group_market_registry")
    require(isinstance(obs, list) and len(obs) == research.get("market_registry_total"),
            "HBA_REGISTRY_INCOMPLETE")
    holders = {}
    for row in obs:
        ticker = row.get("ticker")
        require(ticker not in holders, "DUPLICATE_TDCC_TICKER")
        holders[ticker] = row
    scores = model.get("all_scored_for_exit_audit")
    ranked = model.get("all_qualified")
    require(isinstance(scores, list) and
            len(scores) == model.get("feature_coverage") and
            isinstance(ranked, list) and
            len(ranked) == model.get("qualified_count") and len(ranked) <= 3000,
            "ORIGINAL_MODEL_COVERAGE_INCONSISTENT")
    sc = {v.get("ticker"):v for v in scores}
    require(len(sc) == len(scores) and
            sum(1 for v in scores if v.get("model_gate") is True) == len(ranked),
            "MODEL_SCORE_GATE_AUDIT_FAILED")
    built = []
    seen=set()
    for i, row in enumerate(ranked, 1):
        ticker = row.get("ticker")
        require(ticker not in seen and isinstance(ticker, str) and
                len(ticker)==4 and ticker.isdigit() and not ticker.startswith("91"),
                "DUPLICATE_OR_INVALID_RANKED_STOCK")
        seen.add(ticker)
        require(row.get("rank") == i and sc.get(ticker, {}).get("model_gate") is True,
                "MODEL_RANK_DISAGREES_WITH_SCORING")
        observed = holders.get(ticker)
        require(observed is not None and ticker in names, "MISSING_VERIFIED_HBA_OR_NAME")
        current = observed.get("small_holders")
        delta = observed.get("small_holders_delta")
        small_shares = observed.get("small_shares")
        other_shares = observed.get("other_shares")
        require(all(finite(v) for v in (current, delta, small_shares, other_shares))
                and current-delta>0 and small_shares>=0 and other_shares>=0 and
                small_shares+other_shares>0, "INVALID_HBA_HOLDERS_OR_SHARES")
        require(all(finite(row.get(k)) for k in
                    ("score", "close", "ret20", "ret5", "turnover20_median"))
                and row["score"] >= .5 and row["ret20"] >= .05 and
                row["ret5"] >= 0 and row["turnover20_median"] >= 1e7,
                "ORIGINAL_MODEL_PRICE_GATE_MISMATCH")
        built.append({
            "rank": i, "ticker": ticker, "name": names[ticker],
            "close": row["close"], "score": row["score"],
            "ret20": row["ret20"], "ret5": row["ret5"],
            "turnover20_median": row["turnover20_median"],
            "retail_holder_date": overlay.isoformat(),
            "retail_holder_week_delta_pct": 100*delta/(current-delta),
            "other_shares_pct": 100*other_shares/(small_shares+other_shares),
            "in_legacy781": None,
        })
    exiting = []
    if isinstance(previous, dict) and previous.get("status") == "RESEARCH_SCAN_READY":
        old_date = as_date(previous.get("decision_date"))
        require(old_date <= decision, "PREVIOUS_REPORT_FROM_FUTURE")
        for item in (previous.get("ranked", []) if old_date < decision else []):
            ticker = item.get("ticker")
            if ticker not in seen:
                evidence = sc.get(ticker)
                exiting.append({"ticker":ticker, "name":item.get("name") or ticker,
                                "score":evidence.get("score") if evidence else None,
                                "score_date":decision.isoformat() if evidence else None,
                                "reason":reason_for_exit(evidence)})
    require(all(built[i]["turnover20_median"] >= built[i+1]["turnover20_median"]
                for i in range(len(built)-1)), "RANKING_TURNOVER_ORDER_INVALID")
    return {
        "schema":SCHEMA, "system":"HENGCE",
        "status":"VERIFIED_HISTORICAL_REPLAY_RESEARCH_ONLY",
        "decision_date":decision.isoformat(),
        "source_price_eod":decision.isoformat(),
        "source_tdcc_model_asof":tdcc_known.isoformat(),
        "source_tdcc_research_overlay":overlay.isoformat(),
        "friday_shadow_only":decision.weekday()==4,
        "model_id":"v22d_daily_nowcast_liquidity_top5_v1",
        "model_classifier_sha256":CLASSIFIER,
        "model_regressor_sha256":REGRESSOR,
        "source_canonical_mother_sha256":original["original_2026_canonical"],
        "original_eod_receipt":"eod/"+decision.strftime("%Y%m%d")+"/status.json",
        "universe_coverage":len(scores),
        "price_gate_count":model.get("price_gate_count"),
        "qualified_count":len(built),
        "original_781_qualified":None,
        "ranking_method":"20D_MEDIAN_TURNOVER_DESC_TICKER_ASC",
        "score_threshold":.5,
        "top5":built[:5], "all_qualified":built, "exited":exiting,
        "model_first_publication_pit_verified":False,
        "formal_strategy_active":False, "buy_signal":False,
        "sell_signal":False, "broker_order_execution":False,
        "capital_authority_twd":0,"authorized_lots":0,
        "source_role":"VERIFIED_PRIVATE_ORIGINAL_CHECKPOINT_BRIDGE_RESEARCH_ONLY",
        "model_receipt_sha256":model["receipt_sha256"],
        "tdcc_actual_first_observed":first.isoformat(),
    }


def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model-receipt", required=True, type=Path)
    p.add_argument("--hba-integrated", required=True, type=Path)
    p.add_argument("--eod-status", required=True, type=Path)
    p.add_argument("--official-price-csv", required=True, type=Path)
    p.add_argument("--previous-report", type=Path)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args()
    import csv
    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))
    with a.official_price_csv.open(encoding="utf-8-sig", newline="") as handle:
        names={v["Ticker"]:v["Name"] for v in csv.DictReader(handle)}
    result=bridge(read(a.model_receipt),read(a.eod_status),read(a.hba_integrated),
                  names,read(a.previous_report) if a.previous_report else None)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2,
                                sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"qualified":result["qualified_count"],
                      "exited":len(result["exited"])},ensure_ascii=False))


if __name__=="__main__":
    main()
