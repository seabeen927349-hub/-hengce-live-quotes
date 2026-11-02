# HENGCE Market State × Selection — Preregistration

Date: 2026-11-02 (Asia/Taipei)
Project: `research/market_state_selection_interaction_20261102`
Upstream literature gate: `LITERATURE_GATE.json = PASS`
Frozen Market State source: `research/market_state_observation_20261102/14_S5_STATE_CLASSIFIER_FREEZE_20261102.json`
Frozen state input matrix SHA256: `2e9783338e24a1f2fd5303780750b8c269316265b4ea394f1dc8e4d3ca831755`

## 1. Question

Does the already-frozen HENGCE contemporaneous Market State condition the 20-session cross-sectional excess return of one fixed, simple, point-in-time electronics selection benchmark?

This is deliberately **not** a test of the unfinished new HENGCE Selection Core. It is a bounded falsification test of whether Market State contains information relevant to cross-sectional selection at all.

## 2. Hard anti-contamination rules

Before this preregistration was committed:
- no forward stock return for this experiment was inspected;
- no state-to-future-return mapping was inspected;
- no benchmark-selection performance was inspected;
- no state-specific rule was constructed;
- no horizon comparison was performed.

After this commit:
- the state classifier may not be changed;
- the universe rule may not be changed;
- the selection rule may not be changed;
- the 20-session primary horizon may not be replaced because another horizon looks better;
- no state-specific threshold/expert/filter may be introduced in this experiment;
- no result creates trading or production authority.

## 3. Data lineage

Use only the existing official HENGCE historical electronics archives:
`/HENGCE_CANONICAL/HIST_SOURCE_2018_2026_20261027/TWSE_ELECTRONICS_YYYY.zip`, years 2018–2026.

Each yearly archive supplies:
- `electronics_YYYY.csv` — date-correct listed-electronics stock rows;
- `trading_sessions_YYYY.csv` — Taiwan trading-session calendar / TAIEX context;
- `corporate_actions_YYYY.csv` — official ex-reference data.

No fresh download, alternate data vendor, alternate mother, or survivor-biased current stock list is allowed.

Use `HENGCE_MARKET_ENVIRONMENT_OBSERVATION_MATRIX_V3.csv` only for the frozen contemporaneous state features and date mapping. It contains no forward-return columns.

## 4. Timing / point-in-time contract

For market event date `d`:
- all selection inputs use information through the close of `d` only;
- the S5 state is the frozen classification attached to `NEXT_SESSION_OPEN_CONTEXT(d)`;
- `entry_date` is the next Taiwan trading session after `d`, equal to the observation date;
- portfolio entry is at `entry_date` open;
- the primary holding horizon is exactly 20 Taiwan trading sessions, counting `entry_date` as holding session 1;
- exit is the close of holding session 20.

No future availability may affect candidate ranking at `d`.

## 5. Corporate-action-safe daily price-path returns

For stock `i` on date `t` after the first observation:
- `REF(i,t) = official_ex_reference(i,t)` if an official corporate-action reference exists;
- otherwise `REF(i,t) = close(i,t-1)`;
- `r(i,t) = ln(close(i,t) / REF(i,t))` when both prices are valid.

This is a price-path return, not a total-return/dividend-reinvestment claim.

## 6. Point-in-time tradable U100

For each signal date `d`:
1. start from the date-correct electronics members present in the official archive on `d`;
2. require valid current close;
3. over the latest 20 Taiwan trading sessions ending at `d`, require at least 18 valid turnover observations;
4. define `LIQ20 = median(turnover_ntd)` over those valid observations;
5. require 20 valid corporate-action-safe daily returns in the latest 20 trading sessions ending at `d` for the momentum ranking below;
6. rank eligible names by `LIQ20` descending, tie-break by ticker ascending;
7. retain the first 100 names as `U100`.

If fewer than 100 names satisfy the rules, that signal date is not eligible.

## 7. Fixed selection benchmark

For each `U100` member on signal date `d`:
- `MOM20 = sum` of its 20 corporate-action-safe log price-path returns ending at `d`.

Rank by:
1. `MOM20` descending;
2. `LIQ20` descending;
3. ticker ascending.

Select exactly Top 5. Equal-weight: 20% each.

No other feature, score, flow, margin, TDCC, industry, valuation, or state-specific input may alter this ranking.

## 8. Frozen 20-session outcome

