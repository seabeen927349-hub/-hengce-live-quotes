# FIXED 1,000,000 TWSE Selection Null Audit — Frozen Addendum (2026-11-04)

## Authority
Research-only, no strategy/production authority, no modification of existing `HENGCE_SELECTION_CORE_NULL_BASELINE_CONTRACT_V1_20261031`, historical mother, candidate forward-return gates, Q017, or Escape. Base branch SHA `df266cd6dead2f30ac8b981b1d2494caa729d32e`.
**User instruction:** DO NOT COMPOUND. Each of 84 existing monthly selection windows starts with independent NT$1,000,000 and each of 5 selected tickers has an independent NT$200,000 buying-power sleeve. Cash is not recycled between names within that event. No profits/losses affect the next window's share count. We report per-window PnL, sum of these independent PnLs, sum / (84*1m) and PnL per 1m per exposure window. Do NOT label `1m + sum(PnL)` as an executable continuously funded terminal portfolio.

## Frozen investigation method before new recomputation
- Reuse exact previous 84 historical month-end windows, Top100 price/turnover universe and ticker/dates; benchmark N1 prior20 Top5, N2 prior5 Bottom5, N0 all eligible equal-weight theoretical, N3 matched random 5, seed `20261031`, 10,000 paths.
- Month-end signal t after close, next session t+1 open, exit close of 20th session counting entry, nonoverlap, no borrowing or future-open gating, 1 lot=1000 shares. Shares for each ticker = floor(200,000/(entry_open*1000)), no replacement if unaffordable/unpriced.
- 40bp total and separately 80bp, deducted from initial invested nominal; dividends not reinvested. Missing exit price for a purchased name invalidates entire event's formal price-only aggregate; no deletion or survivor filtering.
- Compare equal-date TAIEX price index *at signal close* to exit close, scaled at 1m per window; it is a different timing proxy (not true executable next-open trading). Do not compound index benchmark.
- Corporate actions: inspect official archive `event_type` and `rights_plus_dividend_value`. Cash-only `息` may be reported as an *indicative, unverified* cash credit `shares * value` for ex-date strictly AFTER entry date and on/before exit, with eligibility and source veracity caveats; `權` and `權息` require rights/shares accounting unavailable, flag `UNRESOLVED_RIGHTS`, never convert all `rights_plus_dividend_value` to cash. Events ex-date ON entry are excluded because purchased after ex-date; verify with records. If independent source does not certify cash credits, label all as scenario only; price-only base remains separate.
- Evaluate signal prior5-day/20-day corporate-action exposure as potential rank contamination rather than post-hoc removing losers/winners. Do not silently modify any selections.
- N3 10k paths must carry missing-exit state forward as `BLOCKED`, report numbers; never compare N2 against only future-data-complete paths as a formal percentile. Optional per-event random distribution with all securities price-covered on *that date* is descriptive only and labeled conditional.
- Annual, 2018-24 versus 2025-26, remove best 1/3/5 **per-position** and **per-event**, sensitivity 40bp/80bp, event-level win and sample counts. Year splits already historically exposed and do not establish genuine OOS.
- Treat PIT stock-class coverage, corporate-action rights, adjustment/source revisions, executable opening and TAIEX benchmark binding as separate DATA/VALIDATION blockers. Never claim alpha GO.

No changing event dates, k, 5/20 lookbacks, costs, filters or missingness treatment after seeing outcomes; record code bugs transparently.
