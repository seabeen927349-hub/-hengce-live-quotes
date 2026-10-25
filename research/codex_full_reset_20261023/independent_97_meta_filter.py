#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import json
import math
import statistics
from pathlib import Path

# Reuse only the point-in-time data loader and the exact HR1 mother-sample definition.
# The meta-model below DOES NOT use V6 score, V6 score gap, or the five Hengce factor ranks as predictors.
with contextlib.redirect_stdout(io.StringIO()):
    import research.codex_full_reset_20261023.ranking_v13_weak_regime_profiles as v13

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research/codex_full_reset_20261023/INDEPENDENT_97_META_FILTER_RESULT_20261025.json"
EVENTS_OUT = ROOT / "research/codex_full_reset_20261023/independent_97_meta_filter_events.jsonl"

DATES = v13.dates
H = 10
V6 = (0.20, 0.25, 0.30, 0.05, 0.20)  # mother-sample reconstruction only
SCORE_MIN = 0.75
COST_DIAG = 0.012
TARGET_COVERAGES = (0.70, 0.75, 0.80, 0.85, 0.90, 0.95)
PRIMARY_MIN_VALIDATION_COVERAGE = 0.80
SECONDARY_MIN_VALIDATION_COVERAGE = 0.70

FEATURE_NAMES = (
    "stock_r1", "stock_r5", "stock_r20", "stock_r60",
    "stock_vol20", "stock_beta60", "stock_resid5",
    "turnover_log_ratio20", "entry_gap",
    "drawdown_from_20d_close_high", "positive_day_fraction10", "positive_day_fraction20",
    "market_median_r1", "market_median_r5", "market_median_r20",
    "market_positive_r1_fraction", "market_positive_r20_fraction",
    "market_dispersion_r1", "market_dispersion_r20",
    "relative_r5", "relative_r20",
)


def wilson_lower(w: int, n: int, z: float = 1.959963984540054):
    if n <= 0:
        return None
    p = w / n
    den = 1 + z*z/n
    return (p + z*z/(2*n) - z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))) / den


def product(xs):
    z = 1.0
    for x in xs:
        z *= 1.0 + x
    return z - 1.0


def quantile(xs, q):
    ys = sorted(xs)
    if not ys:
        raise ValueError("empty quantile")
    if len(ys) == 1:
        return ys[0]
    pos = (len(ys)-1)*q
    lo = int(math.floor(pos)); hi = int(math.ceil(pos))
    if lo == hi:
        return ys[lo]
    return ys[lo] + (ys[hi]-ys[lo])*(pos-lo)


def median(xs):
    return statistics.median(xs) if xs else 0.0


def stdev(xs):
    return statistics.stdev(xs) if len(xs) >= 2 else 0.0

# Exact mother-sample selector: V6 top1, score>=0.75, no gap/breadth gate, H10.
SIGNALS = {}
for d, F in v13.features.items():
    arr = []
    for t, vals in F.items():
        arr.append((sum(V6[k]*vals[k] for k in range(5)), t))
    arr.sort(key=lambda z: (-z[0], z[1]))
    if arr:
        SIGNALS[d] = {"ticker": arr[0][1], "score": arr[0][0]}


def path_outcome(signal_i: int, ticker: str, end: str):
    ei = signal_i + 1
    xi = ei + H
    if xi >= len(DATES) or DATES[xi] > end:
        return None
    er = v13.by[DATES[ei]].get(ticker)
    if er is None or er.o is None or er.o <= 0:
        return None
    entry = er.o
    for j in range(ei+1, xi+1):
        r = v13.by[DATES[j]].get(ticker)
        if r is None or r.c is None or r.c <= 0 or r.bad:
            return None
        ret = r.c/entry - 1.0
        if ret > 0:
            return {"win": True, "entry_date": DATES[ei], "exit_date": DATES[j],
                    "entry_open": entry, "exit_close": r.c, "gross_return": ret,
                    "hold": j-ei, "exit_i": j}
    r = v13.by[DATES[xi]].get(ticker)
    if r is None or r.c is None or r.c <= 0 or r.bad:
        return None
    ret = r.c/entry - 1.0
    return {"win": ret > 0, "entry_date": DATES[ei], "exit_date": DATES[xi],
            "entry_open": entry, "exit_close": r.c, "gross_return": ret,
            "hold": H, "exit_i": xi}


