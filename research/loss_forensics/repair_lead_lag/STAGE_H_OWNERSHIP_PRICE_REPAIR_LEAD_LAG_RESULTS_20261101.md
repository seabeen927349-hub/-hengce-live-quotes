# Stage H — Ownership / Price Repair Lead-Lag Results — 2026-11-01

Status: **STRUCTURAL_SUPPORTED_NOT_CALIBRATED**  
Production authority: **NONE**  
Formal weight: **0**  
Parent preregistration: `OWNERSHIP_PRICE_REPAIR_LEAD_LAG_PREREGISTRATION_V1_20261101.md`  
Downstream execution lock: `STAGE_H_H1_H2_H3_EXECUTION_LOCK_20261101.md`

## 1. Governance / authority

No H1/H2/H3 rule was changed after downstream outcomes were inspected.

The execution-lock wording was corrected before final analysis from an accidental `peak-to-trough price drawdown` phrase back to the parent-preregistered definition: **price drawdown at t0 versus PX_BASE**. No outcome, population, threshold, sequence rule, or model rule was changed by that correction.

Historical Stage H ownership calculations use the already-established current-100 merged ownership authority (`current100_ownership_intervals_audit.csv` in the research workspace): official Jan-Apr TDCC sidecar plus the existing continuation vessel. This distinction is necessary because the continuation TDCC vessel alone does not contain the full Jan-Apr sidecar for every pilot ticker. The frozen 368-event cohort and all Stage H Jan-Apr next-snapshot ownership outcomes therefore use the merged Stage H ownership authority, not a continuation-only substitute.

Frozen provenance remains:
- 503 complete peak-to-trough down legs after excluding 3042 and 6415.
- 503 identity SHA256: `f03abb00e164ac16868274f866f0bb4eba30b0dca0e86257fd5d8573448348e3`.
- 368 first-valid post-peak Big400 fracture/outflow events.
- 368 cohort SHA256: `b42ca061bd51d62ebeb4ab4fd128b371260d02a871f2e9f9cf85f904078b4920`.

## 2. Sequence-state prevalence

### Primary window — second valid ownership snapshot after t0

Population disposition:
- OK: **330**
- corporate-action censored: **37**
- right-censored: **1**

Among the 330 classifiable events:

| State | N | Share |
|---|---:|---:|
| NEITHER | 141 | 42.7% |
| PRICE_ONLY | 109 | 33.0% |
| COARSE_TIE | 51 | 15.5% |
| OWNERSHIP_ONLY | 15 | 4.5% |
| PRICE_FIRST | 12 | 3.6% |
| OWNERSHIP_FIRST | 2 | 0.6% |

Exact two-sided ordering is therefore rare in the primary window: only 14 events have exact `OWNERSHIP_FIRST` or `PRICE_FIRST`, and 12/14 are PRICE_FIRST.

With signed lead-lag defined as `price repair session - ownership repair session`, the 14 exact-order primary events have:
- median: **-8.5 sessions**
- mean: **-6.71 sessions**
- minimum: **-9**
- maximum: **+4**

Negative values mean price repaired first.

### Secondary robustness window — fourth valid ownership snapshot after t0

Population disposition:
- OK: **304**
- corporate-action censored: **63**
- right-censored: **1**

State prevalence:

| State | N |
|---|---:|
| PRICE_ONLY | 101 |
| NEITHER | 85 |
| COARSE_TIE | 62 |
| PRICE_FIRST | 37 |
| OWNERSHIP_FIRST | 11 |
| OWNERSHIP_ONLY | 8 |

There are 48 exact-order events in this wider window: 37 PRICE_FIRST and 11 OWNERSHIP_FIRST. Signed lead-lag median is **-8 sessions** and mean is **-5.92 sessions** (range -19 to +10).

Interpretation: the data do **not** support a generic narrative that ownership usually repairs before price. The opposite ordering is much more common among events where exact ordering can be observed.

## 3. H1 — subsequent broad control loss

Frozen target: next valid TDCC snapshot after sequence observability, where `ControlLoss = (dBig400Pct < 0) AND (dBig1000Pct < 0)`.

Directional groups are frozen as:
- OWN = OWNERSHIP_FIRST + OWNERSHIP_ONLY
- PRICE = PRICE_FIRST + PRICE_ONLY

### Primary raw result

| Group | ControlLoss | N | Rate |
|---|---:|---:|---:|
| OWN | 4 | 17 | **23.5%** |
| PRICE | 51 | 121 | **42.1%** |

