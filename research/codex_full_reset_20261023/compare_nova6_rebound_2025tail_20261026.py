from __future__ import annotations

import importlib.util
import io
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "results/compare_nova6_rebound_2025tail_20261026"
OUT.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location("port", HERE / "frozen_1m_portfolio_20261026.py")
port = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(port)

# Canonical NOVA6 2025 frozen audit ledger, signal dates 2025-10-22..2025-12-29.
NOVA6_2025_TAIL = """signal_date,entry_date,exit_date,round_pl
2025-10-22,2025-10-23,2025-10-27,34704.79999999999
2025-10-23,2025-10-27,2025-10-28,-3341.399999999904
2025-10-27,2025-10-28,2025-10-29,4905.999999999955
2025-10-28,2025-10-29,2025-10-30,5967.999999999977
2025-10-29,2025-10-30,2025-10-31,-8460.200000000006
2025-10-30,2025-10-31,2025-11-03,9819.99999999999
2025-10-31,2025-11-03,2025-11-04,3702.599999999966
2025-11-03,2025-11-04,2025-11-05,-34714.0
2025-11-04,2025-11-05,2025-11-06,33905.99999999997
2025-11-05,2025-11-06,2025-11-07,-14541.799999999956
2025-11-06,2025-11-07,2025-11-10,-3213.000000000003
2025-11-07,2025-11-10,2025-11-11,47309.60000000003
2025-11-10,2025-11-11,2025-11-12,47277.19999999992
2025-11-11,2025-11-12,2025-11-13,56721.20000000006
2025-11-12,2025-11-13,2025-11-14,-51588.800000000025
2025-11-13,2025-11-14,2025-11-17,16944.79999999996
2025-11-14,2025-11-17,2025-11-18,-17292.79999999997
2025-11-17,2025-11-18,2025-11-19,-19879.599999999984
2025-11-18,2025-11-19,2025-11-20,57590.19999999993
2025-11-19,2025-11-20,2025-11-21,-64017.6
2025-11-20,2025-11-21,2025-11-24,21927.599999999995
2025-11-21,2025-11-24,2025-11-25,17472.400000000067
2025-11-24,2025-11-25,2025-11-26,3208.8000000000347
2025-11-25,2025-11-26,2025-11-27,20239.200000000037
2025-11-26,2025-11-27,2025-11-28,2091.8000000000247
2025-11-27,2025-11-28,2025-12-01,-1421.9999999999902
2025-11-28,2025-12-01,2025-12-02,23289.99999999995
2025-12-01,2025-12-02,2025-12-03,-7447.399999999985
2025-12-02,2025-12-03,2025-12-04,1026.7999999999936
2025-12-03,2025-12-04,2025-12-05,-9086.399999999994
2025-12-04,2025-12-05,2025-12-08,-388.8000000000175
2025-12-05,2025-12-08,2025-12-09,-14031.599999999966
2025-12-08,2025-12-09,2025-12-10,-5389.59999999997
2025-12-09,2025-12-10,2025-12-11,10178.600000000088
2025-12-10,2025-12-11,2025-12-12,16649.999999999985
2025-12-11,2025-12-12,2025-12-15,-26498.200000000004
2025-12-12,2025-12-15,2025-12-16,3938.200000000106
2025-12-15,2025-12-16,2025-12-17,28406.39999999995
2025-12-16,2025-12-17,2025-12-18,-20367.79999999993
2025-12-17,2025-12-18,2025-12-19,21762.39999999999
2025-12-18,2025-12-19,2025-12-22,1667.1999999999848
2025-12-19,2025-12-22,2025-12-23,6522.000000000075
2025-12-22,2025-12-23,2025-12-24,1040.0000000000268
2025-12-23,2025-12-24,2025-12-26,212.39999999998577
2025-12-24,2025-12-26,2025-12-29,21513.80000000001
2025-12-26,2025-12-29,2025-12-30,15345.600000000024
2025-12-29,2025-12-30,2025-12-31,18053.599999999984
"""

START = pd.Timestamp("2025-10-22")
END = pd.Timestamp("2025-12-29")


