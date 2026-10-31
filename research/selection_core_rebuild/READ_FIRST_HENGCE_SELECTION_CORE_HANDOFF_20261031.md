# HENGCE Selection Core Rebuild — New Chat Handoff
Date: 2026-10-31
Language: Traditional Chinese only
Status: `BASELINE_NULL_LOCKED_CHALLENGER_NOT_YET_DEFINED`
Trading / production authority: `NONE`

## Start here
Do not restart the project. Do not ask the user to redefine the universe. Do not revive V6/V43 as the new core.

Suggested first user command:
`繼續衡策 Selection Core rebuild。先讀這個 handoff；不要回到 V6/V43，不要偷看新候選 forward return。從真正正交資訊家族的 capability / novelty gate 繼續。`

## Frozen universe and hard validation law
- Universe: `TWSE_LISTED_ELECTRONICS_PIT_DAILY`
- TWSE listed electronics only; TPEx/OTC excluded; signal-date PIT membership.
- Latest 3M: total PnL must be > 0; strong-market latest-3M loss = KILL; sufficient actual trades required; report trade count/frequency/capital efficiency.
- Long-term: multiple cycles ~2018-2026, weak/bear periods, beat contemporaneous TAIEX, finite-capital portfolio accounting.
- Event means alone cannot promote.
- Signal after close; entry next open; current Selection rebuild baseline cost = 40bp round trip; explicit overlap rules; no lookahead/revision leakage.

## Governance lock
Permanent rules:
- NO silent mutation.
- NO threshold retuning in place.
- NO post-hoc winner-aware tuning.
- Every challenger must be separately versioned and preregistered BEFORE forward-return testing.
- Failed challenger = KILL; no rescue tweaks.
- Selection Core, Escape Overlay, Execution are separate.
- Legal states: PASS / FAIL / INCONCLUSIVE / DATA_BLOCKED.
- Truthful failure is valid; fabricated success is governance failure.
- Escape overlay has zero Selection authority.

Library authority artifacts:
- `/HENGCE/Research Outputs/SELECTION_CORE_REBUILD/HENGCE_RESEARCH_INTEGRITY_LOCK_V1_20261031.json`
- `/HENGCE/Research Outputs/SELECTION_CORE_REBUILD/HENGCE_SELECTION_CORE_REBUILD_STATE_V2_20261031.json`
- `/HENGCE/Research Outputs/SELECTION_CORE_REBUILD/HENGCE_SELECTION_CORE_NULL_BASELINE_CONTRACT_V1_20261031.json`

Current state:
- `V2_20261031_BASELINE_NULL_LOCKED`
- `BASELINE_NULL_LOCKED_CHALLENGER_NOT_YET_DEFINED`
- challenger = `NOT_YET_DEFINED`
- trading authority = `NONE`
- Escape v2.4.7 frozen unchanged; risk overlay only.

Prohibitions:
- `NO_RESCUE_TUNING_OF_FROZEN_PARENTS`
- `NO_FEATURE_SALVAGE_FROM_PARENT_WITHOUT_NEW_HYPOTHESIS`
- `NO_ESCAPE_ALPHA_INJECTION`
- `NO_PRODUCTION_PROMOTION`

## Null baseline contract
Horizons: 5 / 10 / 20 / 40 / 60 sessions.

Nulls:
- N0 equal-weight eligible cross-section.
- N1 prior20 momentum TopK.
- N2 prior5 reversal BottomK.
- N3 matched random; seed 20261031; 10,000 draws.

Pair same date / same eligible universe / same k / same cost and entry convention / fail closed.
Required reporting includes event count, unique tickers, signal-date count, monthly frequency, mean/median/win, remove-best 1/3/5, MAE/MFE, date-block excess vs N0/N1, bootstrap CI, latest3M, yearly and regime splits.

## Frozen legacy parents
- CONTROL / RETAIL V0.11.1: `REJECT_SELECTION_CORE`; allowed role `FROZEN_LIFECYCLE_EXIT_BENCHMARK_ONLY`.
- MONSTER BUY V1: `REJECT_CORE_CHAMPION`; allowed role `FROZEN_LONG_HORIZON_EVENT_BENCHMARK_ONLY`.
- V1-V43 lineage: `EXPOSED_HISTORICAL_REFERENCE_ONLY`; not pristine OOS; no Selection authority.

## V6 exact novelty-reference recovered
Important: this does NOT revive V6.

Immutable legacy snapshot commit: `b5e53bc459d216958893c6b0fd28eb6f5ab8c70f`.

V6 factor space and fixed weights:
1. `resid_rev` = 0.20
2. `mom20` = 0.25
3. `skip5_60` = 0.30
4. `liquidity` = 0.05
5. `lowvol` = 0.20

Exact V13 feature construction:
- `resid_rev = rank(-resid5)`
- `mom20 = rank(r20)`
- `skip5_60 = rank(r60-r5)`
- `liquidity = rank(turn20)`
- `lowvol = rank(-vol20)`
- `turn20` = stock 20-session mean trading value.
- eligibility included `turn20 >= NT$20m`.

V41/V43 still live inside this five-factor information space: V41 uses signal-time expanding same-regime prior-only mean-IC learning; V43 switches the statistic to ICIR; both shrink 90% toward V6 weights. Therefore they are historical references, not a new information family.

## Capital-share migration draft — killed before any forward-return test
Research-only branch: `research/selection-core-rebuild-20261031`.
Frozen novelty verdict commit: `d0c9c95ce5290289f35d51189b995a89e8455ff2`.
Frozen file: `research/selection_core_rebuild/HENGCE_CAPITAL_SHARE_MIGRATION_NOVELTY_GATE_20261031.md`.

