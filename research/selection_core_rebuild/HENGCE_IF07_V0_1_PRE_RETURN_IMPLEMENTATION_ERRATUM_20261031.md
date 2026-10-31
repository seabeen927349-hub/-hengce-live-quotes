# HENGCE IF-07 V0.1 — Pre-Return Implementation Erratum

Date: 2026-10-31  
Branch: `research/selection-core-rebuild-20261031`  
Applies to: `IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1`  
Forward returns inspected before this erratum: `NO`  
Research thresholds changed: `NO`  
Trading / production authority: `NONE`

## Why this erratum exists

The frozen preregistration defines Discovery and Validation by **signal_date**, not by fiscal-report year.

A prior implementation draft incorrectly used current fiscal years 2023 and 2024 as a shortcut for Discovery. That is not equivalent:
- 2022Q4 is normally filed in early 2023 and therefore can generate a Discovery signal;
- 2024Q4 cannot exist before 2024-12-31 and is normally filed in 2025, therefore it is normally Validation, not Discovery.

This bug was identified before any IF-07 forward-return inspection.

## Frozen correction

### Stage A — accounting-only upper-bound candidate build

No upload timestamps, signal dates, prices, forward returns or null outcomes are used.

Potential current periods that can legally map into Discovery `signal_date ∈ [2023-01-01, 2024-12-31]`:
- 2022Q4
- 2023Q1
- 2023Q2
- 2023Q3
- 2023Q4
- 2024Q1
- 2024Q2
- 2024Q3

Required prior-year same-quarter comparators:
- 2021Q4
- 2022Q1
- 2022Q2
- 2022Q3
- 2022Q4
- 2023Q1
- 2023Q2
- 2023Q3

2024Q4 is **not** a Stage-A Discovery current period.

### Stage A correction handling

The official quarterly MOPS correction list may be used only as an early **exclusion accelerator**:
- if either the current company-quarter or prior-year comparator appears in the official correction list, exclude the pair before accounting selection;
- absence from that quarterly list does not by itself satisfy the frozen final `correction_field == exact 無` contract.

### Stage B — exact metadata gate only after accounting selection

Only Stage-A `6/6 PASS` accounting candidates proceed to the rate-limited official electronic-book `t57sb01` metadata query.

For each candidate, the original frozen rules remain mandatory:
- current filing must have exactly one usable consolidated row;
- prior-year comparator must have exactly one usable consolidated row;
- current and prior `財務報告更(補)正` must each equal exact `無`;
- current official `上傳日期` must be parseable and remains the sole `upload_ts` authority for V0.1;
- unresolved/blank/ambiguous metadata fails closed.

No ZIP timestamp, HTTP response date/header, board-resolution announcement time, statutory deadline or inferred date may substitute for the official `上傳日期` in V0.1.

### Stage C — signal date, PIT universe, split

Only after Stage B passes:
1. map current `upload_ts` to the preregistered signal date using the frozen TWSE session/cutoff rule;
2. require ticker row presence on that signal date in the canonical daily `TWSE_ELECTRONICS_YYYY.zip` archive;
3. classify Discovery vs Validation strictly by the resulting `signal_date`.

## Sample-sufficiency upper-bound rule

Because Stage B and Stage C can only remove Stage-A candidates, never add them:
- if the Stage-A no-return `6/6 PASS` upper bound is already below any preregistered Discovery minimum, IF-07 V0.1 may be declared `INCONCLUSIVE_SAMPLE_INSUFFICIENT` without opening any return data;
- otherwise continue to Stage B metadata collection.

## Governance consequence

This erratum changes only implementation ordering and corrects fiscal-period coverage to match the already-frozen signal-date split. It does not alter:
- six accounting conditions;
- thresholds;
- nulls;
- entry/cost geometry;
- Discovery/Validation date boundaries;
- promotion criteria.
