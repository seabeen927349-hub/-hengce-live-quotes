# HENGCE LIVE STATE INTERPRETER — Architecture V1
Date: 2026-11-01
Status: RESEARCH / ADVISORY / NOT A PRICE-TARGET MODEL

## Objective
Do not predict one exact top, one exact bottom, or one fixed target price.
Maintain a continuously updated estimate of the stock's control / inventory / liquidity state and revise that estimate as new evidence arrives.

Primary live questions:
1. Is control/sponsorship intact?
2. Has a first fracture appeared?
3. Is the fracture being repaired or widening?
4. Is a downside break a false break / supply flush, or genuine sponsorship loss?
5. Is an upside move renewed control/reconcentration, or merely liquidity for distribution?
6. Is capital relocating into/out of related names?

## Core states
- CONTROL_INTACT
- ATTENTION_EXPANSION
- FIRST_FRACTURE
- REPAIR_IN_PROGRESS
- REPAIR_CONFIRMED
- FAILED_REPAIR
- FALSE_BREAK / SUPPLY_FLUSH
- CONTROL_LOSS
- RECONCENTRATION
- BATON_DEPARTURE
- BATON_ARRIVAL
- SYSTEMIC_SHOCK_OVERRIDE
- IDENTITY_UNRESOLVED

These are state estimates, not immutable labels. The interpreter must allow state reversal when new evidence invalidates the prior interpretation.

## Mixed-frequency evidence stack
### Intraday / real-time
- price path, gap, high/low/close location
- volume and transaction count vs intraday historical baseline
- bid/ask imbalance and order-book changes when available
- real-time market breadth / sector relative strength
- related-stock baton behavior
- news / major-information timestamp and immediate price response

### Daily / EOD
- margin financing / short balance
- institutional flow and role rotation
- turnover, price impact, abnormal volume
- corporate actions and mechanical adjustments
- relative return vs market / industry

### Weekly / slower structural layer
- TDCC Big400 / Big1000 / Mid
- holder-count dispersion / reconcentration
- repair / failed-repair sequence

No slow field may be silently projected into a live field. Each observation carries its own availability timestamp.

## Interpretation doctrine
### A. Never classify a top from price alone
A strong day, high volume, rising margin, positive institutional flow and rising short interest can appear both at true peaks and legitimate continuation days. Therefore one-day appearance is insufficient.

### B. The first break is a question, not an answer
When price breaks:
- check whether selling is stock-specific or market-wide;
- check relative strength vs sector/market;
- check whether fast flow reverses while leverage remains;
- check whether sell pressure is absorbed and price reclaims key intraday reference zones;
- later verify whether ownership repairs or continues dispersing.

### C. False break / supply flush
More consistent with:
- broad market shock but stock relative resilience;
- aggressive sell volume absorbed without persistent price deterioration;
- fast recovery / reclaim while leverage washes out;
- later ownership repair/reconcentration;
- related strong-capital evidence remains in the name.

### D. Genuine control loss
More consistent with:
- stock underperforms market/industry after the fracture;
- repeated rebounds fail to attract strong ownership repair;
- holder count broadens while Big400/Big1000 leak;
- faster professional flow repeatedly exits or fails to support;
- margin/fragmented buyers become marginal holders;
- related opportunity receives capital while the name does not recover sponsorship.

### E. Upside interpretation
A breakout is not automatically bullish.
Ask whether the move is financed by:
- reconcentration / strong absorption; or
- attention / leverage / broad holder expansion while strong ownership leaks.

The same price breakout can therefore map to REPAIR_CONFIRMED or DISTRIBUTION/FAILED_REPAIR risk depending on inventory response.

## Live update logic
Every new observation performs Bayesian-style evidence updating rather than deterministic rule firing:
- Evidence FOR control
- Evidence AGAINST control
- Systemic / mechanical confounds
- Missing / stale evidence
- Current confidence
- What observation would falsify the current state next

The user-facing output should always separate:
FACTS / INTERPRETATION / CONFIDENCE / NEXT CONFIRMATION.

## Live answer format
For a requested stock during market hours:
1. Current state estimate
2. What changed since prior observation
3. Evidence supporting control/repair
4. Evidence supporting genuine breakdown/control loss
5. Systemic-market confound
6. Which side currently has the stronger case
7. What next observable event would change the conclusion

Avoid target-price certainty. The goal is continuous diagnosis.

## Key research implication
The system should optimize for `state recognition latency` and `false state-change avoidance`, not exact top/bottom prediction.

The central skill is distinguishing:
- fracture that gets repaired;
- fracture that becomes failed repair;
- panic that transfers inventory into stronger hands;
- rally that transfers inventory into weaker hands.

This is the capability required to answer in real time whether an apparent top/breakdown is genuine or false.
