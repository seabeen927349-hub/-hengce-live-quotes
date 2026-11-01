# HENGCE DSP / Loss Forensics — Actual-Availability Audit

Date: 2026-11-01
Preregistration authority: `91d785b9e9aaae1367bf1cbb8c73e61bb2c16e95`
Status: **DATA_BLOCKED / FORMAL FORWARD-LABEL EXECUTION NOT OPENED / NO TRADING AUTHORITY**

## 1. Audit question
Can historical `A_t` / `A_t1` be reconstructed as the true public availability/publication time of the exact TDCC ownership payload, and can every h=1 source-side component be assigned a point-in-time legal availability time without hindsight?

Answer: **not to the preregistered standard**.

## 2. Ownership payload: what is known
The existing Library artifact `current100_ownership_intervals_audit.csv` carries:
- `SnapshotDate`;
- `SourceTier`;
- `SourcePath`;
- `RawSHA256`;
- ownership values and integrity fields.

It does **not** carry `published_at`, `retrieved_at`, HTTP `Last-Modified`, response timestamp, or another contemporaneous official release timestamp.

For the 2026-04 through 2026-10 segment, many rows identify raw archive paths under:
`ownership/tdcc/backfill_candidate/wirelessr/YYYYMMDD/tdcc_ownership_4d.csv`.

This is enough to preserve source provenance and payload hashes, but not enough by itself to prove when the payload first became public.

## 3. Official TDCC semantics
Official TDCC shareholder-distribution history page:
`https://www.tdcc.com.tw/portal/zh/smWeb/qryStock`

It establishes that the observation is a weekly reference-date balance and provides historical queries. It does not expose a historical per-snapshot `published_at` timestamp that can be mapped to each 2026 observation used here.

Official open-data endpoint used by the archive:
`https://opendata.tdcc.com.tw/getOD.ashx?id=1-5`

The endpoint serves the current snapshot payload, but the historical response headers / first-publication timestamp for the 2026 snapshots were not preserved in the HENGCE dataset.

## 4. wirelessr archive: useful contemporaneous upper-bound evidence, not exact publication time
Public repo:
`https://github.com/wirelessr/tdcc-opendata-archive`

The repository's automation was created on 2026-05-04, before the formal OOS window. Its workflow schedules a daily fetch at 02:00 UTC / 10:00 Taiwan time and the downloader:
- requests the official TDCC current-week endpoint directly;
- writes the raw response bytes to `snapshots/YYYY/YYYY-MM-DD.csv`;
- skips if already archived;
- commits a newly observed snapshot.

Therefore a snapshot's first archive commit is strong evidence that **by that commit time** the official endpoint had exposed that payload.

It is **not** proof of TDCC's exact first-publication time. The archive checks periodically and GitHub Actions can start later than its nominal schedule. A first successful retrieval can lag the true TDCC publication by hours or days. It therefore supplies a conservative `first_observed_by_archive` timestamp, not the preregistered `A_t = earliest independently verifiable timestamp at which the exact payload first became publicly knowable`.

The historical pattern itself proves why a fixed +N rule is invalid. Examples:
- snapshot 2026-06-26 first archived 2026-06-27 05:45:13Z;
- snapshot 2026-07-09 first archived 2026-07-13 05:24:31Z;
- snapshot 2026-10-16 first archived 2026-10-17 06:21:50Z.

The complete OOS/next-confirmation manifest is stored in `ACTUAL_AVAILABILITY_PROVENANCE_MANIFEST_20261101.csv`.

## 5. Source-side daily data availability
The canonical `HENGCE_2026_HIST_MOTHER.csv` contains:
`Date,Ticker,Name,Volume,Turnover,Open,High,Low,Close,Margin_MarginBalance,ForeignNet,TrustNet,TotalNet`.

It contains no per-row or per-field `published_at` / `retrieved_at` timestamp.

Official TWSE evidence provides useful conservative timing constraints:
- individual-security three-institution trading file: 18:00 without block trades and 20:00 including block trades;
- margin-balance product: approximately 21:00 each trading day;
- TWSE rules require margin balances to be announced before the next business-day market open.

Sources:
- `https://eshop.twse.com.tw/zh/product/detail/c4c87ac184e44896a05fcab5a9d544ec`
- `https://eshop.twse.com.tw/zh/product/detail/388dd3a09824427d8c01a9d2b21e820b`
- `https://twse-regulation.twse.com.tw/TW/law/DOC01.aspx?FLCODE=fl007121&FLNO=69`

These constraints prevent treating the daily date as an intraday availability time. They do not repair the missing historical TDCC publication timestamps.

## 6. PIT market / sector / regime audit
Library search found research artifacts containing `Industry` and `MarketRegimeState`, but no authority was found that proves:
- each stock's sector membership was historically effective as of each h=1 date rather than later/current classification backfill; and
- the exact regime rule/state used for the requested residual adjustment has a frozen PIT provenance chain for all OOS rows.

Examples of found artifacts:
- `HENGCE_PERSISTENCE_MATCHED_CONTROL_20261005.csv` contains `Industry` by research event;
- `C_event_ledger.csv` contains `MarketRegimeState` / `RegimePersistence`.

Those are derived research artifacts, not a sufficient historical classification/source manifest. Under the preregistration, silent fallback to current-sector mapping or a newly invented regime rule is prohibited.

## 7. Why the audit fails the preregistered gate
The preregistration explicitly prohibits:
- snapshot reference date as a substitute for availability;
- fixed +N release assumptions;
- later pipeline file modification times;
- later-retrieved payloads without proof of when the exact version became publicly knowable;
- current-sector backfill.

The available evidence can establish conservative archive-observation times, but cannot reconstruct the exact historical TDCC `published_at` / earliest-public timestamp for the minimum formal sample. PIT sector/regime provenance is also incomplete.

Therefore the formal availability eligibility requirement is not met.

## 8. Formal decision
**Evidence status: `DATA_BLOCKED`.**

Consequences:
- event-level forward ownership labels were not opened for this new study;
- no Brier/log-loss/ECE recomputation was performed;
- no sensitivity/FNR or specificity/FPR was computed;
- no h=1 actual-publication latency distribution is claimed;
- Pass 4's earlier snapshot-reference-date h=1 result remains historical authority only and is not upgraded to actual-availability validation;
- production authority remains `NONE`.

This is a data-provenance failure, not evidence that the source-side mechanism is false. It also is not permission to rescue it with a weaker timestamp definition.