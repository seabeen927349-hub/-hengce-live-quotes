# HENGCE DSP / Loss Forensics — Actual-Availability Control-Deterioration Preregistration

Date: 2026-11-01
Parent authority: `7e4815e2c479173519d79f220acc01048db0b938`
Status: **FROZEN PREREGISTRATION / LABELS MUST NOT BE RE-OPENED TO ALTER THIS SPEC / NO TRADING AUTHORITY**

## 0. Authority accepted without reopening
This study inherits and does not retest these conclusions:
- Pass 3: CORE_LOOSENING, BRIDGE/DESTINATION_PRELOAD, PROFESSIONAL_FLOW all have formal incremental weight = 0. No rescue is authorized.
- Corrected Pass 4 h=1 is the only new evidence permitted for follow-up, and only as a recognition-latency layer.
- h=1 is not a BUY/SELL model and not an exact-price model.
- 6415 and 3042 are excluded as primary cases/anchors and are excluded from the execution sample here.
- production/capital authority remains NONE.

This study does **not** retune Pass 4. It asks whether the already observed source-side h=1 information remains useful after replacing snapshot-reference timing with true public-availability timing.

## 1. Sole research question
> Using only source-side post-t evidence that was actually public and usable at the claimed historical time, can the system identify `CONTROL_DETERIORATION` before the next ownership confirmation was actually publicly available, while reducing danger misses without materially increasing false alarms on durable repairs?

Primary evidence family is fixed:
`post-t professional flow × PIT residual price response × leverage quality`.

Destination evidence is secondary audit only. It cannot be promoted into the primary family because Pass 3 failed it.

## 2. Event population — frozen before new execution
Start from the exact final corrected-Pass-4 current100 OOS event population:
- reference-date evaluation window: 2026-06-26 through 2026-10-16;
- 334 OOS events before actual-availability censoring;
- same expanding-PIT candidate semantics and same CONTROL+HOOK t-time BASE replication;
- same ownership integrity/fail-closed rules;
- exclude tickers 6415 and 3042.

No event may be added because it has a convenient timestamp or removed because of its outcome.

An event becomes **availability-eligible** only if all required availability timestamps below are independently reconstructable and ordered consistently. Otherwise that event is `ABSTAIN_AVAILABILITY_UNKNOWN`.

## 3. True availability semantics
### 3.1 Ownership snapshot reference date is not availability
For each ownership observation t define:
- `REF_t`: ownership snapshot/reference date printed by the source.
- `A_t`: earliest independently verifiable timestamp at which the exact ownership payload/version used by the research could have been publicly known.
- `A_t1`: corresponding earliest independently verifiable public-availability timestamp for t+1 ownership confirmation.

`REF_t` and `REF_t1` may be used for identity/block partitioning, but **never** as substitutes for `A_t`/`A_t1` in latency calculations.

Acceptable evidence for `A_t` / `A_t1` must identify the exact historical payload/version and timestamp, e.g. immutable official publication metadata, archived official response metadata, or a contemporaneous original-vessel receipt whose provenance proves when that exact payload first became knowable.

Unacceptable substitutes:
- assuming a fixed +N-day release lag;
- using current query time as historical publication time;
- using file modification time created later by the research pipeline;
- inferring publication solely from snapshot date, weekday, or usual practice;
- using a later-retrieved payload without proof that the same version existed at the claimed time.

If historical ownership availability cannot be reliably reconstructed for the minimum required sample, the study terminates `DATA_BLOCKED`.

### 3.2 Daily source-side component availability
For each post-t daily component d define its exact public availability timestamp:
- `A_PRICE_d` for the completed regular-session price/market/sector/regime inputs;
- `A_FLOW_d` for aggregate professional-flow inputs;
- `A_LEVERAGE_d` for leverage/margin inputs.

The h=1 evidence bundle is not considered available until **all required source-side components** are public:
`A_H1 = max(A_PRICE_h1, A_FLOW_h1, A_LEVERAGE_h1, all PIT adjustment inputs used at h1)`.

Date-only records without a defensible historical availability time are not silently promoted to timestamped evidence. If a component lacks verifiable timing, that event is availability-abstained unless an official source establishes a conservative upper bound that guarantees the component was public before a specific later timestamp. Such a bound must be documented and may only delay availability, never accelerate it.

