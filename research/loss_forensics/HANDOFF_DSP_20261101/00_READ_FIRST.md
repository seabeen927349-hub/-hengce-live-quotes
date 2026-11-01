# HENGCE Dynamic State Probability Engine — New Chat Handoff

Date: 2026-11-01  
Status: ACTIVE RESEARCH / SHADOW DATA ONLY / NO PRODUCTION OR TRADING AUTHORITY

## Bootstrap authority

Repo: `seabeen927349-hub/-hengce-live-quotes`  
Research branch: `research/loss-forensics-20261101`

At every new-chat start, verify the latest research branch head. If the branch advanced because a prospective collector wrote evidence, use the newest head but do not silently change the governance below.

## CURRENT AUTHORITY — READ FIRST

Read in this order before analysis or status promotion:

1. `research/loss_forensics/CURRENT_STATE_DSP_PROSPECTIVE_LIVE_COLLECTING_20261101.json`
2. `research/loss_forensics/PROSPECTIVE_LIVE_COLLECTOR_DEPLOYMENT_AUDIT_20261101.md`
3. `research/loss_forensics/PROSPECTIVE_SCHEDULED_RUN_PROOF_MANIFEST_20261101.json`
4. `research/loss_forensics/PASS4_FROZEN_EXECUTABLE_BINDING_AUDIT_20261101.md`
5. `research/loss_forensics/CURRENT_STATE_DSP_ACTUAL_AVAILABILITY_BLOCKED_20261101.json`
6. `research/loss_forensics/CURRENT_STATE_DSP_FUGLE_LIVE_TRANSPORT_VERIFIED_20261101.json`
7. `research/loss_forensics/PROSPECTIVE_ACTUAL_AVAILABILITY_PROTOCOL_20261101.md`
8. `research/loss_forensics/HANDOFF_DSP_20261101/03_RESEARCH_DRIFT_LOCK.md`

## States that must remain separate

- `HISTORICAL_LATENCY = DATA_BLOCKED`
- `PROSPECTIVE_LIVE_LATENCY = COLLECTING`
- `FUGLE_TRANSPORT = VERIFIED_100/100/0_SHADOW_ONLY`
- `TDCC_FIRST_OBSERVED = COLLECTOR_DEPLOYED_PENDING_FIRST_VERIFIED_OBSERVATION`
- `DEPLOYMENT_ENGINEERING_STATE = DEPLOYED_AWAITING_FIRST_SCHEDULE_PROOF`
- `UNATTENDED_DEPLOYMENT = NOT_ESTABLISHED`
- `INTERPRETER_BINDING = INTERPRETER_BINDING_PENDING_FROZEN_EXECUTABLE`
- `PRODUCTION_AUTHORITY = NONE`
- `TRADING_AUTHORITY = NONE`

Do not merge these into a generic statement that “the system works.”

### Deployment terminology hard lock

`DEPLOYMENT_ENGINEERING_STATE` is a non-authority operational descriptor only.

`DEPLOYED_AWAITING_FIRST_SCHEDULE_PROOF` means only that the frozen collector workflow definitions have been placed on default branch `main` with routing back to the research ledger.

It does **not** mean unattended execution has been proven.

The formal authority field remains:

`UNATTENDED_DEPLOYMENT = NOT_ESTABLISHED`

until the scheduled-run proof gate passes. Never substitute the engineering descriptor into the formal authority field.

## Historical latency remains blocked

The old corrected Pass 4 median 3 sessions means only:

`h=1 checkpoint -> next TDCC snapshot reference date`

It is **not** verified publication latency and is **not** verified market-known latency. Live transport or prospective deployment cannot retroactively validate historical availability. Historical rerun requires a separate new preregistration if exact historical provenance is later recovered.

## Fugle transport authority

Verified bounded fact:
- current100
- single-symbol `/intraday/quote/{symbol}`
- 100 requested / 100 success / 0 failure

Authority remains:

`SHADOW_INTRADAY_ESCAPE_RESEARCH_ONLY_NO_FORMAL_EOD_RANKING_OR_TRADING_AUTHORITY`

6415 and 3042 may remain members of the transport universe but may not be reinstated as primary research examples or architecture anchors.

