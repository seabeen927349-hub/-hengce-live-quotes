# X12 Prospective Shadow Validation Protocol — 2026-10-25

## Purpose
Freeze the accepted X12 research frontier inside HENGCE and validate it prospectively with the same governance pattern used for the V-series prospective shadow: no capital, no broker orders, no production promotion, and no additional model search. This is a validation layer, not X13/X14/X15 revival or a new tuning round.

## Frozen model and formal authority
- Frontier lock commit: `fc418d51771a2807ebf3af277c3d1892cef3b2f4` (`research: lock X12 frontier for Hengce shadow integration`).
- Lock timestamp: `2026-10-25T06:26:20Z`.
- Eligible prospective signal dates must be strictly later than `2026-10-25`.
- Frozen X12 source: `research/codex_full_reset_20261023/ranking_x12_prior_q25_skip.py`.
- Frozen X12 Git blob SHA: `facd953a312cf83fd0cd4c979306107d80c6ea58`.
- Formal X12 run: `40163760289`, head SHA `02175a45a63e6435dacad354c96f5581bc57d26f`.
- Formal artifact: `12586973752`, digest `sha256:849fbe8e7ca0adeeabe91241d6d53b23e5cecca2ff4c017b8a99e42053b5dae9`.
- Formal result status: `X12_STRICTLY_DOMINATES_X11_AND_RAISES_WIN_RATE`.
- Frozen pre-lock baseline: 30 complete scheduled baskets; last signal `2026-08-25`, last entry `2026-08-26`, last exit `2026-09-23`.
- Frozen pre-lock X12 events SHA-256: `1a5dfe097ddd4db9443301c8ca1e6346941d6a84013a769908804b7824319002`.
- Formal 1.2% cost result: 24 active trades, 18 wins, 75.00% win rate, compounded return `3.621555903594956`, max drawdown `-0.16528280465128753`, remove-best active-trade return `2.0603872868777515`.
- Formal 1.6% cost compounded return: `3.337164429324934`.
- Any drift in the frozen X12 source or pre-lock event history is a hard failure. Do not silently rebaseline.

## Frozen X12 decision rule
X12 retains the exact X11/V43 scheduled baskets, stock picks, weights, H20 schedule, cost framework, and upstream risk stack. For each scheduled basket, X12 reads the current X10 confidence multiplier. After the same four-observation minimum used by the existing tail layer, it compares the current multiplier with the expanding prior-only 25th percentile of previously observed multipliers. If the current multiplier is below that threshold, the scheduled basket remains in the schedule but its exposure is set to zero. The current observation is appended only after the decision. No future outcome may be used in this gate.

## Observation rules
1. Use the existing X12 model exactly as frozen. No factor, stock-selection, weight, Top-N, holding-period, cap, covariance, regime, ICIR, confidence, exposure, quantile, minimum-history, or skip-rule tuning is permitted.
2. Count only complete scheduled baskets with `signal_date > 2026-10-25`; entry and exit must also be after the lock date.
3. A scheduled X12 skip remains a valid scheduled basket with zero exposure. Active-trade metrics are reported separately and must not be converted into future-availability filtering.
4. Data refreshes must remain PIT/no-lookahead. Historical corrections that change the frozen pre-lock fingerprint invalidate the run and require an explicit research review.
5. Zero capital and zero broker-order authority. No production writes and no changes to Q017, E2, or M1 production.
6. PR #30 remains unmerged. A shadow pass does not authorize merge or production promotion.
7. If no eligible complete post-lock basket exists, the correct state is `WAITING_FOR_POST_LOCK_DATA` (or `WAITING_FOR_COMPLETE_POST_LOCK_OUTCOME` when an upstream scheduled basket exists but its H20 outcome is incomplete).

## Registered read points
- 1–5 complete post-lock scheduled baskets: accumulation only; no verdict.
- First 6 complete post-lock scheduled baskets: interim review is allowed, but it is non-decisional.
- First 12 complete post-lock scheduled baskets: primary registered read. The first 12 are fixed; later baskets are monitoring and do not rewrite this primary window.

## Registered primary gate
On the first 12 complete post-lock scheduled baskets, all of the following must hold:
- 1.2% cost compounded return > 0.
- 1.2% cost remove-best-active-trade return > 0.
- 1.2% cost max drawdown >= -30%.
- 1.6% cost compounded return > 0.

If fewer than two active trades exist in the primary window, remove-best-active-trade return is undefined and the gate cannot pass.

A pass is evidence only. It does not auto-promote X12, change production, authorize capital/orders, or reopen parameter tuning. A fail also does not authorize hindsight retuning; it becomes evidence for a separately governed research decision.

## Execution
The workflow is research-only and read-only (`contents: read`) and supports manual dispatch. A narrowly scoped push trigger exists only for this protocol, shadow script, lock file, and workflow so the initial installation can be validated once. Ordinary future data changes do not auto-trigger the shadow; future reads are deliberate registered validation runs.
