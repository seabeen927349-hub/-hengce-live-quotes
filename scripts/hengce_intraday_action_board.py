#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _first(d, names, default=None):
    if not isinstance(d, dict):
        return default
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    return default


def _to_float(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except Exception:
        return None


def _to_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False


def _ticker(row):
    v = _first(row, ["Ticker", "ticker", "Symbol", "symbol", "StockNo", "stock_no", "證券代號"])
    return str(v).strip() if v is not None else ""


def _extract_rows(base):
    if isinstance(base, list):
        return base
    if not isinstance(base, dict):
        return []
    for k in ["rows", "data", "rankings", "candidates", "results", "table", "stocks"]:
        v = base.get(k)
        if isinstance(v, list):
            return v
    # last resort: dict keyed by ticker
    out = []
    for k, v in base.items():
        if isinstance(v, dict) and (k.isdigit() or _ticker(v)):
            r = dict(v)
            r.setdefault("Ticker", k)
            out.append(r)
    return out


def _extract_context(ctx):
    state = _first(ctx, ["MarketContextState", "market_context_state", "state", "State"], "CONTEXT_UNAVAILABLE")
    policy = _first(ctx, ["NewCapitalPolicy", "new_capital_policy", "policy", "Policy"], None)
    if policy is None:
        s = str(state).upper()
        if s in {"RISK_OFF", "BLOCK_NEW_CAPITAL"}:
            policy = "BLOCK_NEW_CAPITAL"
        elif s in {"CAUTION", "PROBE_ONLY"}:
            policy = "PROBE_ONLY"
        elif s in {"RISK_ON", "NORMAL", "BROAD_ADVANCE"}:
            policy = "NORMAL"
        else:
            policy = "CONTEXT_UNAVAILABLE"
    return str(state), str(policy)


def _parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _validate_live(live, trade_date=None, max_age_seconds=480, now=None):
    if not isinstance(live, dict):
        return False, "LIVE_NOT_OBJECT"
    generated = _parse_dt(_first(live, ["generated_at_taipei", "generated_at", "timestamp"]))
    snap_id = _first(live, ["snapshot_id", "SnapshotId"])
    if not snap_id or generated is None:
        return False, "LIVE_MISSING_SNAPSHOT_METADATA"
    rows = live.get("data")
    if not isinstance(rows, list) or not rows:
        return False, "LIVE_EMPTY"
    if int(live.get("stale_count", 0) or 0) > 0:
        return False, "LIVE_STALE_COUNT_NONZERO"
    if trade_date:
        qdates = {str(r.get("quote_date")) for r in rows if r.get("quote_date")}
        if qdates and qdates != {trade_date}:
            return False, f"LIVE_TRADE_DATE_MISMATCH:{sorted(qdates)}"
    now = now or datetime.now(generated.tzinfo or timezone.utc)
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=generated.tzinfo)
    age = (now - generated).total_seconds()
    if age < -30:
        return False, "LIVE_FUTURE_TIMESTAMP"
    if age > max_age_seconds:
        return False, f"LIVE_TOO_OLD:{int(age)}s"
    return True, "PASS"


def _geometry(row):
    blo = _to_float(_first(row, ["BreakoutLower", "breakout_lower", "breakout_low", "BreakoutLow", "breakout_zone_low", "BreakoutZoneLow"]))
    bhi = _to_float(_first(row, ["BreakoutUpper", "breakout_upper", "breakout_high", "BreakoutHigh", "breakout_zone_high", "BreakoutZoneHigh"]))
    nochase = _to_float(_first(row, ["NoChase", "no_chase", "NoChasePrice", "no_chase_price"]))
    invalid = _to_float(_first(row, ["Invalidation", "InvalidationPrice", "invalid", "invalid_price", "StructureInvalidation"]))
    return blo, bhi, nochase, invalid


def _price_proof(base_row, live_row):
    p = _to_float(_first(live_row, ["price", "last", "last_price"]))
    hi = _to_float(_first(live_row, ["high", "day_high"]))
    if p is None:
        return "LIVE_UNAVAILABLE"
    blo, bhi, nochase, invalid = _geometry(base_row)
    if invalid is not None and p < invalid:
        return "STRUCTURE_INVALIDATED"
    if nochase is not None and p > nochase:
        return "EXTENSION_NO_CHASE"
    if blo is None or bhi is None:
        return "LIVE_BOUND_NO_GEOMETRY"
    if p < blo:
        if hi is not None and hi >= blo:
            return "FAILED_BREAKOUT"
        return "BELOW_BREAKOUT_WAIT"
    if blo <= p <= bhi:
        return "IN_BREAKOUT_ZONE_NEEDS_ACCEPTANCE"
    if p > bhi:
        return "ABOVE_BREAKOUT_NEEDS_FOLLOW_THROUGH"
    return "LIVE_BOUND_NO_GEOMETRY"