## Prospective collector deployment — definition is on main, execution is not yet proven

Frozen Fugle collector source:
- `966a4fbb8051034ced6cdedf7f0a6f4267aad3a8`

Default-branch Fugle deployment:
- `9708f018db282ec4ddaa745c392d8ead54d65093`

Frozen TDCC collector source:
- `95812e5cb4c2f828edfecaa6327c88f750ba52d5`

Default-branch TDCC deployment:
- `32d2e7f4dd10276941e966dc4dea83fb40b0092f`

The only deployment delta is branch routing: workflows are defined on `main` so GitHub cron can see them, but checkout/pull/push target `research/loss-forensics-20261101`. Universe, endpoints, rate-limit, timestamp, hash, protocol, authority, schema and append-only semantics remain frozen.

### Important deployment status

Manual smoke dispatch was **not executed** in the deployment audit because the available GitHub connector exposed no start-workflow-dispatch action and there was no authenticated browser profile. No alternative trigger was relabeled as manual dispatch.

At the audit write, no new post-protocol Fugle observation or TDCC payload/attempt artifact had appeared. No run was proven with `event = schedule` plus a matching artifact commit.

Therefore the engineering state is:

`DEPLOYMENT_ENGINEERING_STATE = DEPLOYED_AWAITING_FIRST_SCHEDULE_PROOF`

while the formal unattended authority remains:

`UNATTENDED_DEPLOYMENT = NOT_ESTABLISHED`

Do not upgrade to `VERIFIED_SCHEDULED_COLLECTION` merely because the workflow files are on `main`.

Required upgrade proof for each collector:
1. GitHub run metadata says `event = schedule`;
2. run succeeds;
3. new immutable ledger artifact lands on research branch;
4. artifact commit SHA is verified;
5. run was not dispatch/rerun;
6. no backfill/backdating.

Manual dispatch alone never satisfies the unattended gate.

## Prospective known-at ledger doctrine

The live question is:

> What did HENGCE first know, at what time, from which exact source/payload?

Not:

> Looking back, what should HENGCE have known then?

Preserve, when genuinely observable:
- observation generated timestamp;
- Fugle source `lastUpdated`;
- individual quote/trade timestamp;
- TDCC snapshot reference date;
- TDCC exact-payload first-observed receipt time;
- TDCC official publication timestamp only with independent exact proof;
- sector classification/effective timestamp;
- regime-input actual availability timestamp;
- CONTROL/HOOK actual-known time;
- h=1 evidence actual-known time;
- next ownership confirmation actual-known time.

Reference date never substitutes for availability time. Unknown stays null. Do not backdate.

## Frozen Pass 4 interpreter — NOT BOUND

The exact executable provenance search found governance/report-level method definitions and reproducibility hashes, but did not recover all artifacts required for exact replay. In particular, exact executable preprocessing/model/refit provenance and exact row-level OOS replay artifacts were not recovered.

Therefore:

`INTERPRETER_BINDING_PENDING_FROZEN_EXECUTABLE`

Until all binding gates are satisfied and the historical frozen metrics are reproduced from exact provenance, formal outputs are forbidden:
- h=1 probability;
- h=1 classification;
- CONTROL_LOSS probability;
- calibrated early-warning probability;
- BUY / SELL.

Allowed label:

`SHADOW_DATA_COLLECTING / INTERPRETER_NOT_BOUND`

Do not reconstruct Pass 4 approximately from prose. Do not substitute source-only diagnostic. Do not retrain a look-alike HGB.

## Frozen Pass 4 protections

No changes are authorized to:
- coefficients/model semantics;
- thresholds;
- labels;
- gates;
- calibration procedure;
- live-outcome-driven tuning.

Pass 3 is not to be rerun or rescued in this thread. No new factor/model research is authorized by the current task.

## Next action

First inspect whether the prospective ledger has genuinely advanced after the deployment commits. If so, verify run provenance and artifact immutability before changing any status. If no valid scheduled proof exists, leave `UNATTENDED_DEPLOYMENT = NOT_ESTABLISHED`.

Separately, leave Pass 4 interpreter unbound unless exact pre-existing provenance is recovered and all ten binding gates pass. A missing executable is an acceptable failure; an approximate replacement is not.