## 4. h=1 observation cutoff — actual-time definition
The first eligible h=1 session is the first TWSE regular trading session occurring after `A_t` for which the entire source-side bundle becomes public before `A_t1`.

The feature snapshot is frozen at `A_H1`. No data with availability timestamp later than `A_H1` may enter h=1 predictors.

Actionable recognition time is the first regular TWSE market open strictly after `A_H1`, denoted `EXEC_H1`, provided `EXEC_H1 < A_t1`.

If `A_H1 >= A_t1`, or no executable market open exists before `A_t1`, the event has **zero actionable early-recognition lead** and cannot be counted as a successful early recognition.

## 5. Frozen labels — no redefinition for prettier results
The behavioral label remains the corrected Pass-4 next-ownership durability target; only the positive/negative naming is flipped to make danger the positive class.

For candidate at t with pre-build baseline `Big400Pct(t-1)`:
- `CONTROL_DETERIORATION = 1` iff `Big400Pct(t+1) < Big400Pct(t-1)`.
- `DURABLE_REPAIR = 1` iff `Big400Pct(t+1) >= Big400Pct(t-1)`.

`t+1` ownership is LABEL ONLY and never a predictor.

No future price path, future destination reconcentration, hindsight case label, or later news may enter predictors.

## 6. Source-side h=1 predictors — frozen family only
No new model family is introduced. Reuse the corrected-Pass-4 source-side family and interaction doctrine:
- normalized aggregate professional flow / persistence;
- residual source price response;
- leverage/margin path;
- locked interaction of visible flow × residual price response × t-known ownership state × leverage quality.

### 6.1 PIT residual price-response construction
Residual price response must be computed from information available strictly before the evaluated observation.

For each stock, estimate expected return using only prior observations and PIT-known covariates:
`r_i = alpha + beta_m * r_market + beta_s * r_sector + regime controls + error`.

Rules:
- all beta/normalization/rolling-statistic estimation ends strictly before the evaluated daily return;
- market and sector returns must themselves be public by `A_PRICE_d`;
- sector membership/classification must be historically valid as of d; current-sector backfill is prohibited;
- regime controls must be generated from the pre-existing PIT regime rule/state using only information available before d; no regime threshold is fitted on forward labels;
- if a PIT sector/regime history required by the residual cannot be verified, the event abstains rather than falling back silently to a simpler residual;
- no future return enters beta, normalization, or residual construction.

This is a timing/integrity refinement of the existing residual-response family, not a new alpha family.

## 7. Destination evidence — secondary audit only
Frozen related-name/destination fields may be audited for timestamp integrity and descriptive error concentration, but:
- they cannot define eligibility;
- they cannot alter the primary danger probability;
- they cannot rescue a failed primary result;
- future destination reconcentration is prohibited.

## 8. Probability model and calibration
- BASE remains the final corrected-Pass-4 strict-time CONTROL+HOOK replication.
- h=1 model adds only the frozen source-side post-t family above.
- model class, calibration method, and expanding chronological fitting protocol remain the corrected-Pass-4 protocol; no hyperparameter search.
- probability calibration uses only chronologically prior labeled observations whose labels would already have been publicly available by the training cutoff.
- any row whose training-label availability is not established is excluded from training until it becomes available.

## 9. Primary metrics
Probability quality:
- Brier score;
- log loss;
- ECE / reliability;
- coverage and abstention.

Danger protection, with `CONTROL_DETERIORATION` as positive class:
- sensitivity / recall = TP/(TP+FN);
- false-negative rate = FN/(TP+FN);
- specificity = TN/(TN+FP);
- false-positive rate = FP/(TN+FP).

Repair protection:
- full predicted-danger-probability distribution for DURABLE_REPAIR cases (median, quartiles, p90/p95, calibration bins);
- false alarms by chronological block.

Recognition latency:
- `wall_clock_lead = A_t1 - A_H1`;
- `actionable_lead_sessions = number of regular TWSE market opens at or after EXEC_H1 and strictly before A_t1`;
- report min, p25, median, mean, p75, max and zero-lead share.

AUC is secondary only and cannot promote the result.

## 10. Frozen classification operating points
To avoid threshold hunting, two operating points are fixed before execution:

