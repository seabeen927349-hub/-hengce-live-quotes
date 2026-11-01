# HENGCE Loss Forensics OOS Judge — START HERE

Date: 2026-11-01
Purpose: cross-chat / cross-session bootstrap. Do **not** rely on conversational memory for this research.

## Mandatory read order

Read these exact artifacts before making any claim about prospective OOS progress, success, failure, or promotion:

1. `research/loss_forensics/PROSPECTIVE_ACTUAL_AVAILABILITY_PROTOCOL_20261101.md`
2. `research/loss_forensics/LOSS_FORENSICS_PROSPECTIVE_OOS_EVALUATION_PREREGISTRATION_20261101.md`
3. `research/loss_forensics/LOSS_FORENSICS_OOS_GOVERNANCE_LOCK_20261101.json`
4. `research/loss_forensics/CURRENT_STATE_LOSS_FORENSICS_OOS_JUDGE_20261101.json`
5. `research/loss_forensics/LOSS_FORENSICS_OOS_CANDIDATE_ARM_CARD_20261101.json`
6. the latest prospective immutable evidence ledgers referenced by current state
7. any later explicit freeze/ARM anchor whose authority chain descends from this governance

Then run:

`python3 scripts/hengce_loss_forensics_oos_governance_validate.py`

If the validator does not pass, stop and report the exact inconsistency. Do not repair semantics from memory.

## Current state at creation

- raw prospective data collection: allowed
- formal 60-day OOS clock: **NOT STARTED**
- candidate: **UNASSIGNED**
- ARM: **NOT_ARMED**
- formal OOS days: **0**
- formal conclusion: **NONE**
- production authority: **NONE**
- trading authority: **NONE**

This state is intentional. Historical research and raw prospective collection do not become formal OOS simply because data exist.

## What must happen before formal Day 1

One exact candidate must be frozen with:

- hypothesis;
- event definition;
- eligible universe and exclusions;
- exact control/matching construction;
- one primary endpoint and one primary horizon among T+1/T+5/T+20;
- expected direction and null;
- non-null minimum practical effect;
- exact outcome handling;
- exact dependence/statistical method;
- exact required collectors;
- exact feature/event extractor executable or deterministic query package with Git blob SHA;
- actual-availability provenance contract for every required input.

Only after every ARM gate passes may `arm_status` become `ARMED` and the formal start date be set to a future TWSE trading session under the frozen rule.

## Fixed evaluation bounds

- target valid formal trading days: 60
- maximum extension: Day 90, **event/diversity scarcity only**
- minimum valid events: 120
- minimum distinct event dates: 24
- minimum distinct symbols: 30
- maximum one-date share: 20%
- maximum one-symbol share: 10%
- minimum valid-day integrity share: 80%
- chronological stability: expected sign in >=3 of 4 blocks
- T+1/T+5/T+20 are outcome horizons; only one is primary for a candidate
- last included primary outcome must mature before final evaluation
- formal evaluation execution count: at most one per cohort

## Legal interpretations

`PREARMED_DATA_COLLECTING` means raw evidence is being gathered but performance judgment is forbidden.

`COLLECTING` means candidate is ARMED and formal prospective days are accumulating.

`INSUFFICIENT_EVENTS` at Day 60 permits only the bounded scarcity extension.

`OOS_INCONCLUSIVE_LOW_EVENT_RATE` closes the cohort at Day 90 if diversity remains inadequate.

`OOS_FAIL` means stop with formal weight 0. No rescue inside the same cohort.

`OOS_MIXED` is research-interest only, formal weight 0.

`OOS_PASS_CANDIDATE` is not validation and never creates trading authority.

`VALIDATED` cannot be assigned by this first cohort. It requires a second untouched confirmation cohort under a new preregistration.

## Permanent prohibitions

Do not:

- backdate `actual_known_at`;
- count pre-ARM observations in formal OOS;
- change thresholds after outcomes;
- switch primary horizon/metric after outcomes;
- add filters after outcomes;
- extend because p-value/effect size is disappointing;
- use secondary endpoints to rescue a failed primary;
- resurrect `CORE_LOOSENING`, `BRIDGE/DESTINATION_PRELOAD`, or `PROFESSIONAL_FLOW` without a separate new preregistration;
- use 6415/3042 as tuning anchors;
- reconstruct missing Pass 4 interpreter from prose;
- call collection or a passed research cohort production/trading authority.

## Cross-chat rule

If a future conversation remembers something different from these files, the repository authority wins. If the files themselves conflict or hashes fail, fail closed. Do not choose the more convenient interpretation.

## Failure policy

Failure is an allowed and expected scientific outcome. The system must prefer an honest `OOS_FAIL`, `OOS_MIXED`, `DATA_QUALITY_FAIL`, or `OOS_INCONCLUSIVE_LOW_EVENT_RATE` over an invented success.
