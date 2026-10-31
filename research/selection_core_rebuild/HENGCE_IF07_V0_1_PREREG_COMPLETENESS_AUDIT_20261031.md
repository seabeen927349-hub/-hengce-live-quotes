# HENGCE IF-07 V0.1 Preregistration Completeness Audit

Date: 2026-10-31
Challenger: `IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1`
Audit scope: existing frozen preregistration only
Preregistration mutation: `NONE`
Forward returns opened: `NO`
Stage B executed: `NO`

## Authority identities audited

### Frozen preregistration
- Path: `research/selection_core_rebuild/HENGCE_IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1_PREREG_20261031.md`
- Creation commit: `a607cfdf1706a95ad4fc854899007cf366599deb`
- Current Git blob SHA: `4dd87057f78cbd8be7c889602d261b5038b79672`
- Current branch content matches the file at the creation commit byte-for-byte at Git blob identity level: `YES`
- Status at creation: `PREREGISTERED_NOT_YET_RETURN_TESTED`

### Stage B candidate authority
- Authority declaration: `research/selection_core_rebuild/HENGCE_IF07_STAGE_B_CANDIDATE_AUTHORITY_20261031.json`
- Source Stage A workflow run: `41176211171`
- Source Stage A Actions artifact ID: `13032993979`
- Source artifact ZIP SHA-256: `2366448ec259065df5e2a515a11bb9fbf0a5c40b806607f6ac1edce0385ee782`
- Recovered original rows path: `research/selection_core_rebuild/generated/IF07_STAGE_A_ACCOUNTING_UPPER_BOUND_NO_RETURNS.json`
- Recovered original rows SHA-256: `64ea76312f99413965edc8ca9797864ef04d3ba8c2cee1f47bf950ffa9fa3bfb`
- Recovered original rows Git blob SHA: `6d201a70627e03c2fa704c070210c04ba9435046`
- Recovered files commit: `106692af641964c326116527f07b70e3e139d4d5`
- Candidate count: `187`
- Unique candidate tickers: `128`
- Candidate identity law: only original rows where `accounting_6of6_pre_metadata_candidate == true` in the exact hashed rows authority may enter Stage B.

## Completeness audit

The audit does not add, infer, repair, reinterpret, or optimize any rule. `PREREG_INCOMPLETE` means the requested item is not fully frozen to a mechanically reproducible specification inside V0.1 as persisted before forward-return inspection.

