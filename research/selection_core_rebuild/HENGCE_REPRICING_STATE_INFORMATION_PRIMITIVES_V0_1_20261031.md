# HENGCE Repricing State Selection Core — Information-Primitive Decomposition V0.1

Date frozen: 2026-10-31
Status: `PRIMITIVE_DECOMPOSITION_FROZEN_FORWARD_RETURNS_SEALED`
Selection authority: `RESEARCH_ONLY`
Trading / production authority: `NONE`
Authority head bootstrapped before this document: `243248d58aa5fb053e1cd7ec5bcc2f528730594f`

## 0. Purpose

This document does **not** rescue V43, does **not** rescue MONSTER BUY V1, and does **not** merge / ensemble the two frozen models.

V43 and MONSTER BUY V1 are used only as frozen anatomical specimens to formulate a new, falsifiable hypothesis:

> A stock may enter a repricing state when observable supply can be absorbed without commensurate adverse price impact, weak-hand leverage has been reduced and then begins to re-accelerate, the state is unusually strong relative to the contemporaneous cross-section, the mapping is conditional on market regime, and any adaptive weighting uses only alpha evidence fully observable before the current signal date.

The sentence above is a **hypothesis**, not an established common causal mechanism. V43 and MONSTER do not use the same raw information set, and their historical success cannot be used to declare the hypothesis true.

## 1. Authority / governance inherited

The following latest Selection Core rebuild governance remains controlling:

- `READ_FIRST_HENGCE_SELECTION_CORE_HANDOFF_20261031.md`;
- `HENGCE_IF07_PRE_UNSEAL_GOVERNANCE_ADDENDUM_V0_1_20261031.md` for generic evaluation / promotion mechanics where compatible;
- `HENGCE_IF09_IF10_AUDIT_READOUT_20261031.md`;
- frozen null baseline contract N0/N1/N2/N3;
- no silent mutation;
- no post-hoc winner-aware tuning;
- challenger preregistration before any new challenger forward-return inspection;
- Selection / Escape / Execution layer separation;
- latest-3M, trade-frequency, finite-capital, TAIEX-relative, weak/bear, cross-cycle gates remain mandatory for eventual promotion.

This new research lane does not alter IF-07/IF-08/IF-09/IF-10 conclusions.

## 2. Frozen specimen anatomy — what may be learned, and what may not be inherited

### 2.1 V43 specimen

Frozen V43 lineage is an exposed historical reference only. Its underlying cross-sectional information space is the legacy five-factor family:

- residual reversal;
- 20-session momentum;
- skip-5 / 60-session trend;
- liquidity;
- low volatility.

V43 then applies signal-time, expanding, prior-only, regime-conditioned factor efficacy learning with ICIR and a strong shrink toward V6 weights.

**Permitted anatomical lesson:**
- selection is relative to the contemporaneous cross-section;
- factor efficacy can be state/regime dependent;
- adaptive learning must use only labels fully mature before the signal date.

**Forbidden inheritance:**
- the five V6/V43 factors as the default new core;
- V43 Top3;
- V43 H20 schedule;
- ICIR stabilizer `0.05`;
- shrink `0.90`;
- V6 weights;
- same-regime minimum-anchor counts;
- any legacy V43 exposure/risk scaler.

### 2.2 MONSTER BUY V1 specimen

Frozen MONSTER V1 encodes a discrete early-repricing lifecycle: institutional supply can hit the tape while price remains resilient, margin leverage is first flushed and then begins to return, with legacy hard conditions including Incubation/Markup percentiles, Bridge Absorption, Controlled Re-Leverage, liquidity and first-trigger rules.

**Permitted anatomical lesson:**
- price response must be interpreted jointly with observed supply, not as breakout shape alone;
- leverage stock and leverage impulse are distinct pieces of information;
- a transition can matter more than a static level.

**Forbidden inheritance:**
- Incubation `P97`;
- Markup `P90`;
- Bridge Boolean gate;
- Controlled Re-Leverage Boolean gate;
- Monster first-trigger eligibility rule;
- Monster liquidity threshold;
- Monster event list as training labels for the new core;
- any threshold reverse-engineered from known 6415/6782 or other familiar winners.

## 3. Critical distinction: common mechanism is not common formula

There is no evidence that V43's five legacy price/liquidity factors and MONSTER's flow/margin rules are two measurements of one latent variable. That claim must be falsifiable.

