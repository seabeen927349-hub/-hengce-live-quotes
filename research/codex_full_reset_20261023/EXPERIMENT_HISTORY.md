# HENGCE full-reset experiment history

This file is a required negative-and-positive evidence ledger for the 2026-10-23 full research reset. It is **not** a ranking of preferred models. Codex must read the underlying pinned commits/artifacts, not rely on this summary alone.

## Rule

Every successful, failed, rejected, aborted or abandoned line of research remains visible. A failure must not disappear merely because a later model looks better. Old production or research champions receive no privilege in the reset.

## Model / signal research

### E2_PROFIT_MAX Candidate B — validated historical reference

- Evidence: `research/e2_profit_max/E2_PROFIT_MAX_CANDIDATE_B_FINAL_VALIDATION_20261019.json` and PIT validation lock.
- Result: PASS final research validation under its frozen contract.
- PIT 2023–2025: +53.01% compounded return, 13 entries, 8 wins, 61.54% win rate, max drawdown -41.63%.
- Observed 2026 through 2026-10-16: +74.96%, 6 entries, 3 wins, 50% win rate, max drawdown -10.41%.
- Important limitation: tiny trade count; 2023–2026 is now exposed. Treat Candidate B as a reproducible baseline/reference only, not the reset champion.

### E2 Round-2 finite search

- Evidence: `research/e2_profit_max/round2/**`.
- Searched a deliberately finite gate/exit space under frozen residual-reversal core.
- Includes payloads, candidate-date/macro masks and code needed to reproduce what was actually tested.
- Use both winning and losing grid cells. Do not infer that untested families were inferior.

### E2 P2-A baseline-destruction diagnostics — ABANDONED / incomplete

- PR #26, branch `phase2/e2-p2a-baseline-destruction-20261023`.
- Pinned head: `fbe16b4ec1c9b3495704b1ef716accd9e11b9ece`.
- Leave-one-year-out remained positive across removal of 2023, 2024 and 2025.
- Trade-level diagnostics were blocked because preserved Round-2 event payloads were unreadable/corrupt.
- No candidate was created or accepted. No holdout was opened.
- This is a first-class failed/abandoned experiment. Codex must investigate the data defect and must not erase it from trial accounting.

### Q017 prospective characterization

- PR #27, branch `phase2/q017-prospective-optimization-20261023`.
- Pinned head: `e9c39b0d9c801ecefdc54fb781c7fd188e1f847e`.
- Registered nearby K and residual-admission challengers against the then-production schema-v5 family.
- Pre-activation 2026-10-21/22 locks were explicitly smoke-only, not valid winner-selection evidence.
- This work is useful for sensitivity/structural evidence, not a proof that the old Q017 family is optimal.

### Canonical Q017 / unified HENGCE migration

- PR #28, pinned head `c2bfe20cd4534df439ffb318d67554eec1fd18a0`.
- This is primarily contract/runtime/data-lineage engineering, not a profitability experiment.
- Current canonical Q017 and old schema-v5 09:01/Top3/DXY Q017 are incompatible contracts. Preserve both histories; do not silently translate performance evidence across them.

### Candidate C profit + win-rate screen — FAILED / ABORTED

- Branch `research/hengce-profit-winrate-optimization-20261023`.
- Pinned head `4930fb042354d0abacdab47d2f16ab12846f89ff`.
- Workflow run `39907799192`.
- Compile and unit-test stage passed; the real-data locked finite research screen failed.
- User then explicitly stopped the attempt.
- Preserve the code, CI failure and its narrow SOX-gate × exit hypothesis as negative evidence. The new reset is **not** constrained to that search space.

### Q012 microstructure integrity work

- PR #1, pinned head `5303f4382c44fa2d2a3955fae781220453df66c1`.
- Found that feature extraction could discard trades without prior depth or attach invalid/mismatched cached books.
- Fixed/characterized integrity issues without claiming profitability improvement.
- Critical lesson for the reset: do not use microstructure fields unless timestamp/symbol/book validity and availability are proven. Missing depth stays missing.

## Research governance / evidence work that must remain in the corpus

### Phase 1 evidence foundation

- PR #13 (`fb4ac5809de1012edaedf10e2c9870770db39eae`) and PR #15 (`840771e20215cbf9899dd74599a6fdc2a5af881c`).
- Built coverage, dependency, lineage, executability and known-gap inventories.
- These are not model wins; they define what can and cannot be scientifically claimed from the stored data.

### Phase 2 governance freeze / scoped authorization

- PR #23 (`e067d9bb68cf9eb7f21ba01080fc1b32c6509475`) and PR #25 (`21c8a8c0d1973a0a07bf1b97a605c864cbb36cbb`).
- Built experiment ledger/custody concepts and previously scoped E2 diagnostics.
- Old search restrictions are historical governance evidence. The new reset authorization broadens **research-only** model search, while capital authority, broker execution and production promotion remain zero/forbidden.

## Engineering/data-path history relevant to research validity

The repository also contains merged work on original-vessel EOD ingestion, mother-first gating, no-fill state handling, writer races, recovery safety, health observability, all-electronics live coverage, calendar/closure handling and exact engineering replay. These are not alpha models, but they explain provenance, data gaps, failure modes and which artifacts can be trusted. Codex should inspect the pinned repo snapshot and PR history when a feature depends on one of these paths.

## Mandatory interpretation

1. There is no inherited champion in this reset.
2. Prior success is a baseline to beat robustly, not a parameter neighborhood to overfit.
3. Prior failure is information and must remain in the experiment ledger.
4. 2023–2026 is exposed development/validation history, not pristine unseen holdout.
5. If the complete causal/PIT table cannot be reconstructed without leakage, reduce the feature set; never fill missing evidence with hindsight.
6. If no candidate survives multiple-testing, risk, cost and stability checks, the correct result is `NO_ROBUST_WINNER`.
