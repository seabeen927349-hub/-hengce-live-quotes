#!/usr/bin/env python3
"""HENGCE E2_PROFIT_MAX live display / paper-state bridge.

Validated Candidate B is frozen. This module replaces the revoked legacy E2 at
its compatibility entrypoint, but never submits broker orders. It publishes a
formal research signal display and a causal paper state for HENGCE.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median

import hengce_daily_command_center_core_legacy as core

TZ = core.TZ
ROOT = core.ROOT
OUT = ROOT / "hengce" / "e2_live"
OUT.mkdir(parents=True, exist_ok=True)
STATE = OUT / "state_latest.json"
MORNING = OUT / "morning_latest.json"
HISTORY = OUT / "history"
HISTORY.mkdir(parents=True, exist_ok=True)
EXECUTION_OVERRIDE = OUT / "execution_override.json"
LOCK = "E2_PROFIT_MAX_DISPLAY_EXECUTION_LOCK_v1_0_20261019.json"
MODEL_LOCK = "research/e2_profit_max/E2_PROFIT_MAX_CANDIDATE_B_PIT_VALIDATION_LOCK_20261019.json"
LEGACY_REVOCATION = "E2_LEGACY_REVOCATION_20261019.json"
SCHEMA = 2
K = 25.0
LOCAL_M1_MAX = 0.0
LOCAL_M5_MAX = -0.02
SOX1_MAX = 0.0
SOX5_MAX = -0.03
RESID_MAX = 0.04
LIQ20_MIN = 20_000_000.0
BETA_WINDOW = 60
BETA_MIN = 30
HOLD_INTERVALS = 20


def atomic_json(path: Path, obj: dict) -> None:
    core.atomic_json(path, obj)


def f(x):
    try:
        v = float(str(x).replace(",", "").strip())
        return v if math.isfinite(v) else None
    except Exception:
        return None


def iso_date(x):
    if not x:
        return None
    return str(x)[:10]


def load_old_state() -> dict:
    if not STATE.exists():
        return {"paper_position": {"state": "IDLE"}}
    try:
        x = json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"paper_position": {"state": "DATA_PENDING", "reason": "STATE_JSON_INVALID"}}
    if x.get("module") != "E2_PROFIT_MAX_STATE":
        return {"paper_position": {"state": "IDLE"}, "legacy_state_ignored": True}
    return x


def load_execution_override() -> dict:
    if not EXECUTION_OVERRIDE.exists():
        return {}
    try:
        x = json.loads(EXECUTION_OVERRIDE.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "INVALID", "reason": "EXECUTION_OVERRIDE_JSON_INVALID"}
    if not isinstance(x, dict):
        return {"status": "INVALID", "reason": "EXECUTION_OVERRIDE_NOT_OBJECT"}
    return x


def apply_execution_override(pos: dict, target) -> tuple[dict, dict]:
    """Apply an explicit user execution fact without mutating Candidate B ranking/model.

    Supported v1 override:
      {"version":1,"status":"NO_FILL","ticker":"3026","signal_date":"2026-10-19",
       "effective_date":"2026-10-20","reason":"USER_CONFIRMED_NOT_FILLED"}

    A NO_FILL can only release a matching ENTRY_PENDING/HOLDING paper position and is
    therefore fail-closed against stale or unrelated overrides.
    """
    ov = load_execution_override()
    if not ov:
        return pos, {"applied": False, "status": "NONE"}
    if ov.get("status") == "INVALID":
        return {**pos, "state": "DATA_PENDING", "reason": ov.get("reason")}, {
            "applied": False, "status": "INVALID", "reason": ov.get("reason")
        }
    status = str(ov.get("status") or "").upper()
    if status != "NO_FILL":
        return {**pos, "state": "DATA_PENDING", "reason": "UNSUPPORTED_EXECUTION_OVERRIDE_STATUS"}, {
            "applied": False, "status": status or "MISSING", "reason": "UNSUPPORTED_EXECUTION_OVERRIDE_STATUS"
        }
    if ov.get("version") != 1:
        return {**pos, "state": "DATA_PENDING", "reason": "EXECUTION_OVERRIDE_VERSION_MISMATCH"}, {
            "applied": False, "status": status, "reason": "EXECUTION_OVERRIDE_VERSION_MISMATCH"
        }
    eff = iso_date(ov.get("effective_date"))
    if not eff or eff > target.isoformat():
        return pos, {"applied": False, "status": status, "reason": "NOT_EFFECTIVE_YET"}
    ticker = str(ov.get("ticker") or "")
    signal_date = iso_date(ov.get("signal_date"))
    pos_ticker = str(pos.get("ticker") or "")
    pos_signal_date = iso_date(pos.get("signal_date"))
    if pos.get("state") == "NO_FILL":
        # Preserve the historical no-fill on its effective date only. On a later
        # session the slot is genuinely free; do not let a persistent override
        # become a permanent lock.
        if iso_date(pos.get("execution_effective_date")) == target.isoformat():
            return pos, {"applied": False, "status": status, "reason": "ALREADY_APPLIED_THIS_SESSION"}
        return {"state": "IDLE"}, {"applied": False, "status": status, "reason": "PRIOR_NO_FILL_SLOT_RELEASED"}
    if pos.get("state") not in ("ENTRY_PENDING", "HOLDING"):
        return pos, {"applied": False, "status": status, "reason": "NO_OPEN_PAPER_POSITION"}
    if ticker != pos_ticker or signal_date != pos_signal_date:
        return {**pos, "state": "DATA_PENDING", "reason": "EXECUTION_OVERRIDE_POSITION_MISMATCH"}, {
            "applied": False, "status": status, "reason": "EXECUTION_OVERRIDE_POSITION_MISMATCH"
        }
    released = {
        "state": "NO_FILL",
        "signal_date": pos_signal_date,
        "ticker": pos_ticker,
        "name": pos.get("name", ""),
        "score": pos.get("score"),
        "beta60": pos.get("beta60"),
        "residual": pos.get("residual"),
        "entry_due": pos.get("entry_due"),
        "execution_effective_date": eff,
        "execution_reason": ov.get("reason") or "USER_CONFIRMED_NOT_FILLED",
        "slot_released": True,
        "model_signal_preserved": True,
        "broker_order_execution": False,
    }
    return released, {
        "applied": True,
        "status": "NO_FILL",
        "ticker": pos_ticker,
        "signal_date": pos_signal_date,
        "effective_date": eff,
        "slot_released": True,
    }


def tw_rows_through(target):
    rows = core.load_tw_history()
    z = []
    for r in rows:
        ds = iso_date(r.get("date"))
        if not ds or ds > target.isoformat():
            continue
        c = f(r.get("close")); op = f(r.get("open")); turn = f(r.get("turnover_ntd"))
        t = str(r.get("ticker") or "")
        if len(t) != 4 or not t.isdigit() or c is None or c <= 0:
            continue
        z.append({"date": ds, "ticker": t, "name": r.get("name", ""), "open": op, "close": c, "turnover": turn})
    if not z:
        raise RuntimeError("E2_ELECTRONICS_HISTORY_EMPTY")
    latest = max(r["date"] for r in z)
    if latest != target.isoformat():
        raise RuntimeError(f"E2_ELECTRONICS_HISTORY_NOT_CURRENT:{latest}:TARGET={target.isoformat()}")
    return z


def prepare_features(rows, target):
    by_t = defaultdict(list)
    for r in rows:
        by_t[r["ticker"]].append(dict(r))
    stock = {}
    by_date_r1 = defaultdict(list)
    for t, rs in by_t.items():
        rs.sort(key=lambda x: x["date"])
        prev = None
        turns = []
        for i, r in enumerate(rs):
            r1 = (r["close"] / prev - 1.0) if prev not in (None, 0) else None
            turns.append(r["turnover"] if r["turnover"] is not None else float("nan"))
            vals = [v for v in turns[max(0, len(turns)-20):] if math.isfinite(v)]
            liq = (sum(vals) / len(vals)) if len(vals) >= 10 else None
            r["r1"] = r1; r["liq20"] = liq; r["idx"] = i
            stock[(r["date"], t)] = r
            if r1 is not None and math.isfinite(r1):
                by_date_r1[r["date"]].append(r1)
            prev = r["close"]
    market = {}
    dates = sorted(by_date_r1)
    for i, ds in enumerate(dates):
        vals = by_date_r1[ds]
        m1 = median(vals) if vals else None
        market[ds] = {"m1": m1, "m5": None}
        if i >= 4:
            xs = [market[d]["m1"] for d in dates[i-4:i+1]]
            if all(v is not None for v in xs):
                prod = 1.0
                for v in xs: prod *= (1.0 + v)
                market[ds]["m5"] = prod - 1.0
    td = target.isoformat()
    if td not in market or market[td]["m1"] is None or market[td]["m5"] is None:
        raise RuntimeError("E2_LOCAL_MARKET_FEATURES_MISSING")
    candidates = []
    for t, rs in by_t.items():
        rs.sort(key=lambda x: x["date"])
        idx = next((i for i, r in enumerate(rs) if r["date"] == td), None)
        if idx is None:
            continue
        cur = rs[idx]
        if cur.get("r1") is None or cur.get("liq20") is None or cur["liq20"] < LIQ20_MIN:
            continue
        prior = rs[max(0, idx-BETA_WINDOW):idx]
        obs = []
        for p in prior:
            mr = market.get(p["date"], {}).get("m1")
            if p.get("r1") is not None and mr is not None:
                obs.append((p["r1"], mr))
        if len(obs) < BETA_MIN:
            continue
        sr = sum(a for a,b in obs); sm = sum(b for a,b in obs); n = len(obs)
        cov = sum(a*b for a,b in obs)/n - (sr/n)*(sm/n)
        var = sum(b*b for a,b in obs)/n - (sm/n)*(sm/n)
        if abs(var) <= 1e-18:
            continue
        beta = cov / var
        if not math.isfinite(beta) or beta <= 0:
            continue
        resid = cur["r1"] - beta * market[td]["m1"]
        if not math.isfinite(resid) or resid > RESID_MAX:
            continue
        score = beta * (1.0 + K * max(-resid, 0.0))
        candidates.append({
            "ticker": t, "name": cur.get("name", ""), "beta60": beta,
            "stock_r1": cur["r1"], "electronics_m1": market[td]["m1"],
            "electronics_m5": market[td]["m5"], "residual": resid,
            "score": score, "liq20_turnover_twd": cur["liq20"], "signal_close": cur["close"]
        })
    candidates.sort(key=lambda x: (-x["score"], x["ticker"]))
    return market[td], candidates, sorted({r["date"] for r in rows})


def macro_features(target):
    core.refresh_sox(target)
    return core.sox_features(target)


def quote_open(ticker):
    key = os.environ.get("FUGLE_API_KEY")
    if not key:
        return None, "FUGLE_API_KEY_MISSING"
    q, err = core.fugle_quote(ticker, key)
    if not q:
        return None, err or "QUOTE_MISSING"
    op = f(q.get("openPrice"))
    return op, None if op is not None else "OPEN_NOT_OBSERVED_YET"


def find_close(rows, ticker, ds):
    for r in rows:
        if r["ticker"] == ticker and r["date"] == ds:
            return r["close"]
    return None


def position_progress(pos, market_dates, rows, target):
    if pos.get("state") != "HOLDING":
        return pos, False
    ed = iso_date(pos.get("entry_date")); ticker = str(pos.get("ticker") or "")
    if not ed or not ticker:
        return {**pos, "state": "DATA_PENDING", "reason": "HOLDING_STATE_INCOMPLETE"}, False
    after = [d for d in market_dates if d > ed]
    completed = sum(1 for d in after if d <= target.isoformat())
    pos = {**pos, "completed_hold_intervals": completed, "hold_target_intervals": HOLD_INTERVALS,
           "display_progress": f"D{min(completed,HOLD_INTERVALS)}/{HOLD_INTERVALS}"}
    if len(after) >= HOLD_INTERVALS:
        due = after[HOLD_INTERVALS-1]
        pos["scheduled_exit_date"] = due
        if due <= target.isoformat():
            close = find_close(rows, ticker, due)
            if close is None:
                return {**pos, "state": "DATA_PENDING", "reason": "EXIT_CLOSE_MISSING"}, False
            pos.update({"state": "EXITED", "exit_date": due, "exit_reference_close": close,
                        "display_progress": f"D{HOLD_INTERVALS}/{HOLD_INTERVALS}"})
            ep = f(pos.get("entry_reference_open"))
            if ep not in (None, 0):
                pos["paper_gross_return"] = close/ep - 1.0
                pos["paper_net_return_after_0_8pct_cost"] = close/ep - 1.0 - 0.008
            return pos, True
    return pos, False


def compatibility_strict(engine_status, top1, action):
    rows = []
    if top1:
        rows = [{"Ticker": int(top1["ticker"]), "Name": top1.get("name", ""),
                 "E2Score": top1.get("score"), "E2Action": action, "E2Rank": 1}]
    return {"authority": LOCK, "cohort_count": len(rows), "engine_status": engine_status,
            "buy_count": 1 if action == "ENTRY_PENDING" else 0,
            "watch_count": 1 if rows and action not in ("ENTRY_PENDING", "HOLDING", "EXIT") else 0,
            "rows": rows}


def build_postclose(target):
    existing = core.load_tw_history()
    latest = max((r.get("date", "") for r in existing), default="")
    if latest < target.isoformat():
        core.append_electronics_day(target)
    rows = tw_rows_through(target)
    local, candidates, market_dates = prepare_features(rows, target)
    sf = macro_features(target)
    local_checks = {"electronics_m1_lt_0": local["m1"] < LOCAL_M1_MAX,
                    "electronics_m5_lte_minus_2pct": local["m5"] <= LOCAL_M5_MAX}
    macro_checks = {"sox_1d_lte_0": sf["sox_1d"] <= SOX1_MAX,
                    "sox_5d_lte_minus_3pct": sf["sox_5d"] <= SOX5_MAX}
    gate_go = all(local_checks.values()) and all(macro_checks.values())
    top1 = candidates[0] if candidates else None
    old = load_old_state(); prior_pos = dict(old.get("paper_position") or {"state":"IDLE"})
    prior_pos, execution_override = apply_execution_override(prior_pos, target)
    prior_state = prior_pos.get("state", "IDLE")
    no_fill_today = prior_state == "NO_FILL" and iso_date(prior_pos.get("execution_effective_date")) == target.isoformat()
    if no_fill_today:
        # Do not permit same-session hindsight replacement. The user may report a
        # missed fill after observing the session; next-session selection resumes
        # normally, preserving causal validation.
        pos = prior_pos
        exited_today = False
        can_accept = False
    else:
        pos, exited_today = position_progress(prior_pos, market_dates, rows, target)
        can_accept = prior_state in ("IDLE", "EXITED") and not (
            prior_state == "EXITED" and iso_date(prior_pos.get("exit_date")) == target.isoformat()
        )
        if prior_state == "EXITED" and iso_date(prior_pos.get("exit_date")) < target.isoformat():
            pos = {"state": "IDLE"}; can_accept = True
        if prior_state == "HOLDING" or prior_state == "ENTRY_PENDING" or exited_today:
            can_accept = False
    action = "OFF"
    if pos.get("state") == "HOLDING":
        action = "HOLDING"
    elif pos.get("state") == "ENTRY_PENDING":
        action = "ENTRY_PENDING"
    elif pos.get("state") == "EXITED":
        action = "EXIT"
    elif pos.get("state") == "NO_FILL":
        action = "NO_FILL"
    elif gate_go and top1 and can_accept:
        pos = {"state":"ENTRY_PENDING", "signal_date":target.isoformat(), "ticker":top1["ticker"],
               "name":top1.get("name",""), "score":top1["score"], "beta60":top1["beta60"],
               "residual":top1["residual"], "entry_due":"NEXT_TWSE_SESSION_OPEN",
               "hold_target_intervals":HOLD_INTERVALS, "roundtrip_cost_model":0.008}
        action = "ENTRY_PENDING"
    elif gate_go and top1 and not can_accept:
        action = "BLOCKED_NON_OVERLAP"
    engine_status = "ON" if action == "ENTRY_PENDING" else "HOLDING" if pos.get("state") == "HOLDING" else "EXIT" if pos.get("state") == "EXITED" else "NO_FILL" if pos.get("state") == "NO_FILL" else "OFF"
    strict = compatibility_strict(engine_status, top1, action)
    occupied = 1 if pos.get("state") in ("ENTRY_PENDING", "HOLDING") else 0
    out = {
        "schema_version": SCHEMA, "system":"HENGCE", "module":"E2_PROFIT_MAX_STATE",
        "generated_at_taipei":core.now_tw().isoformat(), "signal_asof":target.isoformat(),
        "engine":"E2_PROFIT_MAX", "engine_status":engine_status,
        "binding_status":"PASS", "authority":"VALIDATED_RESEARCH_SIGNAL_DISPLAY",
        "capital_authority_twd":0, "broker_order_execution":False,
        "market_regime":"PROFIT_MAX_GATE_GO" if gate_go else "PROFIT_MAX_GATE_OFF",
        "local_gate":{"go":all(local_checks.values()), "checks":local_checks, "electronics_m1":local["m1"], "electronics_m5":local["m5"]},
        "macro_gate":{"go":all(macro_checks.values()), "checks":macro_checks, "sox_session":sf["session"], "sox_1d":sf["sox_1d"], "sox_5d":sf["sox_5d"], "dxy_used":False},
        "top1":top1, "action":action, "paper_position":pos,
        "execution_override": execution_override,
        "strict":strict,
        "extension_shadow":{"engine_status":"DISABLED_LEGACY_REVOKED","capital_authorized":False,"rows":[]},
        "position_state":{"asof":target.isoformat(), "held":[pos] if pos.get("state")=="HOLDING" else [],
                          "pending":[pos] if pos.get("state")=="ENTRY_PENDING" else [],
                          "no_fill":[pos] if pos.get("state")=="NO_FILL" else [],
                          "max_slots":1,"occupied_next_session":occupied,"free_slots_next_session":1-occupied},
        "locks":{"model":MODEL_LOCK,"display_execution":LOCK,"legacy_revocation":LEGACY_REVOCATION},
        "rules":{"K":K,"top_n":1,"hold_intervals":HOLD_INTERVALS,"cost_roundtrip":0.008,"overlap":"FORBIDDEN","dxy_used":False,
                 "no_fill_policy":"EXPLICIT_MATCHED_OVERRIDE_RELEASES_NEXT_SESSION_SLOT_NO_SAME_SESSION_HINDSIGHT"},
        "q017_effect":"NONE"
    }
    atomic_json(STATE, out)
    atomic_json(HISTORY / f"{target.strftime('%Y%m%d')}_postclose.json", out)
    return out


def build_morning(target):
    state = load_old_state(); pos = dict(state.get("paper_position") or {"state":"IDLE"})
    pos, execution_override = apply_execution_override(pos, target)
    source_asof = state.get("signal_asof")
    entry_due = []
    if pos.get("state") == "ENTRY_PENDING" and iso_date(pos.get("signal_date")) < target.isoformat():
        op, err = quote_open(str(pos.get("ticker")))
        if op is not None:
            pos.update({"state":"HOLDING","entry_date":target.isoformat(),"entry_reference_open":op,
                        "entry_reference_source":"FUGLE_OBSERVED_OPEN","completed_hold_intervals":0,
                        "hold_target_intervals":HOLD_INTERVALS,"display_progress":f"D0/{HOLD_INTERVALS}"})
            state["paper_position"] = pos
            state["engine_status"] = "HOLDING"
            state["action"] = "HOLDING"
            state["generated_at_taipei"] = core.now_tw().isoformat()
            state["strict"] = compatibility_strict("HOLDING", state.get("top1"), "HOLDING")
            state["execution_override"] = execution_override
            state["position_state"] = {"asof":target.isoformat(),"held":[pos],"pending":[],"no_fill":[],"max_slots":1,"occupied_next_session":1,"free_slots_next_session":0}
            atomic_json(STATE, state)
        else:
            entry_due = [{**pos, "entry_observation_status":err}]
    elif pos.get("state") == "NO_FILL":
        state["paper_position"] = pos
        state["engine_status"] = "NO_FILL"
        state["action"] = "NO_FILL"
        state["generated_at_taipei"] = core.now_tw().isoformat()
        state["execution_override"] = execution_override
        state["strict"] = compatibility_strict("NO_FILL", state.get("top1"), "NO_FILL")
        state["position_state"] = {"asof":target.isoformat(),"held":[],"pending":[],"no_fill":[pos],"max_slots":1,"occupied_next_session":0,"free_slots_next_session":1}
        atomic_json(STATE, state)
    out = {
        "schema_version":SCHEMA,"system":"HENGCE","module":"E2_PROFIT_MAX_MORNING_BRIDGE",
        "trade_date":target.isoformat(),"generated_at_taipei":core.now_tw().isoformat(),"binding_status":"PASS",
        "source_signal_asof":source_asof,"engine_status":state.get("engine_status","OFF"),
        "new_signal_buy_count":1 if pos.get("state")=="ENTRY_PENDING" else 0,
        "entry_due_count":len(entry_due),"entry_due":entry_due,
        "held_from_prior_close":[pos] if pos.get("state")=="HOLDING" else [],
        "no_fill_from_prior_signal":[pos] if pos.get("state")=="NO_FILL" else [],
        "paper_position":pos,"top1":state.get("top1"),"local_gate":state.get("local_gate"),"macro_gate":state.get("macro_gate"),
        "execution_override":execution_override,
        "authority":"VALIDATED_RESEARCH_SIGNAL_DISPLAY","capital_authority_twd":0,"broker_order_execution":False,
        "note":"Informational/paper state only; no automatic broker order submission."
    }
    atomic_json(MORNING, out)
    return out


def self_test():
    beta = 2.0; resid = -0.03
    score = beta*(1+K*max(-resid,0))
    assert abs(score-3.5) < 1e-12
    assert LOCAL_M5_MAX == -0.02 and SOX5_MAX == -0.03 and HOLD_INTERVALS == 20
    ds = [f"2026-01-{i:02d}" for i in range(1,23)]
    p = {"state":"HOLDING","entry_date":ds[0],"ticker":"2330","entry_reference_open":100.0}
    rows = [{"date":d,"ticker":"2330","close":110.0} for d in ds]
    q, ex = position_progress(p, ds, rows, datetime.strptime(ds[20], "%Y-%m-%d").date())
    assert ex and q["exit_date"] == ds[20] and q["display_progress"] == f"D{HOLD_INTERVALS}/{HOLD_INTERVALS}"
    print(json.dumps({"self_test":"PASS","engine":"E2_PROFIT_MAX","schema":SCHEMA,"K":K,"hold_intervals":HOLD_INTERVALS,
                      "no_fill_execution_state":True,"candidate_b_formula_mutated":False,"broker_order_execution":False}))


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--mode",choices=["morning","postclose","self-test"],required=True);ap.add_argument("--date");a=ap.parse_args()
    target=datetime.strptime(a.date,"%Y-%m-%d").date() if a.date else core.now_tw().date()
    if a.mode=="self-test": self_test(); return 0
    try:
        out=build_morning(target) if a.mode=="morning" else build_postclose(target)
        print(json.dumps(out,ensure_ascii=False,indent=2));return 0
    except Exception as e:
        fail={"schema_version":SCHEMA,"system":"HENGCE","module":"E2_PROFIT_MAX_STATE","mode":a.mode,"trade_date":target.isoformat(),
              "generated_at_taipei":core.now_tw().isoformat(),"binding_status":"DATA_PENDING","engine_status":"DATA_PENDING",
              "authority":"NO_E2_SIGNAL","capital_authority_twd":0,"broker_order_execution":False,"error":f"{type(e).__name__}:{e}",
              "paper_position":{"state":"DATA_PENDING"},"strict":{"authority":LOCK,"engine_status":"DATA_PENDING","buy_count":0,"watch_count":0,"rows":[]},
              "q017_effect":"NONE","policy":"FAIL_CLOSED_E2_ONLY_Q017_INDEPENDENT"}
        atomic_json(STATE if a.mode=="postclose" else MORNING,fail);print(json.dumps(fail,ensure_ascii=False,indent=2));return 2

if __name__=="__main__": raise SystemExit(main())