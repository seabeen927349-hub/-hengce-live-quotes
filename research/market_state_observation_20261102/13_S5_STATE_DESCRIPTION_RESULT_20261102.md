# HENGCE Market Environment Observation — S5 State-Description Result

Date: 2026-11-02 (Asia/Taipei)  
Input: `HENGCE_MARKET_ENVIRONMENT_OBSERVATION_MATRIX_V3.csv`  
Input SHA256: `2e9783338e24a1f2fd5303780750b8c269316265b4ea394f1dc8e4d3ca831755`  
Preregistration: `12_S5_STATE_DESCRIPTION_PREREGISTRATION_20261102.md`  
Status: **PASS — TWO RECURRENT CONTEMPORANEOUS ENVIRONMENT STATES FOUND**

## 1. Hard boundary
This analysis inspected **no forward return, future drawdown, future volatility, P&L, stock rank, Selection Core outcome, or trading result**. State discovery used contemporaneous observation fields only.

Total V3 rows: 2,142.  
Complete eligible rows under the frozen 9-feature core: 2,083.  
Eligible date span: 2018-04-09 through 2026-10-27.

## 2. K-selection result

| K | Silhouette | Min cluster share | Min years | Admissible |
|---:|---:|---:|---:|:---:|
| 2 | 0.3896 | 17.71% | 8 | YES |
| 3 | 0.2053 | 9.55% | 7 | YES |
| 4 | 0.2133 | 7.97% | 7 | YES |
| 5 | 0.1744 | 7.01% | 7 | YES |
| 6 | 0.1704 | 3.98% | 6 | NO |
| 7 | 0.1772 | 3.98% | 4 | NO |
| 8 | 0.1819 | 1.92% | 4 | NO |

Under the preregistered rule, **K=2 is selected**. Its silhouette score (0.3896) is materially above every K=3..8 candidate. K=6..8 additionally fail the minimum cluster-share / recurrence admissibility gate.

The data therefore do **not** support forcing four, five, or more formal environment states at this stage.

## 3. Formal descriptive states

### State A — `DIFFUSE_NORMAL`
- observations: 1,714 (82.29%)
- median 20-session TAIEX path is positive;
- electronics equal-weight path and breadth are also positive;
- drawdown is shallow;
- realized volatility, dispersion and synchronization are materially lower than the stress state;
- turnover is less concentrated in the top 10 names.

### State B — `SYNCHRONIZED_STRESS`
- observations: 369 (17.71%)
- median 20-session TAIEX and electronics equal-weight paths are negative;
- breadth is strongly negative;
- 60-session drawdown is deeper;
- realized volatility and cross-sectional dispersion are higher;
- electronics move much more synchronously;
- top-10 turnover concentration is higher.

These names are contemporaneous descriptions only. They are not forecasts and do not mean BUY/SELL.

## 4. Median state profile in original units

| Metric | DIFFUSE_NORMAL | SYNCHRONIZED_STRESS |
|---|---:|---:|
| `TAIEX_R20` | 0.027535 | -0.053066 |
| `ELEC_EW_R20` | 0.028593 | -0.060342 |
| `ELEC_ADV_DEC_20` | 0.170854 | -0.621622 |
| `TAIEX_DD60` | -0.015465 | -0.095640 |
| `TAIEX_RV20` | 0.138086 | 0.264301 |
| `ELEC_XS_MAD_1` | 0.008850 | 0.011137 |
| `ELEC_VALUE_RATIO20` | 1.011589 | 0.973736 |
| `ELEC_VALUE_TOP10_SHARE` | 0.430138 | 0.466973 |
| `ELEC_SYNC20` | 0.490418 | 0.764994 |

The strongest separation is not just price direction. `SYNCHRONIZED_STRESS` combines weaker path, weaker breadth, deeper drawdown, higher volatility/dispersion, and much higher synchronization. This is a coherent market-internal structure rather than a single-index rule.

## 5. Recurrence across calendar years

| Year | DIFFUSE_NORMAL | SYNCHRONIZED_STRESS | Stress share |
|---:|---:|---:|---:|
| 2018 | 159 | 28 | 14.97% |
| 2019 | 229 | 13 | 5.37% |
| 2020 | 198 | 47 | 19.18% |
| 2021 | 206 | 38 | 15.57% |
| 2022 | 144 | 102 | 41.46% |
| 2023 | 239 | 0 | 0.00% |
| 2024 | 202 | 40 | 16.53% |
| 2025 | 208 | 35 | 14.40% |
| 2026 | 129 | 66 | 33.85% |

