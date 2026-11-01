# HENGCE LOSS FORENSICS — Ownership / Price Repair Lead-Lag V1 Preregistration
Date: 2026-11-01
Status: FROZEN PREREGISTRATION / EXPLORATORY FAMILY / FORMAL_WEIGHT=0 / NO TRADING AUTHORITY

## 0. Governance boundary
This is a NEW, isolated research family created only after frozen Pass 3 and corrected Pass 4 reached final authority.

It MUST NOT:
- modify, rescue, reinterpret, or retune Pass 3;
- modify corrected Pass 4 or its h=1 recognition-latency result;
- revive CORE_LOOSENING, BRIDGE/DESTINATION_PRELOAD, or PROFESSIONAL_FLOW as standalone promoted families;
- duplicate CONTROL by merely asking whether the next TDCC snapshot retains ownership;
- create production, ranking, BUY/SELL, or capital authority.

Existing authority remains unchanged. This family begins with FORMAL_WEIGHT=0.

## 1. Why this family is distinct
Existing CONTROL asks whether ownership durability persists into the next TDCC snapshot.
Corrected Pass 4 asks whether daily/cross-stock evidence can recognize that durability earlier than the next TDCC snapshot.

This family asks a different question:

> After an ownership fracture, in what order do strong-holder ownership and price repair, how large is the repair-time gap, and does that sequence carry incremental information about the NEXT state after the repair sequence becomes observable?

The object is therefore `REPAIR SEQUENCE / LEAD-LAG`, not duplicate next-snapshot durability and not exact-price prediction.

## 2. Prior semantics recovered from existing authority
The 2026 swing-lifecycle forensic work used a simple ownership branch after peak-associated Big400 outflow:
- initial post-peak valid TDCC snapshot shows Big400 outflow;
- next valid weekly ownership snapshot is observed;
- a positive reversal/rebuilding branch was called REPAIR;
- persistent leakage/non-repair was called FAILED REPAIR.

The historical 12% swing sample is ex-post segmented and therefore is DESCRIPTIVE ONLY. It is not clean prospective evidence.

## 3. Two-stage research design
### Stage H — historical decomposition
Purpose: verify whether the lead-lag state is measurable, non-tautological, sufficiently frequent, and structurally coherent.

Permitted sample:
- the already-defined 2026 swing-lifecycle / ownership-fracture population;
- no resegmentation or threshold changes based on new lead-lag outcomes;
- 6415 and 3042 remain excluded as primary anchors/examples.

Stage H can produce only:
- EXPLORATORY; or
- STRUCTURAL_SUPPORTED_NOT_CALIBRATED; or
- FAILED; or
- DATA_BLOCKED.

Stage H can NEVER create formal probability weight because the 2026 history has already been repeatedly inspected.

### Stage P — prospective validation
Only future events observed after this preregistration may supply formal validation.
All inputs must carry actual-known / first-observed provenance.
No historical publication timestamp may be backfilled or inferred.

## 4. Event origin and frozen baselines
For every eligible event, define:

`t0 = initial valid ownership-fracture observation`

Historical Stage H:
- use the pre-existing fracture/outflow event population; do not regenerate events with outcome-aware thresholds.

Prospective Stage P:
- use the then-frozen FIRST_FRACTURE semantics already authorized by the live state process;
- if exact executable FIRST_FRACTURE provenance is unavailable, event creation is DATA_BLOCKED rather than reconstructed from prose.

Baseline values:
- `OWN_BASE = Big400Pct` at the immediately preceding valid ownership snapshot before t0;
- `PX_BASE = corporate-action-adjusted close` on the corresponding baseline trading date;
- Big1000, holder count, margin/leverage, regime, and flow are context/covariates, not substitutes for Big400 repair.

## 5. Repair clocks — frozen before new outcome execution
### 5.1 Local ownership repair
`OWN_LOCAL_REPAIR` occurs at the first later valid TDCC ownership observation where:
`Big400Pct(current) > Big400Pct(previous_valid_snapshot)`

This preserves the sign-based reversal idea used in the earlier forensic branch.

### 5.2 Full ownership repair
`OWN_FULL_REPAIR` occurs at the first later valid TDCC ownership observation where:
`Big400Pct(current) >= OWN_BASE`

No optimized restoration percentage is permitted in V1.

### 5.3 Full price repair
`PX_FULL_REPAIR` occurs at the first later trading session where:
`AdjustedClose(current) >= PX_BASE`

Corporate-action discontinuities must be adjusted or the event is censored/excluded according to the existing corporate-action protocol. No optimized price-recovery threshold is permitted in V1.

### 5.4 Primary observation window
Primary window ends at the SECOND valid ownership snapshot after t0.
Secondary robustness window ends at the FOURTH valid ownership snapshot after t0.

The primary two-snapshot window is fixed because the older repair branch was defined on the immediate following ownership observation; V1 extends timing without searching arbitrary horizons.

## 6. Sequence states
Because historical TDCC availability can be coarse and exact public-release timestamps are not proven, do not manufacture false day-level precision.

