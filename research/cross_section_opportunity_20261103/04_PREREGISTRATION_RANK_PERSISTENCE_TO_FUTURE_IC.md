# HENGCE Rank Persistence → Future Rank IC — Preregistration

Date: 2026-11-03 (Asia/Taipei)
Project: `research/cross_section_opportunity_20261103`
Literature gate: `LITERATURE_GATE_RANK_STRUCTURE.json = PASS_DIAGNOSTIC_ONLY`
Frozen selector: existing PIT U100 + MOM20 ranking from `market_state_selection_interaction_20261102`
Authority: research-only diagnostic; no trading/production authority.

## 1. Question

Does the *current stability of the cross-sectional MOM20 ordering* identify when the same frozen MOM20 ranking will contain more future cross-sectional information?

This tests ranking structure, not raw return dispersion and not a new trading rule.

## 2. Anti-contamination statement

Before this preregistration commit:
- no `RANK_PERSIST5` series defined below was computed;
- no future per-date MOM20 rank IC was computed;
- no persistence-to-future-IC relationship was inspected, grouped, regressed, or plotted;
- no persistence threshold or alternate lag was searched.

The canonical MOM20 Top-5 date-level outcomes were replayed before this preregistration only to reproduce the already-known aggregate benchmark; that replay did not compute the rank-persistence predictor or rank-IC outcome.

After this commit, the primary lag, universe, predictor, outcome, model, and temporal split may not be changed based on results.

## 3. Signal-date universe

Start only from the existing 1,986 primary MOM20 signal dates and reconstruct exactly the frozen PIT U100 on each date using the existing benchmark contract:
- date-correct membership;
- 20-session median turnover liquidity ranking;
- 20 valid MOM20 return observations;
- top 100 by liquidity with the frozen tie-break behavior;
- uniform comma-stripping numeric parser;
- corporate-action-aware log returns using `ex_reference` where present.

No universe expansion or rescue is allowed.

## 4. Current-only predictor: `RANK_PERSIST5`

For each primary signal date `d`:
1. take the frozen current U100 constituents;
2. take each constituent's current `MOM20(d)`;
3. take the same constituent's `MOM20(d-5 trading sessions)`;
4. compute Spearman rank correlation across stocks with both values finite.

Define:

`RANK_PERSIST5(d) = Spearman[MOM20(d), MOM20(d-5)] within current U100`.

Eligibility requires at least 95 paired stocks. Otherwise the date is excluded from this diagnostic with an explicit reason.

Why 5 sessions: this is a single preregistered one-trading-week stability horizon, intended to measure whether the current ordering is persistent rather than a one-day reshuffle. No alternate persistence lag is allowed in the primary test.

## 5. Future outcome: `FWD_RANK_IC20`

For the same signal date and current U100, use the already-frozen corporate-action-safe next-open-to-20-session stock outcomes from the MOM20 benchmark.

Define:

`FWD_RANK_IC20(d) = Spearman[MOM20(d), H20(d)]`

across current U100 stocks with valid H20 outcomes.

Eligibility requires at least 95 finite MOM20/H20 pairs, matching the existing U100 outcome-quality gate.

Interpretation:
- positive IC = higher current MOM20 ranks tend to have higher future H20 returns;
- negative IC = current ordering tends to reverse;
- zero = no cross-sectional ordering information.

This outcome uses the entire U100 ranking and is not the same as Top-5 excess.

## 6. Frozen state control

Use existing S5 state on signal date:
- `DIFFUSE_NORMAL` => `STRESS=0`
- `SYNCHRONIZED_STRESS` => `STRESS=1`.

## 7. Primary model

Estimate exactly:

`FWD_RANK_IC20 = alpha + b1*RANK_PERSIST5 + b2*STRESS + b3*(RANK_PERSIST5*STRESS) + error`.

Use Newey-West/HAC standard errors with lag 20.

Report:
- Normal persistence slope `P_NORMAL = b1`;
- Stress persistence slope `P_STRESS = b1+b3`;
- interaction `P_INTERACTION = b3`;
- HAC 95% CI and p-value for each.

No sign is required in advance.

## 8. Temporal stability

Run the identical model for:
- early: 2018-01-01 through 2022-12-31;
- late: 2023-01-01 through latest mature primary signal date.

For each state-specific slope that has a full-sample HAC 95% CI excluding zero, require the early and late slope signs to match the full-sample sign for a stable conclusion.

## 9. Secondary descriptive outputs

Without inference-driven retuning, report:
1. mean/median `FWD_RANK_IC20` by frozen state;
2. within each state, LOW/MID/HIGH terciles of `RANK_PERSIST5`, where cutpoints are based only on the current predictor distribution inside that state;
3. for each tercile: n, mean/median future IC, and fraction of positive IC dates.

These terciles are descriptive only and cannot become thresholds.

## 10. Conclusion taxonomy

### `RANK_PERSISTENCE_CONDITIONS_FUTURE_IC`
At least one of `P_NORMAL` or `P_STRESS` has a full-sample HAC 95% CI excluding zero and its coefficient sign matches in both early and late periods.

### `RANK_PERSISTENCE_RELATION_UNSTABLE`
A state-specific slope or interaction appears nonzero in the full sample but required temporal sign stability fails.

### `NO_RANK_PERSISTENCE_CONDITIONING_FOUND`
Neither state-specific persistence slope has a full-sample HAC 95% CI excluding zero.

A negative stable relation is a valid result and must not be rescued.

## 11. Authority boundary

This diagnostic cannot create:
- a persistence threshold;
- a new MOM20 variant;
- a BUY/SELL/ranking rule;
- state-specific expert routing;
- exposure/capital changes;
- production promotion.

Any later candidate must be separately frozen and tested on genuinely prospective/OOS evidence.