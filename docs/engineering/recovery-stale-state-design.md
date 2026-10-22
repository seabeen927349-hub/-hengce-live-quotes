# Phase 1.5: Recovery and Stale-State Operational Hardening

Status: **DESIGN ONLY — NOT IMPLEMENTED / NOT AUTHORIZED FOR EXECUTION**.
Read-only source inventory at PR #19's original head
`410f50ff1ec38bda659b63185d872c67d9b53741`, plus its health non-interference fix.
No recovery producer, schedule, model, decision, state, history or authority is
changed by this document. No workflow is dispatched for this inventory.

After PR #19 passes human review and is merged, create a separate Issue, branch
and PR from **then-current main**. Reinventory before implementation; these file
references and risks are observations, not evidence that future main is unchanged.
This document is a proposed task specification, not permission to start that work.

## Mission and boundaries

Recover safely from workflow failure, partial execution, retries, stale checkouts,
partial artifacts and late recovery without contaminating authoritative state.
Preserve the existing producer computations and source authority. Operational
reconciliation may validate or republish already valid evidence; it must not
invent market observations, rewrite an immutable decision or create hindsight.

Hard locks: no Q017/E2/M1 formula, weight, threshold, ranking, universe authority or
capital authority changes; no broker execution, optimizer, backtest, tuning,
historical signal regeneration, sealed holdout access, Phase 2 or automatic
promotion. M1 remains RESEARCH_SHADOW_ONLY / capital 0; B10 remains
BLOCKED_PENDING_EXPLICIT_HUMAN_AUTHORIZATION; PROMOTE_TO_PRODUCTION=FORBIDDEN.
Q017/E2/M1 stay separate. No shared Q017 primary/backup capture lock. Preserve
producer schedules. Any subtask requiring these boundaries to change is BLOCKED.

## Retry / recovery inventory and existing guarantees

Paths below are under `.github/workflows/` or `scripts/`. Idempotence means only
the property evidenced in the source, not blanket end-to-end exactly-once safety.
The full existing main-writer inventory remains `writer-topology.json` (29 writer
jobs, 31 publication exits); the additional health writer is documented separately.

