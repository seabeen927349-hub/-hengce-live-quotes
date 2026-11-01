# HENGCE Dynamic State Probability Engine — New Chat Handoff
Date: 2026-11-01
Status: ACTIVE RESEARCH / NO TRADING AUTHORITY

## Bootstrap authority
Repo: `seabeen927349-hub/-hengce-live-quotes`
Branch: `research/loss-forensics-20261101`
Parent head before this handoff folder: `6633c1b2cee2db424d10168f6a4d022b1eaa2c41`

At next-chat start, check current branch head. If the branch advanced, use the newest head, but do not silently override the governance below.

## Objective
Continue Loss Forensics as a **Dynamic State Probability Engine**.
Do not return to exact-price prediction, fixed Bull/Bear scoring, V43 rescue, Monster rescue, or single-ticker storytelling.

Primary outputs when eventually calibrated:
- P(CONTINUATION)
- P(REPAIR)
- P(CONTROL_LOSS)
- P(SYSTEMIC_SHOCK)
- ABSTAIN / NO_EDGE

The target is state-transition diagnosis and recognition latency, not exact top/bottom prices.

## User research doctrine
- All legitimately obtainable data may be used.
- The user does not require a model if evidence does not support one.
- Failure is acceptable; fabricated success, silent retuning, threshold rescue and hindsight masquerading as live knowledge are not.
- Traditional Chinese for user-facing discussion.

## Current exclusions
For current mechanism research and interpretive examples, exclude **6415** and **3042** as primary anchors/examples. Do not let them define architecture.

## Must-read files
1. `research/loss_forensics/DYNAMIC_STATE_PROBABILITY_ENGINE_CHARTER_V1_20261101.md`
2. `research/loss_forensics/STATE_INTERACTION_PREREGISTRATION_PASS3_20261101.md`
3. `research/loss_forensics/PASS3_PARTIAL_FINDINGS_REPAIR_VELOCITY_PRICING_POWER_20261101.md`
4. `research/loss_forensics/PASS4_QUADRANT_STRESS_TEST_FLOW_PRICE_OWNERSHIP_20261101.md`
5. `research/loss_forensics/PASS4_INCREMENTAL_TARGET_CORRECTION_20261101.md`

Also retrieve existing validated artifacts when needed:
- `HENGCE_HIDDEN_CONTROLLER_CONTROL_HOOK_V1_REPORT.md`
- `current100_ownership_intervals_audit.csv`
- `HENGCE_BRIDGE_RELOAD_MARGINAL_CONTROL_CAPITAL_ATLAS_V0_20261029.md`
- `HENGCE_OPERATOR_IDENTITY_CONFLICT_ATLAS_V1_20261029.md`
- `HENGCE_OPERATOR_BUY_SELL_BEHAVIOR_MAP_V0_20261029.md`

## Strongest validated evidence
### CONTROL durability
Existing CONTROL V1 target: when strong-holder ownership rises at snapshot t, does next TDCC retain at least the pre-build ownership level?
Strict expanding time-order OOS (2026-06-26 through 2026-10-16):
- AUC 0.694
- confidence >=0.70 -> 84.56% next-snapshot retention
- confidence >=0.80 -> 88.79%
- confidence >=0.90 -> 93.51%
This predicts ownership durability, not stock return.

### HOOK / release deterioration
`CONTROL FULL + HOOK READY`
- 5d mean -2.83%, median -2.05%, positive 33.7%
- 10d mean -4.20%, median -3.95%, positive 30.8%

`CONTROL FULL + HOOK READY + dBig400 < 0`
- OOS 52 events
- 5d mean -3.07%, median -3.41%
- 10d mean -5.91%, median -5.42%, positive 22.5%
- 40d median -7.52%

Existing architecture is stronger for lifecycle/exit recognition than exact entry timing.

### Negative baseline
Nine-year price/liquidity-only preliminary out-of-time discrimination was weak (roughly AUC 0.51–0.55 depending on target/model). Do not rescue price-pattern-only research by tuning.

