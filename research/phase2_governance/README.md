# Phase 2 readiness governance freeze — Issue #22

**NOT_READY_FOR_PHASE2_RUNS_YET. NO OPTIMIZER WAS RUN.**

Authoritative base: `main@42f4d4edd4b327c693290416d54d1e7622733969`.
This package implements research governance infrastructure only. It grants no
Phase 2, profitability search, challenger, holdout, capital, broker or production
authority. Every production file and existing workflow remains unchanged.

## Environment and dependency lock

`environment-lock.json` freezes CPython **3.12.14**, Linux x86_64, the target wheel
platform, fourteen direct/transitive package versions, exact wheel filenames and
SHA256 hashes. `requirements.lock` installs those artifacts with
`--require-hashes`. The original experiment/holdout schemas, audit validator, E2
source and baseline model/execution locks are hash-bound to the exact base.
Existing Phase 1 pins are preserved, with the schema validator's dependencies
added in a separate research environment. Nothing installs into production.

The CI job creates its own venv, downloads only the locked manylinux2014/cp312
wheels and installs offline from that directory. This avoids platform-dependent
wheel selection drifting to an unlisted artifact. Runtime checks verify Python,
platform, all versions and source hashes. This is not a hermetic OS/container
build: kernel/OS image, interpreter binary digest and bootstrap pip are not fully
frozen. B01 remains PARTIAL. Other platforms require a separately reviewed lock.

## Experiment ledger

`ledger/experiments.jsonl` is initially **empty**. No real trial, hypothesis test
or profitability result is inserted by this PR. `ledger_store.py` reuses the
unchanged `research/phase1_audit/experiment.schema.json` with Draft 2020-12
validation, plus the existing hash-chain/append validator. The record schema's
`capital_authority=0` and `phase2_authorized=false` remain mandatory.
`ledger-contract.json`, the policy and all checkpoint/output envelopes enforce
`capital_authority_twd=0`, `broker_order_execution=false`,
`PROMOTE_TO_PRODUCTION=FORBIDDEN`; adding fields to the old record schema would
violate its additionalProperties=false contract, so it is not silently extended.

Records are canonical UTF-8 JSON lines, with exactly one final newline per row.
Append validates unique experiment IDs, earlier same-engine parents, hashes,
timestamps and the exact old byte prefix before writing. It uses a process-safe
file lock, O_APPEND/O_NOFOLLOW and fsync. It never updates/deletes a previous row.
FAILED and ABORTED must have decision REJECT. The schema encodes **REJECTED as
decision=REJECT**, not as an invented result enum. COMPLETED/REJECT and failed
records remain retained; unavailable metrics remain null. Audit logging itself
never authorizes or executes a recorded trial. All records count toward the
retained audit count; there is no success-only filter or failure deletion.

An immutable PROPOSED row cannot be updated in place. A later audit event needs
its own unique ID and an earlier parent ID, retaining the original proposal.
The pending family/multiple-testing policy must account for every attempted
variant and all failed/rejected/aborted attempts; this package does not activate
a trial budget, run experiments or claim automated runner registration.

## Independent checkpoint mechanism

A self-contained chain cannot prove that its whole history was not rewritten.
Two additional boundaries are implemented:

1. **External custody actor:** `checkpoint.py` retains write-once, numbered
   checkpoint files outside both repository and ledger trees. Each contains a
   ledger ID, count, head, exact prefix SHA256, generation, prior checkpoint hash,
   custody identity and timestamp. Initialization accepts only an empty ledger.
   Checkpoint advance requires an exact expected checkpoint token and exactly
   one schema-valid appended row; the old independently retained prefix must
   still match. Checkpoint publication uses atomic create-if-absent plus fsync;
   previous checkpoints are never replaced by the API.
2. **Independent Git base anchor:** CI obtains the PR base SHA from GitHub and
   checks that the proposed ledger preserves its exact bytes. A rewritten local
   ledger plus rewritten in-tree metadata cannot redefine that trusted prefix.
   The initial Issue #22 base has no ledger, so its only accepted genesis is the
   explicitly empty ledger. This bootstrap cannot insert genuine trial rows.

The **appender only reads external custody**, and must receive its trusted
expected checkpoint token. It cannot checkpoint its own append. After one
append, another append STOPs until the independent custodian validates and
checkpoints it. Stale tokens, root overlap, symlinks, schema/hash/identity/prefix
conflicts, partial lines and uncheckpointed tails fail closed. A crash keeps any
partial tail visible; neither actor truncates it or discards failed records.
Ambiguous operations require independent inspection, not blind retry/rewrite.

