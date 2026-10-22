# HENGCE zero-authority health plane — Issue #18

Authoritative base: `9c904d1d8514138b1ca7b760063d71f637a3f5ec`.
No producer schedule, trigger, compute step, decision, model, threshold, ranking,
universe, capital or execution authority changes. Health does not repair state.

## Architecture

`config/hengce_health_v1.json` is a strict, versioned operational contract. It
records workflow files/names, original UTC cron expressions and Taipei meanings,
start/runtime grace, missing severity, artifact/date/timestamp/semantic fields,
source roles, and the health-only authority boundary. Unknown contract fields,
artifact paths, workflow identities or source semantics fail conservatively.
The snapshot records its policy hash and the observed main SHA.

`hengce_health_collect_runs.py` is the only live API component. A dedicated health
workflow queries scheduled main-branch Actions run metadata with `actions: read`.
It normalizes a bounded 48-hour, paginated manifest. Partial collection, HTTP/API
failure, pagination truncation, stale manifests and uncovered evaluation periods
produce unknown/degraded liveness rather than a fabricated missing-run claim.

`hengce_system_health.py` evaluates only injected time, local artifacts, policy
and the normalized manifest. It has no network calls, producer imports, decision
calculation, provider download, repair or promotion. Its four independent axes:

| Axis | Meaning |
| --- | --- |
| `scheduler_liveness` | Expected schedule slot absent, queued/not started, started late, running overdue, failed, or observed on time |
| `artifact_freshness` | Artifact date, generation/capture time, source binding and relevant completed-retry freshness |
| `data_readiness` | Actual input/leg/mother/downstream availability, including legitimate `PENDING_DATA` |
| `authority_safety` | Source authority boundaries and contradictions; health itself always has zero authority |

The aggregate severity is FAIL_CLOSED, DEGRADED, PENDING_DATA, PASS, then NOT_DUE.
Per-axis facts are retained: a failed run and pending margin can coexist. Reporting
bad health is a successful observation; a green health workflow means collection/
publication succeeded, not that trading or data readiness passed.

## Liveness inventory and windows

All times below are Taipei; original UTC crons remain in the machine contract.

| Existing lane | Expected schedule | Start grace | Missing severity |
| --- | --- | --- | --- |
| Q017 primary | 07:45; independent capture at 09:01 | 10 min | FAIL_CLOSED |
| Q017 backup | 08:15; independent capture at 09:01 | 10 min | DEGRADED |
| Daily command center | 06:30, 08:50, 09:03/09:10/09:20, 15:00/15:30/16:00/17:00 | 15 min | FAIL_CLOSED |
| E2 backup | 08:55, 09:05 | 10 min | DEGRADED |
| Q017 recovery | 09:02, 09:04, 09:06 | 10 min | DEGRADED |
| Macro cache | 05:45/06:15/06:45/07:15/07:35 | 10 min | DEGRADED |
| E2 postclose | 15:10/15:40/16:10 | 15 min | DEGRADED |
| Display refresh | Event-driven; no independent cron heartbeat | N/A | NOT_DUE for scheduler |

Runtime limits are explicit operational bounds in the contract (primary/backup
90 min, daily 60, E2 backup/macro/postclose 20, recovery/display 10). These health
bounds do not modify producer execution timeouts or trading thresholds.

Expected slots come from UTC crons mapped to the evaluated Taipei date, including
the preceding UTC date for early-morning observers. Only scheduled main runs count;
manual/PR runs cannot mask absence. Queued records after grace are distinguished
from missing records. Completed failure/cancel/timeout/skip is a workflow problem,
not inferred from source PENDING. Multiple matching records are marked ambiguous.

## Artifact freshness and readiness

| Artifact | Health rule |
| --- | --- |
| Q017 observation latest + dated canonical | Due after 09:12. Require current date, exact canonical binding, immutable/window flags, original canonical SHA256 convention, valid universe hash/causal membership, eligible/quote coverage and 09:01:00–09:01:59.999999 capture/fetch/generation times. Missing/late/invalid yields health FAIL_CLOSED only. |
| E2 morning | Due after 09:15. Current date/PASS alone is insufficient. Generation 08:50–09:00 is ON_TIME; after 09:00 through 09:15 is RECOVERY_WINDOW/DEGRADED; after 09:15 is LATE_RECOVERY/DEGRADED. Early, stale, missing or invalid state is distinct. |
| Current EOD status | Due after 15:20. Price/institutional/margin/mother and three-leg/formal/downstream flags remain separate. Source PENDING is PENDING_DATA. A completed final 17:00 retry with pending inputs emits FINAL_RETRY_SOURCE_PENDING. A status older than a completed retry is freshness DEGRADED, not scheduler failure. |
| Dual-engine display | Due after 09:12. Verify isolation/zero-capital locks, current Q017 date and valid observation, source dates and status coherence, and source timestamps no newer than display. E2's prior-session date is checked against known prior formal-complete EOD evidence, not a fabricated holiday calendar. Fresh display generation never launders stale inputs. |

