# HENGCE LOSS FORENSICS — Stage I Large-Layer Internal Rotation V1 Preregistration

Date: 2026-11-01  
Status: **FROZEN PREREGISTRATION / RETROSPECTIVE STRUCTURAL TEST / FORMAL_WEIGHT=0 / NO TRADING AUTHORITY**

## 0. Research question

Within the already-frozen first post-peak Big400-fracture population, does the **internal composition of the same net Big400 loss** carry information about subsequent economic damage?

Plain-language distinction:
- **coherent large-layer exit**: both the >1000-lot layer and the 400–1000-lot layer shrink together;
- **internal large-layer rotation / handoff**: one of those two large-holder layers shrinks while the other expands, partially offsetting the net loss above the 400-lot boundary.

The question is not whether Big400 fell; every event in the frozen cohort already satisfies that. The question is whether the decomposition of that fall contains information beyond the fall magnitude itself.

## 1. Governance boundary

This study MUST NOT:
- rescue or rename the previously failed `capital-share migration` family whose proposed capital-share rank reduced mathematically to turnover/liquidity information;
- alter Stage H Repair Lead-Lag results or definitions;
- invent beneficial-owner identity from public TDCC buckets;
- claim exact account-to-account transfer;
- retune the 400 / 1000 boundaries, which are inherited TDCC/HENGCE ownership layers;
- choose a drawdown threshold after seeing outcomes;
- change the frozen 368-event cohort to improve results;
- create BUY / SELL / ranking / escape-monitor / production authority.

This is a retrospective structural falsification test. Historical TDCC exact first-publication time remains unavailable to the previously frozen actual-availability standard. Therefore even a positive result cannot become formal alpha from this history; prospective validation with actual-known provenance is required for promotion.

## 2. Prior evidence and novelty boundary

Prior ownership-migration work already established that Big1000 and the 400–1000 layer can offset one another and that simple next-week directional continuation is weak. Prior case studies also described ownership handoff / fragmentation examples.

Therefore this V1 does **not** claim virgin novelty for the existence of internal rotation.

The new falsifiable object is narrower:

> Conditional on a frozen post-peak Big400 fracture and its magnitude, does internal large-layer rotation reduce subsequent downside relative to a coherent exit of both large-holder layers?

The exact 368-event cohort-wide downside test defined below has not been inspected before this preregistration.

## 3. Frozen population

Use the already-reconstructed 2026 electronics-100 swing population:
- 548 complete up legs;
- 513 complete down legs;
- exclude 3042 and 6415 -> 503 complete down legs;
- 503 event identity SHA256: `f03abb00e164ac16868274f866f0bb4eba30b0dca0e86257fd5d8573448348e3`;
- first valid post-peak Big400 fracture/outflow events -> 368 events;
- 368 cohort SHA256: `b42ca061bd51d62ebeb4ab4fd128b371260d02a871f2e9f9cf85f904078b4920`.

`t0` remains the frozen first valid post-peak ownership observation with `dBig400 < 0`.

No event may be added, removed, resegmented, or shifted based on Stage I outcomes.

## 4. Ownership decomposition fixed before outcome inspection

At each t0:
- `U = Big1000Pct` (>1000-lot ownership share);
- `L = Big400Pct - Big1000Pct` (400–1000-lot ownership share);
- `S = 100 - Big400Pct` (<400-lot ownership share).

Week-over-week changes from the immediately preceding valid ownership snapshot:
- `dU = U_t0 - U_prev`;
- `dL = L_t0 - L_prev`;
- `dB400 = dU + dL`;
- `dS = -dB400`.

Because the cohort is frozen on `dB400 < 0`, every event has positive net migration across the 400-lot boundary into `S`. Stage I therefore does **not** pretend that `dS` itself is new information.

### Primary continuous decomposition

Define:

`GROSS_LARGE_MOVEMENT = abs(dU) + abs(dL)`

`INTERNAL_OFFSET_SHARE = (GROSS_LARGE_MOVEMENT - abs(dB400)) / GROSS_LARGE_MOVEMENT`

