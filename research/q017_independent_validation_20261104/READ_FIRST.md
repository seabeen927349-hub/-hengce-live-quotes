# HENGCE Q017 independent assessment — 2026-11-04

**VERDICT: FORMAL_TRADING_NO_GO / EXPECTED_ALPHA_INCONCLUSIVE.** This report neither modifies nor promotes the frozen Q017 code. `main`, canonical mother, 09:01 snapshots and broker/financial authority are untouched.

## Authority and source separation

- Verified `main` baseline HEAD: `b53e5fd08755f0b4b3e6e640fabb85c5fad60e06`.
- Legacy SOX-open residual D10 research source: branch `q017-2026-sox-dxy-electronics`, SHA `09e59c5a0142a73be9d7ad0d50388444232d0a8e`, `research/q017_sox_tw_electronics/capacity_aware_multistock_2026.py` and historical `summary.json`.
- Unified frozen H20 contract: `hengce/HENGCE_Q017_SOLE_ACTIVE_CONTRACT_v1_0_20261026.json`, `scripts/hengce_q017_canonical_producer.py`.
- Separate schema-v5 **09:01 observation/ranking** versus **internal unified close-based Top1 next-open** lanes explicitly defined in `hengce/HENGCE_Q017_SCOPE_RESOLUTION_v1_0_20261025.json`. DXY/Top3/09:01/D10 and DXY-free/Top1/next-open/H20 are NOT interchangeable.

## 1 — Real operation check: FAIL_CLOSED

Both 2026-11-04 Q017 09:01 supervisor status files in `main` show `PREPARED_MODEL_FAIL_CLOSED`; electronic historical source remained at **2026-10-22** while completed EOD was **2026-11-03**, and required pre-09:00:45 snapshot was absent. `formal_buy_count=0`. Backfilling a missed 09:01 window is prohibited. The latest persisted formal 09:01 Q017 decision is dated **2026-10-22** and was `CASH`. The tracked main tree has no `hengce/q017_canonical/latest.json` output; an available producer script does not authorize an absent candidate. The 2026-11-04 premarket cache recorded SOX 1d +2.63%, which would fail the SOX<=0 prerequisite; this cache is NOT a substitute for an immutable 09:01 decision.

## 2 — Legacy six-month fixed NT$1m arithmetic: PASS; attribution to today's model: FAIL

Workbook `HENGCE_Q017_6M_FIXED_1M_MAINLINE_RETIREMENT.xlsx` contains **7 old D10 opportunities**, to which H20 and 0.8% cost/no-overlap were later applied; H20 does NOT reselect names/dates from today's frozen H20 formula. Four executed rows, all entry Open/exit Close, costs, boardlots and PnL checked exactly against the original historical mother:

| Entry | Ticker | Exit | Lots | Fixed-1m PnL |
| --- | --- | --- | ---: | ---: |
| 2026-05-19 | 2408 | 2026-06-16 | 3 | +393,504 |
| 2026-06-24 | 3711 | 2026-07-23 | 1 | +7,912 |
| 2026-07-29 | 3026 | 2026-08-26 | 2 | +271,408 |
| 2026-09-15 | 8150 | 2026-10-16 | 11 | +206,932 |

Total **+879,756**, 4/4 profitable. These figures demonstrate historical PnL *arithmetic*, NOT frozen-Q017 selection edge. The legacy D10 research script also requires the future exit-date price row to exist before including a candidate (`if exitrow`), creating a future availability/survival conditioning risk. No claim that this necessarily changed these specific trades is made.

## 3 — Read-only reimplementation of actual frozen unified Q017 formula (NOT byte-exact original code parity)

Using the retained 2026 daily TWSE PIT electronics archive, prior-only beta60/min30 with electronics median-return, frozen Q017 residual and score, liquidity, local and SOX gates; signal after close, next open entry, fixed H20 exit, cost 0.8% roundtrip, 1m fixed principal, boardlots, no overlap. Source-version conflicts affecting `2026-10-08` onward cause all signal dates >=2026-10-08 to be excluded. 18 dates passed joint SOX/electronics macro screening, 16 admitted frozen-formula Top1, 12 skipped due no overlap. Completed four research-only positions:

| Signal | Entry | Ticker | Exit | Lots | PnL |
| --- | --- | --- | --- | ---: | ---: |
| 2026-03-04 | 2026-03-05 | 6282 | 2026-04-01 | 21 | -36,178.80 |
| 2026-05-19 | 2026-05-20 | 2408 | 2026-06-16 | 3 | +429,792.00 |
| 2026-07-08 | 2026-07-09 | 2467 | 2026-08-06 | 1 | -37,416.00 |
| 2026-08-24 | 2026-08-25 | 3450 | 2026-09-21 | 2 | +89,056.00 |

Aggregate **+445,253.20** on four noncompounded tickets; **2 wins / 2 losses**. Best single trade accounts for **96.53%** of net gains. Remove-best-one PnL **+15,461.20**. The four entry dates differ completely from the old workbook's four dates, confirming model-attribution mismatch.

Same four signal dates, PIT E/liquidity universe, next-open H20 and cost: fixed-seed 200,000 matched random single-name draws had **+50,755** mean, **+626,090** 95th percentile; Q017 is at only **90.17th percentile**. Comparable descriptive prior20 momentum Top1 PnL **-86,800**. These are post-hoc *descriptive* diagnostics, not pre-registered formal N0/N1/N2/N3 evaluation; only one 2026 vintage and four trades.

The implementation is independently coded from the frozen formulas, **not** a direct input-identical run of the original GitHub producer. SOX gate-date set was extracted from the GitHub 2026 SOX prices before local replay; the research program documents that it is a compiled gate input. No claim of full production parity, original adjusted-price verification, cross-cycle stability, or true prospective OOS.

## Gates

- `PASS_ARITHMETIC`: old workbook four H20 prices and PnL verified against original canonical mother; frozen-formula research calculations have **12/12 local regression checks PASS**.
- `FAIL_LEGACY_TO_CURRENT_ATTRIBUTION`: D10-generated entry dates are not current Q017 H20 entries.
- `RESEARCH_ONLY`: independent H20 reimplementation, no byte-exact parity with reviewed producer.
- `INCONCLUSIVE_ALPHA`: small post-hoc 2026 sample; 96.5% dependence on one trade; performance not past 95th matched random; no genuine forward OOS or multi-regime validation.
- `FAIL_OPERATION_20261104`: Q017 observers fail closed; no timely snapshot or valid current binding.
- `NO_GO_PRODUCTION`: do not generate trade instructions, capital allocation or backfilled formal 09:01 signals.

## Artifacts

The reproducible scripts, numerical result JSON, 12 unit tests, test log, integrity manifest and complete Chinese report are in the retained Library folder:

`/HENGCE/Research Outputs/Q017_INDEPENDENT_VALIDATION_20261104/HENGCE_Q017_20261104_Independent_Validation_NO_GO.zip`

ZIP SHA256 `42145b235dcc6f1f18d2ae1dfa28b0fde797c44616d1dfa7f092b2484e8ad63f`; 10 members; SHA manifest included. Original TWSE source CSV/ZIP and Q017 workbook remain separate retained user Library objects.

The next legitimate engineering work is to restore the daily EOD-to-electronics-history bridge before the premarket snapshot cutoff, retain fail-closed semantics, and then collect **future** zero-capital immutable observations and outcomes. Research return validation must compare frozen-code-exact, PIT-safe and corporate-action-aware signals across multiple market regimes before any promotion. Do not retune thresholds after exposed results.
