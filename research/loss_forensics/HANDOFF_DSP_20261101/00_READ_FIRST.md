# HENGCE Dynamic State Probability Engine — New Chat Handoff
Date: 2026-11-01
Status: ACTIVE RESEARCH / NO TRADING AUTHORITY

## Bootstrap authority
Repo: `seabeen927349-hub/-hengce-live-quotes`
Branch: `research/loss-forensics-20261101`

At next-chat start, check current branch head. If the branch advanced, use the newest head, but do not silently override the governance below.

## CURRENT AUTHORITY — MUST READ FIRST
Before any new analysis, read these current-state files:

1. `research/loss_forensics/CURRENT_STATE_DSP_FUGLE_LIVE_TRANSPORT_VERIFIED_20261101.json`
2. `research/loss_forensics/CURRENT_STATE_DSP_ACTUAL_AVAILABILITY_BLOCKED_20261101.json`
3. `research/loss_forensics/HANDOFF_DSP_20261101/03_RESEARCH_DRIFT_LOCK.md`

These three files jointly define the current state.

## Critical current distinction
Two research states must remain separate:

- `HISTORICAL_ACTUAL_PUBLICATION_LATENCY = DATA_BLOCKED`
  Historical h=1 actual-market-known latency is NOT validated because exact TDCC publication provenance and other PIT provenance remain incomplete. Do not reinterpret the old median-3-sessions result as true market-known lead time.

- `PROSPECTIVE_CURRENT100_LIVE_TRANSPORT = VERIFIED / COLLECTING`
  Fugle free/basic Developer API has been verified for the bounded current100 universe using per-symbol `/stock/intraday/quote/{symbol}` requests.
  Proof: 100 requested / 100 success / 0 failure; transport healthy.
  The verification run occurred on Sunday 2026-11-01 and correctly returned 2026-10-30 quote dates as stale rather than pretending Sunday was a market day.

## Fugle current decision
Do NOT expand the active realtime universe to all Taiwan stocks now.
Do NOT purchase the paid Developer plan solely to regain full-market snapshot access now.

Current priority is:

`VERIFIED_CURRENT100_FUGLE_TRANSPORT -> SHADOW_EARLY_WARNING -> PROSPECTIVE FALSE-NEGATIVE / FALSE-POSITIVE / REPAIR / CONTROL-DIORATION TRACKING`

Expansion beyond current100 is only reconsidered if prospective errors show that missing cross-sector or destination-capital context is a material and repeated source of false negatives or false positives.

The live Fugle layer is strictly:
`SHADOW_INTRADAY_ESCAPE_RESEARCH_ONLY_NO_FORMAL_EOD_RANKING_OR_TRADING_AUTHORITY`

It must not be converted directly into BUY/SELL, exact-price prediction, production authority, or a new model family.

## MANDATORY DRIFT LOCK
Before ANY analysis, modeling, factor discovery, forward-outcome inspection, threshold change, or case reinterpretation, read:

`research/loss_forensics/HANDOFF_DSP_20261101/03_RESEARCH_DRIFT_LOCK.md`

This is hard governance. If a proposed step conflicts with the drift lock, stop.

## Objective
Continue Loss Forensics as a **Dynamic State Probability Engine / capital-preservation early-warning research program**.
Do not return to exact-price prediction, fixed Bull/Bear scoring, V43 rescue, Monster rescue, Selection Core rescue, or single-ticker storytelling.

The practical objective is not model worship. The user goal is:

> reduce the chance of becoming the last liquidity provider/holder when stronger capital is already withdrawing or transferring risk.

Capital preservation matters more than exact-price prediction.

Primary future outputs, only when calibrated:
- P(CONTINUATION)
- P(REPAIR)
- P(CONTROL_LOSS)
- P(SYSTEMIC_SHOCK)
- ABSTAIN / NO_EDGE

## User research doctrine
- All legitimately obtainable data may be used.
- The user does not require a model if evidence does not support one.
- Failure is acceptable; fabricated success, silent retuning, threshold rescue and hindsight masquerading as live knowledge are not.
- Traditional Chinese for user-facing discussion.

## Current exclusions
For current mechanism research and interpretive examples, exclude **6415** and **3042** as primary anchors/examples. Do not let them define architecture.

