from __future__ import annotations

import importlib.util
import io
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "results/compare_nova6_rebound_20261026"
OUT.mkdir(parents=True, exist_ok=True)

# Import unchanged frozen signal + fixed-capital simulator.
spec = importlib.util.spec_from_file_location("port", HERE / "frozen_1m_portfolio_20261026.py")
port = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(port)

# Canonical audited NOVA6 recent-3M event ledger copied verbatim from
# HENGCE_NOVA6_AUDITED_EVENTS_20261026.csv (round_pl column).
NOVA6 = """signal_date,entry_date,exit_date,round_pl
2026-07-21,2026-07-22,2026-07-23,1495.0000000000086
2026-07-22,2026-07-23,2026-07-24,-19660.00000000002
2026-07-23,2026-07-24,2026-07-27,-14738.400000000016
2026-07-24,2026-07-27,2026-07-28,-29189.59999999996
2026-07-27,2026-07-28,2026-07-29,-11215.79999999994
2026-07-28,2026-07-29,2026-07-30,-15234.00000000003
2026-07-29,2026-07-30,2026-07-31,55112.79999999997
2026-07-30,2026-07-31,2026-08-03,10669.600000000046
2026-07-31,2026-08-03,2026-08-04,-11982.39999999995
2026-08-03,2026-08-04,2026-08-05,41028.00000000009
2026-08-04,2026-08-05,2026-08-06,-15311.999999999962
2026-08-05,2026-08-06,2026-08-07,-8411.999999999958
2026-08-06,2026-08-07,2026-08-10,-3292.0
2026-08-07,2026-08-10,2026-08-11,47051.99999999999
2026-08-10,2026-08-11,2026-08-12,41563.99999999999
2026-08-11,2026-08-12,2026-08-13,54686.00000000006
2026-08-12,2026-08-13,2026-08-14,11067.999999999984
2026-08-13,2026-08-14,2026-08-17,8855.999999999958
2026-08-14,2026-08-17,2026-08-18,-5196.000000000004
2026-08-17,2026-08-18,2026-08-19,-61957.99999999999
2026-08-18,2026-08-19,2026-08-20,31060.00000000002
2026-08-19,2026-08-20,2026-08-21,-6446.000000000013
2026-08-20,2026-08-21,2026-08-24,-11188.800000000028
2026-08-21,2026-08-24,2026-08-25,-6812.399999999992
2026-08-24,2026-08-25,2026-08-26,-5882.000000000004
2026-08-25,2026-08-26,2026-08-27,4871.200000000064
2026-08-26,2026-08-27,2026-08-28,34947.8
2026-08-27,2026-08-28,2026-08-31,48501.99999999994
2026-08-28,2026-08-31,2026-09-01,-44634.79999999999
2026-08-31,2026-09-01,2026-09-02,-16759.600000000024
2026-09-01,2026-09-02,2026-09-03,-25327.399999999918
2026-09-02,2026-09-03,2026-09-04,16000.400000000038
2026-09-03,2026-09-04,2026-09-07,-5084.79999999995
2026-09-04,2026-09-07,2026-09-08,-18819.599999999988
2026-09-07,2026-09-08,2026-09-09,25012.00000000001
2026-09-08,2026-09-09,2026-09-10,-5794.000000000022
2026-09-09,2026-09-10,2026-09-11,-24212.0
2026-09-10,2026-09-11,2026-09-14,-36331.00000000001
2026-09-11,2026-09-14,2026-09-15,-4472.000000000062
2026-09-14,2026-09-15,2026-09-16,6626.800000000007
2026-09-15,2026-09-16,2026-09-17,50597.59999999998
2026-09-16,2026-09-17,2026-09-18,27891.599999999937
2026-09-17,2026-09-18,2026-09-21,-187.6000000000217
2026-09-18,2026-09-21,2026-09-22,15960.000000000036
2026-09-21,2026-09-22,2026-09-23,8418.599999999911
2026-09-22,2026-09-23,2026-09-24,-4156.800000000003
2026-09-23,2026-09-24,2026-09-29,7128.3999999999205
2026-09-24,2026-09-29,2026-09-30,2507.9999999999045
2026-09-29,2026-09-30,2026-10-01,-6089.600000000022
2026-09-30,2026-10-01,2026-10-02,1432.0000000000005
2026-10-01,2026-10-02,2026-10-05,28741.800000000087
2026-10-02,2026-10-05,2026-10-06,14850.800000000025
2026-10-05,2026-10-06,2026-10-07,45310.99999999995
2026-10-06,2026-10-07,2026-10-08,-14170.800000000005
2026-10-07,2026-10-08,2026-10-12,-23398.40000000003
2026-10-08,2026-10-12,2026-10-13,-28379.20000000004
2026-10-12,2026-10-13,2026-10-14,19232.79999999995
2026-10-13,2026-10-14,2026-10-15,-47354.80000000003
2026-10-14,2026-10-15,2026-10-16,9510.40000000004
2026-10-15,2026-10-16,2026-10-19,1682.399999999962
2026-10-16,2026-10-19,2026-10-20,5614.399999999979
2026-10-19,2026-10-20,2026-10-21,29872.400000000023
2026-10-20,2026-10-21,2026-10-22,46304.39999999996
"""


