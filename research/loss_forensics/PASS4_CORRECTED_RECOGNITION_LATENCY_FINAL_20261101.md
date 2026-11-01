# HENGCE Dynamic State Probability Engine — Corrected Pass 4 FINAL

Date: 2026-11-01
Status: FINAL CORRECTED RECOGNITION-LATENCY VALIDATION / RESEARCH ONLY / NO TRADING AUTHORITY
Authority basis:
- `HANDOFF_DSP_20261101/03_RESEARCH_DRIFT_LOCK.md`
- `PASS4_INCREMENTAL_TARGET_CORRECTION_20261101.md`
- final expanding-PIT Pass-3 candidate semantics.

This file supersedes the earlier CONTROL-only baseline diagnostic execution. Final BASE remains CONTROL + HOOK evidence, as required by the drift lock.

## 1. Corrected target
The incremental target is recognition latency, not a duplicate durability model.

For a frozen strong-inflow/reload candidate at ownership snapshot t:
- label only: `T1_CONTROL_DURABLE = 1` iff Big400Pct(t+1) >= Big400Pct(t-1).
- predictors at h=1/2/3 use only t-known ownership/HOOK evidence plus daily/cross-stock information available after t and before t+1.
- t+1 ownership and future destination reconcentration are never predictors.

Historical original-V1 per-event probabilities are unavailable in the handoff/current100 artifacts. The comparison BASE is therefore a strict-time current100 replication of frozen CONTROL + HOOK evidence with the same locked HGB + chronological calibration protocol. This replication boundary is explicit.

## 2. Candidate / OOS population
Expanding-PIT corrected t+1 population:
- 855 usable candidates across 39 snapshot dates.
- t+1 durable = 718.
- t+1 failed = 137.

Strict expanding OOS evaluation:
- 2026-06-26 through 2026-10-16.
- 334 / 334 eligible candidates scored across 17 dates.
- durable = 285; failed = 49.
- coverage = 100%; abstention = 0% within the defined evaluation period.

## 3. BASE = CONTROL + HOOK at t
Evidence status: `VALIDATED_OOS` comparison baseline for this current100 replication.
- n = 334
- Brier = 0.1213545543
- log loss = 0.3995738511
- ECE10 = 0.0294817394
- AUC = 0.6495524526

## 4. h=1 — first trading day after t
Early evidence bundle includes only allowed pre-t+1 information:
- normalized aggregate professional flow and persistence;
- market-adjusted source residual price response with beta estimated strictly from pre-t history;
- post-t leverage/margin path;
- locked four-quadrant flow x residual-price x ownership-state x leverage interactions;
- frozen destination preload already known at t where available;
- post-t/pre-t+1 destination flow/relative-response and optional execution mirror where available.

Evidence status: `VALIDATED_OOS` for recognition latency.
- Brier = 0.1166464284
- log loss = 0.3777559378
- ECE10 = 0.0222562530
- AUC = 0.7276763337

Versus BASE:
- Delta Brier = -0.0047081260
- Delta log loss = -0.0218179134
- Delta ECE = -0.0072254864

Frozen robustness checks all pass:
- early block 2026-06-26..2026-08-14: Brier 0.1192859817 -> 0.1149675168; log loss 0.3931804729 -> 0.3741951594.
- late block 2026-08-21..2026-10-16: Brier 0.1230408907 -> 0.1180151062; log loss 0.4047858443 -> 0.3806587463.
- remove single most favorable date (2026-09-04): Brier 0.1212876998 -> 0.1178877159.
- sample condition passes: 334 predictions, 285 durable, 49 failed.

Recognition latency from h=1 checkpoint to next ownership snapshot date:
- mean remaining trading sessions = 2.6976
- median = 3
- min = 2
- max = 3

Therefore **h=1 is the earliest frozen checkpoint that qualifies**.

## 5. h=2
Evidence status: `FAILED` under the locked calibration-damage rule, despite stronger discrimination.
- Brier = 0.1081477213
- log loss = 0.3422239922
- ECE10 = 0.0536692809
- AUC = 0.8163265306

