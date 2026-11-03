# HENGCE Opportunity Capacity × Frozen MOM20 Edge — Preregistration

Date: 2026-11-03 (Asia/Taipei)
Project: `research/cross_section_opportunity_20261103`
Upstream topic gate: `LITERATURE_GATE.json = PASS_DIAGNOSTIC_ONLY`
Upstream opportunity-capacity preregistration: `00_PREREGISTRATION_OPPORTUNITY_CAPACITY.md`
Frozen MOM20 benchmark contract/result source: `research/market_state_selection_interaction_20261102/00_PREREGISTRATION_STATE_CONDITIONING_TEST.md`
Frozen input matrix SHA256: `2e9783338e24a1f2fd5303780750b8c269316265b4ea394f1dc8e4d3ca831755`

## 1. Question

Does the point-in-time cross-sectional differentiation capacity that survived the first preregistered diagnostic actually condition the realized 20-session cross-sectional excess return of the already-frozen MOM20 Top-5 selector?

This directly separates two concepts:
- `opportunity capacity`: how much future cross-sectional differentiation exists;
- `selection edge`: whether one fixed selector can exploit that differentiation.

The first diagnostic established only the former. This experiment tests their connection for one frozen selector; it does not invent a new selector.

## 2. Anti-contamination statement

Before this preregistration commit:
- the canonical MOM20 date-level result was replayed only to verify exact reproduction of the already-known aggregate state-conditioning result;
- no MOM20 date-level outcome was merged with `ELEC_XS_MAD_1` / `MAD_Z` for this question;
- no MOM20 excess was grouped, regressed, correlated, plotted, or thresholded by current cross-sectional MAD;
- no capacity threshold was selected using MOM20 outcomes.

After this commit:
- predictor, outcome, state interaction, horizon, temporal split, and inference method may not change in response to results;
- no threshold search is allowed;
- no alternate momentum horizon/ranking may be substituted;
- no result creates trading, production, exposure, or capital authority.

## 3. Data lineage

Use only:
1. exact canonical yearly archives `TWSE_ELECTRONICS_2018.zip` through `TWSE_ELECTRONICS_2026.zip`, with the already-recorded canonical SHA256 values;
2. exact frozen Market Environment Matrix with SHA256 `2e9783338e24a1f2fd5303780750b8c269316265b4ea394f1dc8e4d3ca831755`;
3. the already-corrected uniform numeric parser rule: remove comma separators from every numeric archive field before numeric conversion.

The MOM20 replay must first reproduce exactly:
- n = 1,986;
- Normal mean excess H20 = 0.023170258091523337;
- Stress mean excess H20 = -0.001584329217566494;
- Stress-minus-Normal delta = -0.02475458730908983;
- HAC lag20 p = 0.038035387022118304.

If exact replay fails, this experiment stops.

## 4. Outcome

For each primary MOM20 signal date, use the already-frozen:

`MOM20_EXCESS_H20 = TOP5_H20 - U100_H20`.

No outcome definition changes are allowed.

## 5. Predictor

Use exactly one opportunity-capacity predictor selected by the first preregistered diagnostic:

`MAD_Z = (ELEC_XS_MAD_1 - 0.009115597798) / 0.0031179637715`

measured on the MOM20 signal date.

Why only this predictor:
- in the first preregistered capacity diagnostic, `MAD_Z` was the only prespecified predictor whose coefficient sign was stable in both 2018–2022 and 2023–2026;
- `SYNC_Z` and `RV_Z` changed sign across periods and therefore are not promoted into this bridge test.

This choice is based on the already-preregistered capacity outcome, not on MOM20 selection outcomes.

## 6. Frozen state control

Use the already-frozen S5 state label:
- `DIFFUSE_NORMAL` => `STRESS = 0`
- `SYNCHRONIZED_STRESS` => `STRESS = 1`

Only MOM20 primary dates have known state by construction.

## 7. Primary model

Estimate exactly:

`MOM20_EXCESS_H20 = alpha + b1*MAD_Z + b2*STRESS + b3*(MAD_Z*STRESS) + error`.

Use Newey-West/HAC standard errors with lag 20.

Interpretation:
- Normal capacity slope: `B_NORMAL = b1`;
- Stress capacity slope: `B_STRESS = b1 + b3`;
- state difference in capacity slope: `B_INTERACTION = b3`.

Report HAC 95% confidence intervals and p-values for all three linear combinations. No iid t-test is authoritative.

No sign is hypothesized in advance.

## 8. Temporal stability

Run the identical model without retuning for:
- early: 2018-01-01 through 2022-12-31;
- late: 2023-01-01 through the latest mature MOM20 signal date.

For `B_NORMAL` and `B_STRESS`, report early and late coefficient signs.

## 9. Secondary descriptive terciles

For descriptive interpretation only, within each frozen state separately:
- compute current `MAD_Z` terciles using current predictor values only;
- report n, mean and median `MOM20_EXCESS_H20`, and positive-excess fraction for LOW / MID / HIGH terciles.

Terciles are not trading thresholds and may not be optimized.

## 10. Conclusion taxonomy

### `CAPACITY_CONDITIONS_MOMENTUM_EDGE`
If at least one of `B_NORMAL` or `B_STRESS` has a full-sample HAC 95% CI excluding zero AND that slope has the same sign in early and late periods.

### `STATE_SPECIFIC_CAPACITY_RELATION_SUGGESTIVE`
If the interaction or a state-specific slope looks nonzero but the required temporal sign stability fails.

### `CAPACITY_DOES_NOT_MAP_TO_MOMENTUM_EDGE`
If neither state-specific slope has a full-sample HAC 95% CI excluding zero.

A significant negative slope is a valid result: more raw differentiation may make this particular momentum selector worse. It must not be rescued.

## 11. Authority boundary

Even `CAPACITY_CONDITIONS_MOMENTUM_EDGE` does not authorize a capacity gate, threshold, BUY/SELL rule, new expert, or capital allocation. It only tells us whether the first-stage opportunity-capacity signal is relevant to one already-frozen selector.

A production rule would require a separately frozen candidate plus untouched prospective/OOS validation.