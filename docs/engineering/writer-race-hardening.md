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
producer-referenced canonical/latest/status paths, immutable paths, explicit
dependency profiles/read barriers/write contracts and before/after arbitration.
`writer_topology.py --check` reproduces it from Git without
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
| Remote changes after computation | Blind rebase may apply stale data; initial PR rejected even unrelated E2 writes | Compare exact trees against declared reads/writes; incompatible write or input change stops; proven unrelated updates may be transplanted |
| Remote changes between fetch and push | Non-FF rejection followed by blind retry in many writers | Exact SHA lease rejects; next attempt refetches and revalidates original proposal bytes |
| Identical state already published | Extra retries/commits possible | Raw bytes and modes identical at every proposed path: `IDEMPOTENT_NOOP`, no commit/push |
| Compatible independent evidence/status | Rebase semantics depend on Git conflict detection | Check both read and write sets, then transplant only original proposed bytes in an isolated index |
| Existing immutable evidence differs or is deleted | Some writers can rebase or replace evidence | Stop, including on a fresh remote base; conflicting observation never replaces existing bytes |
| Primary/backup 09:01 observation | Independent capture lanes | Same independent capture commands and concurrency groups; arbitration starts only after capture |
| Mixed evidence/status publication conflicts | Push/rebase may blend mutable output | Unrelated lane status may coexist; actual write/input conflicts stop the whole transaction and retain capture bytes in CI artifacts |

The helper publishes exactly one generated commit against its parent, the
producer's computation base. It never pulls, rebases, resolves conflicts, resets
or stashes the checkout. A candidate always has the observed remote as parent.
`--force-with-lease=refs/heads/main:<observed SHA>` provides exact compare-and-swap;
the parent check forbids history rewrites. No repository settings or branch
protection are changed. Normal uncontended artifact bytes are unchanged.

## Dependency contracts and the real schedule regression

The initial PR incorrectly treated every mutable remote change as a global
barrier. The real schedule is Primary startup/sync at 07:45 Taipei and Backup
startup/sync at 08:15, followed by the 08:50 E2 morning bind and the observers'
09:01 capture publication. E2 legitimately advances main from B to R while both
observers still use B. This must not invalidate an independent Q017 capture.

`test_real_0745_0815_0850_0901_interleaving_publishes_both_captures` models exactly
that sequence with synthetic local Git fixtures. Original head `9346983` fails
with `REMOTE_ADVANCED_REQUIRES_FRESH_COMPUTATION_OR_HUMAN_REVIEW`; the corrected
publisher passes, retaining both captures/statuses and E2's exact bytes.

Every invocation explicitly selects a profile. Every receipt includes the exact
generated-commit write set, immutable subset, allowed write patterns, and a
conservative authoritative read barrier: **all paths, except explicitly proven
unrelated patterns**. This is a superset of actual reads, not a claim that a
producer consumes every tracked file. New or unknown paths remain dependencies.

| Profile | Allowed transaction writes | Proven unrelated remote changes |
| --- | --- | --- |
| `q017-primary-capture` | Primary observation/history/pointers, attempt/status outputs in the existing staging contract | E2 and dual-engine state, transport-only context, backup observation/status/attempt outputs |
| `q017-backup-capture` | Backup observation/history/pointers, backup attempt/status outputs | E2 and dual-engine state, transport context, primary observation/history/pointer and lane-specific supervisor status/attempts |
| `q017-decision-display` | Existing decision/history/ledger/latest and dual-engine latest outputs | Backup observation/status/attempt outputs and transport context; E2 state remains a read dependency |
| `conservative-all` | Actual generated-commit delta; existing staging paths remain in the inventory | None proven: full-tree read barrier until the producer's narrower dependencies are audited |

All 31 publication sites declare their profile. Primary/backup capture profiles
follow `hengce_q017_observer_supervisor_v2`, its v1 prewarm fallback,
`hengce_q017_observation_lock_v5`, the separate backup activation, macro cache,
premarket snapshot and v4 previous-decision readers. Their normal/fallback paths
read Q017 history, prior decisions, macro/premarket inputs and EOD readiness, not
E2 or rolling transport outputs. Source/workflow/contract changes are themselves
dependencies. `q017-decision-display` additionally follows the actual display
reader: E2 `state_latest.json` cannot be excluded. Future reader changes require
re-auditing these contracts; no blanket engine-namespace independence is claimed.

On each remote advance, reject incompatible overlap with any proposed write,
then reject every changed read-dependency path. Only after both checks pass may
`read-tree`/`update-index`/`commit-tree` on an isolated index overlay the original
proposed bytes onto the exact observed remote tree. No textual merge, recompute,
last-writer-wins rule or historical signal regeneration occurs. Exact lease
publication still arbitrates every attempt, including advancement during push.

After acceptance (including idempotent acceptance), a non-destructive two-tree
checkout update plus conditional local HEAD update adopts the accepted commit.
This lets subsequent decision computation start from the correct accepted base
instead of an unpublished sibling. Dirty paths unchanged between trees are
preserved; dirty/untracked collisions cause an explicit local-sync failure and
stop subsequent steps. No reset/stash or blind pull/rebase is used. Receipts
distinguish already-published valid remote state from a failed local adoption.

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
result, dependency profile, exact write/immutable sets, declared read barrier,
remote delta on revalidation and explicit conflict reason. Results are `PUBLISHED`, `IDEMPOTENT_NOOP`,
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

- 25 race tests cover the real 07:45/08:15/08:50/09:01 schedule, stale E2 bases,
  simultaneous E2 writers, unrelated E2 and changed Q017 macro/input dependencies,
  following decision publication after transplant, independent status transactions,
  E2-dependent display rejection, unknown inputs, out-of-contract profile writes,
  collision-safe checkout adoption, remote advancement
  during the actual push, immutable conflicts, input changes, idempotence with
  distinct commit metadata, retries, compatible append-only union, independent
  concurrent Q017 publication, capture retention,
  preserved dirty/untracked worktrees, and receipt fields.
- 8 workflow tests reproduce the 29-writer topology, verify all publication exits
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

- Legitimate unrelated E2/transport/other-lane updates no longer block scoped Q017
  publication. Real read/input changes, incompatible writes and unclassified paths
  still fail closed. Other unaudited writer transactions explicitly retain the
  conservative full-tree read barrier; their throughput is not claimed improved.
- A valid remote publication can precede local checkout adoption failure. That
  failure is explicit, preserves collisions and stops later computation; it does
  not roll back or rewrite an already accepted remote artifact. Rejected captures
  remain non-authoritative CI artifacts without automatic promotion.
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
