# HENGCE FinMind SponsorPro Broker Tape transport authority — 2026-11-03

Status: RESEARCH_ONLY / FORWARD_RETURNS_SEALED

Official FinMind-MCP source verification establishes:

- `TaiwanStockTradingDailyReport` is a Sponsor broker-branch dataset.
- `TaiwanStockTradingDailyReportSecIdAgg` is a Sponsor broker-branch aggregate dataset with daily per-stock/per-branch buy and sell volume and average price.
- `TaiwanStockTradingDailyReportSecIdAgg` is explicitly supported by Sponsor Pro `storage_objects` whole-day parquet downloads.
- Sponsor Pro whole-day parquet access is requested through `/api/v4/storage_objects` and returned as a short-lived HTTP redirect to object storage.
- The official FinMind-MCP client sends `Authorization: Bearer <token>` only to FinMind and does not forward that header to the signed object-storage URL.
- The signed URL must not be persisted.

HENGCE primary feasibility dataset:
`TaiwanStockTradingDailyReportSecIdAgg`

HENGCE secondary raw audit dataset:
`TaiwanStockTradingDailyReport`

Permitted work before feasibility PASS:
- transport validation
- schema validation
- source-date/PIT validation
- SHA-256 receipt
- coverage and missingness audit
- lineage audit

Forbidden before feasibility PASS and preregistration:
- forward-return inspection
- backtest
- ranking-value test
- broker selection
- threshold tuning
- feature-weight tuning
- trading authority

The raw licensed parquet must not be committed to the HENGCE repository. Only non-reconstructive receipts, schema summaries, coverage summaries and hashes may be committed.