Risk-rate difference, PRICE minus OWN: **+18.6 percentage points**.

Per-state raw rates:
- OWNERSHIP_FIRST: 0/2 = 0.0%
- OWNERSHIP_ONLY: 4/15 = 26.7%
- PRICE_FIRST: 3/12 = 25.0%
- PRICE_ONLY: 48/109 = 44.0%
- COARSE_TIE: 20/51 = 39.2%
- NEITHER: 59/141 = 41.8%

Thus the frozen H1 directional requirement is met in the primary window.

### Adjusted diagnostic

The preregistered continuous-covariate diagnostic uses initial Big400 fracture magnitude, initial Big1000 change, holder-fragmentation change, margin/leverage change, pre-t0 20-session volatility, pre-t0 20-session median traded value, t0 price drawdown versus PX_BASE, and electronics-regime return.

Complete-case directional N is **88** because the full holder-fragmentation covariate is not present in the Jan-Apr official sidecar. Composition is only **8 OWN** versus **80 PRICE**.

Adjusted PRICE-vs-OWN odds ratio for next ControlLoss:
- OR: **4.53**
- 95% CI: **0.51 to 40.54**
- model p-value: **0.176**

The adjusted coefficient remains in the preregistered direction, but the interval is extremely wide. This is not a calibrated effect estimate and is not used to claim statistical confirmation.

### Time stability

Primary raw H1:
- EARLY_H1: OWN 3/13 = 23.1%; PRICE 40/86 = 46.5%
- LATE_H2: OWN 1/4 = 25.0%; PRICE 11/35 = 31.4%

Direction remains the same, but the late difference is much smaller and the OWN sample is very small.

### Secondary-window sensitivity

At the fourth-snapshot sequence window:
- OWN: 7/19 = **36.8%**
- PRICE: 63/138 = **45.7%**

Direction remains consistent but attenuation is material.

**H1 verdict: SUPPORTED IN DIRECTION, NOT CALIBRATED.**

## 4. H2 — renewed leakage before durable reconcentration

Frozen definitions:
- renewed leakage = subsequent valid snapshot with `dBig400Pct < 0`;
- durable reconcentration = positive Big400 build whose next valid snapshot retains Big400Pct at or above the pre-build baseline;
- inspect up to four valid ownership snapshots after sequence observability.

### Primary result

| Group | Leak first | N evaluable | Rate |
|---|---:|---:|---:|
| OWN | 8 | 17 | **47.1%** |
| PRICE | 82 | 121 | **67.8%** |

Difference, PRICE minus OWN: **+20.7 percentage points**.

Per-state:
- OWNERSHIP_FIRST: 0/2 = 0.0%
- OWNERSHIP_ONLY: 8/15 = 53.3%
- PRICE_FIRST: 6/12 = 50.0%
- PRICE_ONLY: 76/109 = 69.7%
- COARSE_TIE: 31/51 = 60.8%
- NEITHER: 86/141 = 61.0%

Time split:
- EARLY_H1: OWN 46.2%; PRICE 70.9%
- LATE_H2: OWN 50.0%; PRICE 60.0%

The directional relationship remains in both chronological blocks.

### Secondary-window sensitivity

- OWN: 9/19 = **47.4%**
- PRICE: 90/137 = **65.7%**
- one directional event is right-censored.

H2 is the more stable of the two structural hypotheses.

**H2 verdict: SUPPORTED IN DIRECTION, NOT CALIBRATED.**

## 5. Frozen V0.11 replay check for H3

The frozen V0.11 CONTROL / RETAIL state engine was replayed from the canonical continuation vessel and daily mother-data snapshot alignment.

On the 100-stock pilot at the packaged 2026-10-22 checkpoint, replay matched the frozen packaged fields for all 100 pilot rows across the state inputs used by H3, including ControlPosition8, PrevControlPosition8, RetailHook, dBig400Pct, dBig1000Pct, holder fields, margin change, DataOK, and packaged MODEL_STATE semantics.

No synthetic Jan-Apr V0.11 state was created. H3 begins only once the frozen state engine is PIT-valid under its own continuation-vessel history.

## 6. H3 — incremental held-out probability quality

Frozen target: next-valid-snapshot V0.11 ControlLoss.

Eligibility after V0.11 PIT/DataOK and next-target requirements:
- eligible events: **187**
- eligible dates: 2026-05-29 through 2026-10-02
- target ControlLoss events: **78**

