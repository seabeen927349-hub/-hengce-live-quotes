# HENGCE Cross-Section Opportunity Capacity — Preregistration

Date: 2026-11-03 (Asia/Taipei)
Project: `research/cross_section_opportunity_20261103`
Upstream literature gate: `LITERATURE_GATE.json = PASS_DIAGNOSTIC_ONLY`
Frozen input matrix: `HENGCE_MARKET_ENVIRONMENT_OBSERVATION_MATRIX_V3.csv`
Frozen input matrix SHA256: `2e9783338e24a1f2fd5303780750b8c269316265b4ea394f1dc8e4d3ca831755`
Frozen state classifier: `research/market_state_observation_20261102/14_S5_STATE_CLASSIFIER_FREEZE_20261102.json`

## 1. Question

Can information visible at the current Taiwan electronics market close identify whether the *next 20 Taiwan trading sessions* will contain a larger or smaller cross-sectional differentiation opportunity set?

This is a diagnostic of opportunity capacity. It is not a trading strategy, not a ranking rule, and not a test that high dispersion automatically creates alpha.

## 2. Hard anti-contamination rules

Before this preregistration commit:
- no shifted/future `ELEC_XS_MAD_1` outcome for this experiment was computed or inspected;
- no predictor-to-future-opportunity regression was run;
- no state-transition future opportunity summary was inspected;
- no threshold was selected based on future opportunity outcomes.

After this commit:
- the primary outcome definition may not change;
- the predictor set may not change;
- the 20-session horizon may not be replaced because another horizon looks better;
- no percentile or threshold search is allowed in the primary test;
- no result creates BUY/SELL, ranking, exposure, production, or capital authority.

## 3. Timing

For each eligible matrix row with market event date `d`:
- predictors use only values present on row `d`;
- future opportunity window is the next 20 sequential Taiwan market-event observations after `d`, excluding `d` itself;
- the row is eligible only if all required current predictors are non-missing and all 20 future `ELEC_XS_MAD_1` observations are available.

This is retrospective development evidence; 2018–2026 is not untouched OOS for this research program.

## 4. Primary outcome

Define:

`FWD20_XS_MAD_MEAN(d) = mean(ELEC_XS_MAD_1 over d+1 ... d+20 trading observations)`.

`ELEC_XS_MAD_1` is the already-existing point-in-time cross-sectional median absolute deviation measure in the frozen Market Environment Matrix.

Interpretation:
- larger `FWD20_XS_MAD_MEAN` = future daily stock returns are, on average, more differentiated across the electronics cross-section;
- smaller value = future cross-section is more compressed.

This is opportunity *capacity*, not realized alpha or manager skill.

## 5. Frozen current predictors

Use exactly three current variables, all already present in the frozen matrix:
1. `ELEC_XS_MAD_1` — current one-session cross-sectional differentiation;
2. `ELEC_SYNC20` — current 20-session synchronization;
3. `TAIEX_RV20` — current 20-session market volatility.

Each is transformed using the already-frozen S5 RobustScaler median/IQR where available:
- `MAD_Z = (ELEC_XS_MAD_1 - 0.009115597798) / 0.0031179637715`
- `SYNC_Z = (ELEC_SYNC20 - 0.516295466743) / 0.1897473237275`
- `RV_Z = (TAIEX_RV20 - 0.150345114704) / 0.0765906461875`

No refit scaling is allowed.

## 6. Primary model

Estimate one prespecified OLS diagnostic:

`FWD20_XS_MAD_MEAN = alpha + b1*MAD_Z + b2*SYNC_Z + b3*RV_Z + error`.

Because adjacent 20-session outcomes overlap, use Newey-West/HAC standard errors with lag 20.

Primary falsifiable statements:
- `b1` tests persistence of current cross-sectional differentiation;
- `b2` tests whether synchronization contains incremental information about future differentiation after controlling for current differentiation and volatility;
- `b3` controls for the possibility that dispersion is merely a volatility proxy.

No sign is required in advance. The model is informative only if at least one predictor has a HAC 95% confidence interval excluding zero and temporal stability is not contradictory.

## 7. Temporal stability

Without retuning, rerun the same model for:
- early: 2018-01-01 through 2022-12-31;
- late: 2023-01-01 through the latest mature date.

For each predictor whose full-sample HAC 95% CI excludes zero, report whether the early and late coefficient signs agree with the full-sample sign.

## 8. Secondary transition diagnostic

Reproduce the frozen S5 labels exactly from the frozen classifier. Then, for descriptive purposes only, assign current rows to one of these ex-post path categories based on the next 20 state labels:
- `NORMAL_STABLE`: current `DIFFUSE_NORMAL` and no Stress observation in the next 20;
- `NORMAL_TO_STRESS`: current `DIFFUSE_NORMAL` and at least one Stress observation in the next 20;
- `EARLY_STRESS`: current Stress and at least one Normal observation occurred within the previous 5 observations;
- `MATURE_STRESS`: current Stress and previous 5 observations are all Stress;
- `STRESS_TO_NORMAL`: current Stress and at least one Normal observation occurs within the next 5 observations.

These categories may overlap (`STRESS_TO_NORMAL` can also be `EARLY_STRESS` or `MATURE_STRESS`), so they are reported as separate descriptive lenses, not mutually exclusive regression states.

For each category, report mean/median `FWD20_XS_MAD_MEAN` and sample size. Do not run threshold searches or construct trading rules from these summaries.

## 9. Normal-state heterogeneity diagnostic

Within rows currently classified `DIFFUSE_NORMAL`, report `FWD20_XS_MAD_MEAN` by frozen, outcome-blind terciles of current `SYNC_Z` and separately by current `MAD_Z` terciles. Tercile cutpoints are computed from the current predictor distribution only, never from future outcomes.

This is descriptive and may show that the broad Normal state contains different opportunity-capacity conditions. It cannot authorize a new state taxonomy.

## 10. Conclusion taxonomy

### `PREDICTABLE_OPPORTUNITY_CAPACITY`
If at least one of `b1`, `b2`, `b3` has a full-sample HAC 95% CI excluding zero AND its coefficient sign is the same in early and late samples.

### `WEAK_OR_UNSTABLE_OPPORTUNITY_SIGNAL`
If a full-sample coefficient appears nonzero but temporal sign stability fails, or only borderline evidence is present.

### `NO_PREDICTABLE_OPPORTUNITY_CAPACITY_FOUND`
If none of the three frozen predictors has a HAC 95% CI excluding zero in the full sample.

Even `PREDICTABLE_OPPORTUNITY_CAPACITY` means only that the *size of the future differentiation opportunity set* is partially forecastable. It does not mean HENGCE knows which stocks will win.

## 11. Authority boundary

No outcome from this experiment authorizes:
- a BUY/SELL signal;
- a stock-ranking rule;
- state-specific expert routing;
- exposure changes;
- production promotion;
- capital allocation.

Any later attempt to connect opportunity capacity to actual selection alpha requires a separate preregistration using a frozen selection benchmark and preserved prospective/OOS evidence.