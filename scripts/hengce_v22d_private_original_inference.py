#!/usr/bin/env python3
"""Read-only V2.2-D original-checkpoint daily research replay.

Sources: existing SHA-pinned historical price mother, G1 TDCC cohort and
2026 canonical mother supplied locally from private HENGCE Library.
No downloader, no training, no synthetic daily TDCC headcount, no orders.
The original model checkpoint is NEVER committed to this repository.
Historical TDCC first-publication dates are not fully PIT-certified, so even
a same-day run cannot promote this report to a formal selector.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import zipfile
from pathlib import Path
from zoneinfo import ZoneInfo

MODEL_HASH = "db47b6f2276150610972d50a8f2b1a9d816eb89fc415d41db5c81b12c1c94a97"
REG_HASH = "8e6931fa9b4ca4324db3b24feb47312bbcbdb9030388e00ab5e8f2e36b014c06"
PRICE_HASH = "b3275f8d58779fbec864a05066414d27e80cef8a68a76a08051f93808f1f8c93"
TDCC_HASH = "71083d73a791b6bf25770139c65e8d29012a44e31c39f66479806bf5a562bc88"
KNOWN_20261111_CANONICAL_HASH = "67cc7454094a884c4769d0fa5172bdfba175fc7b95182714a40ced3c42d28d5f"
FEATURES = [
    "weekday", "known_lag", "log_known", "last_known_delta",
    "prior_known_delta", "ret1", "ret5", "ret10", "ret20",
    "turnratio5_20", "margin10", "intradayrange", "logturn20",
    "thiswk_turnratio", "thiswkret", "netfrac",
]
PRICE_COLS = [
    "Date", "Ticker", "Open", "High", "Low", "Close", "Volume",
    "Turnover", "Margin_MarginBalance", "TotalNet",
]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_hash(path, wanted):
    found = digest(path)
    if found != wanted:
        raise ValueError("ORIGINAL_VESSEL_SHA_MISMATCH " + str(path.name) +
                         " actual=" + found)
    return found


def infer(base, tdcc, recent, checkpoint, decision_day,
          recent_sha256=KNOWN_20261111_CANONICAL_HASH):
    """Reproduce original features/LightGBM; never infer a live trading signal."""
    import numpy as np
    import pandas as pd
    import lightgbm as lgb

    decision = dt.date.fromisoformat(decision_day)
    if decision.weekday() > 3:
        raise ValueError("V22D_ONLY_MONDAY_THROUGH_THURSDAY")
    if decision > dt.datetime.now(ZoneInfo("Asia/Taipei")).date():
        raise ValueError("FUTURE_DECISION_DATE_FORBIDDEN")
    for path, wanted in ((base, PRICE_HASH), (tdcc, TDCC_HASH),
                         (recent, recent_sha256)):
        check_hash(path, wanted)
    if decision > dt.date(2026, 11, 11) and recent_sha256 == KNOWN_20261111_CANONICAL_HASH:
        raise ValueError("NEWER_CANONICAL_SHA_REQUIRED_FOR_LATER_DECISION")

    with zipfile.ZipFile(checkpoint) as archive:
        def load(name, expected):
            raw = archive.read(name)
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("ORIGINAL_V22D_MODEL_CHECKPOINT_SHA_MISMATCH")
            return lgb.Booster(model_str=raw.decode("utf-8"))
        classifier = load("V22D_original_2019_2022_classifier.txt", MODEL_HASH)
        regressor = load("V22D_original_2019_2022_regressor.txt", REG_HASH)

    cols = ["SnapshotDate", "Ticker", "HolderLe10Lots",
            "RetailPeopleValid", "Big400Pct", "TierStatus"]
    w = pd.read_csv(tdcc, usecols=cols,
                    dtype={"Ticker": str, "SnapshotDate": str}, low_memory=False)
    w["SnapshotDate"] = pd.to_datetime(w.SnapshotDate, format="%Y%m%d", errors="coerce")
    first = (w[(w.SnapshotDate.dt.year == 2018) & w.TierStatus.eq("VALID")]
             .sort_values(["Ticker", "SnapshotDate"])
             .groupby("Ticker").first())
    cohort = set(first[first.Big400Pct >= 50].index)
    if len(cohort) != 781:
        raise ValueError("FIXED_2018_781_COHORT_MISMATCH")
    w = w[w.Ticker.isin(cohort)].copy()
    w["N"] = pd.to_numeric(w.HolderLe10Lots, errors="coerce").where(
        w.RetailPeopleValid.astype(str).str.lower().isin(["true", "1"]))
    w = (w.sort_values(["Ticker", "SnapshotDate"])
         .drop_duplicates(["Ticker", "SnapshotDate"]).reset_index(drop=True))
    g = w.groupby("Ticker", sort=False)
    for i in (1, 2):
        w["Nlag" + str(i)] = g.N.shift(i)
    w = (w[["Ticker", "SnapshotDate", "N", "Nlag1", "Nlag2"]]
         .rename(columns={"SnapshotDate": "known_date", "N": "known0",
                          "Nlag1": "known1", "Nlag2": "known2"})
         .sort_values(["known_date", "Ticker"]))

    now = pd.Timestamp(decision)
    start = now - pd.Timedelta(days=100)
    def price_chunks(path, after=None):
        for ch in pd.read_csv(
                path, usecols=PRICE_COLS, dtype={"Ticker": str},
                parse_dates=["Date"], low_memory=False,
                na_values=["--", "---", "-"], chunksize=75000):
            keep = (ch.Date >= start) & (ch.Date <= now) & ch.Ticker.isin(cohort)
            if after is not None:
                keep &= ch.Date > after
            part = ch.loc[keep]
            if len(part):
                yield part
    parts = list(price_chunks(base))
    parts.extend(price_chunks(recent, after=pd.Timestamp("2026-11-06")))
    if not parts:
        raise ValueError("NO_PRICE_HISTORY_FROM_EXISTING_VESSELS")
    p = (pd.concat(parts, ignore_index=True)
         .sort_values(["Ticker", "Date"])
         .drop_duplicates(["Ticker", "Date"])
         .reset_index(drop=True))
    if p.Date.max().date() != decision:
        raise ValueError("DECISION_EOD_NOT_IN_ORIGINAL_MOTHER")
    for col in PRICE_COLS[2:]:
        p[col] = pd.to_numeric(p[col], errors="coerce").astype("float32")
    p["wfriday"] = p.Date.dt.to_period("W-FRI").dt.end_time.dt.normalize()
    p["weekday"] = p.Date.dt.weekday.astype("int8")
    g = p.groupby("Ticker", sort=False)
    for k in (1, 5, 10, 20):
        p["ret" + str(k)] = (p.Close / g.Close.shift(k) - 1).clip(-.90, 3).astype("float32")
    for k in (5, 20):
        p["volmean" + str(k)] = g.Volume.transform(
            lambda s: s.rolling(k, min_periods=k).mean()).astype("float32")
        p["turnmed" + str(k)] = g.Turnover.transform(
            lambda s: s.rolling(k, min_periods=k).median()).astype("float32")
    p["turnratio5_20"] = (p.volmean5 / p.volmean20.replace(0, np.nan)).clip(0, 50).astype("float32")
    p["margin10"] = (p.Margin_MarginBalance / g.Margin_MarginBalance.shift(10) - 1).replace(
        [np.inf, -np.inf], np.nan).clip(-1, 3).astype("float32")
    p["intradayrange"] = (p.High / p.Low.replace(0, np.nan) - 1).clip(0, 1).astype("float32")
    p["logturn20"] = np.log1p(p.turnmed20.clip(lower=0)).astype("float32")
    gw = p.groupby(["Ticker", "wfriday"], sort=False)
    p["week_days"] = (gw.cumcount() + 1).astype("int8")
    p["thiswk_turnavg"] = (p.Turnover.fillna(0).groupby(
        [p.Ticker, p.wfriday], sort=False).cumsum() / p.week_days).astype("float32")
    p["thiswk_turnratio"] = (p.thiswk_turnavg / p.turnmed20.replace(0, np.nan)).clip(0, 50).astype("float32")
    lastwk = gw.Close.last().rename("weekclose").reset_index().sort_values(["Ticker", "wfriday"])
    lastwk["prev_week_close"] = lastwk.groupby("Ticker").weekclose.shift(1)
    p = p.merge(lastwk[["Ticker", "wfriday", "prev_week_close"]],
                on=["Ticker", "wfriday"], how="left", validate="many_to_one")
    p["thiswkret"] = (p.Close / p.prev_week_close - 1).clip(-.9, 3).astype("float32")
    p["thiswknet"] = p.TotalNet.fillna(0).groupby(
        [p.Ticker, p.wfriday], sort=False).cumsum()
    p["thiswkvol"] = p.Volume.fillna(0).groupby(
        [p.Ticker, p.wfriday], sort=False).cumsum()
    p["netfrac"] = (p.thiswknet / p.thiswkvol.replace(0, np.nan)).clip(-10, 10).astype("float32")
    p["valid_close"] = p.Close.where(p.Volume.gt(0))
    logclose = np.log(p.valid_close.where(p.valid_close.gt(0)))
    p["volatility20"] = logclose.groupby(p.Ticker).diff().groupby(
        p.Ticker).transform(lambda s: s.rolling(20, min_periods=20).std()).astype("float32")
    d = p[p.Date.eq(now)].copy()
    d["cutoff"] = d.Date - pd.Timedelta(days=14)
    d = d.sort_values(["cutoff", "Ticker"])
    d = pd.merge_asof(d, w, left_on="cutoff", right_on="known_date",
                      by="Ticker", direction="backward", allow_exact_matches=True)
    d["last_age"] = (d.cutoff - d.known_date).dt.days
    d["known_lag"] = ((d.wfriday - d.known_date).dt.days / 7).round().astype("float32")
    d["log_known"] = np.log1p(d.known0).astype("float32")
    d["last_known_delta"] = (d.known0 / d.known1 - 1).clip(-.5, .5).astype("float32")
    d["prior_known_delta"] = (d.known1 / d.known2 - 1).clip(-.5, .5).astype("float32")
    d = d[d.known0.gt(0) & d.known1.gt(0) & d.known2.gt(0) &
          d.last_age.between(0, 7) & d.known_lag.between(1, 5)].copy()
    for col in FEATURES:
        d[col] = d[col].replace([np.inf, -np.inf], np.nan)
    d["score"] = classifier.predict(d[FEATURES]).astype("float32")
    d["estimated_weekend_holders"] = (
        d.known0 * np.exp(np.clip(regressor.predict(d[FEATURES]), -.7, .7))
    ).clip(lower=0).astype("float32")
    d["eligible"] = (d.ret20.ge(.05) & d.ret5.ge(0) &
                     d.turnmed20.ge(1e7) & d.volatility20.gt(0) &
                     d.valid_close.gt(0) & d.score.ge(.50))
    eligible = d[d.eligible].sort_values(
        ["turnmed20", "Ticker"], ascending=[False, True])
    rows = eligible[["Ticker", "score", "ret20", "ret5", "turnmed20",
                     "known_date", "known0", "estimated_weekend_holders", "Close"]].head(5).copy()
    rows["known_date"] = rows.known_date.dt.strftime("%Y-%m-%d")
    top = []
    for rank, row in enumerate(rows.to_dict("records"), 1):
        top.append({"rank": rank, "ticker": row["Ticker"],
                    "daily_decline_score": float(row["score"]),
                    "return_20d": float(row["ret20"]), "return_5d": float(row["ret5"]),
                    "median_20d_turnover_twd": float(row["turnmed20"]),
                    "last_assumed_available_tdcc_date": row["known_date"],
                    "last_known_le10_holder_count": float(row["known0"]),
                    "estimated_week_end_le10_holder_count": float(row["estimated_weekend_holders"]),
                    "last_verified_close": float(row["Close"])})
    generated = dt.datetime.now(ZoneInfo("Asia/Taipei"))
    result = {
        "schema": "HENGCE_V22D_PRIVATE_ORIGINAL_CHECKPOINT_REPLAY_V1",
        "system": "HENGCE", "model_id": "v22d_daily_nowcast_liquidity_top5_v1",
        "status": "RESEARCH_REPLAY_NOT_PIT_CERTIFIED",
        "decision_date": decision.isoformat(), "generated_at_taipei": generated.isoformat(),
        "fixed_cohort_count": 781, "feature_coverage": len(d),
        "qualified_count": len(eligible), "top5": top,
        "last_assumed_tdcc_snapshot": d.known_date.max().strftime("%Y-%m-%d") if len(d) else None,
        "source_sha256": {"original_prices": PRICE_HASH, "original_tdcc": TDCC_HASH,
                          "original_2026_canonical": recent_sha256, "classifier": MODEL_HASH,
                          "regressor": REG_HASH},
        "historical_tdcc_first_observed_pit_certified": False,
        "current_selection": False, "retrospective_only": True,
        "prediction_is_real_daily_retail_count": False,
        "score_is_calibrated_probability": False, "trading_authority": False,
        "formal_selection_authority": False, "buy_signal": False, "sell_signal": False,
        "broker_execution": False, "capital_authority_twd": 0,
        "authorized_lots": 0,
    }
    result["receipt_sha256"] = hashlib.sha256(
        json.dumps(result, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode("utf-8")).hexdigest()
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-price-mother", type=Path, required=True)
    p.add_argument("--original-tdcc-mother", type=Path, required=True)
    p.add_argument("--original-2026-canonical", type=Path, required=True)
    p.add_argument("--private-original-model", type=Path, required=True)
    p.add_argument("--decision-date", required=True)
    p.add_argument("--canonical-sha256", default=KNOWN_20261111_CANONICAL_HASH)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    result = infer(args.original_price_mother, args.original_tdcc_mother,
                   args.original_2026_canonical, args.private_original_model,
                   args.decision_date, args.canonical_sha256)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
                        + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"],
                      "date": result["decision_date"],
                      "qualified": result["qualified_count"],
                      "top5": [r["ticker"] for r in result["top5"]]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
