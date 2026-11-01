# HENGCE Research Constitution — Literature First Gate v1

Status: **GLOBAL / FAIL-CLOSED / SUPERSEDES SILENT MODEL-FIRST PRACTICE**  
Effective date: 2026-11-02 (Asia/Taipei)  
Human directive: **No HENGCE research may enter model construction/versioning before the relevant literature review is completed and auditable.**

## 1. Non-negotiable rule

For every new HENGCE research question, mechanism, feature family, strategy, model, overlay, regime rule, selection rule, exit rule, scoring rule, threshold family, or behavioral hypothesis:

> **READ THE RELEVANT LITERATURE FIRST. MODEL SECOND.**

The literature gate is a prerequisite, not a post-hoc citation exercise. Research findings, papers, theses, reports, null results, counterevidence, identification problems, and limitations must be reviewed **before** model construction or empirical search is allowed.

This constitution applies across all HENGCE engines, branches, chats, notebooks, code paths, and future research programs. A later branch may add stricter rules but may not weaken this gate without explicit human authorization recorded in governance.

## 2. Fail-closed state machine

Every research topic begins in:

`LITERATURE_REVIEW_ONLY`

Allowed before the gate passes:

- literature discovery and retrieval;
- full-text reading and evidence extraction;
- source verification and bibliographic cleanup;
- data acquisition, data cleaning, lineage checks, and capability audits that do **not** inspect target outcomes for feature discovery;
- documentation of known mechanisms, competing explanations, null evidence, and unresolved questions;
- construction of a literature ledger / evidence map;
- replication planning that does not inspect unseen target returns or tune rules.

Forbidden before the gate passes:

- creating or naming a new model/version/candidate family;
- inventing a factor, feature, score, threshold, ranking rule, entry/exit rule, or regime rule from observed target outcomes;
- backtesting a new hypothesis or candidate;
- searching forward returns to discover a relationship;
- parameter/grid/random/Bayesian/manual tuning;
- silent retuning or rescuing a failed family;
- candidate acceptance/promotion;
- using an abstract, search snippet, table of contents, news article, or secondary summary as if the underlying study had been fully read;
- excluding weak/null/contradictory evidence because it harms a preferred narrative.

Only after an auditable topic-level `LITERATURE_GATE.json` passes the machine contract may the topic enter:

`PREREGISTRATION_ALLOWED`

Only after preregistration may empirical candidate construction/testing proceed under the separate HENGCE research/holdout/OOS rules.

## 3. What counts as "read"

A source may be marked `FULL_READ` only when the accessible full text has been reviewed sufficiently to capture, where applicable:

1. research question and hypotheses;
2. exact sample period and universe;
3. data sources and sample construction/exclusions;
4. variable definitions and timing;
5. empirical identification/methodology;
6. main tables/results and economic direction/magnitude;
7. robustness/alternative specifications/placebos/subsamples;
8. stated limitations and identification threats;
9. counterevidence and competing mechanisms;
10. what the evidence can and cannot support for HENGCE.

If the full text is inaccessible or the table/robustness audit is incomplete, the source must remain `PARTIAL` or `FOUND_ONLY`. No status inflation is permitted.

## 4. Completion standard for a topic

`LITERATURE_COMPLETE=PASS` does **not** mean "all papers ever written." It means a bounded, documented review has reached the following minimum standard:

- review scope and search boundary are explicit;
- all materially relevant, reasonably accessible primary studies found within that scope are classified;
- core theory/mechanism sources needed to understand the topic are covered;
- Taiwan-specific empirical evidence is prioritized whenever the HENGCE claim is Taiwan-specific;
- major supportive evidence is read;
- major null/negative/contradictory evidence is read;
- known replications and regime/time-period reversals are included where found;
- identification/proxy limitations are recorded;
- unresolved material conflicts are documented rather than hidden;
- a saturation assessment explains why further search is unlikely to change the initial preregistration materially, or explicitly states remaining gaps;
- the canonical literature ledger/evidence map is versioned and referenced.

A topic may pass with documented scientific disagreement. It may **not** pass with unsearched counterevidence, unresolved source identity, or abstract-only claims masquerading as full reads.

## 5. Required topic-level evidence before modeling

Every project that moves beyond documentation/data-only work must contain a machine-readable `LITERATURE_GATE.json` at the project root with at least:

- `literature_review_complete: true`;
- `literature_status: "PASS"`;
- topic/scope/search boundary;
- canonical ledger reference and version/snapshot identifier;
- counts of FULL_READ / PARTIAL / FOUND_ONLY;
- confirmation that counterevidence and null results were included;
- confirmation that limitations/identification threats were recorded;
- confirmation that abstracts were not promoted to FULL_READ;
- saturation assessment;
- unresolved material conflicts/gaps;
- reviewer/date;
- explicit statement that no model construction/backtest/tuning preceded the gate for this topic.

The gate validates **process authority only**. It is not evidence that the literature claim is true, and it does not authorize production, capital, holdout access, or candidate acceptance.

## 6. Anti-retrofit rule

A literature review created after a model has already been designed or tuned cannot retroactively certify that model as literature-first.

If model-first work already exists, it must be labeled `PRE_LITERATURE_CONTAMINATED`. It may be retained for audit/history but cannot be treated as clean confirmatory evidence. A fresh preregistered path is required after the literature gate passes.

## 7. Cross-chat / cross-branch continuity

Literature evidence must live in a persistent canonical ledger, not only in conversation memory. New chats and branches must retrieve the latest ledger before continuing the topic and must write newly read sources back to that ledger.

For the current Taiwan behavioral-finance program, the canonical persistent ledger is:

`/HENGCE_CANONICAL/RESEARCH/BEHAVIORAL_FINANCE/HENGCE_TAIWAN_BEHAVIORAL_FINANCE_LITERATURE_LEDGER_v1.xlsx`

This path is a Library authority pointer; GitHub manifests should record the exact ledger version/snapshot used for a given preregistration.

## 8. Relationship to existing HENGCE governance

This constitution is an **upstream prerequisite**. Existing rules on PIT observability, no-lookahead, preregistration, variant budgets, append-only research ledgers, holdout custody, OOS validation, production promotion, and capital authority remain in force.

Passing literature review does not weaken any downstream gate.

Order of authority for a new research topic:

1. `LITERATURE_REVIEW_ONLY`
2. `LITERATURE_COMPLETE=PASS`
3. preregistration / hypothesis freeze
4. data-lineage / PIT capability validation
5. bounded empirical testing
6. robustness / counterexample tests
7. OOS / prospective validation as applicable
8. promotion review under existing HENGCE authority

Skipping step 2 invalidates clean research provenance for the topic.

## 9. No-good-news exception

A compelling idea, a strong backtest, an intuitive story, a user suggestion, a famous investor claim, a large effect size, or a surprising chart is **not** an exception. Strong-looking results increase the need for literature and counterevidence review; they do not waive it.

## 10. Amendment rule

This gate is frozen as a global HENGCE principle. Weakening or bypassing it requires:

- explicit human authorization;
- a governance change describing exactly what is weakened and why;
- preservation of this prior rule in history;
- no silent override by model code, research notes, branch instructions, or automated agents.

Absent those conditions, unknown or missing literature-gate state is **BLOCKED**.
