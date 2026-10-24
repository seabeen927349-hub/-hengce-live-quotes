# Official data foundation: evidence improved; no new model claim

User instruction: continue research; use **free official sources only**. No paid
service, account purchase or private credential is needed by this package.

This is a data-only step after 8,529 retained research evaluations. **New model
evaluations: 0. No optimizer or profitability search in this step.** Neither old
NO_ROBUST_WINNER nor the subsequent failed six-model screen is rewritten.

## Evidence obtained

Collection plan and initial parser were committed/pushed at `8ece4f7` before the
13 planned requests. All 13 returned response bytes; HTTP success is distinguished
from schema/data validation. Raw gzip bytes, SHA256 values, URLs and actual UTC
fetch start/end timestamps are retained alongside each request receipt.

| Official source | Raw returned event rows | Exact daily-PIT electronics projection |
| --- | ---: | ---: |
| TWT49U 2023 | 1,086 | 377 |
| TWT49U 2024 | 1,184 | 357 |
| TWT49U 2025 | 1,358 | 385 |
| TWTAUU 2023 | 26 | 13 |
| TWTAUU 2024 | 15 | 11 |
| TWTAUU 2025 | 17 | 8 |
| **Total returned events** | **3,686** | **1,151** |

The table combines 1,119 ex-right/dividend events and 32 capital reductions.
Returned annual rows are not a claim of complete coverage of every corporate
action type. Full-market/ETF raw rows are evidence only, never model-universe
fallback. Normalized events admit only the preserved date-specific electronics
membership; no current constituents or current security master substitute for PIT.

Additional responses: two detailed action-term records, two monthly stock-price
reports, one 2025-04-07 opening-reference/limit report (441 PIT electronics records),
and two official event PDFs. Five earlier source-discovery probes are retained,
including an initial rejected request using `strDate` instead of `startDate`.
Probe file mtimes are labeled as such; they are not invented fetch timestamps or
historical publication evidence.

## Findings that change the data diagnosis

1. **6189 on 2025-07-25:** official report identifies rights plus dividend; detail
   reports TWD3.999732 cash per old share and 200 free shares per 1,000 old shares.
   Those terms reconcile the reported reference price within its display precision.
2. **2364 on 2025-08-28:** official rights event; detail reports 300 free shares
   per 1,000 old shares and zero cash. Its raw price discontinuity cannot simply
   be interpreted as a corresponding loss of shareholder wealth.
3. **3090 on 2025-07-15:** the TWSE notice dated 2025-07-14 suspends common-share
   trading pending material disclosure. Missing OHLC is consistent with a market
   suspension; it is not repaired by inserting yesterday's price or another stock.
4. **2327 in August 2025:** an official TAIFEX underlying-event notice cites the
   TWSE stock event: 1,000 old shares exchange for 4,000 new shares; trading stops
   2025-08-14 through 2025-08-22 and resumes 2025-08-25. The monthly stock report's
   resumption marker corroborates a conversion. This is underlying-event evidence,
   not an import of derivatives models, contracts, capital or trading authority.
5. **26 unique tickers on 2025-04-07:** prior censored one-price entries match
   the official **lower** limit exactly. A buy at a lower limit is not inherently
   impossible. Daily prices/volume still do not establish the opening auction
   allocation or execution of a specified order. No fake fill or no-fill is inferred.

The two detail responses do not echo an effective date. Binding is explicitly to
the requested ticker/date and independently validated annual parent event; the
limitation is retained. Cash-payment and new-share-delivery dates remain unknown.
Do not assume those receivables are immediately saleable or reinvestable.

## Leakage and schema protection

- Historical TWT49U responses append the **latest** financial-report period,
  EPS and net asset value. For example, historic 2025 events include a 2026
  reporting period. Normalization projects an explicit event-field allowlist and
  quarantines these current financial values. Changing them cannot change the
  historical projection, as a negative synthetic test verifies.
- Initial strict collection rejected three reduction reports' `YYY/MM/DD` date
  representation and two detail reports' lowercase `ok` status. These five
  refusal receipts remain untouched. A separate offline adapter supports those
  exact documented schemas; it does not relabel the original acquisition outcomes.
- TWT84U repeats the header `開盤競價基準` for two different time columns. A positional
  contract retains current and previous references separately. A generic dict/zip
  conversion could silently overwrite one, so it is deliberately not used here.
