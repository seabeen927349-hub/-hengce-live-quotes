# HENGCE Dynamic State Probability Engine — Corrected Pass 4 Recognition-Latency Validation

Date: 2026-11-01
Status: EXECUTED / RESEARCH ONLY / NO TRADING AUTHORITY
Frozen correction authority: `PASS4_INCREMENTAL_TARGET_CORRECTION_20261101.md`
Scope exclusions: 6415 and 3042 are excluded from the execution sample and are not research anchors.

## 1. Correct target and replication boundary
Corrected Pass 4 asks whether information available after ownership snapshot t but before t+1 TDCC can improve recognition of **next-snapshot CONTROL durability** earlier than CONTROL alone.

Target:
`T1_CONTROL_DURABLE = 1` iff Big400Pct(t+1) >= Big400Pct(t-1) for the frozen strong-inflow/reload candidate at t.

No t+1 ownership value enters predictors. No future destination reconcentration enters predictors.

Historical original-V1 per-event `ControlProb` values are not present in the handoff/current100 artifacts. Therefore the t-time baseline below is a strict-time current100 replication of the frozen CONTROL feature set/model class, not a claim of bit-identical historical V1 probabilities.

## 2. Candidate / OOS population
Corrected t+1 candidate population:
- 876 usable strong-inflow candidates
- 735 t+1 durable
- 141 t+1 failed
- 39 snapshot dates, 2026-01-16 through 2026-10-16

Strict expanding OOS evaluation:
- 2026-06-26 through 2026-10-16
- 355 held-out predictions across 17 snapshot dates
- 302 durable
- 53 failed

All h=1/2/3 checkpoints exist before t+1 for the evaluated rows.

## 3. t-time CONTROL baseline
`BASE_CONTROL_T1`
- n = 355
- Brier = 0.1260606176
- log loss = 0.4150647493
- ECE10 = 0.0243109597
- AUC = 0.6172060477

This is the baseline that early evidence must beat.

## 4. Frozen early checkpoints
Early features use only information observable after t and before t+1:
- cumulative normalized aggregate professional flow;
- flow persistence;
- source residual price response versus current100 equal-weight market, using beta estimated only from pre-t daily history;
- source margin/leverage path;
- four-quadrant flow x residual-price x leverage interactions;
- frozen related-destination preload known at t where available;
- destination post-t sponsor flow / leverage / relative response where available;
- optional source-destination execution mirror.

### h = 1 trading day after t
- Brier = 0.1193342108
- log loss = 0.3889643819
- ECE10 = 0.0200773695
- AUC = 0.7065475447

Versus t-time CONTROL:
- Delta Brier = -0.0067264068
- Delta log loss = -0.0261003674
- Delta ECE = -0.0042335902

Chronological robustness:
- early block Brier 0.1310725683 -> 0.1255991641; log loss 0.4262867469 -> 0.4060360664
- late block Brier 0.1220864951 -> 0.1143665459; log loss 0.4061664987 -> 0.3754277431
- remove single most favorable date (2026-10-08): Brier 0.1173178790 -> 0.1116016431

All frozen promotion conditions pass.

Remaining trading sessions from the h=1 checkpoint until the next ownership snapshot date:
- mean = 2.6986
- median = 3
- min = 2
- max = 3

Therefore **h=1 is the earliest validated recognition point under the frozen h=1/2/3 design**.

### h = 2 trading days after t
- Brier = 0.1142137083
- log loss = 0.3624554010
- ECE10 = 0.0405582483
- AUC = 0.7890166188

All frozen conditions also pass; ECE is worse than baseline but by +0.01625, inside the pre-locked +0.02 material-damage ceiling.
Median remaining sessions to next ownership snapshot date = 2.

### h = 3 trading days after t
- Brier = 0.1049408201
- log loss = 0.3414479392
- ECE10 = 0.0182299910
- AUC = 0.8006372610

All frozen conditions pass.
Median remaining sessions to next ownership snapshot date = 1.

Because recognition latency is the objective, h=1 is the operative validated checkpoint; h=2/h=3 show that information continues to accumulate but are not earlier.

## 5. Destination-coverage sanity check
Only 18 / 355 Pass-4 OOS rows have one of the frozen explicit related-name edges. The h=1 improvement is present in both groups:
- non-edge rows (n=337): Brier 0.1277609683 -> 0.1211061752
- frozen-edge rows (n=18): Brier 0.0942262736 -> 0.0861591006

Therefore the h=1 improvement is not confined to the small related-edge subset.

## 6. Source-only diagnostic ablation
To test whether the h=1 result is merely destination-edge/missingness behavior, a post-primary diagnostic ablation retained CONTROL plus only source post-t information: source professional-flow intensity/persistence, residual price response, margin/leverage path, and the four flow-price-leverage quadrant indicators.

Source-only h=1:
- Brier = 0.1220365447 vs BASE 0.1260606176
- log loss = 0.3981900048 vs BASE 0.4150647493
- ECE10 = 0.0151005727 vs BASE 0.0243109597
- AUC = 0.6864300887 vs BASE 0.6172060477

Both chronological halves improve:
- early Brier 0.1310725683 -> 0.1280439178; log loss 0.4262867469 -> 0.4138204105
- late Brier 0.1220864951 -> 0.1172731225; log loss 0.4061664987 -> 0.3857961983

After removing the single most favorable date (2026-09-18), Brier remains better: 0.1259345390 -> 0.1230721429.

This supports the narrower claim that **post-t source flow / price response / leverage contains genuine early recognition information**, independent of the sparse explicit destination-edge layer.

The source-only ablation was run after the primary frozen Pass-4 test and is diagnostic; it does not silently replace the frozen primary model.

## 7. Corrected Pass 4 conclusion
Within the current100 pilot and the stated replication boundary:

> **Yes: next-TDCC durability can be recognized earlier than the t-time CONTROL replication. The earliest frozen checkpoint with robust probability improvement is one trading day after t.**

The validated latency gain is approximately **3 trading sessions median** (2.70 mean) before the next ownership snapshot date.

This is a recognition-latency result, not a new durability target and not a trading rule.

Important limits:
- the latency measure is to the next ownership **snapshot date**, not a separately verified public-release timestamp;
- original historical V1 event probabilities were unavailable, so the baseline is a current100 strict-time CONTROL replication;
- only current100 has been validated here; no whole-market production generalization is authorized;
- destination-preload attribution remains under-covered and is not promoted by Pass 3.

## 8. Reproducibility hashes
- Pass-4 corrected candidate/features matrix: `2794bf17fcda4f31d8611dfa0b1f9e1b47c6a7011c2be8b14f3d6d4fd40abc51`
- t-time CONTROL baseline predictions: `6860842caa1344c093070161eec84b0acb817f4f89977edc420b8ed7f26f7993`
- h=1 predictions: `01700804083921685c9bb1d1d682e5102d2df8ebde20f2df7bcc5709cfdba814`
- h=2 predictions: `0bfcf1e5efd267247c683a22d5319134f0f71c6b9847b6a3ba262557d91278d7`
- h=3 predictions: `d1408fdc5e8be4021da8efa72bc0e61906eb28abce590c380c84fe42fd5e8332`
- source-only diagnostic predictions: `4d9450656e6d05f142df6ead5868c6596b6b4383488f651eb610ec8aea9353dc`

No production or capital authority is created by this validation.