Health rechecks integrity without importing producer modules or granting formal
decision authority. Original producer/guard validation remains authoritative.
Generation time cannot prove first publication/first-seen time: late persistence
of a genuinely 09:01 capture is not retroactively claimed on time. The next health
observation and run metadata show what was actually observed; no history backfill.

## Reasons

- Liveness: MISSING_SCHEDULED_RUN, NOT_STARTED_AFTER_GRACE, LATE_RUN, RUN_OVERDUE,
  WORKFLOW_FAILED, AMBIGUOUS_SCHEDULE_SLOT, SCHEDULER_METADATA_UNAVAILABLE.
- Timing/integrity: ON_TIME, RECOVERY_WINDOW, LATE_RECOVERY, EARLY_BIND,
  STALE_SOURCE_DATE, SOURCE_TIMESTAMP_INVALID, Q017_CAPTURE_LATE_OR_OUT_OF_WINDOW,
  Q017_OBSERVATION_HASH_INVALID, Q017_CANONICAL_BINDING_MISSING_OR_DIFFERENT,
  Q017_UNIVERSE_HASH_INVALID, EOD_STATUS_STALE_FOR_COMPLETED_RETRY,
  DISPLAY_STALE_OR_INCOHERENT_SOURCE.
- Readiness: SOURCE_PENDING, FINAL_RETRY_SOURCE_PENDING, SOURCE_STATUS_UNKNOWN,
  SOURCE_ERROR, CURRENT_SOURCE_UNAVAILABLE.
- Safety/contract: HEALTH_CONTRACT_INVALID, SOURCE_CAPITAL_AUTHORITY_NONZERO,
  SOURCE_BROKER_EXECUTION_ENABLED, DISPLAY_AUTHORITY_ISOLATION_INVALID,
  DISPLAY_CASH_BUY_COUNT_CONTRADICTION, EOD_UNEXPECTED_MODEL_AUTHORITY.

The evaluator emits additional precise structural/coverage reason codes where
needed. Raw provider/model payloads, scores and user trades are not copied into
health reports; source dates/timestamps/age and bounded operational facts are.

## Health workflow and publication

The new health workflow checks five milestones: 08:05, 08:40, 09:20, 15:50 and
17:20 on weekdays. It has its own concurrency group, never shared with capture.
Manual `self-test` is offline/read-only; `current-health` is restricted to main.
PR jobs run synthetic tests only. The live job has only `actions: read` and the
`contents: write` needed for snapshot publication, with no notifications.

The only canonical output is `hengce/health/latest.json`. Every snapshot, policy,
normalized run manifest and health publication receipt has:

```json
{"health_only":true,"signal_authority":false,"ranking_authority":false,"capital_authority_twd":0,"broker_order_execution":false}
```

Snapshots include schema, evaluated time/date, observed authoritative main SHA,
policy hash, all four axes, per-lane reasons and source dates/timestamps. The CLI
writes only the health namespace with a unique temporary file and atomic replace.
No initial live snapshot is fabricated or committed in this feature PR: the
approved main health job produces observations after merge/explicit dispatch.

Publication uses the existing `hengce_publish.py --profile health-only`, whose
write contract allows only `hengce/health/latest.json`. A changed producer input
rejects stale health publication; no blind pull/rebase is reintroduced. Snapshot,
metadata and publication receipts are retained as run artifacts even on failure.

All existing publication profiles, including the default `conservative-all`
used by E2, macro, daily/EOD, recovery and display, explicitly exclude only
`hengce/health/**` from their read barriers because no existing producer consumes
health. The producer-source/workflow reference audit found health consumers only
in the new health collector/evaluator/workflow and the publication contract.
Health policy/code paths remain dependencies, as do all unknown inputs. This prevents
the new 08:05/08:40 health writes from recreating the long-running-observer
availability defect. Synthetic local Git tests prove both this noninterference
and rejection of health writes to model paths. The pinned topology's 29 writers /
31 publication exits all declare this exclusion. Default-profile synthetic tests
cover E2, macro, EOD and display computed at B, health-only R, then successful
exact-lease transplant preserving health bytes; health arriving between fetch and
lease is revalidated. Mixed health + changed macro/unknown input, canonical
conflicts and immutable conflicts still STOP; identical output remains a no-op.
The existing writer-topology inventory records this dependency exclusion.