For this cohort `GROSS_LARGE_MOVEMENT > 0` by construction.

Interpretation:
- `0` = no internal cancellation; U and L move coherently in the same direction (or one is exactly zero);
- higher values = larger opposite-direction movement between U and L relative to the net Big400 boundary loss;
- near `1` = most gross movement is internal U/L rotation and only a small remainder crosses below 400.

No percentile threshold or optimized cutpoint is permitted for the primary test.

### Secondary sign-only mechanism classes

These are descriptive robustness classes only; they do not replace the continuous primary predictor:
- `COHERENT_EXIT`: `dU < 0` and `dL < 0`;
- `TOP_TO_MID_HANDOFF`: `dU < 0` and `dL > 0`;
- `MID_EXIT_TOP_ACCUM`: `dU > 0` and `dL < 0`;
- `BOUNDARY_TIE`: `dU == 0` or `dL == 0` within stored data precision.

No magnitude threshold is added.

## 5. Integrity / corporate-action eligibility

Primary ownership-integrity requirement:
- `stable_1pct == True`, using the already-existing ownership audit definition for implied total-share stability within 1% week/week at t0.

The pre-outcome feature audit found 364 of the frozen 368 events satisfy this condition. The four failing events are excluded by this preregistered integrity rule, not by outcome.

Price-outcome integrity:
- require t0 close and the next 20 valid trading sessions;
- if an existing TWSE corporate-action/reference-price protocol flags a discontinuity inside the outcome horizon, the event is censored from the primary price endpoint rather than repaired with a newly invented adjustment;
- events without 20 subsequent trading sessions are right-censored for the primary endpoint.

Counts of every exclusion/censoring reason must be reported.

## 6. Primary economic outcome

Primary outcome is continuous, with no crash threshold:

`FWD20_MDD_LOSS = max(0, 1 - min(Close_{t0+1 ... t0+20}) / Close_t0)`

where the window uses the next 20 valid trading sessions for the same stock.

Interpretation:
- 0 = price never closes below the t0 close during the next 20 sessions;
- 0.20 = worst closing drawdown was 20% below t0 close.

This endpoint is chosen to test future economic damage directly rather than another ownership-state label. No 10%, 12%, 20% or other binary crash threshold is primary.

## 7. Primary hypothesis

### I-H1 — internal rotation is less damaging than coherent exit

Conditional on the magnitude of the frozen Big400 fracture and pre-t0 price/risk context:

`higher INTERNAL_OFFSET_SHARE -> lower FWD20_MDD_LOSS`.

Equivalently, coherent withdrawal of both U and L should be more damaging than a Big400 fracture containing substantial U/L internal offset.

Failure conditions include:
- coefficient direction is zero or adverse;
- any apparent relation disappears once Big400 fracture magnitude is controlled;
- held-out prediction does not improve over the fixed baseline;
- effect is driven by one stock/date block;
- direction reverses materially across chronological blocks.

## 8. Fixed baseline and incremental held-out test

The purpose is incremental information beyond the known fracture, not a new all-purpose price model.

### BASE predictors
Use only values observable at or before t0:
1. `FRACTURE_MAG = -dBig400`;
2. pre-t0 20-session close-return volatility;
3. pre-t0 20-session median traded value;
4. price drawdown at t0 from the frozen swing peak close;
5. t0 margin-balance percentage change versus the preceding valid ownership snapshot's mapped trading date;
6. electronics-universe return over the same baseline-to-t0 interval when already available from the frozen research workspace.

No individual institutional-category identity is used.

If a BASE covariate is unavailable for an event, that event is excluded from BASE and TEST equally; no future-data imputation is allowed.

### TEST predictors
All BASE predictors plus:
- `INTERNAL_OFFSET_SHARE`.

### Model
- fixed Ridge regression;
- `alpha = 1.0`;
- continuous features standardized on training data only;
- no feature selection;
- no interaction search;
- no hyperparameter tuning.

### Evaluation
Strict expanding-time evaluation by t0 date:
- train only on events with strictly earlier t0 dates;
- begin evaluation only after at least 80 eligible prior events;
- test the next t0 date as one block;
- BASE and TEST use identical rows/folds.

