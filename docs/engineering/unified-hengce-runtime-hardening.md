# Single HENGCE runtime engineering review — PR #28

This is engineering work, not model optimization. MODEL CHANGES: NONE IMPLEMENTED.
No optimizer, backtest, candidate acceptance, holdout access, historical signal
regeneration, broker execution, capital change, or production promotion is added.

## Authority and runtime inventory

| Component | Actual role | Disposition |
| --- | --- | --- |
| Formal legacy v2/v3 artifact from `RUN_IN_WORK.sh` | Existing formal candidate/geometry/activation evidence; explicit admission required | KEEP as internal source |
| `hengce_unified_candidate_adapter.py` | Normalizes source identities; unions/deduplicates; preserves separate scores and evidence; no geometry computation | KEEP / harden |
| `hengce_intraday_action_board.py` | Existing context/live downgrade and held-position exit rules; never generates geometry | KEEP / boundary corrections |
| `hengce_unified_action_board.py` | Sole HENGCE Action Board, provenance and source binding | KEEP / harden |
| `hengce_unified_runner.py` | Single local transaction coordinator, shared by shell/orchestrator | KEEP (new) |
| `RUN_INTRADAY_ACTION_BOARD.sh` | Thin deployed/repository entry point | MIGRATE to coordinator |
| `RUN_HENGCE_COMPLETE.sh` | Optional formal compute then same unified coordinator; no duplicate artifact selector | MIGRATE |
| `hengce_scan_once_router.py` | One invocation of unified runner, one display; no producer recovery | MIGRATE |
| `hengce_unified_scan_display.py` | Only committed, current HENGCE bundle is user authority | KEEP / harden |
| Q017 v5 observation/recovery/authority guard and scheduled workflows | Old 09:01/Top3/DXY operational evidence, not frozen canonical Q017 | DEPRECATE for canonical admission; KEEP historical evidence and independent capture schedules |
| E2 runtime and research | Existing operational/research artifacts; not a competing scan-once decision route | KEEP as internal evidence; never relabel as canonical Q017 |
| Dual-engine display and V3 display artifacts | Historical operational evidence, not scan-once authority | DEPRECATE user-facing use; KEEP replay evidence |
| Interactive calls to legacy recovery/repair; newest-mtime recursive discovery; implicit old-radar fallback | Could restore old authority or select unrelated/stale output | REMOVE from unified path |

Before: independent CLI stages could overwrite partial files, receipt hashes were
read after computation, display accepted a PASS action by itself, failed runs left
old PASS actions, ticker aliases disagreed, and interactive refresh invoked legacy
producer/recovery paths.

After: candidate sources → validated normalized candidates → ticker union →
provenance and separate scores → legal existing geometry/activation → one Action
Board → receipt-bound single HENGCE display. The router never runs recovery or
another engine. Scheduled producer schedules/capture lanes are unchanged.

## Contracts and intentional boundary corrections

- Canonical ticker aliases normalize `.TW` and `TWSE:`; conflicting aliases stop.
  Identical duplicate legacy rows coalesce; conflicting duplicate rows stop.
  Presentation is deterministic ticker order, **not a mixed-source score ranking**.
- LegacyScore and Q017Score remain separate, with LegacyEvidence/Q017Evidence.
  No score fusion or new entry geometry is computed.
- Geometry requires four finite positive coherent bounds. Missing/invalid geometry
  cannot yield entry/probe review. Existing held-position invalidation exit priority
  remains intact; context must not suppress an established exit.
- Unknown/incompatible context policies stop entry authority; nonfinite numbers,
  ambiguous activation flags/ranks, duplicate live tickers and malformed JSON stop.
- Formal and context sources must explicitly bind `trade_date` (or
  `valid_for_trade_date`) and a timezone-aware generation timestamp to the current
  Taipei action session. `formal_scan_allowed=true` and formal `run_id` are required.
  No trading-calendar inference or implicit same-date recovery is introduced.
- Live age remains capped at the established 480 seconds; environment overrides
  may tighten it, never weaken it. Source quote date is validated against wall-clock
  Taipei session, not used to choose that session. Expected-inactive lifecycle
  exceptions retain the existing core contract.
- Multiple default formal paths are ambiguous and stop; an explicit path resolves
  selection but cannot bypass validation. Explicit missing paths never fall back.
- Missing/invalid optional Q017 is isolated as unavailable; valid legacy operation
  continues without promoting Q017. Missing/invalid mandatory inputs stop the bundle.

## Canonical Q017 producer search and readiness

Repository and all fetched history were searched for the exact universe and
turnover/score contract. Only the branch adapter/descriptor matched the frozen
canonical contract. Q017 v5 and `research/phase2_q017/family-v1.json` use materially
different 09:01/Top3/DXY contracts. E2 feature math resembles some factors but does
not establish canonical Q017 PIT universe/returns/residual/adjustment lineage.
No usable handoff archive with a verified producer was available (a checksum is not
an implementation). None was relabeled, reconstructed, or run as a new model.

