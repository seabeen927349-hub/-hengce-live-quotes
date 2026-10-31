#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import pathlib
import statistics
import time
import urllib.request
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

FACTORS = ["resid_rev", "mom20", "skip5_60", "liquidity", "lowvol"]
LEGACY_TURN_MIN = 20_000_000.0
LEGACY_JUMP = 0.15
V43_CORR_FAIL = 0.90
LEGACY_R2_FAIL = 0.80
K = 5


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fnum(x):
    if x is None:
        return None
    s = str(x).strip().replace(",", "")
    if s in ("", "--", "---", "-"):
        return None
    try:
        v = float(s)
        return v if math.isfinite(v) else None
    except Exception:
        return None


def clean_label(x: str) -> str:
    return "".join(str(x).replace("\u3000", " ").split())


def json_tables(obj):
    for key, fields in obj.items():
        if not key.startswith("fields") or not isinstance(fields, list):
            continue
        suffix = key[len("fields"):]
        data = obj.get("data" + suffix)
        if isinstance(data, list):
            yield fields, data, key, "data" + suffix


def locate_table(obj, ticker_terms, value_predicate):
    hits = []
    for fields, data, fk, dk in json_tables(obj):
        labels = [clean_label(x) for x in fields]
        ti = next((i for i, x in enumerate(labels) if any(term in x for term in ticker_terms)), None)
        vi = next((i for i, x in enumerate(labels) if value_predicate(x)), None)
        if ti is not None and vi is not None:
            hits.append((fields, data, ti, vi, fk, dk, labels[vi]))
    if len(hits) != 1:
        raise RuntimeError(f"expected exactly one matching table, got {len(hits)}")
    return hits[0]


def parse_t86_obj(obj):
    fields, data, ti, vi, fk, dk, vlabel = locate_table(
        obj,
        ticker_terms=("證券代號", "股票代號"),
        value_predicate=lambda x: "三大法人買賣超股數" in x,
    )
    out = {}
    for row in data:
        if not isinstance(row, list) or max(ti, vi) >= len(row):
            continue
        t = str(row[ti]).strip()
        if len(t) == 4 and t.isdigit():
            v = fnum(row[vi])
            if v is not None:
                out[t] = v
    return out, {"fields_key": fk, "data_key": dk, "value_field": vlabel, "rows": len(out)}


def parse_margin_obj(obj):
    fields, data, ti, vi, fk, dk, vlabel = locate_table(
        obj,
        ticker_terms=("股票代號", "證券代號"),
        value_predicate=lambda x: ("融資" in x and "今日餘額" in x),
    )
    out = {}
    for row in data:
        if not isinstance(row, list) or max(ti, vi) >= len(row):
            continue
        t = str(row[ti]).strip()
        if len(t) == 4 and t.isdigit():
            v = fnum(row[vi])
            if v is not None and v >= 0:
                out[t] = v
    return out, {"fields_key": fk, "data_key": dk, "value_field": vlabel, "rows": len(out)}


def fetch_json(url: str, retries=5, timeout=30):
    headers = {
        "User-Agent": "Mozilla/5.0 HENGCE-Repricing-State-NoForward/1.0",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.twse.com.tw/",
    }
    err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            obj = json.loads(raw.decode("utf-8-sig"))
            if str(obj.get("stat", "")) != "OK":
                raise RuntimeError(f"TWSE stat={obj.get('stat')}")
            return raw, obj
        except Exception as e:
            err = repr(e)
            time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"fetch failed {url}: {err}")


def fetch_t86_for_date(d: str, cache_dir: pathlib.Path):
    ds = d.replace("-", "")
    p = cache_dir / f"T86_{ds}.json"
    url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={ds}&selectType=ALLBUT0999&response=json"
    if p.exists():
        raw = p.read_bytes()
        obj = json.loads(raw.decode("utf-8-sig"))
    else:
        raw, obj = fetch_json(url)
        p.write_bytes(raw)
    rows, schema = parse_t86_obj(obj)
    return d, rows, schema, url, len(raw), hashlib.sha256(raw).hexdigest()


