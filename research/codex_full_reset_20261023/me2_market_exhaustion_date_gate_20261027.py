from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FIXED_PATH = Path(__file__).with_name("frozen_fixed_capital_roundlot_20261026.py")
OUT = ROOT / "research/codex_full_reset_20261023/results/me2_market_exhaustion_date_gate_20261027"
OUT.mkdir(parents=True, exist_ok=True)

RECENT_START = pd.Timestamp("2026-07-22")
RECENT_END = pd.Timestamp("2026-10-21")
YEAR_START = pd.Timestamp("2025-10-22")
YEAR_END = pd.Timestamp("2026-10-21")

BASELINE_EXPECTED = {
    "trades": 39,
    "signal_days": 14,
    "pnl": 92556.0,
    "pf": 1.888,
}


def load_fixed_module():
    spec = importlib.util.spec_from_file_location("fixed_cap", FIXED_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {FIXED_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def add_date_state(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = panel.copy().sort_values(["Ticker", "Date"]).reset_index(drop=True)
    g = x.groupby("Ticker", group_keys=False)
    if "prev_close" not in x.columns:
        x["prev_close"] = g["Close"].shift(1)
    x["ret1_me2"] = x["Close"] / x["prev_close"] - 1.0
    x["body_me2"] = x["Close"] / x["Open"] - 1.0
    rng = (x["High"] - x["Low"]).replace(0, np.nan)
    x["close_loc_me2"] = (x["Close"] - x["Low"]) / rng
    x["deep3_me2"] = x["ret1_me2"] <= -0.03
    x["deep5_me2"] = x["ret1_me2"] <= -0.05
    x["up1_me2"] = x["ret1_me2"] > 0

    def agg_day(z: pd.DataFrame) -> pd.Series:
        r1 = z["ret1_me2"].dropna()
        return pd.Series({
            "n_market": int(r1.size),
            "breadth1": float(z["up1_me2"].mean()),
            "above20": float(z["above_ma20"].mean()) if "above_ma20" in z.columns else np.nan,
            "med_ret1": float(z["ret1_me2"].median()),
            "med_ret3": float(z["ret3"].median()),
            "med_gap": float(z["gap"].median()),
            "med_body": float(z["body_me2"].median()),
            "med_close_loc": float(z["close_loc_me2"].median()),
            "disp1": float(r1.std(ddof=0)) if len(r1) else np.nan,
            "deep3_frac": float(z["deep3_me2"].mean()),
            "deep5_frac": float(z["deep5_me2"].mean()),
        })

    d = x.groupby("Date", sort=True).apply(agg_day).reset_index().sort_values("Date").reset_index(drop=True)
    for c in ["breadth1", "above20", "med_ret1", "med_ret3", "med_gap", "med_body", "med_close_loc", "disp1", "deep3_frac", "deep5_frac"]:
        d[f"lag1_{c}"] = d[c].shift(1)
        d[f"d1_{c}"] = d[c] - d[c].shift(1)
    return x, d


def gate_masks(date_state: pd.DataFrame) -> dict[str, pd.Series]:
    d = date_state
    # Deliberately small, preordered set of natural-boundary hypotheses.
    # No percentile/threshold scan is allowed in ME2 discovery.
    return {
        "G1_SELLING_CLIMAX_REJECTION": (d["med_gap"] < 0) & (d["med_body"] > 0),
        "G2_PANIC_REJECTION": (d["breadth1"] <= 0.50) & (d["med_gap"] < 0) & (d["med_body"] > 0),
        "G3_PANIC_INTENSITY": d["breadth1"] <= 0.50,
        "G4_PRIOR_PANIC_BREADTH_RECOVERY": (d["lag1_breadth1"] <= 0.50) & (d["d1_breadth1"] > 0),
        "G5_NEG_GAP_UPPER_HALF_CLOSE": (d["med_gap"] < 0) & (d["med_close_loc"] >= 0.50),
    }


def run_with_cost(fixed, panel: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, label: str, cost: float):
    old = fixed.COST
    try:
        fixed.COST = float(cost)
        return fixed.simulate(panel, start, end, label)
    finally:
        fixed.COST = old


def panel_for_gate(panel: pd.DataFrame, eligible_dates: set[pd.Timestamp]) -> pd.DataFrame:
    y = panel.copy()
    y["signal"] = y["signal"] & y["Date"].isin(eligible_dates)
    return y


def monthly_quality(summary: dict) -> dict:
    rows = summary.get("monthly_by_signal_date", []) or []
    active = [r for r in rows if int(r.get("count", 0)) > 0]
    positive = [r for r in active if float(r.get("sum", 0.0)) > 0]
    return {
        "active_months": len(active),
        "positive_months": len(positive),
        "monthly": active,
    }


def gate_pass(summary40: dict, summary100: dict, baseline40: dict) -> tuple[bool, list[str]]:
    reasons = []
    days = int(summary40.get("unique_signal_dates", 0))
    trades = int(summary40.get("selected_roundlot_trades", 0))
    pnl = float(summary40.get("total_pnl", 0.0))
    pf = summary40.get("profit_factor")
    remove3 = float(summary40.get("remove_best_3_signal_dates_pnl", -math.inf))
    mdd = float(summary40.get("max_drawdown_pct", -math.inf))
    pnl100 = float(summary100.get("total_pnl", 0.0))
    pf100 = summary100.get("profit_factor")
    mq = monthly_quality(summary40)

    # Discovery governance fixed before reading the result:
    # retain >= half of 14 baseline days; not merely the top 3;
    # positive economics, PF >= 1.5, no worse MDD than baseline;
    # remove-top3-days stays positive; survives 100bp; spans >=3 months
    # with at most one negative active month.
    checks = [
        (days >= 7, f"signal_days {days} >= 7"),
        (trades >= 15, f"trades {trades} >= 15"),
        (pnl > 0, f"40bp pnl {pnl:.2f} > 0"),
        (pf is not None and float(pf) >= 1.50, f"40bp PF {pf} >= 1.50"),
        (remove3 > 0, f"remove-top3-day pnl {remove3:.2f} > 0"),
        (mdd >= float(baseline40["max_drawdown_pct"]) - 1e-12, f"MDD {mdd:.6f} no worse than baseline {baseline40['max_drawdown_pct']:.6f}"),
        (pnl100 > 0, f"100bp pnl {pnl100:.2f} > 0"),
        (pf100 is not None and float(pf100) > 1.0, f"100bp PF {pf100} > 1"),
        (mq["active_months"] >= 3, f"active_months {mq['active_months']} >= 3"),
        (mq["positive_months"] >= max(0, mq["active_months"] - 1), f"positive_months {mq['positive_months']} >= active_months-1"),
    ]
    for ok, desc in checks:
        reasons.append(("PASS: " if ok else "FAIL: ") + desc)
    return all(ok for ok, _ in checks), reasons


def forensic_ledger(trades: pd.DataFrame, date_state: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    g = trades.groupby("signal_date").agg(
        trades=("pnl", "size"),
        pnl=("pnl", "sum"),
        mean_trade_pnl=("pnl", "mean"),
        win_rate=("pnl", lambda s: float((s > 0).mean())),
        gross_notional=("entry_notional", "sum"),
    ).reset_index().rename(columns={"signal_date": "Date"})
    g = g.sort_values("pnl", ascending=False).reset_index(drop=True)
    g["pnl_rank_desc"] = np.arange(1, len(g) + 1)
    g["forensic_tier"] = "MIDDLE"
    g.loc[g["pnl_rank_desc"] <= 3, "forensic_tier"] = "TOP3"
    g.loc[g["pnl_rank_desc"] > max(0, len(g) - 3), "forensic_tier"] = "BOTTOM3"
    return g.merge(date_state, on="Date", how="left").sort_values("pnl", ascending=False)


def compact(summary: dict) -> dict:
    keep = [
        "raw_signals", "selected_roundlot_trades", "skipped_zero_lot",
        "unique_signal_dates", "total_pnl", "win_rate", "profit_factor",
        "max_drawdown_amount", "max_drawdown_pct", "max_concurrent_positions",
        "remove_best_trade_pnl", "remove_top2_trades_pnl",
        "remove_best_signal_date_pnl", "remove_best_3_signal_dates_pnl",
        "monthly_by_signal_date",
    ]
    return {k: summary.get(k) for k in keep}


def main():
    fixed = load_fixed_module()
    base = fixed.load_base_module()
    y26 = base.load_2026()
    hist, inventory = base.load_history()
    panel = base.build_panel(hist, y26)
    panel, date_state = add_date_state(panel)

    # ---- exact baseline reproduction gate ----
    t3, d3, s3 = run_with_cost(fixed, panel, RECENT_START, RECENT_END, "ME2_BASELINE_3M", 0.004)
    errs = []
    if int(s3.get("selected_roundlot_trades", -1)) != BASELINE_EXPECTED["trades"]:
        errs.append(f"trades={s3.get('selected_roundlot_trades')}")
    if int(s3.get("unique_signal_dates", -1)) != BASELINE_EXPECTED["signal_days"]:
        errs.append(f"days={s3.get('unique_signal_dates')}")
    if abs(float(s3.get("total_pnl", -1e99)) - BASELINE_EXPECTED["pnl"]) > 10.0:
        errs.append(f"pnl={s3.get('total_pnl')}")
    if s3.get("profit_factor") is None or abs(float(s3["profit_factor"]) - BASELINE_EXPECTED["pf"]) > 0.02:
        errs.append(f"pf={s3.get('profit_factor')}")
    if errs:
        raise RuntimeError("ME2 baseline mismatch; abort before date-gate research: " + "; ".join(errs))

    ledger = forensic_ledger(t3, date_state)
    ledger.to_csv(OUT / "ME2_14_SIGNAL_DAY_FORENSIC.csv", index=False)

    masks = gate_masks(date_state)
    comparisons = []
    details = {}
    frozen_gate = None

    for gate_name, mask in masks.items():
        eligible = set(pd.to_datetime(date_state.loc[mask, "Date"]))
        pg = panel_for_gate(panel, eligible)
        tg40, dg40, sg40 = run_with_cost(fixed, pg, RECENT_START, RECENT_END, gate_name + "_3M_40BP", 0.004)
        tg100, dg100, sg100 = run_with_cost(fixed, pg, RECENT_START, RECENT_END, gate_name + "_3M_100BP", 0.010)
        passed, reasons = gate_pass(sg40, sg100, s3)
        details[gate_name] = {
            "definition": {
                "G1_SELLING_CLIMAX_REJECTION": "market median gap < 0 AND market median body > 0",
                "G2_PANIC_REJECTION": "breadth1 <= 0.50 AND market median gap < 0 AND market median body > 0",
                "G3_PANIC_INTENSITY": "breadth1 <= 0.50",
                "G4_PRIOR_PANIC_BREADTH_RECOVERY": "prior-day breadth1 <= 0.50 AND breadth1 improves vs prior day",
                "G5_NEG_GAP_UPPER_HALF_CLOSE": "market median gap < 0 AND market median close-location >= 0.50",
            }[gate_name],
            "recent_3m_40bp": compact(sg40),
            "recent_3m_100bp": compact(sg100),
            "pass": bool(passed),
            "pass_reasons": reasons,
        }
        comparisons.append({
            "gate": gate_name,
            "pass": bool(passed),
            "days": sg40.get("unique_signal_dates"),
            "trades": sg40.get("selected_roundlot_trades"),
            "pnl40": sg40.get("total_pnl"),
            "pf40": sg40.get("profit_factor"),
            "mdd_pct40": sg40.get("max_drawdown_pct"),
            "remove_top3_day_pnl40": sg40.get("remove_best_3_signal_dates_pnl"),
            "pnl100": sg100.get("total_pnl"),
            "pf100": sg100.get("profit_factor"),
            "active_months": monthly_quality(sg40)["active_months"],
            "positive_months": monthly_quality(sg40)["positive_months"],
        })
        if frozen_gate is None and passed:
            frozen_gate = gate_name

    cmpdf = pd.DataFrame(comparisons)
    cmpdf.to_csv(OUT / "ME2_NATURAL_GATE_COMPARISON_3M.csv", index=False)

    result = {
        "governance": {
            "stock_selector": "FROZEN / UNCHANGED",
            "discovery_window": [str(RECENT_START.date()), str(RECENT_END.date())],
            "date_gate_search": "five predeclared natural-boundary mechanisms only; no threshold sweep; first passing gate in fixed order is frozen",
            "fixed_order": list(masks.keys()),
            "promotion_rule": "3M pass first; only then run frozen unchanged gate on 1Y",
        },
        "baseline_reproduction": {
            "status": "PASS",
            "recent_3m_40bp": compact(s3),
        },
        "forensic_tier_means": ledger.groupby("forensic_tier").agg(
            days=("Date", "size"),
            pnl=("pnl", "sum"),
            breadth1=("breadth1", "mean"),
            med_ret1=("med_ret1", "mean"),
            med_gap=("med_gap", "mean"),
            med_body=("med_body", "mean"),
            med_close_loc=("med_close_loc", "mean"),
            disp1=("disp1", "mean"),
            deep3_frac=("deep3_frac", "mean"),
        ).reset_index().to_dict(orient="records"),
        "gate_tests": details,
        "frozen_gate": frozen_gate,
        "recent_3m_decision": "SURVIVE_FREEZE" if frozen_gate else "NO_SURVIVOR_KILL_ME2",
        "one_year": None,
        "historical_inventory": inventory,
    }

    if frozen_gate is not None:
        mask = masks[frozen_gate]
        eligible = set(pd.to_datetime(date_state.loc[mask, "Date"]))
        pg = panel_for_gate(panel, eligible)
        # baseline 1Y and frozen ME2 gate, unchanged after 3M selection
        tb1, db1, sb1 = run_with_cost(fixed, panel, YEAR_START, YEAR_END, "BASELINE_1Y_40BP", 0.004)
        ty40, dy40, sy40 = run_with_cost(fixed, pg, YEAR_START, YEAR_END, frozen_gate + "_1Y_40BP", 0.004)
        ty100, dy100, sy100 = run_with_cost(fixed, pg, YEAR_START, YEAR_END, frozen_gate + "_1Y_100BP", 0.010)
        one_year_survive = (
            float(sy40.get("total_pnl", 0.0)) > 0
            and sy40.get("profit_factor") is not None and float(sy40["profit_factor"]) > 1.0
            and float(sy40.get("remove_best_3_signal_dates_pnl", -math.inf)) > 0
            and float(sy100.get("total_pnl", 0.0)) > 0
        )
        result["one_year"] = {
            "baseline_40bp": compact(sb1),
            "frozen_gate_40bp": compact(sy40),
            "frozen_gate_100bp": compact(sy100),
            "decision": "SURVIVE" if one_year_survive else "KILL",
            "rule_was_unchanged_after_3m": True,
        }
        ty40.to_csv(OUT / "ME2_FROZEN_GATE_TRADES_1Y.csv", index=False)
        dy40.to_csv(OUT / "ME2_FROZEN_GATE_EQUITY_1Y.csv", index=False)

    with open(OUT / "RESULT.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=True)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=True))


if __name__ == "__main__":
    main()