Primary mutually exclusive states by the end of the two-snapshot window:
- `OWNERSHIP_FIRST`: OWN_FULL_REPAIR is observed before PX_FULL_REPAIR.
- `PRICE_FIRST`: PX_FULL_REPAIR is observed before OWN_FULL_REPAIR.
- `COARSE_TIE`: both first become observable within the same ownership interval and exact ordering cannot be proven.
- `OWNERSHIP_ONLY`: ownership fully repairs; price does not by window end.
- `PRICE_ONLY`: price fully repairs; ownership does not by window end.
- `NEITHER`: neither fully repairs by window end.

`UNKNOWN_TIMING` is mandatory when provenance is insufficient to order observations.

## 7. Lead-lag metric
When both repair times are provably ordered:

`REPAIR_LEAD_LAG = session_index(PX_FULL_REPAIR) - session_index(OWN_FULL_REPAIR)`

Interpretation:
- positive -> ownership repairs first;
- negative -> price repairs first;
- zero -> same mapped session only when exact timing supports that statement.

Historical Stage H with unproven publication timing must use the label:
`REFERENCE_DATE_LEAD_LAG`
not `ACTUAL_KNOWN_LATENCY`.

Prospective Stage P may use actual-known latency only from immutable first-observed timestamps.

## 8. Frozen hypotheses
### H1 — ownership-first protection
Conditional on comparable initial fracture severity and regime, `OWNERSHIP_FIRST` / `OWNERSHIP_ONLY` should have lower probability of subsequent broad control loss than `PRICE_FIRST` / `PRICE_ONLY`.

### H2 — price-ahead-of-ownership fragility
`PRICE_FIRST` / `PRICE_ONLY` should be more likely to experience renewed Big400 leakage before durable reconcentration than ownership-first states.

### H3 — incremental state information
After the repair-sequence state becomes observable, adding sequence state / lead-lag to the existing CONTROL+HOOK state should improve held-out probability quality for the NEXT ownership-state transition. It must not merely restate the ownership repair condition already observed.

### Secondary, non-primary price endpoint
Fixed market/sector-adjusted T+5 and T+20 returns measured only AFTER the sequence state becomes observable may be reported as descriptive/secondary endpoints. No exact target-price, top/bottom, or threshold optimization is authorized.

## 9. Covariates / controls fixed in advance
Use only contemporaneously available values:
- initial Big400 fracture magnitude;
- initial Big1000 change;
- holder-count / fragmentation change when available;
- margin/leverage change;
- stock volatility and liquidity;
- market/electronics regime;
- price drawdown at t0 relative to PX_BASE;
- normalized aggregate professional flow only as corroborative context, never as beneficial-owner identity.

Where sample size permits, prefer same-stock or stock-cluster controls and chronological evaluation. Do not create outcome-aware all-to-all pairings.

## 10. Historical execution diagnostics
Before any prospective promotion, Stage H must report:
- event count and censoring rate;
- prevalence of all six sequence states plus UNKNOWN_TIMING;
- distribution of reference-date lead-lag where observable;
- stock/date concentration;
- regime breakdown;
- corporate-action exclusions;
- sensitivity of conclusions to the fixed two-snapshot vs four-snapshot window;
- whether H1/H2 direction is stable across early/late chronological blocks.

If exact source rows or event provenance cannot be recovered, Stage H is DATA_BLOCKED. Hand-picked examples may not substitute for the matrix.

## 11. Prospective OOS gate
Minimum collection rule:
- at least 60 trading days after prospective arming; AND
- at least 100 evaluable fracture/repair-sequence events; AND
- at least 25 events in each of the two major comparison sides (`OWNERSHIP_FIRST or OWNERSHIP_ONLY` versus `PRICE_FIRST or PRICE_ONLY`).

If the time requirement is met but event counts are not, status = `INSUFFICIENT_EVENTS`; extension is permitted only to satisfy the preregistered event-count requirement, never because performance is poor.

Primary comparison after state observability:
- BASE = existing CONTROL + HOOK state available at that time;
- TEST = BASE + frozen repair-sequence/lead-lag family.

Primary metrics:
- Brier score;
- log loss;
- ECE/calibration;
- coverage/abstention.
AUC is secondary.

Promotion requires ALL:
1. held-out Brier improves;
2. held-out log loss improves;
3. ECE does not deteriorate by more than +0.02 versus BASE;
4. direction persists in at least two chronological blocks;
5. improvement remains after removing the single most favorable date/cluster;
6. event-count gate is satisfied.

Otherwise FORMAL_WEIGHT remains 0.

## 12. Mandatory failure / stop conditions
Declare FAILED or keep weight 0 if any of the following occurs:
- sequence ordering is mostly unidentifiable because of coarse/missing timing;
- the apparent effect is only a restatement of Big400 already crossing the baseline;
- sign reverses materially across chronological blocks or regimes;
- gains disappear after conditioning on initial fracture severity;
- held-out Brier/log loss do not both improve;
- result is driven by one stock/date/cluster;
- prospective result contradicts historical narrative;
- a threshold/horizon change would be required to obtain significance.

No rescue by changing 2/4 snapshot windows, restoration percentages, price baselines, exclusions, or event definitions after outcomes are viewed. Any such change requires declaring V1 closed and creating V2 preregistration first.

## 13. Authority state
Current evidence status: `PREREGISTERED_NOT_EXECUTED / EXPLORATORY`
Formal probability weight: `0`
Production authority: `NONE`
Trading authority: `NONE`

Success is not assumed. A clean FAILED or DATA_BLOCKED result is an acceptable final outcome.