Brier/log loss improve strongly in both time blocks and leave-best-date-out remains better, but ECE worsens by +0.0241875415 versus BASE, exceeding the pre-locked +0.02 material-damage ceiling.

Formal h=2 qualification = **FAIL**.

## 6. h=3
Evidence status: `VALIDATED_OOS`, but it is later than h=1 and therefore does not improve the earliest recognition point.
- Brier = 0.1048363643
- log loss = 0.3369831721
- ECE10 = 0.0319296862
- AUC = 0.8110275689

Both time blocks improve; leave-best-date-out improves; ECE damage is only +0.0024479468 and remains inside the locked ceiling.
Median remaining session to next ownership snapshot date = 1.

## 7. Destination-coverage / attribution audit
Only 19 / 334 final OOS rows have an explicit frozen related-name edge. h=1 improvement appears in both groups:
- non-edge rows n=315: Brier 0.1238178092 -> 0.1195984157.
- edge rows n=19: Brier 0.0805163807 -> 0.0677055848.

A post-primary source-only diagnostic ablation was run to ensure h=1 was not a missing-destination artifact. It retained BASE CONTROL+HOOK and only source post-t flow / residual-price / leverage information.

Source-only h=1 diagnostic:
- Brier = 0.1162257311
- log loss = 0.3782934456
- ECE10 = 0.0151762197
- AUC = 0.7235230934

It improves both chronological halves:
- early Brier 0.1192859817 -> 0.1168518105; log loss 0.3931804729 -> 0.3811508880.
- late Brier 0.1230408907 -> 0.1157153403; log loss 0.4047858443 -> 0.3759640090.

After removing its single most favorable date (2026-09-11), Brier remains better: 0.1146349406 -> 0.1113501292.

This diagnostic supports the narrower mechanism that source-side post-t flow / residual-price response / leverage carries genuine early information. Because the ablation was not the frozen primary comparison, it is not used to silently replace the primary model.

## 8. Final corrected Pass 4 decision
Evidence status: `VALIDATED_OOS` for the current100 pilot, within the stated replication boundary.

> After state t is known, the allowed daily/cross-stock evidence available by the first following trading day improves held-out calibrated probability of next-TDCC durability versus the t-time CONTROL+HOOK BASE.

Earliest validated recognition point: **h=1 trading day after t**.
Validated recognition-latency gain: **median 3 trading sessions (mean 2.70) before the next ownership snapshot date**.

Important limits:
- latency is measured to the next ownership snapshot date, not a separately verified public-release timestamp;
- this is current100, not whole-market production validation;
- original historical V1 per-event probabilities were not available, so BASE is a strict-time CONTROL+HOOK replication rather than bit-identical V1 history;
- destination-preload itself failed final Pass 3 and does not receive formal standalone weight;
- h=1 validates an early-evidence bundle / recognition layer, not a BUY/SELL rule and not exact-price prediction.

## 9. Reproducibility SHA256
- expanding-PIT corrected Pass-4 candidate/features matrix: `1655fb0f0c3d297ce03a078714c7c11b7c663f941d77bf8a6e0236703bb40d3e`
- BASE CONTROL+HOOK t1 predictions: `2a0630103bc4a0cc63924a83eb63c8d4655833fdc52c875b479f06740aa0e0c7`
- h=1 predictions: `2eb8231c596c9a23f25c42681705b3628a8126b74f8b92dd27ad5cc84d55c9f9`
- h=2 predictions: `22224690f48403477d580cc328d057eb7c588175685946078099b7067f6b2422`
- h=3 predictions: `e183958c08046c98c718383fad4e2b617d93f9ab09786a6ccef1fc4908f871b0`
- source-only h=1 diagnostic: `3dabf3b7acd03d6b1618b2f64f5b550449d131ab26ee62d715464777ca78bcba`

No production or capital authority is created.
