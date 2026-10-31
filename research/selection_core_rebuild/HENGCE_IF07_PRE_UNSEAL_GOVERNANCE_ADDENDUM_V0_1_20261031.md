# HENGCE IF-07 PRE-UNSEAL GOVERNANCE ADDENDUM V0.1

Date frozen: 2026-10-31  
Artifact ID: `HENGCE_IF07_PRE_UNSEAL_GOVERNANCE_ADDENDUM_V0_1`  
Scope: `EVALUATION_AND_PROMOTION_GOVERNANCE_ONLY`  
Selection specification authority: `NONE`  
Trading / production authority: `NONE`  
Forward returns at freeze: `SEALED_NOT_OPENED`  
Stage B at freeze: `PREPARED_NOT_EXECUTED`

## 0. Purpose and hard boundary

This addendum operationalizes only evaluation / promotion governance that existed as HENGCE hard law but was not mechanically complete in `IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1`.

It is not a replacement preregistration and has zero authority to mutate, reinterpret, reconstruct, rerank, rescreen, or relax the frozen IF-07 Selection specification.

The following remain immutable and are outside this addendum's authority:

- `IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1`;
- the recovered 187-event / 128-ticker Stage B candidate authority;
- candidate identity rule `accounting_6of6_pre_metadata_candidate == true` in the exact hashed authority rows;
- PIT universe and membership law;
- financial-statement availability timing;
- accounting fields;
- ZERO_RED_FLAG formulas and inequalities;
- missing-value / unavailable-field treatment;
- signal timing;
- candidate inclusion / exclusion;
- holding horizons;
- next-open execution;
- total round-trip transaction cost of 40 bps;
- overlap / event de-duplication law already frozen in V0.1;
- N0 / N1 / N2 / N3 definitions;
- remove-best 1 / 3 / 5 reporting;
- year-by-year reporting;
- Discovery / Validation contract;
- research-stage `INCONCLUSIVE` rule.

No rule in this addendum may alter which events are Selection candidates. It only controls whether a frozen challenger may later be promoted after its already-frozen research contract is tested.

## 1. Frozen identities

### 1.1 IF-07 V0.1 preregistration

Path:
`research/selection_core_rebuild/HENGCE_IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1_PREREG_20261031.md`

Creation commit:
`a607cfdf1706a95ad4fc854899007cf366599deb`

Git blob SHA:
`4dd87057f78cbd8be7c889602d261b5038b79672`

Status:
`FROZEN_UNCHANGED`

### 1.2 Stage B candidate authority

Authority declaration:
`research/selection_core_rebuild/HENGCE_IF07_STAGE_B_CANDIDATE_AUTHORITY_20261031.json`

Exact recovered rows:
`research/selection_core_rebuild/generated/IF07_STAGE_A_ACCOUNTING_UPPER_BOUND_NO_RETURNS.json`

Rows SHA-256:
`64ea76312f99413965edc8ca9797864ef04d3ba8c2cee1f47bf950ffa9fa3bfb`

Rows Git blob SHA:
`6d201a70627e03c2fa704c070210c04ba9435046`

Recovered files commit:
`106692af641964c326116527f07b70e3e139d4d5`

Candidate count:
`187`

Unique candidate tickers:
`128`

Only rows whose original `accounting_6of6_pre_metadata_candidate` value is exactly `true` in that exact hashed file may enter Stage B.

## 2. Existing HENGCE governance inherited without modification

The following are direct inheritance, not new IF-07 thresholds.

### 2.1 Research integrity lock — inherited

From `HENGCE_RESEARCH_INTEGRITY_LOCK_V1_20261031`:

- failure is acceptable;
- fabricated success is forbidden;
- cherry-picking is forbidden;
- silent mutation is forbidden;
- post-hoc threshold retuning is forbidden;
- winner-aware feature selection is forbidden;
- negative-result suppression is forbidden;
- retroactive metric switching is forbidden;
- challenger preregistration must precede forward-return testing;
- promotion requires portfolio-level proof;
- legal result states are `PASS / FAIL / INCONCLUSIVE / DATA_BLOCKED`.

