# HENGCE DSP — RESEARCH DRIFT LOCK
Date: 2026-11-01
Status: HARD GOVERNANCE / MUST READ BEFORE EXECUTION

## Purpose
Prevent the next chat from drifting away from the currently authorized research question.
This file has higher priority than convenience, narrative attractiveness, model rescue, or newly discovered correlations.

## Authorized objective
The current objective is ONLY:

1. Execute the frozen Pass 3 state-interaction test exactly as preregistered.
2. If Pass 3 completes, execute corrected Pass 4 to test **pre-TDCC recognition latency** for distinguishing DURABLE_REPAIR from BRIDGE_RELOAD / FAILED_REPAIR.
3. Promote a new family into calibrated probability only if held-out Brier/log-loss improve without material calibration deterioration.

The research object is **state transition and recognition latency**, not exact price prediction.

## Current BASE that must not be silently redefined
BASE = existing CONTROL + HOOK evidence.
Known validated behavioral targets:
- CONTROL durability OOS AUC 0.694.
- CONTROL confidence >=0.80 -> 88.79% next-snapshot retention.
- CONTROL FULL + HOOK READY + dBig400<0: OOS 52 events; 10d mean -5.91%, median -5.42%, positive 22.5%.

These results must not be re-labeled as universal stock-return accuracy.

## HARD STOP — prohibited drift
Immediately stop and return to this file if the work begins doing ANY of the following:

1. **Exact-price drift**
   - predicting one top, one bottom, one target price, or optimizing an entry/exit price.

2. **Generic Bull/Bear score drift**
   - collapsing all evidence into a fixed additive score before state-specific calibration.

3. **Old-model rescue**
   - reviving V43, Monster, Selection Core, old P97/P90/Bridge thresholds, or merging old models to avoid a failed test.

4. **Single-case anchoring**
   - allowing any one stock to define the mechanism.
   - 6415 and 3042 remain excluded as primary anchors/examples for this research line.

5. **Threshold hunting / silent retuning**
   - changing cutoffs, lookbacks, labels, related-name definitions, or candidate windows after viewing forward outcomes unless the current test is first declared FAILED and a separate new preregistration is created.

6. **Outcome leakage**
   - using t+1 TDCC, future destination reconcentration, future price path, future news, or any information unavailable at the claimed observation time as a predictor.

7. **Identity overclaim**
   - treating foreign/trust/dealer/broker labels as beneficial owners.
   - claiming same person/controller without Level-C direct evidence.

8. **Standalone-variable drift**
   - converting Big1000 down, Big400 up/down, institutional buying/selling, margin change, one breakdown, or one rebound into direct BUY/SELL rules.

9. **Narrative rescue**
   - declaring a mechanism successful because cases look intuitive when held-out Brier/log-loss/calibration do not improve.

10. **Probability laundering**
   - presenting a raw score, vote count, heuristic percentage, or in-sample fitted probability as calibrated probability.

11. **Data fabrication / missing-data substitution**
   - filling unavailable fields silently.
   - treating retrieval failure as evidence that data do not exist.

12. **Architecture expansion before frozen tests finish**
   - introducing a new primary research family before Pass 3 and corrected Pass 4 are executed, unless required to resolve data validity. New observations may be logged as EXPLORATORY only and may not modify the frozen test.

## Mandatory drift self-check before any new branch of work
Before changing direction, explicitly answer internally:

A. Does this directly test Pass 3 or corrected Pass 4?
B. Is every predictor available at the claimed time?
C. Am I changing a rule because I saw the outcome?
D. Does this duplicate CONTROL rather than add recognition latency?
E. Is this an explanatory case study or a probability input?
F. If the result is negative, will I accept formal weight = 0 without rescue?

If A is NO, or B/F is NO, the proposed work is out of scope.
If C is YES, stop and create a new preregistration instead of modifying the active test.

## Pass 3 lock
Use `STATE_INTERACTION_PREREGISTRATION_PASS3_20261101.md` exactly.
Required comparisons:
- BASE = CONTROL + HOOK
- BASE + CORE_LOOSENING
- BASE + BRIDGE / DESTINATION_PRELOAD
- BASE + PROFESSIONAL_FLOW corroboration

Required primary metrics:
- held-out Brier score
- held-out log loss
- calibration/reliability
- coverage/abstention
AUC is secondary.

Promotion rule:
If a family does not improve held-out probability quality without material calibration damage, FORMAL WEIGHT = 0.
No rescue.

## Pass 4 lock — corrected incremental target
Do NOT rebuild next-snapshot CONTROL durability. CONTROL already addresses it.

The ONLY incremental question is:

> After state t is actually known, can daily/cross-stock evidence arriving before t+1 TDCC predict DURABLE_REPAIR vs BRIDGE_RELOAD / FAILED_REPAIR earlier than CONTROL confirmation?

Must measure BOTH:
1. probability-quality improvement vs BASE;
2. recognition-latency gain in trading days.

Candidate early evidence may include only contemporaneously available:
- normalized professional flow;
- market/sector/regime-adjusted residual price response;
- leverage-quality path;
- destination preload already known at t;
- post-t, pre-t+1 related-name flow / relative-strength evidence;
- optional execution mirror.

Future t+1 ownership is LABEL ONLY.

## Flow-price doctrine lock
Do not interpret raw flow-price response alone.
Economic unit:
`VISIBLE FLOW x PRICE RESPONSE x OWNERSHIP STATE x LEVERAGE QUALITY`.

The following simple rules are already rejected:
- selling + price holds = bullish
- buying + price rises = bullish
- institutional buying = controller buying
- institutional selling = controller exiting

## Evidence-status labels that must be used
Every new claim belongs to one of:
- VALIDATED_OOS
- STRUCTURAL_SUPPORTED_NOT_CALIBRATED
- EXPLORATORY
- FAILED
- DATA_BLOCKED
- UNKNOWN_FAIL_CLOSED

Never mix these categories in prose.

## Compute-failure rule
At handoff, Python/container execution was returning system-level ClientError.
If compute fails again:
- mark DATA_BLOCKED;
- continue only with retrieval/audit work that does not alter frozen test definitions;
- do not claim numeric validation;
- do not replace missing computation with hand-picked examples.

## Definition of success
Success is NOT finding a pretty model.
Success is one of these honest outcomes:
- a new family improves held-out probability quality and recognition latency -> promote cautiously;
- it improves interpretation but not held-out probability quality -> diagnostic only, weight 0;
- it fails -> reject;
- data/runtime prevent testing -> DATA_BLOCKED.

All four outcomes are acceptable.

## New-chat first-action requirement
Before execution, the next chat must read:
1. `00_READ_FIRST.md`
2. this `03_RESEARCH_DRIFT_LOCK.md`
3. `STATE_INTERACTION_PREREGISTRATION_PASS3_20261101.md`
4. `PASS4_INCREMENTAL_TARGET_CORRECTION_20261101.md`

Then it should state a one-sentence internal scope lock equivalent to:
`Execute frozen Pass 3, then corrected Pass 4; no new model family, no retuning, no exact-price drift, accept failure.`

Only then proceed.