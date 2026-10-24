# Issue31 — Data Foundation V2

**Scientific result: BLOCKED_DATA_READINESS. STOP FOR HUMAN REVIEW.**

Production model changes: **NONE**. New model evaluations: **0**. Prior retained
model evaluations: **8,529**, unchanged. PR #30 stays OPEN / DRAFT / NOT MERGED.
No model-search batch may start automatically after this package.

## Frozen lineage and plans

- Canonical task: `../CODEX_DATA_FOUNDATION_V2_TASK.md`, registered by human at
  `593652df3e414b223eea0d568299084cf5c85c52`.
- Parent tree `cf326040b11f0f6136fd7b09ba5eae14f274a37e`; V1 evidence head
  `0c24f9795e36b52e28eafed186eee5591ec93353`; corpus base
  `05bf0e35fb6a88473fd4f947952ef1b6875d3f88`. No moving-main rebase.
- PLAN_V2.json and 141-file SHA256 parent inventory pushed at `e1a43dc` before
  the planned source batch. The supplemental four-request discovery plan was
  pushed at `779b154` before its source requests. Both plans remain byte-exact.
- Uploaded ZIP SHA256 verified as
  `887705d2c81a8f0f17fe66129e29ce49342cbf1e09e886b95ea7f4fabfdf1b45`;
  every inner manifest digest also verified. Repository-native task takes priority.

## Workstreams A–C: global events, entitlement assertions and identities

All **1,151** retained daily-PIT electronics events are classified; none is
silently discarded. Their raw source-row index/hash, effective date, ticker and
frozen membership binding are retained. Source symbols are distinguished from
numeric detail proof. Unspecified rights remain ambiguous between free shares
and paid issue; absent terms never become zero.

| Classified event type | Count |
| --- | ---: |
| CAPITAL_REDUCTION_CASH_RETURN | 19 |
| CAPITAL_REDUCTION_LOSS_ABSORPTION | 13 |
| CASH_DIVIDEND | 1021 |
| MIXED_ACTION | 2 |
| MIXED_CASH_AND_UNSPECIFIED_RIGHTS | 31 |
| RIGHTS_PAID_SUBSCRIPTION | 1 |
| RIGHTS_TERMS_UNKNOWN | 63 |
| STOCK_DIVIDEND_FREE_SHARES | 1 |

`ENTITLEMENT_LEDGER.jsonl` has **1,165 append-only assertions**: 1,151 initial
assertions, 12 separately sourced numeric enrichments, and two supplemental
split/suspension assertions. Global previous-hash links, per-event supersession
links and duplicate assertion IDs are audited. Initial assertions are not replaced.
Superseding a known unequal term must produce CONFLICT rather than silently
choosing a source. All actual global latest assertions remain PARTIAL.

The frozen, outcome-blind batch fetched 12 affected action details, ordered by
(date,ticker) and excluding two details already retained in V1. All 12 validated
numeric terms; two additional official source-description pages were retained.
The global number of events with known cash terms increased from two to **14**.
This is not 14 fully resolved entitlements. Old/new listed security IDs, payment,
delivery, subscription-deadline and fractional-share fields stay null where unproven.
A paid company issue is distinguished from an old-holder subscription entitlement;
no subscription cash outflow or exercise is manufactured.

| Coverage dimension | Global denominator | Proven coverage |
| --- | ---: | ---: |
| Event classification | 1,151 | 1,151 classified, some only from source symbols |
| Numeric cash terms | 1,151 | 14 |
| Payment dates | 1,151 | 0 |
| New-share saleability dates | 1,151 | 0 |
| Complete listed-security identity transitions | 1,151 | 0 |
| Historical first-seen / revision lineage | 1,151 | 0 / 0 |

The supplemental 2327 conversion has an officially supported economic ratio of
four new shares per old share and a 2025-08-25 resumption/saleable date. It is
reported separately from the 1,151-event denominator. Listed-instrument IDs and
complete historical identity continuity remain UNKNOWN. Same ticker, economic
continuity and identical listed-instrument identity are different propositions.
A current master is never substituted for a historical identity document.

The original annual event sources do not inventory every merger, delisting,
relisting or suspension in the market. No absence of those events is inferred.
3090's specific suspension is retained separately; its next observed trade date
is not invented as an exact official resumption timestamp.

## Workstream D: historical impact coverage and a blocking retention gap

All **8,529** prior evaluations have a TRIAL_INVENTORY row. **69** have retained
windows that can be mapped: 45 from original baseline/family evidence and 24
from the diversified continuation. Of those, 45 are bound by retained metadata
and original metrics, not a per-trial event-hash receipt; 24 have exact event files.
Pinned primary-quality windows are never borrowed for the separate stricter-quality
calls. Binding reads stored metrics only; no returns, signals or selections rerun.

**8,460 evaluations did not retain their individual trade windows.** Their
per-trial mapping is explicitly UNKNOWN_WINDOWS_NOT_RETAINED. This portion of
Workstream D is BLOCKED; the package does not claim 100% trade-window coverage.
It would violate the zero-trial/no-history-rewrite instruction to regenerate
signals and pretend the resulting windows had been preserved originally.

There are **1,906 retained basket-window observations**, including repeated cost
scenarios and matched-benchmark streams. These are not independent trade counts.
**793** intersect a retained action/suspension event. Unique affected-observation
counts by phase (overlapping, not additive): entry314, holding707, exit293,
suspension-window11. Per-ticker event intersections and exact missing fields are
retained. Buying on an ex-date does not credit the preceding owner's entitlement.
No retained-event intersection means only that the available event corpus has no
match; it does not prove complete action clearance or successful execution.

## Workstream E: direction-aware execution evidence

