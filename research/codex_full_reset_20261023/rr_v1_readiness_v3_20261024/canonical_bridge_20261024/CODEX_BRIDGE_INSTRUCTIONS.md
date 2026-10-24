# Codex bridge instructions

This bundle bridges the existing ChatGPT Library canonical vessel into the RR V1 research workflow.

## What is newly available
The actual bytes of:
`/HENGCE_CANONICAL/HENGCE_2026_HIST_MOTHER.csv`

The file is not a reconstructed or second mother. It is the existing canonical Library artifact.

Verified SHA256:
`60fb82570d48ef2620a8390d612457fc79e795b9e1fe485f61739103bfa8db47`

Verified rows: 207,218
Coverage: 2026-01-02 through 2026-10-21
Duplicate (Date,Ticker) keys: 0

## How to use
Use these bytes to re-run the Stage-A canonical-mother accessibility/authenticity reconciliation.
Do not count this as a model evaluation.
Do not retune RR V1.

The previous blocker
`CANONICAL_ACCUMULATED_MOTHER_REFERENCED_BUT_NOT_ACCESSIBLE`
should now be reassessed using the actual bytes and receipt.

## Important non-resolution
This bundle does NOT prove 2026-10-22 mother completion.
The existing main `eod/20261022/status.json` records:
- price COMPLETE
- institutional COMPLETE
- margin PENDING
- mother PENDING
- formal_complete_day=false

Therefore do not fabricate a 10/22 promotion or append a synthetic second mother.

Use the existing EOD-to-canonical bridge only if/when its own contract is satisfied.

## Authority
Research only. No production Q017/E2/M1/V43 changes.
No main write. No broker execution. Capital authority = 0.
