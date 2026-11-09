# HENGCE Research Constitution — Literature First Gate v1

Status: **GLOBAL / FAIL-CLOSED / SUPERSEDES SILENT MODEL-FIRST PRACTICE**  
Effective date: 2026-11-02 (Asia/Taipei)  
Human directive: **No HENGCE research may enter model construction/versioning before the relevant literature review is completed and auditable. For Taiwan-equity research, this includes a broad Taiwan Stock Market Master Corpus foundation, not only literature about the current hypothesis.**

## 1. Non-negotiable rule

For every new HENGCE research question, mechanism, feature family, strategy, model, overlay, regime rule, selection rule, exit rule, scoring rule, threshold family, or behavioral hypothesis:

> **READ THE RELEVANT LITERATURE FIRST. MODEL SECOND.**

For Taiwan-equity research, a second rule is equally binding:

> **DO NOT NARROW THE LITERATURE TO THE CURRENT IDEA. MAINTAIN AND READ THE BROADER TAIWAN-STOCK EMPIRICAL CORPUS.**

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
- excluding weak/null/contradictory evidence because it harms a preferred narrative;
- restricting the literature search to the current favored mechanism while leaving materially relevant Taiwan-stock domains unreviewed.

Only after the required literature gates pass may the topic enter:

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

## 4. Taiwan Stock Market Master Corpus Foundation

For any HENGCE research whose target universe or mechanism concerns Taiwan equities, there is a **master-corpus prerequisite** in addition to the topic-specific review.

The persistent Taiwan Stock Market Master Corpus must cover materially relevant empirical Taiwan-stock research across at least:

- asset pricing / return anomalies / factor models;
- behavioral finance / investor behavior;
- institutional / foreign / fund flow;
- ownership / chip / concentration;
- market microstructure / order flow;
- liquidity / transaction costs;
- margin / short selling / securities lending / leverage;
- volatility / crash / tail risk;
- momentum / reversal / reference points;
- information / news / earnings / revenue / dividends / events;
- fundamentals / accounting / valuation;
- corporate governance / ownership structure;
- industry / supply-chain / lead-lag information diffusion;
- analysts / media / attention;
- IPO / SEO / index / ETF effects;
- derivatives / equity price discovery where informative for equities;
- regulation / market design / price limits / tax / continuous trading reforms;
- regime / crisis / macro conditions;
- technical trading / trading rules;
- cross-market / international spillovers.

This is **not** permission to claim that every Taiwan-stock paper ever written has been found. Literal exhaustiveness cannot be proven. Instead, the corpus must use continuous broad search, topic classification, primary-source retrieval, counterevidence retention, and saturation assessment.

For Taiwan-equity model work, the master foundation remains `BLOCKED` until all P1 master domains are at least `PROVISIONALLY_SATURATED`, with material accessible primary studies, major null/counterevidence, and known replications represented. A topic-specific literature gate cannot waive an unsatisfied master-foundation gate.

A currently fashionable mechanism — for example 52-week high, sentiment, foreign flow, or any other single idea — must not crowd out unrelated Taiwan-stock evidence.

Canonical master ledger:

`/HENGCE_CANONICAL/RESEARCH/TAIWAN_STOCK_MARKET/HENGCE_TAIWAN_STOCK_MARKET_MASTER_LITERATURE_LEDGER_v1.xlsx`

The prior behavioral-finance ledger remains a preserved subset, not the overall authority:

`/HENGCE_CANONICAL/RESEARCH/BEHAVIORAL_FINANCE/HENGCE_TAIWAN_BEHAVIORAL_FINANCE_LITERATURE_LEDGER_v1.xlsx`

## 5. Completion standard for a topic

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

## 6. Required topic-level evidence before modeling

Every project that moves beyond documentation/data-only work must contain a machine-readable `LITERATURE_GATE.json` at the project root with at least:

- `literature_review_complete: true`;
- `literature_status: "PASS"`;
- topic/scope/search boundary;
- canonical Taiwan-stock master-ledger reference and version/snapshot identifier when applicable;
- topic-specific evidence subset / ledger reference;
- counts of FULL_READ / PARTIAL / FOUND_ONLY;
- confirmation that counterevidence and null results were included;
- confirmation that limitations/identification threats were recorded;
- confirmation that abstracts were not promoted to FULL_READ;
- master-domain saturation status when the research concerns Taiwan equities;
- saturation assessment;
- unresolved material conflicts/gaps;
- reviewer/date;
- explicit statement that no model construction/backtest/tuning preceded the gate for this topic.

The gate validates **process authority only**. It is not evidence that the literature claim is true, and it does not authorize production, capital, holdout access, or candidate acceptance.

