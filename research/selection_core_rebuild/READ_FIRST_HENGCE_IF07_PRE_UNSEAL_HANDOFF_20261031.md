# READ FIRST — HENGCE IF-07 PRE-UNSEAL HANDOFF — 2026-10-31

## 0. Purpose

This is the authoritative handoff for continuing HENGCE Selection Core / IF-07 in a new conversation.

Repository: `seabeen927349-hub/-hengce-live-quotes`  
Branch: `research/selection-core-rebuild-20261031`  
State before this handoff packaging commit: `567c18ac1ac64297ed6983a4e9623847aff6fa0f`

This handoff is packaging only. It does not execute Stage B, open returns, mutate the challenger, or create trading authority.

## 1. Current formal state

- Challenger: `IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1`
- PIT data capability: `PASS`
- Preregistration: `FROZEN_UNCHANGED`
- Stage A: `PASS_NO_RETURN_STAGE_A`
- Exact Stage A candidate authority: `RECOVERED_VERIFIED_FROZEN`
- Candidate count: `187`
- Unique candidate tickers: `128`
- Stage B: `PREPARED_NOT_EXECUTED`
- Stage B offline admission gate: `NOT_EXECUTED`
- Exact t57 retrieval after authority recovery: `NOT_STARTED`
- Forward returns: `SEALED_NOT_OPENED`
- Discovery returns: `NOT_AUTHORIZED`
- Validation: `NOT_OPENED`
- Production / trading authority: `NONE`
- New data-source exploration: `CLOSED`
- Current stop reason: explicit user instruction not to execute Stage B until later authorization.

## 2. Frozen Selection specification — do not modify

The following remain frozen and outside any later governance addendum's authority:

- `IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1`;
- 187-event / 128-ticker authority;
- candidate identity rule `accounting_6of6_pre_metadata_candidate == true` in the exact recovered rows authority;
- PIT universe;
- accounting fields;
- all six ZERO_RED_FLAG formulas and thresholds;
- missing-value treatment;
- financial-statement availability and revision law;
- signal timing;
- candidate inclusion/exclusion;
- holding horizons 5/10/20/40/60 sessions;
- primary horizon 20 sessions;
- next-open entry convention;
- 40 bp total round-trip transaction cost;
- N0/N1/N2/N3 null definitions;
- remove-best 1/3/5 reporting;
- year-by-year reporting;
- Discovery / Validation split and contract;
- research-stage `INCONCLUSIVE` rule;
- no-pyramiding event/portfolio law.

No silent mutation, no rescue retuning, no threshold adjustment after outcomes, no candidate reconstruction, no new whitelist, and no winner-aware feature selection.

## 3. Exact candidate authority

Authority declaration:
`research/selection_core_rebuild/HENGCE_IF07_STAGE_B_CANDIDATE_AUTHORITY_20261031.json`

Exact recovered original rows:
`research/selection_core_rebuild/generated/IF07_STAGE_A_ACCOUNTING_UPPER_BOUND_NO_RETURNS.json`

Rows SHA-256:
`64ea76312f99413965edc8ca9797864ef04d3ba8c2cee1f47bf950ffa9fa3bfb`

Rows Git blob SHA:
`6d201a70627e03c2fa704c070210c04ba9435046`

Recovered original audit:
`research/selection_core_rebuild/generated/IF07_STAGE_A_ACCOUNTING_UPPER_BOUND_AUDIT_NO_RETURNS.json`

Audit SHA-256:
`abdfa1d7e689ab96d50f6f5f93282ecd311330ce55c54e15a83700364aa3815b`

Audit Git blob SHA:
`dc8b7d3e7114842522e0f398ae41c2b07fe84bc3`

Original Stage A source:
- workflow run `41176211171`
- job `124464189390`
- Actions artifact ID `13032993979`
- artifact ZIP SHA-256 `2366448ec259065df5e2a515a11bb9fbf0a5c40b806607f6ac1edce0385ee782`
- recovered files commit `106692af641964c326116527f07b70e3e139d4d5`

No separate original 187-only manifest existed. The full exact rows JSON above is the sole authority because it contains the original candidate flags. Never manufacture a derived 187-only file and call it original authority.

## 4. Preregistration and completeness finding

Frozen preregistration:
`research/selection_core_rebuild/HENGCE_IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1_PREREG_20261031.md`

Creation commit:
`a607cfdf1706a95ad4fc854899007cf366599deb`

Git blob SHA:
`4dd87057f78cbd8be7c889602d261b5038b79672`

Completeness audit:
`research/selection_core_rebuild/HENGCE_IF07_V0_1_PREREG_COMPLETENESS_AUDIT_20261031.md`

Audit commit:
`3789e3c73e05599892fdd3e279d358c3c6036091`

