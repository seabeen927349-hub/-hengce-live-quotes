# HENGCE IF-07 Authority-Chain Correction — 2026-10-31

**Challenger:** `IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1`  
**Formal state after correction:** `EXECUTION_SPEC_BLOCKED`  
**Blocking stage:** `STAGE_B_METADATA_TRANSPORT_MECHANICS`  
**Forward returns:** `SEALED_NOT_OPENED`  
**Validation:** `NOT_OPENED`  
**Selection mutation:** `NONE`  
**Production / trading authority:** `NONE`

## 1. Why this correction exists

Two consecutive research-branch artifacts became internally inconsistent.

Commit `31709222406bc17ce4ee574b0da5f35e6270e2d8` formally recorded that:

- formal Stage B run `41187903523` / SHA `c355edbd898a714cb7ddaacd0c1bd94d90433306` used the frozen 187-event authority and performed zero retries;
- 92 events resolved and passed the metadata/PIT path;
- 52 tickers / 68 candidate events hit the explicitly fail-closed official t57 rate-limit marker;
- 11 tickers / 16 candidate events hit a 45-second connection timeout whose duration was not frozen;
- 9 tickers / 11 candidate events hit DNS resolution failure whose permanent-exclusion treatment was not frozen;
- therefore excluding those 27 transport-failure events would add an unfrozen execution rule and alter the return-tested sample;
- predecessor run `41185962038` was explicitly marked `INVALID_FOR_FORMAL_RESEARCH_EXECUTION_BUG` because it introduced unfrozen retry/backoff behavior.

The next branch commit `4da1aa30a06088ac0385cc201ab0b2f04f1da58a` then described the same invalid predecessor run `41185962038` as if its 186-event output had been legally admitted, and proceeded to identify later N3/bootstrap execution-spec gaps.

That later description cannot supersede the earlier invalidation because no authority-valid transport-handling rule or new pre-return frozen transport contract was inserted between the two commits.

## 2. Controlling authority

The controlling Stage B authority therefore remains the formal no-retry run `41187903523` together with the governance receipt created at commit `31709222406bc17ce4ee574b0da5f35e6270e2d8`.

The 186-event result from run `41185962038` is not admissible for formal IF-07 research execution.

The file `HENGCE_IF07_DISCOVERY_EXECUTION_SPEC_BLOCKED_20261031.md` from commit `4da1aa30a06088ac0385cc201ab0b2f04f1da58a` may be retained as a **secondary diagnostic** showing that N3/bootstrap mechanics are also under-specified, but its claims that the 186-event Stage B sample was legally completed have no authority.

## 3. Independent check of the frozen contracts

The frozen Stage B exact-metadata contract explicitly fail-closes blank/missing/ambiguous/rate-limited/structurally unresolved metadata, but it does not uniquely specify:

- HTTP connection-timeout duration;
- whether a transient DNS failure permanently excludes a candidate;
- retry count, retry schedule, or backoff behavior for those transport failures.

The user's execution authorization required the process to stop rather than invent missing mechanical rules at execution time.

No forward-return outcome was used in this correction.

## 4. Secondary blocker review

The frozen Null/Baseline Contract specifies N3 as same-date/same-k matched random with seed `20261031` and `10,000` draws, and requires bootstrap confidence intervals, but does not uniquely freeze PRNG implementation details or bootstrap replicate/CI construction mechanics.

Library and branch searches found no earlier frozen global implementation that uniquely supplies those missing mechanics for IF-07 without adding rules after preregistration.

These are real secondary execution-spec gaps, but they are not the controlling blocker because the legal Stage B sample itself is unresolved first.

## 5. Final legal state

`IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1 = EXECUTION_SPEC_BLOCKED`

Reason:
`FROZEN_STAGE_B_CONTRACT_DOES_NOT_UNIQUELY_DEFINE_TIMEOUT_DNS_RETRY_TRANSPORT_HANDLING`

Consequences:

- do not open Discovery returns;
- do not open Validation returns;
- do not use the 92-event sample as if transport failures were legally permanent exclusions;
- do not use the 186-event sample from the invalid retry/backoff run;
- do not add retry/backoff/timeout/DNS rules now under V0.1;
- do not complete N3/bootstrap mechanics now under V0.1;
- do not retune, rescue, or reinterpret V0.1;
- production / trading authority remains `NONE`.

This is not `MODEL_FAIL` and not `DATA_BLOCKED`. It is a governance/execution-spec failure discovered before any candidate forward return was opened.

Any future continuation that wants to test this economic hypothesis must use a separately versioned challenger / execution contract frozen before any newly affected forward-return inspection. It may not silently mutate V0.1.