`SYNCHRONIZED_STRESS` appears in 8 of 9 calendar years represented in the eligible sample. 2023 has no formal stress-state observations under this partition. This satisfies the preregistered recurrence gate and shows the state is not a one-year artifact.

## 6. Algorithmic stability

Fixed-seed reruns at seeds 101, 202, 303 and 404 all produce:
- Adjusted Rand Index vs reference = **1.0000**

Median seed-stability ARI = **1.0000**, exceeding the preregistered 0.80 requirement.

### Leave-one-year-out structural audit
For each calendar year, that year was removed, K=2 was fit on all other years, then the omitted year was assigned and compared with the reference partition. No outcome variables were used.

| Held-out year | Rows | Agreement with reference partition |
|---:|---:|---:|
| 2018 | 187 | 97.86% |
| 2019 | 242 | 96.69% |
| 2020 | 245 | 98.78% |
| 2021 | 244 | 97.95% |
| 2022 | 246 | 93.50% |
| 2023 | 239 | 100.00% |
| 2024 | 242 | 99.59% |
| 2025 | 243 | 92.59% |
| 2026 | 195 | 97.44% |

Agreement range: **92.59% to 100.00%**.  
Median agreement: **97.86%**.

This materially strengthens the claim that the two-state geometry recurs across time rather than being created by one exceptional year.

## 7. Persistence

`DIFFUSE_NORMAL` episodes:
- count: 44
- median length: 9.0 eligible sessions
- mean length: 38.95
- maximum: 309

`SYNCHRONIZED_STRESS` episodes:
- count: 44
- median length: 3.5 eligible sessions
- mean length: 8.39
- maximum: 32

The transition audit is descriptive only:
- DIFFUSE_NORMAL remains DIFFUSE_NORMAL next eligible observation: 97.43%
- SYNCHRONIZED_STRESS remains SYNCHRONIZED_STRESS next eligible observation: 88.32%

These persistence numbers are **not** future-return probabilities.

## 8. Auxiliary contemporaneous flow / leverage characterization

These channels were excluded from clustering and cannot alter state membership.

2023–2025 official flow medians:
- Foreign net-volume share: DIFFUSE_NORMAL -0.002680; SYNCHRONIZED_STRESS -0.011410
- Trust net-volume share: DIFFUSE_NORMAL 0.001258; SYNCHRONIZED_STRESS 0.007972
- Dealer net-volume share: DIFFUSE_NORMAL 0.002092; SYNCHRONIZED_STRESS 0.000353

2026 revision-safe leverage medians where available:
- Margin 5-session log change: DIFFUSE_NORMAL 0.015877; SYNCHRONIZED_STRESS -0.016373
- Margin 20-session log change: DIFFUSE_NORMAL 0.044074; SYNCHRONIZED_STRESS -0.035380
- Margin-short 20-session log change: DIFFUSE_NORMAL 0.050902; SYNCHRONIZED_STRESS -0.094534

These are simultaneous associations only. They do not establish motive, causality, smart-money identity, or future direction.

## 9. Latest V3 observation

Latest eligible V3 observation: **2026-10-27**  
Assigned state: **`SYNCHRONIZED_STRESS`**

Contemporaneous values:
- TAIEX_R20 = -0.035785
- ELEC_EW_R20 = -0.016758
- ELEC_ADV_DEC_20 = -0.295154
- TAIEX_DD60 = -0.075892
- TAIEX_RV20 = 0.206731
- ELEC_XS_MAD_1 = 0.015180
- ELEC_SYNC20 = 0.522423

However, this point is **borderline**:
- sample silhouette = -0.0856
- distance to DIFFUSE_NORMAL centroid = 2.6790
- distance to SYNCHRONIZED_STRESS centroid = 2.4374

Therefore the correct descriptive statement is:

`2026-10-27 = SYNCHRONIZED_STRESS / BORDERLINE_LOW_CONFIDENCE`

It would be wrong to describe this as a deep or unambiguous stress-state observation.

The V3 matrix ends at 2026-10-27. This result must **not** be represented as a 2026-11-02 real-time state until the existing observation builder is advanced with already-canonical later data.

## 10. Formal conclusion

**PASS:** HENGCE can distinguish at least two recurrent contemporaneous market-environment structures using the clean observation layer.

What is established:
1. the partition is materially separated;
2. it is deterministic across seeds;
3. it recurs across calendar years;
4. leave-one-year-out reconstruction agrees 92.59%–100%;
5. the structure is multivariate, not merely TAIEX up/down.

What is **not** established:
- that either state predicts future returns;
- that a stress-state entry is a sell signal;
- that a normal-state entry is a buy signal;
- that two states are the final production taxonomy;
- that more granular sub-states are impossible.

No predictive gate is opened by this result.
