# V43 Clean Prospective Observer Acceptance — 2026-10-24

The canonical prospective validation observer for frozen V43 is accepted as a **research-only validation instrument**.

## Canonical observer
- Branch: `research/v43-clean-prospective-observer`
- Commit: `959f96831fdea65f32bed65ca11011d67328f695`
- Commit message: `research(v43): establish canonical clean prospective observer`
- Parent: official research head `70904e263b6446e4c6c4c4243af0aae070db3997`
- Canonical commit contains only four text files: observer implementation, V3 launcher, protocol, and workflow. It contains none of the failed binary-reference experiments.

## Acceptance run
- GitHub Actions run: `40062355605`
- Conclusion: `success`
- Artifact ID: `12547942218`
- Artifact name: `hengce-ranking-v43-clean-prospective-observer`
- Artifact SHA-256: `0cdc57ae0f2d6de873eea526b6f9f1e6cc00ac34de70fa4ee70cc95b56317cb5`

## Hard parity result
- Frozen V43 source expected Git blob: `60c3ce478c5f88bfce9263739a310ea5f5cf05a6`
- Frozen V43 source actual Git blob: `60c3ce478c5f88bfce9263739a310ea5f5cf05a6`
- Source verified: `true`
- Rebuilt historical event count: `30`
- Rebuilt historical events SHA-256: `ed5b0c4caff523525ecafb303e04dc82bc07d7d2fe706733edf4ce0180ecfd6e`
- Expected frozen events SHA-256: `ed5b0c4caff523525ecafb303e04dc82bc07d7d2fe706733edf4ce0180ecfd6e`
- Parity verified: `true`
- Invalid events: `[]`
- Last frozen exit: `2026-09-23`
- Dynamic frozen subset SHA-256 also matches exactly.

## Current prospective state
- Read-only main Q017 snapshot maximum date at acceptance: `2026-10-22`
- Snapshot SHA-256: `e46c5788404dcf8ac780af75f84cbb3c39cb63f11d161113a8356d1a19f3d26a`
- Status: `WAITING_FOR_POST_LOCK_DATA`
- Complete post-lock baskets: `0`
- Pending schedule candidate: signal `2026-09-24`, with `17` sessions available after signal and `21` required. It is pre-lock and can only act as a schedule bridge once complete; it is never prospective evidence.
- Full daily marked path is preserved for future drawdown monitoring.
- First 6 complete post-lock baskets remain interim/non-decisional; first 12 remain the registered primary read.

## Research integrity
- New model evaluations: `0`
- Parameters searched: `0`
- Historical challenger selection rerun: `false`
- No prospective GLOBAL fallback is authorized; the observer fails closed if frozen V43 prior-regime ICIR requirements cannot be satisfied.

## Authority boundary
Research only. Capital authority remains 0. Broker execution false. Production promotion false. Main/Q017/E2/M1 unchanged. PR #30 unmerged. No local retuning and no V45 authorization.
