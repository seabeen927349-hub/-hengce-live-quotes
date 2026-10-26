from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "results/rolling_3m_stability_20261026"
OUT.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location("port", HERE / "frozen_1m_portfolio_20261026.py")
port = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(port)

YEAR_START = pd.Timestamp("2025-10-22")
YEAR_END = pd.Timestamp("2026-10-21")
WINDOW = 63


def pf(s: pd.Series):
    if s.empty:
        return None
    pos=float(s[s>0].sum()); neg=float(-s[s<0].sum())
    if neg==0: return math.inf if pos>0 else None
    return pos/neg


def summarize(t: pd.DataFrame, start, end):
    if t.empty:
        return {"start":str(start.date()),"end":str(end.date()),"trades":0,"signal_dates":0,"pl":0.0,"wr":None,"pf":None,"mdd":None}
    return {
        "start":str(start.date()),"end":str(end.date()),
        "trades":int(len(t)),"signal_dates":int(t.signal_date.nunique()),
        "pl":float(t.pl.sum()),"wr":float((t.pl>0).mean()),"pf":pf(t.pl),
        "mdd":port.max_drawdown_realized(t),
    }


def main():
    panel=port.build_panel()
    market_dates=sorted(pd.to_datetime(panel.loc[panel.Date.between(YEAR_START,YEAR_END),"Date"].unique()))
    rows=[]
    for i in range(0,len(market_dates)-WINDOW+1):
        start=pd.Timestamp(market_dates[i]); end=pd.Timestamp(market_dates[i+WINDOW-1])
        opp=port.candidate_events(panel,start,end)
        t=port.simulate_strict_pool(opp)
        rows.append(summarize(t,start,end))
    roll=pd.DataFrame(rows)
    roll.to_csv(OUT/"rolling_63_session_windows.csv",index=False)

    # Non-overlapping 63-session blocks from the same frozen one-year start.
    blocks=[]
    for i in range(0,len(market_dates),WINDOW):
        chunk=market_dates[i:i+WINDOW]
        if len(chunk)<WINDOW:
            break
        start=pd.Timestamp(chunk[0]); end=pd.Timestamp(chunk[-1])
        opp=port.candidate_events(panel,start,end)
        t=port.simulate_strict_pool(opp)
        blocks.append(summarize(t,start,end))
    blockdf=pd.DataFrame(blocks)
    blockdf.to_csv(OUT/"nonoverlap_63_session_blocks.csv",index=False)

    result={
      "definition":"Frozen challenger, STRICT_POOL, every rolling 63 TWSE trading sessions; no parameter changes and each window capital restarts at fixed NT$1m for stress-test comparability.",
      "rolling_63":{
        "n_windows":int(len(roll)),
        "positive_pl_share":float((roll.pl>0).mean()) if len(roll) else None,
        "pf_gt_1_share":float((roll.pf>1).mean()) if len(roll) else None,
        "min_pl":float(roll.pl.min()) if len(roll) else None,
        "p10_pl":float(roll.pl.quantile(.10)) if len(roll) else None,
        "median_pl":float(roll.pl.median()) if len(roll) else None,
        "max_pl":float(roll.pl.max()) if len(roll) else None,
        "worst_mdd":float(roll.mdd.min()) if len(roll) else None,
        "min_pf":float(roll.pf.replace([np.inf,-np.inf],np.nan).min()) if len(roll) else None,
        "negative_windows":roll.loc[roll.pl<=0,["start","end","trades","signal_dates","pl","pf","mdd"]].to_dict("records"),
        "worst_5_by_pl":roll.nsmallest(min(5,len(roll)),"pl").to_dict("records"),
      },
      "nonoverlap_63":blockdf.to_dict("records")
    }
    (OUT/"RESULT.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=True),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=True))

if __name__=="__main__":
    main()
