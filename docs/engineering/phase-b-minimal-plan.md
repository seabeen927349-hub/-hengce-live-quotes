# Engineering review: minimal changes and replay gate

Baseline: `900b0bc862e03a2b496129b0fc68d066c39542bf`.

This PR addresses only the missing reproducible before/after regression gate.
It does not repair existing authority, state-transition, or write-publication
defects. Those repairs change failure behavior and require separate review.
No production source, model, ranking, authority contract or historical data is
changed. No Q017, E2, M1 or legacy capital authority is created.

## Phase B: ordered by behavioral risk, lowest first

| Order | Why / change | Files affected | Risk | Equivalence proof | Required regression |
| --- | --- | --- | --- | --- | --- |
| 1 (this PR) | Missing full historical before/after evidence: add an offline replay gate | `tests/engineering/replay_equivalence.py`, the new replay workflow, this document | Low: test-only; production files must be byte-identical | Two independent git archives, fixed historical inputs and clocks; exact complete payload and full candidate ranking comparison | Q017 binding and fail-closed cases, E2 history failure, legacy kill switch, display isolation, router time branches |
| 2 | Measure failures and performance before optimizing | New independent diagnostics under `tests/engineering/` | Low if diagnostics never feed authority | Production artifact bytes unchanged before/after diagnostics | No writes, no network backfill, no capital authority |
| 3 | Reduce duplicate helpers / wildcard imports | Public command center and selected data helpers only | Low to medium; imports, numeric parsing and ordering can change | Exact historical payload, full ranking, scores, schemas, hashes and failure equality | Import compatibility, stable ordering, numeric edge cases |
| 4 | Remove fixed-temp writer races and partial immutable publication | Core/display/review writers, Q017 write-once/recovery, EOD publication | Medium to high; concurrency and crash behavior change | Normal-path byte equality plus separately reviewed failure differences | Competing writers, process death, partial partitions, no-clobber and receipt coherence |
| 5 | Close authority-validation gaps | Display, v5 guard/monitor/recovery | High; currently accepted malformed inputs would be rejected | Valid historical results identical; STOP and present changed failure behavior | Wrong module, score, authority, observation/universe hashes and late evidence |
| 6 | Align session and postclose orchestration | Router, E2 morning and affected workflows | High; state transitions / fail-closed behavior may change | Fixed prior states and provider responses; exact step-by-step comparison | Stale pending, invalid override, quote date, timeout, partial EOD and engine isolation |

No model-performance work belongs in these changes. Any such idea must remain
a separate research proposal with no production ranking or authority effect.

## Replay method

Run from a complete checkout with Python 3.12 and `requests==2.32.5`:

```sh
python -B tests/engineering/replay_equivalence.py \
  --before 900b0bc862e03a2b496129b0fc68d066c39542bf \
  --after HEAD --report /tmp/hengce-replay.json
```

The runner exports before/after code into separate temporary directories, then
copies the SAME snapshot data from the pinned baseline into each directory.
All engine writes remain in temporary directories. Provider calls are blocked.
Only the production SOX downloader is replaced by an offline no-op; the original
SOX feature function reads the original pinned CSV. No downloaded or synthetic
market values replace historical inputs.

Q017's complete decision must equal its committed historical decision, including
the original computation timestamp and decision hash. The full candidate list
is captured from the original function's local `cand` at return using a Python
profile hook. The hook never changes a candidate, formula, score or sort.
E2 executes its original postclose function against the fixed history, macro CSV,
execution override and IDLE prior state; its complete result must equal the
committed historical state. Its full candidate list is captured directly from
the original `prepare_features` return value. This is a same-session fixed-state
replay, not a multi-session portfolio backtest or model rebuild.

Both full ranking payloads, all scores, complete engine outputs and decision
hashes are compared exactly. No tolerance, ignored official field, re-ranking,
time normalization or acceptance of a changed historical result is allowed.
The report includes before/after SHAs, snapshot SHA, changed files, full ranking
counts/digests, binding hashes, failure cases and zero-capital checks.

Failure fixtures invoke actual CLI handlers for missing quote, late quote,
invalid observation hash, invalid universe hash, missing observation and E2
history unavailability. The legacy radar kill switch, separated display and
router time branches are also checked. Synthetic invalid inputs are confined to
temporary copies. Known guard/display weaknesses are not silently corrected or
given new authority by this test.

The first PR deliberately rejects changes outside engineering tests/docs and its
new read-only workflow. All production code and historical artifacts therefore
remain byte-identical. This restriction must be consciously reviewed before a
later production engineering PR can use a broader gate.

## Limits and STOP rule

This fixture covers 2026-10-21 Q017/E2 and the listed failure routes. It does not
claim exhaustive state-machine coverage, real provider reliability, concurrent
publication correctness, M1 numerical replay, or access to the external canonical
mother. M1 and legacy production artifacts remain unchanged. Existing defects
remain separately tracked by the Phase B table.

Any historical output or before/after mismatch raises `STOP`, exits nonzero and
does not publish a PASS report. Investigate and present the difference for human
judgment; never update the historical expected output to make a test pass.
CI has `contents: read`, no production schedule, no commit/push/deploy step and no
merge capability. Local test success and remote CI status must be reported
separately; an unrun workflow is not a passing workflow.
