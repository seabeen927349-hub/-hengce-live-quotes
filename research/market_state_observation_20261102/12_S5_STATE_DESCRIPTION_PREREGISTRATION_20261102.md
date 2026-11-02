# HENGCE Market Environment Observation — S5 State-Description Preregistration

Date: 2026-11-02 (Asia/Taipei)
Project: research/market_state_observation_20261102
Input artifact: HENGCE_MARKET_ENVIRONMENT_OBSERVATION_MATRIX_V3.csv
Input SHA256: 2e9783338e24a1f2fd5303780750b8c269316265b4ea394f1dc8e4d3ca831755

## Purpose
Identify whether the contemporaneous observation vector contains recurrent, internally coherent market-environment structures. This is a non-predictive state-description exercise only.

## Hard prohibitions
No forward returns, future drawdowns, future volatility, Selection Core outcomes, P&L, BUY/SELL/HOLD labels, predictive thresholds, or performance-based state selection may be inspected or used.

## Primary sample
Use observations with all preregistered core features present. No row may be removed based on any future outcome. Initial rolling-window warm-up is excluded automatically by complete-case eligibility.

## Frozen core feature set
One descriptive primitive per major environment dimension, plus equal-weight path to preserve index-vs-cross-section divergence already established in S4:
1. TAIEX_R20 — cap-weighted market path
2. ELEC_EW_R20 — electronics equal-weight path
3. ELEC_ADV_DEC_20 — breadth
4. TAIEX_DD60 — drawdown state
5. TAIEX_RV20 — market realized volatility
6. ELEC_XS_MAD_1 — cross-sectional dispersion
7. ELEC_VALUE_RATIO20 — electronics activity / turnover intensity
8. ELEC_VALUE_TOP10_SHARE — trading concentration
9. ELEC_SYNC20 — cross-sectional synchronization

No flow, margin, attention, TDCC or derivatives variable enters the primary clustering because their continuous historical coverage is shorter. Those legs may only be used afterward for contemporaneous characterization where available.

## Transformation
Each frozen core feature is transformed with RobustScaler: subtract sample median and divide by interquartile range. No winsorization, clipping, tail deletion, or target-dependent transform is allowed.

## State discovery algorithm
KMeans with random_state=20261102 and n_init=100.
Candidate K = 2,3,4,5,6,7,8.

## K-selection rule
A candidate is admissible only if:
- smallest cluster share >= 5% of eligible observations; and
- every cluster appears in at least 6 distinct calendar years.

Among admissible candidates, select the K with highest silhouette score. If two candidates are within 0.02 silhouette points, choose the smaller K. Calinski-Harabasz and Davies-Bouldin are audit diagnostics only and cannot override this rule.

## Stability audit
After selecting K, rerun clustering across fixed seeds {20261102, 101, 202, 303, 404}. Map labels to the reference solution by maximum centroid similarity and report Adjusted Rand Index. Median ARI >= 0.80 is required for a stable descriptive solution. If stability fails, result is FAIL / NO_STABLE_STATE_PARTITION.

## State naming
Names are assigned only after clustering, based on centroid signs/magnitudes in the frozen contemporaneous features. Names must be descriptive, not predictive: examples such as BROAD_ADVANCE, NARROW_ADVANCE, STRESS, QUIET_CONSOLIDATION are allowed only if supported by centroid structure. Bullish/bearish outcome claims are prohibited.

## Auxiliary contemporaneous characterization
Where available, official Foreign/Trust/Dealer flow metrics and revision-safe 2026 margin/short metrics may be summarized by state. These variables do not alter cluster membership, K, scaling, or names.

## Deliverables
- cluster-selection diagnostics for K=2..8
- selected K or explicit failure
- state centroid profile in original units and robust z-units
- calendar-year recurrence
- episode-length descriptive persistence
- auxiliary flow/margin characterization where data coverage permits
- explicit statement that no forward outcome was viewed
