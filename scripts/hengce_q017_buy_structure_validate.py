#!/usr/bin/env python3
"""Research-only structural BUY-state validation for HENGCE/Q017.

Pre-registered candidates (no tuned percentage/ATR/time thresholds):
A HL_BREAK:
  confirmed swing low L1 -> swing high H -> higher confirmed swing low L2;
  first later close > H => signal.
B RETEST_REBREAK:
  start from A; later bar trades at/below H but closes above H (support retest);
  first later close above the highest high from A breakout through retest => signal.
C FAILED_BREAKDOWN_REVERSAL:
  confirmed swing low L; first later close < L; later close > L (reclaim);
  first later close above the highest high from breakdown through reclaim => signal.

Pivots are strict one-bar pivots and become usable only after t+1 close.
Signal is known at close; entry is next trading session open.  No portfolio
claim is made: this is an event-study gate before any model adoption.
"""
from __future__ import annotations

import argparse, csv, json, math, random
from collections import defaultdict
from pathlib import Path

DEV_END = "2026-07-21"
HOLDOUT_START = "2026-07-22"
COST = 0.004
HORIZONS = (1, 3, 5, 10)
SEED = 20261026
BOOT_N = 5000


def num(x):
    try:
        return float(str(x).replace(",", ""))
    except Exception:
        return None


def load(path: Path):
    by = defaultdict(list)
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            d = r.get("date") or r.get("Date")
            t = str(r.get("ticker") or r.get("Ticker") or "").strip()
            if not d or not t:
                continue
            vals = {k: num(r.get(k) if k in r else r.get(k.capitalize())) for k in ("open","high","low","close")}
            turnover = num(r.get("turnover_ntd") if "turnover_ntd" in r else r.get("Turnover"))
            if any(vals[k] is None for k in vals) or turnover is None:
                continue
            by[t].append({"date":d,"ticker":t,**vals,"turnover":turnover})
    for t in by:
        by[t].sort(key=lambda z:z["date"])
    return by


def pivots(bars):
    hi=[]; lo=[]
    for i in range(1,len(bars)-1):
        if bars[i]["high"] > bars[i-1]["high"] and bars[i]["high"] > bars[i+1]["high"]:
            hi.append(i)
        if bars[i]["low"] < bars[i-1]["low"] and bars[i]["low"] < bars[i+1]["low"]:
            lo.append(i)
    return hi,lo


def liquid_ok(bars, i):
    if i < 19:
        return False
    avg = sum(b["turnover"] for b in bars[i-19:i+1])/20.0
    return avg >= 50_000_000 and 10 <= bars[i]["close"] <= 900


def add_event(out, model, bars, signal_i, meta):
    if signal_i >= len(bars)-1 or not liquid_ok(bars, signal_i):
        return
    key=(model,bars[signal_i]["ticker"],bars[signal_i]["date"])
    if key in out:
        return
    entry_i=signal_i+1
    e={
        "model":model,"ticker":bars[signal_i]["ticker"],"signal_date":bars[signal_i]["date"],
        "entry_date":bars[entry_i]["date"],"entry_open":bars[entry_i]["open"],**meta
    }
    for h in HORIZONS:
        exit_i=entry_i+h-1
        if exit_i < len(bars):
            gross=bars[exit_i]["close"]/bars[entry_i]["open"]-1.0
            e[f"gross{h}"]=gross; e[f"net{h}"]=gross-COST; e[f"exit{h}_date"]=bars[exit_i]["date"]
        else:
            e[f"gross{h}"]=None; e[f"net{h}"]=None; e[f"exit{h}_date"]=None
    end=min(len(bars),entry_i+5)
    if end>entry_i:
        e["mfe5"]=max(b["high"] for b in bars[entry_i:end])/bars[entry_i]["open"]-1
        e["mae5"]=min(b["low"] for b in bars[entry_i:end])/bars[entry_i]["open"]-1
    else:
        e["mfe5"]=e["mae5"]=None
    out[key]=e


def signals_for_ticker(bars):
    hi,lo=pivots(bars)
    out={}
    # A + B
    a_events=[]
    for n in range(1,len(lo)):
        l1,l2=lo[n-1],lo[n]
        if bars[l2]["low"] <= bars[l1]["low"]:
            continue
        hs=[h for h in hi if l1 < h < l2]
        if not hs:
            continue
        h=hs[-1]
        start=max(l2+2,h+2)  # pivot at i confirmed after i+1 close; act from following bar onward
        sig=next((i for i in range(start,len(bars)) if bars[i]["close"]>bars[h]["high"]),None)
        if sig is None:
            continue
        meta={"l1_date":bars[l1]["date"],"l1":bars[l1]["low"],"h_date":bars[h]["date"],"h":bars[h]["high"],"l2_date":bars[l2]["date"],"l2":bars[l2]["low"]}
        add_event(out,"HL_BREAK",bars,sig,meta)
        a_events.append((sig,h,meta))
    for sig,h,meta in a_events:
        retest=None
        for i in range(sig+1,len(bars)):
            if bars[i]["low"] <= bars[h]["high"] and bars[i]["close"] > bars[h]["high"]:
                retest=i; break
            if bars[i]["close"] < bars[h]["high"]:
                break  # failed hold; not a clean retest candidate
        if retest is None:
            continue
        ceiling=max(b["high"] for b in bars[sig:retest+1])
        reb=next((i for i in range(retest+1,len(bars)) if bars[i]["close"]>ceiling),None)
        if reb is not None:
            add_event(out,"RETEST_REBREAK",bars,reb,{**meta,"base_break_date":bars[sig]["date"],"retest_date":bars[retest]["date"],"rebreak_level":ceiling})
    # C
    for l in lo:
        start=l+2
        if start>=len(bars):
            continue
        br=next((i for i in range(start,len(bars)) if bars[i]["close"]<bars[l]["low"]),None)
        if br is None:
            continue
        rec=next((i for i in range(br+1,len(bars)) if bars[i]["close"]>bars[l]["low"]),None)
        if rec is None:
            continue
        repair_high=max(b["high"] for b in bars[br:rec+1])
        sig=next((i for i in range(rec+1,len(bars)) if bars[i]["close"]>repair_high),None)
        if sig is not None:
            add_event(out,"FAILED_BREAKDOWN_REVERSAL",bars,sig,{"protected_low_date":bars[l]["date"],"protected_low":bars[l]["low"],"breakdown_date":bars[br]["date"],"reclaim_date":bars[rec]["date"],"repair_high":repair_high})
    return list(out.values())


