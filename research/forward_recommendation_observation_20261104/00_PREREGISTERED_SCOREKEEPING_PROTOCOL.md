# HENGCE research-only recommendation scorekeeping — initial prospective protocol

**Created on 2026-11-04 during the Taiwan market session.**
**Authority:** RESEARCH_OBSERVATION_ONLY; **no** BUY/SELL, trading/capital authority, Selection Core promotion, new Market State trading rule, or modification of any frozen model.

## Purpose
The user explicitly permits recommendations in order to measure **actual prediction quality**, including failed picks. This is a scorekeeping protocol, not a newly validated model. Keep selection alpha, market risk, and execution separate. Every future candidate must have a reproducible point-in-time source and a time-stamped **pre-outcome** signed-off candidate slate.

## Known source contamination
Two overlapping groups of securities were mentioned conversationally as potential 2026-11-03 dip-watch candidates; original timestamped immutable selection receipt is **not** currently verified. The 2026-11-04 intraday price paths for all seven have already been viewed and **may not be used** to rank, drop, reweight, modify, claim a Nov-04 signal hit, or call an untouched historical holdout.

Group A, **three-name dip watch** (equal weight): 4770, 5876, 4764.
Group B, **five-name next-session watch** (equal weight): 4770, 2317, 2395, 3034, 6873.
Preserve both original groups unchanged, duplicates retained across *group* scorecards; unique-union supplementary analysis only.

## Immutable observation cohort as of registration
Cohort recorded **2026-11-04 12:02:15 Asia/Taipei**, during the trading session. Earliest hypothetical execution for prospective scoring is **next eligible Taiwan trading-session open after registration** (normally 2026-11-05, subject to exchange calendar) — never 2026-11-04 open or 2026-11-03 close.
- Hypothesis tracked: whether a **fixed equal-weight hypothetical basket** of all names in each pre-existing group, entered on that next eligible open, yields positive net total return and excess versus a market-wide passive benchmark over H5 and H20.
- Important: observational baskets are **not** personalized recommendations to place an order. A candidate can be high-risk, halted, illiquid or bankrupt. This protocol measures forecasts, not their safety.
- Entry price: first eligible **official TWSE daily Open** after registration, adjusted only for official corporate actions when required. If the first eligible opening print is missing, do not assume a fill: mark `NO_EXECUTION_PRICE`, report missingness, and predefine how it affects basket comparability (e.g., excluded from execution portfolio but included in intent-to-recommend coverage).
- Outcomes: **close after 5 and 20 completed trading sessions measured from entry session**, and 20-session worst drawdown from official daily Low/Close. Anchor date to **execution** and define H1 as entry session close; H5 as fifth session including entry.
- Ex-ante non-optimized cost: 40 basis points round-trip on the executed basket (20bps entry + 20bps exit), plus separate sensitivity to 80bp; evaluate dividends/corporate actions or flag missing. Do not use prices from unaudited public quotes, user screenshots, privately licensed quotes, or tomorrow's future prices as current inputs.
- Baseline: **official TAIEX**, equivalent **open-of-entry-session to close-of-H5/H20** returns, clearly flagged as a *price-index benchmark without dividends* (not a perfect benchmark for 7 diverse equities). Record a zero-return/cash comparison as secondary.
- Metrics: directional positive-return hit rate; equal-weight mean net return; excess over same-window TAIEX; max adverse excursion/drawdown; group membership, valid/invalid observation counts; negative-result visibility. Present both gross and after-cost results.
- Forbidden: deleting losers, winner-only subsets, retroactive selection times, winner-heavy weights, stealth thresholds, using 11/04 returns as untouched validation, optimizing after first score, or feeding this shadow result into the formal Selection Core.
- Minimum evidence for claim: H5/H20 one cohort = **AN EXAMPLE**, not a measured accuracy rate or robust alpha. Report confidence/sample size before making any skill claim; prospective repeated independent cohorts, time-split validation and benchmark/cost controls required.
- Missing prices/data: **fail closed**, never impute success or zero returns. Insufficient coverage => `UNSCORABLE` with explanation.
- Research gate: further new selection features/hypotheses must meet the original literature-first / preregistration rules. This scorekeeping protocol itself does not authorize new signal discovery.

## What has not happened
No trade has been placed, no formal model selection has been made, no 11/04 result is credited as an untouched prospective win, and no future H5/H20 returns have been read or claimed. The scorer must wait for genuine official future data and report failure as clearly as success.
