# HENGCE TDCC Canonical Vessel — Self-Test State

Date: 2026-11-01
Research branch: `research/loss-forensics-20261101`
Scope: infrastructure / prospective actual-availability collection only

## Authority boundary

This record does **not** modify Pass 3, Pass 4, any model coefficient, threshold, label, gate, calibration, production authority, or trading authority.

Historical latency remains `DATA_BLOCKED`.
Prospective live latency remains `COLLECTING`.
Interpreter binding remains `DATA_BLOCKED_EXACT_EXECUTABLE_PROVENANCE_NOT_RECOVERED`.

## Canonical TDCC vessel state

The default-branch canonical TDCC workflow has been converged so ownership and provenance are derived from the exact same fetched response bytes. The former parallel polling path has been retired to a no-network verifier.

Relevant main commits:

- `ea83beb5a3a612cc43b2a0bed181724cb3890d70` — retire parallel TDCC poller to no-network verifier.
- `0f802d4f6c76ca9d70edc47e65b4af7c6497e825` — fix canonical schedule-proof push path by clearing expected transient worktree changes after the evidence commit and before `git pull --rebase`.

## Failure diagnosis and repair

A genuine native `event=schedule` run reached the canonical TDCC fetch and provenance validation successfully, created the intended schedule-proof evidence inside the runner, but failed at the final commit/push plumbing stage because same-payload transient worktree changes blocked `git pull --rebase`.

The failure therefore did **not** establish a TDCC source failure, payload-integrity failure, provenance failure, or model failure. It was an infrastructure transport/push failure.

The repair in `0f802d4f...` is deliberately narrow: after the evidence commit, expected transient TDCC worktree state is restored/cleaned before rebase and push. No research semantics were changed.

## Self-test result

The workflow triggered by push of `0f802d4f6c76ca9d70edc47e65b4af7c6497e825` completed successfully.

Formal classification:

- `CANONICAL_WORKFLOW_REPAIR_SELFTEST = PASS`
- `NATIVE_SCHEDULE_PROOF = PENDING`
- `UNATTENDED_DEPLOYMENT = NOT_ESTABLISHED`
- `PROSPECTIVE_LIVE_LATENCY = COLLECTING`
- `HISTORICAL_LATENCY = DATA_BLOCKED`
- `PRODUCTION_AUTHORITY = NONE`
- `TRADING_AUTHORITY = NONE`

A successful push-triggered run MUST NOT be substituted for a native `event=schedule` proof.

## Upgrade gate

Native scheduled proof may be upgraded to PASS only after a run using the repaired workflow satisfies all of the following:

1. GitHub event is exactly `schedule`.
2. Run conclusion is `success`.
3. The canonical TDCC fetch/provenance checks pass.
4. The schedule-proof evidence is actually persisted to `main`.
5. The persisted evidence is traceable to the scheduled run and payload SHA.
6. No backfill, manual timestamp substitution, or reference-date substitution is used.

Until all six gates pass, governance must continue to report native scheduled proof as `PENDING` and unattended deployment as `NOT_ESTABLISHED`.

## Drift lock

Do not use this infrastructure repair to reopen historical latency, rescue any rejected family, alter Pass 4, claim calibrated early-warning probability, or create buy/sell authority.