def _decision(base_row, proof, policy):
    formal = _to_bool(_first(base_row, ["FormalEntryTrigger", "formal_entry_trigger", "EntryTrigger", "entry_trigger"], False))
    base_activation = str(_first(base_row, ["ActivationState", "activation_state", "BaseActivationState"], "UNKNOWN"))
    held = _to_bool(_first(base_row, ["PositionHeld", "position_held", "Held", "held"], False))

    # Exit authority always survives context gating.
    if held and proof == "STRUCTURE_INVALIDATED":
        return formal, base_activation, "EXIT_TRIGGERED", "EXIT_ALLOWED", "EXIT_ALL"

    if policy == "BLOCK_NEW_CAPITAL":
        return formal, base_activation, "BLOCKED_BY_MARKET_CONTEXT", "BLOCK_NEW_CAPITAL", "ABSTAIN"
    if policy == "CONTEXT_UNAVAILABLE":
        return formal, base_activation, "CONTEXT_UNAVAILABLE", "FAIL_CLOSED_CONTEXT", "ABSTAIN"

    bad = {"LIVE_UNAVAILABLE", "FAILED_BREAKOUT", "EXTENSION_NO_CHASE", "STRUCTURE_INVALIDATED"}
    if proof in bad:
        return formal, base_activation, f"DOWNGRADED_{proof}", f"ABSTAIN_{proof}", "ABSTAIN"

    # Critical invariant: live may never promote a false formal trigger.
    if not formal:
        return formal, base_activation, "NO_PROMOTED_ACTIVATION", "ABSTAIN_NO_PROMOTED_ACTIVATION", "ABSTAIN"

    if policy == "PROBE_ONLY":
        return formal, base_activation, "DOWNGRADED_TO_PROBE_REVIEW", "REVIEW_PROBE_ONLY", "REVIEW_PROBE"

    return formal, base_activation, "BASE_TRIGGER_LIVE_VALIDATION", "ELIGIBLE_BASE_TRIGGER_LIVE_VALIDATION", "REVIEW_ENTRY"


def build(base, live, context, trade_date=None, max_age_seconds=480, now=None):
    live_ok, live_reason = _validate_live(live, trade_date=trade_date, max_age_seconds=max_age_seconds, now=now)
    ctx_state, policy = _extract_context(context if isinstance(context, dict) else {})
    rows = _extract_rows(base)
    live_map = {_ticker(x): x for x in live.get("data", []) if _ticker(x)} if isinstance(live, dict) else {}

    binding_status = "PASS" if live_ok and policy != "CONTEXT_UNAVAILABLE" else "FAIL_CLOSED"
    out_rows = []
    for r in rows:
        t = _ticker(r)
        lr = live_map.get(t, {}) if live_ok else {}
        proof = _price_proof(r, lr) if live_ok else "LIVE_UNAVAILABLE"
        formal, base_activation, intra_activation, eligibility, action = _decision(r, proof, policy if live_ok else "CONTEXT_UNAVAILABLE")
        out_rows.append({
            "Ticker": t,
            "LivePrice": _to_float(lr.get("price")),
            "LiveHigh": _to_float(lr.get("high")),
            "LiveLow": _to_float(lr.get("low")),
            "LiveAvgPrice": _to_float(lr.get("avg_price")),
            "PriceProof": proof,
            "FormalEntryTrigger": formal,
            "BaseActivationState": base_activation,
            "IntradayActivationState": intra_activation,
            "ExecutionEligibility": eligibility,
            "FinalAction": action,
        })

    return {
        "schema_version": 1,
        "ActionLayer": "INTRADAY_ACTION_BOARD",
        "binding_status": binding_status,
        "binding_reason": "PASS" if binding_status == "PASS" else f"{live_reason}|policy={policy}",
        "BaseRunId": _first(base, ["run_id", "RunId", "scan_id", "ScanId"], None) if isinstance(base, dict) else None,
        "LiveSnapshotId": _first(live, ["snapshot_id", "SnapshotId"], None) if isinstance(live, dict) else None,
        "LiveGeneratedAt": _first(live, ["generated_at_taipei", "generated_at"], None) if isinstance(live, dict) else None,
        "MarketContextState": ctx_state,
        "NewCapitalPolicy": policy,
        "authority": {
            "changes_v1r": False,
            "changes_composite": False,
            "changes_hps": False,
            "changes_entry_geometry": False,
            "changes_40td_freeze": False,
            "can_upgrade_formal_entry_trigger": False,
            "can_block_or_downgrade_execution": True,
            "existing_position_exit_never_blocked": True,
        },
        "rows": out_rows,
    }


