# HENGCE Escape 2026 read-only historical replay — 2026-11-04

**Authority:** RESEARCH_SHADOW_ONLY / FORMAL_ESCAPE_BLOCKED / TRADING_AUTHORITY_NONE. Main, original historical mother, EOD and frozen Escape contract are unchanged. The validated scope is **2026-01-02 through 2026-10-27**, not November 4.

## Executed evidence

1. Read canonical Library `/HENGCE_CANONICAL/HENGCE_2026_HIST_MOTHER.csv` (version 16, 79,893,881 bytes) directly. SHA256 `6f7494b46af07a11f68429981b3ec666ad0a520ed9b51ae0150f4c34435639e7`; exact match to `HENGCE_HIST_MOTHER_INCREMENTAL_RECEIPT_20261103.json`. Rows: **1,026,627**. Historical mother latest date: 2026-11-03.
2. Read Library `/HENGCE_CANONICAL/HIST_SOURCE_2018_2026_20261027/TWSE_ELECTRONICS_2026.zip`, internal `electronics_2026.csv`. Internal archive CSV SHA256 `76a7febdda2887672c5bc707e8f2d43cfa3cdcb60060bda80b0da2806e8fc635`. **195** archived trading sessions, **88,901** archive price rows, of which **218** preferred-share/non-four-digit rows excluded, leaving **88,683** electronic ordinary-security rows. Daily E cohort counts: **452–459**.
3. Read-only cross-validation with mother, excluding nonordinary securities: 0 cross-source *closing price* differences; **494 electronic rows with share-volume differences and 494 rows with turnover differences**, concentrated on **2026-10-08 (457)**, **2026-10-21 (14)**, **2026-10-22 (23)**. All source values remain unchanged. The cause and version timeline of these differences are **unverified**.
4. Computed 17 frozen-name candidate histories without zero-filling missing institutional or margin fields. At 2026-10-27, **16/17** were nonnull; `vulnerability_leverage_score_raw` was null. Across 195 sessions, **0** had fully complete electronics margin coverage (minimum 96.696%, mean 97.796%, maximum 98.904%). Full **17/17 past-40 baseline-ready days: 0**. **16/17 past-40 baseline-ready days: 125**, but these are not formally admitted days.
5. Compared a separately implemented full read-only source replay (`replay_2026_shadow.py`) against a second 2026 replay (`escape_replay_pipeline.py`): **all 17 names have identical null masks; all 16 calculable series match within absolute 1e-8** on all 195 days. Also reran the second pipeline only through **2026-09-30 (179 sessions)**; all 17 past values match the 195-day replay, showing no future-session dependence in this test.
6. Existing six research-adapter synthetic unittests ran successfully (6/6). These do not replace independent official golden-formula or cross-cycle out-of-sample validation.

## Exploratory component event diagnostic — NOT an Escape detector output

One onset per run of persistent adverse events; past 60 eligible history sessions with minimum 40 prior observations, >=90th adverse-percentile event, 3/5 persistence; first 20 sessions after a discrepant archive day excluded. The data source/contract gates are STILL FAIL. Event-level mean forward returns of chained equal-weight electronic daily returns are **not investment strategies**.

| Component | Eligible onset dates | 5-day events | Mean next-5-day return | Mean next-10-day return | Mean next-20-day return |
| --- | --- | ---: | ---: | ---: | ---: |
| TotalNet relative outflow | 2026-06-05; 2026-07-21; 2026-08-25 | 3 | -2.05% | +0.86% | +2.81% |
| Foreign relative outflow | 2026-06-17; 2026-08-25 | 2 | +2.61% | +1.37% | -2.75% |
| Trust relative outflow | 2026-06-03 | 1 | -8.15% | -2.83% | -0.98% |
| Dealer relative outflow | 2026-07-14; 2026-07-31 | 2 | +1.62% | +0.23% | +5.35% |

Small, correlated episodes; **no verified predictive power**. No canonical Escape alarm, sensitivity, specificity, accuracy or sell signal can be claimed. No out-of-sample test has been completed.

## Hard blockers / remediation

- `PIT_U_SECURITY_STATUS_NOT_INDEPENDENTLY_CONFIRMED`: 2026 U currently proxied from as-of price rows, not independently certified listing/security registry.
- `HISTORICAL_SOURCE_REVISIONS_UNRECONCILED`: volume/turnover mismatch on 3 dates; versioned source reconciliation required.
- `MARGIN_FULL_COHORT_INCOMPLETE`: null sector balances cannot be silently converted into zero. Separately audit non-marginable securities/eligibility before adjusting the denominator, and preserve the locked formula.
- `NO_17_OF_17_BASELINE`: cannot pass 40-observation histories for all 17 inputs; formal detector must refuse admission.
- `NO_CROSS_CYCLE_OOS_VALIDATION`: no causal lead-time, false-positive, or regime-generalization claims.
- 2026 E archive ends 2026-10-27, so **no** November 3/4 PIT E proof was established from this archive.

## Reproduction provenance

Canonical mother and original electronics archive are separately owned **Library source objects** rather than committed GitHub assets; do not create copies of the formal mother or overwrite its hash. Supporting local artifacts in this conversation: `escape_replay_pipeline.py`, `shadow_flow_diagnostic.py`, `validation_summary.json`, `historical_17_metric_research_shadow.csv`, `flow_component_exploratory.json`, `fail_closed_detector_packet.json`. Existing repo producer: `research/escape_dual_source_20261104/metric_producer.py` (patched fail-closed, original frozen detector untouched).

The branch is research-only and must not be merged into formal authority solely because computation runs or a provider reports complete intraday snapshots.
## Cross-cycle feasibility audit (new check)

The 1,026,627-row, hash-matched historical mother includes daily price rows back to **2018**, but **2018–2025 have ZERO nonnull records** in `ForeignNet`, `TrustNet`, `TotalNet` and `Margin_MarginBalance`. Verified per-year mother row counts: 2018 98,125; 2019 97,413; 2020 99,088; 2021 99,726; 2022 102,473; 2023 101,024; 2024 105,016; 2025 107,709. The 2026 records have 213,488 nonnull TotalNet rows and 209,196 nonnull margin rows among 216,053 dated price rows. Consequently **all-years full-17 Escape OOS backtesting is NOT runnable from this mother**, notwithstanding the existence of separately archived 2018–2025 electronics classifications. This is a material DATA_BLOCK, not an unexecuted future promise. Next admissible resolution requires actual versioned pre-2026 institutional/margin history and independently validated PIT U/E membership; do not backfill zeros or promote price-only proxies as Escape detection.
