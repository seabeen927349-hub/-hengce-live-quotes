# HENGCE LOSS FORENSICS — Stage I Large-Layer Internal Rotation V1 Results

Date: 2026-11-01  
Preregistration commit: `2d16de583f436d0a0450ce8c010cf4f1f4d6e63a`  
Status: **EXPLORATORY_WEAK / FORMAL_WEIGHT=0 / NO TRADING AUTHORITY**

## 0. Executive result

The locked hypothesis was directionally supported but only weakly.

Within the frozen Big400-fracture population, events with more internal offset between the >1000-lot layer and the 400–1000-lot layer tended to have somewhat smaller subsequent 20-session maximum closing-price loss than coherent exits where both large-holder layers fell together.

The locked expanding-time TEST model improved both aggregate held-out MAE and RMSE versus BASE, satisfying the narrow aggregate incremental gate. However:
- the improvement was very small;
- the adjusted structural coefficient confidence interval crossed zero;
- the early chronological block showed essentially no protective relation;
- held-out improvement was concentrated in the later block rather than being stable throughout history.

Therefore V1 is **not** promoted to `STRUCTURAL_SUPPORTED_NOT_CALIBRATED`. The correct historical verdict is `EXPLORATORY_WEAK`.

Formal probability weight remains `0`.

## 1. Frozen population integrity

Stage I reused the exact Stage H 368-event matrix; no new event generation occurred after outcome inspection.

Frozen authority:
- 503 down-leg identity SHA256: `f03abb00e164ac16868274f866f0bb4eba30b0dca0e86257fd5d8573448348e3`;
- 368 fracture cohort SHA256: `b42ca061bd51d62ebeb4ab4fd128b371260d02a871f2e9f9cf85f904078b4920`.

The Stage H matrix contains exactly:
- 330 prior Stage-H `OK` rows;
- 37 prior Stage-H corporate-action-censored rows;
- 1 prior Stage-H right-censored row;
- total = 368.

For Stage I, all 368 events mapped one-to-one to `current100_ownership_intervals_audit.csv` at t0.

Maximum absolute difference between frozen `dB400_t0` and the ownership audit `dB400` was only floating-point noise:

`4.44e-16` percentage points.

Ownership denominator integrity:
- `stable_1pct=True`: 364 / 368;
- `stable_1pct=False`: 4 / 368.

## 2. Pre-registered ownership decomposition

For each fracture:
- `U = Big1000Pct`;
- `L = Big400Pct - Big1000Pct`;
- `S = 100 - Big400Pct`;
- `dB400 = dU + dL`.

Primary predictor:

`INTERNAL_OFFSET_SHARE = (abs(dU)+abs(dL)-abs(dB400)) / (abs(dU)+abs(dL))`

Interpretation:
- 0 = coherent movement across the two large-holder layers, with no internal U/L cancellation;
- larger values = more opposite-direction U/L movement relative to the same net Big400 loss.

Pre-outcome sign-class counts reproduced the preregistration audit exactly:

| Mechanism class | All 368 | stable_1pct only |
|---|---:|---:|
| TOP_TO_MID_HANDOFF | 167 | 166 |
| COHERENT_EXIT | 149 | 147 |
| MID_EXIT_TOP_ACCUM | 42 | 41 |
| BOUNDARY_TIE | 10 | 10 |

`INTERNAL_OFFSET_SHARE` distribution across all 368:
- min 0;
- median 0.09324;
- 75th percentile 0.52552;
- max 0.99469.

## 3. Corporate-action and outcome eligibility

Primary endpoint:

`FWD20_MDD_LOSS = max(0, 1 - min(Close[t0+1 ... t0+20]) / Close[t0])`

using the next 20 valid same-stock trading sessions.

The existing TWSE corporate-action protocol was reused rather than invented after seeing outcomes. In `TWSE_2026_price.csv`, the corporate-action/reference-price discontinuity marker is `ChangeSign = <p>X</p>`.

Protocol cross-check:
- all 37 corporate-action dates already censored by Stage H map exactly to this `X` marker.

Stage I outcome status before ownership-integrity filtering:
- `OK`: 309;
- `CORP_ACTION_CENSORED`: 55;
- `RIGHT_CENSORED`: 4.

After additionally requiring `stable_1pct=True`:
- primary evaluable price events: **305**.