Primary held-out metrics:
- MAE of `FWD20_MDD_LOSS`;
- RMSE of `FWD20_MDD_LOSS`.

I-H1 incremental gate passes only if TEST improves **both** aggregate held-out MAE and RMSE versus BASE.

No threshold optimization is allowed.

## 9. Structural coefficient diagnostic

Separately from the held-out predictive gate, fit a fixed full-sample diagnostic regression on eligible historical events:

`FWD20_MDD_LOSS ~ INTERNAL_OFFSET_SHARE + BASE predictors`.

Report:
- coefficient sign and magnitude for `INTERNAL_OFFSET_SHARE`;
- heteroskedasticity-robust interval;
- ticker-clustered interval if estimable;
- sample N and missingness.

This diagnostic does not override the held-out gate.

## 10. Mandatory descriptive robustness

Report without changing the primary gate:
1. FWD20_MDD_LOSS mean/median by the four sign-only mechanism classes;
2. early-versus-late chronological direction;
3. stock concentration and t0-date concentration;
4. result after removing the single most frequent ticker;
5. result after removing the single most populated t0 date;
6. continuous relationship by fixed quartiles of `INTERNAL_OFFSET_SHARE` computed for description only from the full eligible feature distribution; quartiles may not become trading thresholds;
7. secondary next-valid-TDCC `ControlLoss` and four-snapshot ownership durability only as mechanism checks, not primary success gates.

## 11. Interpretation boundary

A positive result may support only:

> When Big400 has already fractured, broad coherent withdrawal across both large-holder layers contains more downside information than a fracture partly explained by internal large-layer rotation.

It may NOT support:
- exact identification of who bought from whom;
- claim that 400–1000 holders are the same beneficial owners as >1000 holders;
- claim that shares below 400 are necessarily retail investors;
- claim that historical Stage I is tradable at t0, because exact historical TDCC first-publication timing is not proven to the formal actual-availability standard.

## 12. Verdict states

Historical Stage I may end only as:
- `STRUCTURAL_SUPPORTED_NOT_CALIBRATED`;
- `EXPLORATORY_WEAK`;
- `FAILED`;
- `DATA_BLOCKED`.

Formal weight remains 0 under every historical verdict.

Any production or probability promotion requires a separate prospective Stage P with immutable actual-known / first-observed provenance and no historical backfill.

## 13. Anti-rescue lock

After Stage I outcomes are opened, V1 may not be rescued by:
- changing the 20-session horizon;
- replacing maximum drawdown with whichever return horizon looks best;
- adding magnitude thresholds to dU/dL;
- moving the 400/1000 boundaries;
- excluding mechanism classes because they perform poorly;
- adding institution identities;
- changing Ridge alpha;
- reducing the 80-event expanding-history start;
- changing the frozen 368 population;
- dropping controls selectively.

If the locked test fails, V1 fails. A materially different question requires a new preregistration rather than an edit.

## 14. Pre-outcome feature audit recorded before lock

Using the frozen 368 cohort and existing ownership audit, without opening Stage I future price outcomes:
- all 368 events map exactly to a t0 ownership row;
- maximum absolute mismatch between frozen `dB400_t0` and audit `dB400` is floating-point noise only;
- `stable_1pct=True`: 364 events;
- sign-only counts before integrity filtering: COHERENT_EXIT 149; TOP_TO_MID_HANDOFF 167; MID_EXIT_TOP_ACCUM 42; BOUNDARY_TIE 10;
- after `stable_1pct=True`: COHERENT_EXIT 147; TOP_TO_MID_HANDOFF 166; MID_EXIT_TOP_ACCUM 41; BOUNDARY_TIE 10;
- `INTERNAL_OFFSET_SHARE` range: 0 to 0.99469; median approximately 0.09324.

These are predictor/prevalence diagnostics only. Cohort-wide Stage I forward drawdown outcomes were not inspected before this lock.

Current authority: `PREREGISTERED_NOT_EXECUTED`  
Formal weight: `0`  
Production authority: `NONE`  
Trading authority: `NONE`
