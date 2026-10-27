# Codex task — HENGCE RR V1 frozen validation

Execute exactly one research-only frozen Residual Reversal configuration from `RR_V1_PREREG_20261023.json`.

## Hard boundaries
- Do not write or merge `main`.
- Do not touch canonical Q017/E2/M1 production behavior.
- Broker execution=false, capital authority=0, signal/ranking authority=false, production promotion=false.
- Do not search, tune, optimize, compare alternates, or substitute another model/config.
- Maximum new model evaluations: **1**.
- Keep PR #30 draft/open/not merged.

## Frozen config
`RESIDUAL_REVERSAL|NEG_RESID1|TO50000000|N1|H20|PRIOR_SOX5_LE_-0.03`

Use the exact feature and execution semantics already implemented in `research/codex_full_reset_20261023/stage_c_rule_search.py`. No semantic rewrite.

## Data route
Use the existing HENGCE repo data path only. `eod/` is confirmed through `20261022`. Reuse the canonical accumulated/Historical Mother route if present and compatible. Do **not** create a parallel EOD tree or second mother and do not redownload an entire alternate market history.

Requested validation interval: `2026-01-01` through `2026-10-22`, with sufficient pre-2026 warmup to reproduce the frozen 60-session beta, returns, liquidity, SOX prior-5-day regime, and PIT electronics eligibility.

If the existing accumulated source cannot provide the required interval/schema/lineage, stop with `BLOCKED_DATA_READINESS`; do not silently fall back to a different dataset.

## V2 evidence rules remain binding
- fail closed on unknown corporate-action entitlement / identity / execution evidence;
- no invented fills or entitlement dates;
- complete-case calculations may be shown only as diagnostics and must never be called an executable whole strategy;
- preserve existing V2 evidence and do not retroactively alter old results.

## Required outputs
Create under `research/codex_full_reset_20261023/rr_v1_20261023/results/`:
1. `RR_V1_READINESS.json`
2. `RR_V1_DATA_LINEAGE.json`
3. `RR_V1_EVENTS.jsonl`
4. `RR_V1_RESULT.json`
5. `RR_V1_REPORT.md`
6. `RR_V1_AUDIT.json`

The result state must be one of:
- `BLOCKED_DATA_READINESS`
- `INSUFFICIENT_PROSPECTIVE_EVIDENCE`
- `FAILED_FROZEN_VALIDATION`
- `PASSED_RESEARCH_VALIDATION_ONLY`

Regardless of outcome, no state grants production/signal/capital/ranking/merge authority.

## Minimum report
Report exact data date range, row counts, PIT universe validation, number of intended/complete/censored baskets, each cost case 0.8/1.2/1.6%, compounded return, win rate, max drawdown, remove-best-trade return, trade/ticker concentration, censor reasons, regime occurrence count, and year/date coverage limitations.

Audit must demonstrate config hash/freeze, no second config, no parameter tuning, one-or-zero new evaluation, no main writes, and offline deterministic tests where possible.