| Workflow / lane | Existing retry / recovery surface | Evidence and limits |
| --- | --- | --- |
| `hengce-q017-primary-observer.yml` | 07:45 Taipei startup, supervisor preparation retries, bounded independent 09:01 capture; separate evidence and decision publication | `hengce_q017_observation_lock_v5.py::collect_observation/write_once/compute_decision`; existing dated observation reused, hash conflict rejected; canonical/aliases/history/ledger are separate local writes |
| `hengce-q017-backup-observer.yml` | 08:15 startup; independent 09:01 capture and backup status | `hengce_q017_backup_observer_v5.py::activate_backup_lane/observe`; separate backup namespace, no direct decision authority; mutable status/attempt summaries can be overwritten |
| `hengce-q017-recovery.yml` | Scheduled 09:02/04/06, manual optional date, push self-test | `hengce_q017_recovery_compute_v5.py::existing_decision/promote_if_needed/compute`; valid existing decision returns without recomputation; canonical-first, validated backup copied only when missing, differing hash STOP; daily recovery receipt regenerated |
| `hengce-daily-command-center.yml` | 06:30 premarket, 08:50 E2, 09:03/10/20 monitor/compute routes, 15:00/30,16:00,17:00 postclose; manual mode/date; selected steps continue on error | Public router and YAML conditions determine work; some earlier step failure may coexist with later status/display writes. Need enumerate transaction completeness per selected route, never infer from overall green status |
| `hengce-e2-morning-backup.yml` | 08:55/09:05, manual; pip retries | Existing current-date/module/PASS/authority check skips a completed bridge; it is date/status-only. `hengce_e2_live.py::build_morning` may update state before morning bridge, with new timestamps. Semantic safeguards exist, byte-level repeatability is not guaranteed; health retains lateness |
| `hengce-e2-profit-max-live.yml` | 15:10/40,16:10 postclose, manual date, selected code push | `build_postclose` consults prior paper position/override, then writes state and per-date history separately. E2 history is explicitly mutable in publisher contract; do not relabel it immutable |
| `hengce-q017-macro-cache.yml` | 05:45/06:15/06:45/07:15/07:35 refresh; manual refresh/validate/self-test; precompute sync | `hengce_q017_macro_cache_v1.py` refresh/validation; cache and source files must remain hash-bound. Later refresh can change bytes; no promise of byte-identical retries |
| `hengce-dual-engine-display-refresh.yml` | Daily workflow completion event (including failed completion), selected push, manual | Rebuilds display from current source files and overwrites latest; structure checks do not alone prove freshness or source transaction completeness |
| Daily EOD / original-vessel ingest | Repeated independent price/institutional/margin attempts; mother receipt gate; retries above | `hengce_eod_incremental_ingest.py::_read/_write/ingest`: valid complete leg reused (`ALREADY_COMPLETE`); duplicate date/ticker rejected. Individual CSV replacements/receipts/status are not one local transaction |
| Daily 10-session review consumers | Repeated postclose update | `hengce_q017_10d_review.py::append_session` and extension `append` deduplicate session date; cohort immutable fields checked. Whole ledger/summary writes still need crash/stale-base characterization. No review regeneration or counterfactual signal work authorized |
| `hengce-system-health.yml` | Milestone checks and manual self-test/current-health | Health-only namespace, stale-input rejection and independent concurrency; diagnostic success is not producer recovery success |
| Other inventory writers | Quote transport, electronics coverage, shadow and manual/dated utilities may be rerun by Actions | Characterize only current operational consumers before adding to recovery scope; existing publication CAS applies, not an end-to-end idempotence claim |
| Dated EOD ingest and research retry utilities | `hengce-eod-*-20261014/15/19/20.yml`, `hengce-e2-profit-max-round2-retry.yml` and related historical/research writers exist | Inventory references only. Do not dispatch, regenerate historical signals, inspect sealed data, run research acquisition/optimizer/tuning, or repurpose them as automatic recovery |

## Risk inventory

