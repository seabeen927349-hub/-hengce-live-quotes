# HENGCE IF-07 — Bulk ZIP Member Timestamp Rejection

Date: 2026-10-31  
Branch: `research/selection-core-rebuild-20261031`  
Scope: PIT source engineering only  
Forward returns inspected: `NO`  
Trading / production authority: `NONE`

## Question

Can the per-member timestamp stored inside the official quarterly MOPS bulk iXBRL ZIP substitute for the company-specific TWSE electronic-report `上傳日期` required by the frozen IF-07 V0.1 preregistration?

## Reproducible probe

Workflow run: `41173941131`  
Job: `124457487552`  
Script: `research/selection_core_rebuild/if07_bulk_zip_timestamp_probe_v0_2.py`

Four pre-return control samples were compared against already verified official upload timestamps.

| Ticker | Period | Verified official upload | ZIP member timestamp | Result |
|---|---|---|---|---|
| 2330 | 2023Q1 | 2023-05-12 13:51:34 | 2026-08-27 02:30:26 | FAIL |
| 2454 | 2024Q2 | 2024-08-13 17:27:52 | unavailable in this probe due non-ZIP response | FAIL |
| 3037 | 2025Q3 | 2025-10-30 18:45:28 | unavailable in this probe due non-ZIP response | FAIL |
| 2303 | 2026Q2 | 2026-07-29 17:18:33 | 2026-10-31 02:32:22 | FAIL |

Observed deltas for successful ZIP-member reads:
- 2330 2023Q1: +103,898,332 seconds;
- 2303 2026Q2: +8,068,429 seconds.

These timestamps are consistent with later package rebuild/archive times, not original company filing availability.

## Verdict

`BULK_ZIP_MEMBER_TIMESTAMP_AS_UPLOAD_TS = FAIL`

Permanent consequence for IF-07 V0.1:
- ZIP member timestamps have zero PIT timing authority;
- they must not be used as `upload_ts`, as a proxy for `upload_ts`, or to resolve `signal_date`;
- bulk ZIPs remain valid only as accounting-file byte transport, subject to the separate timestamp and correction gates.

No forward-return data were used to reach this decision.
