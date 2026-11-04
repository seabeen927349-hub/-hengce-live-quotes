# HENGCE | 4770 broker-flow ex-post audit (2026-11-04)

**Authority:** DESCRIPTIVE_ONLY_NO_SELECTION_ALPHA_OR_TRADING_AUTHORITY.
**Scope:** The user's inquiry: did the same money that bought 4770 on 2026-11-03 drive the 2026-11-04 rebound? This question was asked **after** the 2026-11-04 intraday rebound had already been observed. Therefore this is **ex-post**, not an ex-ante prediction, an OOS success, or a model-development authorization.

## Source audit
- Official HENGCE public EOD three-leg source: `eod/20261103/status.json` COMPLETE; 4770 EOD in `price_4.csv`, `institutional_4.csv`, `margin_4.csv`.
- 2026-11-03: open 283, high 284.5, low 266.5, close 276, traded 1,334,011 shares; T86 combined net +93,746 shares; MI_MARGN margin ending lots 1,472 vs prior 1,599 (delta -127 lots).
- Official HENGCE broker-concentration sidecar `eod/20261103/broker_hhi.csv`: 4770 `BROKER_GROSS_HHI_1D = 0.030347852000761642`. A **gross HHI alone** cannot establish direction, identity or a causal driver; without a valid comparable baseline, no percentile or abnormality claim.
- Independently reported 2026-11-03 broker-branch leaders (third-party public aggregations, **NOT** an independently downloaded canonical TWSE BSR broker-by-broker report): Nomura net +76 lots, KGI Taipei +74, Goldman Sachs Asia +42, UBS Singapore +33, Fu Bang +30. See https://berich.cc/stock/4770?branch=918A&card=inventory ; and https://histock.tw/stock/4770 . Beware broker-group vs specific-branch names are not interchangeable.
- Reported 2026-10-28 through 2026-11-03 cumulative branch-flow leaders differ from single-day list: https://signova.tw/stock/4770 ; do **not** infer that a specific single account accumulated from the differences.
- Public TWSE BSR description: aggregated broker brokerage + dealer orders, no direct beneficial-owner mapping: https://bsr.twse.com.tw/bshtm/bsWelcome.aspx
- License boundary: do NOT commit paid FinMind sponsor or Fugle per-security live quotes, raw broker tables, precise order book or private snapshots to public repository; use links and high-level observations only.

## Causal interpretation and rival explanations
- 11/03 falling price plus aggregated branch net buying supports a *limited* observation: some named execution venues were net buyers into a falling close.
- **Not established:** same beneficial owner, same institutional capital, trading intent, persistence to 11/04, or that these net purchases caused the next session's rebound.
- 11/04 opening gap and intraday reversal should be decomposed using the **official next-session OHLC after close** (not a public archived paid live snapshot), to distinguish an opening gap from a sustained aggressive-buyer drive.
- Bid/ask executed volume bucket alone cannot establish broker identity or larger position accumulation.
- Rival mechanisms: multiple unrelated clientele at same broker, short-cover / intraday unwind, broad-market relief rally, passive hedging, or liquidity recovery. These have **not** been eliminated.

## Next check after 2026-11-04 official publication
1. Verify official 11/04 final OHLC, trades and volume from canonical EOD (not pre-close quotes).
2. Obtain lawfully accessible, permitted official 11/04 **broker branch** daily net flow under appropriate terms. Reconcile broker branch IDs (not aliases/group totals), compare the five 11/03 venues' 11/04 **net** buying/selling and 3~5-session accumulation, including missing coverage. A broker-level repeat is still not a beneficial-owner identifier.
3. Compare official 11/04 T86 aggregate, MI_MARGN balance changes and broker HHI, while keeping the three mechanisms distinct (institutional category, execution venue, leverage).
4. Present alternative explanations alongside the evidence. If source unavailable, mark **NOT_VERIFIABLE**, not "smart money confirmed".
5. This study is descriptive and already exposed to 11/04 outcome. Must **not** reselect original seven recommendation cohort, derive a trading rule, tune HENGCE Selection Core, or use 11/04 as untouched prospective test.

**Current conclusion:** 11/03 branch-level net buyers can be named from third-party data, but the identity or continuity of 11/04 rebound buyers is **NOT_VERIFIED** before official 11/04 broker data.
