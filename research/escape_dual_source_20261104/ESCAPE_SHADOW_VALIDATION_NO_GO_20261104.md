# HENGCE Escape frozen-rule retrospective test — 2026-11-04

**Decision: NO-GO / FORMAL NOT ADMITTED.** Shadow research only. Existing active main and frozen metric/detector/state engine are UNMODIFIED.

## Input & reproducibility

- Existing restored 2023–2026 TWSE shadow panel: **919 trading days**, 2023-01-03–2026-10-27.
- Reported TWSE margin balances (excluding unreported rows as missing, not filling zeros) allow **889** numerically complete 17-metric days; **849** days with >=40 past metric observations. Eligibility and PIT U classification are not independently certified.
- GitHub detector V1 blob `eb3a3d80ae3473017e5fb1f70365ec9a4a0231f0`, state engine V2 blob `f9c78ac71962a6634ec236b248f85ad127ef7cc1`. This is a **read-only logic reconstruction**, not direct byte-exact execution of the frozen Python scripts.
- No indicator optimization: past 60-session empirical baseline, minimum 40; severe >=90th percentile, moderate >=80th; event persistence as coded.
- 2023–2024 reference; 2025 retrospective validation; 2026 later-period retrospective test. The GitHub scripts were restored **2026-11-03**, after all source dates, so these splits are **NOT independent prospective out-of-sample tests**.
- To isolate unreconciled 494 E-cohort share-volume/turnover inconsistencies observed on 2026-10-08, 10-21, 10-22, all evaluation as-of dates from **2026-10-08** onward are excluded.
- Price-only comparator: trailing 20-session E equal-weight chained return < 0. Outcome: next **20 TWSE sessions** E-cohort equal-weight chained return <= -5%; observation at EOD t and outcome strictly t+1 to t+20. Not a TWSE-listed electronic index.
- Additional outcome checks at 5d <= -3% and 10d <= -5%; no live trade simulation.

## Results: retrospective 2025–2026, 418 fully matured future-20-session labels

| Research candidate | Flagged sessions | Events after flagged day | Conditional probability | Event-day recall |
|---|---:|---:|---:|---:|
| No signal (unconditional) | 418 | 47 | **11.24%** | N/A |
| Escape **raw** L2+ | 148 | 14 | **9.46%** | 29.79% |
| Escape raw L3+ | 11 | 0 | **0%** | 0% |
| Prior-20d-price-negative baseline | 141 | 22 | **15.60%** | 46.81% |
| Escape V2 **stateful** L2+ with prior_level continuity | 418 | 47 | **11.24%** | 100% (indiscriminate) |

By year, Escape raw L2+ conditional target rates were **6.67%** (2025, 6/90) and **13.79%** (2026, 8/58). The price-only benchmark rates were **18.37%** (2025, 18/98) and **9.30%** (2026, 4/43). The relative ranking reverses between years.

20-session stratified moving-block bootstrap, 2500 resamples with fixed seed: Escape raw L2+ minus price-only event-rate difference **-6.48 percentage points**; 95% percentile interval **[-25.10, +7.59] pp**, includes 0. Thus not proof of inferiority, but **no evidence of stable superiority**. Using non-overlapping alert *onsets* (20-session cooldown carried across the calendar boundary), Escape raw L2+ **1/11** onsets were followed by the target; price-only **2/9**.

## State engine blocking finding

If V2's optional `prior_level` is carried forward between sessions, its explicit de-escalation hysteresis maintained **L6 from the first raw L6 on 2024-07-30 through 2026-10-27**; the stringent five-consecutive recovery condition occurred on **0** dates. Under this hypothetical but natural persistent-state integration, **all 427 research-valid 2025–2026 sessions were L6**, so the state cannot distinguish risk. The **current inspected FinMind and Fugle intraday shadow workflows do not actually invoke V2 or pass prior_level**; this is NOT an observation of a deployed L6 lock.

## Checks and blockers

- **20/20** new validation regression tests passed (source count, metric completeness, lag/forward alignment, disjoint forward-5 to forward-20 arithmetic, source-revision date exclusion, state continuity, output math, and no authority promotion). Tests prove local reproducibility, **not** predictive edge.
- Current formal data gates remain false: `PIT_U_SECURITY_STATUS`, `MARGIN_ELIGIBILITY`, `REVISION_RECONCILIATION`, `OUT_OF_SAMPLE_PROSPECTIVE`.
- The previous 2018–2022 full-market backfill remains incomplete; individual public FinMind sample access is insufficient.
- Pre-freeze design contamination and historical revisions remain unresolved. Overlapping forward returns limit independent sample size; event-level sensitivity confirms few unique cases.
- Do not silently edit frozen V2. A revised state engine must be separately versioned, tested for hysteresis and de-escalation, then independently compared against the same simple price benchmark **in future as-of records**. Correctness of 17 indicator computations alone is insufficient.

**Authority:** `RESEARCH_ONLY`; `FORMAL_ESCAPE_STATE=UNVERIFIED`; `TRADING_AUTHORITY=NONE`. Do not merge as formal Escape, issue trade directives, or alter main merely because an exploratory research reconstruction can emit levels.

## Artifact

Self-contained reproducibility archive: `HENGCE_Escape_20261104_OOS_Validation_NoGo.zip` (local SHA256 `fdf59bf21a68c3027410ebae00c1595d170552cf285c13e8a7fffa5425a6bc33`). Code, research reconstructed daily levels, sample-split tables, 20-session block-bootstrap, full 20 regression tests, hash manifest and decision record. Uses the previously archived 919-day research input rather than duplicating its entire full-market mother.
