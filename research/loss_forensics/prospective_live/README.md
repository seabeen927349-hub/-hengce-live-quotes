# Prospective Live Actual-Availability Ledger

Authority: research/shadow only. Trading authority: **NONE**. Production authority: **NONE**.

This directory is the append-only evidence area for the cohort `PROSPECTIVE_ACTUAL_AVAILABILITY_V1`.

## Status separation

- `HISTORICAL_LATENCY = DATA_BLOCKED`
- `PROSPECTIVE_LIVE_LATENCY = COLLECTING`

Nothing recorded here retroactively validates historical publication latency.

## Core question

For every prospective event, preserve enough contemporaneous evidence to answer:

> What did HENGCE first know, at what timestamp, from which exact source/payload?

The prohibited replacement question is:

> What does hindsight suggest HENGCE should have known then?

## Files

- `EVENT_LEDGER_SCHEMA_V1.json`: frozen field contract for prospective observations/events.
- `observations/YYYY/MM/DD/*.json`: immutable current100 live observations created after the protocol commit.
- `tdcc/payloads/<sha256>.csv`: exact first-seen TDCC raw payload; one copy per unique payload hash.
- `tdcc/first_observed/<sha256>.json`: immutable first-observed receipt/provenance for that payload.
- `tdcc/attempts/YYYY/MM/DD/*.json`: polling attempt metadata, including failures, so observation gaps are visible.
- `resolutions/YYYY/MM/DD/*.json`: later append-only outcome/confirmation records referring to earlier observation IDs. A resolution does not rewrite the original event.

Directories appear only after the collector actually creates evidence. Empty directories are not committed.

## Availability semantics

`first_observed_at_taipei` is the HENGCE collector's first successful receipt time for an exact payload/hash. It is a conservative public-by observation when polling a public endpoint. It is **not** silently relabeled as the source's official publication time.

`official_published_at` stays `null` unless an independent contemporaneous source proves the exact publication timestamp.

Snapshot/reference dates are stored separately and can never populate an availability field.

## Fugle timing

For each requested current100 symbol the collector preserves:

- request-start timestamp;
- response-received timestamp;
- source `lastUpdated` value returned by Fugle;
- source last-trade time returned by Fugle;
- quote/reference date;
- SHA256 of the exact response object received;
- selected market fields needed to reconstruct what the shadow process actually observed.

A failure is retained as a failure; it is not filled from another symbol, another run, or a later quote.

## Sector timing

The current universe's industry classification may be preserved as `observed_at`, with universe/source provenance. Unless a separate effective-date source is captured, `effective_from` remains null. Current membership must not be backfilled into older observations.

## Regime timing

A regime output is unavailable for formal latency until the exact frozen regime definition and all input availability timestamps are bound. Missing provenance remains null; no replacement regime may be invented.

## CONTROL/HOOK and h=1

`actual_known_at` is valid only when all required inputs are independently available and the exact frozen computation is bound.

At protocol freeze, no separately versioned exact Pass 4 executable/model artifact had been identified on this branch. Therefore formal h=1 probability/classification fields must remain null under:

`INTERPRETER_BINDING_PENDING_FROZEN_EXECUTABLE`

This is deliberate. A prose reconstruction or the source-only diagnostic is not the frozen primary model.

## Outcomes

False alarms, misses, durable repair, deterioration, and measured lead/lag are written only after the relevant ownership confirmation itself is actually observed. Unknown is not zero.

No prospective outcome may be used to alter Pass 4 coefficients, thresholds, labels, feature definitions, or rules inside this cohort.

## Operational note

A workflow definition committed only on this research branch does not by itself prove unattended scheduled collection is running. Eligible evidence begins only with actual collector outputs produced after the protocol freeze. Manual dispatches on this branch can be valid evidence. Continuous scheduled collection requires the same frozen collector to run from a scheduler-active context without changing semantics.