def load_t86(dates, cache_dir: pathlib.Path, workers=4):
    cache_dir.mkdir(parents=True, exist_ok=True)
    by = {}
    manifest = []
    failures = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch_t86_for_date, d, cache_dir): d for d in dates}
        done = 0
        for fut in as_completed(futs):
            d = futs[fut]
            try:
                dd, rows, schema, url, nbytes, sh = fut.result()
                by[dd] = rows
                manifest.append({"date": dd, "rows": len(rows), "url": url, "bytes": nbytes, "sha256": sh, **schema})
            except Exception as e:
                failures.append({"date": d, "error": repr(e)})
            done += 1
            if done % 50 == 0 or done == len(dates):
                print(f"T86 progress {done}/{len(dates)} failures={len(failures)}", flush=True)
    manifest.sort(key=lambda x: x["date"])
    if failures:
        raise RuntimeError(f"T86 failures: {failures[:10]} total={len(failures)}")
    if set(by) != set(dates):
        raise RuntimeError("T86 date coverage mismatch")
    return by, manifest


def load_margin(root: pathlib.Path):
    paths = sorted(root.rglob("MI_MARGN_*.json"))
    by = {}
    manifest = []
    for p in paths:
        stem = p.stem
        ds = stem.split("_")[-1]
        if len(ds) != 8 or not ds.isdigit():
            continue
        d = f"{ds[:4]}-{ds[4:6]}-{ds[6:]}"
        raw = p.read_bytes()
        obj = json.loads(raw.decode("utf-8-sig"))
        rows, schema = parse_margin_obj(obj)
        if d in by:
            raise RuntimeError(f"duplicate margin date {d}")
        by[d] = rows
        manifest.append({"date": d, "rows": len(rows), "path": str(p), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), **schema})
    manifest.sort(key=lambda x: x["date"])
    return by, manifest


def pct_rank_legacy(vals: dict[str, float]):
    a = sorted(vals.items(), key=lambda kv: (kv[1], kv[0]))
    n = len(a)
    if n <= 1:
        return {t: 0.5 for t, _ in a}
    out = {}
    i = 0
    while i < n:
        j = i + 1
        while j < n and a[j][1] == a[i][1]:
            j += 1
        pct = ((((i + 1) + j) / 2) - 1) / (n - 1)
        for k in range(i, j):
            out[a[k][0]] = pct
        i = j
    return out


def midrank_open(vals: dict[str, float]):
    a = sorted(vals.items(), key=lambda kv: (kv[1], kv[0]))
    n = len(a)
    out = {}
    i = 0
    while i < n:
        j = i + 1
        while j < n and a[j][1] == a[i][1]:
            j += 1
        average_rank_1based = ((i + 1) + j) / 2
        u = (average_rank_1based - 0.5) / n
        for k in range(i, j):
            out[a[k][0]] = u
        i = j
    return out


def rank_vector(values):
    s = pd.Series(values, dtype=float)
    return s.rank(method="average").to_numpy(dtype=float)


def same_date_spearman(df, x, y, min_n=5):
    rows = []
    for d, g in df[["Date", x, y]].dropna().groupby("Date"):
        if len(g) < min_n or g[x].nunique() < 2 or g[y].nunique() < 2:
            continue
        rho = spearmanr(g[x].to_numpy(), g[y].to_numpy()).statistic
        if rho is not None and math.isfinite(float(rho)):
            rows.append((d, float(rho), len(g)))
    return rows


