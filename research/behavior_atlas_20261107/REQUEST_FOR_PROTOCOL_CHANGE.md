# HENGCE Behavior Atlas — Protocol Interpretation / Materiality Amendment Request (2026-11-07)

## Request from research owner
The user explicitly instructed the research to **prioritize the historical TDCC large-holder distribution** and not use tiny isolated data irregularities as an excuse to stall the entire nine-year behavioral-pattern research.

## Existing rule and possible misinterpretation
PROTOCOL_LOCK_V1 §G1 currently requires full data-quality/PIT governance. Earlier G1 notes gave disproportionate emphasis to TDCC 418 invalid stock-week tiers out of 1,013,961 (0.0412%) and numeric-missing Close 6,641 out of 2,111,682 (0.3145%). Treating isolated missingness by itself as a global fail-stop materially wastes research capacity.

## Proposed narrow interpretation (no change to research question or experiment budgets)
1. **Preserve full TDCC original corpus**: 457 weekly snapshots and 1,013,961 stock-week observations; 1,013,543 with valid Big400/Big1000 structure. Never delete whole weeks or stock universes solely due to a small number of invalid fields. Retain null, reasons, source hashes, and affected-event IDs.
2. **Minor local exceptions**: A missing or invalid row is not an automatic G1 BLOCKED/FAIL_STOP reason. Allow all unaffected valid observations to proceed to descriptive research *once the mandatory literature and sample eligibility gates are met*. Do not create arbitrary auto-pass thresholds; record invalidity by year, trading regime, sector and cohort, and whether it could bias a candidate pattern.
3. **Systematic methodological risks remain material even when their raw count is low**: look-ahead from TDCC publication timestamps, wrong TWSE vs TPEx/DR identity or historical listing status, corporate actions that mechanically move holding-share tiers, and survivorship bias must be explicitly handled. These are not equivalent to a few missing cells.
4. **Source market mismatch is not invalid data**: 564,390 TDCC stock-weeks whose code is absent from same-year TWSE mother are *out-of-scope or unclassified for the TWSE-only target*, not 564,390 data errors. Preserve for potential separate TPEx research, but never blend into the TWSE ordinary-stock population without point-in-time market-type confirmation.
5. **Avoid false gate approvals**: G1 can acknowledge structural integrity PASS and limited descriptive utility, while strict historically observable predictive/trading usage remains blocked until official time/identity controls. A user-facing distinction must be made between local data cleaning and research-validity constraints.
6. **If later evidence shows the small fraction is systematically located in unique crashes or the events defining a discovered mode**, only those affected analyses are quarantined/retested; not every unrelated valid observation.
7. **No additional experiments, no G3 advancement, no hindsight threshold tuning, no N2 changes.** The 6 experiment maximum, 2 QA rounds and original gate sequencing remain unchanged.

## Knowledge of outcomes
The historical 2018–2026 prices and older HENGCE return reports have previously been examined. No new Behavior Atlas G3 finding has been generated and this materiality interpretation is made **before** any new behavioral discovery/validation output. It is a data quality prioritization correction, not a change to make an unprofitable model appear profitable.

## Decision
Owner directive favors proportional QA. Interpretation accepted in the research branch only. Treat G1 structural evidence as PASS where explicitly verified; retain G1 overall BLOCKED solely for unverified historical TWSE common-stock identity / TDCC release-time for prediction. Do not mark G0 or G1 overall PASS without supporting evidence.