Canonical calculation/producer: **BLOCKED / NOT AVAILABLE**. The verified producer
code-commit allowlist is intentionally empty. Contract-compatible self-assertions
cannot certify a producer. A future producer requires an explicit reviewed code
commit, PIT input lineage, exact schema, session metadata, frozen rule values,
Top1 cardinality, qualification/filter/score evidence, and independent verification
before an allowlist change. There is no environment variable bypass. Offline tests
inject a synthetic producer allowlist only inside test/self-test execution.

Q017-only candidates always have unavailable geometry and a false entry trigger.
BOTH candidates reuse only legal existing legacy geometry. No Q017 evidence can
create entry, stop, target, risk, or capital authority.

## Local publication, receipts, and failure semantics

A per-output-directory publication lock serializes only local runtime work, never
Q017 primary/backup observation capture. Each JSON uses a unique same-directory
temporary file, fsync, replace, and directory fsync. A RUNNING receipt first revokes
prior authority. The PASS receipt is written last and binds base/action hashes,
transaction ID, source byte hashes, source paths, session, and zero-authority flags.
Local source hashes are revalidated before publication; changed computation inputs
stop. Failures revoke the receipt and replace old base/action rows with empty
FAIL_CLOSED artifacts. A busy writer cannot clobber the lock owner's transaction.

Display checks complete membership, exact hashes/transaction/run/source evidence,
zero-authority envelope, current action session, action age, and original live age.
Re-rendering never refreshes stale source age. A crash between replacements yields
an incomplete bundle and ABSTAIN. Scan-once suppresses all subprocess output and
prints exactly one JSON result; a failed/timeout runner cannot reuse old PASS.
These are local UI artifacts, not a second repository publisher. Existing exact
leases, dependency arbitration, immutable semantics, recovery fences, and independent
Q017 capture remain untouched in `hengce_publish.py` and producer workflows.

## Verification and adversarial review

Initial offline fault tests reproduced five defects before corrections: missing
geometry yielded REVIEW_ENTRY; unknown context plus NORMAL passed; conflicting
legacy duplicates were silently chosen; duplicate live rows overwrote one another;
contract integer coercion accepted 1.9 as Top1. Tests now exercise these boundaries
plus runtime receipts, source changes, stale inputs, optional source isolation,
geometry ownership, producer self-certification rejection, and single-output routing.

The deployment installer includes/checksums the entire runtime dependency set and
preserves every joblib hash. Handoff and detached bundle tests execute the installed
package. Unified, handoff, bundle and replay checks run on PRs without path filters.
The frozen historical model payload remains exact-equality compared; the authorized
router migration has an exact six-clock route contract and actual main() behavioral
checks. Baseline regressions cannot disappear. Report labels router migration
explicitly; it does not falsely label changed routing IDENTICAL.

Adversarial review added rejection of conflicting context/quote metadata aliases,
failed/unexpected-stale/inactive quotes, conflicting geometry aliases even for held
positions, and entry review of explicitly nonformal candidates. These corrections
have targeted regression cases. Valid held-position exits with valid geometry
retain priority over capital-blocking context. A final targeted review follows
those substantive changes. CI run IDs/results are recorded in PR #28 for its final
head; CI success does not imply canonical producer readiness.

Optional standalone Phase 2 governance scope suites were also attempted. Their
branch-specific freeze assertions reject this production/runtime PR as outside a
governance-only package (2 scope errors in each suite). That scope guard is
intentionally unchanged; these are not authorization or model trials and do not
create experiment records. This PR relies on its runtime/replay/producer safety
gates, not a bypass of the prior governance package's changed-file allowlist.

## Remaining risks and debt

- No verified canonical Q017 producer; production admission stays blocked.
- No authoritative TWSE holiday calendar is inferred here. Session admission alone
  does not prove a day is a valid trading session; producer calendar validation and
  missing-session/holiday readiness remain explicit upstream responsibilities.
- Formal/context artifacts without explicit session metadata now fail closed and
  require producer-side contract migration, not a permissive fallback.
- Hashes are consistency evidence, not signatures. Local code/filesystem trust is
  assumed. Publication lock requires local POSIX filesystem semantics.
- Local source revalidation is optimistic; external writers must atomically publish
  inputs. There is no cross-host transaction or shared lock with external sources.
- Legacy scheduled writers/displays remain for replay and historical evidence.
  A later reviewed migration should retire their public consumers only after
  inventorying real integrations; this change does not erase research evidence.
- Highest-value next step: independently specify/verify canonical Q017 mathematics
  and PIT lineage, then implement one reviewed producer with offline golden cases.
  No frozen model-rule change is proposed or implemented here.

Merge status: NOT MERGED. Draft PR #28 remains for human review.
