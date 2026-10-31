# HENGCE Repricing State Selection Core — M0/M1/M2/M3 Preregistration V0.1

Date frozen: 2026-10-31  
Research lane: `REPRICING_STATE_SELECTION_CORE`  
Parent primitive freeze commit: `927b5cf8d59d8a22d950c02e4c100ead358a1796`  
Status at creation: `PREREGISTERED_FORWARD_RETURNS_STILL_SEALED`  
Selection authority: `RESEARCH_ONLY`  
Trading / production authority: `NONE`

## 0. Non-negotiable boundary

This preregistration defines a **new challenger family**. It does not revive V43, does not revive MONSTER BUY V1, and does not combine their scores, candidates, labels, weights, thresholds, event lists, or execution schedules.

V43 and MONSTER BUY V1 remain frozen anatomical references only.

Before this file is committed:

- no Repricing State candidate forward-return table has been opened;
- no Repricing State M0/M1/M2/M3 outcome has been computed;
- no threshold has been fit to known winners;
- no P97/P90/Bridge/Controlled-Re-Leverage rule is inherited;
- no V43 `0.05` ICIR stabilizer, `0.90` shrink, V6 weight, Top3 rule, H20 schedule, or risk scaler is inherited.

Any later change to a score formula, window, selected count, tie-break, missingness rule, null implementation, bootstrap implementation, regime mapping, AP update rule, execution rule, or decision gate requires a new version **before** looking at the affected outcomes. V0.1 may not be silently edited or rescued.

## 1. Governing authority

This preregistration is subordinate to the latest Selection Core rebuild authority and inherits without relaxation:

- formal universe = signal-date `TWSE_LISTED_ELECTRONICS_PIT_DAILY`;
- frozen N0/N1/N2/N3 null contract;
- signal after close / next-TWSE-open entry / 40 bp total round-trip cost;
- mandatory 5/10/20/40/60-session reporting;
- fail-closed PIT semantics;
- no winner-aware tuning / no post-hoc threshold changes / no parent-feature privilege;
- Selection Core / Escape Overlay / Execution separation;
- latest-3M, actual trade frequency, capital efficiency, TAIEX-relative, weak/bear and cross-cycle evidence required before promotion;
- `PASS / FAIL / INCONCLUSIVE / DATA_BLOCKED` are legitimate research outcomes.

Escape v2.4.7 has zero Selection authority in this preregistration.

## 2. Hypothesis to falsify

The challenger hypothesis is:

> A persistent repricing state is more likely when (a) observable institutional supply is absorbed with positive stock-specific price response, (b) margin leverage has been flushed and its short impulse is improving, (c) these states are strong relative to the same-date electronics cross-section, (d) the relative importance of absorption versus leverage transition changes continuously with the contemporaneous TAIEX regime, and (e) any adaptive emphasis is supported only by fully matured prior cross-sectional alpha evidence.

This is not presumed true. Each added mechanism is separately ablated in M0→M3.

## 3. Frozen primitive definitions

The exact primitive definitions in `HENGCE_REPRICING_STATE_INFORMATION_PRIMITIVES_V0_1_20261031.md` are controlling.

Abbreviations used below:

- `uSA(i,t)` = same-date mid-rank of trailing-20-session supply-absorption estimator;
- `uLT(i,t)` = same-date mid-rank of leverage-transition estimator;
- `RG(t)` = continuous TAIEX regime in `(-1,1)`;
- `AP_SA(t)`, `AP_LT(t)` = expanding prior-only alpha-persistence estimates, available only after their underlying horizon labels are fully matured before `t`.

All mid-ranks are:

`u = (rank_ascending - 0.5) / N`

with average ranks for exact value ties. Therefore every valid `u` lies strictly inside `(0,1)`.

Ticker tie-break is used only after final model scores tie: ascending four-digit ticker code.

## 4. Common eligibility cohort — frozen before outcomes

All four RS models and all paired nulls use the **same date-specific eligible cohort**.

A stock is eligible on signal date `t` only if, using information observable by the close of `t`:

1. it is a PIT member of `TWSE_LISTED_ELECTRONICS_PIT_DAILY` on `t`;
2. every price / volume / official institutional-flow field required to compute the full trailing-20-session `SA_raw` path is valid;
3. every margin-balance field required to compute the full `g1`, `g5`, `g20`, `flush`, `reaccel`, and `LT` path is valid;
4. current close and next-session calendar mapping needed for later execution geometry are structurally resolvable, but no future price value is inspected at preregistration / novelty stages;
5. the TAIEX history needed for `RG(t)` is valid.

No missing institutional or margin value is converted to zero. No later observation is backfilled into an earlier PIT state without proof it was already public then.

Eligibility is name-level fail-closed. A date is evaluable only when at least `K=5` names remain eligible. No additional liquidity, percentile, price, market-cap, P97/P90, Bridge, or Monster-style eligibility gate is allowed.

Mandatory coverage reporting on every stage:

- PIT electronics count;
- RS eligible count;
- eligible/PIT coverage ratio;
- exclusions by missing primitive leg.

Low coverage is not repaired by loosening rules. It may lead to `DATA_BLOCKED` / `INCONCLUSIVE` at later validation.

## 5. Signal-date geometry and selected count

Signal-date surface:

- evaluate every TWSE trading session for which the common eligibility cohort satisfies §4;
- there is no V43 non-overlap schedule and no Monster first-trigger rule in candidate generation.

Selected count:

`K = 5` names per valid signal date.

Rationale classification: `NEW_PRE_RETURN_EVALUATION_GEOMETRY`, not inherited from V43 or MONSTER and not chosen from challenger outcomes.

Every model selects the five highest final scores. Exact final-score ties are broken by ascending ticker.

The daily top-5 surface is the research Selection output. Portfolio overlap / capital occupancy is handled separately in §13 and may suppress execution without changing the Selection score or rank.

## 6. RS-M0 — Supply Absorption only

Model ID: `RS_M0_SA`

Score:

`Score_M0(i,t) = uSA(i,t)`

Purpose:

- establish whether supply-conditioned residual price response contains incremental selection information at all;
- no leverage transition, regime weighting, or alpha persistence is used.

M0 is **not** a null. It must beat the frozen simple nulls to survive.

## 7. RS-M1 — Joint Repricing State

Model ID: `RS_M1_SA_LT`

Score:

`Score_M1(i,t) = sqrt( uSA(i,t) * uLT(i,t) )`

Purpose:

- test whether a conjunction of supply absorption and leverage transition adds information beyond M0;
- the geometric mean is fixed before outcomes and prevents a single extreme dimension from fully compensating for a weak second dimension.

No discrete Bridge, CRL, percentile, or trigger gate is permitted.

## 8. RS-M2 — Continuous Regime-conditioned Repricing State

Model ID: `RS_M2_REGIME`

Base weights from TAIEX regime only:

`bSA(t) = (1 - RG(t)) / 2`

`bLT(t) = (1 + RG(t)) / 2`

so `bSA + bLT = 1` and both lie in `(0,1)`.

Score:

`Score_M2(i,t) = exp( bSA(t) * ln(uSA(i,t)) + bLT(t) * ln(uLT(i,t)) )`

Fixed directional hypothesis:

- negative TAIEX regime continuously emphasizes supply absorption;
- positive TAIEX regime continuously emphasizes leverage transition.

There is no WEAK/STRONG selection cutoff and no Escape multiplier. If this direction is wrong, M2 fails; the sign may not be flipped after outcomes.

## 9. RS-M3 — Prior-only Alpha Persistence

Model ID: `RS_M3_ALPHA_PERSISTENCE`

### 9.1 Horizon-level prior IC

For each feature `f ∈ {uSA, uLT}` and horizon `H ∈ {5,10,20,40,60}`:

1. on each past eligible signal date `s`, compute Spearman cross-sectional IC between `f(i,s)` and gross next-open-to-H-session-close return across stocks with a fully valid matured outcome;
2. the entire H-session label is inadmissible until its exit session is fully observable;
3. for current signal date `t`, an IC observation may enter training only if its exit date is strictly earlier than `t`;
4. current-date, overlapping-unmatured, future, revised-later, or censored labels are never used;
5. no same-regime sample filter is used.

For a horizon with at least one admissible historical IC observation:

`MeanIC_f,H(t) = arithmetic mean of all admissible prior ICs at H`

AP becomes active only when **all five horizons** have at least one admissible `MeanIC` for both features.

Then:

`AP_f(t) = mean_H MeanIC_f,H(t)`

