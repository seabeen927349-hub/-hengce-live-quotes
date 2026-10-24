# V43 Prospective Shadow Validation Protocol — 2026-10-24

## Purpose
Freeze the accepted V43 research frontier and validate it prospectively without capital, broker orders, production promotion, or additional model search. This is a validation layer, not V45.

## Frozen model and baseline
- Frontier lock commit: `2e48350b8eab28c7fd81d1144e15aa3fa892b855` (`research: lock V43 frontier after V44 rejection`).
- Lock timestamp: `2026-10-24T02:47:24Z`.
- Eligible prospective signal dates must be strictly later than `2026-10-24`.
- Frozen V43 source Git blob SHA: `60c3ce478c5f88bfce9263739a310ea5f5cf05a6`.
- Frozen pre-lock baseline: 30 complete baskets, last exit `2026-09-23`.
- Frozen pre-lock V43 events SHA-256: `ed5b0c4caff523525ecafb303e04dc82bc07d7d2fe706733edf4ce0180ecfd6e`.
- Any drift in the V43 source or pre-lock event history is a hard failure. Do not silently rebaseline.

## Observation rules
1. Use the existing V43 model exactly as frozen. No factor, weight, Top-N, holding-period, cap, covariance, regime, ICIR, exposure, or V30 risk-overlay tuning is permitted.
2. Count only complete baskets with `signal_date > 2026-10-24`; entry and exit must also be after the lock date.
3. Data refreshes must remain PIT/no-lookahead. Historical corrections that change the frozen pre-lock fingerprint invalidate the run and require an explicit research review.
4. Zero capital and zero broker-order authority. No production writes and no changes to Q017, E2, or M1 production.
5. PR #30 remains unmerged. A shadow pass does not authorize merge or production promotion.
6. If no eligible complete post-lock basket exists, the correct state is `WAITING_FOR_POST_LOCK_DATA` (or `WAITING_FOR_COMPLETE_POST_LOCK_OUTCOME` when a post-lock basket exists but is incomplete).

## Registered read points
- 1–5 complete baskets: accumulation only; no verdict.
- First 6 complete baskets: interim review is allowed, but it is non-decisional.
- First 12 complete baskets: primary registered read. The first 12 are fixed; later baskets are monitoring and do not rewrite this primary window.

## Registered primary gate
On the first 12 complete post-lock baskets, all of the following must hold:
- 1.2% cost compounded return > 0.
- 1.2% cost remove-best-basket return > 0.
- 1.2% cost max drawdown >= -30%.
- 1.6% cost compounded return > 0.

A pass is evidence only. It does not auto-promote V43. A fail does not authorize parameter tuning or an unregistered V45; it only becomes new evidence for a separately governed research decision.

## Execution
The workflow is research-only, read-only (`contents: read`), and supports manual dispatch. A narrowly scoped push trigger exists only for this protocol/script/workflow so the initial gate can be validated once when installed; future data changes do not automatically trigger it.