def raw_feature_dict(signal_i: int, ticker: str):
    d = DATES[signal_i]
    r = v13.by[d][ticker]
    entry = v13.by[DATES[signal_i+1]][ticker]

    universe = [x for x in v13.by[d].values()
                if not x.bad and x.r1 is not None and x.r5 is not None and x.r20 is not None]
    m1 = [x.r1 for x in universe]
    m5 = [x.r5 for x in universe]
    m20 = [x.r20 for x in universe]
    med1, med5, med20 = median(m1), median(m5), median(m20)

    hist = []
    for j in range(max(0, signal_i-19), signal_i+1):
        rr = v13.by[DATES[j]].get(ticker)
        if rr is not None and rr.c is not None and rr.c > 0 and not rr.bad:
            hist.append(rr)
    closes = [x.c for x in hist]
    r1s = [x.r1 for x in hist if x.r1 is not None]
    last10 = r1s[-10:]
    last20 = r1s[-20:]

    turn_ratio = (r.turn / r.turn20) if r.turn20 and r.turn20 > 0 and r.turn and r.turn > 0 else 1.0
    entry_gap = entry.o/r.c - 1.0
    dd20 = r.c/max(closes) - 1.0 if closes else 0.0

    f = {
        "stock_r1": r.r1,
        "stock_r5": r.r5,
        "stock_r20": r.r20,
        "stock_r60": r.r60,
        "stock_vol20": r.vol20,
        "stock_beta60": r.beta60,
        "stock_resid5": r.resid5,
        "turnover_log_ratio20": math.log(max(turn_ratio, 1e-9)),
        "entry_gap": entry_gap,
        "drawdown_from_20d_close_high": dd20,
        "positive_day_fraction10": sum(x > 0 for x in last10)/len(last10) if last10 else 0.5,
        "positive_day_fraction20": sum(x > 0 for x in last20)/len(last20) if last20 else 0.5,
        "market_median_r1": med1,
        "market_median_r5": med5,
        "market_median_r20": med20,
        "market_positive_r1_fraction": sum(x > 0 for x in m1)/len(m1) if m1 else 0.5,
        "market_positive_r20_fraction": sum(x > 0 for x in m20)/len(m20) if m20 else 0.5,
        "market_dispersion_r1": stdev(m1),
        "market_dispersion_r20": stdev(m20),
        "relative_r5": r.r5-med5,
        "relative_r20": r.r20-med20,
    }
    for k in FEATURE_NAMES:
        if f[k] is None or not math.isfinite(float(f[k])):
            f[k] = 0.0
    return f


def mother_events(start: str, end: str):
    ev = []
    next_free = -1
    for i, d in enumerate(DATES):
        if d < start or d > end or i < next_free:
            continue
        s = SIGNALS.get(d)
        if s is None or s["score"] < SCORE_MIN:
            continue
        o = path_outcome(i, s["ticker"], end)
        if o is None:
            continue
        fd = raw_feature_dict(i, s["ticker"])
        ev.append({"signal_date": d, "ticker": s["ticker"], **o, "features": fd})
        next_free = o["exit_i"]
    return ev

# Preserve exact HR1 split semantics: one continuous 2024-2025 training schedule, separate 2026 holdout schedule.
pre = mother_events("2024-01-01", "2025-12-31")
ev2024 = [e for e in pre if e["signal_date"].startswith("2024-")]
ev2025 = [e for e in pre if e["signal_date"].startswith("2025-")]
ev2026 = mother_events("2026-01-01", "2026-10-22")
if len(pre) != 97:
    raise RuntimeError(f"Mother sample mismatch: expected 97, got {len(pre)}")


def matrix(events):
    X = [[float(e["features"][k]) for k in FEATURE_NAMES] for e in events]
    y = [1 if e["win"] else 0 for e in events]
    return X, y


def scaler(X):
    p = len(X[0])
    mu = [statistics.mean(row[j] for row in X) for j in range(p)]
    sd = []
    for j in range(p):
        vals = [row[j] for row in X]
        s = statistics.stdev(vals) if len(vals) >= 2 else 1.0
        sd.append(s if s > 1e-12 else 1.0)
    return mu, sd


def transform(X, mu, sd):
    return [[(row[j]-mu[j])/sd[j] for j in range(len(mu))] for row in X]


def sigmoid(z):
    if z >= 0:
        q = math.exp(-z); return 1/(1+q)
    q = math.exp(z); return q/(1+q)


def fit_logit(X, y, lam):
    mu, sd = scaler(X); Z = transform(X, mu, sd)
    p = len(Z[0]); n = len(Z)
    base = (sum(y)+0.5)/(n+1.0)
    b = [math.log(base/(1-base))] + [0.0]*p
    lr = 0.08
    for it in range(2200):
        g = [0.0]*(p+1)
        for row, yy in zip(Z, y):
            pr = sigmoid(b[0] + sum(b[j+1]*row[j] for j in range(p)))
            err = pr-yy
            g[0] += err
            for j in range(p): g[j+1] += err*row[j]
        g[0] /= n
        for j in range(p): g[j+1] = g[j+1]/n + lam*b[j+1]/n
        step = lr / math.sqrt(1.0 + it/400.0)
        for j in range(p+1): b[j] -= step*g[j]
    return {"kind":"logit", "lam":lam, "mu":mu, "sd":sd, "b":b}


