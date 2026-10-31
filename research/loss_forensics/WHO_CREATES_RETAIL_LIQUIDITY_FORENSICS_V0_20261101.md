# HENGCE LOSS FORENSICS — Who Creates Retail Liquidity V0
Date: 2026-11-01
Status: RETROSPECTIVE FORENSICS / NOT A MANIPULATION CLAIM / NOT A TRADING RULE

## Question
Who moves first around major turns, how do different cohorts hand inventory to each other, and why can individual investors feel compelled to sell near lows and buy near highs?

## Non-claim
Current evidence does NOT establish that one controller, broker, institution, or coordinated group deliberately engineers all major turns. The evidence is consistent with a mixture of informed/professional trading, large-holder inventory management, attention-driven retail demand, leverage constraints, short selling, public information reactions, and endogenous feedback.

## Data
- bound TWSE electronics 100-stock pilot
- 2026 daily TWSE price, trades, margin/short balance, institutional flows
- weekly TDCC current100 ownership intervals
- 12% ex-post zig-zag interior pivots: ~499 peaks / 491 troughs in the reconstruction used here

## 1. Around a peak, visible professional flow can reverse much faster than margin leverage
Event-aligned medians around interior peaks:
- t-10: 5d margin change -1.39%; total-institution intensity ~flat; price ~17% below eventual peak.
- t-2: margin +1.45%; total institutions +3.16% of daily volume; price ~9% below peak.
- t-1: margin +2.89%; total institutions +6.15%; price ~5.6% below peak.
- t0 peak: margin +3.59%; total institutions +7.38%; foreign +4.83%; volume 1.54x 20d median; transactions 1.44x; CLV ~0.82.
- t+1: total institutions -9.27%; foreign -9.53%; price -4.16% from peak; margin 5d change still +1.99%.
- t+5: price ~-12.0%; margin 5d change -4.44%.

Sign reversals:
- 71.7% of peaks have positive total-institution intensity on the peak day; only 23.6% are positive on t+1.
- 55.7% explicitly flip from total-institution positive at t0 to negative at t+1.
- only 12.8% flip from positive 5d margin change at t0 to negative at t+1.

Interpretation: aggregate institutional/professional flow often changes direction far faster than leveraged retail inventory. This does not prove institutions created the peak; it demonstrates reaction-speed asymmetry and the possibility that slow inventory becomes liquidity for faster capital after the turn.

## 2. Around a trough, professional flow also tends to turn before leverage recovers
Medians around troughs:
- t-1: price still falling; total institutions -4.76%; margin 5d -2.46%.
- t0 trough: daily return -4.41%; total institutions -4.38%; margin 5d -3.97%; CLV ~0.15.
- t+1: price +4.82%; total institutions +1.86%; foreign +1.49%; margin 5d still -2.60%.
- t+5: price ~+13.9% from trough; margin 5d has recovered to +3.44%.

Negative-to-positive institutional sign reversal from t0 to t+1 occurs in ~35.8% of troughs, while negative-to-positive margin reversal occurs in only ~8.5%.

Interpretation: leverage tends to confirm later; faster flow can begin changing direction while the retail-leverage cohort is still deleveraging.

## 3. Short sellers are a distinct information-bearing cohort, but not proof of orchestration
At major peaks, median 5d short-balance change is +41.7%; ~70.0% of usable peaks have rising short balance. At troughs, median 5d short-balance change is -19.2%; only ~33.5% show rising short balance.

Taiwan academic evidence independently finds shorting flows contain incremental information about future returns. This makes shorting a useful forensic comparator for information timing, but short sellers can be hedgers/arbitrageurs and must not be equated with a controller.

## 4. Weekly ownership data show a lagged inventory transition around turns
Peak windows (median weekly ownership change):
- 8-14 days before peak: Big400 -0.07pp; holder count +0.35% where available.
- 1-7 days before: Big400 +0.05pp.
- 0-7 days after: Big400 +0.15pp.
- 8-14 days after: Big400 -0.40pp; Big1000 -0.44pp; holder count +2.15%.

