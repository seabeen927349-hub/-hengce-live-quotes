# HENGCE LOSS FORENSICS — Swing Lifecycle V0
Date: 2026-11-01
Status: RETROSPECTIVE FORENSICS / NOT A TRADING MODEL
Universe: bound TWSE electronics 100-stock pilot
Data: HENGCE 2026 daily mother + TWSE price/margin/institutional + current100 weekly TDCC ownership audit

## Question
What tends to accompany the full rise/fall lifecycle of a stock, and why does the retail experience often feel like `I buy -> it falls; I sell -> it rises`?

## Method
This is deliberately retrospective. Major swings are segmented with a 12% zig-zag reversal definition so the full lifecycle can be inspected after the fact. The same exercise was repeated at 8% and 15% reversal scales as a robustness check. A 12% segmentation produced 548 complete up legs and 513 complete down legs in 2026 through the available daily mother window.

Each leg is divided by elapsed leg time into EARLY / MID / LATE. Daily features include 5d margin-balance change, volume relative to trailing-20d median, institutional flow/volume, transaction-count relative to trailing median, close-location value, and price state. Weekly ownership uses Big400 / Big1000 / Mid and total-holder counts from the current100 TDCC audit.

This is not prospective alpha validation. Turning points are known ex post by construction.

## 1. The strongest lifecycle shape: leveraged retail arrives late and leaves late
Median 5-trading-day margin-balance change:

| Phase | Median 5d margin change | Median volume / 20d median |
|---|---:|---:|
| UP EARLY | -1.59% | 0.96x |
| UP MID | +0.44% | 1.05x |
| UP LATE | +2.16% | 1.23x |
| DOWN EARLY | +0.44% | 1.13x |
| DOWN MID | -0.88% | 0.83x |
| DOWN LATE | -2.04% | 0.85x |

Leg-level paired check: among 502 up legs with usable early/late margin data, LATE margin growth exceeded EARLY in 65.3% of legs; median late-minus-early difference was +4.94 percentage points. Among 487 down legs, late margin change was lower than early in 67.1%; median late-minus-early difference was -5.03 percentage points.

The shape survives 8%, 12%, and 15% swing definitions:
- UP EARLY margin change remains negative at all three scales; UP LATE remains positive.
- DOWN EARLY remains slightly positive; DOWN LATE remains about -2%.

Interpretation: leveraged retail is not generally the first cohort into a major rise. It tends to add leverage after price proof/attention has already accumulated. During declines, leverage does not fully leave early; deleveraging becomes strongest late.

## 2. Tops look bullish, not bearish
For 12% interior swing peaks (492 events before corporate-action exclusion):
- median 20d return entering the peak: +28.2%
- peak-day volume: 1.53x trailing-20d median
- peak-day transaction count: 1.44x trailing median
- 5d margin change: +3.85%
- daily foreign-flow / volume median: +4.73%
- daily total-institution flow / volume median: +7.15%
- close location in daily range: ~81%

Five sessions later, median price was already -12.0% from the peak, margin balance was -4.64% from the peak level, and institutional flow medians had turned negative.

This is crucial: the modal visible picture at a major top is not `everything looks bad`. It is high attention, high volume, strong close, rising leverage and still-positive visible institutional demand.

## 3. Bottoms look bearish, not bullish
For 12% interior swing troughs (471 events):
- 5d margin change at the trough: -4.19%
- foreign and total institutional flow medians were negative
- close location was only ~15% of the daily range
- Big400 / Big1000 latest weekly change around the trough was usually still negative

Five sessions after the trough, median price was already +13.9% and margin balance +3.63% from the trough level.

Thus the data confirming that `things are bad` often coincide with or lag the end of the decline. A trader who requires emotional/visible confirmation before selling naturally sells late.

## 4. Ownership transfer appears AFTER many peaks
Using TDCC snapshots roughly 4-11 calendar days after each 12% peak:
- 489 usable peak events
- median Big400 change: -0.44 percentage points
- median Big1000 change: -0.49pp
- Big400 fell in 73.2% of events
- where total-holder counts were available (324 events), median holder-count change was +2.49%
- holder count rose in 78.7%
- joint `Big400 down + holder count up` occurred in 64.8% of those holder-count observations

The mirror after troughs is materially different (466 events, roughly 4-11 days later):
- median Big400: +0.08pp
- median Big1000: +0.09pp
- median total-holder count: -0.66%
- Big400 fell only 41.8%
- holder count rose only 38.7%

Interpretation: after many peaks, inventory becomes more dispersed at the same time large-holder concentration falls. After many troughs, concentration begins to rebuild and holder count contracts. This is exactly the inventory-transfer geometry that can create a retail-late-entry / retail-late-exit experience.

