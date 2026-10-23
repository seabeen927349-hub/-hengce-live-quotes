# HENGCE — Codex full research reset

## Mission

Start the HENGCE model-research program over from first principles using the **complete repository-available causal/PIT mother corpus plus every prior successful, failed, rejected, aborted and abandoned experiment**.

Your job is **not** to defend Q017, E2, Candidate B, Candidate C, M1, Legacy HENGCE, or any old parameter choice. They are reference evidence only. Design and search for the strongest model supported by the data.

Primary research goal:

> Find a robust model or Pareto set that jointly maximizes **after-cost profit** and **win rate**, subject to adequate sample size, controlled drawdown/tail risk/turnover, causal point-in-time validity, regime stability, and explicit multiple-testing penalties.

If the evidence cannot support such a winner, return `NO_ROBUST_WINNER`. Do not manufacture one.

## Frozen research starting point

- Working branch: `research/codex-full-reset-20261023`
- Immutable corpus base commit: `05bf0e35fb6a88473fd4f947952ef1b6875d3f88`
- Immutable corpus base tree: `aa1af4ce9ed69327e2da272caef4128992ba6ea3`
- New human reset authorization: `research/codex_full_reset_20261023/RESET_AUTHORIZATION.json`
- Corpus map: `research/codex_full_reset_20261023/CORPUS_MANIFEST.json`
- Prior positive/negative experiment history: `research/codex_full_reset_20261023/EXPERIMENT_HISTORY.md`
- Existing evidence inventory: `research/phase1_audit/evidence_inventory.json`

Do not silently rebase the study onto moving `main`. If additional data after the frozen cutoff are later admitted, create a separately versioned data-cutoff event and preserve this study unchanged.

## Authority boundary

This authorization is **research only**.

- `capital_authority_twd = 0`
- `broker_order_execution = false`
- no real-money orders
- no change to current production ranking/signal/geometry/position logic
- no write to `main`
- no automatic merge
- no automatic production promotion
- no laundering a research winner into current HENGCE output

All outputs must remain on a research branch until a separate explicit human production/promotion instruction.

## 0. Recover all history before modeling

Before testing a new model:

1. Read `CORPUS_MANIFEST.json` and `EXPERIMENT_HISTORY.md`.
2. Inspect the entire pinned base snapshot, especially:
   - `research/**`
   - `eod/**`
   - `hengce/**`
   - `receipts/**`
   - `shadow/**`
   - `scripts/**`
   - `.github/workflows/**`
   - `docs/**`
3. Fetch/inspect all historical branch/commit refs named by the manifest, including closed/unmerged/abandoned work.
4. Inspect repository PR/history relevant to research and data integrity. Do not assume merged = scientifically successful or closed = scientifically useless.
5. Build an append-only reset experiment ledger. Import prior experiments as `HISTORICAL_REFERENCE` records and preserve their outcome (`PASS`, `FAIL`, `REJECT`, `ABORT`, `ABANDONED`, `ENGINEERING_ONLY`, etc.).
6. Never delete a failed trial from counts or summaries.

Historical branch contents must be read by pinned commit SHA. Do not use a moving branch tip as evidence when a SHA exists.

## 1. Rebuild the research mother table from causal evidence

Do **not** begin with a model formula. First build an auditable research table whose every row/feature has a point-in-time availability rule.

For each Taiwan signal/session date and security, retain where evidence exists:

- security identity and **PIT universe membership**;
- daily/open/close/return history available by that timestamp;
- turnover/liquidity history;
- market/electronics cross-sectional state;
- institutional flows from the original-vessel source when timestamp-legal;
- margin data from the original-vessel source when timestamp-legal;
- macro/US evidence only from sessions completed before the Taiwan decision timestamp;
- microstructure/live fields only when authentic timestamped quote/book evidence exists;
- suspension/limit/corporate-action/security-master evidence only where actually preserved;
- feature availability timestamp, source artifact, source commit/blob/hash, and transformation version.

### PIT / causal hard requirements