`tests/engineering/health_dependency_audit.py` enforces the other half of this
contract: producer computation must not consume or write the excluded health
namespace. Writer Race Safety runs on **every PR**, so a future helper/source-only
change cannot bypass the guard through a path filter. Both Writer Race Safety and
Health Observability run its offline static/mutation regressions.

The audit covers all inventoried producer workflows and a conservative superset
of current/future tracked repository code and operational config/contracts. It
rejects direct health path references (including staging/writing/dependency lists),
health evaluator/collector imports, split path components and constant string
concatenations. Local imports, including constant dynamic imports, are followed;
test helpers invoked/imported by a producer lose their test exemption. Missing
inventoried workflows or unparseable Python/contracts fail closed. Exceptions are
exact observability workflow/evaluator/collector/policy/publisher paths, plus
uninvoked tests and documentation; there is no production scripts wildcard.

Nine synthetic/static tests include injecting a health read into the actual E2
producer source map and rejecting it, future producer writes/staging/declarations,
imports, split paths and hidden test helpers. They modify no repository producer
bytes. A new genuine health dependency requires explicit profile/dependency and
guard re-audit; changing only a profile cannot silently exempt a producer read.
This is a static source guard, not a proof about arbitrary runtime-generated or
obfuscated paths, remote code or external writers. Such new mechanisms need human
dependency review; this task adds no runtime sandbox or model behavior.

## Synthetic validation

Tests use synthetic strings, in-memory artifacts, normalized runs, stubbed API
pages and disposable local Git remotes. Socket connections are denied in the
health test process; neither tests nor CI test jobs depend on live API results.
Tests cover every Issue #18 case plus malformed sources, UTC/Taipei boundaries,
manual-run masking, metadata incompleteness, stale EOD after successful retries,
display/source timestamp ordering, contract semantics and namespace publication.

Run:

```sh
python -B tests/engineering/test_system_health.py
python -B tests/engineering/test_writer_races.py
python -B tests/engineering/test_writer_workflows.py
python -B tests/engineering/replay_equivalence.py --before 9c904d1d8514138b1ca7b760063d71f637a3f5ec --after HEAD --report /tmp/hengce-health-replay.json
```

Existing regression/expected-output files and Engineering Replay are unchanged.
Run IDs/results for the exact final head are reported in the PR.

## Limitations and trading calendar

- This is a weekday/cron expectation model, **not an authoritative exchange
  calendar**. Weekend/non-scheduled cases are NOT_DUE; weekdays never prove the
  exchange is open. A holiday may cause missing-artifact alerts even while all
  schedules ran correctly. `market_data_expected=UNVERIFIED_EXCHANGE_SESSION`
  and calendar confidence/limitation are explicit in every snapshot.
- GitHub REST run metadata does not reliably identify the triggering cron for a
  delayed run. Slot attribution uses created-time buckets ending at the next
  expected occurrence; very late creation can be ambiguous/misattributed. Absence
  means no compatible record was observed, not proof of GitHub's root cause.
- GitHub can delay the health workflow itself. A workflow that never runs cannot
  publish its own heartbeat. No external watchdog/notification is added; consumers
  must inspect health snapshot generation age and run evidence independently.
- Read-only metadata failures/rate limits, pagination and retention affect evidence
  coverage. Unknown liveness is DEGRADED, not falsely called absent or healthy.
- Generation timestamps are not first-seen/publication lineage. No retrospective
  on-time arrival claim, authoritative holiday list or pristine sample is invented.
- Source changes during collection can reject publication. There is no aggressive
  retry/recompute loop; the next scheduled or authorized manual health run observes
  anew. Captured diagnostics remain available subject to artifact retention.
- The verifier checks operational source integrity/coherence, not profitability,
  fills, every conceivable state transition, permanent custody or model validity.
  B01–B09 stay PARTIAL. B10 remains BLOCKED_PENDING_EXPLICIT_HUMAN_AUTHORIZATION;
  Phase 2 is unauthorized; M1 stays RESEARCH_SHADOW_ONLY/capital 0;
  PROMOTE_TO_PRODUCTION=FORBIDDEN. Actual user trades are not model evidence.