Trough windows:
- 1-7 days before: Big400 -0.21pp; holder count +0.54%.
- 0-7 days after: Big400 -0.25pp; holder count +1.31%.
- 8-14 days after: Big400 +0.17pp; Big1000 +0.105pp; holder count -0.20%.

This is crucial: aggregate ownership concentration does not consistently lead the exact price pivot. Often the stock turns first and the weekly ownership state confirms dispersion/reconcentration later. Therefore a simple story that one whale first dumps and mechanically creates every top is false.

## 5. The emerging causal architecture is a feedback loop, not necessarily a single manipulator
### Fast / information-sensitive capital
Possible participants: institutions, large holders, sophisticated shorts, specialist/quant capital. Evidence: order aggressiveness and information advantage in Taiwan literature; quicker flow sign changes around pivots; strong-holder inventory migration.

### Attention amplifiers
Price acceleration, new highs, abnormal volume, high transaction counts, news, analyst signals and social search make the stock enter more individual investors' choice sets. This can occur without collusion.

### Slow / confirmation-seeking capital
Margin-leveraged individual participation tends to rise later in rallies and decline later in selloffs. Retail is not homogeneous, but margin is a strong leveraged-retail proxy in Taiwan.

### Inventory handoff
When attention and liquidity are abundant, earlier holders can reduce inventory with less price impact. If inventory is rapidly repaired by another strong cohort, the move can survive. If strong ownership continues leaking while holder count broadens, the new marginal holder is structurally weaker.

### Pain / capitulation
Once price breaks, the same signals reverse: negative return, visible selling, loss of control, margin maintenance pressure, and social proof. Some investors voluntarily de-risk, some are constrained, and some are forced. TWSE 2026 evidence says market-wide forced liquidation is small, so `all capitulation = margin call` is false.

### Re-absorption
After weak/leveraged supply has been released, price can rebound before public evidence becomes emotionally safe again. The late seller therefore experiences `I sold, then it rose`.

## 6. Why this can look intentional even when it is endogenous
For a large inventory holder, the best time to sell is when many willing buyers exist; for a buyer seeking inventory, the best time to buy is when sellers are abundant and urgent. Attention, leverage and loss aversion produce exactly those counterparties. Thus rational inventory management by faster actors can mechanically exploit behavioral liquidity without requiring an explicit conspiracy or illegal manipulation.

The stronger manipulation hypothesis requires independent evidence: order-level spoofing/painting, coordinated accounts, broker-branch/account linkage, false-information dissemination, wash trades, or other direct conduct. Current aggregate data do not establish this.

## 7. External literature consistent with the architecture
- Barber et al. (2009), full Taiwan investor history: individuals lose systematically; virtually all losses trace to aggressive orders, while institutions earn positive performance.
- Lien, Hung & Lin (2020), TWSE order data: individuals account for most transitory weighted price contribution, but professional-institution price contribution is more predictive of future returns; institutional order aggressiveness is higher.
- Taiwan analyst-report research: foreign institutions and domestic mutual funds react aggressively to analyst information; individual investors become de facto liquidity providers to aggressive institutions around those reports.
- Taiwan shorting research: shorting flows negatively predict future stock returns, consistent with informed shorting.
- Attention research: individual investors are net buyers of news/abnormal-volume/extreme-return attention stocks.

## Current answer
The most defensible answer to `who makes retail buy high and sell low?` is currently:

> No single actor has been proven. The recurring mechanism is an ecosystem in which faster/information-sensitive capital, large-holder inventory management, informed shorting and public-information reactions move or change direction earlier; price/volume/news then amplify attention; leveraged/confirmation-seeking retail arrives later and provides liquidity; if strong ownership fails to repair, price breaks; negative confirmation and constraints then cause late selling; faster capital can re-absorb once weak supply is released.

This mechanism can be deliberately exploited by sophisticated participants, but the current evidence does not justify claiming that the entire cycle is deliberately manufactured by one controller.