def build_legacy_features(hist: pd.DataFrame):
    rows_by_date = defaultdict(dict)
    for x in hist.itertuples(index=False):
        rows_by_date[x.date][x.ticker] = {
            "close": float(x.close), "turn": float(x.turnover_ntd),
            "r1": None, "r5": None, "r20": None, "r60": None,
            "turn20": None, "vol20": None, "beta60": None, "resid5": None, "bad": False,
        }
    dates = sorted(rows_by_date)
    for i, d in enumerate(dates):
        if i == 0:
            continue
        pd_ = dates[i - 1]
        for t, r in rows_by_date[d].items():
            p = rows_by_date[pd_].get(t)
            if p and p["close"] > 0 and r["close"] > 0:
                z = r["close"] / p["close"] - 1
                r["bad"] = abs(z) > LEGACY_JUMP
                if not r["bad"]:
                    r["r1"] = z
    mkt = defaultdict(dict)
    for i, d in enumerate(dates):
        for t, r in rows_by_date[d].items():
            for h in (5, 20, 60):
                if i < h:
                    continue
                q = rows_by_date[dates[i - h]].get(t)
                if not q or q["close"] <= 0 or r["close"] <= 0:
                    continue
                ok = True
                for j in range(i - h + 1, i + 1):
                    z = rows_by_date[dates[j]].get(t)
                    if z is None or z["bad"]:
                        ok = False
                        break
                if ok:
                    r[f"r{h}"] = r["close"] / q["close"] - 1
            if i >= 19:
                zs = [rows_by_date[dates[j]].get(t) for j in range(i - 19, i + 1)]
                if all(z is not None and z["turn"] is not None and z["turn"] >= 0 for z in zs):
                    r["turn20"] = statistics.mean(z["turn"] for z in zs)
                if all(z is not None and z["r1"] is not None for z in zs):
                    vv = [z["r1"] for z in zs]
                    if len(set(vv)) > 1:
                        r["vol20"] = statistics.stdev(vv)
        for h in (1, 5):
            vals = [r[f"r{h}"] for r in rows_by_date[d].values() if r[f"r{h}"] is not None]
            if vals:
                mkt[d][f"r{h}"] = statistics.median(vals)
    hh = defaultdict(lambda: deque(maxlen=60))
    for d in dates:
        mr = mkt[d].get("r1")
        for t, r in rows_by_date[d].items():
            h = hh[t]
            if len(h) >= 30:
                xs = [x for x, y in h]
                ys = [y for x, y in h]
                xb, yb = statistics.mean(xs), statistics.mean(ys)
                den = sum((x - xb) ** 2 for x in xs)
                if den > 0:
                    r["beta60"] = sum((x - xb) * (y - yb) for x, y in h) / den
            if r["beta60"] is not None and r["r5"] is not None and mkt[d].get("r5") is not None:
                r["resid5"] = r["r5"] - r["beta60"] * mkt[d]["r5"]
            if mr is not None and r["r1"] is not None:
                h.append((mr, r["r1"]))
    features = {}
    for d in dates:
        elig = {t: r for t, r in rows_by_date[d].items()
                if r["resid5"] is not None and r["r20"] is not None and r["r60"] is not None and r["r5"] is not None
                and r["turn20"] is not None and r["vol20"] is not None and r["turn20"] >= LEGACY_TURN_MIN}
        if len(elig) < 10:
            continue
        rr = pct_rank_legacy({t: -r["resid5"] for t, r in elig.items()})
        m20 = pct_rank_legacy({t: r["r20"] for t, r in elig.items()})
        sk = pct_rank_legacy({t: r["r60"] - r["r5"] for t, r in elig.items()})
        liq = pct_rank_legacy({t: r["turn20"] for t, r in elig.items()})
        lv = pct_rank_legacy({t: -r["vol20"] for t, r in elig.items()})
        features[d] = {t: (rr[t], m20[t], sk[t], liq[t], lv[t]) for t in elig}
    return features, rows_by_date, dates


def load_taiex(path: pathlib.Path):
    df = pd.read_csv(path, dtype={"Date": str})
    dcol = "Date" if "Date" in df.columns else "date"
    ccol = "TAIEX_Close" if "TAIEX_Close" in df.columns else "Close"
    df = df[[dcol, ccol]].rename(columns={dcol: "Date", ccol: "Close"}).dropna()
    df["Date"] = df["Date"].astype(str)
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna().sort_values("Date").drop_duplicates("Date", keep=False)
    dates = df["Date"].tolist()
    closes = df["Close"].to_numpy(dtype=float)
    valid = set()
    for i in range(63, len(dates)):
        w = closes[i - 63:i + 1]
        if len(w) == 64 and np.isfinite(w).all() and (w > 0).all():
            rets = w[1:] / w[:-1] - 1
            if np.isfinite(rets).all():
                valid.add(dates[i])
    return valid, {"rows": len(df), "first": dates[0] if dates else None, "last": dates[-1] if dates else None, "sha256": sha256_file(path)}


