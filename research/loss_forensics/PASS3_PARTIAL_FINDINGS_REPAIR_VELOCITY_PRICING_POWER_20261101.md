# HENGCE DYNAMIC STATE PROBABILITY ENGINE — Pass 3 Partial Findings
Date: 2026-11-01
Status: EXPLORATORY / NO NUMERIC PROMOTION / NO TRADING AUTHORITY

Scope exclusions for interpretive examples: 6415 and 3042.

## Execution status
The preregistered cross-sectional numeric test has NOT yet been completed because the local compute runtime returned ClientError when reading the materialized audit/mother files.
No Brier/log-loss/calibration improvement is claimed.
The data are materialized and the test specification is frozen in `STATE_INTERACTION_PREREGISTRATION_PASS3_20261101.md`.

This file records only structural findings and falsification-oriented refinements from existing validated artifacts and counterexamples.

## 1. Core Loosening cannot carry a standalone negative weight
Existing governance explicitly documents healthy inventory elasticity:
- Big1000 -> Mid while Big400 remains stable can represent parking, role rotation, supply testing or controlled handoff;
- Mid -> Big1000 reconcentration can restore core control;
- true distribution is more likely only when inventory exits the broader strong-holder complex and does not return.

Therefore:
`dU < 0 + dL > 0` alone must have FORMAL_WEIGHT = 0.

The actual Pass-3 object is:
`CORE_LOOSENING -> does it progress to BIG400 leakage / weak-hand takeover, or does it reconcentrate?`

## 2. Repair Velocity emerges as the main protection variable
The first outward-transfer snapshot is not enough.
Observed false-distribution examples excluding 6415/3042:

### 2408
2026-05-22:
- Big400 -72.49m
- Big1000 -73.56m
- institutions -40.97m
- price roughly flat

2026-05-29:
- Big400 +45.01m
- Big1000 +43.81m
- margin -2.83%
- foreign identity +93.43m
- total institutions +82.86m

Interpretation: immediate strong-hand repair invalidated the first distribution interpretation.

A second 2408 repair episode:
2026-09-18:
- Big400 -31.540m
- Big1000 -35.495m

2026-09-24:
- Big400 +34.597m
- Big1000 +34.395m

Again, rapid repair reset SELL WATCH.

### 8021
2026-06-18:
- Big400 -8.34m
- Big1000 -5.00m

2026-06-26:
- Big400 +1.86m
- Big1000 +3.43m
- institutions positive
- margin remained lower

Interpretation: first outflow did not become permanent control loss.

### Contrast: 6213 first withdrawal cycle
- outward transfer continues across snapshots;
- attempted repairs remain small;
- no strong replacement sponsor appears;
- weaker money increasingly becomes necessary.

Current structural conclusion:
> The most important variable after FIRST_FRACTURE may be not the magnitude of the first fracture, but the speed and quality with which strong inventory returns.

Candidate latent variable for a later preregistration:
`REPAIR_VELOCITY` = ownership restoration relative to prior loss, measured over the first one/two valid ownership observations, with buyer-quality context.

This feature is NOT added to the frozen Pass-3 predictors post hoc. It remains exploratory until separately preregistered.

## 3. Repair quality matters as much as repair speed
A fast ownership rebound should not automatically increase P(REPAIR) if weak leverage simultaneously becomes the marginal buyer.

Protective repair is more consistent with:
- Big400 / Big1000 rebuilding;
- margin falling or contained;
- holder fragmentation not becoming permanent;
- price stabilization or rebound without requiring accelerating weak-hand financing.

Dangerous pseudo-repair / bridge is more consistent with:
- source strong ownership temporarily returns;
- price is maintained/attractive;
- ownership gives back quickly;
- destination preload appears elsewhere;
- source leverage or fragmented holders increasingly finance the price.

Thus future probability logic should distinguish:
`REPAIR_SPEED x REPAIR_BUYER_QUALITY`.

## 4. Pricing Power / Flow-Response Efficiency is a stronger candidate than raw institutional flow
Existing operator governance asks a more useful question than `who bought/sold?`:
> Who currently has pricing power?

Important asymmetries:
- large visible selling + price refuses to fall -> hidden/alternative absorption may be stronger;
- large visible buying + price cannot rise -> overhead supply may dominate;
- core holders buy during fear + leverage falls + price stabilizes -> control strengthening;
- core holders sell into accelerating price + leverage/fragmented holders expand -> control relinquishment risk.

This suggests a new evidence family:
`FLOW_PRICE_RESPONSE`.

Do NOT use unstable raw ratios such as return / near-zero net flow.
Preferred future implementation:
1. normalize professional flow by volume;
2. remove market/sector return component;
3. estimate expected price response conditional on flow magnitude and regime;
4. use the residual response as pricing-power evidence.

Candidate states:
- `SELL_PRESSURE_ABSORBED`: professional flow strongly negative but stock residual return / path remains resilient;
- `BUY_PRESSURE_INEFFECTIVE`: professional flow strongly positive but stock residual return/path is weak;
- `SPONSOR_EFFICIENT`: positive flow produces disproportionate positive residual price response;
- `DISTRIBUTION_EFFICIENCY`: strong price persists despite weakening sponsor flow and growing weak-hand financing.

These must be tested with 2023-2026 professional-flow history using time-order validation before any formal probability weight.

## 5. Why this matters for the state engine
The state engine should not update CONTROL_LOSS simply because:
- Big1000 falls;
- institutions sell;
- price breaks once.

A better sequence is:
FIRST_FRACTURE
-> measure where inventory went
-> measure whether price absorbs sell pressure
-> measure whether weak hands replace strong hands
-> observe repair velocity
-> check destination preload / capital relocation
-> promote either REPAIR or FAILED_REPAIR.

## 6. Current evidence hierarchy after counterexample review
### Highest-confidence validated
- CONTROL retention probability
- HOOK / release deterioration states

### Strong structural, awaiting calibration
- REPAIR_VELOCITY
- buyer-quality contamination
- pricing-power / flow-response efficiency
- Bridge Reload vs Durable Repair
- Destination Preload / capital relocation

### Explicitly rejected as standalone rules
- Big1000 down -> bearish
- institutional selling -> bearish
- one-week Big400 outflow -> sell
- one-week Big400 inflow -> buy

## 7. Next numeric execution once compute runtime is available
1. execute frozen Pass-3 event labels on current100 audit excluding 6415/3042;
2. compare BASE CONTROL+HOOK vs BASE+CoreLoosening vs BASE+Bridge/Preload;
3. report Brier/log-loss/calibration without threshold retuning;
4. separately preregister and test REPAIR_VELOCITY and FLOW_PRICE_RESPONSE rather than inserting them post hoc into Pass 3.

No numeric success is claimed in this file.