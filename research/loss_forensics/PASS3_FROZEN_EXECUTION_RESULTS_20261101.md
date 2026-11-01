# HENGCE Dynamic State Probability Engine — Frozen Pass 3 Execution Results

Date: 2026-11-01
Status: EXECUTED / RESEARCH ONLY / NO TRADING AUTHORITY
Initial handoff head: `f5da0236717ddcc69cd9e15d50a2afd92e74ba26`
Primary preregistration: `STATE_INTERACTION_PREREGISTRATION_PASS3_20261101.md`
Scope exclusions: 6415 and 3042 are excluded from the execution sample and are not research anchors.

## 1. Compute / data status
The prior system-level runtime failure did not recur. Frozen Pass 3 was numerically executed.

Primary ownership pilot:
- `current100_ownership_intervals_audit.csv`
- 4,100 rows = 100 tickers x 41 ownership snapshots
- snapshot range 2026-01-09 through 2026-10-22

Canonical daily mother used for interval reconstruction:
- full `HENGCE_2026_HIST_MOTHER.csv` available through 2026-10-30
- this full mother reproduces the frozen 2026-10-22 `AbsorptionFrac`, `HoldersChg`, `MarginChg`, and `PriceRet` values in `CURRENT_CONTROL_BUILDS_20261022.csv`.

## 2. Existing artifact/spec mismatch discovered before outcome fitting
`MODEL_SPEC.json` describes expanding PIT percentiles, but `CURRENT_CONTROL_BUILDS_20261022.csv` is exactly reproduced by a trailing-25-snapshot PIT rank for `d_Big400_hist_pct` and `AbsorptionFrac_hist_pct` on checked rows.

This is recorded as an existing artifact/spec mismatch, not silently tuned after outcomes. The Pass-3 replication used trailing-25 PIT ranks to match the frozen executable behavior.

## 3. Frozen candidate / label population
Pre-outcome strong-inflow candidate screen: 778 intervals across 38 snapshot dates.
After fail-closing seven candidates whose t+1/t+2 ownership outcome path had denominator/integrity problems:
- usable labeled candidates: 771
- durable two-snapshot repair/control: 556
- reversal / failed durability: 215

Strict expanding OOS evaluation period:
- 2026-06-26 through 2026-10-08
- 252 held-out predictions across 16 snapshot dates
- durable: 181
- failed/reversal: 71
- no evaluation-period abstention after the frozen chronological fit/calibration requirements were satisfied.

## 4. Formal frozen comparisons
All models used the same locked `HistGradientBoostingClassifier` and chronological Platt calibration. AUC is secondary; Brier/log-loss/calibration/time-block robustness govern promotion.

### BASE = CONTROL + HOOK
- n = 252
- Brier = 0.2014837104
- log loss = 0.5891642998
- ECE10 = 0.0415563487
- AUC = 0.6041553187

### BASE + CORE_LOOSENING
- Brier = 0.2025116317
- log loss = 0.5916626818
- ECE10 = 0.0413767216
- AUC = 0.6018208700

Result: **FAIL / formal incremental weight = 0**.
Aggregate Brier and log loss both worsen. The early half improved, but the later half deteriorated materially; removing its single most favorable date also leaves it worse than BASE.

This preserves the prior governance conclusion that `dU<0 + dL>0` / Core loosening is diagnostic structure, not a standalone probability upgrade.

### BASE + BRIDGE / DESTINATION_PRELOAD — aggregate numeric screen
- Brier = 0.1981485191
- log loss = 0.5807848031
- ECE10 = 0.0455359453
- AUC = 0.6315461832

The aggregate numeric gate by itself passes: both chronological halves improve and leave-best-date-out Brier remains better.

However the required information-attribution audit invalidates formal promotion:
- only 13 / 252 OOS rows (5.16%) have an actual frozen related-destination edge/evidence path;
- on those 13 rows, BASE Brier = 0.1984057378;
- BASE+BRIDGE Brier = 0.2151219977, i.e. **worse by 0.0167162599**;
- on the 239 rows without actual destination evidence, Brier changes 0.2016511315 -> 0.1972252755.

Therefore the aggregate improvement cannot honestly be attributed to destination preload information. It is a model-structure / missingness / edge-membership perturbation outside the rows where destination evidence is actually observed.

Result: **NOT PROVEN / formal incremental weight = 0**. Bridge / destination preload remains a bounded diagnostic hypothesis requiring a broader pre-registered related-name universe or more forward evidence. The aggregate apparent success is explicitly not promoted.

### BASE + PROFESSIONAL_FLOW
- Brier = 0.1969728111
- log loss = 0.5799259192
- ECE10 = 0.0559166926
- AUC = 0.6426737219

Aggregate Brier/log loss improve, and leave-best-date-out remains better. But the frozen chronological robustness criterion fails:
- early block Brier: 0.1953634323 -> 0.1865814741; log loss 0.5750812476 -> 0.5562375318
- late block Brier: 0.2100520997 -> 0.2115206829; log loss 0.6088805728 -> 0.6130896616

Result: **FAIL / formal incremental weight = 0**. Professional flow is useful corroborating evidence, but its incremental probability benefit is not temporally stable enough for formal Pass-3 promotion.

## 5. Frozen Pass 3 conclusion
**No new feature family receives formal nonzero probability weight from this Pass 3.**

- CORE_LOOSENING: zero weight — probability quality worsened.
- BRIDGE / DESTINATION_PRELOAD: zero weight — aggregate numeric improvement failed information-attribution / effective-coverage audit.
- PROFESSIONAL_FLOW: zero weight — aggregate improvement did not persist in the late OOS block.

This is a null formal promotion result, not a failed research process. It narrows the valid frontier:
- destination preload remains structurally interesting but under-covered in current100;
- professional flow contains signal but is not stable enough at ownership-snapshot frequency;
- the legitimate next question remains whether daily post-t information can reduce recognition latency before t+1 TDCC, which is corrected Pass 4.

## 6. Reproducibility hashes
- Pass-3 labeled candidate matrix: `84f531a939ddac82aa4ca4ee5533c55436e9c6c733f7b6421241607bcb36c200`
- BASE predictions: `7e73541179eb54024643d47a0600f66e6b4681fa0fe29cdf1a3cc20291621d42`
- BASE+CORE predictions: `16cd58cd5d64a3b724b8f57b8c14305547371bb8e1d2b6eeaabcea91eae9edae`
- formal BASE+BRIDGE predictions: `57b098824519faebdf9c031f197e22c2b3050d6e67cd2532c968e2a65d8ef13e`
- formal BASE+PROFESSIONAL_FLOW predictions: `972bc960b8a599aa277cb5d86e3854b4997dd27eefc1394f65b2931ed75dfcf6`

No production or capital authority is created by this result.
