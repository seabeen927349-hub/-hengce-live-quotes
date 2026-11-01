# HENGCE DSP / Loss Forensics — Actual-Availability Control-Deterioration Execution

Date: 2026-11-01
Preregistration commit: `91d785b9e9aaae1367bf1cbb8c73e61bb2c16e95`
Availability audit commit: `a3d9e3777f7d5246bb4b38ab5fcd3d1ce618e03b`
Status: **DATA_BLOCKED / EXECUTION STOPPED BEFORE FORMAL FORWARD-LABEL ACCESS / NO TRADING AUTHORITY**

## 1. Frozen question
Can source-side post-t evidence (`professional flow × PIT residual price response × leverage quality`) identify true `CONTROL_DETERIORATION` before the next ownership confirmation is actually publicly available, without materially overcalling durable repairs?

## 2. Pre-label availability gate
The preregistration requires defensible historical `A_t` and `A_t1` timestamps for the exact ownership payload and PIT-safe source-side component timing.

The availability audit did not satisfy this gate:
1. TDCC snapshot reference dates are known, but per-snapshot exact historical first-publication timestamps are not preserved in HENGCE.
2. The contemporaneous wirelessr archive supplies first-observed retrieval timestamps, which are valid conservative evidence that data were public by those times but are not equivalent to the exact earliest TDCC publication timestamp required by the preregistration.
3. Daily source-side canonical rows contain no historical publication/retrieval timestamp. Official TWSE production schedules can constrain flow/leverage availability conservatively, but do not solve ownership timing.
4. PIT sector-membership and regime provenance required by the frozen residual-response definition is incomplete; derived research tables do not establish effective-date/source authority for every OOS event.

Therefore the event population cannot be transformed into a preregistration-compliant availability-eligible formal evaluation set.

## 3. Formal execution status
Formal forward-label access for this new study: **NOT OPENED**.

Consequently the following are intentionally **NOT COMPUTED**:
- Brier score;
- log loss;
- ECE / reliability;
- AUC;
- sensitivity / recall;
- false-negative rate;
- specificity;
- false-positive rate;
- durable-repair danger-probability distribution;
- actual-publication recognition-latency distribution;
- OP-A / OP-B confusion matrices;
- chronological block comparisons.

This is not missing reporting. It is the required fail-closed behavior under the frozen preregistration.

## 4. Minimum sample requirement
The minimum formal sample requirement cannot be evaluated because exact availability eligibility cannot be established without substituting weaker timing assumptions.

No count is manufactured by treating archive-first-observed time, snapshot reference date, or fixed release lag as exact `A_t/A_t1`.

## 5. Result classification
**Evidence status: `DATA_BLOCKED`.**

This is neither:
- `FAILED` evidence against the source-side mechanism; nor
- `VALIDATED_OOS` evidence under actual public timing.

It means the current historical provenance is insufficient to answer the preregistered question honestly.

## 6. Existing authority remains unchanged
- Pass 3 remains null promotion; all new families formal weight = 0.
- Corrected Pass 4 h=1 remains `VALIDATED_OOS` only under its original snapshot-reference-date latency semantics.
- The source-only h=1 result remains diagnostic and is not promoted.
- Destination evidence remains secondary only.
- 6415 and 3042 remain excluded as primary anchors.
- production/trading authority remains `NONE`.

## 7. What would unblock this exact preregistration
This preregistration may be executed without changing its definitions only if new provenance is obtained that establishes:
1. historically defensible per-snapshot TDCC first-publication/availability timestamps (or immutable contemporaneous records strong enough to meet the preregistered `A_t/A_t1` semantics);
2. PIT historical sector membership with effective dates/source provenance;
3. a frozen PIT regime rule/state provenance chain for the OOS dates;
4. conservative source-side component availability timestamps consistent with actual publication schedules.

If any definition, threshold, label, residual specification, or success gate is changed instead of merely filling provenance gaps, a new preregistration is required.

No model rescue or alternate pretty study is authorized by this result.