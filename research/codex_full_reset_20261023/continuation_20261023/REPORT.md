# Diversified fixed-hypothesis continuation

**Result: NO_NEW_POTENTIAL_UNDER_REGISTERED_SCREEN. No accepted model.**

This separately registered follow-up tests six fixed models, each with a matched
all-liquid-electronics basket benchmark, under two quality scenarios: **24 new
evaluations**. Together with the retained parent study: **8,529 evaluations**.
No prior result or ledger byte is replaced. Production authority remains zero.

## Design and provenance

Rules and synthetic tests were committed and pushed before computation at
`46eee6639b59fd76a8fd901de9d6c67ac493573c`. Source/plan/shared-implementation hashes,
the exact mother hash, and the parent journal hash are bound into every new
journal record. New ledger: 48 STARTED/EVALUATED records, all terminal.

Universe remains exact PIT TWSE-listed electronics. Fixed top 10 equal weight;
turnover20 >= TWD50m; 61 consecutive valid price sessions; next-session open;
exit close after 5 or 20 session intervals; no overlapping baskets or year-end
forced close. No training or parameter selection occurs in this batch.

- Skip-five momentum: return from t-60 to t-5, positive only.
- Trend pullback: largest three-session pullback in positive 60-session trends.
- Low-vol trend: lowest prior-20-return volatility among positive 60-session trends.

Each signal is frozen before checking future outcomes. Missing/invalid data,
an entry session with high==low, or unproven price discontinuity censors the
entire intended basket; its interval is still occupied. No replacement ticker.
Aggregate cost is subtracted once at exit. Benchmarks enter/exit on exactly the
model schedule and use all signal-time base-eligible tickers. They are descriptive
controls, not investable indices.

## Results: complete cases only, not identified strategy returns

**Every model has censored intended baskets. The full strategy return is unknown.**
The figures below exclude those unknown outcomes and must never be described as
the return of an executable strategy. Ten constituent positions in one basket
are not ten independent trade observations. All periods below are 2024–2025.

| Model | Quality threshold | Complete / intended baskets | Complete-case net return at 1.2% | Complete-case wins | Complete-case daily-close drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| LOW_VOL_TREND_H20 | 0.1 | 14 / 21 | 2.02% | 57.14% | -19.20% |
| LOW_VOL_TREND_H20 | 0.15 | 20 / 22 | -17.27% | 40.00% | -29.62% |
| LOW_VOL_TREND_H5 | 0.1 | 63 / 68 | -42.75% | 30.16% | -42.91% |
| LOW_VOL_TREND_H5 | 0.15 | 65 / 68 | -47.72% | 29.23% | -47.74% |
| SKIP5_MOMENTUM_H20 | 0.1 | 9 / 22 | 23.83% | 66.67% | -17.34% |
| SKIP5_MOMENTUM_H20 | 0.15 | 20 / 22 | 30.54% | 60.00% | -52.48% |
| SKIP5_MOMENTUM_H5 | 0.1 | 49 / 68 | -59.44% | 40.82% | -68.61% |
| SKIP5_MOMENTUM_H5 | 0.15 | 64 / 68 | -39.49% | 50.00% | -54.53% |
| TREND_PULLBACK_H20 | 0.1 | 12 / 21 | 2.36% | 50.00% | -28.03% |
| TREND_PULLBACK_H20 | 0.15 | 20 / 21 | 6.67% | 60.00% | -44.58% |
| TREND_PULLBACK_H5 | 0.1 | 56 / 64 | -66.86% | 37.50% | -68.22% |
| TREND_PULLBACK_H5 | 0.15 | 64 / 66 | -56.06% | 42.19% | -57.47% |

The positive complete-case momentum/pullback numbers do not establish profitable
models. For example, skip-five H20 at .15 has +30.54% on 20 complete baskets,
but two intended baskets are censored, daily-close drawdown is 52.48%, and 2024
complete-case return is negative under 1.6% cost stress. Its .10 attack has only
nine complete baskets and 13 censored. Changing quality rules to rescue it would
be a new experiment, not a successful outcome of this one.

Five-session models are negative on complete cases under both quality thresholds.
Low-vol H20 loses under the .15 scenario and fails year stability. Removing the
best basket, yearly stressed returns, all cost scenarios and matched-benchmark
metrics are retained for every trial in SUMMARY.json and the 24 event files.
No benchmark-excess claim is identifiable where model/benchmark outcomes are censored.

## Why returns remain uncertain

At .15, the six model streams contain 35 unique ticker/date/reason keys in
2024–2025: 29 occurrences of limit-locked/unfillable entry, eight invalid/missing
OHLC, and two >15% discontinuities (occurrences can repeat across models).
At .10 there are 68 unique keys; many ordinary limit moves can trigger the stricter
guard. A discontinuity is not evidence by itself of a corporate action.

Examples include 2025-04-07 one-price entries; missing/invalid rows for 2327 on
2025-08-14 and 3090 on 2025-07-15; >15% raw jumps for 2364 on 2025-08-28 and
6189 on 2025-07-25. CENSOR_DIAGNOSTIC.json retains the complete affected-key list.
Daily OHLC cannot prove opening-auction fill availability. No late alternative
fill is invented. A conservative total-loss lower bound is retained for censored
streams; complete-case results are neither that bound nor an unbiased estimate.

## Validation and limits

- Thirteen new synthetic contracts PASS: causal prefix and deterministic ties,
  malformed/nonfinite history, source discontinuity, exact selections, interval
  reservation, year purge, locked entry, once-only costs, missing-return handling,
  immutable output, sample/benchmark refusal, finite zero-authority scope and
  checkpoint rejection of missing/replaced/unregistered evidence.
- Parent 17 offline contracts and 119 existing engineering regressions PASS.
- Parent completed-evidence audit PASS; parent ledger SHA256 remains unchanged.
- New retained-evidence audit PASS: 24 terminal trials, chain/provenance, result
  hashes, independently recalculated event arithmetic and summary screening.
- Final-head CI and Engineering Replay evidence is recorded in PR #30.

All 2023–2026 history is exposed. Freezing this batch does not restore an
independent holdout. No significance, highest-profit or robust-winner claim is
made. Corporate-action/security-master lineage, original first-seen/revision
timestamps, executable fills and intraday drawdown remain unverified. Shared
market regimes and holdings create dependence. Costs do not prove achievable
execution or account for market impact. These are hypothetical raw-price results.

## Highest-value next research

Obtain independently sourced effective-dated corporate actions and security
identity continuity, and official auction/limit-reference evidence for the exact
censored cases before evaluating revised outcome handling. Preserve raw source
bytes, publication/effective timestamps, hashes and every unavailable case.
Do not reconstruct adjusted returns from guessed corporate-action factors.
Any revised study must register its own finite budget, count all earlier exposure,
and retain this failed batch. Future shadow validation needs a frozen separate
protocol and actual unseen observations; this change launches no live producer.

**PRODUCTION MODEL CHANGES: NONE.** No production files or schedules changed.
Capital=0; signal/ranking authority=false; broker=false; promotion=false.
No main push, merge or automated trading. **NOT MERGED.**