## Current structural findings — not probability-promoted
1. One fracture is not enough: Big400 outflow, Big1000 decline, institutional selling or one breakdown cannot stand alone.
2. Same strong-holder inflow can be DURABLE REPAIR, BRIDGE RELOAD, or NEW CONTROL TAKEOVER.
3. `Big1000 down + Mid up` alone has formal weight 0: it may be parking/inventory elasticity; only progression into broader leakage matters.
4. Raw professional flow is insufficient. Candidate economic unit:
   `VISIBLE FLOW x PRICE RESPONSE x OWNERSHIP RESPONSE x LEVERAGE QUALITY`.
5. Structural quadrants:
   - selling + resilient price + ownership repair/strengthening + leverage contained -> ABSORPTION_CANDIDATE
   - selling + resilient price + ownership leakage / weak-hand financing -> DISTRIBUTION_WITH_PRICE_SUPPORT
   - buying + positive response + durable ownership + contained leverage -> SPONSORSHIP_EFFECTIVE
   - buying + weak/collapsing response + ownership leakage -> SPONSORSHIP_INEFFECTIVE
6. These are hypotheses only until held-out numeric validation.

## Critical Repair Velocity correction
Do NOT build another model merely predicting next-snapshot ownership durability. CONTROL V1 already does this.

The legitimate incremental target is **recognition latency**:

> After FIRST_FRACTURE or apparent repair/reload at ownership snapshot t, can daily and cross-stock evidence available AFTER t becomes known but BEFORE t+1 TDCC distinguish DURABLE_REPAIR from BRIDGE_RELOAD / FAILED_REPAIR earlier than CONTROL confirmation?

Any new value must come from earlier recognition, not duplicate next-snapshot retention classification.

Candidate early evidence:
- normalized professional flow after t
- market/sector/regime-adjusted residual price response
- source leverage quality / margin path
- destination preload already observable at t
- destination daily sponsor flow / relative strength after t
- optional source-out / destination-in execution mirror

## Frozen Pass 3 task
Execute `STATE_INTERACTION_PREREGISTRATION_PASS3_20261101.md` exactly as preregistered.
No threshold retuning after viewing forward labels.

Compare:
- BASE = CONTROL + HOOK
- BASE + CORE_LOOSENING
- BASE + BRIDGE / DESTINATION_PRELOAD
- BASE + PROFESSIONAL_FLOW corroboration

Primary metrics:
- held-out Brier score
- held-out log loss
- calibration / reliability
- coverage / abstention
- AUC secondary

Promotion rule: if a new family does not improve held-out probability quality without material calibration damage, formal weight = 0.

## Corrected Pass 4 task
After Pass 3, test the incremental pre-TDCC classifier:
- predictors may use only data available from t availability through before t+1 TDCC;
- t+1 ownership is future label only;
- no future destination reconcentration may leak into predictors;
- compare probability quality against CONTROL+HOOK available at t;
- explicitly measure recognition-latency gain in trading days.

Potential flow-price implementation:
1. normalize professional flow by volume;
2. remove market/sector/regime price component using earlier data only;
3. calculate out-of-time residual price response;
4. interact with ownership state at t and leverage quality;
5. test Brier/log-loss/calibration improvement.
Avoid unstable return/net-flow ratios near zero flow.

## Compute status at handoff
The previous chat's local Python, visible Python, and later container execution repeatedly returned system-level `ClientError` during the final numeric phase.
Therefore:
- Pass 3 full-sample numeric test is NOT completed.
- Pass 4 incremental probability/latency test is NOT completed.
- No new Brier/log-loss/calibration improvement is claimed.
If compute works in the new chat, execute the frozen tests directly. If compute remains unavailable, do not invent results.

## Non-negotiable governance
- Facts, inference, and causality must remain separated.
- Retrieval failure != data absence.
- Corporate-action effects must be adjusted/censored.
- TDCC reference date != knowledge date; preserve availability semantics.
- Foreign/trust/dealer are observable vehicles, not beneficial-owner identity.
- Same playbook or baton timing != same person.
- Level C identity requires independent broker/account/legal evidence.
- Retrospective labels cannot be presented as live signals.
- No silent retuning or post-hoc threshold hunting.
- A probability requires held-out calibration; raw weighted scores are not probabilities.
- ABSTAIN / NO_EDGE is valid and preferred to fake precision.

## Next action
Do not spend the first turn re-explaining the architecture. Bootstrap authority, verify compute/data, and execute Pass 3. If successful, immediately continue to corrected Pass 4 recognition-latency validation.