def build_rs_panel(hist, t86_by, margin_by, taiex_valid, legacy_features, legacy_rows, dates):
    price = defaultdict(dict)
    for x in hist.itertuples(index=False):
        price[x.date][x.ticker] = {
            "close": float(x.close), "volume": float(x.volume_shares), "turn": float(x.turnover_ntd)
        }
    di = {d: i for i, d in enumerate(dates)}
    lt_raw = defaultdict(dict)
    base_cohort = defaultdict(set)
    r1 = defaultdict(dict)
    for i, d in enumerate(dates):
        if i == 0:
            continue
        pd_ = dates[i - 1]
        for t, x in price[d].items():
            p = price[pd_].get(t)
            if p and p["close"] > 0 and x["close"] > 0:
                r1[d][t] = x["close"] / p["close"] - 1
        if i < 20 or d not in taiex_valid:
            continue
        for t, x in price[d].items():
            if t not in r1[d] or x["volume"] <= 0 or t not in t86_by.get(d, {}):
                continue
            mvals = []
            ok = True
            for j in range(i - 20, i + 1):
                dj = dates[j]
                v = margin_by.get(dj, {}).get(t)
                if v is None or not math.isfinite(v) or v < 0:
                    ok = False
                    break
                mvals.append(v)
            if not ok:
                continue
            gs = [math.log1p(mvals[k]) - math.log1p(mvals[k - 1]) for k in range(1, 21)]
            g5 = statistics.mean(gs[-5:])
            g20 = statistics.mean(gs)
            lt_raw[d][t] = {"g1": gs[-1], "g5": g5, "g20": g20, "flush": -g20, "reaccel": g5 - g20, "margin": mvals[-1]}
            base_cohort[d].add(t)
    rresid = defaultdict(dict)
    for d, names in base_cohort.items():
        vals = [r1[d][t] for t in names if t in r1[d]]
        if not vals:
            continue
        med = statistics.median(vals)
        for t in names:
            if t in r1[d]:
                rresid[d][t] = r1[d][t] - med
    out_rows = []
    coverage = []
    for i, d in enumerate(dates):
        if i < 39 or d not in taiex_valid:
            continue
        prelim = {}
        for t in price[d]:
            if t not in lt_raw.get(d, {}):
                continue
            num = 0.0
            den = 0.0
            ok = True
            for j in range(i - 19, i + 1):
                dj = dates[j]
                if t not in base_cohort.get(dj, set()) or t not in rresid.get(dj, {}):
                    ok = False
                    break
                vol = price[dj][t]["volume"]
                tn = t86_by[dj].get(t)
                if tn is None or vol <= 0:
                    ok = False
                    break
                sp = max(0.0, -tn) / vol
                num += sp * rresid[dj][t]
                den += sp
            if not ok or den <= 0:
                continue
            z = lt_raw[d][t]
            prelim[t] = {"SA_raw": num / den, **z}
        if len(prelim) < K:
            coverage.append({"Date": d, "pit_count": len(price[d]), "eligible": len(prelim), "evaluable": False})
            continue
        uflush = midrank_open({t: z["flush"] for t, z in prelim.items()})
        ureaccel = midrank_open({t: z["reaccel"] for t, z in prelim.items()})
        lt = {t: math.sqrt(uflush[t] * ureaccel[t]) for t in prelim}
        usa = midrank_open({t: z["SA_raw"] for t, z in prelim.items()})
        ult = midrank_open(lt)
        m1 = {t: math.sqrt(usa[t] * ult[t]) for t in prelim}
        # simple margin diagnostics on the same final cohort
        umargin = midrank_open({t: z["margin"] for t, z in prelim.items()})
        ug1 = midrank_open({t: z["g1"] for t, z in prelim.items()})
        ug5 = midrank_open({t: z["g5"] for t, z in prelim.items()})
        ug20 = midrank_open({t: z["g20"] for t, z in prelim.items()})
        # R-017 contemporaneous references, no outcomes
        r017raw = {}
        for t in prelim:
            if i < 19 or t not in r1.get(d, {}):
                continue
            turns = []
            closes_ok = True
            for j in range(i - 19, i + 1):
                dj = dates[j]
                q = price[dj].get(t)
                if q is None or q["turn"] < 0:
                    closes_ok = False
                    break
                turns.append(q["turn"])
            if not closes_ok:
                continue
            adv20 = statistics.mean(turns)
            medturn = statistics.median(turns)
            curturn = turns[-1]
            ret20 = None
            if i >= 20:
                q0 = price[dates[i - 20]].get(t)
                if q0 is not None and q0["close"] > 0 and price[d][t]["close"] > 0:
                    ret20 = price[d][t]["close"] / q0["close"] - 1
            if adv20 > 0 and medturn > 0 and curturn >= 0 and ret20 is not None:
                shock = curturn / medturn
                impact = abs(r1[d][t]) / (curturn / adv20) if curturn > 0 else None
                r017raw[t] = {"ret1": r1[d][t], "ret20": ret20, "shock": shock, "liq": adv20, "impact": impact}
        r017ranks = {}
        for key in ("ret1", "ret20", "shock", "liq", "impact"):
            vals = {t: z[key] for t, z in r017raw.items() if z[key] is not None and math.isfinite(z[key])}
            r017ranks[key] = midrank_open(vals) if vals else {}
        for t, z in prelim.items():
            row = {
                "Date": d, "Ticker": t, "SA_raw": z["SA_raw"], "uSA": usa[t],
                "flush": z["flush"], "reaccel": z["reaccel"], "LT": lt[t], "uLT": ult[t], "M1": m1[t],
                "MarginRank": umargin[t], "g1Rank": ug1[t], "g5Rank": ug5[t], "g20Rank": ug20[t],
            }
            if t in legacy_features.get(d, {}):
                for name, val in zip(FACTORS, legacy_features[d][t]):
                    row[name] = val
            for key, col in (("ret1", "R017_ret1_rank"), ("ret20", "R017_ret20_rank"), ("shock", "R017_turnover_shock_rank"), ("liq", "R017_liquidity_rank"), ("impact", "R017_impact_rank")):
                row[col] = r017ranks.get(key, {}).get(t)
            out_rows.append(row)
        coverage.append({"Date": d, "pit_count": len(price[d]), "eligible": len(prelim), "evaluable": True})
    return pd.DataFrame(out_rows), pd.DataFrame(coverage)


