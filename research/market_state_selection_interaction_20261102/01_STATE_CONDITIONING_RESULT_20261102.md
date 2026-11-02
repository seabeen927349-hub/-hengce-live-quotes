# HENGCE Market State × Fixed Selection Benchmark — Corrected Result

Date: 2026-11-02 (Asia/Taipei)  
Preregistration commit: `50e41ec44e2adebf719662a8eb3894845b55f4aa`  
Status: **ECONOMICALLY_MATERIAL_CANDIDATE — conditioning established under the preregistered retrospective test; no trading/production authority**

## 0. Correction audit

An initial result commit used a parser that stripped comma formatting from 2026 `turnover_ntd` but did not uniformly strip commas from all 2026 numeric OHLC fields. The official 2026 archive contains values such as `3,750.00`; those high-price observations were therefore incorrectly parsed as missing in the first execution.

Before this result was reported to the user as final, an independent clean replay detected the discrepancy. The corrected implementation applies one uniform numeric sanitation rule to **all** numeric archive fields: remove comma separators, then numeric-convert. No economic definition, universe rule, state definition, ranking rule, horizon, outcome gate, or inference rule was changed.

Two independent implementations using the corrected parser reproduce the same corrected sample counts, state summaries, DELTA, HAC statistics, block-bootstrap interval, and temporal deltas.

The earlier `INCONCLUSIVE` result is superseded as an implementation/parser defect, not as a retune.

## 1. What was tested

This is **not** a test of the unfinished new HENGCE Selection Core. It is the preregistered bounded test of whether the already-frozen S5 Market State conditions one fixed, simple point-in-time electronics selection benchmark.

Frozen benchmark:
- date-correct listed-electronics universe from existing official yearly HENGCE archives;
- liquid U100 formed only from the latest 20 sessions known at signal close;
- rank U100 by 20-session corporate-action-safe momentum;
- select Top 5, equal weight;
- enter next Taiwan trading session at open;
- hold exactly 20 trading sessions;
- compare Top-5 return with same-date U100 equal-weight return;
- no state-specific rule, threshold, feature, horizon, or retuning.

The S5 classifier was already frozen before this experiment and had used no forward returns. The classification itself remains descriptive-only and has no trading authority.

## 2. Input lineage

State matrix:
- `HENGCE_MARKET_ENVIRONMENT_OBSERVATION_MATRIX_V3.csv`
- SHA256 `2e9783338e24a1f2fd5303780750b8c269316265b4ea394f1dc8e4d3ca831755`

Official yearly electronics archive SHA256:
- 2018 `eb233ccafbb5d2cacb293a926dd2211bc803e79d5d409685fa2b021dfa223759`
- 2019 `01f680cb42cc074b716c762ed0d886af44e0cdbef04d5cd236cd4df127df8a9f`
- 2020 `c57fc918e9a18a57ffaa9b500c41b2ca6ead94cd2ceb227637444e784ae7cb0d`
- 2021 `ee2ae0fe25e2e1cebf220faaa546089210311311257256e6f1ba22f8389bc594`
- 2022 `ad2ece10ec4a0e94c501def438c6e7c92a5193975dcb33a76e8f915c8183cc9b`
- 2023 `09a50dd3d6b3fc8c7730c65044231836811c83ce420a538ed2ac8f126e680dca`
- 2024 `f4518a7951bfffac59242955cef117b9d0f064730a43380126cf3f9655219979`
- 2025 `22851a275796c0ec4f089353b31415f148b17e1c1ec7dc8d4a07b5f88601f41a`
- 2026 `4be2223ca3dcbd01645fe90e53332a19600acbef070297d7358adf49c288d530`

## 3. Primary sample

Frozen S5 classified observations available before outcome-quality filtering:
- `DIFFUSE_NORMAL`: 1,714
- `SYNCHRONIZED_STRESS`: 369

Primary H20 sample after the preregistered outcome-quality gate:
- total signal dates: **1,986**
- first signal date: **2018-04-03**
- last signal date with mature H20 outcome: **2026-09-22**
- `DIFFUSE_NORMAL`: **1,641**
- `SYNCHRONIZED_STRESS`: **345**

Exclusions by state:

| Reason | DIFFUSE_NORMAL | SYNCHRONIZED_STRESS |
|---|---:|---:|
| Primary included | 1,641 | 345 |
| Top-5 outcome invalid | 55 | 23 |
| H20 horizon not yet mature | 18 | 1 |

