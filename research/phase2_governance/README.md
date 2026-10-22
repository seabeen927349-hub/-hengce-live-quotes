# Scoped E2 P2-A authorization — Issue #24 / PR #25

Human authorization: **HENGCE-P2-AUTH-20261023-001**.
Authoritative base: `main@f10463b07a25d647c0ce6762be2661005eebfeef`.
Original receipt commit: `71ef7d3dbc83715c6bff23ac809c4e21dee48a3b`.

This supersedes Issue #22's blanket run denial only for the scoped permission
below. **This authorization PR runs no optimizer, model trial or actual P2-A
diagnostic, appends zero experiment records and opens/accesses no holdout.**
Engineering Replay remains the required frozen-baseline equivalence check.

## Scope and permission gate

`phase2-policy.json` records phase2_authorized=true with the explicit human
authorization ID. This Boolean grants no unscoped route. The engine scopes are:

- E2: P2A_BASELINE_DESTRUCTION_ONLY.
- Q017: PROSPECTIVE_CHARACTERIZATION_ONLY; no historical tuning.
- M1: RESEARCH_SHADOW_ONLY_NO_OPTIMIZATION, capital 0.

`require_phase2_run(policy, engine, stage, operation)` admits only **E2 /
P2A_BASELINE_DESTRUCTION** and these six operations:

1. BASELINE_REPLAY on already exposed development/validation data with proven lineage.
2. COST_STRESS at 1.0x / 1.5x / 2.0x on the existing aggregate 0.008.
3. LEAVE_BEST_TRADES_OUT.
4. LEAVE_ONE_YEAR_OUT.
5. REGIME_CHARACTERIZATION.
6. PARAMETER_PERTURBATION_ROBUSTNESS locally around the frozen baseline.

These are robustness diagnostics, without new candidate creation/acceptance.
P2-B/P2-C, grid/random/Bayesian search, unrestricted feature mining, historical
signal regeneration, Q017 tuning, M1 optimization, holdout access and production
routes are denied. Unknown request fields/operations and missing scope fail closed.
The original receipt bytes are pinned to their SHA256; the complete reviewed
policy is pinned separately, including pending/null values and unknown-key rejection.
Editing a JSON Boolean, authority field, receipt or pending acceptance value
cannot silently authorize a broader route.

The gate returns **SCOPED_GATE_ALLOWED_NO_EXECUTION**, authorization ID, operation,
zero execution authority, budget/cost metadata and execution prerequisites.
It imports no model or market provider, dispatches no workflow and reads no data
panel. It is a permission validator, not a research runner or trial allocator.

A metadata-only CLI check is:

```text
python -B research/phase2_governance/ledger_store.py check-run --engine E2 --stage P2A_BASELINE_DESTRUCTION --operation BASELINE_REPLAY
```

COST_STRESS additionally requires `--cost-multiplier 1.0`, `1.5` or `2.0`.
The check returns before append/custody code; it cannot run an experiment.
Unscoped `check-run`, other engines/stages and unauthorized requests return BLOCKED.

**Actual diagnostic experiments require authorization PR #25 to be merged,
proven input lineage, and the existing append-only ledger plus independent
checkpoint process.** This PR does not execute or integrate a model runner.
A permission response alone is not evidence of a completed trial, checkpoint,
lineage validation or merge. No production authority is derived from it.

## Approved rules versus still-pending acceptance

Scoped human approval now covers chronological-only/no random split, expanding
walk-forward method, purge >=20 TWSE sessions, embargo >=20 TWSE sessions, initial
family budget max 24 evaluated variants, retention/counting of FAILED / REJECTED /
ABORTED trials, the frozen aggregate roundtrip cost 0.008 and 1.0/1.5/2.0x cost stress.
Approving the walk-forward method does not authorize P2-B or invent fold boundaries.

Minimum observations, minimum trades, drawdown/tail-loss/turnover and cost-stress
acceptance thresholds, exact P2-B fold dates/steps, prospective custody/access
and a family correction-rule specification remain **PENDING_HUMAN_APPROVAL**,
with no invented numeric values. They block candidate ACCEPT and later stages;
they do not veto the six allowed P2-A diagnostics. Candidate creation/acceptance
and holdout access remain explicitly false.

