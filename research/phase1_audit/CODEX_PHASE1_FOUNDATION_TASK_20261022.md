# HENGCE Codex Task — Phase 1 Foundation B01–B09

## Mission
Improve the HENGCE research foundation so future optimization can be scientifically valid and auditable. Do **not** optimize Q017/E2/M1 yet. This task is limited to B01–B09 items that can be completed without Phase 2 authorization.

Base commit: `8add7e8f8467218bae19bd9e0ad75a10faab5e32`
Working branch: `codex/phase1-foundation-b01-b09-20261022`

Primary goal: maximize readiness for future after-cost expected-profit research while preserving all current production behavior exactly.

## Non-negotiable hard locks
- No Q017/E2/M1 formula changes.
- No weight changes.
- No threshold changes.
- No ranking rule changes.
- No universe-authority changes.
- No production decision rewrites.
- No historical signal regeneration or backfill.
- No optimizer/grid search/hyperparameter tuning.
- No profitability backtest/challenger search.
- No sealed holdout opening.
- No Phase 2 work.
- No broker execution enablement.
- No new capital authority.
- M1 remains `RESEARCH_SHADOW_ONLY` with `capital_authority=0`.
- Full-market/electronics-live remains transport/context only with zero ranking/signal/capital authority.
- Q017, E2 and M1 remain separate; mixed ranking is forbidden.
- Actual user trades are not model evidence.
- `PROMOTE_TO_PRODUCTION = FORBIDDEN`.

If any requested improvement would violate a lock, stop that subtask and record it as `BLOCKED_REQUIRES_EXPLICIT_HUMAN_AUTHORIZATION` instead of proceeding.

## Authoritative starting evidence
Read first:
- `research/phase1_audit/HENGCE_PHASE1_EVIDENCE_DELTA_20261022.json`
- current Q017/E2/M1 contracts and locks
- Engineering Replay workflow and tests
- current EOD, Q017 observation/decision, E2 history, electronics-live contracts

Preserve the meaning of the previous human review: B01–B09 were still PARTIAL; B10 is `BLOCKED_PENDING_EXPLICIT_HUMAN_AUTHORIZATION`.

## Work packages

### B01 — Reproducible environment / dependency evidence
Allowed:
- inventory all workflow/runtime dependencies;
- add research-only environment manifest(s);
- pin Python package versions used by research/replay tooling where safe;
- record GitHub Actions versions and runtime assumptions;
- add validation scripts/tests that detect unpinned/floating research dependencies;
- document OS/tzdata/binary assumptions that cannot be fully pinned.

Do not modify production runtime behavior solely to satisfy the audit.

Deliverables should distinguish `PRESENT`, `PARTIAL`, `ABSENT`, and `NOT_APPLICABLE`.

### B02 — Frozen baselines
Create auditable research baseline manifests for:
- Production Q017
- Production E2
- M1 Shadow
- Legacy HENGCE only if evidence is sufficient and clearly separated

Each manifest should capture where available:
- commit SHA
- formula/version/schema
- universe definition
- data cutoff
- timestamp semantics
- ranking rule
- entry/exit semantics
- cost/capital assumptions
- runtime/dependencies
- expected-output evidence paths/hashes

Critical: do not regenerate historical expected outputs. Existing evidence only.

Priority: improve the missing M1 numerical baseline evidence without changing M1 logic.

### B03 — Historical coverage / universe / calendar / corporate-action evidence
Build a read-only coverage inventory from existing repo data only.

Report by dataset and date range:
- price
- institutional
- margin
- formal complete EOD days
- electronics PIT membership
- calendar/security-master evidence
- suspension/limit/status evidence if present
- corporate-action vintage evidence if present

Do not download or backfill market history in this task.

### B04 — PIT availability / revision lineage
Inventory fields/artifacts that actually preserve:
- event timestamp
- fetched/generated timestamp
- publication timestamp
- first-seen timestamp
- revision/version history

Never infer first-seen/publication time from later files.

Create explicit gap classification for facts that are irrecoverable retrospectively.

### B05 — Executability evidence
Separate two research families explicitly:
1. `DAILY_NEXT_OPEN_RESEARCH`
2. `INTRADAY_TIMING_RESEARCH`

Inventory authentic existing evidence for 09:01/09:03/09:05, bid/ask, depth, queue, latency, fill, limit/suspension and executable volume.

Do not use daily OHLC as fake intraday evidence.

The absence of historical 09:03/09:05 evidence may block intraday timing research but should not automatically block a future daily/next-open design if its own gates are satisfied.

### B06 — Feature/regime/rejected-signal lineage
Inventory current Q017/E2/M1 lineage including:
- candidate populations
- feature values
- gates/regimes
- scores/ranks
- rejected/no-selection/no-fill records
- hashes and timestamp semantics

Do not recompute missing historical candidate lists.

Add prospective logging contracts/tests only if they have zero production authority and do not alter historical decisions.

### B07 — Costs / capital / execution constraints
Create a research-only cost/execution specification that clearly separates:
- existing frozen assumptions (e.g. E2 `cost_roundtrip=0.008`)
- observed exchange/broker rules already supported by evidence
- assumptions requiring future explicit human approval

Components should include where relevant:
- brokerage
- transaction tax
- spread
- slippage
- liquidity/participation
- lot/tick constraints
- latency/fill assumptions
- research notional/sizing

Do not invent calibration values just to clear the blocker.

### B08 — Splits / horizons / embargo / trial budget / risk gates
Prepare a governance proposal, not an optimization run.

It may define candidate policy options and evidence needed for:
- chronological train/validation/holdout boundaries
- walk-forward structure
- purge/embargo
- evaluation horizons
- minimum observations/trades
- multiple-testing/trial budget
- drawdown/tail-risk/cost/turnover gates

Do not choose exposed data as a pristine sealed holdout.
Do not finalize values that require human policy approval; mark them accordingly.

### B09 — Immutable experiment ledger / prospective holdout
Implement or specify, in research-only scope:
- append-only experiment ledger schema
- experiment ID/parent/hypothesis/code commit/data cutoff/parameters/metrics/result/accept-reject/reason fields
- failed-experiment retention
- holdout access/custody/audit-state schema
- one-time-open/consumed semantics

Do not open or populate a sealed holdout.
Do not pretend already exposed historical dates are unseen.

## B10
B10 must remain:
`BLOCKED_PENDING_EXPLICIT_HUMAN_AUTHORIZATION`

Do not clear it under any condition in this task.

## Required engineering protections
Before proposing merge:
1. Run the existing Engineering Replay.
2. Existing exact equivalence checks must remain IDENTICAL for:
   - Q017 Top3/full ranking/scores
   - authority
   - schema
   - universe
   - decision hashes
   - fail-closed behavior
   - display/router behavior
   - zero new capital authority
3. Existing regression tests must remain PASS.
4. Add targeted tests for any new research manifests/ledger/contracts.
5. Provide an explicit changed-file inventory and classify every file as research/governance/test/infrastructure.
6. If any production model/decision file changes, STOP and do not open a merge-ready PR.

## Final output expected from Codex
Open a PR from this branch or a child branch to `main` with:
- concise executive summary;
- exact changed-file list;
- B01–B09 before/after status table;
- unresolved blockers;
- explicit list of items requiring human policy approval;
- Engineering Replay run ID/result;
- regression results;
- statement that B10 remains blocked;
- statement that Phase 2 is not authorized;
- statement that no model/formula/weight/threshold/ranking/production decision was changed.

The desired outcome is **research readiness**, not higher historical performance.