No missing outcome was imputed or rescued.

## 4. State-conditional 20-session results

| Metric | DIFFUSE_NORMAL | SYNCHRONIZED_STRESS |
|---|---:|---:|
| Signal dates | 1,641 | 345 |
| Mean Top-5 H20 | **+3.8181%** | **+5.0526%** |
| Median Top-5 H20 | +2.8522% | +4.8753% |
| Mean U100 H20 | **+1.5011%** | **+5.2111%** |
| Median U100 H20 | +2.2789% | +5.2110% |
| Mean Top5 − U100 excess | **+2.3170%** | **−0.1584%** |
| Median Top5 − U100 excess | +0.6381% | **−0.4891%** |
| Fraction excess >0 | 53.32% | 46.09% |

The important distinction is between **absolute return** and **selection edge**:
- after stress-state observations, the whole U100 tended to rebound strongly (+5.21% mean H20), and Top 5 also rose (+5.05%);
- however, the fixed Top-5 momentum ranking slightly **underperformed** U100 on average in stress (−0.16% excess);
- in diffuse/normal conditions, U100 mean H20 was only +1.50%, while Top 5 averaged +3.82%, giving +2.32% mean excess.

Therefore the result is not “stress predicts falling stocks.” It indicates that, for this fixed benchmark, **cross-sectional selection edge was materially compressed during synchronized-stress environments even while the whole electronics universe often rebounded strongly afterward**.

## 5. Primary estimand

Preregistered:

`DELTA = mean(excess | SYNCHRONIZED_STRESS) - mean(excess | DIFFUSE_NORMAL)`

Observed:

**DELTA = −2.4755 percentage points over 20 sessions.**

So the fixed benchmark's average cross-sectional excess was about 2.48 percentage points lower in the stress state.

## 6. Overlap-robust inference

Twenty-session outcomes overlap heavily, so iid t-tests are not authoritative.

### Newey-West / HAC, lag 20
- DELTA: −2.4755 pp
- HAC SE: 1.1925 pp
- t: −2.0759
- p: **0.0380**
- 95% CI: **[−4.8141 pp, −0.1368 pp]**

### Moving-block bootstrap
Frozen implementation:
- block length: 20 observations
- resamples: 10,000
- RNG seed: 20261102

Result:
- bootstrap mean DELTA: −2.3930 pp
- 95% CI: **[−4.7004 pp, −0.0696 pp]**

The preregistered 95% block-bootstrap interval excludes zero.

## 7. Temporal stability audit

No retuning was performed.

- 2018–2022 DELTA: **−2.8206 pp**
- 2023–2026 DELTA: **−1.8212 pp**

Both frozen temporal halves have the same negative sign as the full sample.

## 8. Frozen conclusion

### `CONDITIONING_ESTABLISHED`: PASS

Both preregistered requirements pass:
1. moving-block-bootstrap 95% CI excludes zero;
2. early and late temporal DELTA have the same sign as the full sample.

### `ECONOMICALLY_MATERIAL_CANDIDATE`: PASS

`abs(DELTA) = 2.4755 pp`, exceeding the preregistered 1.0 percentage-point materiality flag.

Therefore the highest allowed conclusion is:

> **The frozen Market State is a materially relevant candidate conditioning variable for later clean Selection-Core research.**

What this means in plain terms:
- in `DIFFUSE_NORMAL`, this simple momentum selector showed a meaningful ability to separate better stocks from the electronics U100;
- in `SYNCHRONIZED_STRESS`, the same selector lost that relative edge even though absolute future returns were often strong because the whole universe rebounded together.

This is exactly the kind of structural distinction that can justify testing different selection behavior by state.

## 9. Critical limitation

This remains a **retrospective association test**, not untouched historical real-time OOS validation of the state engine itself. The S5 state geometry was fit using contemporaneous observations across the historical sample, although it did not inspect forward outcomes.

Therefore this result may justify a future state-conditioned research architecture, but it may not be used to claim a production-grade regime gate or to infer that current stress should automatically suppress buying.

## 10. Authority boundary

This result grants:
- no BUY/SELL authority;
- no exposure rule;
- no state-specific production threshold;
- no production expert routing;
- no production promotion;
- no capital authority.

The next valid research step is a **new preregistered state-conditioned Selection-Core design followed by untouched temporal OOS/prospective validation**. The present result can be used as prior evidence for that research question, including its uncertainty and parser-correction audit.