## 7. Anti-retrofit rule

A literature review created after a model has already been designed or tuned cannot retroactively certify that model as literature-first.

If model-first work already exists, it must be labeled `PRE_LITERATURE_CONTAMINATED`. It may be retained for audit/history but cannot be treated as clean confirmatory evidence. A fresh preregistered path is required after the literature gate passes.

## 8. Cross-chat / cross-branch continuity

Literature evidence must live in a persistent canonical ledger, not only in conversation memory. New chats and branches must retrieve the latest master ledger before continuing Taiwan-stock literature work and must write newly read sources back to the persistent ledger.

For Taiwan-equity research, the master authority pointer is:

`/HENGCE_CANONICAL/RESEARCH/TAIWAN_STOCK_MARKET/HENGCE_TAIWAN_STOCK_MARKET_MASTER_LITERATURE_LEDGER_v1.xlsx`

Topic/subfield ledgers may continue to exist as subordinate views. GitHub manifests should record the exact master-ledger and topic-ledger versions/snapshots used for a given preregistration.

## 9. Relationship to existing HENGCE governance

This constitution is an **upstream prerequisite**. Existing rules on PIT observability, no-lookahead, preregistration, variant budgets, append-only research ledgers, holdout custody, OOS validation, production promotion, and capital authority remain in force.

Passing literature review does not weaken any downstream gate.

Order of authority for Taiwan-equity research:

1. `TAIWAN_STOCK_MASTER_CORPUS_FOUNDATION`
2. master P1 domains at least `PROVISIONALLY_SATURATED`
3. `TOPIC_LITERATURE_REVIEW_ONLY`
4. topic `LITERATURE_COMPLETE=PASS`
5. preregistration / hypothesis freeze
6. data-lineage / PIT capability validation
7. bounded empirical testing
8. robustness / counterexample tests
9. OOS / prospective validation as applicable
10. promotion review under existing HENGCE authority

Skipping the master or topic literature gate invalidates clean research provenance for the topic.

## 10. No-good-news exception

A compelling idea, a strong backtest, an intuitive story, a user suggestion, a famous investor claim, a large effect size, or a surprising chart is **not** an exception. Strong-looking results increase the need for literature and counterevidence review; they do not waive it.

## 11. Amendment rule

This gate is frozen as a global HENGCE principle. Weakening or bypassing it requires:

- explicit human authorization;
- a governance change describing exactly what is weakened and why;
- preservation of this prior rule in history;
- no silent override by model code, research notes, branch instructions, or automated agents.

Absent those conditions, unknown or missing literature-gate state is **BLOCKED**.


## 12. Mandatory execution checklist and persistent handoff (2026-11-06 addendum)

The mandatory operating checklist is [HENGCE_LITERATURE_FIRST_EXECUTION_SOP_20261106.md](HENGCE_LITERATURE_FIRST_EXECUTION_SOP_20261106.md). For every new research topic or continued round, consult domain experts' *published primary methods and counterevidence first*, before devising any new strategy hypothesis or empirical test. Record reading depth honestly and compare Taiwan-market applicability. If a methodological point is not understood, consult independent professional sources, record the open question, and hold the relevant test; do not improvise a factor or backfit a threshold. Follow the fail-closed master-corpus and topic literature gates above, then preregister before new candidate testing. Keep clear lineage, negatives, limitations, and a cross-chat handoff; study failures are not production authorization. This addendum strengthens existing gates and may not weaken sections 1–11.


## 13. Mandatory full-history capital-cycle interpretation gate (2026-11-09 addendum)

The binding longitudinal capital-cycle rule is [HENGCE_LONGITUDINAL_CAPITAL_CYCLE_HARD_GATE_v1_20261109.md](HENGCE_LONGITUDINAL_CAPITAL_CYCLE_HARD_GATE_v1_20261109.md), with a machine-readable contract in the adjacent JSON file. This is a **stricter interpretation/evidence gate** for HENGCE research about large-money sowing, development, harvesting, failure, withdrawal, re-accumulation and inter-stock rotation. Short HBA alert windows, one-week TDCC changes, end-point holdings or net flow cannot alone establish a multi-year capital-cycle stage. Existing gross buy/sell, multi-year price paths, all relevant PIT-eligible ownership snapshots and negative evidence must be checked across natural, evidence-based turning points before phase claims are asserted.

The literature-first and Taiwan Stock Market Master Corpus gates in sections 1–12 remain fully binding. The longitudinal rule does not authorize a new model, tuning, OOS claims, selection, formal Escape state or trading. Reports without the required historical path evidence must say \`HISTORICAL_CYCLE_UNVERIFIED\`, while preserving short-window alert observations without upgrading them to historical interpretation.
