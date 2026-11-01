# HENGCE Loss Forensics — Prospective OOS Evaluation Preregistration v1

Date: 2026-11-01
Authority branch: `research/loss-forensics-20261101`
Draft/staging branch: `research/loss-forensics-oos-judge-20261101`
Parent authority commit: `42171697203b617dc21fe40e791485516750d28f`
Supersedes prior Pass 3/Pass 4 governance: **NO**
Production authority: **NONE**
Trading authority: **NONE**

## 0. Purpose

This file fills the evaluation gap explicitly left open by `PROSPECTIVE_ACTUAL_AVAILABILITY_PROTOCOL_20261101.md` Section 15. It defines a bounded, fail-closed prospective out-of-sample judgment process so future chats, scripts, or reviewers cannot silently change the meaning of success after seeing outcomes.

The objective is not to guarantee success. The objective is to make success, failure, insufficiency, and data failure distinguishable in advance.

## 1. Permanent authority boundaries

The following frozen conclusions remain unchanged:

- `HISTORICAL_LATENCY = DATA_BLOCKED`.
- `PROSPECTIVE_LIVE_LATENCY = COLLECTING` until valid prospective evidence exists.
- Pass 3 promoted no new family; formal weight remains 0.
- `CORE_LOOSENING`, `BRIDGE/DESTINATION_PRELOAD`, and `PROFESSIONAL_FLOW` may not be rescued through this cohort.
- Pass 4 exact executable/interpreter provenance is not recovered; therefore formal H1 probability/classification, calibrated early-warning probability, and formal control-loss probability remain prohibited.
- No BUY/SELL, order execution, or capital authority may arise from this evaluation.

## 2. Two clocks: raw collection vs formal OOS evaluation

These clocks are deliberately separated.

### 2.1 Raw prospective collection clock
Raw Fugle, TDCC, EOD, leverage, ownership, regime-input, and other provenance-valid observations may be collected immediately and append-only.

Raw collection does **not** by itself start the formal 60-trading-day OOS clock.

### 2.2 Formal OOS clock
The formal OOS clock may start only when all ARM gates in Section 3 pass. Day 1 is the first TWSE trading day after the ARM record is frozen, unless the ARM record explicitly names a later start date.

No observation dated before the formal OOS start date may be counted toward the formal OOS judgment cohort.

This prevents a future researcher from looking at already-collected outcomes, then defining a rule and falsely calling the earlier period prospective OOS.

## 3. ARM gates — all required

Status remains `PREARMED_DATA_COLLECTING` unless every gate below is true:

1. **Candidate definition frozen** — exact hypothesis, event definition, eligible universe, exclusions, control construction, primary endpoint, direction, and minimum practical effect are specified.
2. **Executable bound** — the exact feature/event extractor executable or deterministic query package is identified and SHA-bound. Prose-only reconstruction is insufficient.
3. **Input provenance bound** — every required input has an allowed actual-availability rule. Unknown availability remains null and blocks the affected event.
4. **Outcome rule frozen** — T+1, T+5, T+20 return/drawdown definitions, corporate-action handling, missing-price handling, and market-relative benchmark rules are specified.
5. **Statistical plan frozen** — primary test, confidence interval method, clustering unit, matching/control method, and practical-effect threshold are specified before the first formal OOS day.
6. **Universe rule frozen** — universe membership rule and any exclusions are known before each session. No event-based additions/removals.
7. **Collector identity frozen** — required collector versions/workflows are identified.
8. **No prospective peeking used to tune semantics** — candidate semantics were not chosen after viewing outcomes from dates that will be counted in the cohort.
9. **Trading authority remains NONE**.
10. **ARM manifest written** — machine-readable candidate card reports every required field non-null and `arm_status = ARMED`.

If any gate fails, the system may collect raw data but formal OOS day count must remain 0.

## 4. Formal cohort duration

### Primary target

- minimum valid formal OOS trading days: **60**.
- primary collection target: **60 valid TWSE trading sessions**.
- T+20 final outcome maturity requires up to **20 additional trading sessions** after the last included signal/event date.

Thus a normally populated cohort is expected to require up to 80 trading sessions from formal Day 1 to complete final T+20 judgment.

### Bounded extension for event scarcity only

If Day 60 is reached but the event-diversity gates in Section 5 are not met, collection may continue **only because the preregistered minimum event/diversity requirement is unmet**.

- maximum collection extension: through formal trading Day **90**.
- extension may not be triggered because effect size, p-value, hit rate, or return looks disappointing.
- once event-diversity gates are satisfied after Day 60, no further collection extension is allowed for the purpose of improving results.
- if Day 90 ends and event-diversity gates remain unmet, final state is `OOS_INCONCLUSIVE_LOW_EVENT_RATE`; formal weight = 0; the cohort closes.

