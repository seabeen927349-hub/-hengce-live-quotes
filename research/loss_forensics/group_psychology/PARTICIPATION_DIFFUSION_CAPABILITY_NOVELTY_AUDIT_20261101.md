# HENGCE Group Psychology — Participation Diffusion Capability / Novelty Audit

Date: 2026-11-01
Status: **REJECT_OVERLAP_NO_OUTCOME_UNSEAL**
Formal weight: **0**
Trading / production authority: **NONE**

## 0. Governance
This audit was executed under handoff authority `90aed5b3132ea3ad33981f4c752fa80b3e4d1553` before opening any new-family forward return or drawdown outcome. No new-family forward outcomes were inspected.

The handoff hard rule applies: if participation diffusion collapses to TotalHolders / Big400 fragmentation already present in the baseline, stop before outcome inspection rather than rescue after seeing returns.

## 1. Capability audit

### Native TDCC buckets
Authority repo contains a native raw file at:
`ownership/tdcc/20261022/tdcc_1_5_raw.csv`

At this audit, only the 2026-10-22 native-raw date directory was authority-confirmed under `ownership/tdcc/`. Historical backfill paths used by the canonical sidecar are aggregated 4D ownership files rather than longitudinal native-bucket rows.

Verdict for historical native-bucket longitudinal testing:
**DATA_BLOCKED**.

Native raw may be used to validate current bucket semantics, but one authority-confirmed native snapshot cannot support a historical native-bucket change series.

### Aggregate exact-complement fallback
Canonical TDCC sidecar:
- rows: 122,023
- distinct snapshots: 81
- distinct tickers: 3,091
- reference-date span: 2017-07-21 through 2026-10-22
- exact-valid `<400` complement rows: 112,221 / 122,023 = 91.97%

Definitions:
- `SmallHolders = TotalHolders - Big400Holders`
- `SmallShares = TotalShares - Big400Shares`

The complement is exact set arithmetic at the inherited 400-lot boundary, not an inferred beneficial-owner class. It must not be labelled retail.

Large snapshot gaps exist (including 344, 819, and 1,679 days). Any change feature must therefore require contiguous valid snapshot spacing and must not bridge those gaps.

Overall Phase-1 capability verdict:
**PARTIAL_CAPABILITY_REDUCE_SCOPE**.

## 2. First-cut feature audited
For adjacent valid snapshot observations:

`PARTICIPATION_DIFFUSION = Δlog(SmallHolders) - Δlog(SmallShares)`

Equivalently:

`PARTICIPATION_DIFFUSION = -Δlog(SmallShares / SmallHolders)`

This measures fragmentation of the aggregate `<400` complement only. It does not identify investor type, motive, cost basis, or psychology.

## 3. Input-only novelty diagnostics
No future return/drawdown was loaded or derived.

Using contiguous snapshot changes only:

### Broad available contiguous sample
- evaluable rows: 101,945
- Pearson correlation with `Δlog(TotalHolders)`: about 0.719
- baseline input-only regression using `Δlog(TotalHolders)`, `Δlog(TotalShares)`, `ΔBig400Pct`, `ΔBig1000Pct`, and `ΔBig400Holders`: in-sample R² about 0.636

### Cleaner 2026 full-market segment
- evaluable rows: 71,791
- Pearson correlation with `Δlog(TotalHolders)`: about 0.781
- same input-only baseline R²: about 0.743

These diagnostics are not outcome tests and make no alpha claim.

## 4. Algebraic overlap determination
The fallback feature is exactly:

`Δlog(TotalHolders - Big400Holders) - Δlog(TotalShares - Big400Shares)`.

Thus it contains no new raw ownership information beyond already-available TotalHolders / TotalShares / Big400 holder-share primitives. Its apparent interpretation as participation-versus-absorption is a nonlinear re-expression of existing aggregate ownership information.

Relation to prior families:
- Stage H: **partially overlapping**, because Stage H uses Big400 ownership repair plus holder fragmentation as context, but does not use this exact ratio-difference as its primary repair clock.
- Stage I: **nested / overlapping at the 400-lot boundary**, because Stage I explicitly defines `S = 100 - Big400Pct`; the new fallback adds the `<400` holder-count complement but does not add native bucket information.
- TotalHolders / Big400 baseline: **algebraically derived from existing primitives** and strongly collinear in observed inputs.

## 5. Frozen verdict
The aggregate `<400` participation-diffusion fallback **FAILS the handoff residual-novelty gate as a new information primitive**.

State: `REJECT_OVERLAP_NO_OUTCOME_UNSEAL`.

Consequences:
1. Do not preregister this aggregate fallback as a new alpha family.
2. Do not inspect its forward returns or drawdowns.
3. Do not rescue it by choosing another lag, percentile, z-score, threshold, or return horizon.
4. A genuinely native-bucket participation family requires longitudinal native bucket holder-count + shares data with PIT provenance; until that exists, that version is `DATA_BLOCKED`.
5. Formal weight remains 0.

This is a valid negative research result, not a reason to reinterpret the family after outcomes.