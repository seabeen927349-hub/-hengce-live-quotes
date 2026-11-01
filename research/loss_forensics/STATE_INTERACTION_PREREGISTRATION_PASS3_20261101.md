# HENGCE DYNAMIC STATE PROBABILITY ENGINE — Pass 3 Preregistration
Date: 2026-11-01
Status: FROZEN TEST SPEC / NO TRADING AUTHORITY
Scope exclusions for interpretive examples: 6415, 3042.

## Purpose
Turn Bridge Reload / Repair / New Control Takeover / Core Loosening / Destination Preload from narrative observations into falsifiable, time-ordered event tests.

No threshold retuning is allowed after forward labels are inspected. If a candidate definition fails to improve held-out calibration, it remains a diagnostic only and receives zero formal probability weight.

## A. Unit of observation
Primary unit: stock x TDCC snapshot interval.
All predictors must be observable by the snapshot's documented availability time. Daily overlays may use only trading data available up to that point.

Primary ownership source for current pilot:
`current100_ownership_intervals_audit.csv`.

Corporate-action / denominator instability remains fail-closed.

## B. Base candidate events
### 1. STRONG_OWNERSHIP_INFLOW
A candidate snapshot where aggregate strong-holder ownership rises materially relative to the stock's own expanding PIT history.
Implementation must use PIT percentile or CONTROL-model features, not a threshold selected after outcomes are seen.

### 2. CORE_LOOSENING
Pre-outcome observable structure:
- dU < 0 (Big1000/Core declines)
- dL > 0 (Mid rises)
- Big400 loss is smaller in magnitude than Core loss, or Big400 remains non-negative

This tests internal outward fragmentation before full Big400 leakage.

### 3. MID_PARKING_PRELOAD
Destination candidate:
- dL > 0
- Big400 retained or rising
- dU <= 0 or modest relative to dL

This tests `Mid first -> Core later` preparation.

No future Core reconcentration is used in the candidate definition.

## C. Future labels
### REPAIR_DURABLE label
For an inflow/reload candidate at t:
- next ownership snapshot does not return below the pre-repair baseline; and
- next-two-snapshot cumulative Big400 behavior remains consistent with retention.

Use existing `next_dB400`, `next2_sum`, baseline/control fields where valid.
Exact deterministic encoding must be fixed before model fitting and documented in the execution notebook/output.

### RELOAD_REVERSAL / BRIDGE outcome
For an inflow/reload candidate at t:
- next snapshot gives back a material portion of the inflow or moves below the relevant repair baseline.

A `bridge` interpretation additionally requires contemporaneous evidence of a plausible related destination preload, but destination evidence may NOT use future ownership changes.

### NEW_CONTROL_TAKEOVER outcome
For a strong inflow candidate at t:
- control remains above pre-build baseline next snapshot; and
- next-next snapshot retains or adds enough ownership to remain in the durable-control state.

This label is behavioral durability, not beneficial-owner identity.

### CORE_LOOSENING_FAILURE outcome
For a CORE_LOOSENING candidate:
- subsequent one/two snapshots progress to broader Big400 leakage / control deterioration.

### CORE_LOOSENING_REPAIR outcome
For a CORE_LOOSENING candidate:
- Core reconcentrates and Big400 control is preserved/rebuilt.

### DESTINATION_PRELOAD_SUCCESS outcome
For a MID_PARKING_PRELOAD candidate:
- later Core/Big1000 reconcentration occurs; and
- destination reaches durable CONTROL proof.

A destination price increase alone is NOT success.

## D. Predictor families for bridge-vs-repair classification
Only contemporaneously available predictors may enter.

### OWNERSHIP_STRUCTURE
- current dBig400
- dU
- dL
- internal cancellation share
- absorption fraction
- prior 1/2/4-snapshot ownership path
- current concentration percentile

### BUYER_QUALITY / LEVERAGE
- margin balance change from prior ownership anchor
- interval margin change
- short-balance change where valid
- holder-count change

### PRICE / LIQUIDITY CONTEXT
- interval price return
- turnover / volume shock
- price location and path efficiency
- relative return vs electronics / market

### PROFESSIONAL_FLOW
- source institutional intensity
- persistence/reversal
- price-flow divergence

Professional-flow mirror across source/destination is optional evidence; absence cannot veto a transition because prior cases show non-T86 migration.

### DESTINATION_PRELOAD
Only related-name states available by t:
- Mid/Big400 preload
- contained/reducing leverage
- sponsor flow
- relative-strength improvement

## E. Related-name universe
Do NOT search arbitrary all-to-all pairs after seeing outcomes.
Pass 3 begins with pre-existing research groups / Level-B candidate complexes and separately tests a sector-neighborhood rule defined without forward outcomes.

Known research edges remain examples, not training labels:
- 6213 -> 3189
- 3231 -> 3017
- 2337 -> 2344
- 8021 -> 2383
- 3006 -> 8150
Negative control:
- 2408 -> 2337

Identity ceiling remains Level B without independent account/legal evidence.

## F. Validation
Time ordered only.
Preferred procedure where sample permits:
1. earliest period: fit / derive candidate mapping
2. middle period: model selection / calibration
3. latest period: untouched evaluation

If 2026 sample is too small for three-way split, use expanding-window forward validation and report uncertainty.

Compare:
BASE = CONTROL + HOOK state features
vs
BASE + CORE_LOOSENING
vs
BASE + BRIDGE/DESTINATION_PRELOAD features
vs
BASE + PROFESSIONAL_FLOW corroboration

Primary metrics:
- Brier score
- log loss
- calibration error / reliability buckets
- AUC only as secondary discrimination statistic
- coverage / abstention rate

Formal promotion rule:
A new family may enter calibrated state probability only if it improves held-out Brier/log-loss and does not materially worsen calibration across time blocks.

If it improves narrative fit but not held-out probability quality, formal weight = 0.

## G. Explicit non-claims
- Big400 inflow is not automatically bullish.
- Big1000 decline is not automatically bearish.
- foreign/institutional identity is not beneficial-owner identity.
- a source/destination share-count resemblance is not literal share transfer.
- a bridge reload can be genuine buying; the issue is durability and marginal capital allocation.
- destination preload is not a BUY until CONTROL proof is established.

## H. Current hypothesis to falsify
The incremental hypothesis is:

> After an apparent repair/reload, the probability of future control failure is higher when the source shows weak-hand contamination, internal Core->Mid loosening, and a contemporaneous related-stock destination preload; conversely, repair durability is higher when strong ownership absorbs supply while leverage/fragmentation remain contained and no stronger destination is emerging.

This hypothesis is NOT accepted until the preregistered time-ordered test is executed.