def mdd_from_daily(s: pd.Series) -> float:
    c = s.cumsum()
    peak = c.cummax().clip(lower=0)
    return float((c - peak).min())


def pf(s: pd.Series):
    pos = float(s[s > 0].sum()); neg = float(-s[s < 0].sum())
    if neg == 0: return math.inf if pos > 0 else None
    return pos / neg


def corr(a: pd.Series, b: pd.Series):
    if len(a) < 3 or a.std() == 0 or b.std() == 0: return None
    return float(a.corr(b))


def main():
    n6 = pd.read_csv(io.StringIO(NOVA6), parse_dates=["signal_date","entry_date","exit_date"])
    panel = port.build_panel()
    opp = port.candidate_events(panel, port.RECENT_START, port.RECENT_END)
    new = port.simulate_strict_pool(opp)
    for c in ["signal_date","entry_date","exit_date"]:
        new[c] = pd.to_datetime(new[c])

    # Strategy-logic comparison: aggregate each strategy by signal date.
    a = new.groupby("signal_date").pl.sum().rename("rebound_pl")
    b = n6.set_index("signal_date").round_pl.rename("nova6_pl")
    sig = pd.concat([a,b],axis=1,join="inner").dropna()
    sig["same_sign"] = np.sign(sig.rebound_pl) == np.sign(sig.nova6_pl)

    # Realized daily P/L comparison: aggregate by actual exit day, zeros on dates where one is inactive.
    na = new.groupby("exit_date").pl.sum().rename("rebound_pl")
    nb = n6.groupby("exit_date").round_pl.sum().rename("nova6_pl")
    dates = pd.date_range(min(na.index.min(),nb.index.min()), max(na.index.max(),nb.index.max()), freq="D")
    daily = pd.concat([na,nb],axis=1).reindex(dates).fillna(0.0)
    # Keep only dates where at least one strategy realizes P/L; weekends with both 0 add no information.
    daily = daily[(daily.abs().sum(axis=1) > 0)].copy()
    daily["combo_50_50"] = 0.5*daily.rebound_pl + 0.5*daily.nova6_pl

    # Does NOVA6 behave differently on rebound trigger dates?
    active_dates = set(opp.Date.unique())
    n6_active = n6[n6.signal_date.isin(active_dates)].round_pl
    n6_inactive = n6[~n6.signal_date.isin(active_dates)].round_pl

    result = {
      "rebound_strict_3m": {
        "pl": float(new.pl.sum()), "mdd": port.max_drawdown_realized(new), "trades": int(len(new))
      },
      "nova6_3m": {
        "pl": float(n6.round_pl.sum()), "mdd": mdd_from_daily(n6.groupby("exit_date").round_pl.sum().sort_index()), "nights": int(len(n6)), "pf": pf(n6.round_pl)
      },
      "signal_date_overlap": {
        "n_common": int(len(sig)),
        "pearson": corr(sig.rebound_pl,sig.nova6_pl),
        "spearman": float(sig.rebound_pl.corr(sig.nova6_pl,method="spearman")) if len(sig)>=3 else None,
        "same_sign_rate": float(sig.same_sign.mean()) if len(sig) else None,
        "rebound_pl_on_common": float(sig.rebound_pl.sum()) if len(sig) else 0.0,
        "nova6_pl_on_common": float(sig.nova6_pl.sum()) if len(sig) else 0.0,
      },
      "realized_exit_day": {
        "n_days_union": int(len(daily)),
        "pearson_with_zeros": corr(daily.rebound_pl,daily.nova6_pl),
      },
      "nova6_conditioned_on_rebound_opportunity_signal_days": {
        "active_n": int(len(n6_active)),
        "active_pl": float(n6_active.sum()),
        "active_mean": float(n6_active.mean()) if len(n6_active) else None,
        "inactive_n": int(len(n6_inactive)),
        "inactive_pl": float(n6_inactive.sum()),
        "inactive_mean": float(n6_inactive.mean()) if len(n6_inactive) else None,
      },
      "diagnostic_50_50_fixed_capital_split": {
        "capital_each": 500000,
        "pl": float(daily.combo_50_50.sum()),
        "return_on_total_1m": float(daily.combo_50_50.sum()/1_000_000.0),
        "mdd_realized_daily": mdd_from_daily(daily.combo_50_50),
        "pf_daily": pf(daily.combo_50_50),
        "note": "Diagnostic natural split only; no weight search. P/Ls scale linearly from each strategy's fixed-1m ledger."
      }
    }
    sig.to_csv(OUT/"signal_date_overlap.csv")
    daily.to_csv(OUT/"realized_exit_day.csv")
    (OUT/"RESULT.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=True),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=True))

if __name__ == "__main__":
    main()