| Requested item | Audit status | Existing V0.1 content | Completeness finding |
|---|---|---|---|
| universe / PIT membership | COMPLETE | §2 fixes `TWSE_LISTED_ELECTRONICS_PIT_DAILY`; company must be TWSE-listed electronics on the PIT date; TPEx excluded; eligibility conditions enumerated. | Explicitly frozen. |
| signal timing | COMPLETE | §3 defines `signal_date` as first TWSE trading day whose official close occurs strictly after `upload_ts`; signal after close. | Explicitly frozen. |
| financial statement availability timing | COMPLETE | §3 fixes official TWSE electronic-report `上傳日期` as `upload_ts`; quarter-end/statutory deadline cannot substitute; original filing/revision law fixed. | Explicitly frozen. |
| accounting fields used | COMPLETE | §4 fixes eight current fields and identical prior-year same-quarter fields. | Explicitly frozen. |
| exact Earnings Quality / zero-red-flag formula | COMPLETE | §§5-6 freeze all six formulas and pass inequalities; all six must pass. | Explicitly frozen. |
| missing-value / unavailable-field treatment | COMPLETE | §2: missing required accounting data => excluded/fail closed; no imputation, synthetic history, or later backfill. §9 also requires fail-closed missing-price treatment for null pairing. | Explicitly frozen for the stated event/null contract. |
| candidate inclusion / exclusion rule | COMPLETE | §§2, 6 fix eligibility plus six-of-six selection, all names on a date, no max-k, no whitelist/rescue. | Explicitly frozen. |
| holding horizons | COMPLETE | §8 fixes 5/10/20/40/60 TWSE sessions; 20 primary; secondary horizons cannot rescue primary failure. | Explicitly frozen. |
| next-open execution rule | COMPLETE | §§3, 8 fix next TWSE open after signal date. | Explicitly frozen. |
| transaction cost | COMPLETE | §8 fixes 40 bps total round trip and subtraction convention. | Explicitly frozen. |
| overlap / duplicate handling | COMPLETE | §7 fixes one event/ticker/fiscal-quarter, earliest original upload, no new correction event, signal-date blocks, later-quarter overlap allowed, portfolio no-pyramiding requirement. | Explicitly frozen at event level; no-pyramiding also stated for later portfolio proof. |
| N0 / N1 / N2 / N3 null comparisons | COMPLETE | §9 defines N0 equal-weight eligible cross-section; N1 prior-20-session momentum TopK; N2 prior-5-session reversal BottomK; N3 matched random seed 20261031, 10,000 draws; pairing geometry fixed. §14 mandates all four forms of reporting/comparison. | Null families and pairing are frozen. N2 is mandatory comparison/reporting but is not a Discovery/Validation PASS gate. |
| tail-dependency tests, including remove-best 1 / 3 / 5 | COMPLETE | §14 mandates remove-best 1/3/5 for every opened horizon; §§12-13 make remove-best-5 > 0 a primary-horizon PASS condition. | Explicitly preregistered. |
| latest-3M gate | PREREG_INCOMPLETE | §15 states latest 3 months total PnL > 0 and strong-market latest-3M loss = KILL. §11 requires >=10 matured primary-horizon trades and >=5 distinct signal dates for final latest-3M promotion. | The requirement exists, but V0.1 does not fully freeze a mechanically reproducible latest-3M PnL construction/window anchoring or the definition of `strong-market`. No rule may be supplied now. |
| trade-count / frequency / capital-efficiency reporting | PREREG_INCOMPLETE | §14 reports event count, unique tickers, signal-date count, signals/month. §15 requires `sufficient actual trade count/frequency/capital efficiency`. | Event/frequency descriptive reporting is partly specified, but `sufficient` and `capital efficiency` have no frozen calculation or threshold in V0.1. |
| yearly / regime splits | PREREG_INCOMPLETE | §14 mandates `year-by-year` and `regime splits`; §15 additionally requires bear/weak-market behavior. | Year-by-year reporting is explicit, but regime definitions/classification rules are not frozen. Therefore the combined requested item is incomplete. |
| portfolio-level finite-capital test | PREREG_INCOMPLETE | §15 requires finite-capital portfolio accounting; §7 forbids pyramiding. | The requirement exists, but V0.1 does not freeze portfolio starting capital, sizing/allocation, concurrent-signal cash allocation, lot/share convention, cash reuse, or a complete PASS rule. No values may be added now. |
| TAIEX comparison | PREREG_INCOMPLETE | §15 requires contemporaneous TAIEX outperformance. | The requirement exists, but the exact portfolio/event benchmark geometry and formal comparison statistic are not frozen in V0.1. |
| explicit PASS / FAIL / INCONCLUSIVE conditions | PREREG_INCOMPLETE | §§11-13 explicitly define Discovery/Validation PASS/FAIL and sample-insufficiency `INCONCLUSIVE`; Validation PASS yields only `RESEARCH_VALIDATION_PASS`. §15 lists additional final-promotion laws. | Research-stage PASS/FAIL/INCONCLUSIVE is explicit. Full lifecycle/final-promotion PASS/FAIL is not mechanically complete because several §15 gates above are themselves unspecified. |

## Audit verdict

`PREREG_COMPLETENESS = PREREG_INCOMPLETE`

Reason: the event-level research experiment is substantially and explicitly preregistered, but several user-required final-promotion / portfolio-level controls were only named as hard laws and were not frozen to executable specifications before returns: latest-3M mechanics/strong-market definition, sufficient trade-count/frequency/capital-efficiency rule, regime definition, finite-capital portfolio construction, exact TAIEX comparison, and therefore full-lifecycle PASS/FAIL completeness.

This verdict is **not**:
- `DATA_BLOCKED`;
- model `FAIL`;
- permission to alter V0.1;
- permission to create replacement thresholds after seeing returns.

## Governance consequence

- V0.1 remains frozen and unmodified.
- Stage A remains PASS.
- 187-candidate authority remains frozen and unchanged.
- Stage B remains `PREPARED_NOT_EXECUTED`.
- Forward returns remain `SEALED`.
- Validation remains unopened.
- Production / trading authority remains `NONE`.
- No new data source exploration is authorized.
- This audit does not authorize Stage B execution or forward-return opening.