| Risk / crash point | Current evidence | Required proposed outcome |
| --- | --- | --- |
| Compute interrupted before local commit | Per-file atomic replacement is not a transaction across aliases/canonical/history; some steps continue on error | Validate a complete producer-specific write set in staging before proposing publication; partial files cannot silently become authoritative |
| Truncated write-once observation/decision | `write_once` uses exclusive file creation then writes bytes; killed process can leave an existing incomplete file | Malformed existing canonical must STOP and retain evidence; never replace it under an automatic retry |
| Commit complete, push not attempted / rejected | Proposal bytes exist locally; publisher compares against original parent and remote | Reconcile observed remote with original proposal and input hashes; unrelated health-only delta allowed, real input drift requires fresh validation/computation where lawful |
| Remote push succeeded, acknowledgement lost | Exact lease retry can observe identical remote output as IDEMPOTENT_NOOP | Inspect remote before retry; distinguish accepted output from unpublished proposal, retain accepted SHA/hash evidence |
| Remote accepted, local adoption failed/crashed | `hengce_publish.py` emits PUBLISHED then `read-tree`/`update-ref`; dirty/untracked collision can yield ACCEPTED_PUBLICATION_LOCAL_SYNC_FAILED (already tested) | Remote remains authoritative; fence all later local computation until fresh checkout and revalidation; never repush or recompute as if remote acceptance failed |
| Partial local checkout adoption | Worktree/index and HEAD updates are separate operations | Diagnose state using commit/tree evidence in disposable tests; recreate a clean checkout rather than destructive reset of evidence or continuing mixed state |
| Q017 canonical created, alias/history/ledger not written | `compute_decision` writes canonical first; ledger/history only if created. Existing-decision recovery returns early | Detect incomplete projection/evidence; report NEEDS_RECONCILIATION. Do not claim a ledger event exists, rerank or create a second decision to fill the gap |
| Duplicate append / overwrite | Q017 ledger append is guarded by newly-created canonical, but not atomic with it; timestamp history can collide or omit an entry. Recovery receipts/status/latest overwrite | Define identity from existing date/lane/source/decision hashes; deduplicate only operational evidence with proven identity; never change authoritative signal/history semantics without review |
| E2 state written, morning/history/display missing | Separate `atomic_json` calls; missing state defaults to IDLE, malformed state DATA_PENDING, wrong module may be ignored as legacy | Characterize these exact semantics; fail before recovery publication on unproven state lineage. Changes to engine fallback/position semantics are BLOCKED, not silently included |
| EOD partial shard set / missing receipt | `_write` replaces multiple shard files then receipt; interruption can leave incomplete valid-looking shard coverage | Validate expected source manifest, leg hash/date/count/unique keys/receipt/mother binding before promotion; preserve pending/error facts, no synthetic completion |
| History CSV replacement interrupted | `append_electronics_day` removes target-date rows then rewrites whole CSV; protects against simple date duplicates, not atomic durability | Propose atomic operational staging only if exact source bytes/decision semantics preserved; crash tests must prove no partial publication. No historical regeneration |
| Same-date E2 late rerun | Fresh generated_at can overwrite evidence of late recovery; backup skip is not time-aware | Keep original arrival/capture evidence separate from retry time; health continues LATE_RECOVERY. Do not backdate timestamps or change E2 execution-state rules |
| Duplicate scheduled runs / manual retry | Per-workflow groups queue runs; not global authority serialization | One accepted incompatible transaction; identical output NOOP; changing inputs STOP; capture lanes independent. Wall-clock timestamps alone are not transaction identity |
| Different latest/canonical/history | Canonical write-once but aliases/receipts are mutable, E2 history mutable | Check producer-specific invariants and required output closure before publication. No universal filename-based authority or blanket history rewrite rule |
| Evidence loss on early failure | Existing always-upload retains publisher receipts/new immutable evidence only once publisher runs; earlier compute failure may leave only workspace/logs | Propose bounded, zero-authority diagnostic retention even before publish, including acceptance/adoption distinction; retention expiry and failed upload remain explicit limitations |

These are source-derived risks, not claims that crashes have occurred in live
production. No production state was repaired or live recovery executed here.

## Proposed architecture and task specification

1. Reinventory then-current main. Record each operational recovery route's write
   set, immutable subset, read dependencies, legal date/window, existing validator
   and expected canonical/latest/history closure. Distinguish genuine complete
   outputs, mutable diagnostic receipts and optional derivatives. Do not infer
   authority from names. Reuse publisher contracts, never create a second publisher.
2. Add synthetic fault-injection characterization **before** implementation. Use
   disposable Git remotes, fake artifacts, injected time and stubbed providers.
   Never use live API, production artifacts/outcomes or historical signal replays
   beyond the existing authorized Engineering Replay merge gate.
3. Propose a local operational transaction manifest with states OBSERVED,
   INPUTS_VALIDATED, STAGED_COMPLETE, COMMITTED, REMOTE_ACCEPTED,
   LOCAL_ADOPTED or BLOCKED. Include workflow/run/attempt, date/lane, input hashes,
   original computation SHA, proposal write hashes, accepted remote SHA and reason.
   It is evidence, not signal/ranking/capital authority. Do not manufacture missing
   intermediate evidence after a crash; record UNKNOWN when unproven.
4. Before any recovery action, fetch remote main to a separate clean checkout;
   revalidate authoritative inputs, schema/hash/date/window/override bindings and
   current canonical state. After remote movement, use dependency-aware exact
   CAS/lease publication. No blind pull/rebase of precomputed outputs.
5. Reconcile publish/adoption uncertainty from remote bytes and receipts first.
   Already accepted identical state is a no-op; local failure cannot revoke remote
   success. Fence subsequent computation until checkout/index/HEAD are consistent.
6. Validate complete staged output closure before commit. Any projection repair
   proposal must copy already validated canonical bytes without recomputing a
   decision, preserve authority and source timestamps, and have explicit separate
   human review. If the boundary cannot be proven, diagnose and STOP. Do not
   auto-fill historical ledgers/history or invent first-publication lineage.
