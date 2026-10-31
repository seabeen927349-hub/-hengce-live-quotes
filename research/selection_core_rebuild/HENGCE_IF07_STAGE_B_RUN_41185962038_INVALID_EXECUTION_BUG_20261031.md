# HENGCE IF-07 Stage B — Run 41185962038 Invalid Execution-Bug Receipt

Date: 2026-10-31
Challenger: `IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1`
Affected run: `41185962038`
Affected commit: `faa5c17b1f4c2d751580c2a1b41f15eccf1e0548`
Formal research authority: `NONE`
Forward-return authority: `NONE`

## Verdict

`INVALID_FOR_FORMAL_RESEARCH_EXECUTION_BUG`

The run must not be used for Stage B sample construction, Discovery-return opening, Validation, promotion, or production.

## Exact reason

The first Stage B executor introduced an unfrozen transport retry schedule (`0, 2, 5, 10, 20, 40` seconds) for t57 requests.

The frozen Stage B exact-metadata contract states that blank, missing, non-`無`, duplicate, ambiguous, **rate-limited**, or structurally unresolved metadata must fail closed for the affected candidate. The frozen V0.1 Implementation Contract contains no retry-count or backoff rule. Because retry behavior can alter which candidate metadata become resolved versus fail-closed, that behavior can alter the research sample.

Under the user's explicit execution instruction, any mechanically underspecified rule must not be filled in ad hoc. Therefore this retry schedule cannot acquire formal authority after execution began.

## Legal engineering correction

The frozen V0.1 Implementation Contract explicitly permits one blank-year t57 query per ticker to index available IFRS consolidated-report rows and separately permits engineering bug fixes only when they restore the frozen contract and are versioned/logged.

The corrected execution must therefore:
- use only the exact frozen 187-event candidate authority;
- derive the exact 128 candidate tickers only from the admitted manifest;
- sort ticker request order deterministically;
- issue exactly one official blank-year t57 query per ticker;
- perform zero retries and zero backoff rescue;
- fail closed for that ticker's affected candidates on HTTP failure, rate-limit marker, access denial, timeout, or structurally unresolved response;
- preserve raw responses, request identity, run identity, hashes, and exclusions;
- inspect no prices or forward returns until the no-return metadata/signal-date/PIT/count gates pass.

No Selection formula, threshold, candidate, missing-value rule, horizon, null, regime, or promotion rule is changed by this correction.