## Must-read supporting files
1. `research/loss_forensics/DYNAMIC_STATE_PROBABILITY_ENGINE_CHARTER_V1_20261101.md`
2. `research/loss_forensics/STATE_INTERACTION_PREREGISTRATION_PASS3_20261101.md`
3. `research/loss_forensics/PASS4_INCREMENTAL_TARGET_CORRECTION_20261101.md`
4. `research/loss_forensics/PASS3_PARTIAL_FINDINGS_REPAIR_VELOCITY_PRICING_POWER_20261101.md`
5. `research/loss_forensics/PASS4_QUADRANT_STRESS_TEST_FLOW_PRICE_OWNERSHIP_20261101.md`

Also retrieve existing validated artifacts when needed:
- `HENGCE_HIDDEN_CONTROLLER_CONTROL_HOOK_V1_REPORT.md`
- `current100_ownership_intervals_audit.csv`
- `HENGCE_BRIDGE_RELOAD_MARGINAL_CONTROL_CAPITAL_ATLAS_V0_20261029.md`
- `HENGCE_OPERATOR_IDENTITY_CONFLICT_ATLAS_V1_20261029.md`
- `HENGCE_OPERATOR_BUY_SELL_BEHAVIOR_MAP_V0_20261029.md`

## Existing validated base
### CONTROL durability
Strict expanding time-order OOS (2026-06-26 through 2026-10-16):
- AUC 0.694
- confidence >=0.70 -> 84.56% next-snapshot retention
- confidence >=0.80 -> 88.79%
- confidence >=0.90 -> 93.51%
This predicts ownership durability, not stock return.

### HOOK / release deterioration
`CONTROL FULL + HOOK READY + dBig400 < 0`
- OOS 52 events
- 10d mean -5.91%, median -5.42%, positive 22.5%
- 40d median -7.52%

### Pass 3 final
No new Pass 3 family promoted. CORE_LOOSENING, BRIDGE/DESTINATION_PRELOAD and PROFESSIONAL_FLOW all retain formal weight 0. No rescue is authorized.

### Corrected Pass 4 h=1
Snapshot-reference-date layer showed genuine OOS incremental evidence, but true actual-publication latency remains DATA_BLOCKED. Do not overclaim actual lead time.

## Prospective live evidence collection
From now on, preserve true known-at timestamps wherever possible:
- observation generated time
- Fugle source lastUpdated
- last trade time
- TDCC snapshot reference date
- TDCC first-observed/publication time
- sector effective time
- regime input availability time
- CONTROL/HOOK known-at time
- h=1 evidence known-at time
- next ownership confirmation known-at time

The prospective question is:

> Can current100 live evidence help identify control deterioration earlier without excessive false alarms, using only information truly available at observation time?

Track false negatives, false positives, repair outcomes and control-deterioration outcomes prospectively.

## Fugle transport proof
Main branch output files:
- `escape_live/electronics100_status.json`
- `escape_live/electronics100_snapshot.json`

Verified main proof commit:
`90565cbf6871cf67e7f4a6990e9bd9c4a8811e6a`

Verified status:
- requested_count = 100
- success_count = 100
- failure_count = 0
- healthy_transport = true
- quote_dates = 2026-10-30
- stale_count_vs_run_date = 100
- fresh_market_day = false

The stale state was expected because the proof run occurred on Sunday 2026-11-01.

## Full-market realtime status
The paid whole-market snapshot endpoint returned `AUTH_OR_PLAN_HTTP_403` on the current Basic plan.
This is not a blocker for current100.
Do not treat it as a reason to expand scope or buy a paid plan without evidence that current100 coverage is insufficient.

## Non-negotiable governance
- Facts, inference, and causality must remain separated.
- Retrieval failure != data absence.
- Corporate-action effects must be adjusted/censored.
- TDCC reference date != knowledge date.
- Foreign/trust/dealer are observable vehicles, not beneficial-owner identity.
- No silent retuning or post-hoc threshold hunting.
- A probability requires held-out calibration; raw weighted scores are not probabilities.
- ABSTAIN / NO_EDGE is valid and preferred to fake precision.
- Live Fugle data are SHADOW evidence only until prospective validation supports promotion.
- Do not expand universe merely because more data are technically accessible.

## Next action
Do not re-open broad factor discovery and do not expand to full Taiwan realtime coverage.
Use the verified current100 Fugle transport to build/maintain the prospective shadow evidence ledger and preserve true availability timestamps.
Historical actual-publication latency remains DATA_BLOCKED until missing provenance is genuinely filled.
