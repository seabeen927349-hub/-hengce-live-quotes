# Architecture before and after

Starting commit: `780e8a225de637c32b42da0d28f5aa1428e49e20`.

| Stage | Before | After |
|---|---|---|
| Morning inputs | Macro cache / prewarm snapshot, zero signal authority | Unchanged |
| 09:01 capture | Independent primary/backup supervisors; existing TWSE MIS transport | Unchanged, including timeouts, retries and source contract |
| Observation | Immutable dated schema-5 JSON; 100% eligible quote-row coverage; electronics universe/hash binding | Unchanged |
| Compute, ranking, decision | `build_decision_from_observation`; frozen formula/gates/top3; immutable dated decision | Original source bytes unchanged |
| Decision validation | Exact deterministic rebuild, repeated canonical hashes | Same comparison and failure reasons for original cases; reuse the already computed expected hash and payload hash (8 → 6 hash calls) |
| Monitor validation | Checked decision hash reference and ticker order, but not every score/gate/universe field | All immutable decision fields must equal the locked decision; only module, projection timestamp and monitor metadata may differ |
| Current authority selection | Display trusted `latest.json` schema/authority labels plus CSV membership | Read current dated immutable decision; validate its original observation and exact deterministic output; reject missing/future evidence |
| Scan action output | Several PASS/policy/date flags sufficed | Existing full publication validator checks transaction ID, hashes, source evidence and freshness; additional schema-5 binding, Q017 provenance, score/rank/order and CASH guards |
| Public unified display | Valid generic mixed publication could display legacy rows | Historical `build()` remains available for audit; public CLI additionally requires Q017-only schema-5 evidence |
| Shell action-board entry | Generic candidate union runner | Q017-only candidate runner; public display still requires schema-5 bindings |
| Retired E2 display | Raw source authority string propagated | Explicit `formal_authority=false`, `research_only=true`, retired research authority label; original source authority retained as audit metadata |
| Router health read | Observability state imported by producer/router | Observability-only placeholder, no health-data dependency |
| Engineering CI | Earlier mixed E2/single-HENGCE migration probe asserted obsolete router structure | Existing unfiltered workflow runs the new Q017-only exact replay, dynamically compares PR base/head and also pins the cleanup baseline; older historical tools and drift-detector self-test retained |

The shared `hengce_q017_formal_output.py` owns output policy and current-session evidence selection. It does not implement a second model, ranking function or quote fetch. The same `Q017_ONLY_POLICY` constant is imported by the router and Q017-only wrapper.

The daily canonical pipeline remains separate: prior-day daily features, top1, no DXY and H20 are not the schema-5 opening-observation/top3/DXY/H10 contract. It cannot self-certify formal authority with a Q017 label. Existing daily bridge publications do not contain the necessary schema-5 bindings, so their formal action output is blocked. No bindings were fabricated, no scores translated and no historical evidence regenerated.

The full import/function/artifact inventory and every workflow reference are in `SOURCE_INVENTORY.json` and `Q017_AUTHORITY_ROUTE_MAP.json`. Historical code remains in place because v5 still imports older transport/data helpers and dynamic operator usage cannot be disproved from static references. No evidence or model family was deleted.
