# HENGCE Market Environment Observation — S4 Descriptive Structure Audit

Date: 2026-11-02 (Asia/Taipei)  
Input: `HENGCE_MARKET_ENVIRONMENT_OBSERVATION_MATRIX_V1.csv`  
Input SHA256: `f547cb6591f6027f34aa85f2d8d83ff51d9ea3d1355a5346dc13408900a7ce4e`  
Status: **NON-PREDICTIVE DESCRIPTIVE AUDIT COMPLETE**

## 1. Scope lock
This audit asks only whether the frozen observation vector contains materially distinct **contemporaneous** structure. It inspects no forward return, future drawdown/volatility, Selection Core performance, trade P&L, optimized state label or predictive threshold.

Primary descriptive sample: 2018-04-01 through 2025-12-31. 2026 is excluded from electronics cross-sectional comparisons because the current 2026 source archive fails the frozen data-quality gate for material fields.

## 2. TAIEX path and electronics breadth are related but not identical
On 1,890 valid observation dates:

- `corr(TAIEX_R20, ELEC_EW_R20) = 0.8632`
- `corr(TAIEX_R20, ELEC_ADV_DEC_20) = 0.7854`
- TAIEX 20-session path positive while electronics 20-session breadth negative: **294 / 1,890 = 15.56%**.
- TAIEX 20-session path negative while electronics 20-session breadth positive: **110 / 1,890 = 5.82%**.
- TAIEX and electronics equal-weight 20-session paths have opposite signs: **335 / 1,890 = 17.72%**.

Year-level narrow-up incidence (`TAIEX_R20>0` and `ELEC_ADV_DEC_20<0`):

| Year | Valid days | Narrow-up days | Share |
|---|---:|---:|---:|
| 2018* | 189 | 22 | 11.64% |
| 2019 | 242 | 32 | 13.22% |
| 2020 | 245 | 26 | 10.61% |
| 2021 | 244 | 32 | 13.11% |
| 2022 | 246 | 11 | 4.47% |
| 2023 | 239 | 20 | 8.37% |
| 2024 | 242 | 77 | 31.82% |
| 2025 | 243 | 74 | 30.45% |

*2018 starts April after initial rolling-window warmup.

This establishes only that index path and internal electronics breadth cannot be treated as interchangeable descriptions of the current environment.

## 3. Divergence can persist, but rolling-window overlap matters
The 294 narrow-up observations form 91 contiguous episodes:
- median: 2 sessions
- mean: 3.23
- 75th percentile: 4
- maximum: 17 sessions

Maximum episode: 2025-10-02 through 2025-10-29. Because the observation uses overlapping 20-session windows, episode length is mechanically smoothed. It is not a predictive duration claim.

## 4. Internal structure differs inside positive-index environments
Compare only contemporaneous sets:
- narrow-up: `TAIEX_R20>0` and `ELEC_ADV_DEC_20<0` (294 observations)
- broad-up: `TAIEX_R20>0` and `ELEC_ADV_DEC_20>0` (865 observations)

| Metric | Narrow-up | Broad-up |
|---|---:|---:|
| `ELEC_VALUE_TOP10_SHARE` | 0.4459 | 0.4175 |
| `ELEC_SYNC20` | 0.5235 | 0.4527 |
| `ELEC_XS_MAD_1` | 0.00887 | 0.00873 |
| `ELEC_VALUE_RATIO20` | 1.0076 | 1.0343 |
| `ELEC_TRADES_RATIO20` | 0.9959 | 1.0407 |

No causal or predictive interpretation is authorized. The conclusion is only that periods with the same positive TAIEX-path sign can have different breadth, turnover concentration, synchronization and activity structure.

Selected contemporaneous correlations:
- `corr(ELEC_VALUE_RATIO20, ELEC_TRADES_RATIO20) = 0.852`
- `corr(ELEC_SYNC20, ELEC_SYNC60) = 0.678`
- `corr(ELEC_SYNC20, ELEC_ADV_DEC_20) = -0.545`
- `corr(ELEC_VALUE_TOP10_SHARE, ELEC_ADV_DEC_20) = -0.414`

S2 remains frozen; no metric is dropped because of correlation.

## 5. Institutional-flow channels cannot be collapsed without information loss
For 2023–2025, 723 T86 observation dates pass the frozen 95% cross-sectional coverage gate.

Net-volume-share correlations:
- Foreign vs Trust: **-0.191**
- Foreign vs Dealer: **+0.414**
- Trust vs Dealer: **-0.081**

All three channels have the same sign on only **30.43%** of valid dates.

Pairwise opposite-sign frequency:
- Foreign vs Trust: **54.50%**
- Foreign vs Dealer: **35.27%**
- Trust vs Dealer: **49.38%**

This supports retaining official channels as separate observable primitives. It does not validate investor identity, motive, information superiority or any smart-money label.

Within 2023–2025, median net-volume-share observations were:

| Channel | Narrow-up (n=171) | Broad-up (n=321) |
|---|---:|---:|
| Foreign | -0.00223 | +0.00645 |
| Trust | -0.000138 | +0.00000376 |
| Dealer | +0.00158 | +0.00284 |

These are simultaneous associations only; no next-period return is inspected.

## 6. 2026 source defect: fail closed
Example 2026-10-15 in the yearly electronics source archive:
- electronics rows: 458
- missing OHLC: 26
- missing `volume_shares`: 457 / 458
- missing `turnover_ntd`: 458 / 458
- missing `trades`: 458 / 458

Missing OHLC names include major electronics constituents. The frozen 95% gate therefore correctly marks affected 2026 observations `UNKNOWN`.

A separate Library `HENGCE_2026_HIST_MOTHER.csv` matches 457 / 458 date-correct electronics members on that date with complete OHLC/volume/turnover. However prior HENGCE evidence audit states the historical full-mother/raw-response/receipt chain is absent and first-seen/publication time is not preserved.

Decision:

`2026_SOURCE_REPAIR_CANDIDATE = FOUND_BUT_NOT_AUTHORIZED_FOR_SILENT_PATCH`

Do not lower the 95% gate. Do not silently blend this mother into the frozen archive. A separate lineage reconciliation is required before any repair is promoted.

## 7. Conclusion
The frozen observation vector contains demonstrably non-identical contemporaneous structure: index path != electronics equal-weight path; index path != breadth; breadth != turnover concentration; breadth != synchronization; and foreign/trust/dealer official flow channels are not one homogeneous series.

This justifies continuing the environment-observation research line. It does not establish predictive value or a market-state label.

## 8. Next clean actions
1. 2026 lineage-repair audit: authorize a source-backed patch or keep affected fields UNKNOWN.
2. Ingest official attention/disposition history under its post-close clock.
3. Build revision-safe leverage/short history or leave it UNKNOWN.
4. Only after observation completeness is acceptable may a separately preregistered state-description problem be considered. Predictive testing remains forbidden.
