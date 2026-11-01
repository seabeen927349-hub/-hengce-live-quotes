# HENGCE DYNAMIC STATE PROBABILITY ENGINE — Pass 4 Incremental Target Correction
Date: 2026-11-01
Status: FROZEN RESEARCH CORRECTION / NO TRADING AUTHORITY

## Why this correction is required
The proposed `REPAIR_VELOCITY` concept overlaps with an already validated target in CONTROL V1.

CONTROL V1 already asks:
> when strong-holder ownership rises at snapshot t, does the next TDCC snapshot retain at least the pre-build ownership level?

This is already a durability / one-snapshot-bridge discrimination problem.
Its expanding time-order OOS results for 2026-06-26 through 2026-10-16 were:
- AUC 0.694
- confidence >=0.70 -> 84.56% next-snapshot retention
- confidence >=0.80 -> 88.79%
- confidence >=0.90 -> 93.51%

Therefore a new factor called `REPAIR_VELOCITY` is NOT justified merely for predicting next-snapshot durability.
That would duplicate CONTROL.

## Correct incremental research question
The only legitimate incremental target is:

> After FIRST_FRACTURE or apparent repair/reload at ownership snapshot t, can daily / cross-stock information available BEFORE the next TDCC snapshot distinguish `DURABLE_REPAIR` from `BRIDGE_RELOAD / FAILED_REPAIR` earlier than CONTROL can confirm it?

The value proposition is `recognition latency`, not a duplicate retention classifier.

## Frozen timing semantics
At ownership snapshot t:
- ownership state at t is known only at its documented availability time;
- after that availability time, only daily information arriving before t+1 TDCC may be used for early classification;
- t+1 ownership is the future label and cannot enter predictors.

No future destination ownership reconcentration may leak into the source-side predictor.
Destination-preload features must be observable before the source t+1 TDCC label.

## Candidate early evidence families
### 1. SOURCE FLOW-PRICE RESPONSE
Use daily observations after snapshot t but before t+1:
- normalized professional flow
- stock residual price response vs market/sector/regime
- persistence of sell/buy pressure
- whether price remains resilient despite selling or fails despite buying

### 2. SOURCE LEVERAGE QUALITY
- margin balance path after t
- margin buy/sell/repayment where available
- whether weak leverage begins carrying an attractive/elevated price

### 3. DESTINATION PRELOAD
Only contemporaneously visible related-name evidence:
- Mid / Big400 preload already known at t
- daily sponsor flow after t
- contained/reducing leverage
- relative-strength improvement

### 4. SOURCE-Destination EXECUTION MIRROR
Optional corroboration only:
- source professional flow negative while destination positive across several days
- no requirement that the visible identity be the same beneficial owner
- absence cannot veto bridge because prior cases show non-T86 / different-role migration

## Four-quadrant pricing-power doctrine
`FLOW_PRICE_RESPONSE` alone receives no formal weight.
Interpretation requires:

`VISIBLE FLOW x PRICE RESPONSE x OWNERSHIP STATE AT t x LEVERAGE QUALITY`

Structural quadrants:
1. selling + resilient price + strong ownership retained/repaired + leverage contained -> `ABSORPTION_CANDIDATE`
2. selling + resilient price + ownership leaks / weak-hand financing -> `DISTRIBUTION_WITH_PRICE_SUPPORT`
3. buying + positive residual response + durable strong ownership + leverage contained -> `SPONSORSHIP_EFFECTIVE`
4. buying + weak/negative response + ownership leakage -> `SPONSORSHIP_INEFFECTIVE`

These are hypotheses until time-order numeric validation.

## Promotion criterion
The early classifier may enter the Dynamic State Probability Engine only if, relative to CONTROL available at t:
- held-out Brier score improves for predicting t+1 durability;
- held-out log loss improves;
- calibration does not materially worsen;
- useful decisions are produced earlier than t+1 TDCC;
- improvements persist across time blocks and are not driven by a few cases.

If it only explains the outcome after t+1 ownership arrives, formal incremental weight = 0.

## Current honest status
- CONTROL durability: already empirically validated with expanding OOS.
- Bridge / destination-preload / pricing-power early-warning: structurally supported by multiple cases and counterexamples.
- Incremental early-warning probability improvement: NOT YET PROVEN because current local compute runtime is unavailable.

No numerical success claim is authorized until the frozen timing test is executed.