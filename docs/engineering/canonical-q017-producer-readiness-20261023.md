# Canonical Q017 producer readiness — 2026-10-23

This note supersedes only the **Canonical Q017 producer search and readiness** subsection in `unified-hengce-runtime-hardening.md`. All other runtime-hardening conclusions remain in force.

## Status

**IMPLEMENTED / REVIEW-BOUND / FAIL-CLOSED / NOT AUTO-PROMOTED**

- Producer: `scripts/hengce_q017_canonical_producer.py`
- Reviewed producer commit: `a60265f29cc57e79873f4fc9e99fa8996e15558c`
- Admission: `scripts/hengce_unified_q017_admission.py`
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
- emits source-byte SHA-256 lineage and frozen-evidence references;
- writes atomically and emits zero-authority fields.

No entry/stop/target/risk geometry is generated.

## Explicit session binding

The producer requires both `--signal-date` and `--trade-date`; it does not infer a signal date from a stale file.

It requires the latest electronics-history date to equal the explicit signal date and rejects history containing the trade date or later. It also rejects stale SOX evidence.

There is still no authoritative TWSE holiday calendar in this package. Therefore the producer intentionally accepts only ordinary unambiguous next-session mappings:

- adjacent weekday -> next weekday; or
- Friday -> Monday.

Other gaps fail closed with `OFFICIAL_TRADING_CALENDAR_REQUIRED_FOR_SESSION_GAP`. This intentionally sacrifices availability after holidays rather than guessing that an older signal is the immediately prior TWSE session.

## Admission invariants

The unified runtime admits reviewed producer evidence through `hengce_unified_q017_admission.py`.

The admission layer independently checks:

- reviewed producer name;
- reviewed producer commit;
- frozen evidence commit;
- signal date precedes trade date;
- ordinary next-session binding while no official calendar is available;
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

Golden producer tests cover score/residual identity, signal-day beta exclusion, Top1, local/SOX gates, DXY exclusion, CASH behavior, same-day/noncausal data rejection, stale explicit signal rejection and ambiguous session-gap rejection.

Admission tests cover reviewed producer acceptance plus rejection of wrong producer commit, stale/same-day signal binding, ambiguous session gap, beta observation count below 30 and attempted geometry injection.

The unified Q017 integration workflow runs these tests together with the existing adapter/action/display/runtime suites. Engineering Replay continues to exact-equality gate historical model/safety payloads except the already-authorized single-HENGCE router migration.

## Remaining limitation

A current canonical artifact must not be generated until the required PIT electronics/SOX data and explicit signal/trade session binding are available. This implementation does not fabricate missing daily data, does not translate legacy Q017 v5, and does not use a guessed holiday calendar.

The next infrastructure improvement is an independently authoritative TWSE trading-calendar/session manifest. Until then, ambiguous holiday gaps remain deliberately unavailable.

**MODEL CHANGES: NONE IMPLEMENTED**  
**PR #28: OPEN / DRAFT / NOT MERGED**
