# HENGCE Prospective Live Collector — Deployment Audit

Date: 2026-11-01
Branch: `research/loss-forensics-20261101`
Trading authority: **NONE**
Production authority: **NONE**

## Authority chain

Historical actual-availability authority remains:

- parent/current-state commit: `a899174ca07b2831740365fb02b8c87c7eecff89`
- `HISTORICAL_LATENCY = DATA_BLOCKED`

Verified Fugle transport commit:

- `77b0cdf9fb5fa3c1097fa6df82213c0c895d79a8`
- parent: `a899174ca07b2831740365fb02b8c87c7eecff89`
- validated transport fact carried forward: current100 single-symbol `/intraday/quote/{symbol}` = 100 requested / 100 success / 0 failure
- authority remains `SHADOW_INTRADAY_ESCAPE_RESEARCH_ONLY_NO_FORMAL_EOD_RANKING_OR_TRADING_AUTHORITY`

The transport commit does not supersede or weaken the historical `DATA_BLOCKED` conclusion.

## Prospective collector definitions now committed

### Fugle current100

`.github/workflows/hengce-escape-twse-full-market-fugle.yml`

The collector now preserves, per successful symbol response:

- request-start time;
- response-received time;
- Fugle `lastUpdated`;
- last-trade time;
- exact received HTTP response-body SHA256;
- HTTP Date / Last-Modified / ETag when present;
- quote date and selected observed market values;
- current observed industry code with universe provenance.

Each successful run additionally writes an immutable prospective observation under:

`research/loss_forensics/prospective_live/observations/YYYY/MM/DD/`

Formal h=1 probability/classification remains null while the exact frozen executable is not hash-bound.

### TDCC

`.github/workflows/hengce-prospective-tdcc-first-observed.yml`

The collector is designed to preserve:

- official public endpoint request-start and response-received time;
- exact raw response payload under a content hash;
- raw SHA256;
- parseable snapshot/reference date candidates;
- HTTP Date / Last-Modified / ETag when present;
- immutable first-observed record for each exact payload hash;
- every poll attempt, including failures;
- `official_published_at = null` unless independently proven.

The TDCC first-observed timestamp is a collector receipt timestamp / conservative public-by upper bound. It is not silently relabeled as the exact official publication timestamp.

## Deployment finding

The repository default branch is **`main`**.

GitHub scheduled workflows execute from the default branch. The prospective collector definitions currently exist on the research branch, so their `schedule:` entries are **not evidence that unattended collection is active** on this branch.

The workflows include `workflow_dispatch`, so an explicitly dispatched run using this branch can create valid post-protocol evidence. However, no post-protocol live observation is counted merely because the workflow files exist.

Therefore the current operational status is:

- research phase: `PROSPECTIVE_LIVE_LATENCY = COLLECTING`
- collector specification: `DEFINED_AND_FROZEN_ON_RESEARCH_BRANCH`
- unattended scheduler deployment: `NOT_ESTABLISHED_ON_RESEARCH_BRANCH`
- post-protocol eligible Fugle observation count verified by this audit: `0`
- post-protocol eligible TDCC first-observed payload count verified by this audit: `0`

`COLLECTING` describes the prospective cohort/research phase, not a false claim that a scheduler is currently executing.

## Required deployment action before claiming continuous collection

Without changing any research semantics, the frozen collector must execute from a scheduler-active context or be explicitly dispatched on the research branch.

Moving/deploying the workflow definition to `main` would be an operational deployment change and is **not performed by this audit**, because the requested write scope is the research branch.

## Interpreter status

No separately versioned exact Pass 4 frozen executable/model artifact was identified on this branch during this setup. Therefore:

`INTERPRETER_BINDING_STATUS = INTERPRETER_BINDING_PENDING_FROZEN_EXECUTABLE`

The collector does not reconstruct an approximate model from prose and does not promote the source-only diagnostic into the frozen primary model.

## Historical separation

Nothing in this deployment work changes:

`HISTORICAL_LATENCY = DATA_BLOCKED`

If historical publication provenance is recovered later, historical latency requires a separate preregistration before rerun.