def load_v43(v43_dir: pathlib.Path):
    results = list(v43_dir.rglob("ranking_v43_expanding_regime_icir_result.json"))
    events = list(v43_dir.rglob("ranking_v43_events.jsonl"))
    if len(results) != 1 or len(events) != 1:
        raise RuntimeError(f"V43 artifact files ambiguous results={results} events={events}")
    obj = json.loads(results[0].read_text(encoding="utf-8"))
    event_map = {}
    for line in events[0].read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        # Intentionally retain only old exposed identity fields; no V43 outcome field enters novelty.
        event_map[str(e.get("signal_date"))] = [str(x) for x in (e.get("tickers") or [])]
    return obj, event_map, {"result_sha256": sha256_file(results[0]), "events_sha256": sha256_file(events[0])}


def reconstruct_v43(panel, legacy_features, v43_obj, event_map):
    weight_log = v43_obj.get("weight_log") or []
    correlations = []
    verification = []
    score_rows = []
    for rec in weight_log:
        d = str(rec.get("signal_date"))
        if d not in legacy_features:
            continue
        w = rec.get("weights") or {}
        if set(w) != set(FACTORS):
            raise RuntimeError(f"bad V43 weight keys {d}: {sorted(w)}")
        scores = {t: sum(float(w[f]) * legacy_features[d][t][i] for i, f in enumerate(FACTORS)) for t in legacy_features[d]}
        picks = [t for t, s in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:3]]
        frozen = event_map.get(d)
        ok = frozen is None or picks == frozen
        verification.append({"Date": d, "reconstructed_top3": picks, "frozen_top3": frozen, "match": ok})
        g = panel[panel["Date"] == d][["Ticker", "M1"]].copy()
        if g.empty:
            continue
        g["V43Score"] = g["Ticker"].map(scores)
        g = g.dropna()
        if len(g) >= 5 and g["M1"].nunique() > 1 and g["V43Score"].nunique() > 1:
            rho = float(spearmanr(g["M1"], g["V43Score"]).statistic)
            correlations.append({"Date": d, "year": d[:4], "n": len(g), "spearman": rho, "abs_spearman": abs(rho)})
            for x in g.itertuples(index=False):
                score_rows.append((d, x.Ticker, float(x.V43Score)))
    if any(not x["match"] for x in verification if x["frozen_top3"] is not None):
        bad = [x for x in verification if x["frozen_top3"] is not None and not x["match"]]
        raise RuntimeError(f"V43_RECONSTRUCTION_MISMATCH {bad[:5]}")
    return correlations, verification, score_rows


