# HENGCE Escape — Fugle / FinMind / TWSE read-only source reconciliation (2026-11-04)

**Status:** RESEARCH_SHADOW_ONLY. **No formal model, selection, source-of-record, or trading authority.** This does not change Selection Core, Q017, E2, any locked Escape formula, the canonical Historical Mother, or existing EOD data.

## Observations

1. Live stock-specific Fugle quote access succeeded for 2330, 2317, 2454, with 2026-11-04 13:30:00 Asia/Taipei timestamps. These regular-session quote totals must not be passed as full-day EOD volume.
2. Public FinMind `TaiwanStockPrice` (2026-11-04) matched direct official TWSE `STOCK_DAY` **exactly on all tested OHLC, share-volume and trade-value fields for three electronic stocks**. Fugle closing prices for all three matched official closes. Sample is **3 stocks, 1 day**; this does not establish market-wide equivalence.
3. FinMind `TaiwanStockInstitutionalInvestorsBuySell` and `TaiwanStockMarginPurchaseShortSale` were queried for 2330 for 2026-11-03; same-day 2026-11-04 institutional and margin observations were not returned at the time checked.
4. A genuine source-versus-archived T86 discrepancy exists for 2026-11-03. 2330 archive TotalNet = -6,705,803 shares vs current official TWSE and FinMind = -6,699,293 (delta +6,510). 2454 archive TotalNet = -3,344,344 vs current TWSE T86 = -3,347,344 (delta -3,000). The version change cause and original publication timeline **have not been verified**. Do not treat the current value as a silent correction to the archived evidence.
5. Current Fugle basic plan supports per-symbol intraday quote but whole-market `snapshot/quotes/TSE` returned HTTP 403 in the existing pipeline. The existing FinMind aggregate shadow had 1,088/1,088 active monitored shares on 2026-11-04 15:20; this is intraday context, **not** a 17-metric formal detector packet.

## Gate recommendation

- **Fugle:** regular-session, per-symbol intraday, provisional price/liquidity only.
- **FinMind:** historical price and institutional/margin backfill candidate, only after field and PIT validation; do not authorize automatically.
- **TWSE / HENGCE canonical historical mother:** existing formal EOD authority. Distinguish as-observed historical bytes vs later retrievable official snapshot and append reconciliation evidence; no overwrites.
- **Escape:** do not feed `HENGCE_ESCAPE_FEATURE_DETECTOR_V1` until valid PIT daily U/E memberships, canonical full-window joined panel, denominator/time semantics, and source-revision gates pass.
- Normalizing exact volumes requires units/scope proof. Fugle's quote `total.time` is 13:30 whereas TWSE `STOCK_DAY` contains additional after-session transactions. Never use Fugle raw count or a multiplied guess as canonical EOD.

## Query evidence

- Fugle connected `get_realtime_quote` for 2330 / 2317 / 2454 (response as observed 2026-11-04).
- FinMind: https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id=2330&start_date=2026-11-03&end_date=2026-11-04
- FinMind: https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInstitutionalInvestorsBuySell&data_id=2330&start_date=2026-11-03&end_date=2026-11-04
- TWSE: https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date=20261104&stockNo=2330&response=json
- TWSE T86: https://www.twse.com.tw/rwd/zh/fund/T86?response=json&date=20261103&selectType=24
- Historical EOD stored: `eod/20261103/institutional_2.csv`; receipt: `eod/20261103/receipts/mother.json`

Sample checks were exercised in a local, nonproduction research-only Python reconciliation tool using eight passing tests. Code and test fixtures have **not** been executed inside GitHub CI in this branch; this document is the auditable observation record, not proof of a formal pipeline.