### 2.2 Selection rebuild hard-validation law — inherited

From the frozen Selection Core rebuild handoff / state:

- latest three months are a mandatory validation gate;
- latest-three-month total PnL must be `> 0`; otherwise KILL;
- a strong-market latest-three-month loss is KILL;
- actual trade count, trade frequency, and capital efficiency must be reported and cannot be replaced by one or two lucky trades;
- long-cycle evidence must cover the PIT-safe 2018–2026H1 range that can legitimately be obtained;
- weak / bear market behavior must be checked;
- contemporaneous TAIEX comparison is mandatory;
- finite-capital portfolio accounting is mandatory;
- event means alone cannot promote;
- costs, next-open execution, overlap, and capital constraints must be locked before promotion testing;
- no production promotion follows automatically from a research pass.

### 2.3 Null / baseline governance — inherited

From `HENGCE_SELECTION_CORE_NULL_BASELINE_CONTRACT_V1_20261031`:

- same-date / same-PIT-universe / same-selected-count comparison geometry remains frozen;
- 40 bp total round-trip cost remains frozen;
- 5 / 10 / 20 / 40 / 60-session reporting remains frozen;
- recent-3M, year-by-year, regime splits, remove-best 1/3/5 and null-relative evidence remain mandatory;
- portfolio capital accounting and TAIEX-relative cross-cycle evidence are required before promotion.

### 2.4 V0.1-specific governance already frozen — inherited

This addendum does not replace these existing V0.1 rules:

- primary promotion research horizon = 20 TWSE sessions;
- final latest-3M promotion gate requires at least 10 matured primary-horizon trades and 5 distinct signal dates;
- an already-held ticker cannot receive additional notional from a new signal until its existing tested-horizon position exits;
- if earlier PIT accounting data cannot be acquired for cross-cycle proof, final promotion remains `DATA_BLOCKED`.

### 2.5 Existing HENGCE finite-capital / recent-3M validation convention — inherited where compatible

This is not an IF-07-derived threshold.

Existing HENGCE frozen / audited validation artifacts already use a user-locked research standard of:

- fixed research capital `NT$1,000,000`;
- no upward compounding of the deployment budget;
- Taiwan round-lot execution = `1,000 shares`;
- 40 bp round-trip research cost where the governing model contract uses 40 bp;
- recent-three-month evaluation represented by 63 TWSE trading sessions in the frozen recent-3M audit.

The Selection Core rebuild handoff separately requires whole-lot / capital constraints to be locked before testing.

Therefore this addendum inherits `NT$1,000,000`, `1,000-share round lots`, no upward compounding, and the 63-session recent-3M convention as pre-existing HENGCE validation conventions. It does not inherit any old model's signal, ranking, exposure scaler, or alpha rule.

The exact multi-position cash-allocation mechanics were not globally frozen and are operationalized below.

## 3. New operationalization: latest-3M gate

Classification:
`MIXED — positive-PnL / strong-market-KILL law is inherited; 63-session recent-3M convention is inherited from existing HENGCE validation standard; event-to-ledger mechanics are new operationalization.`

### 3.1 Window

`evaluation_cutoff` = the last TWSE trading session included in the frozen evaluation snapshot.

`latest_3m_sessions` = the 63 TWSE trading sessions ending on `evaluation_cutoff`, inclusive.

A primary-horizon event belongs to latest-3M evidence if:

1. its frozen `signal_date` is inside `latest_3m_sessions`; and
2. its frozen 20-session exit is mature and observable by `evaluation_cutoff`.

Immature events are excluded by the existing V0.1 maturity law; they are never assigned synthetic outcomes.

### 3.2 Gate statistics

The latest-3M gate is evaluated on the finite-capital portfolio ledger defined in §6, not on the arithmetic mean of event returns.

