# HENGCE Prospective Live Collector — Deployment Audit

Date: 2026-11-01  
Research branch: `research/loss-forensics-20261101`  
Default branch: `main`  
Trading authority: **NONE**  
Production authority: **NONE**

## Frozen governance carried forward

- `HISTORICAL_LATENCY = DATA_BLOCKED`
- `PROSPECTIVE_LIVE_LATENCY = COLLECTING`
- historical median 3 sessions remains **snapshot-reference-date latency only**, not verified publication/market-known latency.
- Fugle verified transport remains 100 requested / 100 success / 0 failure.
- Fugle authority remains `SHADOW_INTRADAY_ESCAPE_RESEARCH_ONLY_NO_FORMAL_EOD_RANKING_OR_TRADING_AUTHORITY`.
- frozen Pass 4 coefficients / thresholds / labels / gates remain unchanged.
- no live-outcome retuning is authorized or performed.

## A1. Fugle prospective collector deployment

Frozen collector source:
- commit `966a4fbb8051034ced6cdedf7f0a6f4267aad3a8`
- `.github/workflows/hengce-escape-twse-full-market-fugle.yml`

Default-branch deployment commit:
- `9708f018db282ec4ddaa745c392d8ead54d65093`

### Mechanical routing delta only

Relative to the frozen prospective definition, the `main` deployment changes only branch routing:
1. `actions/checkout@v4` checks out `research/loss-forensics-20261101`.
2. `git pull --rebase` targets `research/loss-forensics-20261101`.
3. `git push` writes `HEAD:research/loss-forensics-20261101`.

No change was made to:
- current100 universe;
- `/intraday/quote/{symbol}` endpoint;
- Basic/free-plan rate-limit discipline;
- request / receipt / source / trade timestamp semantics;
- exact raw-response SHA256 semantics;
- prospective protocol commit binding;
- shadow-only authority;
- observation schema;
- append-only observation path;
- interpreter fail-closed behavior.

The reason for routing is operational: GitHub cron is defined on the default branch, while prospective evidence must continue to land on the research branch.

## A2. TDCC prospective first-observed deployment

Frozen collector source:
- commit `95812e5cb4c2f828edfecaa6327c88f750ba52d5`
- `.github/workflows/hengce-prospective-tdcc-first-observed.yml`

Default-branch deployment commit:
- `32d2e7f4dd10276941e966dc4dea83fb40b0092f`

The same three routing-only differences are applied: checkout, pull and push target the research branch. The frozen TDCC semantics remain unchanged:
- endpoint `https://opendata.tdcc.com.tw/getOD.ashx?id=1-5`;
- exact raw payload SHA256 and content-addressed storage;
- every poll attempt preserved;
- immutable first-observed record for each exact payload;
- snapshot reference date kept separate from availability time;
- `official_published_at = null` unless independently proven for the exact payload;
- HTTP Last-Modified is preserved but never auto-promoted to official publication time;
- first-observed time is HENGCE collector receipt time / conservative public-by upper bound.

## A3. Smoke-test and scheduled-run proof

### Manual dispatch

Status for both collectors:

`NOT_EXECUTED_TOOL_CAPABILITY_BLOCKED`

The available GitHub connector in this audit can read workflow state and rerun an existing run, but exposes no action to start a new `workflow_dispatch`. No authenticated browser profile was available to perform an equivalent GitHub UI dispatch. No alternate trigger was substituted or relabeled as a manual dispatch.

Therefore there is no manual smoke-test run ID or smoke-test artifact commit to claim.

### Scheduled run

At the final pre-authority-write check, `research/loss_forensics/prospective_live/` still contained only:
- `EVENT_LEDGER_SCHEMA_V1.json`
- `README.md`

Verified post-protocol Fugle observation count: `0`  
Verified post-protocol TDCC payload/attempt count: `0`

No GitHub run with independently verified `event = schedule` plus a corresponding new ledger artifact and artifact commit SHA was established in this audit.

For Fugle specifically, 2026-11-01 is Sunday while the frozen cron is Monday-Friday, so a legitimate Fugle scheduled collection run cannot be manufactured on this audit date.

Accordingly:

`prospective_unattended_deployment = NOT_ESTABLISHED`

The fact that scheduler-active definitions now exist on `main` is **deployment preparation**, not proof that unattended collection has executed successfully.

## Upgrade gate

The status may change to:

`VERIFIED_SCHEDULED_COLLECTION`

only after all of the following are verified for the relevant collector:
1. GitHub run metadata proves `event = schedule`;
2. collector completes successfully;
3. a new immutable observation/poll artifact is written to the research branch;
4. the artifact commit SHA is verified;
5. the run was not a manual dispatch or rerun;
6. no backfill or backdating of actual-known timestamps occurred.

Manual dispatch success alone is insufficient.

The detailed per-collector proof fields are frozen in:
`research/loss_forensics/PROSPECTIVE_SCHEDULED_RUN_PROOF_MANIFEST_20261101.json`.

## Interpreter separation

Deployment does not bind the Pass 4 interpreter. Exact executable provenance remains unresolved; see:
`research/loss_forensics/PASS4_FROZEN_EXECUTABLE_BINDING_AUDIT_20261101.md`.

Until binding succeeds, h=1 probability/classification and calibrated control-loss/early-warning probabilities remain null/forbidden.

## Final deployment state

- collector definitions on default branch: `DEPLOYED_WITH_ROUTING_ONLY_DELTA`
- evidence destination: `research/loss-forensics-20261101`
- manual smoke test: `NOT_EXECUTED_TOOL_CAPABILITY_BLOCKED`
- scheduled-run proof: `NOT_VERIFIED`
- unattended deployment: `NOT_ESTABLISHED`
- historical latency: `DATA_BLOCKED`
- prospective live latency: `COLLECTING`
- production authority: `NONE`
- trading authority: `NONE`
