# Stage H H1/H2/H3 Execution Lock — 2026-11-01

Status: FROZEN BEFORE H1/H2/H3 DOWNSTREAM OUTCOME INSPECTION
Authority parent: `OWNERSHIP_PRICE_REPAIR_LEAD_LAG_PREREGISTRATION_V1_20261101.md`
Production authority: NONE
Formal weight: 0

## Frozen population / provenance
- 12% close-price zig-zag exact reconstruction: 548 complete up legs, 513 complete down legs.
- Exclude 6415 and 3042: 503 complete down legs.
- 503 event identity SHA256: `f03abb00e164ac16868274f866f0bb4eba30b0dca0e86257fd5d8573448348e3`.
- First valid post-peak Big400 fracture/outflow population: 368 events, exactly reproducing the later authority split 139 repair + 229 failed repair.
- Frozen 368 cohort SHA256: `b42ca061bd51d62ebeb4ab4fd128b371260d02a871f2e9f9cf85f904078b4920`.
- Primary sequence window remains the second valid ownership snapshot after t0; secondary robustness remains the fourth. No re-segmentation, threshold retuning, or outcome-aware event edits.

## Existing CONTROL+HOOK authority
Use frozen `HENGCE CONTROL / RETAIL CORE V0.11.1` semantics without alteration. Historical state replay must reproduce the packaged V0.11 outputs before use.

Exact existing definitions used downstream:
- `ControlLoss = (dBig400Pct < 0) AND (dBig1000Pct < 0)`.
- `RetailHook = (dTotalHolders > 0) AND (MarginChgPct_calc > 0)`.
- `ControlCore = (Big400Pct + Big1000Pct)/2`.
- `ControlPosition8` and all existing V0.11 state fields follow the frozen package implementation.
- No identity choreography is added.

## Sequence-state comparison groups
Directional primary comparison:
- OWN group = `OWNERSHIP_FIRST` + `OWNERSHIP_ONLY`.
- PRICE group = `PRICE_FIRST` + `PRICE_ONLY`.
- `COARSE_TIE` and `NEITHER` remain reported but are not silently assigned to either directional group.
- Corporate-action-censored and UNKNOWN_TIMING events are excluded from directional outcome tests, with counts reported.

## Sequence observability time
- Two-sided repair: sequence becomes observable when both repairs have become observable; state is aligned to the latest valid TDCC snapshot available at that time.
- `COARSE_TIE`: observable at the ownership snapshot establishing the tie interval.
- One-sided / `NEITHER`: observable at the primary window-end ownership snapshot.
- Existing CONTROL+HOOK state is never manufactured between TDCC snapshots.

## H1 lock — subsequent broad control loss
Primary outcome: at the next valid TDCC snapshot after sequence observability, frozen V0.11 `ControlLoss`.

Primary report:
1. raw next-snapshot ControlLoss rate by sequence state and by OWN vs PRICE group;
2. continuous-covariate adjusted logistic diagnostic using only the preregistered PIT covariate families available before the outcome: initial Big400 fracture magnitude, initial Big1000 change, holder-fragmentation change, margin/leverage change, pre-t0 20-session volatility, pre-t0 20-session median traded value, peak-to-trough price drawdown, and electronics-regime return. No outcome-derived binning or cutpoint search.

H1 direction: OWN group must have lower subsequent broad-control-loss probability than PRICE group. Otherwise H1 is not supported.

## H2 lock — renewed leakage before durable reconcentration
Use the frozen CONTROL durability concept, not a new threshold.
- Renewed leakage: a subsequent valid snapshot with `dBig400Pct < 0`.
- Durable reconcentration: a positive Big400 build at snapshot t whose next valid snapshot retains `Big400Pct >=` the pre-build Big400Pct at t-1, matching the existing CONTROL durability target.
- Starting immediately after sequence observability, inspect up to the next four valid ownership snapshots. A durable reconcentration is counted only if its confirmation is observable inside that four-snapshot horizon.
- Outcome `LEAK_BEFORE_DURABLE = 1` if renewed leakage occurs before confirmed durable reconcentration; `0` if durable reconcentration is confirmed first; unresolved cases are right-censored and reported, not coerced.

H2 direction: PRICE group must have a higher leakage-before-durable rate than OWN group. Otherwise H2 is not supported.

## H3 lock — incremental held-out probability quality
Target: next-valid-snapshot frozen V0.11 `ControlLoss` after sequence observability.

Eligibility:
- Existing V0.11 state must be PIT-valid and `DataOK` at sequence observability.
- A next valid TDCC snapshot must exist.
- Use only periods where the frozen V0.11 state engine is replayable under its own 2026 contiguous-vessel semantics; do not backfill synthetic V0.11 states into Jan-Apr.

BASE predictors:
- one-hot frozen V0.11 `MODEL_STATE`;
- `ControlPosition8`, `PrevControlPosition8`, `RetailHook`, and current `ControlLoss`.

TEST predictors:
- all BASE predictors;
- one-hot Stage H sequence state;
- signed lead-lag sessions when observed, plus a missing-lead-lag indicator. Missing lead-lag is never imputed from future information.

Probability model/evaluation:
- fixed L2 logistic regression, C=1, no class weighting;
- continuous fields standardized from training data only; categorical fields one-hot encoded from training data only;
- strict expanding-time evaluation by sequence-observability TDCC date: train only on strictly earlier dates, test the next date; begin only after at least 60 eligible prior events and both target classes exist;
- same folds for BASE and TEST;
- primary probability metrics: Brier score and log loss; AUC is secondary only.

H3 is supported only if TEST improves both aggregate held-out Brier score and aggregate held-out log loss versus BASE. No threshold optimization and no return target is permitted.

## Governance
No H1/H2/H3 downstream outcomes were inspected before this execution lock. Sequence-state prevalence and lead-lag diagnostics from the preregistered Stage H sequence construction had already been computed; downstream CONTROL/HOOK outcomes had not.