7. Define per-lane retry limits and evidence retention in the future Issue. No new
   producer cadence, notification service or global capture lock. Store unique
   run/attempt evidence with hashes and upload on failure; latest health is not a
   permanent audit ledger. Document access/retention and unavailable evidence.

### Stale input recomputation policy

- Health-only remote changes: retain current non-interference exclusion and exact
  write-conflict/CAS checks. Health code/policy and unknown paths remain inputs.
- Authoritative input drift: original computed transaction cannot be transplanted.
  Fetch/revalidate; re-execute only an already authorized current operational mode
  with its original causal evidence and unchanged model semantics.
- Q017 capture closed: no late refetch, recapture, blending or historical rebuild.
  Only an already valid immutable 09:01 observation may support existing lawful
  recovery; an existing valid decision wins. Conflicting/missing/invalid evidence
  => BLOCKED with zero new signal authority.
- E2 state/override/position drift: stop stale output; current input revalidation
  must precede any lawful rerun. No override fabrication, position reset, new
  capital, same-session hindsight selection or change to no-fill rules.
- Changed universe/code/contract, unclear dependencies or a date outside the
  current authorized operational window: STOP for explicit review. This design
  does not authorize historical signal regeneration, even via a manual date flag.

### Manual recovery and health boundary

Manual dispatch is an explicit request for a named existing operational route,
not a waiver of date/window/immutability/input/authority validation. Default to
diagnosis/self-test; show observed remote, proposed action and blockers. A future
Issue must define who may apply a validated current-day recovery. Historical date
flags already present do not grant permission to use them in this task.

Health may emit RECOVERY_NEEDED / INPUTS_CHANGED / PUBLICATION_UNCERTAIN /
PARTIAL_TRANSACTION / MANUAL_REVIEW_REQUIRED as **proposed diagnostic reasons**,
with source/run evidence and health_only=true, signal_authority=false,
ranking_authority=false, capital_authority_twd=0, broker_order_execution=false.
These fields are not implemented here. Health must not dispatch recovery, write
producer state, synthesize decisions, alter model/authority or mark source ready.
Recovery success requires producer validation plus remote acceptance and retained
evidence; a green health job alone cannot prove it.

### Fail-closed rules

STOP on conflicting immutable bytes, overlapping canonical/latest writes,
unproven/changed authoritative inputs, malformed/missing required artifacts,
inconsistent hashes/date/window, incomplete required output sets, unknown contract
fields, unverifiable remote acceptance, unresolved checkout adoption, exhausted
CAS retries or requested authority changes. Preserve diagnostic evidence without
publishing partial producer state. Legitimate source PENDING remains PENDING_DATA;
late recovery remains late; lack of evidence is not success. No recovery routine
may rewrite accepted canonical bytes, blindly retry stale commits or suppress a
conflict by reducing declared read dependencies.

## Proposed offline tests (not implemented in PR #19)

