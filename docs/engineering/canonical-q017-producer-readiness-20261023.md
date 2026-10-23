# Canonical Q017 producer readiness — 2026-10-23

This note supersedes only the **Canonical Q017 producer search and readiness** subsection in `unified-hengce-runtime-hardening.md`. All other runtime-hardening conclusions remain in force.

## Status

**IMPLEMENTED / REVIEW-BOUND / OFFICIAL-CALENDAR-BOUND / FAIL-CLOSED / NOT AUTO-PROMOTED**

- Producer: `scripts/hengce_q017_canonical_producer.py`
- Reviewed producer commit: `ba003ca8989efa524c5505e28e206a3cc2d27327`
- Admission: `scripts/hengce_unified_q017_admission.py`
- Calendar validator: `scripts/hengce_twse_calendar.py`
- Official retained calendar: `hengce/calendar/TWSE_TRADING_CALENDAR_2026_v1.json`
- Governance/deployment copy: `governance/TWSE_TRADING_CALENDAR_2026_v1.json`
- Output contract: `HENGCE_CANONICAL_Q017_CANDIDATES`, schema version 1
- Default artifact path: `hengce/q017_canonical/latest.json`
- Capital authority: 0
- Broker execution: false
- Production model changes: **NONE IMPLEMENTED**

The producer is not invoked by `衡策掃一次`. Interactive scans consume only a previously produced, current, admitted canonical artifact. This prevents an interactive scan from manufacturing a late signal or repairing missing research evidence.

## Evidence basis

The frozen Q017 handoff defines a 1D residual reversal against the PIT TWSE-electronics median market return. The Phase-1 readonly evidence map identifies the matching inspected implementation/locks: prior beta observations only, maximum 60/minimum 30; `residual1 = stock_r1 - beta60 * electronics_m1`; K=25; Top1; turnover20 >= 20m; residual <= .04; local electronics and SOX gates; DXY excluded; next-open entry; fixed-20-session exit; 0.8% roundtrip; no overlap.

The reviewed implementation evidence is pinned to commit `f5abef555d9174e3919a9dca52e9bfb07351e02e`, including:

- `scripts/hengce_e2_live.py`
- `research/e2_profit_max/E2_PROFIT_MAX_CANDIDATE_B_FINAL_VALIDATION_20261019.json`

E2 remains **research/implementation evidence only**. E2 runtime output is not relabeled as Q017, does not receive Q017 authority, and is not a competing HENGCE engine.

## Producer invariants

The independent Q017 producer:

- reads PIT TWSE-electronics daily close/turnover history and SOX daily history;
- computes per-stock daily close return;
- computes the daily electronics market return as the median of available stock returns;
- computes electronics m5 by compounding five market-median daily returns;
- computes beta from prior observations only, max 60/min 30, excluding signal day;
- requires positive finite beta;
- computes `residual1 = stock_r1 - beta60 * electronics_m1`;
- computes exactly `beta60 * (1 + 25 * max(-residual1, 0))`;
- applies the frozen liquidity/residual/local/SOX gates;
- excludes DXY;
- deterministically ranks by score descending then ticker;
- emits at most Top1 when the full gate is GO;
- emits CASH with no candidate when the global gate is not GO;
- emits source-byte SHA-256 lineage, official-calendar lineage and frozen-evidence references;
- writes atomically and emits zero-authority fields.

No entry/stop/target/risk geometry is generated.

## Official TWSE trading-calendar binding

The retained 2026 calendar comes from the Taiwan Stock Exchange official OpenAPI endpoint:

`https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule`

The manifest is frozen with:

- ROC year 115 / Gregorian year 2026;
- normalized official records SHA-256 `8f9096843c09c877a51df318946e6dc279f36863ec9230b79a8b1a07a1af3cc6`;
- calendar fingerprint `eb8861a737327a867c6cea8d6d58fa41235dd125cdae1760e0b1441751b26f84`;
- base rule Monday-Friday plus the official closure/open-marker exceptions.

The source and governance copies are byte-identical. If both exist and differ, calendar loading fails closed. The deployed hard-bind bundle installs the validated governance copy and records its file hash.

The producer requires both `--signal-date` and `--trade-date`; it does not infer a signal date from a stale file. It requires the latest electronics-history date to equal the explicit signal date, rejects history containing the trade date or later, rejects stale SOX evidence, and requires:

`trade_date == official_next_TWSE_trading_day(signal_date)`

Examples covered by regression tests:

- 2026-10-23 (Friday) -> 2026-10-27 (Tuesday): valid, because 2026-10-26 is an official TWSE closure;
- 2026-10-23 -> 2026-10-26: rejected;
- 2026-02-11 -> 2026-02-23: valid across the official Lunar New Year closure interval.

Dates outside the retained 2026 calendar coverage fail closed rather than being guessed.

## Admission invariants

The unified runtime admits reviewed producer evidence through `hengce_unified_q017_admission.py`.

The admission layer independently checks:

- reviewed producer name and commit;
- frozen evidence commit;
- local retained TWSE calendar schema, official-source records hash and fingerprint;
- artifact calendar fingerprint and raw manifest SHA against the local retained manifest;
- producer input hash for the calendar manifest;
- official next-TWSE-open signal/trade binding;
- GO has exactly one candidate and CASH has none;
- candidate signal/entry dates match artifact dates;
- beta observations are 30..60;
- beta is positive;
- Q017 candidate does not carry geometry/position/entry authority.

The existing unified adapter then independently rechecks the frozen typed contract, producer allowlist, SHA-256 input lineage, Top1, score identity, filter evidence and ticker identity.

Invalid Q017 remains an optional-source failure: it is isolated and cannot acquire authority; valid legacy HENGCE may continue. Missing/invalid mandatory formal/context/live inputs still stop the authoritative bundle.

## Geometry and authority

Q017 remains only an internal candidate source.

- Q017-only -> `GeometryStatus=UNAVAILABLE`, `FormalEntryTrigger=false`, final action ABSTAIN.
- BOTH -> may reuse only already-legal legacy HENGCE geometry.
- No arbitrary score fusion.
- No second user-facing ranking engine.
- No capital authority or broker execution.

## Verification

Calendar tests cover official closures/open markers, 2026-10-23 -> 2026-10-27, 2026-02-11 -> 2026-02-23, closure rejection and tamper rejection.

Golden producer tests cover score/residual identity, signal-day beta exclusion, Top1, local/SOX gates, DXY exclusion, CASH behavior, noncausal/stale data rejection, calendar lineage and non-trading entry rejection.

Admission tests cover reviewed producer acceptance plus rejection of wrong producer commit, stale/same-day signal binding, calendar-lineage tampering, official closure misuse, beta observation count below 30 and attempted geometry injection.

The hard-bind bundle verifies the calendar is installed and usable in an isolated deployed fixture. Engineering Replay continues to exact-equality gate historical model/safety payloads except the already-authorized single-HENGCE router migration; new regression tests run after the historical snapshot comparison without introducing a replay exemption.

## Remaining limitation

A **current** canonical artifact still must not be fabricated. It may be generated only when the required PIT electronics/SOX data are available and bind to an explicit valid 2026 signal/trade session. This implementation does not fabricate missing daily data and does not translate legacy Q017 v5.

Calendar coverage is intentionally pinned to 2026. A future year requires a newly retained official TWSE manifest, independent review, new fingerprint, tests and admission update; the current code fails closed outside coverage.

**MODEL CHANGES: NONE IMPLEMENTED**  
**PR #28: OPEN / DRAFT / NOT MERGED**
