# HENGCE DYNAMIC STATE PROBABILITY ENGINE — Charter V1
Date: 2026-11-01
Status: ACTIVE RESEARCH / NO TRADING AUTHORITY

## Objective
Estimate the current market state of a stock and the probability of transitions between states. Do not optimize for an exact top, exact bottom, or fixed target price.

Primary outputs:
- P(CONTINUATION)
- P(REPAIR)
- P(CONTROL_LOSS)
- P(SYSTEMIC_SHOCK)
- ABSTAIN / NO_EDGE when evidence is insufficient or poorly calibrated

Probabilities must be calibrated. Raw additive scores may not be presented as probabilities.

## State graph
CONTROL_INTACT -> ATTENTION_EXPANSION -> FIRST_FRACTURE
FIRST_FRACTURE -> REPAIR_IN_PROGRESS -> REPAIR_CONFIRMED -> CONTROL_INTACT
FIRST_FRACTURE -> FAILED_REPAIR -> CONTROL_LOSS
SYSTEMIC_SHOCK can overlay any state and reduce the information content of stock-specific breaks.
RECONCENTRATION, BATON_DEPARTURE and BATON_ARRIVAL are secondary inventory states.

## Evidence families
Evidence is grouped before weighting so correlated variables do not double-vote.

1. PRICE_STATE
   - multi-horizon return
   - trend / acceleration
   - distance from rolling high/low
   - breakout / breakdown / reclaim
   - path efficiency / drawdown / rebound structure
   - relative strength vs electronics and market

2. LIQUIDITY_ATTENTION
   - volume shock
   - turnover shock
   - transaction-count shock
   - intraday/daily price impact
   - close-location / gap / range expansion

3. MARKET_REGIME
   - TWSE breadth
   - electronics breadth
   - index trend / volatility
   - industry relative strength
   - systemic shock flags

4. PROFESSIONAL_CAPITAL
   - total institutional flow
   - foreign / trust / dealer only as observed vehicles, not beneficial-owner identities
   - flow persistence / reversal
   - flow relative to volume
   - price-flow divergence

5. LEVERAGE_WEAK_HANDS
   - margin balance and change
   - margin buy/sell/repayment
   - short balance / covering
   - leverage timing relative to price

6. OWNERSHIP_SPONSORSHIP
   - TDCC Big400 / Big1000 / Mid
   - holder count
   - dispersion / reconcentration
   - repair / failed repair
   - ownership regime health

7. FUNDAMENTAL_INFORMATION
   - revenue trend / acceleration
   - EPS / margin trend
   - operating cash flow / FCF
   - inventory / receivable / payable dynamics
   - balance-sheet stress
   - major announcements / events

8. CAPITAL_RELOCATION
   - related-name sponsorship loss/gain
   - same-industry baton candidates
   - cross-sectional opportunity migration

## Historical coverage layers
Use the longest valid history available per family; do not shrink the whole engine to the shortest family.

- PRICE_STATE / LIQUIDITY_ATTENTION / MARKET_REGIME: TWSE electronics 2018-2026 historical files, with corporate-action correction.
- PROFESSIONAL_CAPITAL: validated 2023-2025 T86 plus 2026 T86; 2023-2025 matched coverage ~97-98%.
- LEVERAGE_WEAK_HANDS: use only intervals with validated margin/short data; do not reconstruct absent periods.
- OWNERSHIP_SPONSORSHIP: use only observed TDCC snapshots; known historical bulk gaps remain NULL.
- FUNDAMENTAL_INFORMATION: use available MOPS/Fugle history with explicit publication/availability semantics where possible.

## Estimation doctrine
### 1. Factor census first
For every candidate variable and state transform, estimate:
- conditional future state-transition rates
- 1/5/10/20-day outcome distributions
- year-by-year sign stability
- regime-specific behavior
- missingness and data-age behavior

### 2. Incremental information, not univariate beauty
A variable receives weight only if it adds information beyond its family and beyond existing families.
Use out-of-time tests, conditional likelihood gain, Brier/log-loss improvement, and calibration stability.

### 3. Family compression
Highly correlated variables are compressed or regularized before cross-family combination. Volume, turnover and transaction-count shocks may not each receive full independent weight if they represent the same attention state.

### 4. Dynamic weights
Weight_i is a function of:
- historical reliability
- current regime
- current state
- data freshness
- sample size
- redundancy with other evidence

Fixed permanent weights are prohibited unless empirical stability supports them.

### 5. Time splits
Minimum discipline:
- earlier years: development
- later pre-2026 years: calibration / model selection
- 2026: protected out-of-time evaluation for long-history families whenever feasible
Short-history families use their own rolling/forward validation and receive lower reliability until more history accumulates.

### 6. Calibration
Raw model scores are mapped to probabilities only through held-out calibration.
Track:
- Brier score
- log loss
- reliability/calibration curve
- observed frequency by probability bucket
- ECE / calibration error
- regime-specific calibration

### 7. Abstain
Return ABSTAIN / NO_EDGE when:
- posterior probabilities are too close
- calibration is weak in the current regime
- critical evidence is stale/missing
- families materially conflict without historical resolution
- state is outside observed support

No forced 51/49 answer.

## Probability attribution
Every state update must explain the delta from the previous estimate.
Example:
CONTROL_LOSS 28% -> 47%
- +8pp relative-strength failure
- +6pp professional-flow reversal
- +5pp reclaim failure
- +3pp leverage-quality deterioration
- -3pp systemic-market confound

Attribution must be model-derived or evidence-derived; never invented narratively.

## Research guardrails
- No single ticker may define the architecture.
- No fabricated data or silent imputation of unavailable fields.
- Corporate-action mechanical effects must be corrected/censored.
- Same visible variable cannot be counted repeatedly under multiple families without explicit de-correlation.
- Retrospective labels are allowed for mechanism learning but must be separated from live-available inputs.
- A failed hypothesis remains failed; no silent threshold retuning to rescue it.
- A probability is not published unless calibrated on data not used to fit its raw score.

## Current negative baseline
A price/liquidity-only historical baseline has weak forward discrimination in preliminary out-of-time testing (roughly AUC 0.51-0.55 depending on target/model). This is retained as evidence that surface price patterns alone are insufficient and that the engine must earn incremental value from ownership, capital, leverage, fundamentals and regime interactions.

## Success criterion
Success is not exact top/bottom prediction.
Success means:
1. state probabilities are calibrated;
2. repair vs failed-repair is recognized with useful latency;
3. systemic shocks are not misclassified as stock-specific control loss;
4. probability changes are attributable to observable evidence;
5. the engine can abstain when evidence is weak.
