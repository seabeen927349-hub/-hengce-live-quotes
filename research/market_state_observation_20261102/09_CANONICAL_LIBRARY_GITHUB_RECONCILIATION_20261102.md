# HENGCE Market Environment Observation — Canonical Library / GitHub Reconciliation

Date: 2026-11-02 (Asia/Taipei)  
Project: `research/market_state_observation_20261102`  
Status: **RECONCILED / NON-PREDICTIVE AUTHORITY ONLY**

## 1. Why this receipt exists

The GitHub research branch reached `a03a445a1980265845596bc635128e97507c54d1` with `07_2026_DATA_LINEAGE_REPAIR_DECISION.md`, which correctly rejected silent repair from the Library candidate `HENGCE_2026_HIST_MOTHER.csv` because adequate lineage had not been established for that candidate.

The canonical Library project folder subsequently contained later repair artifacts:

- `04A_S2_V1_1_IMPLEMENTATION_REPAIR_AMENDMENT.md`
- `08_2026_NUMERIC_PARSER_REPAIR_RECEIPT.md`
- `HENGCE_MARKET_ENVIRONMENT_OBSERVATION_MATRIX_V2.csv`
- `OBSERVATION_MATRIX_MANIFEST_V2.json`
- `build_observation_matrix_v2.py`

This receipt reconciles those later canonical facts into GitHub so repo-only continuation does not incorrectly remain blocked on 2026 OHLC/volume/turnover.

## 2. What was actually wrong

The canonical official 2026 yearly archive was not fundamentally missing the relevant OHLC/volume/turnover data. Many valid official numeric strings contained thousands separators. The V1 builder used direct numeric coercion, so comma-formatted values became missing.

A second implementation defect coupled turnover coverage to missing trade-count coverage, causing valid turnover-based metrics to be suppressed when `trades` was absent.

S2 V1.1 repair therefore:

1. normalizes thousands separators before numeric conversion while preserving true blanks as missing;
2. applies the same sanitizer to all years;
3. separates `turnover_coverage_ratio` from `trades_coverage_ratio`;
4. gates turnover-based metrics only by turnover coverage and trade-count metrics only by trade coverage;
5. leaves the frozen 95% and 90% data-quality gates unchanged.

No future outcome was inspected to discover or justify this repair.

## 3. Source-lineage resolution

The later audit found the canonical official acquisition/audit package under:

`/HENGCE_CANONICAL/HIST_SOURCE_2018_2026_20261027/`

including `SOURCE_AND_AUDIT.zip` and `TWSE_ELECTRONICS_2026.zip`.

Therefore V2 repairs the existing official archive. It does **not** use `HENGCE_2026_HIST_MOTHER.csv`.

The candidate mother remains unauthorized as a source-lineage substitute. Its numerical completeness does not establish PIT authority, and its margin/flow fields receive no authority from this parser repair.

## 4. Canonical V2 validation facts

- Matrix: `HENGCE_MARKET_ENVIRONMENT_OBSERVATION_MATRIX_V2.csv`
- Schema: `HENGCE_MARKET_ENVIRONMENT_OBSERVATION_S2_V1_1`
- Rows: `2142`
- Columns: `82`
- SHA256: `15d7e652ce9d5004b928ce89b03e4774151829693296c40ca229d1aaf11345a7`
- Deterministic rerun SHA256: same value
- 2018–2025 common-field value changes versus V1: `0`
- 2026 event rows: `194`
- minimum 2026 price coverage: `0.993392070485`
- minimum 2026 range coverage: `0.995594713656`
- minimum 2026 turnover coverage: `1.000000000000`
- 2026 dates below frozen 95% price gate: `0`
- 2026 dates below frozen 95% turnover gate: `0`
- `ELEC_TRADES_RATIO20` non-null 2026 rows: `0 / 194`
- unlineaged candidate mother used: `false`
- forward-return columns: `0`
- forbidden-token audit: `PASS`

Example 2026-10-15:

- date-correct electronics universe: 458
- price/range valid: 457 / 458
- turnover valid: 458 / 458
- trades valid: 0 / 458
- turnover-based liquidity metrics: available under frozen gates
- trade-count-based liquidity metric: `UNKNOWN`

## 5. Supersedence rule

`07_2026_DATA_LINEAGE_REPAIR_DECISION.md` is not deleted or rewritten. It remains immutable audit history establishing the correct refusal to use an unlineaged candidate mother.

The later canonical parser-repair receipt supersedes only this operational conclusion from `07`:

> official 2026 OHLC/volume/turnover must remain blocked because the frozen archive is materially incomplete.

Current authority is instead:

- official 2026 **price/range/volume/turnover** data are usable where the repaired parser and frozen field-specific quality gates pass;
- 2026 **trade count** remains genuinely missing and trade-count-based metrics stay `UNKNOWN`;
- historical first-seen timestamps are still not preserved, so the conservative next-session-open reconstruction clock remains mandatory;
- no unlineaged candidate source is permitted to replace UNKNOWN fields.

## 6. S1 consequence

`S1_PIT_DATA_CAPABILITY = PASS_WITH_NARROWING` remains unchanged, but the narrowing is metric-specific rather than a blanket 2026 cross-sectional block.

Core EOD price/path, price breadth, daily volatility/range, turnover-based liquidity and price synchronization are eligible through 2026 under frozen gates. The major unresolved S1 capability gaps remain:

- continuous ownership/participation history;
- 2026 trade-count history;
- revision-safe continuous leverage/short history;
- official attention/disposition historical ingestion;
- full historical aggressive/passive microstructure;
- complete contemporaneous supply-chain graph;
- field-specific external/derivatives clock audit.

## 7. Boundary remains closed

This reconciliation does not authorize:

- forward-return inspection;
- future drawdown/volatility targets;
- state classification or clustering;
- state-return mapping;
- predictive thresholds;
- Selection Core interaction tests;
- backtesting or tuning;
- candidate/model promotion;
- capital authority.

Any later predictive question requires a separate preregistration and explicit authority.