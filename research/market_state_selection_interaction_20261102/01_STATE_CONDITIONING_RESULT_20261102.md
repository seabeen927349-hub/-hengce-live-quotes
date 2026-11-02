# HENGCE Market State × Fixed Selection Benchmark — Result

Date: 2026-11-02 (Asia/Taipei)  
Preregistration commit: `50e41ec44e2adebf719662a8eb3894845b55f4aa`  
Status: **INCONCLUSIVE — directionally large, temporally consistent, but preregistered 95% interval still includes zero**

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

2026 `turnover_ntd` values contain comma formatting in the official archive. The implementation strips commas before numeric conversion; this is numeric sanitation only and does not change the preregistered economic definition.

## 3. Primary sample

Frozen S5 classified observations available before outcome-quality filtering:
- `DIFFUSE_NORMAL`: 1,714
- `SYNCHRONIZED_STRESS`: 369

Primary H20 sample after the preregistered outcome-quality gate:
- total signal dates: **1,921**
- first signal date: **2018-04-03**
- last signal date with mature H20 outcome: **2026-09-22**
- `DIFFUSE_NORMAL`: **1,589**
- `SYNCHRONIZED_STRESS`: **332**

Exclusions by state:

| Reason | DIFFUSE_NORMAL | SYNCHRONIZED_STRESS |
|---|---:|---:|
| Primary included | 1,589 | 332 |
| Top-5 outcome invalid | 93 | 36 |
| U100 valid outcomes <95 | 14 | 0 |
| H20 horizon not yet mature | 18 | 1 |

The stress-state Top-5-outcome exclusion rate is higher than the normal-state rate. No missing outcome was imputed or rescued; this remains a limitation of the retrospective comparison.

## 4. State-conditional 20-session results

| Metric | DIFFUSE_NORMAL | SYNCHRONIZED_STRESS |
|---|---:|---:|
| Signal dates | 1,589 | 332 |
| Mean Top-5 H20 | **+3.5321%** | **+5.2463%** |
| Median Top-5 H20 | +2.4951% | +4.6225% |
| Mean U100 H20 | **+1.2501%** | **+5.2337%** |
| Median U100 H20 | +2.1453% | +5.1749% |
| Mean Top5 − U100 excess | **+2.2820%** | **+0.0126%** |
| Median Top5 − U100 excess | +0.7129% | **−0.4579%** |
| Fraction excess >0 | 53.87% | 46.39% |

The important distinction is between **absolute return** and **selection edge**:
- after stress-state observations, the whole U100 tended to rebound strongly (+5.23% mean H20), and the Top 5 also rose (+5.25%);
- however, the fixed Top-5 momentum ranking added almost no mean cross-sectional excess over U100 in stress (+0.013%);
- in diffuse/normal conditions, U100 mean H20 was only +1.25%, while Top 5 averaged +3.53%, giving +2.28% mean excess.

Therefore the descriptive pattern is not “stress is bad for future returns.” It is closer to **cross-sectional differentiation compressing during synchronized stress/rebound episodes** for this one fixed benchmark.

## 5. Primary estimand

Preregistered:

`DELTA = mean(excess | SYNCHRONIZED_STRESS) - mean(excess | DIFFUSE_NORMAL)`

Observed:

**DELTA = −2.2695 percentage points over 20 sessions.**

So the fixed benchmark's average cross-sectional excess was about 2.27 percentage points lower in the stress state.

## 6. Overlap-robust inference

Twenty-session outcomes overlap heavily, so iid t-tests are not authoritative.

### Newey-West / HAC, lag 20
- DELTA: −2.2695 pp
- HAC SE: 1.2045 pp
- t: −1.8842
- p: **0.0597**
- 95% CI: **[−4.6317 pp, +0.0928 pp]**

### Moving-block bootstrap
Frozen implementation:
- block length: 20 observations
- resamples: 10,000
- RNG seed: 20261102

Result:
- bootstrap mean DELTA: −2.1902 pp
- 95% CI: **[−4.4232 pp, +0.1384 pp]**

The interval still crosses zero. Under the preregistered rule, that prevents `CONDITIONING_ESTABLISHED`.

## 7. Temporal stability audit

No retuning was performed.

- 2018–2022 DELTA: **−2.8206 pp**
- 2023–2026 DELTA: **−1.2115 pp**

Both subperiods have the same negative sign as the full sample. The effect is smaller in the later period but does not reverse sign.

## 8. Frozen conclusion

### Formal verdict: `INCONCLUSIVE`

Why not `CONDITIONING_ESTABLISHED`?
- temporal sign consistency passes;
- observed magnitude is economically nontrivial;
- but the preregistered 95% moving-block-bootstrap interval includes zero.

Why not call it useless?
- the point estimate is large (−2.27 pp);
- the sign is stable in both frozen temporal halves;
- the raw structure is coherent: stress raises the whole U100 future return much more than it raises the Top-5 relative edge.

Therefore the truthful conclusion is:

> **Market State is a plausible conditioning variable for future Selection-Core research, but this first clean benchmark test does not yet establish the effect at the preregistered confidence gate.**

It would be wrong to promote a normal-state-only selector, suppress selection in stress, or create state-specific experts from this result alone.

## 9. Authority boundary

This result grants:
- no BUY/SELL authority;
- no exposure rule;
- no state-specific threshold;
- no expert routing;
- no production promotion;
- no capital authority.

If state-conditioned Selection Core research proceeds, it must be a separate clean preregistered path with untouched OOS/prospective validation. This result may be used only as prior evidence that the conditioning question is worth testing, including its null-risk and uncertainty.