The fixed BASE/TEST covariate set was complete for 288 events. No future-data imputation was used. Missingness among the 305 price-evaluable events was concentrated in early-history pre-t0 lookbacks:
- pre-t0 volatility: 13 missing;
- pre-t0 median traded value: 7 missing;
- margin change: 4 missing;
- fracture magnitude, peak drawdown and electronics interval return: 0 missing.

BASE and TEST always used identical complete-case rows.

## 4. Raw economic damage by mechanism

Among the 305 primary price-evaluable events:

| Mechanism class | N | Mean FWD20 max loss | Median FWD20 max loss |
|---|---:|---:|---:|
| COHERENT_EXIT | 129 | 10.59% | 9.26% |
| TOP_TO_MID_HANDOFF | 137 | 9.98% | 8.33% |
| MID_EXIT_TOP_ACCUM | 31 | 10.25% | 9.09% |
| BOUNDARY_TIE | 8 | 9.52% | 9.62% |

The raw coherent-exit versus top-to-mid-handoff difference is therefore directionally consistent with I-H1, but modest.

## 5. Continuous offset descriptive relationship

The preregistration required quartile reporting. The empirical 25th percentile of `INTERNAL_OFFSET_SHARE` is exactly zero, so four unique quantile boundaries do not exist without arbitrarily splitting identical zero observations.

To avoid post-hoc tie breaking, identical zeros were not split. The descriptive quantile report therefore contains three unique bins:

| Offset bin | N | Offset range | Mean FWD20 max loss | Median FWD20 max loss |
|---|---:|---:|---:|---:|
| Low | 153 | 0.0000–0.0692 | 10.71% | 9.28% |
| Middle | 76 | 0.0700–0.4901 | 10.49% | 9.24% |
| High | 76 | 0.5000–0.9947 | 9.08% | 8.26% |

The direction is monotone across these unique bins: more internal U/L offset is associated with less subsequent downside.

This is descriptive only; these bins are not authorized thresholds.

## 6. Locked expanding-time BASE vs TEST

Model:
- Ridge regression;
- alpha = 1.0;
- training-only standardization;
- no feature selection;
- no interaction search;
- no hyperparameter tuning;
- expanding-time by t0 date;
- begin only after at least 80 eligible prior events.

BASE predictors:
1. Big400 fracture magnitude;
2. pre-t0 20-session volatility;
3. pre-t0 20-session median traded value;
4. t0 drawdown from frozen swing peak;
5. margin-balance change from the preceding ownership snapshot;
6. electronics-universe return over the preceding ownership interval.

TEST = BASE + `INTERNAL_OFFSET_SHARE`.

Held-out evaluation:
- N = **193**;
- 22 held-out t0 date blocks;
- first held-out t0 = 2026-04-02;
- last held-out t0 = 2026-09-11.

| Metric | BASE | TEST | TEST - BASE |
|---|---:|---:|---:|
| MAE | 8.8300% | 8.7879% | **-0.0421 pp** |
| RMSE | 11.2879% | 11.2472% | **-0.0407 pp** |

Thus the narrow aggregate preregistered gate — TEST improves both MAE and RMSE — **passes**.

However, the economic size of the improvement is small.

## 7. Adjusted structural diagnostic

Fixed full-sample adjusted diagnostic on the 288 complete-case events:

`FWD20_MDD_LOSS ~ INTERNAL_OFFSET_SHARE + BASE covariates`

With all predictors standardized, the `INTERNAL_OFFSET_SHARE` coefficient was:
- coefficient: **-0.00945**;
- HC3 95% interval: **[-0.02071, +0.00181]**;
- HC3 p = 0.1000.

Ticker-clustered inference:
- coefficient: **-0.00945**;
- 95% interval: **[-0.02124, +0.00234]**;
- p = 0.1161.

On the raw 0-to-1 offset scale, holding standardized BASE covariates fixed:
- coefficient: **-0.02867**;
- HC3 95% interval: **[-0.06283, +0.00549]**.

Interpretation: moving from no internal offset to the theoretical maximum offset corresponds to about 2.87 percentage points less 20-session maximum loss in the fitted sample, but the uncertainty interval includes zero.

Therefore the structural diagnostic is directionally favorable but not statistically robust.

## 8. Chronological stability

Fixed chronological split date from the eligible model sample: **2026-05-29**.

Adjusted standardized coefficient by block:
- EARLY: N=143, coefficient **+0.00121**, p=0.836;
- LATE: N=145, coefficient **-0.01662**, p=0.094.