Eligible Stage H sequence composition:
- NEITHER: 76
- PRICE_ONLY: 70
- COARSE_TIE: 28
- PRICE_FIRST: 8
- OWNERSHIP_ONLY: 5
- OWNERSHIP_FIRST: **0**

This imbalance is important: H3 cannot calibrate a symmetric signed ownership-first versus price-first lead-lag effect from this sample.

Strict expanding-time evaluation starts only after at least 60 eligible earlier events and both target classes exist. Held-out evaluation contains:
- **115 observations**
- **14 held-out TDCC dates**

### Aggregate held-out metrics

| Metric | BASE CONTROL+HOOK | TEST + sequence/lead-lag | TEST - BASE |
|---|---:|---:|---:|
| Brier | 0.245692 | **0.244769** | **-0.000923** |
| Log loss | 0.688379 | **0.686207** | **-0.002171** |
| AUC (secondary) | 0.6011 | **0.6064** | +0.0053 |

By the frozen H3 gate, TEST improves both aggregate Brier and aggregate log loss, so **H3 formally passes its preregistered aggregate gate**.

However, the gain is small and not temporally stable:
- both Brier and log loss improve on only **7 of 14** held-out dates;
- earlier held-out half (66 observations): Brier 0.26921 -> 0.26388; log loss 0.74096 -> 0.72887;
- later held-out half (49 observations): Brier **0.21401 -> 0.21903** and log loss **0.61755 -> 0.62874**, i.e. TEST worsens.

Therefore H3 is evidence of a small incremental structural signal, not evidence of a stable calibrated probability layer.

**H3 verdict: FORMAL AGGREGATE GATE PASS; STABILITY NOT ESTABLISHED.**

## 7. Concentration / censoring diagnostics

Primary 330 classifiable events span **92 unique tickers**.
- maximum events for one ticker: 8
- top-five ticker share of events: **10.9%**
- maximum events on one sequence-observability date: 28

The sample is not dominated by one stock, but event-date clustering is non-trivial and must remain visible in future validation.

Corporate-action censoring increases from 37 events in the two-snapshot window to 63 in the four-snapshot window. This is expected mechanically from the longer observation horizon and is retained as censoring rather than repaired by changing baselines.

## 8. Stage H verdict

### Final status: `STRUCTURAL_SUPPORTED_NOT_CALIBRATED`

Reasons:
1. H1 raw primary direction is supportive and the secondary window preserves direction, but the adjusted OWN sample is too small for a stable effect estimate.
2. H2 shows the clearest structural consistency: PRICE-first/price-only events have more renewed Big400 leakage before durable reconcentration in both primary and secondary windows and both chronological blocks.
3. H3 passes the frozen aggregate Brier + log-loss gate, but the improvement is small, only 7/14 dates improve on both metrics, and the later held-out half deteriorates.
4. Exact OWNERSHIP_FIRST events are extremely rare, and no OWNERSHIP_FIRST event survives into H3 eligibility. A symmetric lead-lag probability model is therefore not identified well enough.
5. No threshold optimization, state reassignment, window rescue, or production promotion is justified.

## 9. Authority consequence

- Formal weight remains **0**.
- No BUY / SELL / escape-monitor / ranking threshold changes.
- No production authority.
- Do not promote `RepairLeadLag` as a calibrated alpha family.
- Retain it as a structural explanatory feature candidate for **future post-prereg Stage P validation**.
- Future evidence should specifically test whether the PRICE_FIRST / PRICE_ONLY fragility relationship survives prospectively and whether enough OWNERSHIP_FIRST observations accumulate to identify a real signed lead-lag effect.

## 10. Local audit hashes

Research-workspace outputs used for this result:
- `stage_h_window2_matrix.csv`: `db1dc73062d2d21a5d69339ef6b5eec622fdc771e80bd843d9c64a030ec313da`
- `stage_h_window4_matrix.csv`: `19f4e6dd5cd08dcabc70b6e3bf4d77debb13613ee5825e4172a92a6bba74c2f4`
- `stage_h_window2_locked_full_corrected.csv`: `cd402caec43eea40f985df895890bacf700f272092e7efb6815b90466723dbdc`
- `stage_h_h3_predictions.csv`: `3cf7e7ec8aee95f2cbc18e0e712add563a3ece9208d8f0c170a007737c7d6397`
- `stage_h_corrected_metrics.json`: `26fb732cf360006be2e94cf99620b4de44d10f383b89367430402ba5df9915e2`