The new core therefore starts from raw PIT observables and a small number of continuous state primitives. It does not import either parent's score.

The new raw-data information families are:

1. price response needed only to measure response to supply;
2. official institutional net-flow evidence (T86 / canonical equivalent);
3. margin balance transition;
4. contemporaneous TWSE-listed-electronics cross-section;
5. TAIEX market regime descriptor;
6. prior-only matured alpha evidence only in RS-M3.

## 4. PIT semantics

For a signal formed after close on date `t`, every field must have been observable through the approved HENGCE vessel by that close. No later correction or weekly observation may be backfilled to an earlier date unless its original availability time proves it was known then.

Required base fields:

- stock close / volume / turnover and PIT universe membership;
- TAIEX close;
- official institutional net shares, using canonical `TotalNet` semantics;
- margin balance;
- any field needed to establish completeness / trading-day alignment.

Missing a required leg produces `MISSING_PRIMITIVE`, never a synthetic zero.

## 5. Primitive P1 — Supply Absorption (`SA`)

Goal: measure **price resilience conditional on observed institutional supply**, rather than raw momentum or turnover shock.

For stock `i` on day `d`:

`r_resid(i,d) = r_close(i,d) - median_j[r_close(j,d)]`

where `j` is the same-date eligible TWSE-listed-electronics PIT cross-section.

`institutional_sell_pressure(i,d) = max(0, -TotalNetShares(i,d)) / VolumeShares(i,d)`

For the trailing 20 TWSE sessions ending at `t`:

`SA_raw(i,t) = sum_d sell_pressure(i,d) * r_resid(i,d) / sum_d sell_pressure(i,d)`

If the denominator is zero, `SA_raw` is missing rather than zero.

The 20-session window is a fixed one-trading-month **continuous estimator**, not a Monster trailing-20 Boolean gate. It will not be searched or changed in place after returns are opened.

Interpretation:
- positive `SA_raw`: stock outperformed its electronics peers specifically while official institutional flow represented supply;
- negative `SA_raw`: institutional supply coincided with adverse residual repricing;
- this is not proof of a hidden operator and must not be described as one.

Novelty burden: because R-017 already killed a turnover-shock / price-state engine, `SA` must demonstrate non-duplication versus legacy price/volume/liquidity features **before** forward returns are opened.

## 6. Primitive P2 — Leverage Transition (`LT`)

Goal: represent a continuous flush-and-reacceleration transition without Monster's hard Controlled Re-Leverage rule.

Define:

`g1(i,d) = log(1 + MarginBalance(i,d)) - log(1 + MarginBalance(i,d-1))`

`g5(i,t) = mean(last 5 valid g1 observations)`

`g20(i,t) = mean(last 20 valid g1 observations)`

`flush(i,t) = -g20(i,t)`

`reaccel(i,t) = g5(i,t) - g20(i,t)`

Within each signal-date eligible cross-section, convert both to mid-ranks in the open interval `(0,1)`:

`u_flush = (rank(flush) - 0.5) / N`

`u_reaccel = (rank(reaccel) - 0.5) / N`

Then:

`LT(i,t) = sqrt(u_flush * u_reaccel)`

This is continuous and contains no inherited P97/P90/Bridge/CRL cutoff. A high value requires both relative prior de-leveraging and relative improvement in the short impulse.

## 7. Primitive P3 — Cross-Sectional Opportunity (`XO`)

`XO` is a **derived geometry primitive**, not an independent raw information family.

On each date:

`u_SA(i,t) = (rank(SA_raw) - 0.5) / N`

`u_LT(i,t) = (rank(LT) - 0.5) / N`

The basic joint opportunity state is:

`XO(i,t) = sqrt(u_SA * u_LT)`

This geometric conjunction is intentionally threshold-free. It rewards simultaneous relative strength in two different state dimensions and penalizes a stock that is extreme in only one.

Important: cross-sectional ranks are representation, not evidence of independent novelty. If `SA` and `LT` are redundant with legacy families, `XO` cannot rescue them.

## 8. Primitive P4 — Continuous Selection Regime (`RG`)

Selection regime is distinct from the frozen Escape overlay. It has **no position-sizing or market-risk authority**.

Define from TAIEX only:

`R63(t) = TAIEX_Close(t) / TAIEX_Close(t-63) - 1`

`RV63(t) = stdev(TAIEX daily returns over the trailing 63 sessions) * sqrt(63)`

`RG(t) = tanh( R63(t) / (RV63(t) + epsilon_machine) )`