No ICIR, stabilizer, shrink, V6 prior, or minimum same-regime anchor count is used.

### 9.2 Persistence-conditioned weights

Start from M2 regime weights `bSA`, `bLT`.

When AP is active:

`rawSA(t) = bSA(t) * (1 + AP_SA(t))`

`rawLT(t) = bLT(t) * (1 + AP_LT(t))`

If `rawSA + rawLT > 0`:

`wSA = rawSA / (rawSA + rawLT)`

`wLT = rawLT / (rawSA + rawLT)`

and:

`Score_M3(i,t) = exp( wSA(t)*ln(uSA(i,t)) + wLT(t)*ln(uLT(i,t)) )`

If AP is not yet active, or the normalization denominator is non-positive, M3 **falls back exactly to M2** for that date. It never falls back to V43/V6 and no alternate tuning is allowed.

Mandatory M3 reporting separates:

- `M3_FALLBACK_TO_M2` dates;
- `M3_AP_ACTIVE` dates.

Any incremental M3 claim must be demonstrated on `M3_AP_ACTIVE` dates; warmup equality cannot be counted as evidence for alpha persistence.

## 10. Pre-return novelty gate — exact mechanics

No RS forward returns may be opened until the label-free novelty audit passes.

### 10.1 Exact/monotone duplication

Analytically or computationally establish whether `SA_raw`, `LT`, `M0`, or `M1` is an exact algebraic / monotone transform of a legacy V43 factor or the killed R-017 price/turnover/liquidity representation. Any established exact duplication = `NOVELTY_GATE_FAIL`.

### 10.2 Same-date score correlation

On every matched date with valid scores for both systems:

- compute Spearman correlation between RS-M1 score and frozen V43 score across common names;
- take absolute value per date;
- report median across dates.

Hard fail if median absolute same-date Spearman `>= 0.90`.

### 10.3 Legacy-factor reconstruction

Predict `Score_M1` using only an intercept plus the five frozen legacy V43 factor ranks (`resid_rev`, `mom20`, `skip5_60`, `liquidity`, `lowvol`) with ordinary least squares.

Date-blocked out-of-sample construction:

- partition rows by calendar year of signal date;
- for each calendar year `y`, train OLS on all other available years and predict only year `y`;
- concatenate all held-out-year predictions;
- calculate standard pooled `R^2 = 1 - SSE/SST` against actual M1 score.

No interactions, splines, regularization, feature selection, or transformations are allowed.

Hard fail if pooled held-out-year `R^2 >= 0.80`.

If fewer than two calendar years have valid overlap, this subtest is `DATA_BLOCKED`, and novelty cannot receive a full PASS.

### 10.4 Novelty verdict

`PASS` requires:

- no exact/monotone duplication;
- median absolute V43 correlation `< 0.90`;
- legacy-factor held-out-year `R^2 < 0.80`;
- sufficient data to compute all required subtests.

Any hard fail stops the RS lane before forward returns. No new transform may be introduced as a rescue inside V0.1.

## 11. Frozen null implementations

The parent null definitions remain N0/N1/N2/N3 and always use the same RS eligible cohort and signal dates.

### N0 — Cross-section EW

Equal-weight forward return of every stock in the same RS eligible cohort on each RS signal date.

### N1 — MOM20 TOP-K

From the same eligible cohort, select `K=5` stocks with highest prior-20-session close-to-close return. Tie-break: ascending ticker.

### N2 — REV5 BOTTOM-K

From the same eligible cohort, select `K=5` stocks with lowest prior-5-session close-to-close return. Tie-break: ascending ticker.

### N3 — deterministic matched random

Frozen parent requirements remain:

- same eligible cohort;
- same `K=5`;
- seed `20261031`;
- `10,000` draws.

This preregistration freezes the previously underspecified random mechanics **before RS outcomes are opened**:

1. cohort tickers are sorted ascending as four-digit strings;
2. draws are indexed `b = 0..9999`;
3. for each `(signal_date, b, ticker)`, compute SHA-256 of the UTF-8 string:
   `N3|20261031|<signal_date>|<b>|<ticker>`;
