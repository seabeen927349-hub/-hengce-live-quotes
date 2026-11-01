# HENGCE DYNAMIC STATE PROBABILITY ENGINE — Pass 4 Preregistration
Date: 2026-11-01
Status: FROZEN TEST SPEC / NO TRADING AUTHORITY
Scope examples exclude 6415 and 3042.

## Purpose
Test two candidate evidence families discovered from counterexample review without contaminating Pass 3:
1. REPAIR_VELOCITY / REPAIR_QUALITY
2. FLOW_PRICE_RESPONSE / PRICING_POWER

No thresholds may be tuned after forward labels are inspected.

# A. REPAIR VELOCITY
## A1. Event origin
Start from a FIRST_FRACTURE ownership event at t:
- broad strong-holder ownership weakens relative to the prior control state, or
- an existing CONTROL/HOOK state transitions into outward inventory movement.

The first fracture is not itself a SELL label.

## A2. Observable repair sequence
At the first valid ownership observation after fracture, measure:
- fraction of prior Big400 loss restored;
- fraction of prior Big1000 loss restored;
- whether Big400 returns above the relevant pre-fracture/control baseline;
- holder-count direction;
- margin direction;
- market/sector regime during the repair interval.

At the second valid ownership observation, measure whether repair persists.

## A3. Repair-quality features
All must be contemporaneously observable:
- ownership restoration fraction;
- Big1000 vs Mid reconcentration path;
- holder fragmentation change;
- margin change / weak-hand contamination;
- professional-flow support or contradiction;
- price stabilization / relative strength, adjusted for market/sector regime;
- whether a related destination preload is simultaneously present.

## A4. Future labels
### DURABLE_REPAIR
- ownership repair survives the next valid snapshot;
- broader Big400 control is retained/rebuilt;
- weak-hand expansion does not become the sole support mechanism.

### TRANSIENT_REPAIR
- repair appears but a substantial portion is given back at the next valid snapshot;
- control returns toward or below the fracture baseline.

### FAILED_REPAIR
- no meaningful strong-holder restoration occurs before further broad ownership leakage / control loss.

These labels concern inventory/control durability, not future stock return.

## A5. Main hypothesis
> Conditional on the same initial fracture magnitude, faster and cleaner strong-holder repair should lower P(CONTROL_LOSS), while repair accompanied by leverage/holder fragmentation and destination preload should be less durable.

## A6. Validation
Compare BASE CONTROL+HOOK with BASE+REPAIR_VELOCITY features using expanding time-order validation.
Primary metrics:
- Brier
- log loss
- calibration error
- AUC secondary
- abstention coverage

No formal probability weight unless held-out Brier/log-loss improve without calibration deterioration.

# B. FLOW-PRICE RESPONSE / PRICING POWER
## B1. Motivation
Raw institutional net flow is not enough. Existing cases show visible selling can coexist with ownership strengthening, and visible buying can coexist with control loss.
The candidate object is the price response conditional on the flow and regime.

## B2. Data scope
Primary sample:
- validated 2023-2025 institutional T86 + price/volume history;
- 2026 T86 + price/volume as latest held-out block where feasible.

Use corporate-action-adjusted/censored price observations.

## B3. Expected-response model
For each stock-day, estimate an expected stock return / price-path response using only past data as a function of:
- market return
- electronics/industry return
- professional-flow intensity relative to volume
- prior volatility / liquidity
- stock size/liquidity controls where available

The object of interest is NOT a raw return/flow ratio.
Use residualized response to avoid denominator instability when net flow is near zero.

## B4. Candidate pricing-power states
### SELL_PRESSURE_ABSORBED
Contemporaneous condition:
- materially negative professional flow;
- residual stock price response is materially stronger than expected given market/sector/flow context;
- volume/liquidity is sufficient to make the observation meaningful.

### BUY_PRESSURE_INEFFECTIVE
- materially positive professional flow;
- residual stock response is materially weaker than expected.

### SPONSOR_EFFICIENT
- positive professional flow produces stronger-than-expected residual price response.

### DISTRIBUTION_EFFICIENCY
- price remains strong / attention expands while sponsor flow weakens and weak-hand financing/fragmentation increases.

Exact cutoffs, if any, must be derived only inside the development sample and frozen before evaluation.

## B5. Future state labels
Test whether each pricing-power state predicts, over the next valid ownership observations:
- durable ownership repair;
- failed repair;
- control loss;
- reconcentration.

Do not use future price return as the only target.

## B6. Interaction test
Main comparison:
BASE CONTROL+HOOK
vs
BASE + FLOW_PRICE_RESPONSE
vs
BASE + REPAIR_VELOCITY
vs
BASE + both

Secondary interactions:
- SELL_PRESSURE_ABSORBED x margin falling
- BUY_PRESSURE_INEFFECTIVE x Big400 leakage
- DISTRIBUTION_EFFICIENCY x holder fragmentation
- SELL_PRESSURE_ABSORBED x destination absence/presence

## B7. Falsification
The family is rejected from formal probabilities if:
- residual-flow states fail to improve held-out Brier/log-loss;
- sign flips materially across years/regimes;
- the apparent edge disappears after market/sector normalization;
- gains come only from one small case cluster.

# C. Explicit safeguards
- no visible institution category is treated as verified beneficial owner;
- Big1000->Mid internal movement alone receives no bearish weight;
- one-week repair alone receives no bullish weight;
- no post-hoc use of future destination ownership in candidate detection;
- no arbitrary all-to-all stock pairing after outcomes are known;
- no numeric probabilities are published before held-out calibration.

# D. Current structural expectations, not accepted results
Counterexample review suggests:
- immediate ownership restoration can invalidate apparent distribution;
- rapid repair with leverage contained is qualitatively stronger than repair financed by weak hands;
- price resilience against visible selling may reveal hidden/alternative absorption;
- price weakness despite visible buying may reveal stronger overhead supply;
- true distribution is more consistent with broad strong-holder leakage that fails to return than with any single identity selling.

These remain hypotheses until Pass 4 is executed.