`RG` lies in `(-1,1)` and uses no WEAK/STRONG cutoff for selection.

Hypothesized direction, fixed before returns:
- when `RG < 0`, supply absorption should carry relatively more information;
- when `RG > 0`, leverage re-acceleration should carry relatively more information.

This directional statement is a falsifiable model assumption, not a fact.

## 9. Primitive P5 — Prior-only Alpha Persistence (`AP`)

`AP` is the highest leakage-risk primitive and is forbidden from using any label not fully matured before the current signal date.

For feature `f ∈ {u_SA, u_LT}` and each governance reporting horizon `H ∈ {5,10,20,40,60}`:

1. for each past signal date `s`, compute same-date cross-sectional Spearman IC between `f(i,s)` and gross next-open-to-H-session-close return;
2. an IC observation becomes admissible only after its H-session exit is fully observable;
3. at current date `t`, use only admissible IC observations whose exit date is strictly before `t`;
4. use expanding prior-only history; no same-regime minimum count, no V43 `0.05` ICIR stabilizer, no `0.90` shrink, no V6 fallback;
5. average the available mean-IC estimates equally across the five predeclared horizons.

Call the result `AP_f(t) ∈ [-1,1]`.

Warmup: if not all five horizon-level histories have at least one admissible IC observation, RS-M3 falls back exactly to RS-M2 for that signal date. It does **not** fall back to V43/V6.

This is a preregistered online information rule. It may be executed only after the preregistration is frozen.

## 10. Pre-return novelty gate

Before any Repricing State candidate forward returns are opened, run a label-free contemporaneous redundancy audit.

Required comparisons:

- `SA_raw`, `LT`, `XO` versus V43 legacy five-factor ranks where both are available;
- `SA_raw` versus R-017 price/turnover/liquidity representations;
- `LT` versus simple margin-level and margin-change ranks;
- RS-M1 score versus frozen V43 score on matched dates, using only already-frozen legacy outputs;
- RS-M1 score versus MONSTER legacy eligibility only as a structural-overlap diagnostic, never as a target label.

Hard novelty fail if any of the following is true on the matched no-return panel:

1. exact algebraic / monotone duplication is established; or
2. median same-date absolute Spearman correlation between the new challenger score and frozen V43 score is `>= 0.90`; or
3. a linear model using only the five legacy V43 factor ranks reconstructs the new challenger score with date-blocked out-of-sample `R^2 >= 0.80`.

These cutoffs are new pre-return novelty-governance cutoffs, not inherited alpha thresholds. They may not be changed after the audit begins.

If fail: `NOVELTY_GATE_FAIL`, stop; do not inspect forward returns and do not rescue with another transform.

## 11. Data-capability gate

Current authority establishes:

- price history is broadly available back to 2018;
- institutional historical sidecar is substantially available for 2023-2025 and current 2026 canonical data exists;
- historical margin is incomplete and must not be fabricated;
- therefore full 2018-2026 cross-cycle promotion capability for an LT-dependent model is **not yet proven**.

Current state for Repricing State:

`RESEARCH_FEATURE_CAPABILITY = PARTIAL`

`CROSS_CYCLE_PROMOTION_CAPABILITY = DATA_BLOCKED_UNTIL_MARGIN_PIT_COVERAGE_PROVEN`

This does not invalidate the hypothesis; it blocks promotion if the required historical PIT panel cannot be established.

## 12. Frozen exclusions

Until a separately versioned preregistration says otherwise, the new core may not use:

- P97 / P90 / Bridge / Controlled Re-Leverage thresholds;
- Big400 / Big1000 / TDCC hard gates;
- V6/V43 factor weights or V43 ICIR/shrink constants;
- Escape v2.4.7 scores or multipliers;
- technical indicator triggers;
- familiar-winner reverse engineering;
- forward-return-informed feature choice;
- threshold search after unseal.

## 13. Decomposition verdict

`COMMON_MECHANISM = HYPOTHESIS_NOT_FACT`

`PRIMITIVE_NOVELTY = CONDITIONALLY_ADMISSIBLE_PENDING_LABEL_FREE_REDUNDANCY_AUDIT`

`DATA_CAPABILITY = PARTIAL / CROSS_CYCLE_PROMOTION_DATA_BLOCKED`

The only legal next step is to freeze the RS-M0/M1/M2/M3 preregistration and its no-look gate. No Repricing State forward-return result may be inspected before that freeze is persisted.