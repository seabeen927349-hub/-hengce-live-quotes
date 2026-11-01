# HENGCE DSP / Loss Forensics — Prospective Actual-Availability Live Protocol

Date: 2026-11-01
Branch: `research/loss-forensics-20261101`
Historical authority parent: `a899174ca07b2831740365fb02b8c87c7eecff89`
Fugle transport authority parent: `77b0cdf9fb5fa3c1097fa6df82213c0c895d79a8`
Trading authority: **NONE**
Production authority: **NONE**

## 1. Two states are permanently separated

- `HISTORICAL_LATENCY = DATA_BLOCKED`
- `PROSPECTIVE_LIVE_LATENCY = COLLECTING`

The Fugle current100 transport result does not alter the historical availability audit. Historical TDCC publication-time provenance remains insufficient under `CURRENT_STATE_DSP_ACTUAL_AVAILABILITY_BLOCKED_20261101.json`.

The prior Pass 4 statement that the h=1 checkpoint was a median three trading sessions before the next TDCC **snapshot reference date** must not be interpreted as real market recognition latency. It is not evidence of how long before the ownership confirmation became publicly knowable.

## 2. Verified transport fact and its authority

The current100 single-symbol Fugle Developer API transport using `/intraday/quote/{symbol}` has been verified at:

- requested: 100
- success: 100
- failure: 0

Its authority is transport/research only:

`SHADOW_INTRADAY_ESCAPE_RESEARCH_ONLY_NO_FORMAL_EOD_RANKING_OR_TRADING_AUTHORITY`

This success authorizes live evidence collection. It does **not** authorize production, trading, BUY/SELL conversion, probability promotion, or historical latency validation.

## 3. Research question

Prospectively, from evidence captured after this protocol is frozen:

> Can the frozen h=1 early-evidence mechanism identify CONTROL deterioration before the next ownership confirmation is actually knowable, and if so, by how much clock/calendar/trading time?

No retrospective reconstruction may substitute for live first-observed evidence.

## 4. Required timestamp chain

Each prospective observation/event must preserve, where the source actually exposes it:

1. observation generated timestamp;
2. Fugle request/response receipt timestamp and source `lastUpdated` timestamp;
3. individual quote/trade timestamp;
4. TDCC snapshot reference date;
5. TDCC actual first-observed timestamp, and official publication timestamp only when independently evidenced;
6. sector classification and its effective timestamp when independently evidenced; otherwise first-observed classification time plus `effective_from = null`;
7. each regime input's actual availability timestamp and regime computed-at timestamp;
8. CONTROL/HOOK state and the timestamp at which all required inputs were actually knowable;
9. h=1 early evidence and the timestamp at which all required inputs were actually knowable;
10. next ownership confirmation reference date and the timestamp at which the exact confirmation payload was first observed / publicly knowable.

Reference date and availability time are different fields and may never be substituted for one another.

## 5. Timestamp semantics

### `first_observed_at`
The first timestamp at which the HENGCE prospective collector successfully received and hashed the exact payload/version.

This is a defensible **upper bound** on public availability when the collector polls a public endpoint. It is not automatically an official `published_at` timestamp.

### `official_published_at`
May be populated only when the source or an independently preserved contemporaneous authority explicitly proves publication/release time for the exact payload/version.

### Missing timestamps
Unknown timestamps are `null` with an explicit provenance status. They must never be guessed from:

- snapshot/reference date;
- file modification time;
- later retrieval time;
- a fixed +N delay;
- market close time;
- current-sector membership;
- a later research artifact.

## 6. Append-only doctrine

Every live run creates an immutable observation artifact with a unique identity derived from run metadata/time.

A later run may add a new artifact that references an earlier event. It may not rewrite the earlier event's first-observed timestamp.

Outcome resolution is append-only:

- an event is created when evidence is first observed;
- a later ownership confirmation may create a separate resolution record referencing that event;
- false alarm, miss, repair outcome, and state transition are assigned only after the required confirmation is actually observed;
- enrichment of provenance never backdates `actual_known_at`.

