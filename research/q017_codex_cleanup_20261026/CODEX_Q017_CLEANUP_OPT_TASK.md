# Codex task — Q017-only cleanup and engineering optimization

Date: 2026-10-26 (Asia/Taipei)

## Mission

HENGCE now has exactly one formal stock-output authority: **Q017**.

Your job is to reorganize, simplify, harden and optimize the Q017 production/live pipeline **without changing Q017 model semantics**.

This is not a model-search task. It is not a tuning task. It is not permission to rescue or reuse older models.

Read first:

1. `research/q017_codex_cleanup_20261026/Q017_ONLY_HARD_LOCK.json`
2. current Q017 live/radar code and tests
3. current authority/router guards
4. current GitHub Actions workflows that capture/compute/publish Q017
5. current frozen Q017 lock/baseline evidence and the latest valid schema-5 fixtures

## Non-negotiable formal semantics

Preserve all of the following exactly:

- Q017 formal live schema = 5
- universe = TWSE listed electronics only
- formal observation = immutable 09:01 Asia/Taipei evidence
- eligible quote-row coverage = 100%
- no 09:02+ quote may repair or fabricate missing 09:01 evidence
- late market backfill forbidden
- missing/incomplete formal evidence => fail closed / no formal signal
- observation-hash and universe-hash binding must remain intact
- Q017 model formula, features, coefficients, thresholds, ranking and buy logic are frozen
- no 2026 retuning

## New authority rule from user

**Only Q017 may output formal stocks.**

All historical/research engines (including but not limited to V43, NOVA family, W1, Q1, E2, M1 and other retained experiments) may remain in the repository for audit/history/research, but they must not be reachable through the formal HENGCE stock-output path.

Do not delete historical evidence merely because it is non-authoritative. Isolate authority instead.

## Required work

### 1. Inventory and architecture map

Produce a complete map of the Q017 production path from capture -> observation -> validation -> compute -> ranking -> decision -> display/output.

Identify:

- duplicated modules
- stale compatibility layers
- redundant wrappers
- dead code
- hidden coupling to retired engines
- workflow duplication
- state files that can be confused with authority
- ambiguous `latest.json` / `decision_latest.json` ownership
- code that can create semantic drift between replay and live

Deliver:
- `INVENTORY.md`
- `ARCHITECTURE_BEFORE_AFTER.md`
- `DUPLICATE_AND_DEAD_CODE_MAP.json`
- `Q017_AUTHORITY_ROUTE_MAP.json`

### 2. Q017-only authority hardening

Trace every command/router/workflow capable of producing a user-visible stock list.

Make it impossible for any non-Q017 engine to become formal output through routing ambiguity, stale aliases, old default branches, display fallbacks or mixed-ranking code.

Required invariant:

`formal_hengce_stock_output_engine == Q017`

Retired/research engines may still emit their own clearly labeled research artifacts, but never through the formal HENGCE output surface.

### 3. Refactor for simplicity

Where safe and proven equivalent:

- deduplicate Q017 helpers
- centralize immutable Q017 constants/contracts
- reduce repeated parsing/validation
- make data/authority boundaries explicit
- isolate legacy adapters
- make one canonical code path for formal schema-5 decision computation
- remove or quarantine stale compatibility logic that is no longer needed

Do not refactor across semantic boundaries unless equivalence can be proven.

### 4. Deterministic equivalence suite

Before and after each meaningful refactor, replay the same frozen fixtures.

Prove:

- identical formal state
- identical formal buy count
- identical ticker ranking/order
- identical score values where serialized precision is part of the contract
- identical observation hash binding
- identical universe hash binding
- identical fail-closed behavior

Use byte-for-byte comparison when possible. If byte equality is impossible because of non-semantic runtime timestamps, normalize only explicitly documented non-semantic fields and prove semantic equality separately.

A semantic drift is a hard failure, not something to tune around.

### 5. Performance / reliability optimization

Allowed only after equivalence is locked.

Measure before/after:

- wall-clock runtime
- network calls during the formal 09:01 path
- repeated file reads/parses
- deterministic recompute latency
- workflow failure/retry behavior
- artifact size where relevant

Target improvements such as caching of immutable data, reduced repeated parsing, better module boundaries and faster offline tests.

Hard lock remains:

- normal 09:01 market network lane must not broaden beyond the authorized source contract
- no new live dependency may be added to make Q017 faster
- no macro/network call may leak into the 09:01 critical path if the existing contract forbids it

### 6. Tests and audit

Add/strengthen offline tests for at least:

- 09:01 observation missing => no formal signal
- 09:02/09:03 data cannot backfill 09:01
- non-electronics injection rejected
- incomplete eligible quote-row coverage rejected
- Q017-only formal router
- non-Q017 model artifact cannot become formal output
- deterministic replay from preserved observation
- observation/universe hash mismatch rejected
- stale `latest` artifacts cannot override a newer valid authority state

Provide one command or one small documented command set to run the full Q017 engineering audit offline.

## Explicitly forbidden

Do not:

- retrain Q017
- tune thresholds
- change features
- change coefficients
- change model formula
- expand the universe
- use outcomes to optimize the model
- run a new model-family search
- combine Q017 with any retired/research model
- regenerate fake historical 09:01 evidence
- replace missing PIT evidence with daily OHLC
- loosen 100% eligible quote-row coverage
- change formal timing
- merge to `main`
- grant broker/capital authority

## Expected deliverables

Place all task outputs under:

`research/q017_codex_cleanup_20261026/results/`

Required:

- `INVENTORY.md`
- `ARCHITECTURE_BEFORE_AFTER.md`
- `DUPLICATE_AND_DEAD_CODE_MAP.json`
- `Q017_AUTHORITY_ROUTE_MAP.json`
- `REFACTOR_PLAN.json`
- `EQUIVALENCE_TEST_REPORT.json`
- `PERFORMANCE_BEFORE_AFTER.json`
- `RISK_REGISTER.md`
- `FINAL_AUDIT.json`
- `REPORT.md`

Also commit code/test/workflow changes on this branch only.

## Allowed final states

Exactly one:

- `PASS_ENGINEERING_OPTIMIZATION_NO_SEMANTIC_CHANGE`
- `PASS_NO_SAFE_CHANGE_NEEDED`
- `BLOCKED_BY_MISSING_EQUIVALENCE_EVIDENCE`
- `FAIL_SEMANTIC_DRIFT_DETECTED`

## Stop condition

Stop and report immediately if you cannot prove Q017 output equivalence after a proposed refactor.

A smaller, proven-safe cleanup is preferred over a larger refactor with uncertain semantics.

No result from this task grants merge authority. Human review is required before any production merge.