Decision:
`CROSS_STOCK_CAPITAL_SHARE_MIGRATION_DRAFT = NOVELTY_GATE_FAIL`

Governance facts:
- forward-return test executed: NO
- challenger preregistered: NO
- rescue tuning allowed: NO

Mathematical reason:
`share(i,t) = turnover(i,t) / sum_j turnover(j,t)`.
Within the same date the denominator is common, so `rank_i(share(i,t)) = rank_i(turnover(i,t))`.
For a fixed lookback L, share growth is individual turnover growth divided by a common market-turnover growth term; its cross-sectional rank is therefore still a turnover-growth transform.

Conclusion:
- capital-share LEVEL is duplicate of turnover/liquidity rank;
- share growth/persistence remains in the same Volume/Liquidity family;
- do NOT rescue via alternate lookbacks, persistence counts, percentiles or normalizations.

## Graveyard evidence that controls this decision
R-017 `Liquidity-adjusted Price Impact Collapse v0.1` already tested turnover shock (`turnover / ADV20`) with price state. Raw bull-side results looked strong, but after controlling same-day ret1 rank, ret20 rank, turnover-shock rank and liquidity rank, monotonicity disappeared in discovery and validation; bear-side absorption was non-monotonic.
Frozen decision: `KILL AS INCREMENTAL ENGINE / CONTEXT ONLY`.

Research information-family registry:
- IF-01 Price = existing/highly correlated family.
- IF-02 Volume/Liquidity = volume, turnover, ADV, liquidity percentile; existing family; hard-gate thesis killed/context-capacity.
- IF-03 Margin = context unless genuinely new mechanism.
- IF-04 Institutional Flow = simple activation variants killed/context unless new microstructure mechanism.
- Priority orthogonal families: Fundamental Quality, Expectation Revision, firm-network/supply-chain Lead-Lag, Structured Corporate Events.

## Data capability state
Canonical mother: `/HENGCE_CANONICAL/HENGCE_2026_HIST_MOTHER.csv`.
- price backfill earliest 2018-01-02 through 2026.
- missing backfilled non-price fields stay NULL; no synthesis.

Historical institutional sidecar: `TWSE_2023_2025_mother.csv`.
- T86 institutional coverage ~97-98% and audited.
- margin history incomplete; do not fabricate.

TDCC:
- strongest in 2026.
- historical bulk gaps include 2018 and 2022-2025.
- do not claim full 2018-2026 ownership coverage.

Fugle:
- authorized augmentation/verification source.
- realtime quote retrieval has worked.
- correctly parameterized historical/content calls across several specs have returned empty results.
- legal state: `FUGLE_HISTORICAL_CONTENT_PATH = DATA_BLOCKED`.
- this is connector retrieval blocked for those paths, NOT proof the provider/account has no historical data.

Broker microstructure:
- broker branch / broker concentration-Gini / aggressive prints / best-five depth-microprice are potentially orthogonal.
- existing Library/GitHub did not supply verifiable historical broker-branch/Gini assets; Fugle content path currently blocked.
- state: `BROKER_MICROSTRUCTURE_CONTROL = DATA_BLOCKED`, NOT hypothesis FAIL.

## Other research lanes
### Earnings Quality R-014
State: `INCONCLUSIVE`.
2026-only diagnostic was right-tail dependent; no promotion.
Next legal requirement is a filing-date-aware quarterly panel ~2023-2026 with CFO/revenue, receivables, inventory, gross/op margin, assets/liabilities, capex/FCF where available. Discovery 2023-24; validation 2025-26. Confirm the panel actually exists before testing.

### R-019 Pressure-Response Sensitivity Change
Role: Activation/turning-point research only.
Requires genuine aggressive-trade prints + best-five quote depth/microprice. Cannot be historically reconstructed from 1-minute bars. Predictive power UNKNOWN. Prospective collection only. No Selection authority.

## NEXT LEGAL RESEARCH STEP
Current challenger remains `NOT_YET_DEFINED`.

Do NOT:
- return to V6/V43;
- rescue capital-share migration;
- create another price/volume transform and call it smart-money alpha;
- inject Escape into Selection;
- inspect a new candidate's forward returns before preregistration.

Do:
1. inventory genuinely orthogonal Selection information families and their PIT data capability;
2. prioritize: A) Earnings Quality if filing-date-aware historical panel is proven available; B) genuine expectation revisions if a true consensus/revision source exists; C) firm-level supply-chain/customer-vendor lead-lag with PIT relationship map; D) structured corporate events with exact event-time timestamps;
3. run a NOVELTY GATE against the research ledger/graveyard BEFORE defining a challenger;
4. if novel and data-capable, write one frozen preregistration and verify persistence;
5. only then open forward returns;
6. compare against N0/N1/N2/N3, and later require latest3M + trade frequency + finite-capital portfolio + TAIEX + cross-cycle gates.

If every orthogonal lane is unavailable, state `DATA_BLOCKED`; do not fall back to another Price/Volume retuning exercise.

## Architecture boundary
Layer 1: Selection Core — rebuild underway, challenger undefined.
Layer 2: Escape / Market Risk Overlay — HENGCE v2.4.7 frozen.
Layer 3: Execution — separate.
Escape has no Selection authority.

## Truthfulness discipline
- Missing pull/file = unavailable or DATA_BLOCKED; never infer success.
- Never fabricate historical coverage.
- Data acquisition failure is not hypothesis failure.
- Draft is not preregistered unless persistence is confirmed.
- Do not reverse-engineer thresholds from exposed familiar winners.