def pf(xs):
    pos=sum(x for x in xs if x>0); neg=-sum(x for x in xs if x<0)
    return None if neg==0 else pos/neg


def pct(xs,p):
    if not xs: return None
    s=sorted(xs); x=(len(s)-1)*p; a=int(math.floor(x)); b=int(math.ceil(x))
    if a==b:return s[a]
    return s[a]*(b-x)+s[b]*(x-a)


def boot(xs):
    if not xs:return {"p_mean_positive":None,"p5":None,"p50":None,"p95":None}
    rng=random.Random(SEED+len(xs)); n=len(xs); means=[]
    for _ in range(BOOT_N):
        means.append(sum(xs[rng.randrange(n)] for _ in range(n))/n)
    return {"p_mean_positive":sum(m>0 for m in means)/BOOT_N,"p5":pct(means,.05),"p50":pct(means,.50),"p95":pct(means,.95)}


def summarize(events, model, split):
    if split=="dev": rows=[e for e in events if e["model"]==model and e["signal_date"]<=DEV_END]
    else: rows=[e for e in events if e["model"]==model and e["signal_date"]>=HOLDOUT_START]
    o={"model":model,"split":split,"events":len(rows)}
    for h in HORIZONS:
        xs=[e[f"net{h}"] for e in rows if e.get(f"net{h}") is not None]
        o[f"h{h}"]={"n":len(xs),"mean_net":sum(xs)/len(xs) if xs else None,"median_net":pct(xs,.5),"winrate":sum(x>0 for x in xs)/len(xs) if xs else None,"pf":pf(xs)}
        if h==5:o[f"h{h}"]["bootstrap_mean"]=boot(xs)
    m=[e["mfe5"] for e in rows if e.get("mfe5") is not None]; a=[e["mae5"] for e in rows if e.get("mae5") is not None]
    o["mfe5_mean"]=sum(m)/len(m) if m else None; o["mae5_mean"]=sum(a)/len(a) if a else None
    return o


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",required=True); ap.add_argument("--out-dir",required=True); args=ap.parse_args()
    data=load(Path(args.input)); all_events=[]
    for bars in data.values(): all_events.extend(signals_for_ticker(bars))
    all_events.sort(key=lambda e:(e["signal_date"],e["model"],e["ticker"]))
    models=["HL_BREAK","RETEST_REBREAK","FAILED_BREAKDOWN_REVERSAL"]
    summary={"schema_version":1,"artifact":"HENGCE_Q017_BUY_STRUCTURE_VALIDATION_20261026","authority":"RESEARCH_ONLY_ZERO_TRADE_AUTHORITY","input":str(args.input),"rules_frozen_before_holdout":True,"dev_end":DEV_END,"holdout_start":HOLDOUT_START,"roundtrip_cost":COST,"liquidity":"20D avg turnover >= 50m; signal close 10..900","entry":"next trading session open","forward_exit":"close after 1/3/5/10 sessions including entry session","models":models,"results":[]}
    for m in models:
        summary["results"].append({"dev":summarize(all_events,m,"dev"),"holdout":summarize(all_events,m,"holdout")})
    # Decision is intentionally conservative and computed only after holdout metrics exist.
    eligible=[]
    for r in summary["results"]:
        d,h=r["dev"],r["holdout"]
        dmeans=[d[f"h{x}"]["mean_net"] for x in (3,5,10)]; hmeans=[h[f"h{x}"]["mean_net"] for x in (3,5,10)]
        p=d["h5"]["bootstrap_mean"]["p_mean_positive"]
        ok=all(x is not None and x>0 for x in dmeans) and all(x is not None and x>0 for x in hmeans) and p is not None and p>=0.95 and h["h5"]["median_net"] is not None and h["h5"]["median_net"]>0
        if ok: eligible.append(r)
    if eligible:
        eligible.sort(key=lambda r:r["holdout"]["h5"]["mean_net"],reverse=True)
        summary["decision"]={"status":"SURVIVOR","model":eligible[0]["holdout"]["model"],"rule":"positive dev+holdout mean at 3/5/10; dev 5D bootstrap P(mean>0)>=0.95; holdout 5D median>0; select highest holdout 5D mean among qualifiers"}
    else:
        summary["decision"]={"status":"NO_SURVIVOR","model":None,"rule":"same pre-registered gate"}
    out=Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    with (out/"BUY_STRUCTURE_EVENTS.csv").open("w",encoding="utf-8",newline="") as fh:
        fields=sorted({k for e in all_events for k in e})
        w=csv.DictWriter(fh,fieldnames=fields); w.writeheader(); w.writerows(all_events)
    (out/"BUY_STRUCTURE_SUMMARY.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
