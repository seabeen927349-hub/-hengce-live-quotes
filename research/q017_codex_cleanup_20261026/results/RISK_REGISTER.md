# Risk register

| ID | Risk | Treatment / residual limitation |
|---|---|---|
| R1 | Daily canonical Q017 and schema-5 Q017 have conflicting contracts | Daily artifacts remain research/bridge inputs. Formal schema-5 hashes, scores, ranks and gate are mandatory at the public output. Existing daily bridge stays fail closed; enabling it requires separate reviewed evidence, not a label change. |
| R2 | A stale or forged latest pointer can misstate formal authority | Current dated immutable decision and its validated original observation control output. Stale `latest`/`decision_latest` pointers are ignored. Missing current evidence means no formal signal. |
| R3 | Monitor preserves tickers but changes scores/gate/universe | Guard compares every immutable decision field. Mutated score, market state and universe-member tests reject the payload. |
| R4 | Old model CLI or saved artifact still exists | Preserve history. Public router/display gates reject legacy provenance and old schema/model modules. Research artifacts keep zero capital/broker authority and explicit research labels where exposed. This does not prevent an administrator from writing future code; CI covers reviewed formal surfaces. |
| R5 | The standalone `Q017_LOCK_20261018.json` is referenced but not present in the repository tree | Do not invent it. Effective frozen code, original schema-5 observations/decisions, hard lock and exact historical source-byte test provide the tested baseline. No claim of external lock-file verification. |
| R6 | Historical helpers look obsolete but are imported by v5 | Retain them. Exact AST duplicate groups are candidates, not proof of interchangeability or deadness. No deletion or cross-contract refactor. |
| R7 | Live provider outages or workflow scheduling races | Capture, retry, recovery and publication lease behavior unchanged; existing offline resilience/race tests retained. No live session or online retry measurement performed. No claim of production deployment readiness. |
| R8 | Microbenchmark noise | Report all five samples and medians for both fixtures. Only the 8 → 6 canonical hash-call reduction is deterministic. Runtime samples may vary; no market-lane speedup or network reduction is claimed. |
| R9 | Missing runtime dependencies after display begins importing schema-5 validation | Install the existing pinned requests/openpyxl dependencies in display/integration CI; no new live service or market dependency. Policy module lazily imports the guard so partial installations can fail closed. |
| R10 | Historical CI encoded an older architecture and mixed-engine replay | Migrate the existing engineering replay workflow to this task's Q017-only audit, preserving unrestricted PR triggers, dynamic base/head comparison, fixed baseline and hard failure on drift. Retain old tools for explicit historical audit. |
| R11 | Schema-5 formula is immutable but validation hardening changes rejection/display behavior | Separate exact model replay from explicitly authorized authority-denial tests. Original GO and CASH decisions/rankings/hashes remain exact; forged/mixed/stale artifacts lose authority. |
| R12 | Repository branch may advance during work | Publish only the designated branch; no force push or main write. Inspect branch head before publishing. No merge, promotion, broker order or capital authority. |

No historical observation/decision, model coefficient, threshold, training set, outcome, market-data source or production schedule was changed. Human review remains required before any production merge.
