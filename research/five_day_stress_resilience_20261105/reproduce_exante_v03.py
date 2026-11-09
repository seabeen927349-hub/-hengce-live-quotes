#!/usr/bin/env python3
"""HENGCE pre-shock resilience research v0.3 — strictly read-only.

Requires existing governed eod/YYYYMMDD/{status.json,price_1.csv..price_9.csv}.
No FinMind shadow promotion, scheduler, brokerage calls, or trading authority.
Only observable pre-shock data may define eligibility and predictor features.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path

PRIOR = "20261007"
PRE = ["20261014","20261015","20261016","20261019","20261020",
       "20261021","20261022","20261027","20261028"]
FUTURE = ["20261029","20261030","20261102","20261103","20261104"]
MODEL_FEATURES = ("pre_daily_vol_pct", "pretrend_1007_pct", "log_money")

def price_day(repo: Path, day: str) -> dict:
    folder = repo/"eod"/day
    status = json.loads((folder/"status.json").read_text(encoding="utf8"))
    if status.get("price_status") != "COMPLETE" or status.get("price_date", day) != f"{day[:4]}-{day[4:6]}-{day[6:]}":
        raise ValueError(f"{day}: PRICE_NOT_FORMALLY_COMPLETE")
    parts = [folder/f"price_{i}.csv" for i in range(1,10)]
    if any(not p.is_file() for p in parts):
        raise ValueError(f"{day}: incomplete nine-part governed price CSV")
    result = {}
    for part in parts:
        with part.open(encoding="utf-8-sig",newline="") as handle:
            for r in csv.DictReader(handle):
                t=r.get("Ticker","")
                if len(t)!=4 or not t.isdigit() or t.startswith("0"):
                    continue
                if t in result:
                    raise ValueError(f"{day}: duplicate {t}")
                fields=("Close","VolumeShares","TurnoverTWD")
                try:
                    numbers=[float(r[k]) for k in fields]
                except (KeyError,TypeError,ValueError):
                    continue
                if not all(math.isfinite(x) and x>0 for x in numbers):
                    continue
                result[t]={"close":numbers[0],"volume":numbers[1],
                           "turnover":numbers[2],"name":r.get("Name","")}
    return result

def average(x): return sum(x)/len(x)
def percentile(x,p):
    xs=sorted(x)
    return xs[min(len(xs)-1,int((len(xs)-1)*p))]
def median(x): return percentile(x,0.5)

def solve(a,b):
    n=len(a)
    aug=[list(a[i])+[b[i]] for i in range(n)]
    for k in range(n):
        p=max(range(k,n),key=lambda j:abs(aug[j][k]))
        aug[k],aug[p]=aug[p],aug[k]
        if abs(aug[k][k])<1e-10: raise ValueError("singular regression")
        z=aug[k][k]
        for j in range(k,n+1): aug[k][j]/=z
        for i in range(n):
            if i==k: continue
            factor=aug[i][k]
            for j in range(k,n+1): aug[i][j]-=factor*aug[k][j]
    return [x[-1] for x in aug]

def regress(training,columns):
    scales={}
    for k in columns:
        vals=[r[k] for r in training]
        lo,hi=percentile(vals,.02),percentile(vals,.98)
        bounded=[min(hi,max(lo,v)) for v in vals]
        mu=average(bounded)
        sd=math.sqrt(average([(v-mu)**2 for v in bounded])) or 1.
        scales[k]=(lo,hi,mu,sd)
    def design(r):
        return [1.]+[(min(scales[k][1],max(scales[k][0],r[k]))-scales[k][2])/scales[k][3] for k in columns]
    width=len(columns)+1
    XX=[[0.]*width for _ in range(width)]
    Xy=[0.]*width
    for row in training:
        x=design(row)
        for i in range(width):
            Xy[i]+=x[i]*row["ret5_pct"]
            for j in range(width): XX[i][j]+=x[i]*x[j]
    for i in range(1,width): XX[i][i]+=.01
    beta=solve(XX,Xy)
    return beta,lambda r:sum(a*b for a,b in zip(beta,design(r)))

def cross_stock_cv(rows, columns, benchmark):
    fullmean=average([r["ret5_pct"] for r in rows])
    sst=sum((r["ret5_pct"]-fullmean)**2 for r in rows)
    test_predictions=[]
    def fold(r): return ((int(r["ticker"])*2654435761)&0xFFFFFFFF)%5
    for f in range(5):
        train=[r for r in rows if fold(r)!=f]
        test=[r for r in rows if fold(r)==f]
        _,predict=regress(train,columns)
        test_predictions.extend({"symbol":r["ticker"],"observed":r["ret5_pct"],
                                 "predicted":predict(r)} for r in test)
    sse=sum((r["predicted"]-r["observed"])**2 for r in test_predictions)
    mae=average([abs(r["predicted"]-r["observed"]) for r in test_predictions])
    top=sorted(test_predictions,key=lambda r:r["predicted"],reverse=True)[:len(rows)//5]
    bottom=sorted(test_predictions,key=lambda r:r["predicted"])[:len(rows)//5]
    def stats(sub):
        return {"n":len(sub),"mean_five_day_return_pct":average([r["observed"] for r in sub]),
                "beat_market_fraction":average([r["observed"]>benchmark for r in sub])}
    beta,_=regress(rows,columns)
    return {"CV_R2":1-sse/sst,"CV_MAE_percentage_points":mae,
            "standardized_in_episode_coefficients":beta,
            "top20":stats(top),"bottom20":stats(bottom)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path("."))
    p.add_argument("--output",type=Path,
                   default=Path("research/five_day_stress_resilience_20261105/reproduce_v03_output.json"))
    p.add_argument("--market-benchmark",type=float,default=-8.69)
    a=p.parse_args()
    dates=[PRIOR]+PRE+FUTURE
    bars={d:price_day(a.root,d) for d in dates}
    out=[]
    for t in bars[PRE[-1]]:
        if t not in bars[PRIOR] or any(t not in bars[d] for d in PRE+FUTURE):
            continue
        history=[bars[d][t] for d in PRE]
        money=[r["turnover"] for r in history]
        if average(money)<20_000_000 or min(money)<2_000_000:
            continue  # ONLY pre-event information determines the stock universe
        cls=[r["close"] for r in history]
        daily=[100*(cls[i+1]/cls[i]-1) for i in range(len(cls)-1)]
        v=math.sqrt(average([(x-average(daily))**2 for x in daily]))
        outcome=100*(bars[FUTURE[-1]][t]["close"]/cls[-1]-1)
        record={"ticker":t,"name":history[-1]["name"],
                "pre_daily_vol_pct":v,
                "pre_max_day_loss_pct":min(daily),
                "pretrend_1007_pct":100*(cls[-1]/bars[PRIOR][t]["close"]-1),
                "pre_mean_money_m":average(money)/1e6,
                "log_money":math.log10(median(money)/1e6),
                "ret5_pct":outcome}
        if all(math.isfinite(x) for x in record.values() if isinstance(x,float)):
            out.append(record)
    if len(out)<100: raise RuntimeError(f"coverage too small: {len(out)}")
    out.sort(key=lambda r:r["ticker"])
    low=sorted(out,key=lambda r:r["pre_daily_vol_pct"])[:len(out)//5]
    high=sorted(out,key=lambda r:r["pre_daily_vol_pct"])[-len(out)//5:]
    measures={"mean_ret":average([r["ret5_pct"] for r in out]),
              "low_vol_mean":average([r["ret5_pct"] for r in low]),
              "high_vol_mean":average([r["ret5_pct"] for r in high]),
              "low_vol_beat_market":average([r["ret5_pct"]>a.market_benchmark for r in low]),
              "high_vol_beat_market":average([r["ret5_pct"]>a.market_benchmark for r in high])}
    models={
        "prior_volatility":cross_stock_cv(out,["pre_daily_vol_pct"],a.market_benchmark),
        "prior_worst_day":cross_stock_cv(out,["pre_max_day_loss_pct"],a.market_benchmark),
        "volatility_trend_liquidity":cross_stock_cv(out,list(MODEL_FEATURES),a.market_benchmark)
    }
    report={"status":"RESEARCH_ONLY_PRE_EVENT_DATA_NOT_A_VALIDATED_TRADING_MODEL",
            "prior_date":PRIOR,"feature_dates":PRE,"outcome_dates":FUTURE,
            "sample_count":len(out),"benchmark_pct":a.market_benchmark,
            "descriptive":measures,"models":models,
            "limitations":["one market episode cross-stock CV: NOT future market prediction",
                           "features selected after inspecting episode",
                           "requires future closes only to measure historical outcome",
                           "no industry controls, corporate action adjustments, or PnL",
                           "all model weights remain research-only"]}
    path=a.root/a.output
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"saved":str(path),"n":len(out),"descriptive":measures},ensure_ascii=False))

if __name__=="__main__":
    main()
