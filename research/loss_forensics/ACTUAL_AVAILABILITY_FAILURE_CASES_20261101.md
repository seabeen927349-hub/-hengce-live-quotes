# HENGCE DSP / Loss Forensics — Actual-Availability Failure Cases

Date: 2026-11-01
Status: **DATA-PROVENANCE FAILURE CASES / NOT MODEL ERROR CASES / NO FORWARD LABEL ACCESS**

Because the preregistered availability gate failed before formal label access, there are no legitimate stock-level model failure cases to enumerate. The failure cases below are the exact evidence/provenance failures that caused formal execution to stop.

## FC-01 — TDCC snapshot date is not publication time
Observed:
- historical ownership rows contain `SnapshotDate` and payload provenance/hash;
- no official historical `published_at` / earliest public availability timestamp is preserved.

Why blocking:
- using `SnapshotDate` would reproduce the known Pass-4 reference-date shortcut rather than answer the new actual-availability question.

Required status: `DATA_BLOCKED`.

## FC-02 — Periodic archive first-observed time is only an upper bound
Observed:
- the wirelessr archive contemporaneously polled the official TDCC endpoint and committed newly observed snapshots;
- first-observed times vary materially by week (e.g. 2026-07-09 snapshot was first archived on 2026-07-13).

Why blocking:
- a polling system can observe after true publication;
- first-observed time proves `public by this time`, not exact earliest publication.

Permitted use:
- provenance / conservative upper-bound audit only.

Prohibited use:
- silently calling it the exact `A_t/A_t1` defined in the preregistration.

## FC-03 — Canonical daily rows have no historical receipt timestamps
Observed:
- `HENGCE_2026_HIST_MOTHER.csv` has date/value fields for price, professional flow and margin balance;
- it has no per-field historical `published_at` or `retrieved_at`.

Mitigation available:
- official TWSE schedules provide conservative production-time bounds for institutional flow and margin data.

Why still blocking:
- those bounds do not solve ownership `A_t/A_t1` and cannot by themselves establish the complete h=1 timing chain.

## FC-04 — PIT sector membership authority not established
Observed:
- derived historical research tables contain `Industry` values.

Missing:
- authoritative effective-date/source lineage proving the classification used on each h=1 date was then-current and not later/current backfill.

Why blocking:
- frozen preregistration explicitly forbids current-sector backfill in residual price-response construction.

## FC-05 — PIT regime provenance incomplete
Observed:
- derived event ledgers contain `MarketRegimeState` / `RegimePersistence` values.

Missing:
- a frozen, auditable rule/state provenance chain demonstrating that the exact regime input used by this study was generated only from data available before each h=1 date.

Why blocking:
- inventing or re-deriving a convenient regime rule now would change the preregistered predictor semantics.

## Consequence
No stock/event may be labeled as:
- false negative;
- false positive;
- correctly warned deterioration;
- correctly protected durable repair
for this new actual-availability study.

Those categories require a formally scored, availability-eligible OOS set, which does not currently exist.

No narrative rescue follows.