Required fields:

- matured candidate events;
- executed trades;
- skipped-for-no-cash trades;
- overlap-suppressed trades;
- distinct executed signal dates;
- total net PnL TWD;
- portfolio return;
- TAIEX return over the same 63-session window;
- excess versus TAIEX;
- mean capital utilization;
- capital efficiency.

### 3.3 Latest-3M decision

Two sufficiency checks are kept distinct:

- the original V0.1 event-sample condition remains unchanged: at least 10 matured primary-horizon event-trades and 5 distinct signal dates;
- as a new promotion-governance operationalization, the finite-capital ledger must also contain at least 10 actually executed matured trades and 5 distinct executed signal dates. The same numeric floor is used deliberately so governance cannot become more permissive than the already-frozen V0.1 latest-3M minimum.

`PASS` only if:

- original V0.1 latest-3M event-sample sufficiency passes;
- finite-capital executed-trade sufficiency passes;
- total finite-capital net PnL `> 0`;
- latest-3M portfolio excess versus contemporaneous TAIEX under §7 is `> 0`.

If either sufficiency check is not met while data are otherwise valid, state = `INCONCLUSIVE`.

If total finite-capital net PnL `<= 0` or latest-3M excess versus TAIEX `<= 0`, state = `FAIL`.

If the same latest-3M market window is classified `STRONG` under §5 and total finite-capital net PnL `<= 0`, state = `FAIL_KILL_STRONG_MARKET`.

No alternative latest-3M window may be selected after outcomes are opened.

## 4. New operationalization: trade frequency and capital efficiency

Classification:
`OPERATIONALIZATION_NEW — global reporting / sufficiency law existed; exact calculations did not.`

No new candidate-count threshold is inferred from the 187-event authority.

### 4.1 Frequency

Report:

`trades_per_63_sessions = executed_trade_count * 63 / evaluation_window_session_count`

and:

`distinct_signal_dates_per_63_sessions = executed_distinct_signal_dates * 63 / evaluation_window_session_count`

For latest-3M promotion sufficiency, the original V0.1 event minimum is preserved and the finite-capital actual-execution ledger uses the same 10-trade / 5-date floor as specified in §3. No lower IF-07-specific frequency threshold is introduced.

For regime-critical promotion evidence in §8, the same 10 executed trades / 5 distinct signal dates floor is used for each required WEAK and BEAR bucket. This is a new governance operationalization that reuses an already-frozen sufficiency magnitude rather than inventing a smaller IF-07-friendly one.

For Discovery / Validation research-stage sufficiency, the original V0.1 rules remain unchanged and are not replaced by portfolio trade counts.

### 4.2 Capital utilization

For each TWSE session:

`capital_utilization_t = occupied_entry_notional_t / 1,000,000`

where `occupied_entry_notional_t` is the sum of entry notionals still locked in open positions.

The inherited fixed deployment ceiling and no-leverage rule require:

`0 <= capital_utilization_t <= 1`

Report the time-series mean, median, maximum, and fraction of sessions with zero deployed capital.

### 4.3 Capital efficiency

For each executed trade `i`:

`capital_sessions_i = entry_notional_i * held_TWSE_sessions_i`

Portfolio capital-session denominator:

`capital_years_TWD = sum_i(capital_sessions_i) / 252`

Capital efficiency:

`capital_efficiency = total_net_pnl_TWD / capital_years_TWD`

A value is valid only when `capital_years_TWD > 0` and all ledger components are finite.

Because no pre-existing HENGCE numeric hurdle for capital efficiency was found, this addendum does not invent one. Promotion requires the metric to be finite and strictly positive; the actual value must be reported. This sign requirement is not a new alpha threshold: it is the minimal operational form of the existing positive-PnL / capital-efficiency hard law.

If `capital_years_TWD == 0`, state = `INCONCLUSIVE`, not PASS.

