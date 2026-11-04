# HENGCE Deep Pullback D1 vs 5-Day Weak Reversal N2 — Independent Matched Audit

Date: 2026-11-04. **Verdict: BOTH RESEARCH_ONLY / ALPHA_INCONCLUSIVE / TRADING_NO_GO**.

## Authority

- Source branch: `research/selection-fixed-1m-noncompound-20261104`, source SHA `d475e9edfde7cb62ae1d096b5f2c232b2a514a69`.
- New D1 rules frozen **before D1 forward return calculation** in `D1_VS_N2_PREREG_20261104.md`, commit `957ef5af10990bcae7ee9acefeff4ae41d0e2f45`.
- Full replay/code/28 tests/names/trades/annual comparisons in Library path `/HENGCE/Research Outputs/DEEP_VS_WEAK_20261104/HENGCE_D1_Deep_Pullback_vs_N2_5Day_Weak_Reversal_Fixed1M_20261104.zip`.
- ZIP SHA256 `b623f3c6f2e935510ea7ddb64a5c581d8ac8ab9cfa20ab389a93f422ff4d07be`, 18 members incl per-file SHA manifest.
- No main / live Q017 / Escape / Original Canonical / existing Selection Core / frozen N2 changed.

## Fair-sample mechanism

Prior 84 monthly dates from 2018–2026 retained. Eight 2018 dates have no full 250 historical sessions to qualify for D1 and are excluded from BOTH methods' matched comparison (not counted as losing D1 zero-return events). **76 common valid event dates**, 2019–2026. Both methods use the same PIT historical daily TWSE electronics Top100 turnover pool; same next-day open; 20th TWSE trading session close; no overlap; exactly NT$1,000,000 **refunded anew at each event, not compounded**, five independent NT$200,000 board-lot sleeves, unspent cash retained, 40bp roundtrip and 80bp stress. All 76 x 2 events priced; N2 names/transaction PnL crosschecked against previously frozen 84-event ledger.

- **N2**: lowest five prior five-session raw closing returns. A relative rank, **not intrinsically a deep-dip** definition.
- **D1**: 250 fully contiguous historical session closes, raw price at least **20% below prior-250-session highest close**, trailing 60-session close return at least **10 percentage points worse than compounded median of all electronics daily stock returns**, rank by deepest drawdown and then most negative market excess. No enough names means cash for missing sleeves, zero winners means no trades.

## Matched 76-event returns — historical unadjusted price-only, not certified total return

| Metric | N2 5-day weak | D1 deep |
|---|---:|---:|
| Sum of 76 independent NT$1m event PnLs at 40bp | **+NT$904,600.68** | **+NT$482,629.36** |
| Mean PnL per new NT$1m event | **+NT$11,902.64** | **+NT$6,350.39** |
| Positive / negative / zero events | 40 / 35 / 1 | 34 / 28 / 14 |
| Bought positions | 251 | 150 |
| Mean invested share of NT$1m | 52.91% | 32.20% |
| 80bp cost aggregate | +NT$743,761.36 | +NT$384,728.72 |
| Remove top 5 event PnLs | +NT$56,323.48 | **-NT$55,906.44** |

N2's original **84-event** non-compounded PnL is NT$1,157,940.48: that result **cannot** be compared with D1's 76-event sum, hence the exact 76-event N2 rematch above.

Yearly results, both with same event dates (NT$):

| Year | N2 PnL | D1 PnL |
|---|---:|---:|
| 2019 | +241 | +8,135 |
| 2020 | +70,439 | -135,384 |
| 2021 | -20,549 | +65,005 |
| 2022 | +22,281 | +106,998 |
| 2023 | +244,764 | +125,001 |
| 2024 | -28,817 | +95,535 |
| 2025 | +228,678 | +171,018 |
| 2026 | +387,563 | +46,322 |

Matched D1 minus N2: **-NT$421,971.32 aggregate**, **-NT$5,552.25 per event**. D1 beat N2 on 32/76 dates; N2 beat D1 on 44/76. Year-block bootstrap, 10k draws, 95% CI for per-event mean **[-NT$18,229.30, +NT$4,501.42]**. CI spans zero, and 2019–26 is not truly unseen prospective data. Stronger N2 gross PnL also partly reflects its higher investment utilization. Do not assert significant alpha.

N3 matched 10k random five-name paths on same 76 dates: only 7,740 complete-price paths, 2,260 blocked. Conditional complete-path median aggregate +NT$542,077.76; future-availability conditioning makes this **not a certified p-value**. Same-date TAIEX price index signal-close-to-exit-close proxy sum +NT$1,597,390.13, **not** next-open costed tradable reference.

## Corporate action and genuine deep validation

- D1 selected 261 total names (fewer than 5 on many dates); **237/261** had at least one corporate action within trailing 250 sessions, **41** a rights/non-cash-only action. This is an *exposure flag*, NOT proof all their -20% raw drawdowns were artificial.
- Independent *signal-side only* historical ex-reference mechanical adjustment for known ex-dates (ratio `ex_reference/previous_close`, backward adjusting pre-event closes; not true investor total return) left **255/261** originally selected D1 names still -20% from adjusted 250-session high; **6** crossed above -20%. It did **not** recompute the D1 60-session relative-market criterion after adjustment and cannot certify any all-in D1 eligibility.
- Matched N2 had 380 selected names; 37 with a company event in prior five trading sessions; 4/380 moved from negative five-day raw returns to nonnegative under the same mechanical reference-align sensitivity.
- Positions crossing corporate actions **during holding**: N2 13, D1 7; rights/stock dividends, cash receivables and taxes not fully reconstructed. Price-only PnL may over/understate actual economic total returns, so neither model can claim live edge.
- PIT dated legal share-class, revision lineage, trading liquidity/open fill feasibility and adjusted true shareholder returns still require independent audit.

## Tests, implementation corrections

- **28/28 regression tests PASS**. Verify dated source integrity (27 annual CSV internal hash checks), N2 old-trade exact price/PnL parity, prior-only 250/60/5 signals, zero-pick-to-cash, no position overlap, 200k share allocation, 1m each event, no compound, 40/80bp reconciliation, missing exit fail-closed, true 76 matched dates and paired year arithmetic.
- An initial local D1 test bug mistakenly accepted pre-250-session 2018 signal windows due to Python negative slice empty-window vacuous `.all()`; corrected *before final verdict* with `if i<249: DATA_NOT_ADMISSIBLE`, exact 250-row assertion and dedicated regression case. Formal results **only 76** common windows.
- Separate CA-reference diagnostic first aggregated mixed bool/None with misleading 1 counts; fixed using numeric condition counts, source-replayed to 255/261. All uncorrected intermediate results invalid.

## Prioritization

**Priority 1: N2**, because better price-only PnL under equal 1m/event constraints, more viable fills and 2025–26 persistence; but not validated alpha. **Priority 2: D1**, because 2022 and 2024 environmental performance merits a *distinct* orthogonal study rather than grafting D1 into N2 after exposed returns. No threshold tuning, model merging or real trading from this analysis.

Next **validation** requires source-derived PIT true total-return series including cash, shares, rights, splits, changes in ordinary-share listing and tradable opens; regenerate both locked signals and all 76 events without post-hoc parameter modifications. Then begin genuine prospective frozen-spec zero-capital observations. If these cannot be supplied, status remains `DATA_BLOCKED_FOR_FORMAL_GO`.