def ols_leave_year_out(df):
    cols = FACTORS + ["M1", "Date"]
    z = df[cols].dropna().copy()
    z["year"] = z["Date"].str[:4]
    years = sorted(z["year"].unique())
    if len(years) < 2:
        return {"status": "DATA_BLOCKED", "years": years, "rows": len(z), "r2": None}
    preds, ys, meta = [], [], []
    for y in years:
        tr = z[z["year"] != y]
        te = z[z["year"] == y]
        if len(tr) < 6 or len(te) < 1:
            return {"status": "DATA_BLOCKED", "years": years, "rows": len(z), "r2": None, "reason": f"insufficient rows for {y}"}
        Xtr = np.column_stack([np.ones(len(tr)), tr[FACTORS].to_numpy(dtype=float)])
        ytr = tr["M1"].to_numpy(dtype=float)
        beta = np.linalg.lstsq(Xtr, ytr, rcond=None)[0]
        Xte = np.column_stack([np.ones(len(te)), te[FACTORS].to_numpy(dtype=float)])
        pred = Xte @ beta
        preds.extend(pred.tolist())
        ys.extend(te["M1"].to_numpy(dtype=float).tolist())
        meta.append({"year": y, "train_rows": len(tr), "test_rows": len(te)})
    ya = np.asarray(ys, dtype=float)
    pa = np.asarray(preds, dtype=float)
    sse = float(np.sum((ya - pa) ** 2))
    sst = float(np.sum((ya - ya.mean()) ** 2))
    r2 = 1.0 - sse / sst if sst > 0 else None
    return {"status": "OK" if r2 is not None else "DATA_BLOCKED", "years": years, "rows": len(z), "r2": r2, "folds": meta}


def exact_monotone_audit(panel):
    new_cols = ["SA_raw", "LT", "uSA", "M1"]
    refs = FACTORS + ["R017_ret1_rank", "R017_ret20_rank", "R017_turnover_shock_rank", "R017_liquidity_rank", "R017_impact_rank"]
    pairs = []
    established = []
    for a in new_cols:
        for b in refs:
            comparable = 0
            same = 0
            reverse = 0
            for d, g in panel[["Date", a, b]].dropna().groupby("Date"):
                if len(g) < 5 or g[a].nunique() < 2 or g[b].nunique() < 2:
                    continue
                ra = rank_vector(g[a].to_numpy())
                rb = rank_vector(g[b].to_numpy())
                comparable += 1
                if np.array_equal(ra, rb):
                    same += 1
                if np.array_equal(ra, (len(rb) + 1) - rb):
                    reverse += 1
            est = comparable >= 10 and (same == comparable or reverse == comparable)
            pairs.append({"new": a, "reference": b, "comparable_dates": comparable, "same_rank_dates": same, "reverse_rank_dates": reverse, "established_monotone_duplication": est})
            if est:
                established.append({"new": a, "reference": b})
    return pairs, established