def predict_logit(model, X):
    Z = transform(X, model["mu"], model["sd"]); b=model["b"]
    return [sigmoid(b[0]+sum(b[j+1]*row[j] for j in range(len(row)))) for row in Z]


def fit_knn(X, y, k):
    mu, sd = scaler(X)
    return {"kind":"knn", "k":k, "mu":mu, "sd":sd, "X":transform(X,mu,sd), "y":list(y)}


def predict_knn(model, X):
    Z = transform(X, model["mu"], model["sd"])
    out=[]; base=(sum(model["y"])+1)/(len(model["y"])+2)
    for row in Z:
        ds=[]
        for tr,yy in zip(model["X"],model["y"]):
            dist=math.sqrt(sum((a-b)*(a-b) for a,b in zip(row,tr)))
            ds.append((dist,yy))
        ds.sort(key=lambda z:z[0]); neigh=ds[:min(model["k"],len(ds))]
        weights=[1/(d+0.35) for d,_ in neigh]
        out.append((sum(w*y for w,(_,y) in zip(weights,neigh))+2*base)/(sum(weights)+2))
    return out


def fit_family(spec, X, y):
    if spec["kind"] == "logit": return fit_logit(X,y,spec["lam"])
    if spec["kind"] == "knn": return fit_knn(X,y,spec["k"])
    return {"kind":"blend", "a":fit_logit(X,y,spec["lam"]), "b":fit_knn(X,y,spec["k"])}


def predict_family(model, X):
    if model["kind"] == "logit": return predict_logit(model,X)
    if model["kind"] == "knn": return predict_knn(model,X)
    a=predict_logit(model["a"],X); b=predict_knn(model["b"],X)
    return [(x+y)/2 for x,y in zip(a,b)]


def loo_scores(spec, X, y):
    out=[]
    for i in range(len(X)):
        Xt=X[:i]+X[i+1:]; yt=y[:i]+y[i+1:]
        m=fit_family(spec,Xt,yt)
        out.append(predict_family(m,[X[i]])[0])
    return out

FAMILIES=[]
for lam in (0.25,1.0,4.0): FAMILIES.append({"kind":"logit","lam":lam})
for k in (5,9,13): FAMILIES.append({"kind":"knn","k":k})
for lam in (0.25,1.0,4.0):
    for k in (5,9,13): FAMILIES.append({"kind":"blend","lam":lam,"k":k})


def basic_metrics(events):
    n=len(events); w=sum(e["win"] for e in events); rets=[e["gross_return"] for e in events]
    return {"trades":n,"wins":w,"losses":n-w,"win_rate":w/n if n else None,
            "wilson95_lower":wilson_lower(w,n),
            "mean_gross_return":statistics.mean(rets) if rets else None,
            "compounded_gross_return":product(rets) if rets else None,
            "after_1p2pct_cost_positive_rate":sum(r>COST_DIAG for r in rets)/n if n else None}


def filtered_metrics(events, scores, threshold):
    chosen=[e for e,s in zip(events,scores) if s>=threshold]
    m=basic_metrics(chosen)
    m["coverage"] = len(chosen)/len(events) if events else None
    skipped=[e for e,s in zip(events,scores) if s<threshold]
    m["skipped"] = len(skipped)
    m["losses_caught_by_skip"] = sum(not e["win"] for e in skipped)
    m["wins_sacrificed_by_skip"] = sum(e["win"] for e in skipped)
    m["loss_capture_rate"] = m["losses_caught_by_skip"]/sum(not e["win"] for e in events) if any(not e["win"] for e in events) else None
    return m, chosen

X24,y24=matrix(ev2024); X25,y25=matrix(ev2025); Xpre,ypre=matrix(pre); X26,y26=matrix(ev2026)
base24=basic_metrics(ev2024); base25=basic_metrics(ev2025); basepre=basic_metrics(pre); base26=basic_metrics(ev2026)

candidates=[]
for spec in FAMILIES:
    oof24=loo_scores(spec,X24,y24)
    full24=fit_family(spec,X24,y24)
    score25=predict_family(full24,X25)
    for cov in TARGET_COVERAGES:
        threshold=quantile(oof24,1.0-cov)
        m24,_=filtered_metrics(ev2024,oof24,threshold)
        m25,_=filtered_metrics(ev2025,score25,threshold)
        candidates.append({"family":spec,"target_coverage":cov,"development_2024_oof":m24,
                           "validation_2025":m25,"development_threshold":threshold})


def selection_key(c):
    a,b=c["development_2024_oof"],c["validation_2025"]
    return (min(a["win_rate"],b["win_rate"]), b["win_rate"], min(a["wilson95_lower"],b["wilson95_lower"]),
            min(a["coverage"],b["coverage"]), b["trades"])

