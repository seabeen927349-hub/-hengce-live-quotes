#!/usr/bin/env python3
"""HENGCE 5-session market-stress cross-sectional diagnostic.

READ ONLY: consumes governed EOD CSV and status receipts in an existing repo.
No network, mother mutation, trade signal, model authority, or scheduler.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path

DEFAULT_DAYS = ["20261029", "20261030", "20261102", "20261103", "20261104"]

def load_leg(root: Path, date: str, leg: str) -> dict:
    folder = root / "eod" / date
    status = json.loads((folder / "status.json").read_text(encoding="utf-8"))
    if status.get(leg + "_status") != "COMPLETE":
        raise RuntimeError(f"{date} {leg} status={status.get(leg + '_status')}, FAIL_CLOSED")
    parts = sorted(folder.glob(f"{leg}_*.csv"))
    if len(parts) != 9:
        raise RuntimeError(f"{date} {leg}: need 9 canonical source parts, got {len(parts)}")
    result = {}
    for path in parts:
        with path.open(encoding="utf-8-sig", newline="") as inp:
            for row in csv.DictReader(inp):
                ticker = row.get("Ticker", "")
                if len(ticker) == 4 and ticker.isdigit() and ticker[0] != "0":
                    if ticker in result:
                        raise RuntimeError(f"{date} {leg}: duplicate symbol {ticker}")
                    result[ticker] = row
    return result

def number(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")

def median(values):
    vals = sorted(values)
    return vals[len(vals)//2] if vals else None

def percentile(values, level):
    vals = sorted(values)
    return vals[min(len(vals)-1, int((len(vals)-1)*level))]

def solve(a, b):
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    n = len(b)
    for k in range(n):
        pivot = max(range(k,n), key=lambda i: abs(m[i][k]))
        m[k],m[pivot] = m[pivot],m[k]
        if abs(m[k][k]) < 1e-12:
            raise RuntimeError("singular normal equations")
        div=m[k][k]
        for j in range(k,n+1): m[k][j]/=div
        for i in range(n):
            if i==k: continue
            ratio=m[i][k]
            for j in range(k,n+1): m[i][j]-=ratio*m[k][j]
    return [row[n] for row in m]

def fit(rows, features):
    stats={}
    for col in features:
        vals=[row[col] for row in rows]
        lo,hi=percentile(vals,.02),percentile(vals,.98)
        wins=[min(hi,max(lo,x)) for x in vals]
        mu=sum(wins)/len(wins)
        sd=math.sqrt(sum((x-mu)**2 for x in wins)/len(wins)) or 1.
        stats[col]=(lo,hi,mu,sd)
    def design(row):
        return [1.]+[(min(stats[f][1],max(stats[f][0],row[f]))-stats[f][2])/stats[f][3] for f in features]
    width=len(features)+1
    a=[[0.]*width for _ in range(width)]
    b=[0.]*width
    for row in rows:
        x=design(row)
        for i in range(width):
            b[i]+=x[i]*row["return5d_pct"]
            for j in range(width): a[i][j]+=x[i]*x[j]
    beta=solve(a,b)
    return beta, lambda row: sum(v*c for v,c in zip(design(row),beta))

def fivefold(rows, features):
    mu=sum(r["return5d_pct"] for r in rows)/len(rows)
    denom=sum((r["return5d_pct"]-mu)**2 for r in rows)
    se=ae=0.
    for fold in range(5):
        key=lambda r: ((int(r["ticker"])*2654435761)&0xFFFFFFFF)%5
        train=[r for r in rows if key(r)!=fold]
        test=[r for r in rows if key(r)==fold]
        if not test: continue
        _,predict=fit(train,features)
        for r in test:
            error=r["return5d_pct"]-predict(r)
            se+=error*error
            ae+=abs(error)
    beta,_=fit(rows,features)
    return {"cv_r2":round(1-se/denom,4),
            "cv_mae_percentage_points":round(ae/len(rows),3),
            "standardized_coefficients":[round(x,4) for x in beta]}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",type=Path,default=Path("."))
    ap.add_argument("--dates",nargs=5,default=DEFAULT_DAYS)
    ap.add_argument("--base",default="20261028")
    ap.add_argument("--prior",default="20261007")
    ap.add_argument("--min-average-value-m",type=float,default=20.)
    ap.add_argument("--min-daily-value-m",type=float,default=2.)
    ap.add_argument("--out",type=Path,default=Path("research/five_day_stress_resilience_20261105/reproduction_output.json"))
    args=ap.parse_args()
    root=args.repo_root
    sessions=[args.base]+args.dates
    price={d:load_leg(root,d,"price") for d in set(sessions+[args.prior])}
    flows={d:load_leg(root,d,"institutional") for d in args.dates}
    margin={d:load_leg(root,d,"margin") for d in args.dates}
    records=[]
    for ticker in price[args.base]:
        if any(ticker not in price[d] for d in sessions):
            continue
        q=[price[d][ticker] for d in sessions]
        close=[number(row["Close"]) for row in q]
        traded=[number(row["TurnoverTWD"]) for row in q[1:]]
        if any(not math.isfinite(v) or v<=0 for v in close+traded):
            continue
        if sum(traded)/5 < args.min_average_value_m*1e6 or min(traded)<args.min_daily_value_m*1e6:
            continue
        r={"ticker":ticker,"name":q[0]["Name"],
           "return5d_pct":100*(close[-1]/close[0]-1),
           "average_value_m":sum(traded)/5/1e6}
        if ticker in price[args.prior]:
            old=number(price[args.prior][ticker]["Close"])
            if old>0: r["pretrend_pct"]=100*(close[0]/old-1)
        if all(ticker in flows[d] and ticker in margin[d] for d in args.dates):
            n=0.; value_net=0.; dmargin=0.; valid=True
            for j,d in enumerate(args.dates):
                fr,mr=flows[d][ticker],margin[d][ticker]
                nv=number(fr["TotalNet"])
                bal=number(mr["MarginBalance"])
                previous=number(mr["MarginPreviousBalance"])
                if not all(math.isfinite(x) for x in [nv,bal,previous]):
                    valid=False
                    break
                n+=nv
                value_net+=nv*close[j+1]
                dmargin+=bal-previous
            if valid:
                first=margin[args.dates[0]][ticker]
                initial=number(first["MarginPreviousBalance"])
                r.update(institutional_net_shares=n,
                    institutional_net_pct_turnover=100*value_net/sum(traded),
                    margin_delta_lots=dmargin,
                    initial_margin_lots=initial)
                if initial>0:
                    r["margin_change_pct"]=100*dmargin/initial
        records.append(r)
    records.sort(key=lambda r:r["return5d_pct"])
    quintiles=[]
    for i in range(5):
        part=records[i*len(records)//5:(i+1)*len(records)//5]
        valid=[r for r in part if "margin_change_pct" in r and "institutional_net_shares" in r]
        quintiles.append({
            "group":i+1,"n":len(part),"complete":len(valid),
            "median_return_pct":median([r["return5d_pct"] for r in part]),
            "fraction_margin_decreased":sum(r["margin_delta_lots"]<0 for r in valid)/len(valid) if valid else None,
            "median_margin_change_pct":median([r["margin_change_pct"] for r in valid]),
            "fraction_institutional_net_sell":sum(r["institutional_net_shares"]<0 for r in valid)/len(valid) if valid else None})
    sample=[{"ticker":r["ticker"],"return5d_pct":r["return5d_pct"],
            "pre":r["pretrend_pct"],"mar":r["margin_change_pct"],"ins":r["institutional_net_pct_turnover"]}
            for r in records if all(k in r for k in ("pretrend_pct","margin_change_pct","institutional_net_pct_turnover"))]
    for row in sample:
        row["pretrend"]=row.pop("pre")
        row["margin"]=row.pop("mar")
        row["institutional"]=row.pop("ins")
    model={}
    for label,cols in [("prior_only",["pretrend"]),("margin_only",["margin"]),
                       ("institutional_only",["institutional"]),
                       ("prior_and_margin",["pretrend","margin"]),
                       ("all_three",["pretrend","margin","institutional"])]:
        model[label]=fivefold(sample,cols)
    output={"status":"RESEARCH_ONLY_NOT_CAUSAL_NOT_PREDICTIVE",
        "dates":args.dates,"base":args.base,"prior":args.prior,
        "universe_size":len(records),"model_sample":len(sample),
        "quintiles":quintiles,"model":model,
        "top_resilient":list(reversed(records[-15:])),
        "most_drawdown":records[:15],
        "limitations":["same-window flow features; not an actionable ex-ante predictor",
                       "one market episode cross-sectional CV only",
                       "no sector, share adjustments, corporate actions, or time-series validation"]}
    dest=root/args.out
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("RESEARCH_ONLY", "N",len(records),"model N",len(sample),"CV",model["all_three"])

if __name__=="__main__":
    main()
