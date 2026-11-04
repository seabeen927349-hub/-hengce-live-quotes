# HENGCE N2 Top1 — 每次固定 NT$5,000,000、不複利、僅買第一名
Date: 2026-11-04. **研究結果 `RESEARCH_RAW_PRICE_ONLY` / `ALPHA_INCONCLUSIVE` / `TRADING_NO_GO`.**

## Frozen authority / no production mutation
- Research parent HEAD `ac0bee88c07abf48201a7e5d398e1d6642c2db27`.
- Rules preregistered **before 5m recomputation** in `N2_TOP1_FIXED5M_PREREG_20261104.md`, commit `b49f37ab6e463e37f84f4441cca69de9767ccede`.
- No changes to main, historical Canonical, live Q017, Escape, original N2 signal list or Selection Core rules. Capital/trading authority remains **NONE**.
- 84 monthly N2 Top1 signal windows from 2018-04-30 through 2026-08-31, as in the previously frozen 1m Top5 ledger; **no five-stock basket, no repeated five one-million simulations**. A fresh independent 5m is allocated to the one frozen rank1 name in each window. No carryover gains, losses or compounding.
- Signal at month-end close, next TWSE open buying, sale at close of twentieth trading session, non-overlap, entire 1000-share lots only, idle unspent cash. Realized PnL formula = `shares * (exit_close - entry_open) - 0.004 * shares * entry_open`. Separate 0.008 cost stress.

## Historical raw-price results (NOT certified investor total return)

| Measure | NT$5m each × 84 dates | NT$5m each × 76 dates (exact D1-study comparability) |
| --- | ---: | ---: |
| Fully priced attempted opportunities | 84 | 76 |
| Afforded/bought >= 1 board lot | **84 / 84** | **76 / 76** |
| Positive / negative | **46 / 38** | **43 / 33** |
| Sum independent PnL, 40bps | **+NT$19,883,039.00** | **+NT$16,057,795.00** |
| Sum independent PnL, 80bps | **+NT$18,237,928.00** | See `summary.json` |
| Mean PnL per independently new 5m window, 40bps | **+NT$236,702.85** | **+NT$211,286.78** |
| Mean 5m-window return, 40bps | **+4.7341%** | **+4.2257%** |
| Average actual allocated capital | **97.92%** | **97.81%** |

**Critical interpretation:** +NT$19.883m is **the sum of 84 independent single-shot 5m-window PnLs**; it is **not** a 5m initial bank account compounded to 24.883m, not a single real investable portfolio, and not an annualized return. Each historical trade consumes up to a *fresh* 5m notional. User-requested fixed-principal bookkeeping was enforced.

Same 84 frozen Top1 dates independently rerun with 1m per attempt: +NT$3,955,424.20, only 79/84 purchased an affordable board lot. The 5m vs 1m total PnL ratio = ~5.027, **not exactly five**, since boardlot rounding and allocated principal differ. On the exact 76 matched dates, original sealed 1m Top1 sum +NT$3,217,226.80 was independently reconciled date by date and 5m sum +NT$16,057,795.00.

## Risks from actual historical drawdown / capital concentration

- **2024:** 9 attempts, **2 positive / 7 negative**, fixed-five-million PnL summed **-NT$2,643,856.40**. Do not mislabel this as the percentage drawdown of an actual continuously invested single 5m portfolio.
- Largest positive event: 2025-12-31 N2 Top1 **2313**, next-open 93.9, H20 close 178.0, 53 lots, +NT$4,437,393.20 net of 40bp. Most negative: 2026-06-30 **6442**, open 1665.0, exit close 1110.0, 3 lots, **-NT$1,684,980.00** (-33.70% of the independent 5m attempt).
- Remove best 1 / 3 / 5 events from the 84-date profit sum: +NT$15,445,645.80 / +NT$8,315,781.80 / +NT$3,553,385.80. Different market regimes had widely different outcomes, and 2024 is severely negative.
- Holdings crossing corporate action records: 4 selected/bought positions, cash dividend `息` flags only. N2 5-day historical ranking itself also has signal-side corporate actions. Neither selection rank nor PnL has independent fully verified shareholder total-return adjustment.
- At opening-price presumed notional, no transaction exceeded **10% of its entry day's total reported turnover**, largest ~**8.08%**; mean day-turnover proportion ~1.19%. **Daily whole-session turnover is NOT the actual next-day open available sell liquidity.** 5m open-fill, limit, slippage, transaction taxes, corporate entitlements remain unchecked. The 84 times when 5m is large enough to buy a board lot do NOT establish actual 84 executable fills.
- Historical sample 2018–2026 has been used repeatedly: **no pristine unseen forward OOS**. Cannot infer stable alpha from this backtest.

## Integrity and replay

- **93/93 pytest cases passed**. 84 exact frozen N2 rank1 ticker/entry/exit triple checks, 84 boardlot/cost/notional and reset checks, nine 2018–2026 archived source ZIP SHA matches, 84 input market open/exit-close row checks, exact full 76-event 1m K1 historical PnL parity, annual reconciliation, 40/80bps and failure cases.
- Full reproducible input copies, source Python, row-level 84-trade ledger, 1m-vs-5m matched 84-date ledger, yearly PnL, test log, JSON output, SHA256 manifest bundled in Library: `/HENGCE/Research Outputs/N2_TOP1_FIXED_5M_20261104/HENGCE_N2_Top1_Fixed5M_NoCompound_2018_2026_20261104.zip`.
- ZIP SHA256 `966facd67190d7a22658e3576101cb83a98884ec28cc1ac89e4a95c89a65e419`; 15 members.
- The nine original year electronic archive ZIPs remain retained in HENGCE Canonical Library, NOT re-uploaded or modified in this study.

## Conclusion

**Fixed 5m Top1 removes nominal whole-lot unaffordability, but does NOT repair strategy data uncertainty or opening-price executability.** This is a capital-capacity / bookkeeping study only, not an improvement in N2 win probability or a new live trade signal. Continue total-return corporate-action-adjusted and forward zero-capital validation; no production promotion.
