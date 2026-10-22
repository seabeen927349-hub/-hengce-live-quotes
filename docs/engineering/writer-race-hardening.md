# Phase 1.5 authoritative publication — Issue #16

Authoritative base: `d38f2c44a6f4efb254cc126ed2b9e162121589e3`.
This is persistence engineering. No production model, data, decision, cost,
schedule, authority or historical expected-output file is changed.

## Root cause and topology

Independent workflow concurrency groups protect only runs in their own group.
The command-center 08:50 E2 writer and 08:55/09:05 backup can compute from the
same checkout. Their prior push/rebase retry can replay stale writes against
newer state. Git can merge nonoverlapping edits to one canonical artifact
without detecting that the combined artifact is semantically inconsistent.
The synthetic legacy reproduction demonstrates this with text fixtures only.

`writer-topology.json` inventories all 29 existing main-writing workflow jobs
and their 31 publication steps at the authoritative pin. It includes existing
triggers/schedules, workflow/job concurrency, literal staging prefixes/globs,
producer-referenced canonical/latest/status paths, immutable paths and before/
after arbitration. `writer_topology.py --check` reproduces it from Git without
executing any workflow. Names confer no authority: explicit producer references
and their write-once contracts determine roles. E2 per-date history and Q017
supervisor/attempt/recovery diagnostics are mutable, not falsely called immutable.

All 29 main writers use the same publication helper, including otherwise dormant
manual archive/repair writers. Leaving their blind-rebase paths would allow a
second publication route to bypass the protection. Their compute commands,
trigger conditions, schedules and authority remain unchanged; none of those
manual research, repair or acquisition workflows was run for this task.
The separate research-branch-only writer is inventoried as an exclusion, not
silently treated as a main writer.

## Before and after

| Situation | Before | After |
| --- | --- | --- |
| E2 primary/backup use the same base | Separate groups permit overlap; retry may rebase stale output | One proposal can win; different mutable state from the stale proposal stops with exit 2 |
| Remote changes after computation | Rebase may apply stale data, even without a textual conflict | Fetch and compare exact Git trees; any mutable/input/code advancement stops |
| Remote changes between fetch and push | Non-FF rejection followed by blind retry in many writers | Exact SHA lease rejects; next attempt refetches and revalidates original proposal bytes |
| Identical state already published | Extra retries/commits possible | Raw bytes and modes identical at every proposed path: `IDEMPOTENT_NOOP`, no commit/push |
| Compatible immutable additions only | Rebase semantics depend on Git conflict detection | Validate both entire deltas are new regular files in explicit immutable prefixes; union only those bytes in an isolated index |
| Existing immutable evidence differs or is deleted | Some writers can rebase or replace evidence | Stop, including on a fresh remote base; conflicting observation never replaces existing bytes |
| Primary/backup 09:01 observation | Independent capture lanes | Same independent capture commands and concurrency groups; arbitration starts only after capture |
| Mixed evidence/status publication conflicts | Push/rebase may blend mutable output | Whole publication stops; newly captured immutable bytes are retained in a CI artifact with the receipts |

The helper publishes exactly one generated commit against its parent, the
producer's computation base. It never pulls, rebases, resolves conflicts, resets
or stashes the checkout. A candidate always has the observed remote as parent.
`--force-with-lease=refs/heads/main:<observed SHA>` provides exact compare-and-swap;
the parent check forbids history rewrites. No repository settings or branch
protection are changed. Normal uncontended artifact bytes are unchanged.

Retry is deliberately narrow: **both** full deltas must consist solely of new
regular immutable files. Modifying any code, input, status or other opaque file
blocks automatic retry even when the proposed output paths do not overlap.
Compatible additions use `read-tree`/`update-index`/`commit-tree` on an isolated
temporary index, retaining remote bytes and producer bytes exactly. The original
proposal/index/worktree remains untouched. No historical outputs are regenerated.

Existing pre-capture/pre-refresh syncs remain unchanged, before any computation
or generated commit; these are not post-computation publication retries.
Post-capture evidence verification reads the exact locally accepted proposal;
it no longer imports/rebases a competing writer's outputs. No producer calculation
or validator is moved or edited. Existing always-run diagnostic publication may
still run after an earlier failure; the helper refuses an unpublished local
ancestor, preventing it from smuggling a rejected prior commit into main.

## Observability