## 7. Frozen-model / interpreter rule

No Pass 4 coefficient, threshold, calibration rule, feature definition, or decision gate may be changed based on prospective outcomes.

The Pass 4 h=1 research authority is a frozen recognition layer. The repository currently does not expose a separately versioned executable/model artifact that can be safely treated as the exact frozen interpreter. Therefore:

`INTERPRETER_BINDING_STATUS = INTERPRETER_BINDING_PENDING_FROZEN_EXECUTABLE`

Until an exact frozen executable/model artifact is identified and hash-bound:

- collect raw and derived evidence with actual availability timestamps;
- do not recreate an approximate h=1 score from prose;
- do not substitute the post-primary source-only diagnostic for the frozen primary family;
- do not output a formal h=1 probability/classification;
- do not call a missing score a negative signal.

Binding a previously frozen executable is permitted only if its identity and hash are established without looking at prospective outcomes. Creating or altering a model requires a new preregistration.

## 8. Sector provenance

The current100 universe records an `industry_code` and universe generation timestamp, but does not establish a per-security historical/effective-from timestamp for that classification.

Prospective observations therefore record:

- observed classification;
- universe version/source;
- first time this collector observed that classification;
- `effective_from = null` unless an effective-date authority is independently captured.

No current-sector backfill is allowed.

## 9. Regime provenance

A formal regime state may be attached only when:

- the frozen regime definition/version is identified;
- every required input has an actual availability timestamp;
- the regime output is computed from only then-known inputs.

Otherwise regime fields remain null / provenance-incomplete. No new regime rule may be invented to make the prospective layer executable.

## 10. TDCC prospective first-observed rule

The collector may poll the official TDCC public endpoint and preserve:

- request-started time;
- response-received time;
- HTTP metadata that is actually returned;
- exact raw payload SHA256;
- snapshot/reference date parsed from the payload when possible;
- HENGCE `first_observed_at` for a previously unseen payload hash/reference-date pair.

The first observation is immutable. A later official publication timestamp may be attached only as separately sourced provenance.

## 11. CONTROL/HOOK and h=1 `actual_known_at`

For any state or early-evidence bundle:

`actual_known_at = max(actual availability timestamps of all required inputs)`

but only when every required input has valid provenance. If any required input lacks a valid actual-availability timestamp, `actual_known_at = null` and the state/evidence cannot be used for formal prospective latency measurement.

## 12. Outcome discipline

The collector records only:

- evidence;
- state transition;
- false alarm;
- miss;
- repair outcome;
- actual confirmation time;
- measured lead/lag once both endpoints are valid.

It does not produce BUY/SELL instructions or exact-price forecasts.

No rule, threshold, label, feature, or residual definition may be changed after seeing a live outcome. Any such change starts a new preregistration and a new prospective cohort.

## 13. Historical study remains closed

If historical TDCC publication provenance is later recovered, the historical latency study must be reopened under a **separate new preregistration** before any historical latency rerun. Until then:

`HISTORICAL_LATENCY = DATA_BLOCKED`

Live evidence cannot be used to retroactively upgrade historical latency.

## 14. Scheduling limitation

This protocol and collector are being developed on the research branch. GitHub scheduled workflows normally execute from the repository default branch. Therefore a schedule entry present only on this research branch must not be represented as proof that unattended prospective collection is running.

A manually dispatched run on this branch can create valid prospective observations. Continuous unattended collection requires an authorized deployment of the frozen collector to a branch/context from which the scheduler actually executes, without changing the research semantics.

## 15. Success condition

The prospective research remains `COLLECTING` until enough resolved events have accumulated to support a separately frozen evaluation plan. No minimum sample, threshold, success gate, or promotion rule is inferred here from live outcomes.

Until that later evaluation is preregistered and executed:

- `PROSPECTIVE_LIVE_LATENCY = COLLECTING`
- production authority = `NONE`
- trading authority = `NONE`
