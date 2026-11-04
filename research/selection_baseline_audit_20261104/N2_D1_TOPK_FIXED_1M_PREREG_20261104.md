# Pre-registration (before Top-K forward-return calculations): N2 versus D1, K=1/3/5, fixed NT$1m per independent entry window
Date: 2026-11-04, parent HEAD `b1d63a01e936f5f4d69ca2e62841f5e7f2f60f54`.

## Research authority
- **No production or broker/capital authority**. No mutations to main, original Canonical, existing frozen Selection baselines, Q017, Escape, earlier D1/N2 result tables.
- TopK comparison is a **new retrospective diagnostic**, not independent prospective OOS. Outcomes were historically exposed; rankings and parameter values are copied exactly from prior frozen D1/N2 signals, NOT adjusted after looking at returns.
- Base data: 76 D1-coverage-gated matched windows from `deep_vs_weak_20261104/signal_gate_all84.csv`, `paired_positions_prices_and_actions.csv`, `paired_event_prices.csv`. All 76 identity/date/rank/ticker records and all K5 prices/sleeves must be read-only, SHA-recorded, and match prior published frozen results.

## Fixed rules, independently per strategy and every window
- **N2**: 5-day weakest-return existing descending rank order, not true price drawdown; **D1**: separate 250d -20% plus 60d market-relative -10pp definition in prior `D1_VS_N2_PREREG_20261104.md`. Do NOT change rankings or recover missing picks.
- Compare six cases N2-K1/K3/K5 and D1-K1/K3/K5, with same 76 admissible entry and exit dates. Missing D1 nominees occupy cash rather than substituted stocks; if zero picks, cash PnL=0.
- Each window has an **independent fresh** NT$1,000,000 buying-power budget, never compounded. For TopK, divide into **K fixed sleeves of NT$1,000,000/K**, one for each existing rank. One rank slot never borrows from another or rolls unused cash into another. The Top1 budget is 100% of 1m, Top3 1/3 each, Top5 1/5 each.
- Entry at prior frozen next TWSE-session open; exit at prior frozen fixed 20th TWSE-session close. Shares per ticker = 1000*floor((1,000,000/K)/(1000*entry_open)). Stocks with missing open or price too high for one lot hold cash. No leverage, fractional lots, stock substitution or earlier reopening, month-to-month compounding.
- Cost = 40bps roundtrip **of actual entry notional**: PnL = shares*(exit_close-entry_open) - 0.004 * (shares*entry_open). 80bp rerun separately. No dividends, distributions, tax receipts, corporate-action shares included in base **raw-price-only** PnL. Transaction fee not separately cash-reserved at entry, matching frozen K5 study; stress and label cash-accounting convention. Windows with a bought stock but missing exit close become **entire-event blocked**, not marked as zero, nor silently drop losing ticker.
- Report for every group: number of complete windows, cash/no-buy events, bought positions and names selected, positive/negative/zero event count, total event PnL (sum of 76 one-million independent windows, NOT investment NAV), mean and median per million, mean utilized buying power, 80bp sensitivity, remove best 1/3/5 **events**, annual and 2018–24 / 2025–26 splits, company-action exposure flags, worst single event, max single event share, matched differences N2 versus D1, and within-strategy K1 vs K3 vs K5. Include source manifest, exact prior K5 parity test, no-retuning test records and annual block bootstrap for paired differences.
- Different K have substantially different board-lot capacity; compare realized capital deployment as well as raw PnL, never call top1 good or bad if single-name concentration dominates.
- Contextual/random benchmark and current total-return adjusted PIT certification **remain unfinished**; lack thereof is a blocker for formal investable alpha.
- **Any live GO forbidden**; permitted verdicts: `RESEARCH_ONLY_PRICE_DIAGNOSTIC`, `INCONCLUSIVE`, `DATA_BLOCKED_FOR_FORMAL_ALPHA`.

## Commitment
Freeze this file in the independent research branch BEFORE calculating six candidate TopK PnLs. No selecting the best K then changing any of these design choices, no ad-hoc constraints to improve historic profitability.