Finding:
`PREREG_INCOMPLETE` applied only to Evaluation / Promotion Governance mechanics, not to the IF-07 Selection specification itself.

Missing executable promotion mechanics were: latest-3M construction, sufficient actual trade-frequency/capital-efficiency rule, ex-ante market-regime classification, finite-capital portfolio construction, exact contemporaneous TAIEX comparison, and full final-promotion / cross-cycle / lifecycle-de-duplication contract.

## 5. Promotion-governance addendum — now frozen before returns

Artifact:
`research/selection_core_rebuild/HENGCE_IF07_PRE_UNSEAL_GOVERNANCE_ADDENDUM_V0_1_20261031.md`

Artifact ID:
`HENGCE_IF07_PRE_UNSEAL_GOVERNANCE_ADDENDUM_V0_1`

Creation commit:
`f9e3c7d1388815c34d1354e090f9831de29b8682`

Git blob SHA:
`25d87ae6ad9370050fae1cf1e896fb68ba206d25`

SHA-256 from GitHub runner against persisted bytes:
`84dbe99cb21cb42bc3a169d8b79a7fb0ac227f4600828c27c673c6480826104b`

Verification workflow run:
`41183468206`

Verification conclusion:
`SUCCESS`

One-shot verifier cleanup commit:
`567c18ac1ac64297ed6983a4e9623847aff6fa0f`

The addendum has `EVALUATION_AND_PROMOTION_GOVERNANCE_ONLY` scope and zero Selection / trading authority.

### Directly inherited HENGCE hard laws

- latest-3M is mandatory;
- latest-3M total PnL must be positive, otherwise KILL;
- strong-market latest-3M loss is KILL;
- actual trade count/frequency/capital efficiency are mandatory;
- cross-cycle and weak/bear evidence are mandatory;
- contemporaneous TAIEX outperformance is mandatory;
- finite-capital portfolio accounting is mandatory;
- fixed NT$1,000,000 research-capital convention, no upward compounding, 1,000-share round lots and 40 bp cost are inherited where compatible;
- no silent mutation, post-hoc retuning, cherry-picking, winner-aware tuning, negative-result suppression or retroactive metric switching;
- no automatic production promotion.

### New operationalization frozen before returns

- latest-3M = 63 TWSE sessions ending on evaluation cutoff;
- portfolio-level actual-execution sufficiency uses at least 10 executed matured trades and 5 distinct executed signal dates, alongside the original V0.1 event sufficiency;
- capital-efficiency formula = total net PnL divided by TWD capital-years (`sum(entry_notional * held_sessions) / 252`); must be finite and positive, with no invented positive numeric hurdle beyond sign;
- ex-ante TAIEX regimes: BEAR if 252-session drawdown <= -20%; otherwise STRONG if 63-session TAIEX return > 0; otherwise WEAK;
- finite-capital portfolio ledger: NT$1m deployment ceiling, 1,000-share round lots, no leverage, no negative cash, no upward compounding, equal same-entry-session cash slices, no same-session residual reallocation, no pyramiding;
- TAIEX comparison uses identical calendar windows and requires positive excess for promotion-critical windows;
- full cross-cycle target = PIT-safe obtainable 2018-01-02 through 2026-06-30; inability to construct it without violating PIT law => `DATA_BLOCKED`;
- WEAK and BEAR promotion evidence each require >=10 executed trades and >=5 distinct executed signal dates; insufficient evidence => `INCONCLUSIVE`; sufficient evidence requires positive attributed net PnL;
- lifecycle de-duplication and duplicate/pyramiding integrity checks are deterministic final gates;
- final governance result can be PASS / FAIL / INCONCLUSIVE / DATA_BLOCKED, but even PASS remains `AWAITING_EXPLICIT_HUMAN_PRODUCTION_AUTHORIZATION`.

## 6. Current forward-return seal evidence

`research/selection_core_rebuild/CURRENT_STATE_20261031.json` still records:

- `selection_core.challenger_status = PREREGISTERED_NOT_YET_RETURN_TESTED`
- `selection_core.new_candidate_forward_return_inspected = false`
- `formal_status.stage_b = PREPARED_NOT_EXECUTED`
- `formal_status.forward_returns = SEALED_NOT_OPENED`
- `formal_status.validation = NOT_OPENED`
- `formal_status.production_trading_authority = NONE`
- `stage_b_preparation.manifest_admission_executed = false`
- `stage_b_preparation.exact_t57_retrieval_started = false`
- `stage_b_preparation.signal_date_mapping_started = false`
- `stage_b_preparation.pit_membership_gate_started = false`
- `stage_b_preparation.discovery_returns_authorized = false`
- `forward_return_lock.state = SEALED_CLOSED`
- `forward_return_lock.validation_returns_forbidden_until_discovery_pass = true`