## 5. New operationalization: ex-ante TAIEX regime classification

Classification:
`OPERATIONALIZATION_NEW — weak / bear / strong testing was mandatory; exact classification was not frozen.`

Only official TAIEX closes available on or before each classification date may be used.

For each signal date `t`:

`R63_TAIEX(t) = Close_TAIEX(t) / Close_TAIEX(t-63 sessions) - 1`

`DD252_TAIEX(t) = Close_TAIEX(t) / max(Close_TAIEX over t-251 ... t) - 1`

Mutually exclusive regime label:

1. `BEAR` if `DD252_TAIEX(t) <= -0.20`;
2. otherwise `STRONG` if `R63_TAIEX(t) > 0`;
3. otherwise `WEAK`.

The -20% drawdown boundary is a conventional bear-market operational definition chosen before returns are opened. It is not estimated from IF-07 and may not be changed in place.

For the latest-3M window as a whole:

- `LATEST3M_BEAR` if the end-date `DD252_TAIEX <= -0.20`;
- otherwise `LATEST3M_STRONG` if the 63-session TAIEX window return `> 0`;
- otherwise `LATEST3M_WEAK`.

Regime labels are determined solely from TAIEX history and never from IF-07 outcomes.

## 6. Finite-capital portfolio ledger

Classification:
`MIXED — NT$1,000,000 / 1,000-share round lot / no upward compounding are inherited HENGCE validation conventions; multi-position cash-allocation mechanics are new operationalization.`

The ledger is generic. No parameter below was selected from IF-07 event count, ticker identity, sector mix, price distribution, or returns.

### 6.1 Capital authority and deployable budget

Initial research account equity:

`C0 = NT$1,000,000`

Round lot:

`LOT = 1,000 shares`

Odd-lot execution for the promotion ledger:

`FORBIDDEN`

Leverage / borrowing / negative cash:

`FORBIDDEN`

Upward compounding of the deployment budget:

`FORBIDDEN`

The account still records realized gains and losses so total PnL and ending equity are exact. However, the maximum deployable capital at any time never exceeds the original `NT$1,000,000`.

Define:

`deployable_equity_t = min(current_account_equity_t, 1,000,000)`

Realized profits above the original NT$1,000,000 remain reserve cash and are not redeployed. Realized losses reduce deployable capital until recovered. This preserves the existing fixed-capital / no-compounding HENGCE validation convention while still enforcing real finite-capital occupancy.

This is research normalization only. It is not a statement about the user's actual account and creates no trading authority.

Each promotion-evaluation window is replayed as a separate research ledger that starts `FLAT` with `C0` immediately before the first session of that window. No position generated by a signal date outside that window is imported into it. This preserves the frozen V0.1 rule that Discovery / Validation membership and latest-3M evidence are assigned by `signal_date`, and it prevents cross-window compounding.

### 6.2 Same-session allocation

For all new, non-suppressed positions whose frozen next-open entry falls on the same TWSE session:

1. compute cash actually deployable before that session's open, excluding capital already occupied by open positions and excluding reserve profit above the NT$1,000,000 deployment ceiling;
2. let `m` be the number of new eligible names entering that session after same-ticker overlap suppression;
3. assign each name the same provisional budget: `slice = deployable_cash / m`;
4. round-lot quantity = `floor(slice / (entry_open * 1000))`;
5. shares = `round_lot_quantity * 1000`;
6. if round-lot quantity = 0, record `SKIPPED_NOT_EXECUTABLE_CAPITAL`;
7. unused cash from a zero-lot or residual slice is not reallocated to another same-session name.

Ticker ordering cannot affect allocation. No name receives priority because of price, identity, prior performance, or later outcome.

### 6.3 Cash and cost ledger

The frozen V0.1 total round-trip cost remains exactly 40 bps.

This addendum does not change that cost or invent a different fee/slippage model.

At entry:

`entry_notional = shares * entry_open`

`cash_debit = entry_notional`

