# HENGCE cost-zone audit and correction｜2026-11-05

STATUS: PRIOR COST-ZONE LEADERS ARE **NOT VERIFIED**; study research-only, no selection/capital authority. This correction supersedes the "largest resistance zone" interpretation in `REPORT.md`.

## Audit scope and provenance
- Original 2026-05-05 through 2026-11-04 125 FinMind daily `TaiwanStockPrice` observations for 6415/3042/8150 and 2026-11-05 Fugle close (research-only; 11/05 formal canonical EOD still pending in retrieved receipt).
- Same turnover survival function as prior experiment: `p=1-exp(-alpha * daily_volume / issued_shares)`, alpha=1 for principal comparison; constant issued shares based on TDCC 2026-10-30 used only for retrospective descriptive audit, **not** a point-in-time historical trading signal.
- Bin width remains **5% of 2026-11-05 closing price**, anchored to spot; unlike previous result, full historical price range has **no +60% ceiling**.
- Alternate daily placement: (a) all daily volume assigned to true daily VWAP; (b) daily volume spread uniformly over the day's high/low range. (b) is a sensitivity assumption, **not** actual intraday volume-at-price evidence.
- All percentages are **hypothetical estimated issued-share mass**, NOT a measured proportion of actual underwater shareholders.

## Reproducible correction

| Stock | 11/05 close | Alpha 1, daily VWAP distribution: highest full-range cost band | Estimated weight | Alpha 1, uniform daily high-low distribution: highest cost band | Estimated weight |
|---|---:|---|---:|---|---:|
| 6415 | 412 | 453.20–473.80 | 13.40% | 473.80–494.40 | 13.18% |
| 3042 | 132 | 204.60–211.20 | 15.28% | 178.20–184.80 | 12.95% |
| 8150 | 76 | **125.40–129.20** | **18.69%** | **125.40–129.20** | 12.49% |

### Precisely what failed
1. **8150 omitted larger peak**: former code scanned only about -20% to +60% of spot. 125.4 / 76 - 1 = **+65%**, so this band was not considered. Truncated search declared 98.8–102.6 (14.43%) the largest; untruncated analysis found 125.4–129.2 (18.69%) larger under identical daily-VWAP alpha=1 assumption. **Prior dominant-zone label was wrong**. Even full-range top is unstable under different alpha: alpha=0.25 yields 91.2–95.0 (11.55%) and alpha=2 yields 98.8–102.6 (20.71%). No zone can be promoted as verified actual supply.
2. **3042 volume-placement instability**: VWAP-based top 204.6–211.2 (15.28%) switches to 178.2–184.8 (12.95%) when same daily mass is uniformly spread between that day's actual high and low. Thus the former "main cost band" is not robust to a realistic ambiguity in price distribution. Using a coarser fixed 10-TWD histogram also emphasizes 180–190. No claim that the latter band is true.
3. **6415 top-band ambiguity**: VWAP top 453.2–473.8 (13.40%) shifts to 473.8–494.4 (13.18%) using high-low spread, with the former band 12.32%; interpretation must be a broad **~453–494** price region, not a precise barrier.
4. **Model does NOT observe holder acquisition cost or position survival**. Issued shares aren't free float; high turnover can recycle the same shares repeatedly. 3042/8150 previously estimated as nearly 100% underwater is not justified as real P&L.
5. **Historical point-in-time integrity**: six-month past TDCC snapshots are research backfill first obtained on 2026-10-29; they cannot be treated as known live on 2026-08-05 to 2026-10-28. Previously using TDCC 2026-10-30 share count as denominator for earlier anchors is forward-looking. A corrected PIT simulation must use historical as-of-valid outstanding shares or remain unknown.
6. **Three-month validation targets are inconsistent**: `VALIDATION_3M_STRICT_TOUCH_PLUS5.json` only looked at 5%-20% above each anchor spot, while 3042's reported band is 55% above its 11/05 spot and 8150's corrected peak is 65% above its 11/05 spot. The previous 4 declines / 7 touched zones neither verifies these reported primary peaks nor establishes alpha; there is no statistically credible incremental advantage over simple price-volume. Those zones must not be presented as "validated resistance".
7. Backtest uses daily OHLC touch (without intraday sequencing or execution prices) and three linked securities; neither sample independence nor real sell-side execution is established.

## Revisions required before making predictions
- Separate (i) transaction **volume-at-price**, (ii) estimated **remaining position cost**, and (iii) **future supply pressure**; do not relabel the first as the latter two.
- Never pre-truncate the search without labeling the explicit distance band. Publish *full-price-range*, *nearest-above-price*, and *top-density* bands separately; fix bin-width and price-handling conventions in advance.
- For historical simulation use **as-of available** share-capital and TDCC timestamps, or omit the feature.
- Require robustness across alpha, range-volume placement, 60d/126d histories and bin widths; if top-price region shifts materially, mark `ZONE_UNSTABLE_NO_SIGNAL`.
- Compare against plain price-volume and recent swing-high baseline at **matched opportunity events**, with non-overlapping forward outcome windows and explicit no-contact outcomes. Any parameter selection after inspecting 3-month outcomes is **exploratory and cannot be validated on the same 3 months**.
- Until independent forward validation: **INVALID_FOR_TRADING / NO_PROMOTION_TO_CANONICAL / NO_RANKING_SIGNAL**.

Related source receipts: `eod/20261104/status.json`, `eod/20261104/receipts/mother.json`, `ownership/tdcc/20261030/receipt.json`, `ownership/tdcc/backfill_candidate/wirelessr/20260508/receipt.json`.
