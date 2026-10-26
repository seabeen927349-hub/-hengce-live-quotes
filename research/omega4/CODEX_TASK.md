# HENGCE Ω4 — CAPITAL RELEASE / TAPE READER

## Mission
Build and validate a research-only exit engine that learns when capital should be released from an existing long position regardless of current unrealized P/L. The objective is not to predict tomorrow's direction. The objective is to maximize after-cost profit of a single TWD 1,000,000 cash book by exiting positions whose forward value has degraded, freeing capital for the next opportunity.

## Authority boundary
- RESEARCH ONLY.
- Work only on branch `research/omega4-capital-release-20261026`.
- Do not modify production models, production ranking, thresholds, authority, broker execution, or historical expected outputs.
- No leverage. No capital authority. No live orders.
- Do not merge to `main`.

## Required data
Use these existing HENGCE files if available in the Codex workspace / mounted files:
- `TWSE_2023_2025_mother.csv`
- `HENGCE_2026_HIST_MOTHER.csv`
- PIT electronics memberships for 2023/2024/2025 and 2026 daily electronics universe.

Expected mother columns include Date, Ticker, Name, Volume, Turnover, Open, High, Low, Close. 2023–2025 may also include margin and T86 fields; they are optional for Ω4 v0 and MUST NOT be required.

If required files are absent, FAIL CLOSED and report exactly which files are missing. Do not synthesize data.

## Research question
Given the SAME entry opportunities, can a causal capital-release exit policy outperform fixed holding by:
1. increasing after-cost total P/L,
2. reducing average capital-days,
3. improving profit per capital-day,
4. not worsening max drawdown,
5. surviving cost and tail robustness tests?

Ω4 v0 is an EXIT experiment first. Do not optimize the buy model yet.

## Core idea
At each daily state of an open position, classify whether capital should remain deployed or be released.

Do NOT use current unrealized P/L itself as the sole exit trigger. P/L may be a state feature, but the policy must primarily detect deterioration in future value / opportunity cost.

Candidate state features, all causal at decision close t:
- 1/3/5/10-day returns
- return relative to PIT electronics cross-section
- 10-day directional efficiency = abs(close_t-close_t-10) / sum(abs(daily changes))
- ATR20 / close
- distance to 20-day high and low
- volume / 20-day median volume
- turnover / 20-day median turnover
- 5-day vs 20-day range compression/expansion
- close location in daily range
- electronics breadth over 1/5/20 days
- holding age
- drawdown from post-entry running high
- MFE and MAE to date
- decay of original entry score if an entry score exists

No future feature normalization. Fit transforms on training fold only or use within-day cross-sectional ranks.

## Exit target / label
Do NOT label the future maximum price as the ideal exit.
Do NOT directly choose the ex-post best sell day.

Use a causal optimal-stopping style target on development folds only.
For each open-position state at t, compare:
- EXIT NOW value: realizable net value after sell costs.
- CONTINUE value over a precommitted short continuation window K in {3,5,10} trading days, including forward return, drawdown penalty, and capital-day penalty.

Precommit a simple utility family such as:
`U_continue = future_net_return - lambda_dd * future_drawdown - lambda_days * capital_days`

Select K / lambda values only via chronological development folds. Do not inspect the final evaluation period to select them.

A state is RELEASE when estimated continuation value is <= cash value / opportunity baseline.

## Entry set for Ω4 v0
The first experiment must keep entries fixed across A/B so the only changed component is the exit policy.

Preferred options in order:
1. Use a frozen, already-existing research entry signal in the repo with historical picks and no production modification.
2. If no suitable signal has full history, use a simple precommitted causal baseline, e.g. top-N by 20-day relative strength within PIT electronics universe subject to 20-day average turnover >= TWD 20M.

Do NOT tune entry parameters to make Ω4 look good.

## Portfolio simulator
Single cash book:
- starting cash: TWD 1,000,000
- no compounding assumption for headline comparison; additionally report actual equity curve if convenient
- no leverage
- max simultaneous positions: 3
- deterministic equal-slot allocation: floor(available target slot capital / round-lot cost)
- round lots only for primary result
- actual positions occupy cash until exit
- if no cash / slot available, skip new entry; never pretend fresh TWD 1m appears each day
- mark-to-market equity curve for MDD
- round-trip cost baseline: 40bp
- stress: 60bp, 80bp, 100bp

Use the same execution timing for A and B. Recommended causal default:
- signal / exit decision at close t
- execution at next tradable open t+1
If the repo already has a frozen alternative convention, preserve it and document it.

## A/B benchmark
A: fixed holding baseline. Precommit a small development-only set such as 5/10/20 trading days and choose one using development folds only.

B: Ω4 Capital Release exit policy.

Same entries, same sizing, same costs, same execution assumptions.

## Chronological validation
No random split.
Use anchored or rolling walk-forward with purging/embargo for overlapping forward labels.
Suggested structure if data permits:
- train 2023H1 -> validate 2023H2
- train through 2023 -> validate 2024H1
- train through 2024H1 -> validate 2024H2
- train through 2024 -> validate 2025H1
- train through 2025H1 -> validate 2025H2

Because 2026 historical data has already been research-visible in prior HENGCE work, DO NOT call 2026 pristine OOS. It may be used only as a retrospective stress period after rules are frozen.

## Model complexity
Start simple.
Preferred first models:
- logistic regression / ridge classifier for RELEASE probability
- optionally a shallow gradient boosting challenger only after simple model baseline

Complexity must beat the simple model after costs and robustness.

## Required metrics
For A and B report:
- total net P/L in TWD
- total return on starting TWD 1m
- win rate
- trade count
- mean winner / loser
- payoff ratio
- expectancy
- profit factor
- max drawdown in TWD and %
- average holding days
- median holding days
- total capital-days
- net profit per 100k capital-days
- turnover
- cash utilization
- 40/60/80/100bp results
- remove-best-trade result
- remove-best-2-trades result
- top ticker contribution
- fold-by-fold P/L and PF
- winning vs losing folds

## Primary promotion gate for EXIT ENGINE
Ω4 EXIT may continue only if, versus fixed holding on the same entries:
- 40bp net P/L is higher
- profit / capital-day is higher
- average capital-days are lower
- MDD is not materially worse
- remove-best and remove-best-2 remain acceptable / preferably positive
- result is not dependent on one ticker or one fold
- 60bp remains positive or clearly robust

Otherwise: `REJECT_EXIT_ENGINE`.

If it passes: `CONTINUE_TO_BUY_EXIT_JOINT_MODEL`.

Do not label anything production-ready.

## Deliverables
Create under `research/omega4/results/`:
- `omega4_summary.json`
- `omega4_fold_metrics.csv`
- `omega4_trades.csv`
- `omega4_equity_curve.csv`
- `omega4_feature_importance.csv` or coefficient table
- `omega4_report.md`

Also create a reproducible runner, preferably:
- `scripts/research_omega4_capital_release.py`

The report must include exact command, git SHA, data filenames, date coverage, row counts, duplicate checks, PIT/universe caveats, and final verdict.

## Non-negotiable integrity rules
- no synthetic performance
- no test-period tuning
- no random train/test split
- no using future high/low as an input feature
- no choosing the best historical sell day as a training answer
- no current-constituent substitution for PIT membership
- no fresh TWD 1m per overlapping trade
- no omitted costs
- no hiding negative folds
- no reporting only the best parameter

If any integrity condition cannot be satisfied, stop and report the blocker rather than forcing a result.