For a stock selected at `d`, entry at next-session open `t0` and 20-session exit `t19`:

`H20_LOG_RETURN = ln(close(t0)/open(t0)) + sum_{j=1..19} r(i,tj)`

where subsequent daily `r` uses the corporate-action-safe reference rule above.

Convert to simple return for reporting:
`H20_RETURN = exp(H20_LOG_RETURN) - 1`.

Per signal date:
- `TOP5_H20` = equal-weight mean of valid Top-5 simple returns;
- `U100_H20` = equal-weight mean of the same entry/exit simple returns for the signal-date U100;
- `TOP5_EXCESS_H20 = TOP5_H20 - U100_H20`.

Primary date-quality gate:
- all 5 Top-5 outcomes must be valid;
- at least 95 of the 100 U100 outcomes must be valid.

Dates failing this outcome-data-quality gate are excluded from the primary inferential sample, with counts reported. No missing outcome may be imputed or replaced.

## 9. State variable

Use the frozen S5 classifier without refit:
- `DIFFUSE_NORMAL`
- `SYNCHRONIZED_STRESS`

Rows with `UNKNOWN_FAIL_CLOSED` are excluded from state comparison and reported.

The classifier was fit on contemporaneous features across the historical sample but used no forward outcomes. Therefore this experiment can establish retrospective outcome association with the frozen taxonomy; it is **not** a historical real-time OOS validation of state discovery.

## 10. Primary estimand

Define:

`DELTA = mean(TOP5_EXCESS_H20 | SYNCHRONIZED_STRESS) - mean(TOP5_EXCESS_H20 | DIFFUSE_NORMAL)`.

Interpretation:
- `DELTA > 0`: the same fixed momentum benchmark had higher cross-sectional excess return in stress;
- `DELTA < 0`: it had higher cross-sectional excess return in diffuse/normal conditions.

The sign is not hypothesized in advance.

## 11. Inference for overlapping 20-session outcomes

Daily signal dates create heavily overlapping H20 returns. Ordinary iid t-tests are not authoritative.

Primary inference:
1. OLS: `TOP5_EXCESS_H20 = alpha + beta * I(SYNCHRONIZED_STRESS) + error`;
2. report `beta = DELTA` with Newey-West/HAC standard errors using lag 20;
3. moving-block bootstrap with block length 20 trading observations and 10,000 resamples; report 95% CI for DELTA.

No lag or block-length search is allowed.

## 12. Temporal stability audit

Without retuning, report DELTA separately for:
- early period: 2018-01-01 through 2022-12-31;
- late period: 2023-01-01 through 2026-10-27, subject to H20 outcome availability.

No yearly cherry-picking is allowed.

## 13. Secondary descriptive outputs

Report by state:
- number of primary eligible signal dates;
- mean and median `TOP5_H20`;
- mean and median `U100_H20`;
- mean and median `TOP5_EXCESS_H20`;
- fraction of dates with `TOP5_EXCESS_H20 > 0`;
- outcome coverage / excluded-date counts.

These are diagnostics, not separate success gates.

## 14. Frozen conclusion taxonomy

### `CONDITIONING_ESTABLISHED`
Only if BOTH hold:
1. the primary moving-block-bootstrap 95% CI for DELTA excludes zero; and
2. early-period and late-period DELTA have the same sign as full-sample DELTA.

### `ECONOMICALLY_MATERIAL_CANDIDATE`
Only if `CONDITIONING_ESTABLISHED` and additionally `abs(DELTA) >= 0.01` (1.0 percentage point over 20 sessions).

This is a secondary practical-materiality flag, not a trading threshold.

### `INCONCLUSIVE`
If full-sample evidence is suggestive but the CI includes zero or temporal sign consistency fails.

### `NO_STATE_CONDITIONING_EVIDENCE`
If the state difference is small/unstable and the preregistered tests do not support conditioning.

A null or failed result must be retained; it may not be rescued by changing horizon, universe, ranking rule, or state definition.

## 15. Authority boundary

Even `ECONOMICALLY_MATERIAL_CANDIDATE` means only:
> the frozen Market State is worth carrying forward as a candidate conditioning variable for later clean Selection-Core research.

It does **not** authorize:
- BUY/SELL;
- market exposure changes;
- state-specific experts;
- changing ranking weights;
- production promotion;
- capital allocation.

A future state-conditioned Selection Core would require a separate preregistration and untouched OOS/prospective validation.