At frozen 20-session exit:

`gross_trade_return = exit_close / entry_open - 1`

`net_trade_return = gross_trade_return - 0.004`

`cash_credit = entry_notional * (1 + net_trade_return)`

This is the exact frozen V0.1 40 bp net-return convention applied to the finite-capital ledger; it is not a new decomposition of fees.

### 6.4 Occupancy and overlap

- each funded position occupies its entry notional until its frozen 20-session exit;
- a new signal for an already-held ticker is recorded `OVERLAP_SUPPRESSED_NO_PYRAMIDING`;
- suppressed signals receive zero capital and do not count as executed portfolio trades;
- other tickers may enter only from deployable cash actually available at their next-open entry;
- proceeds from a same-session close exit do not exist at that morning's open and therefore cannot fund that morning's entry;
- close-exit proceeds become available only for a later session;
- positions are never retroactively resized;
- a signal that cannot fund one 1,000-share round lot is recorded as non-executable under the fixed-capital ledger, not silently converted to an odd-lot trade.

### 6.5 Daily equity and drawdown

For reporting maximum drawdown only, open positions are marked to the official daily close.

For each open position, reserve the already-frozen full 40 bp round-trip cost as a liability:

`cost_reserve_i = 0.004 * entry_notional_i`

Daily marked equity:

`marked_equity_t = cash_t + reserve_profit_cash_t + sum_i(shares_i * close_i,t) - sum_i(cost_reserve_i)`

This accounting device does not change the frozen 40 bp trade return; it prevents an open position from appearing cost-free in the drawdown series.

Maximum drawdown is computed from the running peak of `marked_equity_t`.

### 6.6 Portfolio outputs

Every promotion-evaluation window must report:

- initial account equity;
- ending account equity;
- deployable-cap ceiling;
- total net PnL;
- cumulative portfolio return;
- maximum drawdown;
- matured candidate-event count;
- executed trade count;
- distinct executed signal dates;
- `SKIPPED_NOT_EXECUTABLE_CAPITAL` count;
- `OVERLAP_SUPPRESSED_NO_PYRAMIDING` count;
- mean / median / maximum capital utilization;
- zero-deployment session share;
- capital efficiency;
- contemporaneous TAIEX return;
- excess versus TAIEX.

A promotion gate cannot pass if ending equity, cash, position notional, PnL, or any required ledger field is non-finite, or if any session violates the no-leverage / nonnegative-cash constraint.

## 7. New operationalization: exact contemporaneous TAIEX comparison

Classification:
`OPERATIONALIZATION_NEW — TAIEX outperformance was mandatory; exact benchmark geometry was not frozen.`

Benchmark series:
official TAIEX closing index, with no future revisions or substitute proxy.

For any evaluation window `[S, E]`:

`TAIEX_return(S,E) = TAIEX_close(E) / TAIEX_close(previous_TWSE_session_before_S) - 1`

`portfolio_return(S,E) = ending_equity(E) / starting_equity_before_S - 1`

`excess_vs_TAIEX = portfolio_return - TAIEX_return`

Both portfolio and benchmark use the identical calendar window.

Required comparisons:

- latest-3M promotion window;
- Validation window;
- full cross-cycle window when PIT-safe history exists.

For final promotion, all three available promotion-critical windows must satisfy:

`excess_vs_TAIEX > 0`

This is the mechanical form of the inherited `beat contemporaneous TAIEX` hard law. It is not an IF-07-specific hurdle and cannot be replaced by absolute profitability alone.

If the required official TAIEX benchmark series is unavailable or non-verifiable, state = `DATA_BLOCKED`.

## 8. New operationalization: cross-cycle and weak / bear evidence

Classification:
`OPERATIONALIZATION_NEW — 2018–2026H1 cross-cycle and weak/bear evidence were inherited hard requirements; exact promotion mechanics were not globally frozen.`

### 8.1 Coverage

