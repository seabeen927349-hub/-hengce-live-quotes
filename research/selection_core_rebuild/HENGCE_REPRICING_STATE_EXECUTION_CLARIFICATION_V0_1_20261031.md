# HENGCE Repricing State — Execution Clarification V0.1

Date frozen: 2026-10-31
Status: `EXECUTION_CLARIFICATION_FROZEN_FORWARD_RETURNS_STILL_SEALED`
Parent preregistration: `b912b11a65b9e87cb791f05f9a4023bbe114253c`
Parent seal: `2aeb634b9bdf0d10d957c8c4c7d6728811167dbf`
Authority: `RESEARCH_ONLY`
Trading / production authority: `NONE`

## 0. Purpose and boundary

This note resolves implementation ambiguities discovered during the required **no-forward-return implementation/PIT/completeness audit**. It does not change any RS formula, window, selected count, threshold, null, sample split, outcome rule, or promotion gate.

At this freeze:

- no Repricing State candidate forward-return table has been opened;
- no M0/M1/M2/M3 outcome has been computed;
- no Discovery or Validation return has been inspected;
- no result-aware choice is made here.

Any incompatible alternative interpretation requires a separately versioned preregistration before any affected outcome is opened. V0.1 may not be silently reinterpreted after this note.

## 1. SA residual-median cohort — remove circularity

The frozen preregistration states that the one-day residual inside `SA_raw` is the stock close-to-close one-day return minus the median valid one-day return of the same RS eligible electronics cross-section. Common eligibility also requires the raw data paths needed to compute SA. Interpreting final `SA_raw` validity itself as a prerequisite for the residual median would create a circular definition.

Therefore the only admissible implementation for V0.1 is:

### 1.1 Raw-field eligibility for the daily residual median

For each day `d`, define `SA_RESIDUAL_BASE_COHORT(d)` using **only information already observable by the close of d** and only the raw-field requirements already frozen in the preregistration:

1. signal-date PIT membership in `TWSE_LISTED_ELECTRONICS_PIT_DAILY` on `d`;
2. valid current and prior-session close needed for the stock's close-to-close one-day return;
3. valid current `VolumeShares > 0`;
4. valid current official institutional `TotalNetShares`;
5. the margin-balance observations required to establish the common raw-field path through `d` for `g1/g5/g20/LT`;
6. valid TAIEX history required by the common cohort through `d`.

No `SA_raw` value, SA denominator, SA rank, LT rank, M0/M1/M2/M3 score, V43 score, Monster state, future price, or forward return may affect this base cohort.

Then:

`market_median_r1(d) = median of valid close-to-close r1 across SA_RESIDUAL_BASE_COHORT(d)`

and

`r_resid(i,d) = r1(i,d) - market_median_r1(d)`.

### 1.2 Signal-date SA validity remains fail-closed

After the daily residual series is formed, `SA_raw(i,t)` uses exactly the frozen trailing-20 estimator.

If any required trailing-20 raw leg is missing, or if

`sum_d sell_pressure(i,d) = 0`,

then `SA_raw(i,t) = MISSING_PRIMITIVE` and the stock is excluded from the final common RS signal-date cohort on `t`.

The stock is **not** removed retroactively from historical residual medians merely because its later 20-day SA denominator is zero. That would reintroduce circularity.

## 2. Common cohort applies to M0/M1 as frozen

Although M0 and M1 do not numerically use `RG`, the frozen preregistration defines one common cohort for M0–M3 and the paired nulls. Therefore a signal date/name lacking the required TAIEX history is not silently admitted to M0/M1 during novelty or later outcome testing.

This rule prevents model-specific eligibility drift.

## 3. Legacy V43 factor reconstruction is reference-only

For the novelty gate, the five legacy V43 factor ranks must be reconstructed using the **frozen legacy V13 factor semantics**, including its own historical reference eligibility rule `turn20 >= NT$20,000,000` and its original rank construction.

That legacy liquidity threshold is used only to reproduce the frozen legacy reference space. It is **not imported into RS eligibility** and does not filter the RS score before the matched comparison is formed.

Matched rows are the intersection of:

- a valid frozen RS no-return feature row; and
- a valid frozen legacy-factor row.

No legacy threshold may be applied to create or tune the RS cohort itself.

## 4. V43 matched-score comparison

The frozen V43 artifact contains date-specific `weight_log` records only on the historical V43 signal dates. Therefore:

- compare RS-M1 with V43 only on those exact frozen signal dates for which both systems have valid matched rows;
- use the exact five V43 weights stored for that date;
- compute the V43 ranking score as the frozen weighted sum of the five frozen legacy factor ranks;
- do **not** interpolate, forward-fill, backfill, smooth, or manufacture daily V43 weights;
- verify the reconstructed top-3 ordering against the frozen V43 event artifact where available, using ticker identity only; ignore old V43 return fields for novelty.

If fewer than two calendar years have sufficient matched V43 dates/rows, the preregistered reconstruction subtest is `DATA_BLOCKED` rather than rescued with synthetic weights.

## 5. R-017 reference comparison

R-017 remains a killed reference/context engine. Its no-return novelty comparison uses only its frozen contemporaneous representations:

- `ret1` rank;
- `ret20` rank;
- turnover-shock rank, where turnover shock is current turnover relative to own trailing-20 median turnover;
- liquidity rank;
- raw impact representation `abs(ret1) / (turnover / ADV20)` where defined.

R-017's old forward-return results, discovery coefficients, and validation returns are not inputs to RS feature construction.

## 6. Margin simple-reference comparison

For the required LT redundancy diagnostic, compare LT to no-return simple margin references available at t only:

- same-date cross-sectional rank of `MarginBalance`;
- same-date cross-sectional rank of `g1`;
- same-date cross-sectional rank of `g5`;
- same-date cross-sectional rank of `g20`.

These are diagnostics only; they do not enter the RS score.

## 7. Monster structural-overlap diagnostic

MONSTER BUY V1 remains a frozen anatomical specimen and never becomes a target label.

If its frozen historical eligibility/event artifact is available, report only structural overlap on matched dates/names, such as overlap counts/rates between frozen Monster eligibility and the RS-M1 top-5 surface. No Monster forward return or winner identity may be used to fit, tune, transform, or select RS features.

If the frozen eligibility artifact cannot be recovered, report this diagnostic as `DIAGNOSTIC_DATA_BLOCKED`; do not reconstruct Monster thresholds from winners and do not change the three hard novelty gates.

## 8. Forward-return seal

This clarification authorizes only:

1. PIT/raw-data completeness audit;
2. construction of a no-forward feature panel;
3. label-free redundancy/novelty calculations;
4. persistence of source hashes, panel hashes, and verdicts.

Discovery remains sealed until the preregistered novelty gate and implementation audit receive a full PASS.
