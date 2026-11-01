# HENGCE Loss Forensics — Pass 3 / corrected Pass 4 execution lock

Date: 2026-11-01
Parent handoff head: f5da0236717ddcc69cd9e15d50a2afd92e74ba26
Status: PRE-RESULT EXECUTION LOCK. No Pass 3 / Pass 4 outcome numbers are recorded here.

## Governance
- Preserve all prior handoff / preregistration governance.
- No silent retuning after forward labels are evaluated.
- 6415 and 3042 are excluded from the execution sample and are not permitted as primary cases or research anchors.
- Corporate-action / denominator instability and ownership conflicts fail closed.
- Related-name graph is frozen to the preregistered Level-B edges only: 6213->3189, 3231->3017, 2337->2344, 8021->2383, 3006->8150; 2408->2337 is retained only as the preregistered negative-control edge.

## Source data
Primary ownership source: current100_ownership_intervals_audit.csv.
Daily source: canonical HENGCE_2026_HIST_MOTHER.csv, using only rows available on or before each predictor timestamp.

## Interval feature reconstruction
For stock i at ownership snapshot t with previous snapshot t-1:
- d_Big400 = Big400Pct(t) - Big400Pct(t-1).
- d_Big400_2 = d_Big400(t) + d_Big400(t-1).
- AbsorptionFrac = [Big400Shares(t)-Big400Shares(t-1)] / sum(Volume) over (t-1, t].
- HoldersChg = TotalHolders(t)/TotalHolders(t-1)-1.
- HolderDensityChg = [TotalHolders/TotalShares](t) / [TotalHolders/TotalShares](t-1) - 1.
- MarginChg, PriceRet, TurnoverChg use the last canonical daily observation on or before t divided by the last canonical daily observation on or before t-1, minus 1.
- Professional-flow observables use aggregate TotalNet and are normalized by traded volume; ForeignNet / TrustNet identities are not modeled separately.

## PIT percentile replication note
The frozen MODEL_SPEC text says expanding PIT percentile, but CURRENT_CONTROL_BUILDS_20261022 can be exactly reproduced for d_Big400_hist_pct and AbsorptionFrac_hist_pct with a trailing-25-snapshot PIT rank. This is treated as an existing artifact/spec mismatch, not an outcome-based choice. For replication of the frozen CONTROL behavior in this execution, trailing-25 PIT ranks are used. The mismatch must be reported.

## Candidate repair/reload event
A candidate at t must satisfy all of:
1. stable_1pct == true;
2. no ownership conflict flag;
3. d_Big400 > 0;
4. trailing-25 PIT percentile of d_Big400 >= 0.75;
5. trailing-25 PIT percentile of AbsorptionFrac >= 0.75;
6. both t+1 and t+2 ownership observations exist for the durability label.
No future outcome is used in candidate selection.

## Frozen durability target
Let B0 = Big400Pct at t-1. A candidate is REPAIR_DURABLE=1 iff BOTH:
- Big400Pct(t+1) >= B0; and
- Big400Pct(t+2) >= B0.
Otherwise it is RELOAD_REVERSAL=1 / REPAIR_DURABLE=0.
This operationalizes next-snapshot retention plus next-two-snapshot cumulative retention without tuning a give-back percentage.

## Pass 3 feature-family sequence
All models are fit on exactly the same candidate rows and evaluated on the same time-ordered held-out rows.
1. BASE_CONTROL_HOOK: frozen CONTROL primitives plus HOOK proxy/state observables available at t.
2. +CORE_LOOSENING: add only preregistered Core-loosening interaction information; standalone dU<0 & dL>0 remains zero-weight as previously governed unless incremental held-out probability quality is demonstrated.
3. +BRIDGE_DESTINATION_PRELOAD: add preregistered same-snapshot source/destination preload observables from the frozen related-name graph only. No future destination ownership is allowed.
4. +PROFESSIONAL_FLOW: add contemporaneous normalized aggregate professional-flow information available by t.

## Probability protocol
- Strict expanding time-order evaluation; no random split.
- Evaluation begins no earlier than 2026-06-26 and only when the durability label would have been known for training rows.
- Same fixed model class is used for all four feature-family variants; no per-family hyperparameter search.
- Raw model scores are probability-calibrated only with a chronologically later, still-pre-evaluation calibration block drawn from prior labeled dates. If a valid two-class calibration block is unavailable, the model abstains for that evaluation date.
- Primary metrics: Brier score, log loss, calibration error / reliability, coverage / abstention. AUC is secondary.
- Promotion rule: an added family must improve held-out probability quality without material calibration damage; otherwise its formal incremental weight is zero.

## Corrected Pass 4 recognition-latency protocol
Pass 4 starts only after Pass 3 is completed.
For each candidate at t, use only daily information after t and before t+1 ownership availability. The t+1 ownership response is a future label and is never a predictor.
Fixed post-t checkpoints are trading-day h=1,2,3 where available before t+1.
At each h, early-recognition predictors are limited to:
- cumulative normalized aggregate professional flow;
- source price response residualized against contemporaneous current100 / market return using coefficients estimated from data strictly before t;
- leverage change from t through h;
- destination preload already observable at t plus destination post-t sponsor-flow / relative-response observables;
- source-destination flow mirror for frozen related edges.
No future destination reconcentration is allowed.

Pass 4 compares each h model against the frozen t-time Pass-3 BASE probability using Brier, log loss, calibration and coverage. Recognition-latency gain is reported only if probability quality improves without material calibration damage; gain is the number of remaining trading days from the earliest qualifying h checkpoint to the next ownership observation. If no checkpoint qualifies, validated recognition-latency gain is zero / not demonstrated.