Final promotion requires PIT-safe IF-07 accounting and signal reconstruction covering the obtainable range from:

`2018-01-02 through 2026-06-30`

without backfilled availability timestamps, synthetic accounting fields, reconstructed revision history, or any relaxation of the frozen IF-07 PIT law.

If that cross-cycle PIT accounting cannot be acquired under the frozen IF-07 availability contract, final promotion state = `DATA_BLOCKED`.

No shorter period may be substituted and called cross-cycle PASS.

### 8.2 Full cross-cycle portfolio gate

Using the identical finite-capital ledger in §6 across the full valid cross-cycle panel:

- total net PnL must be `> 0`;
- full-window portfolio return must exceed contemporaneous TAIEX return under §7;
- all required yearly reporting from V0.1 must remain visible;
- no adverse calendar year or regime may be deleted from the report.

This does not require every calendar year to be profitable; no such all-years-positive rule existed in global governance, so this addendum does not invent it.

### 8.3 WEAK and BEAR promotion evidence

Every executed trade in the full cross-cycle portfolio ledger is tagged only by the ex-ante TAIEX signal-date regime from §5.

For each of `WEAK` and `BEAR`, report from the actual full portfolio ledger:

- executed trade count;
- distinct executed signal dates;
- total attributed net PnL;
- gross and net trade-return distribution;
- capital-sessions consumed;
- capital efficiency.

Promotion-critical regime sufficiency requires, separately for WEAK and BEAR:

- executed trades `>= 10`; and
- distinct executed signal dates `>= 5`.

This is a new governance operationalization that reuses the already-frozen latest-3M 10-trade / 5-date sufficiency magnitude instead of inventing a smaller regime-specific threshold after seeing IF-07 outcomes.

If valid cross-cycle data exist but either WEAK or BEAR fails this evidence-count floor, state = `INCONCLUSIVE`, not PASS.

If sufficient WEAK evidence exists, WEAK attributed total net PnL must be `> 0`.

If sufficient BEAR evidence exists, BEAR attributed total net PnL must be `> 0`.

No separate regime-specific Selection filter, threshold retuning, re-ranking, or signal suppression is allowed. Regime is evaluation labeling only.

## 9. New operationalization: lifecycle de-duplication integrity gate

Classification:
`OPERATIONALIZATION_NEW — no lifecycle-duplication artifact was mandatory; exact audit condition was not frozen.`

Candidate authority is not changed.

Before final promotion, verify:

- duplicate `(ticker, fiscal_year, fiscal_quarter)` candidate events = 0;
- a correction / restatement does not create a second tradeable economic event;
- duplicate executed trades from the same frozen event identity = 0;
- pyramided same-ticker overlapping positions = 0;
- every `OVERLAP_SUPPRESSED_NO_PYRAMIDING` record contributes zero additional notional and zero additional trade count;
- same-date multi-name events remain separate tickers but share one date block for inference as already frozen.

If any deterministic duplication violation occurs, promotion state = `FAIL`.

If required event lineage cannot be proven, state = `DATA_BLOCKED`.

## 10. Final promotion decision contract

This contract is evaluation governance only. It grants no automatic Production authority.

### 10.1 `GOVERNANCE_PROMOTION_PASS`

Allowed only if all are true:

1. frozen V0.1 Discovery and Validation contract has produced `RESEARCH_VALIDATION_PASS`;
2. latest-3M gate in §3 = PASS;
3. finite-capital ledger in §6 is valid, with finite ending equity, nonnegative cash, no leverage violation, total net PnL positive, and finite positive capital efficiency;
4. latest-3M portfolio excess versus TAIEX in §7 is positive;
5. Validation portfolio excess versus TAIEX in §7 is positive;
6. full cross-cycle gate in §8 passes with total net PnL positive and full-window excess versus TAIEX positive;
7. WEAK evidence meets 10 executed trades / 5 dates and WEAK attributed total net PnL is positive;
8. BEAR evidence meets 10 executed trades / 5 dates and BEAR attributed total net PnL is positive;
9. lifecycle de-duplication gate in §9 passes;
10. no integrity-lock violation occurred;
11. all mandatory adverse metrics are reported without suppression.

