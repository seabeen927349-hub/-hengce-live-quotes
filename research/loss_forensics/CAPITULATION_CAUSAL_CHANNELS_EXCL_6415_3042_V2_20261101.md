# HENGCE LOSS FORENSICS — Capitulation Causal Channels V2
Date: 2026-11-01
Status: RETROSPECTIVE FORENSICS / NOT A TRADING MODEL / NOT A MANIPULATION CLAIM

Excluded throughout: 6415, 3042.
Sample: 503 complete 2026 peak-to-trough legs from the remaining bound electronics universe.

## Existing price-path taxonomy
Five mutually exclusive ways the decline feels to the holder:
- rebound torture: 169 (33.6%)
- one-way deceleration: 107 (21.3%)
- mixed decline: 84 (16.7%)
- fast crash: 80 (15.9%)
- slow grind: 63 (12.5%)

This file asks a different question: which underlying pressure channels generate those pain paths?

## 1. There is no reliable single pre-peak villain signature
Event-aligned medians from t-20 to peak show that the visible picture becomes more bullish, not less:
- 5d margin change: about -0.2% at t-20, -1.4% at t-10, ~0% at t-5, +1.4% at t-2, +2.9% at t-1, +3.6% at peak.
- 5d average institutional flow intensity rises into the peak.
- volume ratio rises to ~1.53x trailing median at peak.
- transaction-count ratio rises to ~1.44x.
- close location rises to ~0.81.
- 5d short-balance percentage change rises sharply into the peak.

However a same-stock matched-control test was run for 439 peaks. Each peak was paired to another day in the same stock with similar 5d/20d return, volume ratio, transaction ratio and close-location, excluding days within ±5 trading sessions of another major peak.

Result: short build, short percentage change, margin growth, 5d institutional flow and same-day institutional flow were NOT materially different between peaks and matched strong-but-not-peak days (paired Wilcoxon p-values all >0.3; institutional comparisons ~0.8-0.96).

Interpretation: `shorts rising`, `margin rising`, `institutions buying`, `high volume` and `strong close` are features of strong/attention-heavy days in general. They do not uniquely identify the coming peak.

This is a central reason retail can be trapped: the final peak often looks statistically similar to a legitimate continuation day using the most visible daily variables.

## 2. Earliest ownership deterioration is suggestive, but not a clean advance warning
Among events with holder-count data:
- 8-14 days before peak, a `Big400 down + holder count up` state occurred in 117/256 valid events.
- conditional on this pre-peak dispersion, later failed-repair rate was ~51.3% versus ~42.4% without it; median complete decline ~-22.6% vs ~-20.6%.
- failed-repair events had median pre-peak 8-14d Big400 change about -0.17pp and holder count +0.98%; repair events about -0.005pp and +0.16%.
- in the last 0-7d before peak, failed-repair events had median holder-count change +0.62% versus repair -0.52%.

But these differences are not statistically clean in the current sample (e.g. 8-14d pre-dispersion Fisher p ~0.30; last-week holder-change rank test p ~0.09). Treat as a structural clue, not an early-warning rule.

## 3. Six underlying pressure channels
These channels overlap; one episode can contain several.

### Channel A — Systemic synchronization / broad-market shock
Using all TWSE-listed stocks, 293/503 peak episodes (58.3%) encountered a session with >80% of listed stocks down within the next 10 calendar days.
- systemic-window episodes: median complete decline about -21.6%
- non-systemic episodes: median about -17.2%

Many major peaks cluster on the same dates. Therefore a large share of capitulation is not explainable as one stock being individually manipulated. Broad risk-off shocks synchronize stop-losses, risk limits, leverage reduction and liquidity withdrawal.

### Channel B — Fast-capital reversal while slow leverage remains
At the peak, ~71% of events still have positive same-day total institutional flow; next session visible professional/institutional flow often reverses quickly, while 5d margin change remains positive.
This is a reaction-speed asymmetry: faster capital can stop paying or sell before leveraged/confirmation-seeking holders leave.
It creates the first liquidity vacuum, but institutional flip alone does not separate deep from shallow declines well.

### Channel C — Persistent sponsorship loss / failed ownership repair
Failed repair occurs in 229/503 (45.5%).
This channel is strongest in:
- slow grind: 57.1% failed repair, only 14.3% repair
- rebound torture: 53.8% failed repair, 23.1% repair
- fast crash: only 33.8% failed repair vs 36.2% repair