The early block is essentially null, while the later block carries the protective direction.

Held-out BASE vs TEST by the same split:

### EARLY held-out
- N=48;
- MAE: 6.8772% -> 6.8838% (**slightly worse by +0.0066 pp**);
- RMSE: 7.9763% -> 8.0000% (**slightly worse by +0.0237 pp**).

### LATE held-out
- N=145;
- MAE: 9.4765% -> 9.4182% (**improves by -0.0582 pp**);
- RMSE: 12.1875% -> 12.1321% (**improves by -0.0554 pp**).

Across the 22 held-out date blocks, TEST beat BASE on both mean absolute-error contribution and squared-error contribution on 14 dates, and lost on the remainder.

This chronology is the main reason V1 is not classified as structural support.

## 9. Concentration robustness

Model-complete sample concentration:
- most frequent ticker: `2408`, 7 / 288 events;
- most populated t0 date: `2026-03-27`, 27 / 288 events.

### Remove the most frequent ticker (2408)
Held-out N=189:
- MAE: 8.8310% -> 8.7910%;
- RMSE: 11.3425% -> 11.3066%.

Both metrics still improve.

### Remove the most populated date (2026-03-27)
Held-out N=178:
- MAE: 9.0355% -> 8.9709%;
- RMSE: 11.6191% -> 11.5478%.

Both metrics still improve.

Therefore the weak aggregate improvement is not explained by one ticker or one t0 date.

## 10. Secondary ownership mechanism checks

These do not determine the primary verdict.

Next-valid-snapshot broad ownership loss (`next dBig400 < 0` and next `dBig1000 < 0`) among primary price-evaluable events:
- COHERENT_EXIT: 71 / 129 = **55.0%**;
- TOP_TO_MID_HANDOFF: 68 / 137 = **49.6%**;
- MID_EXIT_TOP_ACCUM: 13 / 31 = **41.9%**;
- BOUNDARY_TIE: 1 / 8 = **12.5%**.

Four-snapshot cumulative Big400 change (`next4_sum`) mean:
- COHERENT_EXIT: **-0.374 pp**;
- TOP_TO_MID_HANDOFF: **+0.476 pp**;
- MID_EXIT_TOP_ACCUM: **-0.372 pp**;
- BOUNDARY_TIE: **+1.791 pp**.

The ownership mechanism checks are compatible with the price result: internal large-layer rotation, especially >1000 -> 400–1000 handoff, is less damaging on average than coherent withdrawal. But these are secondary diagnostics and cannot promote V1.

## 11. Verdict

### Formal Stage I verdict: `EXPLORATORY_WEAK`

Reasons:
1. The primary direction is favorable.
2. The aggregate locked held-out gate passes: TEST improves both MAE and RMSE.
3. The result survives removal of the largest ticker and largest event date.
4. The continuous descriptive relation is directionally ordered.
5. But the improvement is very small.
6. Adjusted HC3 and ticker-clustered intervals cross zero.
7. Early-history evidence is essentially null and early held-out performance is slightly worse.
8. The useful direction is mainly a later-period phenomenon in this 2026 sample.

Therefore the evidence is not strong or stable enough for `STRUCTURAL_SUPPORTED_NOT_CALIBRATED`.

## 12. What this changes — and what it does not

What the research now supports as a weak structural clue:

> Once Big400 has already fractured, it matters somewhat whether both large-holder layers are leaving together or whether the >1000 and 400–1000 layers are partially offsetting one another. A coherent exit appears more damaging; internal large-layer rotation appears less damaging on average.

What it does **not** support:
- beneficial-owner identity;
- “same operator” claims;
- a fixed sell threshold;
- a BUY / SELL rule;
- an escape-monitor rule;
- formal probability weight;
- historical tradability at the TDCC reference date;
- resurrection of failed capital-share migration research.

Historical TDCC exact first-publication timing is still unavailable to the formal actual-availability standard. Formal promotion would require a separate prospective study with immutable first-observed timestamps.

## 13. Frozen authority after execution

Stage I V1 status: `EXPLORATORY_WEAK`  
Formal probability weight: `0`  
Production authority: `NONE`  
Trading authority: `NONE`  
Anti-rescue lock: **ACTIVE**

No horizon, bucket boundary, model alpha, event population, exclusion, or outcome definition may now be changed to rescue V1. A materially different test requires a new preregistration.