4. interpret the full 256-bit digest as an unsigned big-endian integer;
5. choose the `K=5` tickers with the smallest digest values; ticker ascending breaks an impossible digest tie;
6. this is sampling without replacement within each date/draw;
7. for each horizon, compute the equal-weight net return of the selected five names after the same 40 bp round-trip cost;
8. aggregate one N3 draw across signal dates by the arithmetic mean of its date-level basket returns;
9. report the full 10,000-draw empirical distribution and the one-sided empirical exceedance probability:
   `p_N3 = (1 + count(draw_mean >= challenger_mean)) / 10001`.

No other RNG, stream ordering, sampling library, or lucky random draw is permitted.

## 12. Forward-return and reporting geometry — frozen

Forward returns remain sealed until §10 novelty PASS and a pre-return execution audit confirms implementation parity with this document.

When legally unsealed:

- signal = after close on `t`;
- entry = next TWSE session open;
- exits = close after 5 / 10 / 20 / 40 / 60 TWSE sessions from entry according to the frozen trading-session calendar;
- round-trip cost = exactly 40 bp total for all challenger/null basket net returns;
- no technical stop, take-profit, dynamic exit, or alternate holding rule is allowed;
- missing entry/exit/path needed for a required metric = fail closed, never synthetic;
- all M0/M1/M2/M3 and null comparisons use the same matched signal dates for each reported comparison.

### Primary research horizon

`H20` is the preregistered primary Selection-discrimination horizon because it represents one trading month and is already one of the frozen null-contract horizons. This does **not** import the V43 schedule or Monster BUY gate.

`H5/H10/H40/H60` are mandatory secondary robustness horizons and may not be hidden.

Required reporting for every model follows the frozen null contract and includes at minimum:

- event/basket count;
- unique tickers;
- signal-date count;
- monthly frequency;
- mean / median / win rate;
- remove-best 1 / 3 / 5;
- MAE / MFE;
- date-block excess versus N0 and N1;
- N3 empirical distribution / `p_N3`;
- latest 3 months;
- year-by-year;
- regime splits;
- coverage / missingness;
- trade count / frequency / capital utilization / capital efficiency at portfolio stage;
- TAIEX-relative and cross-cycle evidence before promotion.

## 13. Portfolio overlap and finite-capital mechanics — frozen

For promotion-oriented portfolio replay, use the existing HENGCE fixed-capital convention:

- initial research capital = `NT$1,000,000`;
- no borrowing / leverage;
- round lot = 1,000 shares;
- no upward compounding of deployable budget above NT$1,000,000;
- realized losses reduce deployable capital until recovered;
- on a common entry session, new eligible names receive equal provisional cash slices before round-lot flooring;
- unused residual cash from one slice is not reassigned to another same-session name;
- if one round lot cannot be purchased from its slice, record `SKIPPED_NOT_EXECUTABLE_CAPITAL`;
- an already-held ticker receives no additional notional until its tested-horizon position exits.

A separate portfolio replay is run for each H horizon. Candidate Selection rank itself is never changed by capital availability.

Latest-3M uses the frozen 63-TWSE-session convention. For this RS challenger, latest-3M promotion evidence is sufficient only with at least 10 actually executed matured H20 trades and at least 5 distinct executed signal dates. Lower activity is `INCONCLUSIVE`, not PASS.

Latest-3M finite-capital net PnL must be `> 0`, and contemporaneous TAIEX excess must be `> 0`; otherwise the promotion gate fails. Strong-market latest-3M net PnL `<= 0` is a KILL condition under inherited governance.

## 14. Bootstrap mechanics — frozen before outcomes

The inference unit is a **signal date block**: all names in a model/null basket on the same signal date remain together.

For each horizon and each paired comparison, first compute one scalar date-level excess return per common signal date.

Bootstrap target statistic:

`mean(date_level_excess)`.

Replicates:

`B = 10,000`.

Deterministic resampling:

- sort the `D` common signal dates ascending;
- for replicate `b=0..9999` and resample position `p=0..D-1`, compute SHA-256 of:
  `BOOT|20261031|<comparison_id>|<H>|<b>|<p>`;
- take the first 64 digest bits as unsigned integer `x`;
- set `u = x / 2^64`;
- choose date index `floor(u * D)`;
- sampling is with replacement and exactly `D` date blocks are drawn per replicate.

95% CI:

- sort the 10,000 bootstrap replicate means ascending;
- lower endpoint = zero-indexed element `249`;
- upper endpoint = zero-indexed element `9749`.

