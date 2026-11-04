# HENGCE IF-10 — public historical announcement source capability, bounded audit
Date: 2026-11-04 (Asia/Taipei)
Status: **DATA_BLOCKED / NO_ALPHA_TEST / NO_TRADING_AUTHORITY**
Branch: `research/if10-source-capability-audit-20261104`; isolated from frozen `research/selection-core-rebuild-20261031`.
This is a **source-access and PIT-vintage audit only**, not a new model or forward-return analysis. The previously frozen IF-10 decision remains authoritative: `HENGCE_IF10_EVENT_AUDIT_DATA_BLOCKED_20261031.json`. No earlier frozen strategy, trading engine, or Canonical data modified.

## Bounded question
Can **now-accessible, reproducible** records provide company-level listed-electronics structured announcements for 2018–2026 with (i) publication time, (ii) original historical content/vintage, (iii) corrections and withdrawals, (iv) sufficiently complete issuer-date coverage? Do not read stock returns. At most four source types checked, no retry loops.

## Checks and concrete evidence
1. **Official TWSE OpenAPI**: documented endpoint `GET https://openapi.twse.com.tw/v1/opendata/t187ap04_L`, **上市公司每日重大訊息**. Government dataset `https://data.gov.tw/en/datasets/18415` describes fields *Date of Issue*, *Date of speech*, *Time of speech*, *Company code*, *subject*, *fact occurrence date*, and *Description*, updated daily. Documentation proves a daily snapshot source with timestamp fields, **not an immutable 2018–2026 original-vintage backfile**. The single live URL retrieval was inaccessible from both web (unreachable) and TinyFish (`target_unreachable`). **No actual source rows were fetched or archived in this audit**.
2. **Official MOPS**: historical company/year search documented by TWSE/MOPS; reproducible example query `https://mops.twse.com.tw/mops/web/t05st01?step=1&firstin=true&year=113&co_id=2330`. Exact live query via TinyFish returned `timeout`; web reader could not access it. Published help pages show the search UI, **but do not establish a machine-retrievable bulk history or original pre-correction versions**. No event rows fetched.
3. **Third-party archival repository**: `0301kenny/wfnt-snapshot-data`, main commit `53bd579d1062a39fec9703aa0bd2ade64e0d23d4`, advertises daily TWSE material-information raw snapshots in README. Inspected complete `GET /git/trees/main?recursive=1` response `truncated=false`. Actual tracked main tree contains `scripts/`, `.github/`, reports, etc., **no `data/raw` or `data/manifest.json`**; direct contents requests for each returned GitHub 404. The repository is **not a usable downloadable original-event dataset via its tracked main branch** at this commit. This does not establish that snapshots never existed elsewhere.
4. **FinLab commercial dataset**: `https://finlab.finance/data/important-announcements` advertises 2006–2026 material announcements with event timestamps and contents, current daily refresh, with newer history tied to a paid tier. Website claims existence/coverage; **no raw rows, original historical versions, license, or user entitlement were verified**. Cannot treat marketing claims as authoritative PIT evidence or assume account access.

## Decision and significance
**IF10_HISTORICAL_PIT_ARCHIVE_ADMISSIBLE = NO; outcome = DATA_BLOCKED.** This does *not* say the structured-event economic hypothesis is false. It says this bounded source audit did not prove original-time/version-complete input data needed to test it. No return inspection; no event-timing proxy or later-edited text used as if originally public; no made-up data or retrospectively optimized selection rule.

## Stop / next admissible step
Do not re-run these blocked URL probes repeatedly or build event/price-based classifier. A future *separate* source-acquisition iteration is justified only by a concrete new access path for timestamped original event snapshots (including revisions), publisher file or verified archived dataset. Once a source is truly accessible, first archive exact raw bytes, acquisition UTC/Taipei timestamp, sha256, provider, dataset query, pagination/coverage count; obtain immutable first-public-time and correction lineage before mapping to signal dates. Re-read raw evidence and pre-register a distinct economic hypothesis and bounded test *before* attaching any future returns. If no such source emerges, retain DATA_BLOCKED.

## Sources and reproducibility links
- TWSE Swagger: https://openapi.twse.com.tw/
- Government listing: https://data.gov.tw/en/datasets/18415
- MOPS historical information: https://mops.twse.com.tw/
- Archived repository: https://github.com/0301kenny/wfnt-snapshot-data/tree/53bd579d1062a39fec9703aa0bd2ade64e0d23d4
- Third-party commercial dataset description: https://finlab.finance/data/important-announcements
- Prior frozen IF10 decision: `research/selection_core_rebuild/HENGCE_IF10_EVENT_AUDIT_DATA_BLOCKED_20261031.json` from `research/selection-core-rebuild-20261031`.
