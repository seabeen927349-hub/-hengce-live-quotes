# HENGCE Final Research Archive — 2026-10-24

## Purpose
This archive freezes the complete research evidence needed to reconstruct the V42→V43→V44 decision and the subsequent frozen V43 prospective-shadow gate. It is research-only evidence, not production authorization.

## Final decision
- **Primary historical research frontier:** V43 Expanding Regime ICIR.
- **Secondary Pareto point:** V42 V41 Equity Budget, retained for lower drawdown.
- **Rejected:** V44 Leadership Persistence; no nearby retune.
- **V45:** not authorized. New model evaluation requires a separately preregistered, genuinely orthogonal PIT/no-lookahead information family.
- **Prospective state:** V43 shadow gate is `WAITING_FOR_POST_LOCK_DATA`; V43 is **not** prospectively validated yet.

## Key 1.2% cost results
| Model | Compounded return | Max DD | Remove-best | Win rate | Role |
|---|---:|---:|---:|---:|---|
| V39 reference | +338.2145% | -26.3897% | +190.1879% | — | prior return reference |
| V41 reference | +324.3464% | -18.5935% | +181.0044% | — | high-return/lower-DD fixed reference |
| V42 | +277.5130% | **-16.2472%** | +149.9911% | 63.33% | secondary Pareto |
| **V43** | **+342.6454%** | -17.6664% | **+193.1221%** | **66.67%** | **primary frontier** |
| V44 | +49.5031% | -52.6417% | +7.9280% | 46.67% | rejected |

At 1.6% cost, V43 remains strong (+306.4882% compounded; +169.8577% remove-best), while V44 remove-best falls below zero (-1.3001%).

## Evidence levels
1. V30/V32/V33/V39/V41 are retained as historical/fixed-reference evidence from the pre-result handoff and formal V42/V43 artifacts.
2. V42/V43/V44 and V43 prospective shadow are retained as raw byte-for-byte Actions ZIP artifacts with SHA-256 in `FINAL_RESEARCH_MANIFEST_20261024.json`.
3. The pre-result V43 handoff ZIP is retained to preserve the exact research boundary before V43 was validated.
4. Repository frontier lock: `2e48350b8eab28c7fd81d1144e15aa3fa892b855`.
5. Captured research branch head before archival commit: `b5e53bc459d216958893c6b0fd28eb6f5ab8c70f`.

## Hard authority boundary
The archive carries zero operational authority: no main write, no Q017/E2/M1 production change, no broker execution, no capital authority, no production promotion, and no PR #30 merge authorization.

## Verification
Verify every archived file against the SHA-256 values in `FINAL_RESEARCH_MANIFEST_20261024.json`. The raw ZIPs are preserved so the result JSON/event JSONL/protocol payloads can be re-extracted without relying on GitHub Actions retention.
