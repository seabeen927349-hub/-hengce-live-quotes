#!/usr/bin/env python3
"""HENGCE v0.5 research candidate: RMS-only anti-false-stability ranking.
Read-only: never updates mother, strategy, or trade authority.
Use a local copy of Library HENGCE_2026_HIST_MOTHER.csv.
Historical episodes in this tool are selected ex-post, NOT a live crash detector.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import numpy as np
import pandas as pd

EVENTS = [
    ("2026-03-02", "2026-03-09", -8.5045),
    ("2026-06-03", "2026-06-10", -6.9601),
    ("2026-06-22", "2026-06-29", -5.7426),
    ("2026-07-13", "2026-07-20", -6.4583),
    ("2026-07-23", "2026-07-30", -10.9641),
    ("2026-10-07", "2026-10-15", -5.6951),
    ("2026-10-28", "2026-11-04", -8.6885),
]
KNOWN_SHA256 = "0245cef58e99e84effdc3d4af6d3a61f21e86ad0d5f69e05a6b6f251875ceaab"


def load(mother):
    if hashlib.sha256(mother.read_bytes()).hexdigest() != KNOWN_SHA256:
        raise RuntimeError("Mother snapshot does not match the 2026 replay; fail closed")
    d = pd.read_csv(mother, usecols=["Date", "Ticker", "Name", "Close", "Turnover"],
                    parse_dates=["Date"], dtype={"Ticker": str}, low_memory=False)
    d = d[d.Ticker.str.fullmatch(r"[1-9]\d{3}", na=False)].copy()
    d["Close"] = pd.to_numeric(d["Close"], errors="coerce")
    d["Turnover"] = pd.to_numeric(d["Turnover"], errors="coerce")
    d.loc[d.Close <= 0, "Close"] = np.nan
    if d.duplicated(["Date", "Ticker"]).any():
        raise RuntimeError("Duplicate symbol/date")
    return (d.pivot(index="Date", columns="Ticker", values="Close").sort_index(),
            d.pivot(index="Date", columns="Ticker", values="Turnover"))


def rank(cp, tv, asof):
    ix = cp.index.get_loc(pd.Timestamp(asof))
    if ix < 12:
        raise RuntimeError("Insufficient past observation dates")
    pre = cp.iloc[ix-8:ix+1]
    money = tv.reindex_like(cp).iloc[ix-8:ix+1]
    anchor = cp.iloc[ix-12]
    mask = (pre.notna().all() & anchor.notna() & money.notna().all()
            & money.ge(2_000_000).all() & money.mean().ge(20_000_000))
    eligible = mask.index[mask]
    daily = 100 * (pre[eligible].iloc[1:].to_numpy()
                   / pre[eligible].iloc[:-1].to_numpy() - 1)
    std = pd.Series(np.std(daily, axis=0), index=eligible)
    rms = pd.Series(np.sqrt(np.mean(daily ** 2, axis=0)), index=eligible)
    worst = pd.Series(np.min(daily, axis=0), index=eligible)
    trend = 100 * (pre[eligible].iloc[-1] / anchor[eligible] - 1)
    N = len(eligible)
    if N < 100:
        raise RuntimeError("Insufficient pre-event eligible symbols")
    pct = lambda s: 100 * (s.rank(method="average") - 1) / (N-1)
    result = pd.DataFrame({"ticker": eligible, "std_pct": std,
                           "rms_pct": rms, "worst_pct": worst, "trend_pct": trend})
    result = result.set_index("ticker")
    # v0.4 unchanged, only for audit
    result["v04"] = .5 * (100-pct(std)) + .3*pct(worst) + .2*pct(trend)
    # v0.5 correction: magnitude of returns, not variation around their mean
    result["v05"] = 100 - pct(rms)
    return result


def selected(cp, tv, asof, end, mkt):
    scores = rank(cp, tv, asof)
    scores["ticker"] = scores.index
    old = scores.sort_values(["v04", "ticker"], ascending=[False, True])
    new = scores.sort_values(["v05", "ticker"], ascending=[False, True])
    outcome = 100 * (cp.loc[pd.Timestamp(end)] / cp.loc[pd.Timestamp(asof)] - 1)
    def topn(f, n):
        sel = f.head(n)
        returns = outcome.reindex(sel.index)
        if returns.isna().any():
            raise RuntimeError(f"Missing forward close in Top {n} for {asof}: "
                               + ",".join(returns.index[returns.isna()]))
        return {"tickers": sel.index.tolist(), "mean_pct": float(returns.mean()),
                "beat_index": bool(returns.mean() > mkt)}
    return {"asof": asof, "end": end, "taiex": mkt, "eligible": len(scores),
            "v04": {str(n): topn(old, n) for n in range(1, 6)},
            "v05": {str(n): topn(new, n) for n in range(1, 6)}}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mother", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    cp, tv = load(args.mother)
    episodes = [selected(cp, tv, *case) for case in EVENTS]
    summary = {}
    for model in ("v04", "v05"):
        summary[model] = {}
        for n in range(1,6):
            returns = [e[model][str(n)]["mean_pct"] for e in episodes]
            summary[model][str(n)] = {
                "seven_event_mean_pct": float(np.mean(returns)),
                "seven_event_beat_market_count":
                    int(sum(e[model][str(n)]["beat_index"] for e in episodes))}
    june = rank(cp, tv, "2026-06-03")
    assert june.loc["3021", "v04"] > 99.9
    assert june.loc["3021", "v05"] < 1
    assert june.loc["6116", "v05"] < 1
    out = {"system": "HENGCE", "model": "RESILIENCE_RMS_V05_RESEARCH",
           "status": "RESEARCH_ONLY_NO_TRADING_AUTHORITY",
           "source_sha256": KNOWN_SHA256, "episodes": episodes, "summary": summary,
           "june_false_stability_corrected": {
               t: {"v04": float(june.loc[t, "v04"]),
                   "v05": float(june.loc[t, "v05"])} for t in ["3021", "6116"]},
           "limitations": ["ex-post event selection and model revision informed by 2026",
                           "no independent next-year validation; cannot forecast crashes",
                           "raw closes not total return, no fees or industry controls"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n", encoding="utf8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