| ID | Fault / scenario | Required assertion |
| --- | --- | --- |
| R01 | Kill between each canonical/alias/history/ledger write | No partial authoritative transaction published; known evidence gaps reported |
| R02 | Kill during exclusive canonical JSON creation | Existing truncated file blocks automatic overwrite |
| R03 | Compute complete, no commit; commit complete, no push | Clean remote reconciliation, no assumption that local bytes were accepted |
| R04 | Push accepted, process killed / acknowledgement lost | Remote accepted hash recognized; no duplicate append/recompute |
| R05 | PUBLISHED followed by local adoption failure; kill between index and HEAD adoption | Remote success retained, following computation fenced, clean-checkout recovery |
| R06 | Missing/invalid canonical with apparently current latest, or inverse | Detect inconsistent closure; no alias-based authority inference |
| R07 | Missing history/ledger after valid canonical | Report evidence gap without reranking or historical fabrication |
| R08 | Repeat same current-day recovery; conflicting repeat | Identical output NOOP; incompatible immutable/canonical state STOP |
| R09 | Simultaneous primary/backup 09:01 captures and duplicate scheduled recovery | Independent capture preserved; exact CAS arbitration, no global capture lock |
| R10 | Health-only advancement during recovery | Producer publishes safely; health bytes preserved |
| R11 | Macro/history/universe/code/override changes during recovery | Inputs revalidated; stale output cannot publish |
| R12 | Q017 missing evidence after window, invalid backup, different canonical | No late market access, blending, overwrite or fabricated signal |
| R13 | E2 state updated before morning/history; missing/corrupt/wrong-module source | Characterize fallback and prevent unproven recovery publication without changing engine rules |
| R14 | EOD shard N replaced then crash; receipt/hash/mother mismatch | No false COMPLETE or downstream release; pending/error remains separate |
| R15 | Repeated review session, torn history CSV, timestamp collision | No duplicate session or silent dropped evidence; no historical rerun |
| R16 | Manual self-test/current-day request vs historical-date request | Self-test read-only; current-day validated; forbidden historical work BLOCKED |
| R17 | Late E2 recovery followed by display/health regeneration | LATE_RECOVERY retained, stale source cannot become healthy |
| R18 | Upload failure/expired or missing receipts | Evidence uncertainty explicit, no invented acceptance or retention guarantee |
| R19 | Health detects recovery need | No producer write/dispatch, authority flags remain false/0 |
| R20 | Unknown route/path/contract, lease exhaustion | Fail closed with bounded diagnostics and no authority escalation |

## Proposed changed-file scope for a future PR

This is a candidate allowlist to refine against latest main, not a commitment to
modify every file. PR #19 changes none of these producer behaviors for recovery.

- New operational helper and tests, e.g. `scripts/hengce_recovery_transaction.py`,
  `tests/engineering/test_recovery_stale_state.py`; new inventory contract and
  engineering documentation. Keep helper separate from model computations.
- `scripts/hengce_publish.py` only if crash/adoption reconciliation needs a minimal
  transport change; preserve exact CAS, conflicts, immutability and non-interference.
- Existing Q017 recovery/observation/backup scripts, E2 script, original EOD ingest
  and legacy core **only** at validated I/O/transaction boundaries if tests prove
  unchanged computation and authority. Engine fallback/position/selection changes
  are BLOCKED; trim scope or seek separate explicit authorization instead.
- Relevant existing recovery/daily/observer/E2/macro/display YAML only for minimal
  validation/failure-evidence steps; schedules/triggers/capture groups/compute
  semantics stay fixed. No new automatic retry service authorized by this draft.
- Optional health evaluator/tests only for diagnostic recovery-need reason codes;
  preserve zero authority and health→producer non-interference. No automatic action.
- Exclude production artifacts, historical data/signals, research/optimizer files,
  formula/weight/threshold/ranking/universe/capital contracts, M1 authority, broker
  integration, holdout and Phase 2. No sealed data is needed for synthetic tests.

## Proposed merge gates for the separate future Issue / PR

1. PR #19 human-reviewed and merged; new Issue/branch starts at then-current main.
2. Current source-based inventory, exact file list, transaction/read/write contracts
   and explicit per-subtask hard-lock assessment reviewed before implementation.
3. Synthetic failure tests first; all proposed in-scope crash/retry scenarios pass
   offline without live provider/API, historical signal generation or holdout.
4. Existing Engineering Replay PASS with all 11 IDENTICAL on the final head;
   existing producer regressions, Writer Race Safety and health tests PASS. Record
   run IDs/results and retain fault-injection evidence.
5. Demonstrate remote-accepted/local-failed distinction, input revalidation after
   recovery, no duplicated semantic effects, full output closure and immutable
   preservation. Document any remaining unproven guarantee instead of claiming
   exactly-once end-to-end recovery.
6. Confirm schedules, triggers, capture independence, model/decision semantics,
   authority and all hard locks unchanged. Health-only changes cannot block any
   existing producer publication profile; mixed real-input changes still STOP.
7. Explicitly list unresolved crash windows, retention/API/runner/calendar limits,
   blocked subtasks and manual recovery requirements. No automatic promotion.
8. Human review required; keep the future PR open and do not merge automatically.