Cost stress scales the **single aggregate** assumption: 0.008, 0.012 and 0.016.
It does not decompose fees/tax/spread/slippage or add components on top. Baseline
max_slots=1, overlap forbidden, next-open entry and fixed20 exit are unchanged.
Every currently exposed 2023–2026 date remains development/validation eligible
only where lineage is proven, never pristine holdout. Daily OHLC is not
substitute evidence for historical Q017 09:01 executability.

B01–B09 remain PARTIAL. B10 becomes **SCOPED_AUTHORIZED_E2_P2A_ONLY**, not broad
Phase 2 clearance. P2-B/P2-C/candidate acceptance/holdout/production remain blocked.
Actual user trades are not model evidence.

## Existing environment, ledger and independent custody remain intact

The research-only environment stays pinned to CPython 3.12.14 / Linux x86_64,
fourteen dependency versions and exact manylinux2014/cp312 wheel hashes. CI uses
a separate venv and hash-required offline installation from downloaded wheels.
No production dependency/runtime/schedule/model/ranking/universe file changes.
The environment lock retains its original Issue #22 baseline and no-authority
flag; an environment manifest cannot grant or veto a later scoped human grant.

The unchanged experiment.schema.json and existing chain validator still govern
canonical JSONL, unique IDs, earlier same-engine parents, exact byte prefix,
process-safe append/O_APPEND/O_NOFOLLOW/fsync and retention of failed/rejected/
aborted records with null unavailable metrics. REJECTED remains decision=REJECT
under the existing schema. Immutable PROPOSED rows are never edited in place;
a subsequent audit event requires its own ID and earlier parent lineage.

The original record-level capital_authority=0 and phase2_authorized=false mean
audit records cannot self-grant authority. They are not a replacement for the
new policy's scoped authorization. Ledger contract/checkpoint flags likewise
grant no execution authority. All research permission/checkpoint envelopes enforce
capital_authority_twd=0, broker_order_execution=false,
PROMOTE_TO_PRODUCTION=FORBIDDEN.

The appender reads an independent external checkpoint and cannot checkpoint its
own write. A separate custody actor conditionally retains write-once numbered
checkpoints outside repository/ledger trees, binding count/head/exact prefix,
generation, prior checkpoint, identity and timestamp. An uncheckpointed or
partial tail stops further operations without truncation. CI also verifies
the independently retained GitHub PR-base ledger prefix; this authorization
transition specifically requires the ledger to remain empty. No second publisher
or automatic repair/reset is introduced.

Independent custody deployment remains PENDING_HUMAN_APPROVAL_NOT_DEPLOYED.
An external directory/custodian label is not authentication; separate identities,
ACL/WORM/versioned retention, checkpoint delivery and access audit must be
configured before actual experiments rely on it. No independent account, secret,
storage service or retention approval is provisioned here. An adversary controlling
ledger, custody and trusted Git history is outside the mechanism's protection.
No signature service or universal tamper-proof storage is claimed.

## Holdout, tests and limitations

The real holdout metadata remains **UNALLOCATED**, with no custodian, commitment,
allocation or access. Pure in-memory synthetic metadata tests preserve irreversible
UNALLOCATED→SEALED→OPENED→CONSUMED, permanent exposure and no second open.
There is no holdout data reader, release API or real transition writer here.

The new tests check six allowed E2/P2-A operations, denied Q017/M1/P2-B/P2-C,
holdout/candidate/capital/broker/promotion/search routes, cost stress, pending
acceptance semantics, policy/receipt tampering and zero authorization-PR records.
Existing ledger/anchor/failed-trial/holdout tests remain required. CI never invokes
a diagnostic runner: only synthetic permission tests and Engineering Replay.

Limitations remain: non-hermetic OS/kernel/interpreter-build/bootstrap provenance;
single wheel target; custody deployment/identity approval outstanding; sparse
E2 and incomplete Q017/M1 evidence; no automatic live trial registration or
ledger-derived budget allocation implemented in this permission-only package.
A later actual runner must enforce family-wide max 24, count failed/rejected/
aborted evaluated variants, preserve causal lineage and checkpoint every trial.
These limitations do not turn pending acceptance values into a P2-A veto.

Final-head Engineering Replay must complete successfully with 11/11 IDENTICAL,
alongside Governance, Writer Race, Health, Recovery and existing producer
regressions. CI IDs and exact inventory belong in PR #25. **NO OPTIMIZER WAS RUN.
NO MODEL TRIAL WAS RUN. Keep PR OPEN / DRAFT; do not merge automatically.**
