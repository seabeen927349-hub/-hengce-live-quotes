# HENGCE Dual Engine 10x Self-Check — 2026-10-18

Status: PASS WITH EXPLICIT RESEARCH-GOVERNANCE LIMITS

1. Q017 contamination check — PASS. E2 cannot alter Q017 universe, filters, score, ranking, hold period, or capital bucket.
2. Q017 parameter consistency — PASS. Canonical values are SOX 1D <= 0, SOX 5D <= -2%, residual <= 4%; stale -3% / DXY-gate prose is superseded.
3. Engine independence — PASS. Q017 and E2 have separate rankings and action lists.
4. Point-in-time causality — PASS. EOD signal only; earliest execution next TWSE session.
5. Trading constraints — PASS. Cash equity, long only, no shorting, no securities lending, no intraday, no margin/leverage.
6. E2 factor freeze — PASS. E2 uses only inst_ratio5, tight_ratio, dist20high with same-date 2-of-3 ordering; no extra stock factor is authorized.
7. SOX-role check — PASS. SOX is an E2 environment/resilience overlay only; no one-way 'SOX down = buy' rule and no hard E2 SOX threshold.
8. Market-regime check — PASS. ROLLING_OVER is explicitly DEGRADED; other regimes are not automatically promoted to BUY.
9. Capital isolation — PASS. Q017 = NT$2m research bucket; E2 = NT$3m research bucket; no silent capital transfer.
10. Handoff/scan contract — PASS. '衡策掃一次' must run and display both engines separately, including actions and remaining capital.

## Research truth labels
- Q017: frozen reference engine; do not mutate from this integration branch.
- E2: frozen challenger, not production-validated OOS.
- E2 2026 reference: N=95, 5D mean +3.88%, median +2.30%, ex-top5 +2.82%, ex-top10 +2.12%.
- Never present E2 same-sample 2026 statistics as prospective expected return.

## Hard stop
No additional factor, window, threshold, weighting, or SOX cutoff may be added under the name of this frozen E2 version. Any future experiment must be a separately named challenger.
