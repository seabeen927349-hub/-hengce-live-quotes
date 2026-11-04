# HENGCE Selection baseline: fixed NT$1m per trade window, noncompounded audit

Date: 2026-11-04. **Verdict: ALPHA_INCONCLUSIVE / TRADING_NO_GO.** No production/main/Canonical/Selection Core changes. All amounts refer to **independent NT$1m re-funded windows**; cumulative PnL is NOT compound growth or final executable equity.

## Authority and inputs

Base research SHA `df266cd6dead2f30ac8b981b1d2494caa729d32e`. Before recomputation, per-window fixed-principal rules registered in commit `0bbddd856a1e74e68350b294c222ac63ce5cac35`, file `research/selection_baseline_audit_20261104/FIXED_1M_NO_COMPOUND_PREREG_20261104.md`. Immutable original Selection N0/N1/N2/N3 baseline contract and IF07 returns remain untouched.

9 archived TWSE electronics ZIPs 2018–2026-10-27; 2,143 sessions, 899,257 four-digit security/date records; 27/27 internal manifest file checks PASS. 3,174 corporate-action records exist but are not yet a PIT-verified total-return feed. Admission is historical daily E-class archive, without independently certified date-by-date legal ordinary-share registry.

At every complete month end after close, prior 60 sessions median turnover >=50 observed; Top100; select N1 highest past20 close return Top5, N2 lowest past5 close return Bottom5, N3 matched random Top5 x10k seed 20261031, or N0 theoretical equal-weight Top100. Trade next TWSE open, exit close of 20th session, no overlap, 40bp roundtrip plus 80bp sensitivity. Each of five picks receives separate NT$200k budget **every event**, 1000-share board lots; unspent cash idle. Exactly 84 matched event windows 2018-04-30 to 2026-09-30 (latest available 2026-10 market data incomplete).

## Fixed principal outcomes (price-only, research diagnostics)

| Benchmark | Complete-price events | Sum of independent window PnL | Mean PnL per priced 1m window | Extra caveat |
| --- | ---: | ---: | ---: | --- |
| N1 past20 momentum Top5 | 83 /84 | +NT$821,837.48 | +9,901.66 (0.99%) | one purchased name 2316 missing 2019-10-01 exit price; ALL 84 formal cumulative not certifiable |
| N2 past5 reversal Bottom5 | 84 /84 | **+NT$1,157,940.48** | **+13,785.01 (1.38%)** | 286 bought position entries; 14 positions through corporate action; 32 signal lookback corporate-action exposures |
| N3 random Top5 | 7,311 /10,000 all-event paths fully priced | +NT$543,704.28 median of surviving paths | not certified | 2,689 excluded by future exit missingness; biased conditioned sample |
| N0 theoretical Top100 | 78 /84 all-name windows fully priced | +NT$1,169,142.23 | +14,989.00 | cannot buy 100 round lots within NT$1m |
| TAIEX index proxy signal close/exit close | 84 /84 | +NT$1,641,871.85 | +19,546.09 (1.95%) | not same next-open fills, no ETF execution or costs |
| TAIEX entry-session close/exit close | 84 /84 | +NT$1,357,465.55 | +16,160.30 | still not aligned open |

N1 and N2 cost 80bp independent-window sums respectively **+NT$658,874.96** and **+NT$974,541**, unchanged lots. N2 mean invested ~54.6% of NT$1m; N1 ~49.5%. Missing board-lot entry for 134/420 N2 slots, 163/420 N1 slots. N2 wins 45/84 windows, N1 34/83. N2 best 1/3/5 **event-window** removals yield +NT$924,846 / +NT$519,610 / +NT$242,863. N2 recent 3-month sample 3 completed events, cumulative +NT$260,294, top event +NT$233,094: concentration risk.

## Paired descriptive comparisons, N2 minus comparator, annual-block bootstrap 95% CI

| Pair | Events | Mean extra NT$ per 1m window | Descriptive 95% CI |
| --- | ---: | ---: | --- |
| N2 – N1 | 83 | +4,047 | -10,713 to +18,569 |
| N2 – N0 theoretical | 78 | +1,006 | -7,225 to +11,769 |
| N2 – TAIEX signal-close index proxy | 84 | -5,761 | -18,984 to +6,352 |

All intervals cross zero. Index proxies N0/N3 are NOT fully matched executable comparators; these are *not* alpha or genuine untouched OOS p-values.

## Corporate action integrity

Annual source lists 2,894 ex-dividend (`息`), 167 ex-rights (`權`) and 113 joint (`權息`) events. N2 286 purchased positions: 14 crossed corporate actions, 2 crossed events involving unresolved share rights. **32 N2 positions** have corporate actions in the five-session preselection lookback: unadjusted price changes could masquerade as reversals; preserve frozen pick identities and verify original adjustment, never post-hoc exclude or rerank. Indicative cash-only dividend assumption yields +NT$62,632 (not certified cash, entitlement, taxes). Rights-plus-dividend values MUST NOT be added wholesale as cash. Missing 2316 exit price invalidates one entire N1 event, not automatically a zero exit.

## Conclusions and execution

- **45/45** fixed-capital accounting / source / event integrity regression tests passed.
- Fixed principal calculation valid as a research price-only diagnostic, not validated total return.
- No independently certified historical PIT share-class registry, corporate-action and dividend/rights full returns, source revisions, actual order fills/slippage, or prospective independent evidence. N3 path complete-case selection bias prohibits claimed statistical significance.
- `RESEARCH_PRICE_ONLY` / `ALPHA_INCONCLUSIVE` / `TRADING_NO_GO`. **Do not optimize parameters, revive models, or authorize trading.**

## Reproducibility and retained materials

Artifact ZIP: `HENGCE_Selection_Fixed_1M_No_Compound_2018_2026_20261104.zip`. SHA256 `4717964ac430c2a0e2978f8d1d8512eab8016e61a9b28556fdc33e5ffa19b8a2`, 15 files incl. Python replay and tests, input authority evidence, per-event and position CSVs, full Chinese README, random matching, paired CI, manifest.

Library: `/HENGCE/Research Outputs/SELECTION_FIXED_1M_20261104/`.

Next legally valid work: obtain as-of corporate actions and PIT securities, certify cash-vs-share rights and preselection lookback price adjustment without changing events/ranks, and use genuinely matched index/ETF tradable benchmark. No market order authority.