def pf(s: pd.Series):
    pos=float(s[s>0].sum()); neg=float(-s[s<0].sum())
    if neg == 0: return math.inf if pos > 0 else None
    return pos/neg


def mdd(s: pd.Series):
    c=s.cumsum(); peak=c.cummax().clip(lower=0)
    return float((c-peak).min())


def corr(a,b):
    if len(a)<3 or a.std()==0 or b.std()==0: return None
    return float(a.corr(b))


def main():
    n6=pd.read_csv(io.StringIO(NOVA6_2025_TAIL),parse_dates=["signal_date","entry_date","exit_date"])
    panel=port.build_panel()
    opp=port.candidate_events(panel,START,END)
    new=port.simulate_strict_pool(opp)
    for c in ["signal_date","entry_date","exit_date"]:
        new[c]=pd.to_datetime(new[c])

    a=new.groupby("signal_date").pl.sum().rename("rebound_pl")
    b=n6.set_index("signal_date").round_pl.rename("nova6_pl")
    sig=pd.concat([a,b],axis=1,join="inner").dropna()
    sig["same_sign"] = np.sign(sig.rebound_pl)==np.sign(sig.nova6_pl)

    na=new.groupby("exit_date").pl.sum().rename("rebound_pl")
    nb=n6.groupby("exit_date").round_pl.sum().rename("nova6_pl")
    dates=pd.date_range(min(na.index.min(),nb.index.min()),max(na.index.max(),nb.index.max()),freq="D")
    daily=pd.concat([na,nb],axis=1).reindex(dates).fillna(0.0)
    daily=daily[daily.abs().sum(axis=1)>0].copy()
    daily["combo_50_50"]=0.5*daily.rebound_pl+0.5*daily.nova6_pl

    active_dates=set(opp.Date.unique())
    n6_active=n6[n6.signal_date.isin(active_dates)].round_pl
    n6_inactive=n6[~n6.signal_date.isin(active_dates)].round_pl

    result={
      "window":{"start":str(START.date()),"end_signal":str(END.date())},
      "rebound_strict":{"pl":float(new.pl.sum()),"mdd":port.max_drawdown_realized(new),"trades":int(len(new)),"signal_dates":int(new.signal_date.nunique())},
      "nova6":{"pl":float(n6.round_pl.sum()),"mdd":mdd(n6.groupby("exit_date").round_pl.sum().sort_index()),"nights":int(len(n6)),"pf":pf(n6.round_pl)},
      "signal_date_overlap":{"n_common":int(len(sig)),"pearson":corr(sig.rebound_pl,sig.nova6_pl),"spearman":float(sig.rebound_pl.corr(sig.nova6_pl,method="spearman")) if len(sig)>=3 else None,"same_sign_rate":float(sig.same_sign.mean()) if len(sig) else None,"rebound_pl_on_common":float(sig.rebound_pl.sum()),"nova6_pl_on_common":float(sig.nova6_pl.sum())},
      "realized_exit_day":{"n_days_union":int(len(daily)),"pearson_with_zeros":corr(daily.rebound_pl,daily.nova6_pl)},
      "nova6_conditioned_on_rebound_opportunity_signal_days":{"active_n":int(len(n6_active)),"active_pl":float(n6_active.sum()),"active_mean":float(n6_active.mean()) if len(n6_active) else None,"inactive_n":int(len(n6_inactive)),"inactive_pl":float(n6_inactive.sum()),"inactive_mean":float(n6_inactive.mean()) if len(n6_inactive) else None},
      "diagnostic_50_50_fixed_capital_split":{"capital_each":500000,"pl":float(daily.combo_50_50.sum()),"return_on_total_1m":float(daily.combo_50_50.sum()/1_000_000.0),"mdd_realized_daily":mdd(daily.combo_50_50),"pf_daily":pf(daily.combo_50_50),"note":"Natural 50/50 diagnostic only; no weight search."}
    }
    sig.to_csv(OUT/"signal_date_overlap.csv")
    daily.to_csv(OUT/"realized_exit_day.csv")
    (OUT/"RESULT.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=True),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=True))

if __name__=="__main__":
    main()