## 5. The first outflow is not enough: REPAIR is a critical branch
Among peak events where the post-peak TDCC snapshot (4-11 days later) showed Big400 outflow and the following weekly snapshot was observable:
- FAILED REPAIR: n=302; median next down-leg depth -21.29%; first post-peak Big400 median -0.965pp and second snapshot -0.335pp; holder count kept increasing.
- REPAIR: n=50; median next down-leg depth -17.05%; first outflow -0.655pp, then second snapshot +1.88pp; holder count contracted on the repair snapshot.

Among trough events with initial post-trough Big400 reconcentration:
- RETAINED RECONCENTRATION: n=196; median next up-leg +42.92%.
- FAILED RECONCENTRATION: n=62; median next up-leg +32.11%.

These return magnitudes are descriptive and mechanically conditioned on ex-post swing formation. The useful structural point is the branch: outward transfer that is rapidly repaired behaves differently from persistent leakage; post-trough concentration that persists behaves differently from a one-week bounce.

## 6. Price / volume alone cannot solve the problem
At 20-day-high breakout events, both successful continuations and future traps commonly show high volume, high transaction counts, positive recent institutional flow and rising margin. The visible breakout itself does not cleanly separate them.

Therefore the forensic object is not `breakout = buy` or `high volume = top`. The object is the lifecycle of inventory and financing after attention arrives:

`attention / repricing -> who finances the next price -> ownership transfer or repair -> persistence or failure`.

## 7. Why the retail experience feels personalized
The current evidence supports a cohort-timing explanation rather than a market targeting individual accounts.

1. Attention is endogenous to late-stage movement. Stocks become salient after large returns, news, abnormal volume and transaction counts; this expands the pool of potential retail buyers.
2. Margin leverage is pro-cyclical at the swing scale: it rises late in rallies and is cut late in declines.
3. Strong holders need counterparties. High price/attention creates liquidity for outward inventory transfer; fear and forced deleveraging create liquidity for reconcentration.
4. Public evidence is lagged. At peaks, many visible indicators remain positive; after several sessions of decline, the negative ownership/flow evidence becomes clearer. At troughs the reverse occurs.
5. An individual's order is too small to `cause` the reversal, but many investors respond to the same salient signal at the same phase. Their trades are therefore statistically clustered near the same points.
6. Memory then amplifies the effect: immediate post-trade reversals are salient and remembered; uneventful trades are not.

## 8. External evidence consistent with the mechanism
- TWSE reports that domestic individuals were ~52% of listed-market trading value in Jan-Jul 2026, but more than 98% of margin trading at end-July was attributable to individuals. Therefore margin balance is a narrow but strong leveraged-retail proxy, not a proxy for all retail activity.
- Taiwan full-account research (Barber, Lee, Liu, Odean) found that aggregate individual trading suffered a large performance penalty and that virtually all losses were attributable to aggressive orders.
- Attention research finds individuals disproportionately buy attention-grabbing stocks (news, abnormal volume, extreme returns).
- Taiwan disposition-effect research found investors were roughly twice as likely to sell a position held at a gain versus a loss, with 84% of investors selling winners faster than losers.

## 9. Important counterpoints / limits
- `Retail` is heterogeneous. Margin accounts represent leveraged retail, not every individual investor.
- Taiwan microdata research also finds short-horizon contrarian individual behavior (buying after negative days / selling after positive days). This does not contradict the multi-week margin-cycle finding; it means retail timing depends on horizon and account type.
- Big400/Big1000 are holder tiers, not verified beneficial owners.
- Weekly TDCC timing is coarse. The 4-11-day post-turn result describes ownership migration around a turn; it is not an exact intraday causal timestamp.
- Corporate actions can create mechanical price/holder-tier shifts. A first event-category exclusion of dividend/capital events within ±2 calendar days removed only ~0.8% of the 12% turning points; peak/trough profiles remained qualitatively unchanged. A full corporate-action-continuous reconstruction is still desirable.
- The repair-return comparisons are retrospective descriptive statistics, not tradable expected returns.

## Current answer
The strongest current explanation for `I buy and it falls; I sell and it rises` is not that the market observes an individual's order. It is that common retail decision rules are synchronized with the stock lifecycle.

A typical losing sequence is:

`price becomes visible -> attention rises -> leveraged retail arrives -> strong close / high volume / public flows still look good -> inventory starts transferring outward -> holder count broadens -> repair fails -> price falls -> negative evidence becomes obvious -> leveraged retail deleverages late -> ownership begins reconcentrating -> price rebounds`.

This is a structural timing problem: the information that feels most emotionally convincing is often strongest near the end of the move it describes.
