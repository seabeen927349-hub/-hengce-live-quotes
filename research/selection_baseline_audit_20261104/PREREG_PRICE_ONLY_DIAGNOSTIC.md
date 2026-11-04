# HENGCE 2018–2026 historical selection baseline diagnostic — pre-return registration

Date: 2026-11-04; status: `RESEARCH_DIAGNOSTIC_ONLY`; production authority: NONE.

This is a separate fixed-portfolio educational benchmark, NOT a replacement for the immutable Selection Core `HENGCE_SELECTION_CORE_NULL_BASELINE_CONTRACT_V1_20261031` or IF-07 preregistration. Existing challenger returns remain sealed. Frozen before this diagnostic's candidate forward returns are computed.

## Universe and calendar

- TWSE electronics per year-specific archived MI_INDEX type-13 membership file; 4-digit ordinary-number ticker filter; TPEx excluded. This archive is **not** independently certified security-class registry; do not claim strong PIT certification.
- Dates follow the union of archived daily TWSE sessions.
- At every month's **last valid TWSE session close** (from all sessions in archive), rank contemporaneously eligible securities by median *reported nonmissing* daily turnover in the latest 60 TWSE sessions including current EOD; >=50 nonmissing observations to be admitted; top 100, ticker-ascending tie-break.
- Initial signal only when 60 full sessions exist and all prerequisites were measured; signal after close, entry next TWSE open, fixed exit close on 20th entry-and-later TWSE session; holding overlap forbidden (skip any monthly signal before prior exit closes), no ex-post signal deferral.

## Benchmarks and capital treatment

- N0: mean equal-weight gross return of all 100 eligible names on each fixed signal/exit pair; **theoretical descriptive** with 40 bp per-name cost and NOT a one-million board-lot portfolio. Report missing future open/exit prices separately; no survivor-only promotion.
- N1: highest prior 20-session close/close return in same PIT top100 pool; Top 5 (ticker tie-break).
- N2: lowest prior 5-session close/close return in same pool; Bottom 5.
- N3: 10,000 global reproducible matched random 5-name draws; numpy PCG64 seed `20261031`; date-order and ticker-order stable; no tuning to performance.
- For N1/N2/N3 only, initial NT$1,000,000, no borrowing or shorting, five equal-budget sleeves based on available capital at each eligible investment event; 1 lot = 1000 shares; any unpurchasable remainder remains cash, no rerank; round-trip total cost = 0.004 * opening notional, alternative sensitivity = 0.008. End capital = old capital plus sum(position open-to-exit PnL net of cost).
- Missing entry open: no purchase; capital remains cash and incident logged. Missing exit close: flag as blocked/uncertain, do not infer last close, zero or sell price; report unknown coverage.
- All observed corporate action records in (signal close, exit close] are kept as explicit exposure flags. Raw open/close **price-only** returns exclude distributions and changes in shareholder entitlements; they do not establish true total return. Report flags and disallow formal investment alpha PASS pending full corporate-action-adjusted replay. Excluding flagged stocks from the sample after looking at their exits is forbidden.
- Any previously delisted/suspended names in contemporary archive are included when observed; no winner-aware stock substitutions.

## Evaluation

- Full available: 2018–2026-10-27. Discovery descriptive 2018–2024; late historical 2025–2026. Since research history may be widely exposed, **not pristine forward OOS**.
- Report annual event counts, selection counts, orders, wins, losses, total net PnL, capital utilization, single-event concentration, remove best 1/3/5, drawdown, retained cash, corporate-action and missing-price incidence, N3 distribution and 2025–2026 splits, TAIEX as uninvestable descriptive price-index comparator.
- Explicitly label all results `RESEARCH_PRICE_ONLY` until PIT security registry, source revisions, cash/share distributions, true next-open tradability and baseline pre-registration are independently certified.
- Validation success may NOT be declared from event-means, same-history random comparisons, price-only returns, or choosing the best among multiple strategies after inspection.

Prohibitions: no parameter search, threshold retuning, winner-aware cleanup, no filling missing zeros, no production/main/canonical mutation, no new Selection challenger backdoor.
