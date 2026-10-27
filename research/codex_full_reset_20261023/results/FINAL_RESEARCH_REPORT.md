# HENGCE full reset: completed finite-batch evidence

**Decision: NO_ROBUST_WINNER. Research only. NOT MERGED.**

Frozen corpus: `05bf0e35fb6a88473fd4f947952ef1b6875d3f88`.
Branch: `research/codex-full-reset-run-20261023`. Issue #29.

## What completed

- Stage B 39936974870: completed/success; 724/724 dates, 313,749 PIT date/ticker
  rows, zero failed dates, all 724 raw official responses revalidated against
  exact daily membership and merged numeric values.
- Stage C 39937394677: completed/success; 4,200 configs × two chronological folds
  = 8,400 selection evaluations. Baseline/validation/neighbor/quality tests bring
  the original search to 8,504 model evaluations.
- One separately preregistered pinned-function baseline diagnostic brings the
  study total to **8,505 model evaluations**. Ledger: 25,432 records, exact append
  prefix retained, no dangling STARTED evaluations. 846 sample-size rejections
  are retained, along with all negative metrics and family rejection reasons.
- Offline completed-evidence audit PASS. Both downloaded ZIP SHA256 values match
  GitHub's independent artifact metadata. Hash-bound archives are checked in so
  evidence does not disappear when Actions artifact retention expires.

## Main results

These are adaptive family walk-forward results: 2023 selects F1 parameters for
2024; 2023–2024 selects F2 parameters for 2025. They are **not** a single fixed
configuration's three-year return. All history was exposed; none is pristine OOS.
Returns below subtract 1.2% aggregate roundtrip cost once per complete basket.
Drawdown includes daily-close mark-to-market within trades.

| Family | 2024–2025 net return | Win rate | Complete baskets | Daily-close max drawdown | Final eligibility |
| --- | ---: | ---: | ---: | ---: | --- |
| RAW_REVERSAL | -15.71% | 64.29% | 14 | -62.49% | REJECTED |
| RAW_MOMENTUM | +1.32% | 46.43% | 28 | -70.92% | REJECTED |
| RESIDUAL_REVERSAL | +91.25% | 60.00% | 15 | -33.42% | REJECTED |
| RESIDUAL_MOMENTUM | -42.60% | 46.15% | 26 | -73.24% | REJECTED |
| VOLATILITY_NORMALIZED | -58.23% | 35.71% | 14 | -71.36% | REJECTED |
| BETA_WEIGHTED_RESIDUAL_REVERSAL | +48.72% | 47.06% | 17 | -51.33% | REJECTED |
| SIMPLE_RANK_ENSEMBLE | -78.97% | 36.00% | 25 | -84.35% | REJECTED |

Residual reversal (+91.25%, 15 baskets, 60% wins) passed the original plan's
eligibility checks but failed both additional **pre-search registered** attacks:
stricter .10 discontinuity treatment and Holm-adjusted quarter-block inference
(adjusted p=0.62890625). Every family failed the alternative-quality attack and
multiple-testing gate. No family is accepted. Do not add a post-hoc filter to
rescue one. Pareto membership is descriptive; it does not imply eligibility.

## Baseline resolution

Initial reset-feature reference attempt: 9 entries, 4 wins, -19.89% at .8% cost;
explicitly failed aggregate reproduction. That failed attempt remains immutable
inside the original Stage C package.

Investigation established semantic differences: pinned E2 compounds five daily
cross-sectional median returns for m5, while reset V1 uses the cross-sectional
median of each ticker's five-session return; pinned E2 also has a >=10-observation
liquidity admission within 20 observations and requires beta>0, unlike the reset
feature generator's full-window/general beta rules.

V2 AST-extracts the exact pinned E2 pure ingestion/feature functions (no module
import, network, runtime writes, optimizer, or new thresholds) and uses the same
verified official mother. It reproduces **13 entries, 8 wins, +53.0103542875737%,
trade-end max drawdown -41.6333333333333%**. This resolves the aggregate mismatch;
it does not authenticate the corrupt original event payload. New V2 events are
explicitly new reconstruction evidence, never claimed as recovered original bytes.
Baseline .8%/three-year results and reset 1.2%/two-year results are not directly
comparable measures of outperformance. Cost stress on the fixed V2 events is
reported separately without generating another signal/model trial.

## Files and reproducibility

- `WINNER_OR_NO_WINNER.json`: current completed-study decision.
- `stage_b/`: complete mother, QA, PASS receipt; raw CSV gzip responses are inside
  `artifacts/stage_b_39936974870.zip`.
- `stage_c/runs/39937394677-1/`: immutable original trial summary, Pareto frontier,
  robustness, regime/concentration reports and original baseline comparison.
- `stage_c/EXPERIMENT_LEDGER.jsonl`: original journal plus the independently
  registered V2 diagnostic appended; no original prefix was replaced.
- `artifacts/stage_c_39937394677.zip`: original journal/root and exact original
  prefix snapshot, byte-for-byte as downloaded.
- `ARTIFACT_MANIFEST.json`, `EVIDENCE_AUDIT.json`, `SEARCH_PREREGISTRATION.json`:
  independent artifact anchors, verification evidence and original finite scope.
- `stage_a/`: original Stage-A snapshots; current lineage/coverage/failure reports
  extend them without hiding earlier corrupt data or failed workflows.

Offline verification (no model trials, no live API):

```sh
python -B research/codex_full_reset_20261023/test_stage_b_contracts.py
python -B research/codex_full_reset_20261023/test_stage_c_integrity.py
python -B research/codex_full_reset_20261023/audit_completed_evidence.py
```

Do not rerun search to reproduce the verification report. A new search is a new
registered/retained experiment, not a rewrite of this batch.

## Limits and next work

This is one registered finite family batch, not a proof that no TWSE electronics
model can work. Small samples, unknown historical variant counts, dependent
quarter blocks, unproven original publication/revision timestamps, raw-price
corporate actions, and conservative censoring limit scientific claims. The .10
quality attack may also remove genuine limit-move days; failure shows sensitivity,
not proof that all such moves are corporate actions. Drawdown uses daily closes,
not unavailable intraday fills/quotes.

Highest-value next step: independently verified corporate-action/security-master
and PIT price-adjustment lineage, then a separately frozen research plan and future
prospective shadow protocol. Do not retune against this exposed validation until
it happens to pass. No historical winner, capital allocation or production
promotion is justified by this package.

Production Q017/E2/M1 compute, ranking, universe authority and producer schedules
are untouched. Capital=0, signal/ranking authority=false, broker=false,
production_promotion=false, merge_authorized=false. No main push or merge.
