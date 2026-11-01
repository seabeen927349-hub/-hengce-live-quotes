# HENGCE Dynamic State Probability Engine — Frozen Pass 3 FINAL

Date: 2026-11-01
Status: FINAL FROZEN EXECUTION / RESEARCH ONLY / NO TRADING AUTHORITY
Authority basis:
- `HANDOFF_DSP_20261101/03_RESEARCH_DRIFT_LOCK.md`
- `STATE_INTERACTION_PREREGISTRATION_PASS3_20261101.md`

This file supersedes the earlier trailing-25 diagnostic execution. The final run uses the preregistered **expanding PIT history** exactly.

## Scope / data
- 6415 and 3042 excluded from the execution sample and not used as anchors.
- ownership source: `current100_ownership_intervals_audit.csv` (100 tickers x 41 snapshots).
- daily source: canonical `HENGCE_2026_HIST_MOTHER.csv`.
- no outcome-driven threshold changes.
- same locked HGB model class and chronological Platt calibration for all families.

The executable 2026-10-22 current CONTROL artifact uses trailing-25 ranks on checked rows, while the frozen spec/preregistration says expanding PIT. This mismatch remains documented, but the preregistration has precedence for this final Pass 3.

## Candidate / label population
Expanding-PIT strong-inflow screen before outcome integrity filtering:
- 752 candidates.

After fail-closing invalid t+1/t+2 ownership paths:
- 744 labeled candidates across 38 snapshot dates.
- REPAIR_DURABLE = 539.
- RELOAD_REVERSAL / failed durability = 205.

Strict expanding OOS period:
- 2026-06-26 through 2026-10-08.
- 229 / 229 eligible held-out candidates scored across 16 dates.
- durable = 168; failed = 61.
- OOS coverage = 100%; abstention = 0% within the defined evaluation period.

## Formal results

### BASE = CONTROL + HOOK
Evidence status: `VALIDATED_OOS` as the comparison baseline for this pilot.
- n = 229
- Brier = 0.1843895982
- log loss = 0.5512810104
- ECE10 = 0.0369753018
- AUC = 0.6549570648

### BASE + CORE_LOOSENING
Evidence status: `FAILED`
- Brier = 0.1932919849
- log loss = 0.5706730342
- ECE10 = 0.0351943951
- AUC = 0.6114363778

Both chronological halves worsen:
- 2026-06-26..2026-08-14: Brier 0.1722814912 -> 0.1808676277; log loss 0.5225865511 -> 0.5413089876.
- 2026-08-21..2026-10-08: Brier 0.2041522557 -> 0.2135708208; log loss 0.5981156452 -> 0.6186005584.

Formal incremental weight = **0**.

### BASE + BRIDGE / DESTINATION_PRELOAD
Evidence status: `FAILED`
- Brier = 0.1891195114
- log loss = 0.5626452062
- ECE10 = 0.0408063152
- AUC = 0.6328064012

Both chronological halves worsen:
- early: Brier 0.1722814912 -> 0.1764008263; log loss 0.5225865511 -> 0.5350257761.
- late: Brier 0.2041522557 -> 0.2098787444; log loss 0.5981156452 -> 0.6077251954.

Formal incremental weight = **0**.

This also resolves the ambiguity seen in the superseded trailing-25 diagnostic run: under the actual frozen expanding-PIT candidate definition, the bridge/destination-preload family does not improve aggregate probability quality at all. No narrative rescue is allowed.

### BASE + PROFESSIONAL_FLOW corroboration
Evidence status: `FAILED` for formal promotion; corroborating signal only.
- Brier = 0.1819328579
- log loss = 0.5459660269
- ECE10 = 0.0433343588
- AUC = 0.6706674473

Aggregate Brier/log loss improve, but the frozen time-block robustness criterion fails:
- early block: Brier 0.1722814912 -> 0.1750763716; log loss 0.5225865511 -> 0.5300613795 (worse).
- late block: Brier 0.2041522557 -> 0.1931239046; log loss 0.5981156452 -> 0.5719253365 (better).
- removing the single most favorable date still leaves a small aggregate Brier improvement, but that cannot override the chronological-block failure.

Formal incremental weight = **0**.

## Final Pass 3 decision
**No new Pass-3 family is promoted into calibrated state probability.**

- CORE_LOOSENING = `FAILED`, weight 0.
- BRIDGE / DESTINATION_PRELOAD = `FAILED`, weight 0.
- PROFESSIONAL_FLOW = `FAILED` for promotion because temporal stability fails, weight 0.

This is the required honest null-promotion result. It does not invalidate the structural narratives; it says they did not survive the frozen probability-quality test at ownership-snapshot frequency.

## Reproducibility SHA256
- expanding-PIT candidate/label matrix: `0095ee407bb913feaa5e6445379b5651d3234599f6ff74b972e7d27e3da40315`
- BASE predictions: `b3120542553acdf62547e9d190fcdb7fa14d4b3439b7ad89e20fb8bd0b89e57f`
- BASE+CORE predictions: `142e6caad2c5219544607024c8315d98f218907f48cfb0df5b0600e646694300`
- BASE+BRIDGE predictions: `39d5b4ecf78e85d17869e916dbdf8a707a057a397c18c7ecfde9695ce3f8738c`
- BASE+PROFESSIONAL_FLOW predictions: `86472958025c9bd19dacb0f0100e57d0d7b236e903227a4d6589ca200c11492c`

No production or capital authority is created.
