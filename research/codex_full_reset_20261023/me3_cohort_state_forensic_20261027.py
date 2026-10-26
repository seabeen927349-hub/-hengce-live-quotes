from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FIXED_PATH = Path(__file__).with_name("frozen_fixed_capital_roundlot_20261026.py")
OUT = ROOT / "research/codex_full_reset_20261023/results/me3_cohort_state_forensic_20261027"
OUT.mkdir(parents=True, exist_ok=True)
START = pd.Timestamp("2026-07-22")
END = pd.Timestamp("2026-10-21")


def load_mod(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def med(z, col):
    s = pd.to_numeric(z[col], errors="coerce").dropna()
    return float(s.median()) if len(s) else np.nan


def mean(z, col):
    s = pd.to_numeric(z[col], errors="coerce").dropna()
    return float(s.mean()) if len(s) else np.nan


def main():
    fixed = load_mod(FIXED_PATH, "fixed")
    base = fixed.load_base_module()
    y26 = base.load_2026()
    hist, inv = base.load_history()
    p = base.build_panel(hist, y26).sort_values(["Ticker", "Date"]).reset_index(drop=True)
    g = p.groupby("Ticker", group_keys=False)
    p["ret1_c"] = p["Close"] / p["prev_close"] - 1
    p["body_c"] = p["Close"] / p["Open"] - 1
    rng = (p["High"] - p["Low"]).replace(0, np.nan)
    p["close_loc_c"] = (p["Close"] - p["Low"]) / rng
    if "Volume" in p.columns:
        p["vol20avg_c"] = g["Volume"].transform(lambda s: pd.to_numeric(s, errors="coerce").rolling(20, min_periods=20).mean())
        p["vol_ratio_c"] = pd.to_numeric(p["Volume"], errors="coerce") / p["vol20avg_c"]
    else:
        p["vol_ratio_c"] = np.nan

    # Exact executable baseline: same validator as frozen candidate.
    trades, eq, summ = fixed.simulate(p, START, END, "ME3_BASELINE")
    assert int(summ["selected_roundlot_trades"]) == 39
    assert int(summ["unique_signal_dates"]) == 14
    assert abs(float(summ["total_pnl"]) - 92555.8) < 10

    rows = []
    for dt, z in p.groupby("Date", sort=True):
        market = z[z["ret3"].notna()]
        b = z[z["base_candidate"]]
        s = z[z["signal"]]
        n = len(market)
        bc, sc = len(b), len(s)
        rows.append({
            "Date": pd.Timestamp(dt),
            "n_market": n,
            "base_count": bc,
            "signal_count": sc,
            "base_density": bc/n if n else np.nan,
            "signal_density": sc/n if n else np.nan,
            "signal_share_of_base": sc/bc if bc else np.nan,
            "base_med_ret1": med(b,"ret1_c"),
            "base_med_ret3": med(b,"ret3"),
            "base_med_gap": med(b,"gap"),
            "base_med_dist_ma10": med(b,"dist_ma10"),
            "base_med_lower_wick": med(b,"lower_wick"),
            "base_med_body": med(b,"body_c"),
            "base_med_close_loc": med(b,"close_loc_c"),
            "base_med_vol_ratio": med(b,"vol_ratio_c"),
            "base_mean_rank_severity": mean(b.assign(ranksev=(b["ret3_rank"]+b["gap_rank"]+b["dist_ma10_rank"])/3), "ranksev") if bc else np.nan,
            "signal_med_ret1": med(s,"ret1_c"),
            "signal_med_ret3": med(s,"ret3"),
            "signal_med_gap": med(s,"gap"),
            "signal_med_dist_ma10": med(s,"dist_ma10"),
            "signal_med_lower_wick": med(s,"lower_wick"),
            "signal_med_body": med(s,"body_c"),
            "signal_med_close_loc": med(s,"close_loc_c"),
            "signal_med_vol_ratio": med(s,"vol_ratio_c"),
            "breadth_ma20": float(z["breadth_ma20"].iloc[0]) if len(z) else np.nan,
        })
    d = pd.DataFrame(rows).sort_values("Date").reset_index(drop=True)
    # Causal density/state transitions; rolling reference excludes current day.
    for c in ["base_count","signal_count","base_density","signal_density","base_med_ret3","base_med_gap","base_med_dist_ma10","base_med_close_loc"]:
        d[f"lag1_{c}"] = d[c].shift(1)
        d[f"d1_{c}"] = d[c] - d[c].shift(1)
        d[f"prior20med_{c}"] = d[c].shift(1).rolling(20, min_periods=10).median()
        d[f"vs_prior20med_{c}"] = d[c] - d[f"prior20med_{c}"]

    daypnl = trades.groupby("signal_date").agg(
        executable_trades=("pnl","size"),
        pnl=("pnl","sum"),
        win_rate=("pnl",lambda s: float((s>0).mean())),
        gross_notional=("entry_notional","sum"),
    ).reset_index().rename(columns={"signal_date":"Date"})
    x = daypnl.merge(d, on="Date", how="left").sort_values("pnl", ascending=False).reset_index(drop=True)
    x["pnl_rank_desc"] = np.arange(1,len(x)+1)
    x["tier"] = "MIDDLE"
    x.loc[x["pnl_rank_desc"]<=3,"tier"] = "TOP3"
    x.loc[x["pnl_rank_desc"]>len(x)-3,"tier"] = "BOTTOM3"
    x.to_csv(OUT/"ME3_14_DAY_COHORT_FORENSIC.csv", index=False)

    feature_cols = [c for c in x.columns if c not in {"Date","pnl","tier","pnl_rank_desc","executable_trades","win_rate","gross_notional"} and pd.api.types.is_numeric_dtype(x[c])]
    cors=[]
    for c in feature_cols:
        q=x[[c,"pnl"]].dropna()
        if len(q)<7 or q[c].nunique()<3: continue
        rho=float(q[c].corr(q["pnl"], method="spearman"))
        q2=q.drop(index=x.nlargest(3,"pnl").index, errors="ignore")
        rho_ex=float(q2[c].corr(q2["pnl"], method="spearman")) if len(q2)>=7 and q2[c].nunique()>=3 else np.nan
        cors.append({"feature":c,"spearman_all14":rho,"spearman_ex_top3":rho_ex,"n":len(q)})
    cor=pd.DataFrame(cors)
    if len(cor):
        cor["same_sign"]=(np.sign(cor["spearman_all14"])==np.sign(cor["spearman_ex_top3"])) & cor["spearman_ex_top3"].notna()
        cor["min_abs_rho"]=cor[["spearman_all14","spearman_ex_top3"]].abs().min(axis=1)
        cor=cor.sort_values(["same_sign","min_abs_rho"], ascending=[False,False])
    cor.to_csv(OUT/"ME3_COHORT_FEATURE_RANK_CORRELATIONS.csv", index=False)

    tier = x.groupby("tier").agg(
        days=("Date","size"), pnl=("pnl","sum"),
        base_count=("base_count","mean"), base_density=("base_density","mean"),
        signal_count=("signal_count","mean"),
        base_med_ret1=("base_med_ret1","mean"), base_med_ret3=("base_med_ret3","mean"),
        base_med_gap=("base_med_gap","mean"), base_med_dist_ma10=("base_med_dist_ma10","mean"),
        base_med_lower_wick=("base_med_lower_wick","mean"), base_med_close_loc=("base_med_close_loc","mean"),
        d1_base_density=("d1_base_density","mean"), vs_prior20med_base_density=("vs_prior20med_base_density","mean")
    ).reset_index()
    tier.to_csv(OUT/"ME3_TIER_SUMMARY.csv", index=False)

    result={
        "status":"FORENSIC_ONLY_NO_GATE_TUNING_YET",
        "stock_selector":"FROZEN_UNCHANGED",
        "baseline":{"trades":int(summ["selected_roundlot_trades"]),"days":int(summ["unique_signal_dates"]),"pnl":float(summ["total_pnl"]),"pf":summ["profit_factor"]},
        "tier_summary":tier.to_dict(orient="records"),
        "top_stable_correlations":cor.head(12).to_dict(orient="records") if len(cor) else [],
        "governance":"This pass is diagnostic only. No gate is selected from the same output until mechanism is stated explicitly; any ME3 gate must then start as a new frozen 3M challenger."
    }
    with open(OUT/"RESULT.json","w",encoding="utf-8") as f:
        json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=True)
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=True))

if __name__ == "__main__":
    main()