Deployment is still **PENDING_HUMAN_APPROVAL_NOT_DEPLOYED**. An external path and
custodian name are not authentication. The selected service must enforce a
separate identity and ACL/WORM/versioned retention inaccessible to the ledger
writer, plus trusted checkpoint delivery and access audit. No independent
account, secret, custody service, retention policy or approval is provisioned in
this PR. Tests use sibling temporary directories and a plainly synthetic actor.
If one adversary controls ledger, external custody and trusted Git history,
this mechanism cannot establish authenticity. It does not claim a signature
service or independently operated custody simply because an API exists.

CLI entry points are metadata-only:

```text
ledger_store.py verify --ledger ... --custody-root ... --expected-checkpoint ...
ledger_store.py append --ledger ... --custody-root ... --expected-checkpoint ... --record ...
checkpoint.py initialize-empty --ledger ... --custody-root ... --expected-checkpoint 000...000 --custodian-id ...
checkpoint.py checkpoint --ledger ... --custody-root ... --expected-checkpoint ... --custodian-id ...
ledger_store.py check-run  # always BLOCKED in this readiness package
```

The checkpoint CLI belongs to the separate approved custody actor, not the
research writer. These examples do not configure or authorize that deployment.

## Policy, human approvals and holdout

`phase2-policy.json` fixes the requested readiness scope: E2 is the **candidate**
for first optimization research, Q017 is prospective/characterization only, and
M1 is RESEARCH_SHADOW_ONLY with no optimization. Engines remain separate.

All eight required approval categories are PENDING_HUMAN_APPROVAL, with
approved_value=null and authorization_id=null. Recommendations are separately
PROPOSED: chronological expanding walk-forward, purge and embargo at least 20
TWSE sessions, at most 24 initial family challenger variants, aggregate cost
stress 1.0/1.5/2.0x, and preregistered robustness/risk checks. Fold boundaries,
minimum observations/trades, numeric drawdown/tail/turnover acceptance, correction
rule and custody/access details remain null pending evidence and human policy.
Recommendations have no execution authority. The run guard always rejects;
changing a Boolean or supplying a made-up approval ID cannot unlock it.

E2's existing **aggregate roundtrip_cost=0.008** remains unchanged. It is not
decomposed into fees/tax/spread/slippage or added on top of component costs.
Baseline execution remains max_slots=1, overlap forbidden, next-open entry,
fixed20 exit. The proposed stress panel scales the aggregate once; it is not run.

All currently exposed 2023–2026 historical data are development/validation
eligible only where lineage is proven, **never pristine holdout**. Q017 daily
OHLC cannot substitute for missing 09:01 executability evidence; no historical
observation reconstruction or signal regeneration occurs.

`holdout-state.json` remains UNALLOCATED, with no custodian, artifact commitment,
date allocation or access. Pure metadata validation enforces
UNALLOCATED→SEALED→OPENED→CONSUMED; OPENED is permanently exposed, including
interrupted/failed evaluation. No reverse/reseal/second open is valid. Tests use
invented 2099 metadata in memory only. There is no holdout data reader, release
API, real transition writer or opened dataset in this package. Actual allocation,
custody and one-time access need explicit later approval after candidate freeze.

One explicit human authorization event is still required for research scope,
walk-forward, purge/embargo, trial budget/multiple-testing, aggregate cost/stress,
minimum observations/trades, risk/turnover gates and prospective custody/access.
Separate promotion authorization would still be required after any future
successful research/holdout. This package cannot issue either authorization.

## B01–B10 and merge gates

B01–B09 remain **PARTIAL**, including the improved environment/ledger mechanisms;
infrastructure completion is not lab-wide dataset/executability/custody evidence.
B10 remains **BLOCKED_PENDING_EXPLICIT_HUMAN_AUTHORIZATION**.
M1 stays RESEARCH_SHADOW_ONLY / capital 0. No actual user trades are model evidence.

The new workflow is paths-filtered to this governance package and itself, with
read-only permissions and no producer schedule or publication. Tests demonstrate
production bytes/scope unchanged, failed-trial retention, exact append prefix,
chain integrity, independently anchored rewrite/truncation detection, duplicate
IDs, stale/concurrent appenders, partial writes, pure holdout irreversibility,
pending approvals, aggregate cost integrity and unauthorized-run refusal.

Final-head Engineering Replay must be a completed successful workflow with all
11 checks IDENTICAL; Writer Race Safety, Health Observability, Recovery Fault
Safety, existing producer regressions and governance tests must pass. CI IDs,
exact file inventory and unresolved limitations belong in the PR. Human review
is required. **Do not merge automatically. NO OPTIMIZER WAS RUN.**