The addendum verification workflow independently confirmed Stage B remained prepared/not executed, forward returns remained sealed/not opened, Validation remained unopened, and production authority remained NONE.

## 7. Stage B preparation already exists — but remains unauthorized to run now

Stage B exact-metadata contract:
`research/selection_core_rebuild/HENGCE_IF07_STAGE_B_EXACT_METADATA_EXECUTION_CONTRACT_20261031.md`

Prepared offline admission gate:
`research/selection_core_rebuild/if07_stage_b_candidate_manifest_gate_no_network.py`

The gate has not been executed against the recovered authority after recovery.

When and only when the user explicitly authorizes Stage B, the first legal execution step is:

1. fetch/verify the exact candidate authority declaration and exact recovered rows SHA-256;
2. run the prepared `if07_stage_b_candidate_manifest_gate_no_network.py` offline against that exact rows authority;
3. if it fails, STOP — no repair, reconstruction, retuning or replacement sample;
4. if it passes, persist/reread the admission result;
5. only after that may exact official t57 metadata retrieval begin, if the user's authorization covers metadata retrieval;
6. no forward returns may be opened until exact metadata -> signal_date -> PIT membership -> dedup -> no-return panel/audit/count gates all pass;
7. Validation remains forbidden until Discovery passes.

A derivative identity/request manifest may be an operational output after admission PASS, but it has zero authority and must never replace the exact original rows authority.

## 8. Explicitly forbidden

Do not:

- revive V6 or V43 as the new core;
- rescue capital-share migration;
- retune price/volume smart-money logic;
- inject Escape v2.4.7 into Selection alpha;
- rerun Stage A;
- infer/reconstruct/rescreen the 187 candidates;
- create a derived 187-only file and call it original authority;
- reopen rejected timestamp proxies;
- use bulk ZIP member timestamps, iXBRL HTTP Date/Last-Modified, board-approval date or another proxy instead of exact t57 `上傳日期`;
- use the invalid early metadata index as panel input;
- use annual ticker union as PIT universe;
- query t57 before explicit Stage B authorization and offline admission PASS;
- inspect/open Discovery returns before all remaining no-return integrity gates pass;
- open Validation before Discovery PASS;
- alter V0.1 preregistration;
- alter the promotion addendum in place after outcomes are opened;
- downgrade any global HENGCE hard gate because IF-07 finds it difficult.

## 9. Source/data facts worth preserving

- Official upload-time authority is TWSE t57sb01 electronic report `上傳日期`, to seconds.
- Bulk MOPS iXBRL accounting is usable for exact accounting values.
- Bulk ZIP member timestamps were proven invalid as filing timestamps.
- Fugle financial-report connector specs exist, but content retrieval probe returned empty data; classify that connector path as `DATA_BLOCKED`, not provider absence.
- Early blank-year/concurrent metadata builder was invalidated due rate-limit/transport bias; its apparent 794 pairs are permanently forbidden panel input.
- PIT universe authority is canonical daily TWSE electronics archive row presence on signal date, not annual/acquisition ticker union.
- Stage A V0.2 exact result: 3560 pair attempts, 2853 accounting pairs available, 187 six-of-six pre-metadata candidates, 128 unique tickers, parser cross-check mismatch 0.
- Candidate period counts: 2022Q4 41; 2023Q1 23; 2023Q2 27; 2023Q3 23; 2023Q4 19; 2024Q1 17; 2024Q2 22; 2024Q3 15.

## 10. New-chat startup rule

On opening a new chat, first read this file, then read:

1. `CURRENT_STATE_20261031.json`
2. `HENGCE_IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1_PREREG_20261031.md`
3. `HENGCE_IF07_V0_1_PREREG_COMPLETENESS_AUDIT_20261031.md`
4. `HENGCE_IF07_PRE_UNSEAL_GOVERNANCE_ADDENDUM_V0_1_20261031.md`
5. `HENGCE_IF07_STAGE_B_CANDIDATE_AUTHORITY_20261031.json`
6. `HENGCE_IF07_STAGE_B_EXACT_METADATA_EXECUTION_CONTRACT_20261031.md`
7. `if07_stage_b_candidate_manifest_gate_no_network.py`

Then report the loaded state and STOP. Do not execute Stage B unless the user gives a new explicit instruction authorizing Stage B.

The correct current endpoint is:

`IF07_SELECTION_FROZEN + PRE_UNSEAL_GOVERNANCE_FROZEN + STAGE_B_PREPARED_NOT_EXECUTED + FORWARD_RETURNS_SEALED_NOT_OPENED + VALIDATION_NOT_OPENED + TRADING_AUTHORITY_NONE`
