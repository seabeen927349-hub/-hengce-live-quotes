# HENGCE Market Environment Observation — S2 V1.2 Leverage Implementation Amendment

Date: 2026-11-02 (Asia/Taipei)  
Project: `research/market_state_observation_20261102`  
Base schema: `HENGCE_MARKET_ENVIRONMENT_OBSERVATION_S2_V1_1`  
Amended implementation metadata: `HENGCE_MARKET_ENVIRONMENT_OBSERVATION_S2_V1_2`  
Authority type: **PIT / REVISION-SAFE IMPLEMENTATION COMPLETION ONLY**

## 1. Why this amendment is allowed

The frozen S2 schema already defines the `LEVERAGE_SHORT` family and its six metrics. It explicitly requires finalized D credit balances to be unavailable before D+2 open when original provisional snapshots are not preserved.

This amendment does not add a family, metric, horizon, predictive threshold or label. It only binds the frozen formulas to the existing validated HENGCE data vessel and adds audit-only coverage metadata.

No forward return, future drawdown/volatility, target, P&L, model performance, state label or Selection Core outcome was inspected.

## 2. Source route — existing HENGCE vessel only

Validated route:

`TWSE official MI_MARGN -> eod/YYYYMMDD margin leg -> /HENGCE_CANONICAL/TWSE_2026_margin.csv -> research leverage sidecar`

The strict vessel lock remains controlling:

`ONLY_VALIDATED_ORIGINAL_VESSEL_MAY_BE_USED`

No alternate mother and no fallback data path are authorized.

The canonical historical mother remains:

`/HENGCE_CANONICAL/HENGCE_2026_HIST_MOTHER.csv`

The mother is not rewritten by this research amendment.

## 3. Revision-safe value

For event date D and ticker i:

- same-day `MarginBalance(D)` / `ShortBalance(D)` is not treated as final;
- finalized `MB_i(D)` = the next trading session D+1 report's `MarginPreviousBalance`;
- finalized `MS_i(D)` = the next trading session D+1 report's `ShortPreviousBalance`;
- those finalized D values become eligible for an observation vector no earlier than **D+2 08:30 Asia/Taipei**, matching the frozen matrix open-context anchor.

This explicitly prevents retrospectively corrected D values from appearing at D+1 open.

## 4. Frozen formulas unchanged

The existing six frozen metrics remain exactly:

- `MARGIN_BAL_LOGCHG5`
- `MARGIN_BAL_LOGCHG20`
- `MARGIN_BAL_BREADTH_1`
- `MSHORT_BAL_LOGCHG5`
- `MSHORT_BAL_LOGCHG20`
- `MSHORT_BAL_BREADTH_1`

The date-correct electronics universe and frozen 95% cross-sectional gate apply.

Audit-only columns added:

- `margin_balance_coverage_ratio`
- `mshort_balance_coverage_ratio`
- `margin_breadth_coverage_ratio`
- `mshort_breadth_coverage_ratio`

They are data-quality metadata, not predictive thresholds.

## 5. Known bridge defect — fail closed

The current canonical margin file has one specific bridge defect:

- report date: `2026-10-14`
- canonical rows retain balances but lost `MarginPreviousBalance` / `ShortPreviousBalance` and transaction fields;
- therefore event date `2026-10-13` cannot be finalized from that canonical bridge alone.

The original GitHub HENGCE vessel still retains complete `eod/20261014/margin_*.csv` rows, including PreviousBalance fields. This proves the source vessel is not missing; the loss occurred in the canonical bridge.

Until that bridge defect is formally repaired from original vessel evidence, event `2026-10-13` remains fail-closed in the sidecar. No synthetic interpolation is allowed.

## 6. Historical boundary

The current canonical margin leg contains 2026 history. The historical mother has no populated margin values for 2018–2025.

Therefore this amendment authorizes a **2026 revision-safe research sidecar only**. It does not claim continuous 2018–2026 leverage history.

Existing HENGCE workflow `.github/workflows/hengce-legacy-margin-2024-backfill-sidecar.yml` establishes that historical MI_MARGN can be reacquired through the existing HENGCE research transport. Historical promotion requires its own source/receipt audit before use.

## 7. Locks unchanged

Still forbidden:

- forward-return discovery;
- state-return mapping;
- backtesting;
- threshold tuning;
- clustering for prediction;
- Selection Core interaction testing;
- merging securities lending with margin short;
- using same-day corrected balances before the revision-safe clock;
- inventing values for missing vessel evidence.