No indefinite extension is permitted.

## 5. Minimum event and diversity gates

A performance judgment is forbidden unless all are true:

- `valid_event_count >= 120`.
- `distinct_event_dates >= 24`.
- `distinct_event_symbols >= 30`.
- no single event date contributes more than **20%** of all valid events.
- no single symbol contributes more than **10%** of all valid events.
- at least **80%** of formal cohort trading days pass the required data-integrity gate; invalid days do not count toward the 60/90 valid-day clock.

Rationale: 100 stock-day observations from the same market session are not independent. Diversity gates reduce the chance that one crash day or one stock creates a false appearance of generality.

These are minimum eligibility gates, not evidence of success.

## 6. Outcome horizons

Every valid event must support the following outcome maturities when data exist:

- **T+1**: first subsequent TWSE trading-session outcome.
- **T+5**: fifth subsequent TWSE trading-session outcome.
- **T+20**: twentieth subsequent TWSE trading-session outcome.

For a candidate to be ARMED, one of these horizons and one exact metric must be designated as the **primary endpoint**. Other horizons are secondary robustness/descriptive endpoints unless separately preregistered.

No candidate may be called successful because the best-looking horizon was selected after outcomes were seen.

## 7. Statistical discipline

The candidate-specific ARM card must define the exact test before Day 1. At minimum:

- one primary endpoint;
- expected sign/direction;
- null value;
- minimum practical effect threshold;
- confidence interval or hypothesis-test method;
- date-clustered or other preregistered dependence handling;
- control/matching construction;
- treatment of ties, missing outcomes, halts, delistings, and corporate actions.

Default if no stronger candidate-specific method is frozen: use event-date cluster bootstrap for the primary effect and report a 95% confidence interval. A candidate may not be ARMED if the practical-effect threshold is still null.

Secondary metrics may be reported but may not rescue a failed primary endpoint.

## 8. Chronological stability gate

The formal cohort is partitioned into four chronological blocks using valid formal OOS trading days. `OOS_PASS_CANDIDATE` requires the preregistered primary effect to have the expected sign in at least **3 of 4** blocks.

A full-sample result driven by one isolated block is not sufficient for promotion.

This stability gate is directional, not a license to retune block boundaries.

## 9. Decision states

Only the following states are legal:

### `PREARMED_DATA_COLLECTING`
Raw data may be collected. Formal OOS day count = 0. No success/failure performance judgment allowed.

### `COLLECTING`
ARM gates passed and formal OOS cohort is accumulating.

### `DATA_QUALITY_FAIL`
Required timestamps/provenance, universe integrity, append-only lineage, or outcome integrity fails materially enough that a formal result cannot be trusted. This is **not** evidence that the hypothesis is false; it means the cohort is invalid or requires a new clean cohort.

### `INSUFFICIENT_EVENTS`
At Day 60, minimum event/diversity gates are not met. Collection may continue only under the bounded Day-90 extension rule.

### `OOS_INCONCLUSIVE_LOW_EVENT_RATE`
Day 90 reached without satisfying event/diversity gates. Cohort closes; formal weight = 0; no promotion.

### `OOS_FAIL`
All eligibility and maturity gates passed, but the primary endpoint fails any required success condition in Section 10. Cohort closes. Formal weight = 0. No threshold rescue, no horizon switching, no silent redefinition.

### `OOS_MIXED`
Primary endpoint fails the promotion gate while one or more secondary diagnostics show nontrivial structure, or the primary endpoint passes but stability/practical-effect criteria fail. This state is research-interest only; formal weight = 0; no production/trading authority.

### `OOS_PASS_CANDIDATE`
All Section 10 gates pass. This is **not VALIDATED** and gives no trading authority. It only authorizes a separately frozen confirmation cohort.

### `VALIDATED`
May be assigned only after a second untouched confirmation cohort under a new preregistration also passes its own frozen gates. This v1 cohort alone can never directly assign `VALIDATED`.

## 10. `OOS_PASS_CANDIDATE` gates — all required

A candidate receives `OOS_PASS_CANDIDATE` only if all are true:

1. at least 60 valid formal OOS trading days;
2. Section 5 event/diversity gates pass;
3. all included events required for the primary endpoint are mature;
4. the primary effect direction matches preregistration;
5. the primary 95% confidence interval excludes the preregistered null in the expected direction, using the frozen dependence method;
6. absolute primary effect meets or exceeds the preregistered minimum practical effect;
7. chronological stability gate passes: expected sign in at least 3 of 4 blocks;
8. control/matched comparison does not reverse the conclusion;
9. no forbidden rule change occurred after ARM;
10. no material data-quality/provenance violation occurred;
11. result is reproducible from frozen inputs and executable identities;
12. `PRODUCTION_AUTHORITY = NONE` and `TRADING_AUTHORITY = NONE` remain explicit.

