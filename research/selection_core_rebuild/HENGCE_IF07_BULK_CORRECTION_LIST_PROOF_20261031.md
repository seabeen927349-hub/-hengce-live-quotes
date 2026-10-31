# HENGCE IF-07 — Official Quarterly Correction-List Capability Proof

Date: 2026-10-31  
Branch: `research/selection-core-rebuild-20261031`  
Scope: correction-source engineering only  
Forward returns inspected: `NO`  
Trading / production authority: `NONE`

## Official route

MOPS endpoint:
`https://mopsov.twse.com.tw/mops/web/ajax_t56sb31_q1`

Quarter query POST fields used:
- `step=1`
- `firstin=ture`
- `off=1`
- `isQuery=Y`
- `TYPEK=sii`
- `year={ROC year}`
- `season={01..04}`

## Reproducible control probe

Workflow run: `41174729512`  
Job: `124459832502`  
Script: `research/selection_core_rebuild/if07_bulk_correction_probe.py`

Pre-return controls:
1. known corrected case `2464` 2024Q2 must be present;
2. known electronic-book exact-`無` control `2330` 2023Q1 must not be present.

Observed:
- 2023Q1: HTTP 200, 66 unique issuer codes parsed, `2330` absent;
- 2024Q2: HTTP 200, 60 unique issuer codes parsed, `2464` present;
- no security/rate-limit block in either query.

Examples in the returned official rows contain issuer, correction date, report type and correction description.

## Verdict

`MOPS_QUARTERLY_CORRECTION_LIST_CAPABILITY = PASS`

This proves a scalable official negative-list source for whether a company-quarter appears in the MOPS financial-report correction query.

## Governance boundary

This proof does **not yet** silently replace the frozen implementation contract's rule requiring electronic-book `財務報告更(補)正 == 無`.

Before the quarterly negative-list may become an equivalent operational correction gate, a separately persisted pre-return engineering source-equivalence amendment must specify and freeze the exact mapping. Until then:
- this source is capability evidence only;
- it may not increase sample size by bypassing an unresolved metadata gate;
- no return may be opened because of this result alone.