primary=[c for c in candidates if c["development_2024_oof"]["coverage"]>=0.80 and c["validation_2025"]["coverage"]>=PRIMARY_MIN_VALIDATION_COVERAGE]
secondary=[c for c in candidates if c["development_2024_oof"]["coverage"]>=0.70 and c["validation_2025"]["coverage"]>=SECONDARY_MIN_VALIDATION_COVERAGE]
primary.sort(key=selection_key,reverse=True); secondary.sort(key=selection_key,reverse=True)
champ=(primary[0] if primary else secondary[0])

# Locked refit protocol for 2026: family + target coverage fixed above; train on 2024-2025,
# calibrate the cutoff from leave-one-out pre-2026 scores only, then score 2026 once.
pre_oof=loo_scores(champ["family"],Xpre,ypre)
refit_threshold=quantile(pre_oof,1.0-champ["target_coverage"])
pre_filtered,pre_chosen=filtered_metrics(pre,pre_oof,refit_threshold)
refit=fit_family(champ["family"],Xpre,ypre)
score26=predict_family(refit,X26)
m26,chosen26=filtered_metrics(ev2026,score26,refit_threshold)

# coefficient orientation for interpretability when the selected model contains a logistic component.
def coeffs(model):
    mm=model if model["kind"]=="logit" else model.get("a")
    if not mm:return None
    pairs=[{"feature":f,"standardized_coefficient":mm["b"][i+1]} for i,f in enumerate(FEATURE_NAMES)]
    return sorted(pairs,key=lambda z:abs(z["standardized_coefficient"]),reverse=True)

improve25=m26 is not None
status="INDEPENDENT_FILTER_DOES_NOT_GENERALIZE"
if champ["validation_2025"]["coverage"]>=0.80 and champ["validation_2025"]["win_rate"]>base25["win_rate"] and m26["coverage"]>=0.75 and m26["win_rate"]>=base26["win_rate"]:
    status="PROMISING_INDEPENDENT_META_FILTER_HISTORICAL_CONFIRMATION"

res={
    "status":status,
    "objective":"learn the failure pattern inside the exact HR1 97-trade mother sample without using Hengce score/ranks as predictors",
    "mother_sample_definition":{"only_hengce_dependency":"reconstruct the exact 97 historical V6-top1/H10 events requested by the user",
        "meta_predictors_exclude":["V6 score","top1-top2 score gap","five Hengce factor ranks"],
        "schedule_semantics":"fixed mother-event schedule; skipped events do not cause schedule reflow"},
    "feature_names":FEATURE_NAMES,
    "model_search":{"families":FAMILIES,"target_coverages":TARGET_COVERAGES,"selection":"2024 leave-one-out development + 2025 validation maximin; 2026 never used for family/coverage selection"},
    "baseline":{"2024":base24,"2025":base25,"2024_2025":basepre,"2026_through_2026_10_22":base26},
    "selected":{"family":champ["family"],"target_coverage":champ["target_coverage"],
        "development_2024_oof":champ["development_2024_oof"],"validation_2025":champ["validation_2025"],
        "pre2026_refit_loo":pre_filtered,"pre2026_refit_threshold":refit_threshold,
        "historical_diagnostic_2026":m26,"top_logistic_coefficients":coeffs(refit)[:10] if coeffs(refit) else None},
    "top10_primary_candidates":primary[:10],"top10_secondary_candidates":secondary[:10],
    "judgment":{"validation_improvement_pp":100*(champ["validation_2025"]["win_rate"]-base25["win_rate"]),
        "diagnostic_2026_improvement_pp":100*(m26["win_rate"]-base26["win_rate"]),
        "diagnostic_2026_coverage":m26["coverage"],
        "not_a_future_guarantee":True,
        "2026_note":"2026 has been exposed elsewhere in the broader project, so this is historical diagnostic evidence, not untouched future OOS."},
    "authority":{"research_only":True,"capital_authority_twd":0,"broker_order_execution":False,"production_promotion":False,"merge_authorized":False}
}

# Save scored 2026 and pre-2026 rows for forensic review.
with EVENTS_OUT.open("w",encoding="utf-8") as fh:
    for label,events,scores,thr in (("PRE2026_LOO",pre,pre_oof,refit_threshold),("2026_DIAGNOSTIC",ev2026,score26,refit_threshold)):
        for e,s in zip(events,scores):
            row={k:v for k,v in e.items() if k!="exit_i"}
            row.update({"split":label,"meta_score":s,"meta_take":s>=thr})
            fh.write(json.dumps(row,ensure_ascii=False)+"\n")

OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("INDEPENDENT97_RESULT="+json.dumps(res,ensure_ascii=False,separators=(",",":")))
