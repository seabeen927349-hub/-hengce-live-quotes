#!/usr/bin/env python3
"""Independent descriptive same-window 2026 N2 Top1 vs TWSE TAIEX price-index benchmark.

No new selector; frozen seven trades are read-only from the original 84-row ledger.
The TAIEX is not directly tradable. This is a NAV-style index-level comparison
with symmetric *hypothetical* 0.4%/0.8% turnover deductions, not ETF fill proof.

Source: Taiwan Stock Exchange official index daily monthly OHLC data:
https://www.twse.com.tw/rwd/zh/TAIEX/MI_5MINS_HIST?response=html&date=YYYYMM01
"""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd

# Entry OPEN & exit CLOSE, transcribed from TWSE monthly issued historical tables,
# independently checked against each window's actual entry and exit dates.
INDEX = [
    ("2026-02-02", "2026-03-11", 32008.46, 34114.19),
    ("2026-04-01", "2026-04-30", 31892.33, 38926.63),
    ("2026-05-04", "2026-05-29", 39228.39, 44732.94),
    ("2026-06-01", "2026-06-29", 44872.82, 44999.90),
    ("2026-07-01", "2026-07-29", 46234.70, 40039.18),
    ("2026-08-03", "2026-08-28", 42780.42, 46331.45),
    ("2026-09-01", "2026-09-30", 46177.11, 47940.13),
]


def run(ledger, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    origin = Path(ledger)
    frozen = pd.read_csv(origin, dtype={"ticker": "str"})
    cohort = frozen[frozen["signal"].str.startswith("2026")].copy()
    assert len(frozen) == 84 and len(cohort) == 7
    assert (cohort["budget"] == 5_000_000).all()
    assert cohort["ticker"].tolist() == ["6282", "4967", "8021", "3714", "6442", "3026", "3702"]
    idx = pd.DataFrame(INDEX, columns=["entry", "exit", "taiex_entry_open", "taiex_exit_close"])
    x = cohort.merge(idx, on=["entry", "exit"], how="inner", validate="one_to_one")
    assert len(x) == len(cohort) == len(idx)
    assert x.index.is_unique
    assert (x["shares"] % 1000 == 0).all()
    assert (x["invested"] <= 5_000_000).all()
    assert (x["taiex_entry_open"] > 0).all()
    assert (x["taiex_exit_close"] > 0).all()
    x["taiex_price_return"] = x.taiex_exit_close/x.taiex_entry_open - 1
    for bps, label in [(0.004, "40bp"), (0.008, "80bp")]:
        x[f"taiex_index_hypothetical_pnl_{label}"] = 5_000_000 * (x.taiex_price_return - bps)
        x[f"n2_excess_pnl_{label}"] = x[f"pnl_{label}"] - x[f"taiex_index_hypothetical_pnl_{label}"]
    x["taiex_source_entry"] = x.entry.str[:7].str.replace("-", "", regex=False) + "01"
    x["taiex_source_exit"] = x.exit.str[:7].str.replace("-", "", regex=False) + "01"
    for k in ["taiex_source_entry", "taiex_source_exit"]:
        x[k] = x[k].map(lambda m: f"https://www.twse.com.tw/rwd/zh/TAIEX/MI_5MINS_HIST?response=html&date={m}")
    x.to_csv(out/"2026_n2_vs_taiex_open_to_close_same_windows.csv",index=False,float_format="%.10f")
    best = x.loc[x.pnl_40bp.idxmax()]
    other = x[x.index != best.name]
    summary = {
        "status":"RETROSPECTIVE_DESCRIPTIVE_ONLY_TRADING_NO_GO",
        "frozen_sample":"2026 signals 7 of the original 84; no ticker or date substitution",
        "method":"index entry open -> 20th session exit close, NT$5m hypothetical independent capital each window, 40/80bp symmetrical roundtrip costs, N2 from frozen ledger",
        "source_sha256": hashlib.sha256(origin.read_bytes()).hexdigest(),
        "frozen_events":len(x),
        "n2_price_pnl_40bp":round(float(x.pnl_40bp.sum()),2),
        "taiex_hypothetical_price_pnl_40bp":round(float(x.taiex_index_hypothetical_pnl_40bp.sum()),2),
        "n2_excess_vs_taiex_40bp":round(float(x.n2_excess_pnl_40bp.sum()),2),
        "n2_price_pnl_80bp":round(float(x.pnl_80bp.sum()),2),
        "taiex_hypothetical_price_pnl_80bp":round(float(x.taiex_index_hypothetical_pnl_80bp.sum()),2),
        "n2_excess_vs_taiex_80bp":round(float(x.n2_excess_pnl_80bp.sum()),2),
        "n2_beats_taiex_windows":int((x.n2_excess_pnl_40bp>0).sum()),
        "n2_loses_taiex_windows":int((x.n2_excess_pnl_40bp<0).sum()),
        "top_n2_trade_ticker":str(best.ticker),
        "top_n2_trade_40bp":round(float(best.pnl_40bp),2),
        "top_trade_excess_40bp":round(float(best.n2_excess_pnl_40bp),2),
        "without_top_n2_pnl_40bp":round(float(other.pnl_40bp.sum()),2),
        "without_top_taiex_pnl_40bp":round(float(other.taiex_index_hypothetical_pnl_40bp.sum()),2),
        "without_top_excess_40bp":round(float(other.n2_excess_pnl_40bp.sum()),2),
        "qualifications":[
           "TWSE TAIEX is an untradeable index; 0.4/0.8% assumed index cost is illustrative, not certified ETF implementation.",
           "TAIEX price index and frozen N2 price-only ledger exclude total return entitlements; 6442 has a holding-period cash dividend omitted from frozen ledger.",
           "Neither N2 5m opening fills nor a matching ETF index-fill has been verified; both remain execution-data blocked.",
           "2026 has been used for retrospective N2 strategy evaluation; this is not pristine forward validation.",
           "The matched seven independent windows are not the same as a one-time Jan-Sep buy-and-hold or a single constantly invested account."
        ]
    }
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    return summary

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--ledger", required=True)
    p.add_argument("--output", required=True)
    a=p.parse_args()
    print(json.dumps(run(a.ledger,a.output),ensure_ascii=False,indent=2))
