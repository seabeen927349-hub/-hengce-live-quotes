# HENGCE — FinMind historical TDCC holdings recovery, 2026-11-07

**Authority: RESEARCH_CANDIDATE_ONLY; NO_MODEL_OR_TRADE_AUTHORITY.**
**Scope:** historical shareholding-grade recovery, not a re-run of N2 or replacement of original TWSE/TDCC canonical vessels.

## Evidence completed during this session

- Source: FinMind v4 dataset `TaiwanStockHoldingSharesPer` using the repository's existing `FINMIND_TOKEN` secret. Never print or commit the token.
- Historical permission and schema tests: 2330 2018 Q1 **13 weekly observations / 208 grade rows**; 2330 2025 Nov **4 observations / 68 grade rows**; 1101 2024 Jan **4 observations / 68 grade rows**. Across-year stock-specific queries worked.
- Omitting `data_id` in the tested 2018 two-week marketwide query returned **zero rows**, so the marketwide shortcut is **NOT VERIFIED** for this token. Do not infer zero market ownership from this response.
- Deterministic sample: the first 25 stocks from the existing frozen 3,091-code TDCC candidate union, date window **2018-01-01 through 2025-10-30**. **25/25 source/schema checks PASS**; **143,871 grade/adjustment records**, **8,740 stock-week keys**, coverage **159–404 weeks per stock**. Lower coverage is not automatically a data error; compare listing life and upstream availability.
- Sample proof: [GitHub Actions run 42359228446](https://github.com/seabeen927349-hub/-hengce-live-quotes/actions/runs/42359228446), retained non-public workflow artifact `hengce-finmind-tdcc-historical-probe` (artifact ID `13569311160`, SHA-256 digest `eabbfc331e4816caa4ca10edab7657d75b55eafff4282840908de250fbe180e2`, retention expires 2026-12-07 UTC).
- Crucial schema correction: FinMind has standard holding tiers, `total`, and `差異數調整（說明4）`. Adjustment entries may have negative units **and** negative percent; preserve them verbatim, exclude them from Big400/Big1000 holding-tier sums, and never silently reject or zero-fill them.
- Critical grade-name correction: FinMind uses `more than 1,000,001` for the highest holding tier; this must be explicitly mapped to the official TDCC level 15 (>=1,000,001 shares).
- Cross-source exact numerical validation: on **2025-11-07**, ticker **2330**, official frozen TDCC and FinMind **Big400** and **Big1000** matched with **0 percentage-point, 0 share, 0 holder** differences for both categories.
- Cross-source proof: [GitHub Actions run 42359633542](https://github.com/seabeen927349-hub/-hengce-live-quotes/actions/runs/42359633542), receipt artifact ID `13569083003`.

## Where work lives

Branch: `research/tdcc-finmind-historical-backfill-20261107`.

- `scripts/hengce_finmind_tdcc_historical_backfill.py`: stock-level FinMind recovery and independent SHA/column/key validation, using frozen 3,091-security TDCC candidate checksum; produces per-stock compressed raw-grade CSV and per-run manifest.
- `scripts/hengce_finmind_tdcc_marketwide_probe.py`: no-data_id feasibility test (marketwide returned zero), receipts only.
- `scripts/hengce_finmind_tdcc_crosscheck.py`: compare valid historical grade sums to official stored TDCC summary for a common date.
- `.github/workflows/hengce-tdcc-finmind-history-probe.yml`: isolated historical probe and bounded 25-symbol sample.
- `.github/workflows/hengce-tdcc-finmind-crosscheck.yml`: isolated exact historical source crosscheck.

The source-derived CSVs are deliberately in an **Actions artifact**, not committed as public repository files; verify FinMind data usage/redistribution permissions before longer-term publication. **The Library TDCC fourth leg has NOT yet been replaced or merged.** Never conflate isolated sample coverage with complete historical full-market coverage.

## Safe next gates before broad recovery

1. Generate a **point-in-time TWSE ordinary-stock universe** from the new 2,111,682-row 2018–2026 full-market mother. The frozen 3,091-code TDCC union includes non-TWSE securities; do not spend historical API quota blindly on all of them.
2. Build an append-only **date + ticker + grade** sidecar with source version, fetch timestamp, original `HoldingSharesLevel`, and explicit adjustment/total classification. No speculative daily forward-fill.
3. Download historical missing **stock-weeks**, not weeks already verified in official 2025 tail and 2026. Batch per ticker within provider rate/plan limits, retain evidence and fail-closed on credential, HTTP, quota or schema errors.
4. Expand source overlap spotchecks to multiple stocks and weeks with official historical data, including all grade counts and adjustment rows. Reject grade mapping drift or nontrivial mismatch.
5. Validate de-listings, corporate actions, distribution share-base changes, and original observable release times. Historical FinMind extraction today does NOT prove contemporaneous data availability; only allow a separately labelled, conservative publication-lag proxy until proven.
6. Build Big400/Big1000 concentration, holder-count compression, and change over 4/12/26 weeks; treat these as **unvalidated research features**, not evidence of particular beneficiary identity or a trading signal.
7. Evaluate 63/126/252-day risk-adjusted excess returns using full-market eligible stock cohorts, predetermined match controls, nonoverlap sensitivity, dividends/corporate actions, and right-tail robustness. No model or trading promotion without forward evidence.

**No claim that the entire 2018–2025 TDCC mother has been filled.** Completed in this session: token entitlement proof, 25-symbol historical recovered sample, official cross-source validation, reproducible gated research code.