Failure of any one gate prevents `OOS_PASS_CANDIDATE`.

## 11. Forbidden rescue operations

After ARM, the following are prohibited within the same cohort:

- changing event thresholds because results are weak;
- changing primary horizon because another horizon looks better;
- changing primary outcome metric because another metric looks better;
- dropping bad-performing symbols/dates/regimes unless the exclusion was preregistered;
- adding a regime filter after seeing outcomes;
- redefining controls/matches after seeing outcomes;
- extending collection because p-value or effect size is close to target;
- changing minimum practical effect;
- replacing missing actual-known-at timestamps with inferred/reference times;
- backdating observations;
- using 6415 or 3042 as special anchors to tune the rule;
- reviving frozen rejected Pass 3 families under new labels without a new preregistration;
- calling a failed primary endpoint successful because secondary endpoints look good.

Any semantic change requires: **new candidate ID + new preregistration + new ARM record + new prospective cohort starting after that freeze**.

## 12. Data-integrity day gate

A formal trading day counts only if all candidate-required vessels pass their frozen completeness/provenance checks. A day with missing required data is marked invalid and does not increment `valid_formal_trading_days`.

No later backfill may transform an originally unavailable input into an earlier `actual_known_at` value. Backfilled data may support descriptive research but not retroactively make a blocked formal event valid.

## 13. Checkpoints

### Day 20
Permitted review: collector health, missingness, event frequency, concentration, timestamp/provenance failures, runtime defects.

Forbidden review for semantic adjustment: primary performance optimization, threshold tuning, horizon switching, feature selection based on returns.

A software bug may be repaired only if the repair does not change intended semantics. If semantics change, close the cohort and start a new one.

### Day 60
- if event/diversity gates fail: state = `INSUFFICIENT_EVENTS`, bounded extension applies;
- if gates pass: stop extending for sample acquisition and wait only for required outcome maturity.

### Final maturity
Once the last included primary-endpoint outcome is mature, execute the frozen evaluation exactly once and record final judgment.

No repeated peeking followed by stopping when significance appears.

## 14. Reporting contract

Every status report must state at minimum:

- candidate ID and ARM status;
- formal OOS start date;
- valid formal trading days / 60;
- maximum collection day / 90;
- valid events / 120;
- distinct event dates / 24;
- distinct symbols / 30;
- latest T+1/T+5/T+20 matured counts;
- data-integrity status;
- forbidden semantic rule-change count;
- current state;
- formal conclusion, if any;
- production authority;
- trading authority.

Before final maturity, performance statistics may be computed for sealed internal validation only if required operationally, but they must not be used to change semantics. Prefer not exposing rolling performance to researchers during collection.

## 15. Failure is an acceptable terminal result

If the candidate reaches `OOS_FAIL`, the correct action is to close it with formal weight 0. Do not rescue it inside the same cohort.

If it reaches `OOS_MIXED`, any follow-up mechanism becomes a new research question and must start under a new preregistration. The mixed evidence may motivate a new hypothesis but cannot be promoted retroactively.

## 16. Success is intentionally hard

`OOS_PASS_CANDIDATE` means only that one prospective cohort passed its frozen primary, practical, stability, control, and provenance gates. It does not mean the mechanism is universally true and does not authorize trading.

A second untouched confirmation cohort is mandatory before `VALIDATED` may even be considered.

## 17. Cross-chat bootstrap rule

Any future ChatGPT conversation continuing this research must read, in order:

1. `PROSPECTIVE_ACTUAL_AVAILABILITY_PROTOCOL_20261101.md`;
2. this preregistration;
3. the frozen OOS lock manifest;
4. the machine-readable OOS state;
5. the candidate ARM card;
6. latest relevant prospective immutable ledgers.

If any required authority artifact is missing, inconsistent, or hash-invalid, fail closed and report the inconsistency instead of inferring the intended rule from conversational memory.

## 18. Final authority statement

This plan governs evaluation timing and judgment only. It does not reopen historical latency, does not reconstruct the missing Pass 4 interpreter, does not promote any rejected family, and does not create production or trading authority.

The correct sequence is:

`RAW COLLECTION -> ARM -> FORMAL OOS COLLECTION -> MATURITY -> ONE FROZEN EVALUATION -> FAIL/MIXED/PASS_CANDIDATE -> SEPARATE CONFIRMATION COHORT IF WARRANTED`.
