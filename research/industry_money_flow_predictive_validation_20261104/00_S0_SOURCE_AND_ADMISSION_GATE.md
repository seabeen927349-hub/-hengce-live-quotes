# HENGCE — FinMind Industry Chain Money Flow: S0 Source Audit & Admission Gate

Date: 2026-11-04 (Asia/Taipei)
Branch: `research/selection-challenge-20261102`
Authority: RESEARCH_GOVERNANCE_ONLY; NO MODEL / MOTHER / TRADING AUTHORITY.
Decision: `SOURCE_REVIEWED_PIT_BLOCKED_PREDICTIVE_RELATION_UNESTABLISHED`
Research-branch head checked before recording: `ea954a5b70b02562b17768c023669c91699ae5df`.

## User's binding admission requirement

The dataset `TaiwanStockIndustryChainMoneyFlow` **must not enter the HENGCE canonical mother, formal Selection Core, live scoring, signals or weighting** unless a properly preregistered and no-lookahead evaluation establishes a stable, economically meaningful incremental relation with *future* stock prices or date-correct stock returns, followed by untouched out-of-sample/prospective confirmation. Mere contemporary price association, an in-sample Pearson correlation, or a statistical-significance-only result does not qualify. Failure, null results, data unavailability and prohibitions must be recorded, not repaired by unregistered retuning.

This file is a **governance/source-audit record only**, not a feature proposal, predictive preregistration, test authorization or empirical result. No forward stock return or P&L has been opened for this dataset here.

## Verified vendor data contract (FinMind official llms-full.txt, reviewed 2026-11-04)

- Dataset: `TaiwanStockIndustryChainMoneyFlow`; advertised tier Sponsor.
- API: `GET /api/v4/data` with `dataset=TaiwanStockIndustryChainMoneyFlow&start_date=YYYY-MM-DD`, **one date per request**, omit `data_id` and `end_date`.
- Fields: date, industry, sub_industry, stock_count, trading_volume, trading_money, trading_money_pct.
- `sub_industry=""` denotes industry-chain total; one company can belong to multiple subindustries/chains, hence summing subindustry or chain percentages can double-count.
- **Historical values use the present-day industry-chain classification.** Historical publication-versioning and first-public timestamp of this derived dataset are **not verified**. This creates classification look-ahead risk. A paid account is asserted by the user but specific live API entitlement/token execution was not tested by this audit.
- Source: https://finmind.github.io/tutor/TaiwanMarket/Chip/

## Existing HENGCE research constraints (checked)

1. `research/industry_supply_chain_lead_lag_20261103/01_S1_INDUSTRY_CLASSIFICATION_RECOVERY_AUDIT_20261103.json`: historical industry classification `RECOVERABLE_BUT_NOT_PIT_CLEARED`; forward outcomes sealed.
2. `research/industry_supply_chain_lead_lag_20261103/02_S1_OFFICIAL_PIT_SOURCE_PATH_VERIFIED_20261103.json`: official **TWSE electronic-industry** same-date membership and categories (MI_INDEX type 13 and 24–31) source path verified; actual complete history/coverage not yet built or cleared; outcome gate closed.
3. `research/industry_supply_chain_lead_lag_20261103/00_S1_PIT_DATA_FEASIBILITY_AUDIT_20261103.json`: true directed firm-to-firm supply-chain network remains separately data-blocked.
4. The TWSE official electronic-industry category hierarchy is **not equivalent** to FinMind's multi-membership industry-chain taxonomy. It may support a separate, explicitly labelled PIT electronics-industry turnover study; it may **never** be silently substituted for the exact FinMind product.

## Ordered gates (do not skip)

- **S0 DATA / AUTHORIZATION:** Confirm actual account endpoint response and allowable private use, retrieve source metadata, sample rows and documented availability timing without viewing future target returns. Do not put credentials/raw licensed data into public git.
- **S1 PIT / RECONSTRUCTION:** For the **exact FinMind industry-chain family**, obtain contemporaneous historical member/vintage mapping with effective dates and publication time, OR start genuinely prospective daily as-of snapshots and accumulate future observations. Current-taxonomy backcasts are not PIT-valid. If these conditions cannot be met, status remains DATA_BLOCKED. A distinct TWSE time-correct industry-sector family may follow its preexisting S1 audit; do not confuse family identities.
- **S2 LITERATURE / PREREGISTRATION:** Establish this candidate family's own literature and governance gate. Before opening any candidate forward outcome, freeze the research universe, date-correct industry-member mapping, feature formulas, timestamp/latency rule, signal dates, target definition and horizons, exclusion rules, baselines, inference, multiple-test correction, held-out temporal splits, success/failure thresholds, cost model and economic relevance. Until S2 is formally authorized, forward stock returns stay sealed. Existing broad P1 saturation does not itself authorize this new candidate test.
- **S3 FALSIFICATION / PRICE RELEVANCE:** Once authorized, estimate whether an as-of industry turnover-share change/concentration/diffusion measure contains information about **subsequent** date-correct stock and industry **excess** returns, above price-momentum/volume/market-state baselines. Prevent same-day target leakage; assume next trading session earliest usability until actual publication timing is established. Account for overlapping holding horizons and multiple comparisons. Record negative results.
- **S4 OOS / PROSPECTIVE:** Confirm sign stability, meaningful incremental lift, robustness to taxonomy/constituent changes, and implementation timing/cost on genuinely unseen data. Only independent governance approval following this gate can propose promotion to a production module.

## Immediate status

- Vendor offers the dataset: `DOCUMENTED`.
- Subscriber says it is paid for: `USER_REPORTED`, not token-proven here.
- Exact FinMind historical taxonomy PIT replay: `NOT_VERIFIED`.
- Predictive stock-price association: `NOT_TESTED`; do **not** report a correlation coefficient.
- Incremental price prediction and economic utility: `NOT_ESTABLISHED`.
- Canonical mother / Selection Core / live trading use: `DENIED`.
- Next permitted action: narrow S0 entitlement/response audit and S1 exact taxonomy-vintage/PIT feasibility; no target leakage.

This is a constraint, not a promise of a profitable result.
