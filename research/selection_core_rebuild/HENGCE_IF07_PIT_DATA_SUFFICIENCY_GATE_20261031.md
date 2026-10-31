# HENGCE IF-07 — PIT Data Sufficiency Gate

Date: 2026-10-31  
Branch: `research/selection-core-rebuild-20261031`  
Forward returns inspected: `NO`  
Trading / production authority: `NONE`

## Binary question

Can IF-07 be tested under a strict 2023–2026 Discovery / Validation design using point-in-time financial-report history without relaxing the PIT law?

## Verdict

`PASS — DATA SUFFICIENT`

`DATA_BLOCKED = NO`

No additional source-family search or timestamp-proxy research is authorized by this gate.

## Evidence already sufficient before this gate

1. Official TWSE electronic-report `t57sb01` exposes company-specific `上傳日期` to the second. Verified examples span the full intended research era:
   - 2330 2023Q1;
   - 2454 2024Q2;
   - 3037 2025Q3;
   - 2303 2026Q2.

2. Official MOPS financial reports contain the required consolidated balance-sheet, income-statement and cash-flow data, and the required accounting fields are machine-readable.

3. Official bulk iXBRL acquisition is available for accounting-file transport. Bulk ZIP member timestamps are explicitly rejected as PIT timestamps, but that does not impair the existence of the accounting history.

4. The official quarterly MOPS correction list is available and has passed pre-return control cases. Final exact `財務報告更(補)正 == 無` remains a company-quarter metadata gate where required by the frozen preregistration.

5. Canonical daily TWSE electronics archives provide the signal-date PIT universe authority. Annual ticker unions have zero formal PIT authority.

6. The invalid metadata-index V0.1 was an acquisition-method failure caused by rate limiting / transient transport errors. It is permanently forbidden as panel input, but it does not demonstrate provider-level historical-data absence.

## Strict PIT contract that is sufficient

For every company-event eventually evaluated:
- accounting values: official consolidated MOPS filing;
- availability time: exact official TWSE electronic-report `上傳日期` only;
- correction rule: frozen exact original-filing / correction contract, fail closed if unresolved;
- universe: canonical daily TWSE-listed-electronics row presence on the resulting signal date;
- signal date and next-open execution: exactly as frozen in IF-07 V0.1 preregistration;
- missing or rate-limited event metadata: fail closed for that event, never substitute ZIP time, HTTP Date, board date, quarter end or statutory deadline.

The data-capability decision does **not** require a scalable all-market upload-timestamp batch endpoint. Exact `t57sb01` metadata may be queried only for the accounting candidates that survive the frozen signal rule. Rate limiting is an execution concern, not evidence that the PIT history is absent.

## Stop rule

Effective immediately:
- stop searching for additional PIT timestamp proxies;
- stop expanding source families merely to make acquisition easier;
- stop treating bulk ZIP timestamp, HTTP headers, board-resolution time, inferred dates or statutory deadlines as candidate authorities;
- do not run further data-capability probes unless an already-frozen required source is later proven unavailable for an actual candidate.

## Preregistration consequence

The source/data gate is closed as `PASS`.

The operative challenger remains:
`IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1`

Its preregistration already exists, is persisted, and has been re-read:
`HENGCE_IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1_PREREG_20261031.md`

Therefore do **not** create a second preregistration or silently retune V0.1. The next research authority is the existing frozen preregistration itself.

`DATA ACQUISITION EXPANSION -> CLOSED`
`PREREGISTRATION AUTHORITY -> ACTIVE`
`FORWARD RETURN LOCK -> REMAINS CLOSED UNTIL THE PREREGISTERED NO-RETURN PANEL / INTEGRITY GATES ARE SATISFIED`