Even then, the state is only:

`GOVERNANCE_PROMOTION_PASS_AWAITING_EXPLICIT_HUMAN_PRODUCTION_AUTHORIZATION`

Trading / Production authority remains `NONE` until a separate explicit human authorization exists.

### 10.2 `FAIL`

Use `FAIL` when required data are valid and sufficient but any deterministic performance / integrity condition above fails, including:

- latest-3M finite-capital PnL `<= 0`;
- latest-3M excess versus TAIEX `<= 0`;
- strong-market latest-3M loss;
- required finite-capital total net PnL `<= 0`;
- Validation excess versus TAIEX `<= 0`;
- full cross-cycle total net PnL `<= 0`;
- full cross-cycle excess versus TAIEX `<= 0`;
- sufficiently sampled WEAK attributed total net PnL `<= 0`;
- sufficiently sampled BEAR attributed total net PnL `<= 0`;
- lifecycle duplicate / pyramiding violation;
- any deterministic integrity-lock violation.

No rescue retuning is allowed after FAIL.

### 10.3 `INCONCLUSIVE`

Use `INCONCLUSIVE` when required data are valid but evidence quantity is insufficient under an already-frozen sufficiency law, including:

- latest-3M executed matured trades `< 10`;
- latest-3M distinct executed signal dates `< 5`;
- WEAK executed trades `< 10` or WEAK distinct executed signal dates `< 5`;
- BEAR executed trades `< 10` or BEAR distinct executed signal dates `< 5`;
- capital efficiency denominator is zero because no capital was deployed.

INCONCLUSIVE is not PASS and does not authorize threshold relaxation.

### 10.4 `DATA_BLOCKED`

Use `DATA_BLOCKED` when required evidence cannot be constructed without violating PIT / provenance law, including:

- PIT-safe 2018–2026H1 accounting availability cannot be obtained;
- official TAIEX benchmark series required for a gate is unavailable or unverifiable;
- lifecycle event identity / revision lineage required for de-duplication cannot be proven.

DATA_BLOCKED is not model FAIL and cannot be converted to PASS by proxy substitution.

## 11. Anti-tailoring / anti-rescue lock

The operationalizations above were frozen while forward returns remained sealed.

Forbidden after unsealing:

- changing 63 sessions to another recent window because IF-07 looks better;
- changing the -20% bear boundary because IF-07 performs poorly in BEAR;
- changing initial capital because a particular IF-07 ticker is expensive;
- changing same-day equal cash allocation because another order would improve PnL;
- changing the inherited 1,000-share round-lot rule, deployable-cap ceiling, cash reuse, overlap suppression, or cost recognition after outcomes;
- changing TAIEX window geometry;
- changing capital-efficiency formula or sign requirement;
- changing cross-cycle dates to remove an adverse year;
- changing WEAK / BEAR requirements because no IF-07 trades occur there;
- creating a new selection filter inside promotion governance.

Any such change requires a separately versioned governance addendum frozen before any newly affected outcome is inspected. It cannot mutate V0.1 or this V0.1 addendum in place.

## 12. Pre-unseal state

At persistence of this addendum:

- `IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1 = FROZEN_UNCHANGED`
- `STAGE_A = PASS`
- `187_CANDIDATE_AUTHORITY = FROZEN`
- `STAGE_B = PREPARED_NOT_EXECUTED`
- `FORWARD_RETURNS = SEALED_NOT_OPENED`
- `VALIDATION = NOT_OPENED`
- `PRODUCTION_TRADING_AUTHORITY = NONE`

This addendum alone does not authorize Stage B or forward-return opening.

The only legal unseal transition requires an explicit later user instruction to execute the frozen Stage B / unseal path.
