# HENGCE Selection Baseline Audit — completed price-only research (2026-11-04)

**Authority:** `RESEARCH_PRICE_ONLY`. **Final:** `ALPHA_INCONCLUSIVE` / `TRADING_NO_GO`. No changes to `main`, canonical raw files, Selection Core, Q017 or Escape.

**Pre-return registration commit:** `946ed3388f72bf8b94461bc92b2048631f1e9311`; `research/selection_baseline_audit_20261104/PREREG_PRICE_ONLY_DIAGNOSTIC.md`. This diagnostic is separate from the immutable HENGCE Null Baseline Contract and does not open IF-07 or any challenger forward returns.

## Data and test evidence

Nine historical electronics ZIPs in `/HENGCE_CANONICAL/HIST_SOURCE_2018_2026_20261027/` (2018–2026-10-27), 2,143 trading sessions and 899,257 four-digit stock/session prices; all 27 archive-internal CSV hash/length manifest checks passed. 3,174 archived corporate-action records include distributions and rights requiring further rights/share cashflow work. Historical security-class PIT certification, source versioning and total-return treatment are NOT complete.

Independent Python event study applies frozen monthly last-session EOD signals (except incomplete 2026-10), historical PIT E membership from daily archived panels, median of latest 60 turnover sessions with >=50 observed and Top100. N1 prior20 Top5; N2 prior5 Bottom5; N0 100-eligible-name theoretical equal weight; N3 fixed PCG64 seed 20261031 10,000 matched random Top5 paths. Next-open, 20th trading-session close, 40bp roundtrip and separate 80bp, NT$1m 1,000-share lots, equal five budgets, no overlapping positions. **84** monthly event windows. **22/22** independent integrity tests pass, including exact pre-return ranking parity and finite-capital ledger reconciliation.

## Findings, price-only research — NOT actual total returns

| Portfolio | Price-only shadow terminal from NT$1m | Recorded exposure / data limitation |
| --- | ---: | --- |
| N1 20-day momentum Top5 | NT$1,578,607 | One 2019-10-01 exit price missing (2316); entire subsequent capital path is unverified, terminal is a *shadow carry-forward*, NOT valid finite-capital audit |
| N2 5-day reversal Bottom5 | NT$3,723,450 | 15 positions crossed archived corporate actions; NO independently validated cash/share entitlements |
| N3 matched random Top5 | NT$1,433,877 **median of 7,311 complete-price paths** | 2,689/10,000 paths blocked by missing exits; 10,000/10,000 paths touched a corporate action. Complete-path conditioning makes this biased, NOT a formal p-value |
| N0 theoretical E Top100 | +1.24% mean **on observed names** per 20-session event | Only 78/84 all-name windows have complete entry/exit prices; 100-name equal weight is not board-lot NT$1m executable |
| TAIEX reference | NT$4,434,847 | Hypothetical reinvestment on the same 84 signal-to-exit **close/close index** windows; NOT the same next-open tradable execution geometry, no dividends/costs |

N2 has 330 purchased positions; price-only net contribution +NT$2,723,450, 80bp separately recomputed ending NT$2,328,060. Remove best 5 *position* PnLs still +NT$1,232,264, but this **does not cure** corporate action, PIT, cross-cycle and prospective validation. N2 2024 loss around NT$165,030 and 2025 +NT$383,316; latest 3m is only 3 completed event windows. N1 2019 example missing exit invalidates formal continuous capital return.

**Important intermediate correction:** During local implementation, 2026 archived numeric turnover strings with thousands commas required explicit numeric parsing. This was an input parsing bug, NOT candidate-parameter retuning; preliminary output before correction is not authoritative. The final output includes 2026 sessions and passes the 22 regression checks. The event-level N1 missing-exit case is flagged as an entire blocked investment event rather than silently realizing other pieces in the formal book.

## Non-promotion reasons

1. Corporate-action-affected trades are not total-return/rights-aware.
2. PIT stock class listing and historical versioned source as-of certification incomplete.
3. N1 actual exit missing and post-block shadow carry not certified.
4. N3 random complete-path selection conditioned on future availability; no valid matched null p-value.
5. Historical price-only TAIEX and N0 not fully implementation-matched.
6. 2025–26 retrospective split is not untouched prospective OOS; few recent trades.

**Disposition:** preserve reproducible diagnostic, investigate proper corporate-action-adjusted total-return and PIT eligibility only if cost justified; do not trade or call N1/N2 validated Selection Core champions.

## Artifacts

Library folder `/HENGCE/Research Outputs/SELECTION_BASELINE_AUDIT_20261104/` contains:

`HENGCE_Selection_Baseline_Audit_2018_2026_20261104.zip` — SHA256 `1894cb9f4f47c9da21087d3e368bdfb5aef400cccd09f37db6a574d3dba92ef8`.

The 13-file ZIP includes complete Python source, 22 tests, source and result JSON, 84 events, per-position transaction CSV, price-only cash ledger, detailed Chinese README and file-by-file integrity manifest. Source ZIPs remain in canonical Library and are never overwritten.