- Missing numbers are never zero-filled. Duplicate identities, wrong echoed date
  ranges, malformed rows, changed schemas and inconsistent term/reference values
  fail closed. Reference-price ratios never become total-return factors.

## Readiness assessment

| Use | Status | Meaning |
| --- | --- | --- |
| Retrospective corporate-action/suspension forensics | AVAILABLE WITH LIMITS | Source-backed explanations and exact raw bytes; not signals |
| Complete adjusted-price/entitlement PnL | BLOCKED | Most action details, delivery/payment dates, subscriptions and identity transitions are not complete |
| Historical first-seen/revision lineage | UNKNOWN | Fetch dates and printed document dates are not first-seen timestamps |
| Proven opening-auction execution/capacity | UNKNOWN | Daily OHLC, volume and reference prices do not prove order allocation |
| New model trials in this package | NOT AUTHORIZED BY THIS DATA-STAGE PLAN | Fixed budget zero; retain cumulative model count 8,529 |
| Production decisions/capital/orders/promotion | FORBIDDEN | All artifacts have zero authority |

`READINESS.json` remains **BLOCKED_DATA_READINESS** for adjusted-PnL use.
The explicit guard refuses adjusted-PnL readiness from these tables alone. No
missing data is fabricated to turn this into a model win. Historical explanations
do not retrospectively certify the prior trial returns.

## Tests, audit and replay

- 16 new fully synthetic/offline tests PASS: future financial-column leakage,
  frozen membership/no fallback, response status/date echo, duplicate/invalid
  records, cash-reduction separation, retained transport/HTTP errors, immutable
  output, zero new trials/authority, exact detail identity, subscriptions, formula
  consistency, slash-date normalization and duplicate-header time semantics.
- Existing 119 engineering regressions PASS. Parent 17 data/temporal tests and
  previous continuation 13 tests remain protecting their original evidence.
- Offline audits revalidate raw/archive hashes, source schemas/projections,
  date-specific membership, corrected representations, the 26 limit cases,
  two detail terms, five exploratory probes and exact checkpoint file inventory.
- Final-head workflow IDs/results and Engineering Replay are recorded in PR #30.
  CI performs offline audits only; it never recollects live data or reruns models.

Reproduce without network or model evaluation:

```sh
python -B research/codex_full_reset_20261023/data_foundation_20261023/test_evidence.py
python -B research/codex_full_reset_20261023/data_foundation_20261023/test_normalize.py
python -B research/codex_full_reset_20261023/data_foundation_20261023/audit_all.py
```

The evidence checkpoint is independently anchored by the pushed Git commit; its
self-contained hashes alone are not described as an independent anchor.

## Next research scope, still free sources only

Before another adjusted-return study, assemble effective-dated terms for the full
1,151-event projection, action-specific cash/share delivery and subscription
handling, and historical identity transitions. Free official announcements may
resolve individual cases; this package does not assert that a free complete
auction-order archive exists. Preserve unavailable cases and prospective evidence
as unknown; do not silently substitute paid data, a current universe, guessed
adjustment factors or post-event knowledge.

A future execution study must preregister buy/sell direction, auction timing,
quantity/capacity, cancellation, cash/share availability and non-fill handling.
The earlier symmetric one-price censor is intentionally conservative, not a
universal trading rule. Any replacement is a new registered experiment, cannot
rescue or overwrite old results, and cannot change production Q017 semantics.
No live collection workflow or new production schedule is deployed here.

## Primary sources

- [TWSE ex-right/ex-dividend calculation table](https://www.twse.com.tw/zh/announcement/ex-right/twt49u.html)
- [TWSE capital-reduction resumption prices](https://www.twse.com.tw/zh/announcement/reduction/twtauu.html)
- [TWSE 3090 suspension notice](https://www.twse.com.tw/staticFiles/news/news/tsecnews/8a8216d697fc438f019808c0ad380026.pdf)
- [TAIFEX 2327 underlying-event notice](https://www.taifex.com.tw/file/taifex/CHINESE/11/attach/2327_20250825.pdf)

**PRODUCTION MODEL CHANGES: NONE.** Signal/ranking authority=false, capital=0,
broker=false, promotion=false. Production bytes, schedules and existing model
semantics remain unchanged. No main push, merge, paid-data purchase or model
acceptance. **NOT MERGED.**
