# HENGCE LOSS FORENSICS — Retail Buy/Sell Illusion Findings V0
Date: 2026-11-01
Status: RETROSPECTIVE / EXPLANATORY

## Core conclusion
The evidence does not support a literal `the market sees my order and reverses` mechanism. It supports a synchronized-cohort mechanism: many retail decisions are triggered by the same visible evidence at the same late lifecycle phase. The individual then experiences a reversal immediately after acting and attributes the timing to the order itself.

## A. Visibility is highest near major peaks
At 12% retrospective major swing peaks in the 100-stock 2026 electronics sample:
- median peak-day volume = 1.54x trailing-20d median;
- transaction count = 1.45x trailing median;
- 20d return entering peak = +28.2%;
- 5d margin balance growth = +3.9%;
- foreign and total institutional flow are still positive on median;
- close is near the high of the daily range (~82%).

This is the exact environment that creates confidence, media/peer attention and perceived confirmation.

## B. Visibility is poor / evidence is ugly near troughs
At major troughs:
- 5d margin change about -4.4%;
- total institutional flow negative;
- close near the bottom of the daily range (~15%);
- latest ownership change usually still shows Big400/Big1000 leakage.

Five sessions after the trough, median price is already ~+14% from the low. Therefore the data that finally makes selling feel emotionally safe often arrives too late.

## C. Margin is a leveraged-retail timing marker
Across complete 12% swing legs:
- UP EARLY: median 5d margin change -1.59%;
- UP MID: +0.44%;
- UP LATE: +2.16%;
- DOWN EARLY: +0.44%;
- DOWN MID: -0.88%;
- DOWN LATE: -2.04%.

The ordering survives 8%, 12% and 15% swing scales. Within-leg paired comparisons also show late-vs-early margin growth is higher in 65.3% of up legs and lower in 67.1% of down legs.

TWSE reports that >98% of margin-trading participation at end-July 2026 was domestic individuals. Margin therefore does not represent all retail, but it is a high-purity leveraged-retail proxy.

## D. Ownership moves in the opposite direction around turns
Roughly 4–11 calendar days after major peaks:
- Big400 median -0.44pp;
- Big1000 median -0.49pp;
- Big400 falls in 73.2% of peak events;
- among observations with holder counts, total holders rise in 78.7%;
- joint Big400-down + holder-count-up appears in 64.8%.

Roughly 4–11 days after troughs:
- Big400 median +0.08pp;
- Big1000 median +0.09pp;
- holder count median -0.66%;
- holder count rises only 38.7%.

This is consistent with distribution near/after peaks and reconcentration near/after troughs.

## E. Breakout confirmation is often not diagnostic
20-day-high breakout events were classified retrospectively by which occurred first during the next 20 sessions: +10% continuation or -10% drawdown.

Among 746 non-ambiguous events:
- baseline `trap first` rate = 35.8%.
- volume and transaction-count medians are nearly the same in future continuations and traps (~1.6x and ~1.5x respectively).
- recent institutional flow is positive in both.
- median latest Big400 change is also essentially the same.

Exploratory inventory-quality splits:
- margin up + total-holder count up: n=108, trap-first rate 48.1%;
- total-holder count up + Big400 down: n=131, trap-first rate 44.3%;
- holder-count up alone: n=185, trap-first 45.4%.

These are descriptive post-hoc findings, not a trading rule. They suggest that a price breakout becomes more vulnerable when participation broadens into more holders and leverage while strong ownership is not improving.

## F. Repair determines whether an apparent distribution was real
After a peak, when the next ownership snapshot shows Big400 outflow, a second snapshot can distinguish rapid repair from continued leakage.

In the retrospective 12% swing sample:
- FAILED REPAIR: n=302; next down-leg median -21.3%; first post-peak dBig400 -0.965pp, next -0.335pp; holder count continues higher.
- REPAIR: n=50; next down-leg median -17.1%; first -0.655pp then +1.88pp; holder count contracts on repair.

After troughs with initial reconcentration:
- retained reconcentration n=196; next up-leg median +42.9%;
- failed reconcentration n=62; next up-leg median +32.1%.

Because swings are defined ex post, these return magnitudes are not tradable expected returns. The structural lesson is that persistence/repair matters more than one-week flow.

## G. Mechanism producing the `I buy -> fall / I sell -> rise` experience
A common lifecycle consistent with the data is:

1. **Quiet inventory formation** — price has not yet attracted widespread attention; margin may fall or stay subdued.
2. **Repricing** — price rises and strong ownership may reconcentrate; more investors notice.
3. **Attention acceleration** — abnormal volume, many trades, headlines/social proof, strong closes and visible institutional buying increase confidence.
4. **Late retail participation** — margin begins expanding; holder count broadens.
5. **Inventory transfer** — some strong-holder layers stop absorbing or distribute into the new demand. Price can still look excellent.
6. **Break** — after marginal demand is exhausted, price drops; public flow evidence turns negative after the turn.
7. **Late deleveraging / capitulation** — margin finally contracts strongly; holder count is still elevated; emotional evidence for selling is strongest.
8. **Reconcentration / repair** — stronger inventory begins returning while attention is low and sentiment remains poor.
9. **Rebound** — the seller experiences `I sold and it immediately rose`.

No individual order is required to cause the move. The same signals synchronize many orders near the same lifecycle boundaries.

## H. External literature consistent with this architecture
- Barber & Odean: individual investors are net buyers of attention-grabbing stocks (news, abnormal volume, extreme returns).
- Barber, Lee, Liu & Odean using complete Taiwan trading records: individuals suffer large aggregate trading losses; virtually all are traced to aggressive orders.
- Taiwan disposition-effect evidence: investors are about twice as likely to sell positions held at gains rather than losses; 84% sell winners faster than losers.

## Limits
- Margin = leveraged retail, not all retail.
- Big400/Big1000 = holder tiers, not identified persons.
- TDCC weekly sampling makes exact causal timing coarse.
- Full broker-branch/Gini content is advertised by Fugle but current connector calls returned empty payloads; do not claim broker evidence until bytes are actually retrieved.
- Corporate-action mechanical effects require continued normalization; a preliminary ±2-day exclusion around known dividend/capital event records removed only ~0.8% of the turning points and did not alter the qualitative peak/trough profiles.
