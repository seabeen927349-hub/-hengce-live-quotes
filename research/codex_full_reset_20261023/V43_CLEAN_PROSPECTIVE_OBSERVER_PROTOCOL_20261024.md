# V43 Clean Prospective Observer Protocol — 2026-10-24

Purpose: continue validation of frozen V43 without reopening model selection.

Hard boundaries:
- research-only; capital authority 0; no broker orders; no production promotion;
- no main/Q017/E2/M1 writes; PR #30 remains unmerged;
- no V45, no parameter search, no local retuning;
- frozen V43 source blob must remain `60c3ce478c5f88bfce9263739a310ea5f5cf05a6`.

Observer design:
1. Rebuild features directly from frozen 2023–2025 research history plus a read-only current 2026 CSV snapshot. Do not import historical screening modules.
2. Reconstruct the fixed V6 common schedule, V43 prior-only ICIR ranking, V19 exposure, V27 50% capped covariance construction, and V30 fragile-strong risk overlay directly from frozen constants.
3. Before any prospective evidence is accepted, rebuild the historical baseline with the original 2026 cutoff `2026-10-22`. It must reproduce exactly 30 events with SHA-256 `ed5b0c4caff523525ecafb303e04dc82bc07d7d2fe706733edf4ce0180ecfd6e` and last exit `2026-09-23`.
4. Separately extend the 2026 common schedule through the newest available data. A pre-lock signal that only becomes complete after the lock is a bridge basket: it occupies the frozen schedule but is not prospective evidence.
5. Prospective evidence requires `signal_date > 2026-10-24`, and only fully completed H20 baskets count.
6. Prospectively, V43 annual GLOBAL fallback is not authorized. If fewer than 3 same-regime realized anchors are available or positive ICIR statistics collapse, fail closed rather than invent a fallback.
7. Preserve full daily marked path for drawdown monitoring; do not validate only on terminal basket PnL.
8. Report STRONG and WEAK regimes separately, but do not change exposure/ranking based on those diagnostics.

Registered reads:
- 1–5 complete post-lock baskets: accumulation only.
- First 6: interim review only, non-decisional.
- First 12: primary registered read.

Primary first-12 gate (unchanged):
- 1.2% compounded return > 0;
- 1.2% remove-best-basket return > 0;
- 1.2% max drawdown >= -30%;
- 1.6% compounded return > 0.

A pass is evidence only. It never auto-promotes V43 or authorizes capital/orders/production changes.
