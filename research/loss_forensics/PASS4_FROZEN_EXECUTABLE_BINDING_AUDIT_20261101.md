# HENGCE Frozen Pass 4 Executable Binding Audit

Date: 2026-11-01  
Branch: `research/loss-forensics-20261101`  
Scope: exact provenance recovery only; no model redesign, no refit rescue, no live-outcome retuning.

## Decision

`INTERPRETER_BINDING_STATUS = DATA_BLOCKED_EXACT_EXECUTABLE_PROVENANCE_NOT_RECOVERED`

The exact executable provenance that produced the frozen corrected Pass 4 final results was **not recovered from the repository evidence searched in this audit**. The prior `INTERPRETER_BINDING_PENDING_FROZEN_EXECUTABLE` wording is superseded because the bounded provenance-recovery audit is complete and gates 1–9 are not all satisfiable from recovered artifacts. This is a fail-closed research state, not a model failure and not permission to reconstruct an approximation.

Allowed state until exact pre-existing provenance is independently recovered:

`SHADOW_DATA_COLLECTING / INTERPRETER_NOT_BOUND / DATA_BLOCKED`

Forbidden formal outputs remain:
- h=1 probability;
- h=1 classification;
- BUY / SELL;
- CONTROL_LOSS probability;
- calibrated early-warning probability.

## Frozen authority checked

Primary final authority:
- commit `20cc74b7c39897c07992de5ec9b215bf78949856`
- `research/loss_forensics/PASS4_CORRECTED_RECOGNITION_LATENCY_FINAL_20261101.md`

Frozen final h=1 metrics recorded there:
- Brier `0.1166464284`
- log loss `0.3777559378`
- ECE10 `0.0222562530`
- AUC `0.7276763337`

Frozen report SHA256 references:
- corrected candidate/features matrix: `1655fb0f0c3d297ce03a078714c7c11b7c663f941d77bf8a6e0236703bb40d3e`
- BASE predictions: `2a0630103bc4a0cc63924a83eb63c8d4655833fdc52c875b479f06740aa0e0c7`
- h=1 predictions: `2eb8231c596c9a23f25c42681705b3628a8126b74f8b92dd27ad5cc84d55c9f9`
- h=2 predictions: `22224690f48403477d580cc328d057eb7c588175685946078099b7067f6b2422`
- h=3 predictions: `e183958c08046c98c718383fad4e2b617d93f9ab09786a6ccef1fc4908f871b0`
- source-only diagnostic: `3dabf3b7acd03d6b1618b2f64f5b550449d131ab26ee62d715464777ca78bcba`

These hashes prove identity only if the corresponding artifacts are present. A hash is not an executable or recoverable payload by itself.

## Search performed

The audit searched:
- current research tree recursively;
- `scripts/`;
- Pass 4 preregistration / target-correction / execution-lock / model-lock / result / final reports;
- commit history around the Pass 4 execution window;
- serialized-model / notebook / table extensions including `.pkl`, `.joblib`, `.ipynb`, `.parquet`;
- repository references to Pass4 / recognition latency / `HistGradientBoostingClassifier` / stored prediction hashes.

Findings:
1. The frozen model class and hyperparameters are documented.
2. Chronological expanding-OOS and chronological Platt-calibration rules are documented at governance/report level.
3. The final h=1 cutoff and allowed semantic evidence bundle are documented.
4. No separately versioned serialized HGB state, calibrator state, exact executable script/notebook, exact frozen feature matrix, or row-level final prediction table was found in the searched repository evidence.
5. The two Pass 4 result commits inspected (`8d40f5957644ea1a44c23e19a781977676074ecb` and final `20cc74b7c39897c07992de5ec9b215bf78949856`) commit report artifacts, not the executable/model/prediction payloads required for exact replay.
6. The final report itself states that original historical V1 per-event probabilities were unavailable and that the comparison BASE was a strict-time current100 replication. This makes exact provenance discipline more, not less, important.

## Binding success gates

| Gate | Requirement | Audit result |
|---|---|---|
| 1 | exact feature definitions | `PARTIAL_NOT_BINDABLE` — semantic bundle documented, exact executable transformations not hash-bound |
| 2 | exact preprocessing / normalization | `FAIL_NOT_FOUND` — exact transformation/scaler state or deterministic executable not recovered |
| 3 | exact expanding-window training semantics | `PARTIAL_RULES_FOUND_EXECUTABLE_NOT_BOUND` |
| 4 | exact h=1 observation cutoff | `PARTIAL_RULE_FOUND_IMPLEMENTATION_NOT_BOUND` |
| 5 | exact coefficients/model state or deterministic refit procedure | `FAIL_NOT_FOUND` — class/hyperparameters alone are insufficient without exact feature/event pipeline |
| 6 | exact calibration procedure | `PARTIAL_RULE_FOUND_STATE_AND_IMPLEMENTATION_NOT_BOUND` |
| 7 | exact OOS event population | `FAIL_ROW_LEVEL_POPULATION_NOT_FOUND` — counts/date range are documented, exact row-level artifact is not recovered |
| 8 | rerun on frozen historical sample | `FAIL_NOT_EXECUTABLE_FROM_RECOVERED_PROVENANCE` |
| 9 | reproduce Brier/log-loss/ECE/AUC to tolerance | `NOT_RUN_EXACT_PROVENANCE_MISSING` |
| 10 | no live-outcome rule changes | `PASS` — no coefficient, threshold, label, gate, feature, calibration or outcome-driven change was made in this audit |

Because all ten gates are required and gates 1-9 are not all satisfied, binding is prohibited and the bounded audit is closed as `DATA_BLOCKED_EXACT_EXECUTABLE_PROVENANCE_NOT_RECOVERED`.

## Explicit non-actions

This audit did **not**:
- reconstruct Pass 4 from prose;
- train a new HGB that merely resembles the frozen run;
- substitute the source-only h=1 diagnostic;
- infer missing normalization or feature transforms;
- use prospective live outcomes;
- change any frozen coefficient, threshold, label, gate or calibration rule.

## Reopen condition

This fail-closed state may be reopened only if **pre-existing exact provenance** is recovered, such as a contemporaneous script/notebook plus exact feature/event artifacts, serialized state, or a deterministic refit package sufficient to satisfy all ten gates and reproduce the frozen metrics without live-outcome changes.

A new approximation, reconstructed implementation, live-outcome retune, or prose-derived clone does **not** satisfy the reopen condition and would require a separate preregistered research track.

Until then:

`DATA_BLOCKED_EXACT_EXECUTABLE_PROVENANCE_NOT_RECOVERED`

Production authority: **NONE**  
Trading authority: **NONE**