Interpretation: long painful declines are much more often associated with persistent ownership deterioration than fast crashes are. In a slow grind, the key pressure is not necessarily forced leverage liquidation; it is absence of a strong sponsor willing to rebuild inventory.

### Channel D — Hope-reset / rebound torture
169 episodes show at least one >=5% rebound from a running low before the final trough.
- median first >=5% rebound arrives around trading day 7 of the decline.
- 39/169 episodes have two or more separate >=5% rebound episodes.
- multiple-rebound episodes last a median ~27 trading sessions and decline ~-27.4% in total.
- failed repair remains common (~51-55%).

Mechanism: temporary price recovery restores conviction without restoring the underlying ownership sponsor. The rebound delays exit; the next low converts hope into capitulation.

### Channel E — Leverage/panic capitulation at the end
Across all 503 episodes:
- peak median 5d margin change ~+3.6%
- trough median ~-3.7%
- 41.7% explicitly transition from positive peak margin change to negative trough margin change.

But TWSE market-wide evidence for Jan-Jul 2026 reports maintenance ratios well above the 130% call threshold and forced-liquidation amounts small relative to market turnover. Therefore `all late selling = margin calls` is false. Much of the negative margin change is voluntary de-risking, repayment, or selective constraint rather than system-wide forced liquidation.

The distinction by pain path is informative:
- fast crash trough median margin5 ~-3.8%
- rebound torture ~-3.7%
- residual/mixed ~-4.9%
- slow grind only ~-1.7%

Slow grind therefore appears more like conviction exhaustion / sponsorship loss than a classic leverage flush.

### Channel F — Relative abandonment / capital relocation
Existing cross-stock ownership work has repeated Level-B baton candidates such as 6213->3189, 3231->3017 and 2337->2344.
This does not prove the same beneficial owner. Economically, it shows that a stock can lose sponsorship while related opportunity receives concentration.
For the holder of the abandoned stock, the pressure is partly opportunity cost: the held name stagnates or falls while the next name reprices, encouraging a late switch.

## 4. Short sellers are a counterparty layer, not a standalone manipulation explanation
Across the 503 episodes:
- median 5d short-balance percentage change at peak ~+41.7%
- median at trough ~-19.2%
- 44.7% show short5 positive at peak and negative at trough.

At the trough, short covering can become buy-side liquidity while long holders are selling. This fits Taiwan literature showing shorting flows contain incremental information about future returns.

But the matched-control test finds peak short build is not abnormal after matching other strong-day conditions. Therefore `shorts increased -> they engineered the fall` is unsupported. Shorting is better interpreted as an information-sensitive/contrarian layer that can build into strength and cover into weakness.

## 5. Why 'I sold and it immediately rose' is structurally plausible
At the ex-post trough across the full sample:
- median institutional flow is negative (~-4.7% of daily volume)
- margin5 is negative (~-3.7%)
- short5 is negative (~-19.2%, consistent with covering)
- next session median institutional flow turns positive (~+2.3%) while margin5 remains negative (~-2.6%)
- next-session median stock return is ~+4.6%.

Because the trough is identified ex post this is descriptive, not a predictive rule. The important sequence is that faster/short-covering/professional capital can turn while the leverage cohort is still reducing risk. A late seller can therefore transact into exactly the liquidity that precedes the rebound.

## 6. Updated answer
The five price pain paths are real, but the deeper causal pressure is better summarized by six channels:
1. broad-market synchronized risk-off;
2. fast-capital reversal before slow leverage exits;
3. persistent sponsorship loss / failed ownership repair;
4. hope-reset rebounds without structural repair;
5. late leverage/panic de-risking;
6. relative abandonment as capital relocates elsewhere.

No current aggregate evidence proves that one actor deliberately orchestrates all six. Sophisticated capital can exploit these predictable liquidity states, but systemic shocks and endogenous feedback can create the same outcome without coordination.

The strongest structural distinction so far is not `who sold first`; it is whether ownership sponsorship returns after the first fracture. Failed repair is the clearest mechanism behind prolonged pain, while fast crashes are more often dominated by sudden flow/liquidity or systemic shocks.
