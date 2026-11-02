# HENGCE Market Environment Observation — S3 Build Receipt

Date: 2026-11-02 (Asia/Taipei)  
Project: `research/market_state_observation_20261102`  
Schema: `HENGCE_MARKET_ENVIRONMENT_OBSERVATION_S2_V1`  
Status: **DETERMINISTIC NON-PREDICTIVE MATRIX BUILD PASS**

## Output
Artifact: `HENGCE_MARKET_ENVIRONMENT_OBSERVATION_MATRIX_V1.csv`

- rows: 2,142
- columns: 80
- first market event date: 2018-01-02
- last market event date: 2026-10-22
- first observation date: 2018-01-03
- last observation date: 2026-10-27
- output SHA256: `f547cb6591f6027f34aa85f2d8d83ff51d9ea3d1355a5346dc13408900a7ce4e`

## Determinism
The final merge was executed twice from the same frozen core and flow sidecar.

- run 1 SHA256: `f547cb6591f6027f34aa85f2d8d83ff51d9ea3d1355a5346dc13408900a7ce4e`
- run 2 SHA256: `f547cb6591f6027f34aa85f2d8d83ff51d9ea3d1355a5346dc13408900a7ce4e`
- byte comparison: PASS

`DETERMINISM_PASS = true`

## Source composition
Core price/EOD source: TWSE electronics yearly archives 2018–2026, including TAIEX trading sessions and corporate-action reference files.

Core-only matrix SHA256:
`47e9e538625b83af751138fd683a4ff975ed3d147943fb700f258e16ab0d373a`

Institutional-flow sidecar SHA256:
`511f69347bda6f1692bb0d61f6975da4c8c44e707bbc37649b07306685ad2070`

T86 flow:
- 2023–2025 canonical source only;
- 723 observation rows pass the frozen 95% date-cross-section coverage gate;
- first accepted flow event date: 2023-01-03;
- last accepted flow event date: 2025-12-31;
- Foreign / Trust / Dealer primitive channels remain separate;
- `TotalNet` is not an independent channel.

## Explicit UNKNOWN fields at this stage
- margin / margin-short frozen metrics: UNKNOWN pending revision-safe continuous history;
- attention/disposition frozen metrics: UNKNOWN pending official-history ingestion;
- TDCC: sparse sidecar only, not continuous daily core;
- external/derivatives: deferred secondary sidecar.

## Anti-leakage audit
Forbidden-token/output audit: PASS.

The matrix contains no:
- forward return;
- future drawdown;
- future volatility;
- target label;
- alpha;
- P&L;
- buy/sell/hold action;
- stock rank;
- optimized market-state/cluster label;
- performance-selected horizon.

## Important provenance boundary
The 2018–2026 EOD source archives are official historical date-valued data acquired retrospectively. They are not proof of original first-seen timestamps. Accordingly the matrix labels the core reconstruction as `RETROSPECTIVE_OFFICIAL_DATE_VALUE` and uses a conservative next-session-open observation anchor rather than pretending those files were captured in real time historically.

## Performance engineering note
A monolithic build that held the full wide price/synchronization matrices and the 134MB institutional file together exceeded the execution budget. The formulas were **not changed**. The implementation was separated into:
1. frozen EOD core builder;
2. T86 flow sidecar builder;
3. deterministic date-key merge.

This is an implementation change only; S2 formulas and quality gates remain unchanged.

## Reproducibility code authority
Exact builder scripts are preserved in the canonical Library project folder with hashes:
- `build_observation_matrix.py`: `f9c596a6afd1dbbcc6d104dd12f2c50bfe0925466ab89ff16c87fecc44c965f9`
- `build_flow_sidecar.py`: `dfa41fc18b0c2abcaf99ae04ba96c583e607f057e083e875ceaead705d942709`
- `merge_flow_sidecar.py`: `6f54c9f387c7d4a3a106282e86eee05817b416dbc0c829006298727cb6074e1d`

## Authority consequence
This receipt authorizes **descriptive inspection of contemporaneous environment dimensions only**.

It does not authorize market-state clustering/classification, risk-on/risk-off labels, predictive thresholds, forward-return tests, Selection Core interaction tests, backtests/tuning, or model/candidate promotion.

The next clean research action is descriptive structure audit: missingness, internal redundancy, contemporaneous divergence and clock-age behavior, without future outcomes.