The retained observations describe 341,446 intended constituent order-leg
exposures, duplicated across study streams. EXECUTION_EVIDENCE.jsonl records the
**1,331 one-price/known-limit leg cases**: 1,248 BUY and83 SELL. All **1,331** fills
remain UNKNOWN. Other retained observations also have execution validity UNKNOWN;
they are not silently treated as filled because they lack a one-price record.

1,131 repeated BUY exposures match the known lower limit. Lower-limit one-price
state does not prove universal buy no-fill; a SELL's allocation/queue uncertainty
has a different interpretation. Neither direction is upgraded to guaranteed fill.
Only actual preserved 2025-04-07 reference/limit evidence is attached. Other dates'
limits, exact decision clock, order type, size, queue, depth, auction matched
volume and allocation stay unknown. The price/timing assumptions are labeled
from the historical research contract, not described as an actually placed order.
The old symmetric censor and every old result/status remain unchanged.

## Official discovery failures and stop behavior

The separate bounded issuer/MOPS discovery obtained no usable payment/delivery
announcement: two issuer pages returned HTTP403; two MOPS queries returned HTTP200
with a security-refusal body. Raw bytes, receipts and original labels are retained.
No alternate host, credential, proxy identity, CAPTCHA handling or purchase used.

The initial discovery code failed to recognize the HTTP200 refusal wording and
issued the already planned second ticker query before offline review. This is a
disclosed collector defect, not successful source access. `discovery/REVIEW.json`
records it without relabeling original receipts. Detection now recognizes those
bodies; a synthetic end-to-end regression proves that a first security refusal
prevents the next query to the source family. No further MOPS/issuer requests were
made. Missing dates are not inferred from a dividend ex-date or reference price.

## Workstream F and readiness

**Actual adjusted-return/PnL engine: BLOCKED_NOT_IMPLEMENTED.** No adequate
empirical scope has complete entitlement, identity and execution evidence.

The implemented helper is an **obligation/readiness diagnostic**, with synthetic
fixtures for ordinary price eligibility, unpaid cash receivable, undelivered
stock, subscription requiring cash/deadline, suspension, old-to-new conversion,
and unresolved-action blocking. It calculates no prices, NAV, returns or model
outcome. Conflicts, partial assertions, invalid numbers/dates or unknown identities
never permit reinvestment or sale of undelivered shares. A synthetic PROVEN
fixture is not claimed as an empirical security or an adjusted-return result.

READINESS_V2.json remains BLOCKED_DATA_READINESS. No adjusted-PnL subset has been
certified. A narrower forensic-only use can reference the exact enumerated event
IDs, dates and source fields; this is not PARTIAL_SCOPE_READY for model research.
Unknown actions outside the retained corpus, missing windows and asymmetric
execution uncertainty prevent a defensible narrower tradable/PnL scope here.

## Testing, audit and CI

- **20 new fully synthetic/offline tests** cover the requested mixed cash/stock,
  delayed delivery, paid subscription, cash/no-cash reductions, split identity,
  suspended exit, unknown availability, current-master refusal, detail mismatch,
  conflicting/duplicate assertions, BUY/SELL lower-limit distinctions, no
  volume-to-fill inference, immutable history, zero authority/trials, invalid
  numbers/dates and HTTP200 source-family stop behavior.
- Inherited 119 engineering tests, 17 original data/temporal tests, 13 continuation
  tests and16 V1 source/normalization tests are run separately. Exact results and
  final-head CI/Replay run IDs are recorded in PR #30.
- One-command audit validates all 141 parent file hashes, both previous study
  inventories, frozen plans, retained raw bytes/receipts, disclosure failures,
  append-only ledger links/supersession, exact file checkpoint and deterministic
  reproduction of these mappings from retained data only. No network/model trial.

```sh
python -B research/codex_full_reset_20261023/data_foundation_v2_20261023/test_v2.py
python -B research/codex_full_reset_20261023/data_foundation_v2_20261023/audit.py
```

## Deliverable inventory

At the root: PLAN_V2.json, DISCOVERY_PLAN_V2.json, PARENT_INVENTORY.json,
EVIDENCE_CHECKPOINT.json, uploaded USER_HANDOFF.zip, implementation, tests and audit.
`collection/` preserves the 14-request batch and its exact collector source;
`discovery/` preserves four probes, original code/manifest and explicit review.
`results/` contains EVENT_CLASSIFICATION.jsonl, ENTITLEMENT_LEDGER.jsonl,
IDENTITY_TRANSITIONS.jsonl, SUPPLEMENTAL_EVENTS.jsonl, HISTORICAL_IMPACT_MAP.jsonl,
EXECUTION_EVIDENCE.jsonl, COLLECTION_MANIFEST.json, COVERAGE_V2.json and
READINESS_V2.json. Exact changed-file inventory and final-head CI are in PR #30.
Checkpoint hashes are externally anchored by the pushed evidence commit, not
claimed to be independent merely because they form a self-contained chain.

## Remaining limits and human-review stop

- Global event-term, delivery/payment, security-ID and historical first-seen gaps
  remain; free announcement source retrieval was refused and stopped.
- 8,460 past trial windows cannot be mapped exactly from retained artifacts.
- Daily prices/volume/reference values cannot prove a simulated order allocation.
- All exposed history remains exposed; no pristine holdout or new model accepted.

**STOP after these V2 deliverables.** A new frozen research specification requires
separate authorization; no model search or promotion launches automatically.
Production Q017/E2/M1 semantics, scores, authority, schedules, live producers,
capital and broker execution remain unchanged. No main push, merge, paid source
purchase, signal regeneration or historical outcome rewrite.

**PRODUCTION MODEL CHANGES: NONE. NOT MERGED.**