No BCa/basic/studentized alternative may be selected after outcomes.

## 15. Complexity / model-selection gates — frozen

This ladder is evaluated once. It is not a tournament in which the best-looking return is automatically selected.

### 15.1 Independent null-survival gate for each Mk

A model `Mk` can be called `NULL_SURVIVOR` only if, at H20:

1. mean date-level excess versus N0 is `> 0` and its frozen 95% bootstrap CI lower endpoint is `> 0`;
2. mean date-level excess versus N1 is `> 0` and its frozen 95% bootstrap CI lower endpoint is `> 0`;
3. `p_N3 <= 0.05`;
4. mean excess versus N1 is positive in at least 3 of the 5 mandatory horizons;
5. no required result is invalidated by PIT / missingness / implementation failure.

N2 remains mandatory reporting but is not a promotion hurdle because it is an intentionally opposite simple reversal comparator rather than the principal positive-selection null.

### 15.2 Incremental complexity gate

A more complex RS model may supersede the immediately preceding model only if:

1. H20 mean date-level excess versus the immediate predecessor is `> 0`;
2. the frozen 95% bootstrap CI lower endpoint for that H20 incremental excess is `> 0`;
3. incremental mean excess is positive in at least 3 of 5 horizons;
4. the more complex model independently passes §15.1.

M3's incremental comparison is computed on `M3_AP_ACTIVE` dates for the AP-specific claim, with a separate all-date comparison also reported.

If a complex model passes nulls but does not pass its incremental gate, complexity is not rewarded: retain the simpler surviving model.

If an intermediate model fails but a later frozen model passes, the later model is still reported; it may become the candidate only if it passes its own null gate **and** has positive H20 mean excess versus every simpler RS model, with the immediate-predecessor CI condition above also satisfied. No formula may be changed to rescue the chain.

### 15.3 Final research choice

Among models meeting all applicable gates, choose the **simplest** model not statistically dominated under §15.2.

If none survive: `REPRICING_STATE_SELECTION_CORE_V0_1 = FAIL`.

No “near pass” creates authority.

## 16. Regime / cross-cycle / recent-3M promotion law

Research survival is not production promotion.

Before any future promotion claim, the selected frozen RS model must additionally satisfy inherited governance:

- latest-3M finite-capital PnL positive;
- adequate actual trade count and signal-date frequency;
- positive capital efficiency;
- beat contemporaneous TAIEX in the required portfolio windows;
- weak and bear regime evidence;
- cross-cycle evidence extending as far toward 2018–2026 as the required PIT data can legitimately support;
- cost / remove-best / concentration robustness;
- no dependence on one or a few lucky trades;
- clean forward/OOS evidence after freeze.

Current known historical margin capability is incomplete. If the required PIT margin history cannot support the mandated cross-cycle test, final promotion remains `DATA_BLOCKED`; historical gaps may not be fabricated or filled by a different feature.

## 17. Prohibited post-unseal actions

After the first RS forward-return computation, V0.1 forbids:

- changing 20/5/63-session primitive windows;
- changing K=5;
- changing score transforms or regime direction;
- changing AP horizon set, averaging, activation or fallback;
- introducing P97/P90/Bridge/CRL or any Monster gate;
- importing V43 weights, ICIR stabilizer, shrink or score;
- threshold search / quantile search / top-k search;
- dropping weak years, regimes, bad months or bad tickers;
- replacing 40 bp cost with a friendlier cost;
- changing the null population;
- changing N3 / bootstrap mechanics;
- redefining primary horizon after seeing results;
- adding a new feature because one known winner was missed;
- reclassifying failure as success through a new metric.

A failed V0.1 may motivate a genuinely new, separately preregistered V0.2 hypothesis, but V0.1 remains failed and immutable.

## 18. Legal next step after this commit

1. persist and re-read this exact preregistration;
2. run a **no-forward-return** implementation / PIT / completeness audit;
3. run the label-free novelty gate in §10;
4. persist the novelty verdict and feature-panel hashes;
5. only if novelty = PASS and execution audit = PASS, explicitly unseal the first RS forward-return evaluation;
6. otherwise stop as `NOVELTY_GATE_FAIL`, `DATA_BLOCKED`, or `EXECUTION_SPEC_BLOCKED`.

At this commit, forward returns remain sealed.