# N2 Top1 60-session positive-return warning: explicit candidate, falsified as universal veto
Date 2026-11-04. Parent forensics commit `166e22647f3062875518c1c583262bfe2524a725`. **Post-hoc exploratory / ALPHA_INCONCLUSIVE / TRADING_NO_GO.**

## Signal (observable at prior month-end close)
After frozen N2 Top1 selects exactly one stock, compute `R60 = C(signal_date) / C(signal_date_minus_60_TWSE_sessions) - 1` from raw historical stock closing prices. **WARNING = R60 > 0** while N2 is targeting the prior-5-session weakest name. Hypothetical strict veto skips the purchase entirely, keeps 5m cash, does NOT substitute N2 rank2, and continues using 84 original signals, fixed independent NT$5m per window, no compounding, H20, 40bp/80bp cost.

This rule was proposed after observing 2024 and other past returns; NOT previously preregistered, NOT OOS and not a reliable forward risk filter. `R60` is unadjusted and may suffer rights/dividends.

## Exact 84-date locked data replay

| | Original N2 Top1, K=1 | Warning skip rule |
| --- | ---: | ---: |
| Attempted opportunities | 84 | 84 |
| Actual historical priced buys | 84 | 39 |
| Wins / losses **among buys** | 46 / 38 | 26 / 13 |
| Win rate among buys | 54.76% | **66.67%** |
| Fixed-independent-window sum PnL, 40bp | **+NT$19,883,039** | +NT$9,930,138.40 |
| Same at 80bp | +NT$18,237,928 | +NT$9,165,726.80 |

- Warning group 45: **20 wins, 25 losses, +NT$9,952,900.60**. Skipping them discards *positive* total net PnL. It does not improve absolute historical profit.
- **2024**: 4 of 9 names warned; all 4 lost **-NT$2,511,420**. 2024 PnL changes from -NT$2,643,856.40 to -NT$132,436.40; the remaining 5 still include 3 losing positions.
- **2018–23**: warning-free 27 buys have 21 wins, 6 losses, +NT$11,852,504.80, but this segment has already been historically reviewed.
- **2025–26**: warning captures **11 trades, 7 wins / 4 losses, +NT$8,661,584.40**; skipping them turns the two-year N2 sum from +NT$6,871,654.40 to **-NT$1,789,930** (7 remaining trades, 3 wins / 4 losses). **Inversion invalidates this condition as a universal trading veto.**
- All 84 trailing-60 raw-price returns independently replayed against nine original archived TWSE price ZIPs; no missing signal values, no reranking, no date changes, 84 original 5m PnLs crosschecked. 27 of 84 had company actions in prior 60 trading sessions (12 warning and 15 not), so true-return / share-rights adjustment is pending.

## Exact handoff
Full source Python, 84 dated stock rows, 60d ex-action flags, summary, SHA256 manifests and report are stored in HENGCE Library:
`/HENGCE/Research Outputs/N2_TOP1_60DAY_WARNING_AUDIT_20261104/HENGCE_N2_TOP1_60DAY_WARNING_SIGNAL_AUDIT_20261104.zip`
ZIP SHA256 `34c8c66da34ad392066b9c30832268af51774007e5da585ecc7e974516013efd`.

## Verdict / future work
**One explicit warning hypothesis was found, and shown to fail important out-of-year stability checks. No validated predictive warning exists yet.** Do not promote rule. Further candidate studies need frozen pre-entry indicators, PIT corporate-action-adjusted return and actual next-open execution constraints, then truly future zero-capital monitoring. Original N2 Top1 remains unchanged. Live trading NO-GO.