def _self_test():
    now = datetime.fromisoformat("2026-10-15T11:30:00+08:00")
    base = {
        "run_id": "TEST_BASE",
        "rows": [
            {"Ticker": "AAA", "FormalEntryTrigger": True, "ActivationState": "READY", "BreakoutLower": 100, "BreakoutUpper": 105, "NoChase": 110, "InvalidationPrice": 90},
            {"Ticker": "BBB", "FormalEntryTrigger": False, "ActivationState": "EMPTY_SHADOW", "BreakoutLower": 100, "BreakoutUpper": 105, "NoChase": 110, "InvalidationPrice": 90},
            {"Ticker": "CCC", "FormalEntryTrigger": True, "PositionHeld": True, "BreakoutLower": 100, "BreakoutUpper": 105, "NoChase": 110, "InvalidationPrice": 90},
        ]
    }
    live = {
        "snapshot_id": "S1", "generated_at_taipei": "2026-10-15T11:29:00+08:00", "stale_count": 0,
        "data": [
            {"symbol": "AAA", "price": 103, "high": 104, "low": 99, "avg_price": 102, "quote_date": "2026-10-15"},
            {"symbol": "BBB", "price": 104, "high": 104, "low": 99, "avg_price": 102, "quote_date": "2026-10-15"},
            {"symbol": "CCC", "price": 89, "high": 101, "low": 88, "avg_price": 95, "quote_date": "2026-10-15"},
        ]
    }
    ctx = {"MarketContextState": "CAUTION", "NewCapitalPolicy": "PROBE_ONLY"}
    o = build(base, live, ctx, trade_date="2026-10-15", now=now)
    assert o["binding_status"] == "PASS"
    m = {r["Ticker"]: r for r in o["rows"]}
    assert m["AAA"]["FinalAction"] == "REVIEW_PROBE"
    assert m["BBB"]["FormalEntryTrigger"] is False and m["BBB"]["FinalAction"] == "ABSTAIN"
    assert m["CCC"]["FinalAction"] == "EXIT_ALL" and m["CCC"]["ExecutionEligibility"] == "EXIT_ALLOWED"

    live2 = dict(live)
    live2["generated_at_taipei"] = "2026-10-15T11:00:00+08:00"
    o2 = build(base, live2, ctx, trade_date="2026-10-15", now=now)
    assert o2["binding_status"] == "FAIL_CLOSED"

    ctx2 = {"MarketContextState": "RISK_OFF", "NewCapitalPolicy": "BLOCK_NEW_CAPITAL"}
    o3 = build(base, live, ctx2, trade_date="2026-10-15", now=now)
    m3 = {r["Ticker"]: r for r in o3["rows"]}
    assert m3["AAA"]["FinalAction"] == "ABSTAIN"
    assert m3["CCC"]["FinalAction"] == "EXIT_ALL"

    print("SELF_TEST_PASS: 10 assertions")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base")
    ap.add_argument("--live")
    ap.add_argument("--context")
    ap.add_argument("--output")
    ap.add_argument("--trade-date")
    ap.add_argument("--max-age-seconds", type=int, default=480)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        _self_test(); return 0
    for name in ["base", "live", "context", "output"]:
        if not getattr(args, name):
            ap.error(f"--{name.replace('_','-')} is required unless --self-test")
    base = json.loads(Path(args.base).read_text(encoding="utf-8"))
    live = json.loads(Path(args.live).read_text(encoding="utf-8"))
    context = json.loads(Path(args.context).read_text(encoding="utf-8"))
    out = build(base, live, context, trade_date=args.trade_date, max_age_seconds=args.max_age_seconds)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"binding_status": out["binding_status"], "rows": len(out["rows"]), "output": args.output}, ensure_ascii=False))
    return 0 if out["binding_status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