### OP-A: fixed probability threshold
`DANGER` iff calibrated `P(CONTROL_DETERIORATION) >= 0.50`.
No tuning.

### OP-B: repair-protected safety operating point
For each expanding evaluation date, using only chronologically prior calibration data with availability-safe labels, choose the **lowest** danger-probability threshold that achieved `specificity >= 0.80` on that prior calibration set. This rule is fixed now; the threshold may vary over time only because prior data change.

OP-B is unavailable/abstained if the prior calibration set contains fewer than 20 deterioration events or fewer than 50 durable-repair events.

No other threshold is reported as a primary success threshold.

## 11. Chronological validation blocks — frozen
Use the same two blocks as corrected Pass 4, based only on event reference date for partition identity:
- Block E: 2026-06-26 through 2026-08-14.
- Block L: 2026-08-21 through 2026-10-16.

Availability time, not reference date, determines predictor legality and training-label maturity inside each block.

No block boundary changes after outcomes are inspected.

## 12. Minimum sample requirement
Formal execution requires, after availability censoring:
- at least 100 OOS events total;
- at least 25 `CONTROL_DETERIORATION` events total;
- at least 75 `DURABLE_REPAIR` events total;
- in each chronological block, at least 10 deterioration events and 30 durable-repair events.

If these minimums are not met because actual historical publication/availability timestamps cannot be established, result = `DATA_BLOCKED`, not FAILED and not a case-study substitute.

## 13. Promotion / failure gates
This study can only validate an **actual-availability recognition layer**. It cannot create production authority.

To pass, ALL must hold:

### Gate A — actual-time lead exists
- median `actionable_lead_sessions` among scored events must be >= 1;
- at least 75% of scored events must have >=1 actionable lead session before `A_t1`.

### Gate B — probability quality
Versus availability-matched CONTROL+HOOK BASE on exactly the same scored rows:
- h=1 Brier must be lower;
- h=1 log loss must be lower;
- ECE may not worsen by more than +0.02 absolute;
- Brier and log loss must not worsen in either chronological block.

### Gate C — danger miss protection
At OP-A and separately at OP-B where available:
- aggregate h=1 false-negative rate must be lower than BASE;
- h=1 sensitivity must not be lower than BASE in either chronological block.

### Gate D — repair protection / no all-danger shortcut
At OP-A and separately at OP-B where available:
- h=1 false-positive rate may not exceed BASE by more than 0.05 absolute in aggregate or either chronological block;
- for OP-B, specificity must remain >=0.80 by construction on prior calibration data and must be reported honestly OOS; no OOS retuning if it misses 0.80.

If probability quality improves but danger-miss protection fails, result = `FAILED_DANGER_MISS`.
If recall improves only by excessive false alarms, result = `FAILED_REPAIR_PROTECTION`.
If lead is not real under actual publication times, result = `FAILED_NO_ACTIONABLE_LATENCY`.
If timestamps/sample cannot be reconstructed, result = `DATA_BLOCKED`.
No rescue/retuning follows any failure in this preregistration.

## 14. Abstention rules
An event is excluded from scoring and counted as abstention for any of:
- unknown/unverifiable `A_t` or `A_t1`;
- ambiguous historical payload version / corrections chain;
- any required h=1 source component has unknown availability and no defensible conservative upper bound;
- `A_H1 >= A_t1`;
- no actionable regular-session open exists after `A_H1` and before `A_t1`;
- PIT sector/regime membership/history cannot be reconstructed safely;
- ownership denominator/corporate-action integrity failure;
- calibration/model cannot be fit from availability-safe prior data.

Coverage = scored availability-eligible events / frozen 334-event OOS population after inherited exclusions.

## 15. Mandatory outputs
After preregistration, execution must write back:
1. availability provenance/audit table and report;
2. exact scored/abstained event manifest with reason codes;
3. probability metrics and chronological-block tables;
4. danger misses / false negatives;
5. false alarms / false positives and durable-repair probability distribution;
6. recognition-latency distribution using actual timestamps;
7. failure-case tables without narrative rescue;
8. latest current-state authority JSON/MD;
9. exact commit SHA and reproducibility hashes where computation occurs.

No formal forward-label execution is authorized until this preregistration commit exists.