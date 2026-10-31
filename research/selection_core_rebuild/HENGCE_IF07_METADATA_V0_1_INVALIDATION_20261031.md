# HENGCE IF-07 Metadata Index V0.1 — INVALIDATION

Date: 2026-10-31  
Branch: `research/selection-core-rebuild-20261031`  
Forward returns inspected: `NO`

## Verdict

`IF07_METADATA_INDEX_2022_2026 = INVALID_FOR_PANEL_INPUT`

The apparent 794 current/prior pairs from the first metadata-index run are permanently forbidden as research-panel input.

## Why

The V0.1 builder queried TWSE electronic-book endpoint `doc.twse.com.tw/server-java/t57sb01` with a blank year and concurrent requests.

The resulting artifact had:
- acquisition ticker count: 468;
- only 69 tickers with any parsed metadata row;
- 399 tickers with zero parsed rows;
- 32 explicit transport/DNS errors;
- only ~51-61 apparent exact-`無` pairs per fiscal quarter.

This is implausibly sparse relative to the canonical TWSE electronics universe and was therefore treated as a data-acquisition failure rather than accepted as fact.

## Diagnostic proof

A later year-scope diagnostic queried known issuers.

For 2330 and 2454, the blank-year query returned 54 IFRS consolidated-report rows and explicit-year queries returned the expected 4 quarterly rows for 2022-2025.

For 3037, the blank-year query initially returned 55 historical rows, but subsequent explicit-year requests returned zero because the page body was:

`查詢過量，請稍後再查詢!`

For 2317 and 3008, blank-year and explicit-year requests in the same runner also returned that rate-limit body rather than true no-data results.

2303 additionally experienced a transient DNS resolution failure.

Therefore a HTTP 200 with zero parsed rows cannot be interpreted as company-quarter absence unless the response is independently proven not to be a rate-limit/security/error page.

## Governance consequence

- Do not use the V0.1 794 pairs.
- Do not use V0.1 zero-row results as evidence of missing filings.
- Do not relax the original-filing/correction gate because metadata retrieval is inconvenient.
- Do not attach any return data to this invalid metadata sample.

The active research path must use a scalable PIT timestamp authority that is independently verified before building the no-return accounting panel.