Every helper attempt emits a uniquely named JSON receipt to the GitHub log and
`$RUNNER_TEMP/hengce-publication/`, including workflow/job/run/attempt identity,
initial parent SHA, observed remote SHA, proposed/changed paths, publication
result and explicit conflict reason. Results are `PUBLISHED`, `IDEMPOTENT_NOOP`,
`RETRY_REVALIDATED`, or `CONFLICT_FAIL_CLOSED`. A rejected push is reported as a
failed closed attempt; it is never labeled revalidated before the next fetch.
Network/initial-validation failures can have an unavailable/null remote SHA.

Each migrated writer job always uploads receipts plus retained immutable capture
bytes as a run-scoped artifact. These diagnostics have zero signal/ranking/capital
authority. Retention follows the existing GitHub artifact policy, not WORM custody;
failed captures are not automatically promoted from artifacts into canonical state.

## Regression evidence

Tests were committed before the helper/workflow implementation. The pre-fix run
had 11 failing publication contracts and one successful reproduction of the old
blind-rebase failure. Tests use disposable local bare Git remotes, clones and
synthetic strings only. No live market outcomes or historical expected outputs.

- 15 race tests cover stale E2 bases, simultaneous E2 writers, remote advancement
  during the actual push, immutable conflicts, input changes, idempotence with
  distinct commit metadata, retries, compatible append-only union, independent
  concurrent Q017 publication, mixed-status rejection with capture retention,
  untouched dirty/untracked worktrees, and receipt fields.
- 7 workflow tests reproduce the 29-writer topology, verify all publication exits
  use the helper, preserve all nonpublication compute/validation steps, check
  every existing trigger/schedule/group/permission/job configuration, and confirm
  independent primary/backup capture ordering.
- Existing Engineering Replay must remain PASS/IDENTICAL; its eight existing
  script regression suites, workflow admission tests and mismatch self-test
  remain unchanged. GitHub run IDs/results belong in the PR for its exact head.

```sh
python -B tests/engineering/test_writer_races.py
python -B tests/engineering/test_writer_workflows.py
python -B tests/engineering/writer_topology.py --check
python -B tests/engineering/test_replay_workflow.py
python -B tests/engineering/replay_equivalence.py --self-test
python -B tests/engineering/replay_equivalence.py --before d38f2c44a6f4efb254cc126ed2b9e162121589e3 --after HEAD --report /tmp/hengce-writer-replay.json
```

## Unresolved risks and scope limits

- Conservative fail-close trades availability for safety. Frequent transport or
  other main updates can reject a long-lived observer even when its capture was
  valid. Mixed status/evidence transactions do not automatically cherry-pick
  evidence into main: captured bytes remain in the CI artifact, requiring review
  or an existing authorized recovery path. This limitation is explicit, not a
  claim that all concurrent captures reach canonical main.
- After compatible-addition publication or idempotence on a different commit,
  the helper leaves the local checkout untouched. A later mutable publication
  from that stale checkout fails closed; it needs a fresh validated computation.
- No remote advancement is ordered by wall-clock timestamps, and no last-writer-
  wins policy is introduced. Uncontended producer bugs remain producer bugs.
- External human/API writers and pre-merge in-flight jobs running old workflow
  code can bypass this helper. Repository-wide prevention would need separate
  operational controls/settings, which this issue forbids changing.
- This does not repair same-process temporary-file crashes, external canonical
  mother storage, distributed broker execution, or storage transactions outside
  Git main. No guarantees are claimed for those domains.
- GitHub artifact upload/service failure and retention expiry can limit diagnostic
  availability. There are at most three lease attempts, each with bounded Git
  command timeouts; rejected state is not silently forced through.

## Hard locks

No Q017/E2/M1 formula, weight, threshold, ranking, universe authority, capital
authority, broker execution, decision semantics or schedule change. No model
imports in the publisher. No optimizer/backtest/tuning, historical signal
regeneration/backfill, sealed holdout access or Phase 2 work. Engines remain
separate. M1 stays `RESEARCH_SHADOW_ONLY`, capital authority 0. Actual user trades
are not model evidence. B01–B09 remain PARTIAL; B10 remains
`BLOCKED_PENDING_EXPLICIT_HUMAN_AUTHORIZATION`;
`PROMOTE_TO_PRODUCTION=FORBIDDEN`. No subtask crossed a hard lock.