- No future membership / survivorship leakage.
- No future price, outcome, macro or revision leakage.
- Rolling estimators must use only observations available before the signal timestamp. If the signal-day value is not legally available yet, exclude it.
- U.S. macro/market features use the latest **completed prior U.S. session** appropriate to the Taiwan decision timestamp.
- Do not infer historical publication/first-seen time from a later generated file.
- Do not convert a later correction into a historical fact unless the original revision was available then.
- Do not use daily OHLC as fabricated 09:01/09:03/09:05 microstructure.
- Do not treat shadow/context transport as formal signal/execution evidence.
- Missing evidence remains missing. Prefer a smaller causal feature set to hindsight reconstruction.
- Corrupt/unreadable artifacts are explicit data-quality failures unless source-equivalent bytes can be independently proven.

Produce a machine-readable lineage report and a coverage matrix before any model comparison.

## 2. Historical exposure: no fake pristine OOS

All 2023–2026 material used in earlier work is exposed development/validation history. **It is not a pristine holdout.**

Therefore:

- do not relabel any exposed date as unseen;
- do not report a single historical split as independent final proof;
- use nested chronological / expanding walk-forward or blocked time-series evaluation;
- purge/embargo observations according to the longest outcome/holding horizon used by a candidate;
- prevent overlapping outcomes from leaking between training and evaluation folds;
- after a research winner is frozen, require future prospective shadow evidence before any production discussion.

A historical research winner may be selected for further prospective evaluation, but must be labeled `HISTORICAL_RESEARCH_WINNER_NOT_PROSPECTIVE_VALIDATED`.

## 3. Search from scratch — no inherited champion

Old families are baselines, not constraints. You may test new model families if their inputs pass the PIT audit.

Reasonable families include, but are not limited to:

- cross-sectional reversal / residual reversal;
- momentum and multi-horizon momentum;
- market/industry-relative residual signals;
- beta/volatility/dispersion/regime signals;
- liquidity/turnover/volume state;
- institutional-flow signals;
- margin-financing / short-interest style signals where legal data exist;
- interactions between local market state and prior completed U.S./SOX/macro state;
- valuation/fundamental features only if true PIT availability is proven;
- microstructure features only on dates with authentic book/quote evidence;
- simple ensembles/rank aggregation;
- regularized linear/logistic/ranking models;
- tree/boosting models and other machine-learning models **only** with strict time-series nesting, complexity control, explainability/feature audit, and no leakage.

You are not required to use any old K, threshold, Top-N, fixed20 exit, gate, score or DXY/SOX convention. Search entry/exit/holding/sizing logic as research variables only when their timestamp and execution assumptions are valid.

Do not confuse a larger search space with better science. Favor parsimonious models unless added complexity survives nested validation and stability tests.

## 4. Objective: profit + win rate, with risk and evidence constraints

Do not optimize win rate alone. A 90% win-rate strategy with poor expectancy or catastrophic tail loss is not a winner.

At minimum report for every serious candidate and every evaluation fold:

- after-cost compounded return / NAV;
- CAGR if duration supports it;
- per-trade mean and median net return;
- expectancy;
- win rate;
- trade count and active years/regimes;
- maximum drawdown;
- downside/tail metrics (e.g. worst trade, 5% tail/CVaR where sample permits);
- turnover / holding time / exposure;
- concentration by ticker/date/regime;
- profit factor where meaningful;
- calibration/AUC only if the model predicts probabilities;
- sensitivity to costs and execution assumptions.

Use a **Pareto frontier** over after-cost profitability, win rate and risk/stability rather than hiding everything inside one arbitrary score. If a deterministic champion must be chosen, pre-register the tie-break/selection rule before looking at its final nested evaluation.

Minimum eligibility should reject obviously tiny or concentrated samples. Derive and justify thresholds from the available history; do not select a minimum trade count after seeing which candidate it favors.

## 5. Costs and executability

The old E2 aggregate round-trip research assumption was 0.8%. Treat that as a historical baseline, not proven universal real cost.

For comparability, at minimum evaluate aggregate round-trip cost scenarios:

- 0.8% (historical baseline)
- 1.2% (1.5× stress)
- 1.6% (2× stress)

Do not double-count invented brokerage/spread/slippage components on top of the aggregate assumption unless independent evidence supports a new decomposed cost model.

When testing entry timing or intraday strategies, require actual evidence for tradability, quote age, bid/ask/depth, limits, latency and fills. Otherwise restrict the research to a coarser legally-supported execution assumption such as next-session open.

## 6. Multiple testing and overfit control

The reset intentionally permits broad research, so false discovery risk is high. Record and control it.

Required:

- unique experiment/trial IDs;
- exact code/data-cutoff/config hashes;
- append-only record for every evaluated trial, including errors and rejects;
- count all variants, not just survivors;
- nested selection inside chronological folds;
- parameter-neighborhood/stability tests;
- leave-one-year/regime-out tests where meaningful;
- remove-best-trades / concentration stress;
- cost stress;
- block/bootstrap confidence intervals when sample size permits;
- explicit multiple-testing correction or false-discovery analysis appropriate to the family;
- probability-of-backtest-overfit / deflated performance analysis when statistically meaningful;
- complexity penalty and feature-count accounting;
- no post-hoc rescue conditions applied only after seeing a failure without registering them as a new trial/family.

If sample size is too small for a statistic, say `INSUFFICIENT_SAMPLE`; do not emit a misleading precise p-value.

## 7. Suggested staged research process

### Stage A — corpus + lineage

Deliver:
- full path/commit inventory;
- causal mother-table schema;
- feature coverage matrix;
- corruption/missing-evidence report;
- imported historical experiment ledger.

No model winner yet.

### Stage B — baselines

Reproduce, where possible and byte/metric-consistent:
- Candidate B;
- Q017 historical/prospective reference behavior under its exact historical contracts;
- any other old model with adequate evidence.

If reproduction fails, record `BASELINE_REPRODUCTION_FAILED` and investigate before comparing a new model against it.

### Stage C — hypothesis families

Pre-register a finite batch of model families / feature groups / hyperparameter search budgets. Automated search is authorized in research, but every trial counts.

### Stage D — nested chronological search

Perform training/model selection entirely inside nested time-series folds with appropriate purge/embargo. Generate fold-level metrics and trial ledger.

### Stage E — robustness destruction

Try to kill the leading candidates using:
- higher costs;
- parameter perturbation;
- leave-one-year/regime-out;
- remove best trades;
- concentration caps;
- feature ablation;
- alternative reasonable calendar/data-quality assumptions;
- corrupted/missing-data exclusion;
- outcome-horizon perturbation where causally legal.

A robust candidate should survive attack; do not rescue it after failure by adding hindsight conditions.

### Stage F — research winner / Pareto set

Return:
- all Pareto-optimal candidates;
- one proposed historical research winner only if a pre-registered selection rule supports it;
- exact model/formula/code/config;
- fold-level and aggregate metrics;
- trial count and multiple-testing adjustment;
- failure modes and regimes where it loses;
- comparison with all reproducible old baselines;
- `NO_ROBUST_WINNER` if warranted.

Do not promote it to production.

## 8. Required deliverables on the research branch

Create a new subdirectory under `research/codex_full_reset_20261023/results/` containing at least:

1. `DATA_LINEAGE.json`
2. `COVERAGE_MATRIX.csv` or equivalent machine-readable table
3. `DATA_QUALITY_FAILURES.jsonl`
4. `EXPERIMENT_LEDGER.jsonl` — includes imported historical attempts plus every new trial
5. `SEARCH_PLAN.json` — frozen before the broad search
6. `TRIAL_SUMMARY.csv`
7. `PARETO_FRONTIER.json`
8. `ROBUSTNESS_REPORT.json`
9. `WINNER_OR_NO_WINNER.json`
10. `REPORT.md`

All results must include the exact source commit/tree, code commit, data cutoff, feature set, execution/cost assumptions and authority statement.

## 9. Stop conditions

Stop and report rather than inventing evidence if:

- PIT membership/data lineage cannot be proven for a feature;
- required outcome prices are missing/corrupt;
- a historical baseline cannot be reproduced and the difference cannot be explained;
- a candidate depends on future/revised information;
- evaluation cannot prevent overlapping-horizon leakage;
- the apparent winner disappears under reasonable cost/stability/concentration stress;
- trial accounting becomes incomplete;
- the only way to improve results is post-hoc rescue tuning;
- the winner is driven by an unacceptably tiny sample.

## 10. Final standard

The objective is not to produce the prettiest historical backtest. The objective is to identify the **strongest causal, after-cost, repeatable evidence** for higher profit and higher win rate using everything HENGCE has learned — including its mistakes.

A good final answer can be either:

- `ROBUST_RESEARCH_WINNER_FOUND`, with reproducible evidence and a future prospective validation plan; or
- `NO_ROBUST_WINNER`, with a clear explanation of why the apparent historical winners are not trustworthy enough.

Both are valid. Fabricating confidence is not.