def diagnostic_correlations(panel, x, refs):
    out = []
    for r in refs:
        z = same_date_spearman(panel, x, r)
        out.append({
            "x": x, "reference": r, "dates": len(z),
            "median_abs_spearman": statistics.median(abs(v) for _, v, _ in z) if z else None,
            "max_abs_spearman": max((abs(v) for _, v, _ in z), default=None),
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hist", required=True)
    ap.add_argument("--margin-dir", required=True)
    ap.add_argument("--v43-dir", required=True)
    ap.add_argument("--taiex", required=True)
    ap.add_argument("--t86-cache-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    hist_path = pathlib.Path(args.hist)
    expected_hist = "e3012612fcf3c38c05f5c7defdf7160a0de481db21ca6381ab53178091ad3f6b"
    hist_sha = sha256_file(hist_path)
    if hist_sha != expected_hist:
        raise SystemExit(f"HIST_SHA_MISMATCH {hist_sha}")
    hist = pd.read_csv(hist_path, compression="gzip", dtype={"ticker": str, "date": str})
    need = {"date", "ticker", "close", "volume_shares", "turnover_ntd"}
    if not need.issubset(hist.columns):
        raise SystemExit(f"HIST_SCHEMA_BLOCKED missing={sorted(need-set(hist.columns))}")
    hist = hist[list(need)].copy()
    for c in ("close", "volume_shares", "turnover_ntd"):
        hist[c] = pd.to_numeric(hist[c], errors="coerce")
    hist = hist.dropna(subset=["date", "ticker", "close", "volume_shares", "turnover_ntd"])
    hist = hist[(hist["ticker"].str.len() == 4) & hist["ticker"].str.isdigit()].sort_values(["date", "ticker"])
    if hist.duplicated(["date", "ticker"]).any():
        raise SystemExit("HIST_DUPLICATE_DATE_TICKER")
    dates = sorted(hist["date"].unique())

    margin_by, margin_manifest = load_margin(pathlib.Path(args.margin_dir))
    missing_margin_dates = sorted(set(dates) - set(margin_by))
    if missing_margin_dates:
        raise SystemExit(f"MARGIN_DATE_BLOCKED count={len(missing_margin_dates)} first={missing_margin_dates[:10]}")

    taiex_valid, taiex_meta = load_taiex(pathlib.Path(args.taiex))
    # The common cohort requires valid RG history; do not silently admit dates without it.
    missing_taiex_signal_dates = [d for d in dates if d >= "2023-01-03" and d not in taiex_valid]
    # Warmup before 63 sessions is expected; after the first valid date no gaps on market dates are accepted.
    if taiex_valid:
        first_valid = min(taiex_valid)
        later_missing = [d for d in dates if d >= first_valid and d not in taiex_valid]
        if later_missing:
            raise SystemExit(f"TAIEX_GAP_BLOCKED {later_missing[:10]} total={len(later_missing)}")
    else:
        raise SystemExit("TAIEX_NO_VALID_RG_DATES")

    t86_by, t86_manifest = load_t86(dates, pathlib.Path(args.t86_cache_dir))

    legacy_features, legacy_rows, legacy_dates = build_legacy_features(hist)
    panel, coverage = build_rs_panel(hist, t86_by, margin_by, taiex_valid, legacy_features, legacy_rows, legacy_dates)
    if panel.empty:
        raise SystemExit("RS_NO_FORWARD_FEATURE_PANEL_EMPTY")
    if panel.duplicated(["Date", "Ticker"]).any():
        raise SystemExit("RS_PANEL_DUPLICATE_DATE_TICKER")

    # Deterministic no-forward panel serialization.
    panel = panel.sort_values(["Date", "Ticker"]).reset_index(drop=True)
    panel_path = out / "repricing_state_no_forward_feature_panel.csv.gz"
    panel.to_csv(panel_path, index=False, compression={"method": "gzip", "mtime": 0})
    coverage_path = out / "repricing_state_no_forward_coverage.csv"
    coverage.sort_values("Date").to_csv(coverage_path, index=False)

    v43_obj, event_map, v43_hashes = load_v43(pathlib.Path(args.v43_dir))
    v43_corrs, v43_verify, _ = reconstruct_v43(panel, legacy_features, v43_obj, event_map)
    matched_years = sorted(set(x["year"] for x in v43_corrs))
    median_v43 = statistics.median(x["abs_spearman"] for x in v43_corrs) if v43_corrs else None
    v43_data_blocked = len(matched_years) < 2 or median_v43 is None
    v43_fail = (not v43_data_blocked) and median_v43 >= V43_CORR_FAIL

    ols = ols_leave_year_out(panel)
    ols_blocked = ols.get("status") != "OK"
    ols_fail = (not ols_blocked) and ols.get("r2") is not None and ols["r2"] >= LEGACY_R2_FAIL

    exact_pairs, exact_established = exact_monotone_audit(panel)
    exact_fail = bool(exact_established)

    r017_diag = diagnostic_correlations(panel, "SA_raw", [
        "R017_ret1_rank", "R017_ret20_rank", "R017_turnover_shock_rank", "R017_liquidity_rank", "R017_impact_rank"
    ])
    margin_diag = diagnostic_correlations(panel, "LT", ["MarginRank", "g1Rank", "g5Rank", "g20Rank"])

    # Frozen Monster BUY V1 event artifact currently begins in 2026, while this audited legacy panel ends 2025.
    # Do not reconstruct Monster eligibility from winners and do not let this descriptive diagnostic alter hard gates.
    monster_diag = {
        "status": "DIAGNOSTIC_NO_DATE_OVERLAP",
        "reason": "Frozen Monster BUY V1 event artifact is 2026; audited historical RS novelty panel is 2023-2025. No winner-aware reconstruction permitted.",
        "hard_novelty_gate_effect": "NONE"
    }

    if exact_fail or v43_fail or ols_fail:
        verdict = "NOVELTY_GATE_FAIL"
    elif v43_data_blocked or ols_blocked:
        verdict = "DATA_BLOCKED"
    else:
        verdict = "PASS"

    year_rows = {y: int((panel["Date"].str[:4] == y).sum()) for y in sorted(panel["Date"].str[:4].unique())}
    year_dates = {y: int(panel.loc[panel["Date"].str[:4] == y, "Date"].nunique()) for y in sorted(panel["Date"].str[:4].unique())}
    coverage_summary = {
        "pit_dates": len(dates),
        "panel_rows": len(panel),
        "panel_dates": int(panel["Date"].nunique()),
        "panel_first": str(panel["Date"].min()),
        "panel_last": str(panel["Date"].max()),
        "year_rows": year_rows,
        "year_dates": year_dates,
        "mean_eligible_per_evaluable_date": float(coverage.loc[coverage["evaluable"] == True, "eligible"].mean()) if (coverage["evaluable"] == True).any() else None,
        "min_eligible_per_evaluable_date": int(coverage.loc[coverage["evaluable"] == True, "eligible"].min()) if (coverage["evaluable"] == True).any() else None,
    }
    receipt = {
        "system": "HENGCE",
        "artifact": "REPRICING_STATE_V0_1_NO_FORWARD_NOVELTY_AUDIT",
        "authority": "RESEARCH_ONLY",
        "new_rs_forward_returns_opened": False,
        "new_rs_outcomes_computed": False,
        "discovery_state_after_this_audit": "SEALED" if verdict != "PASS" else "STILL_SEALED_PENDING_PERSISTED_VERDICT_AND_EXPLICIT_UNSEAL",
        "source_hashes": {
            "historical_panel_sha256": hist_sha,
            "taiex": taiex_meta,
            "v43": v43_hashes,
            "margin_raw_daily_file_count": len(margin_manifest),
            "t86_raw_daily_file_count": len(t86_manifest),
        },
        "coverage": coverage_summary,
        "novelty": {
            "verdict": verdict,
            "hard_gate_1_exact_monotone_duplication": {"fail": exact_fail, "established_pairs": exact_established, "pair_audit": exact_pairs},
            "hard_gate_2_v43_score_correlation": {
                "data_blocked": v43_data_blocked, "fail": v43_fail, "threshold": V43_CORR_FAIL,
                "matched_years": matched_years, "matched_dates": len(v43_corrs), "median_abs_same_date_spearman": median_v43,
                "per_date": v43_corrs, "reconstruction_verification": v43_verify,
            },
            "hard_gate_3_legacy_factor_reconstruction": {
                "data_blocked": ols_blocked, "fail": ols_fail, "threshold": LEGACY_R2_FAIL, **ols
            },
            "r017_diagnostic": r017_diag,
            "margin_simple_diagnostic": margin_diag,
            "monster_structural_overlap": monster_diag,
        },
        "feature_panel": {
            "path": panel_path.name,
            "sha256": sha256_file(panel_path),
            "columns": list(panel.columns),
            "contains_forward_return_column": False,
        },
        "coverage_file": {"path": coverage_path.name, "sha256": sha256_file(coverage_path)},
        "governance": {
            "v43_weights_interpolated": False,
            "v43_old_return_fields_used": False,
            "monster_used_as_target": False,
            "legacy_20m_filter_imported_into_rs_eligibility": False,
            "missing_session_gap_skipping": False,
            "silent_retuning": False,
        }
    }
    (out / "novelty_audit_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "t86_manifest.json").write_text(json.dumps(t86_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "margin_manifest.json").write_text(json.dumps(margin_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "verdict": verdict,
        "coverage": coverage_summary,
        "v43": {"matched_years": matched_years, "matched_dates": len(v43_corrs), "median_abs_spearman": median_v43, "fail": v43_fail, "blocked": v43_data_blocked},
        "legacy_ols": ols,
        "exact_duplication": exact_established,
        "panel_sha256": receipt["feature_panel"]["sha256"],
        "new_rs_forward_returns_opened": False,
    }, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
