# N2 Top1 2026 — fixed 5m one-stock countercheck against 100,000 matched random Top1

**Date 2026-11-04. Independent diagnostic only. Verdict: ALPHA_NOT_DEMONSTRATED / TRADING_NO_GO.** Parent frozen 5m-Top1 authority: `edc6a713b6a640738773ba1957d8c95fa82e3b71`; accompanying warning-signal forensics: `501ab651b9380594c00b5c5cb622d1aaa8fc911e`. No production, original selection signals or canonical source modified.

## Protocol and sample
- Exactly seven already-frozen monthly N2 signal dates 2026-01-30 to 2026-08-31. This is **not all of calendar year 2026**; entry dates next session, exit close of 20th session, 1000-share lots, NT$5,000,000 fresh on each event, **no compounding**, 0.4% roundtrip cost.
- Original frozen seven N2 ticker/date/PnL lines crosschecked to source ledgers; for each signal N2 still matches the lowest previous-five-session return in the frozen, signal-side median-turnover **Top100 TWSE electronics pool**.
- For the matched counterfactual choose **one** uniform-random name each event from same 100, on same entry open, same 20th-session exit close, new fixed 5m, board lots, same 40bps. Seed PCG64(20261104), **100,000 independent paths**, seven names per path, cross-date replacement allowed. **All 7×100 name-date entry opens and exits valid**: no price-complete-path conditioning in this *2026* random test, unlike the older 2018–2026 multi-year N3 run. Still raw-price-only; corporate actions not reconciled.

## 2026 results

| Signal | N2 ticker | N2 PnL NT$ | N2 rank percentile within Top100 by same-window *future* PnL |
| --- | --- | ---: | ---: |
| 2026-01-30 | 6282 | -203,510.40 | 22% |
| 2026-03-31 | 4967 | +1,579,042.00 | 75% |
| 2026-04-30 | 8021 | +388,032.00 | 38% |
| 2026-05-29 | 3714 | -774,792.00 | 25% |
| 2026-06-30 | 6442 | -1,684,980.00 | 28% |
| 2026-07-31 | 3026 | **+3,413,080.00** | 96% |
| 2026-08-31 | 3702 | +680,000.00 | 85% |

- Seven-event **non-compound sum +NT$3,396,871.60**, 4 winners / 3 losers, **not** final executable NAV; best 3026 contributes 100.48% of net, without that **-NT$16,208.40 across other six**.
- At only 3/7 event dates N2's selected stock beat the same-date pool's median subsequent price-only outcome, thus insufficient evidence of consistent per-date selection performance.
- Random Top1 across same seven windows: median **+NT$1,826,785.60**, mean **+NT$2,104,351.13**; 2026 N2 is at **71.947th empirical percentile**, i.e. **28.053%** of matched random paths did *better* (100,000/100,000 price-complete). This is a descriptive empirical percentile, **not formal p-value** due ex-post research and remaining data/execution limitations.
- TAIEX price-index close(signal) to close(exit) proxy, seven independently scaled 5m windows: +NT$2,139,775.11. This has **different execution timing** than next-open stock purchase; context only, do not call a true alpha matched index test.
- Historical 2026-06-30 6442 had one 2026-07-15 ex-dividend event, raw cash reference 11.258666/share × 3000 = NT$33,775.998 possible *unverified pretax cash-receipt scenario*; price-only loss still -NT$1,684,980. No complete dividend/rights true total return, trading slippage, or PIT legal share-class certificate. 2025-12-31 signal 2313 (sold in January 2026) **is not part of 2026 signal-year seven-trade cohort**; 2026 vs realised-calendar-year accounting must not be mixed.

## Bottom line

**The 2026 data do not validate an investable or consistently superior N2 Top1 selection rule.** Positive PnL is dominated by a single extreme 3026 win, and same-window fair random Top1 performance often beats it. However **it is also wrong to conclude a mathematical proof of zero predictive value** from just seven retrospectively evaluated events. Status remains `ALPHA_INCONCLUSIVE / TRADING_NO_GO` pending investor-realised corporate-action adjustment, genuine opening fills, and prospective locked rules.

## Reproducibility

Library `/HENGCE/Research Outputs/N2_TOP1_2026_COUNTERCHECK_20261104/HENGCE_N2_TOP1_2026_RANDOM_BENCHMARK_AUDIT_20261104.zip`, ZIP SHA256 `541a93a7b1999c290282c1396d7c15dbe21b0e7400e90a298925462080a0cbe5`. Contains `run.py`, `2026_seven_events_vs_pool_and_taiex.csv`, `summary.json`, `READ_FIRST_2026_REBUTTAL.md`, reproducibility method and per-file SHA256 manifest. Source annual TWSE archive manifest verified by loader. Research-only.
