# HENGCE Selection Null Baseline — 2026-11-04 Source Audit

**Status: SOURCE_INTEGRITY_PASS; PIT_CAUSALITY_NOT_CERTIFIED; PERFORMANCE_TEST_NOT_OPENED; TRADING_AUTHORITY_NONE.**

Independent research branch from main `b53e5fd08755f0b4b3e6e640fabb85c5fad60e06`. Selection Core's independently governed original research branch and all canonical objects remain unchanged.

## Frozen evaluation contract

Retain `/HENGCE/Research Outputs/SELECTION_CORE_REBUILD/HENGCE_SELECTION_CORE_NULL_BASELINE_CONTRACT_V1_20261031.json`:
- N0: same-day PIT-electronics eligible-cohort equal-weight reference.
- N1: past-20-session momentum TopK, identical cohort and candidate date.
- N2: past-5-session reversal BottomK, identical cohort and candidate date.
- N3: 10,000 paired random k-name draws, seed 20261031.
- Same dates, same selected count, same costs (40bp roundtrip) and next-TWSE-open entry; frozen horizons 5/10/20/40/60 days. No forward returns may be exposed before execution/missing/overlap/corporate-action conventions are frozen.
- These are null comparisons; any standalone monthly Top5 finite-capital illustration, if subsequently specified, is an **independent experiment**, never a retroactive change to the existing Null Baseline Contract.

## Data explicitly inspected — Library archive files

Path `/HENGCE_CANONICAL/HIST_SOURCE_2018_2026_20261027/TWSE_ELECTRONICS_<YEAR>.zip`. Nine 2018–2026 bundles independently contain `electronics_<YEAR>.csv`, `trading_sessions_<YEAR>.csv` (including contemporaneous TAIEX prices), `corporate_actions_<YEAR>.csv`, and `MANIFEST.json`.

| Year | Sessions | 4-digit electronics candidate rows | Missing open/close | Corporate-action events |
| --- | ---: | ---: | ---: | ---: |
| 2018 | 247 | 98,125 | 244 | 308 |
| 2019 | 242 | 97,413 | 255 | 319 |
| 2020 | 245 | 99,088 | 151 | 324 |
| 2021 | 244 | 99,726 | 152 | 353 |
| 2022 | 246 | 102,473 | 143 | 373 |
| 2023 | 239 | 101,024 | 58 | 377 |
| 2024 | 242 | 105,016 | 76 | 357 |
| 2025 | 243 | 107,709 | 137 | 385 |
| 2026 to Oct 27 | 195 | 88,683 | 77 | 378 |
| **Total** | **2,143** | **899,257** | **1,293** | **3,174** |

**Integrity checks:** 27/27 internal archive files match source MANIFEST byte size and SHA-256; 0 duplicate date/ticker keys in annual price panels. All 2,143 session rows have nonnull TAIEX price index. Corporate action types: 2,894 dividend (`息`); 167 rights (`權`); 113 combined (`權息`). Full source volume 899,475 rows including 218 other-than-four-digit candidate rows. Four-digit identifier **does not establish PIT common-share security eligibility**.

Machine-readable local receipts:
- `HENGCE_SELECTION_BASELINE_SOURCE_AVAILABILITY_20261104.json`, SHA256 `6f7b9c5e5ba230f9c2373973cc342e9aeeeec69feded05c5d647a7f67ad34dba`.
- `HENGCE_SELECTION_BASELINE_SOURCE_INTEGRITY_20261104.json`, SHA256 `4f718246f8181e2100dca89300c4e3d36b2dcd986e53502c5932ae43a55c5b0f`.

## Go/no-go gates before calculating benchmark PnL

1. Independent PIT security eligibility, historical ordinary status, delisting survival and official electronics classification provenance: **NOT CERTIFIED** (annual archived membership can be inspected but does not establish historical security status).
2. Corporate actions (especially rights and combined rights/dividends) need explicit shareholder-economic return, share-count and cost-basis treatment: **NOT CERTIFIED**. Unadjusted close-to-close returns may understate/overstate PnL.
3. Versioned source-revision consistency, historical execution-open, locked missing-price handling and boardlot/capital accounting: **NOT CERTIFIED**. 2026 electronic volume/turnover archive differences around Oct 8/21/22 previously observed; no silent overwrite.
4. Exploratory signals may be computed with a clear research label, but **no standalone 2018–2026 performance PASS, Selection Core alpha, formal trade signal or automatic capital authority is established**.

The first stage is complete: **SOURCE DATA PRESENT + VERIFIED INTEGRITY; OUTCOME VALIDATION UNOPENED**. Stop rather than fabricate missing PIT/corporate-action assumptions. Any subsequent experiment must retain these limitations in every result.
