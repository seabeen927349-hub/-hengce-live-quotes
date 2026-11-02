# HENGCE Market Environment Observation — S2 Schema Freeze

Date: 2026-11-02 (Asia/Taipei)  
Project: `research/market_state_observation_20261102`  
Dependency: `LITERATURE_GATE.json = PASS`; `S1_CAPABILITY_AUDIT.json = PASS_WITH_NARROWING`  
Status: **FROZEN FOR NON-PREDICTIVE HISTORICAL RECONSTRUCTION**

## 1. Purpose
S2 freezes the exact **past-only observation schema** used to describe the contemporaneous Taiwan-equity environment. It does not define market states, labels, scores, trades or future-return hypotheses.

The observation object is a **multi-clock numeric vector plus metadata**. Different dimensions may reference different source event dates because public data are released on different clocks.

## 2. Observation anchor
Historical core snapshots use:

`NEXT_SESSION_OPEN_CONTEXT(t)`

where `t` is a Taiwan trading session open. A field is present only if its `effective_asof_timestamp <= t` under the S1 clock contract. Otherwise it is `UNKNOWN`.

This anchor is descriptive only. It is not an entry time and creates no trading authority.

## 3. Frozen descriptive horizons

`H = {5, 20, 60}` trading sessions.

Interpretation only:
- 5 ≈ one trading week;
- 20 ≈ one trading month;
- 60 ≈ one trading quarter.

These horizons are fixed **before any forward-return inspection**. All three remain in the schema; no later outcome may be used to select the "best" horizon.

## 4. Data-quality gates
These are missingness rules, not alpha thresholds.

- Cross-sectional metric requires valid coverage `>= 95%` of the date-correct electronics universe; otherwise the metric is `UNKNOWN`.
- A stock-level rolling h-session statistic requires at least `ceil(0.90*h)` valid observations in the h-session window; otherwise that stock is excluded from that rolling cross-section.
- No winsorization, clipping or tail deletion is allowed in the observation layer.
- If a required corporate-action reference is unavailable, that stock-day return is `UNKNOWN`; do not substitute the previous close.
- Missing delayed legs remain `UNKNOWN`; no forward-fill except where a source is itself explicitly defined as a carried effective rule regime.

The 95%/90% data-quality gates are frozen now and may not later be changed because of predictive results.

## 5. Corporate-action-safe stock return
For stock `i` on trading date `d`:

`REF(i,d) = official_ex_reference(i,d)` if an official corporate-action record exists for `(i,d)`; otherwise `close(i,d-1)`.

`r(i,d) = ln(close(i,d) / REF(i,d))`

This is a corporate-action-safe **price-path return**, not a total-return claim. Its purpose is to prevent mechanical ex-right/ex-dividend reference changes from masquerading as market stress.

For TAIEX:

`r_mkt(d) = ln(TAIEX(d) / TAIEX(d-1))`

For the date-correct electronics cross-section `U_d`:

`r_elec_ew(d) = mean_i r(i,d)` over valid members of `U_d`, subject to the 95% coverage gate.

## 6. Frozen core metrics

### A. Market Path / Breadth

Market path:
- `TAIEX_R5(d)  = sum_{s=d-4..d} r_mkt(s)`
- `TAIEX_R20(d) = sum last 20 r_mkt`
- `TAIEX_R60(d) = sum last 60 r_mkt`
- `TAIEX_DD60(d) = TAIEX(d) / max(TAIEX over last 60 sessions) - 1`

Electronics equal-weight path:
- `ELEC_EW_R5`, `ELEC_EW_R20`, `ELEC_EW_R60` = rolling sums of `r_elec_ew`.

Daily breadth:
- `ELEC_ADV_DEC_1(d) = (N[r(i,d)>0] - N[r(i,d)<0]) / N_valid`

20-session breadth:
- for each current member `i`, `R20_i(d) = sum of valid r(i,s) over last 20 sessions` if rolling-validity gate passes;
- `ELEC_ADV_DEC_20(d) = (N[R20_i>0] - N[R20_i<0]) / N_valid20`.

Cross-sectional daily dispersion:
- `ELEC_XS_MAD_1(d) = median_i |r(i,d) - median_j r(j,d)|`.

No positive/negative interpretation or state label is attached.

### B. Volatility / Downside Stress

Annualized market realized volatility:
- `TAIEX_RV20(d) = sqrt(252) * sample_std(last 20 r_mkt)`
- `TAIEX_RV60(d) = sqrt(252) * sample_std(last 60 r_mkt)`

Annualized downside semideviation:
- `TAIEX_DOWNSIDE20(d) = sqrt(252) * sqrt(mean(min(r_mkt,0)^2 over last 20))`

Electronics equal-weight realized volatility:
- `ELEC_RV20(d) = sqrt(252) * sample_std(last 20 r_elec_ew)`
- `ELEC_RV60(d) = sqrt(252) * sample_std(last 60 r_elec_ew)`

Cross-sectional intraday range proxy from EOD OHLC:
- `RANGE_i(d) = ln(high_i(d) / low_i(d))` when `high>0` and `low>0`;
- `ELEC_RANGE_MEDIAN_1(d) = median_i RANGE_i(d)` subject to 95% coverage;
- `ELEC_RANGE_MEDIAN_20(d) = mean(last 20 ELEC_RANGE_MEDIAN_1)`.

No volatility threshold or risk-off label is permitted.

### C. Liquidity / Market Quality — EOD narrowed family

Market trading-value activity:
- `MKT_VALUE_RATIO20(d) = market_turnover_ntd(d) / median(market_turnover_ntd over prior/current 20 sessions)`.

Electronics aggregate activity:
- `ELEC_VALUE(d) = sum_i turnover_ntd(i,d)`
- `ELEC_TRADES(d) = sum_i trades(i,d)`
- `ELEC_VALUE_RATIO20(d) = ELEC_VALUE(d) / median(last 20 ELEC_VALUE)`
- `ELEC_TRADES_RATIO20(d) = ELEC_TRADES(d) / median(last 20 ELEC_TRADES)`

Turnover concentration:
- `ELEC_VALUE_TOP10_SHARE(d) = sum turnover_ntd of top 10 electronics names / ELEC_VALUE(d)`.

Historical full effective spread, realized spread, depth and aggressive/passive impact are **not** in this core schema. `last_bid/last_ask` from EOD source archives may not be promoted into a historical full-spread metric without a separate source-timing audit.

### D. Institutional Flow — delayed Clock C
Applicable only where canonical T86 coverage is valid. Primitive investor classes are frozen as:
- Foreign (`ForeignNet`)
- Investment trust (`TrustNet`)
- Dealer aggregate (`DealerNet`)

`TotalNet` is never an independent fourth channel.

For investor class `k` on date `d`:
- `FLOW_NET_VOL_SHARE_k(d) = sum_i NetShares_k(i,d) / sum_i volume_shares(i,d)` over matched date-correct electronics members;
- `FLOW_BREADTH_k(d) = (N[NetShares_k>0] - N[NetShares_k<0]) / N_matched`;
- `FLOW_NET_VOL_SHARE_k_MA5(d) = mean(last 5 available daily FLOW_NET_VOL_SHARE_k)`;
- `FLOW_NET_VOL_SHARE_k_MA20(d) = mean(last 20 available daily FLOW_NET_VOL_SHARE_k)`.

T86 publication clock governs availability. No smart-money label, no causal motive and no aggressive/passive interpretation.

### E. Leverage / Short — revision-safe delayed family
This family remains `UNKNOWN` until a clean historical backfill/versioning path exists for the requested date.

Margin financing and margin short are separate.

For finalized margin balance `MB(d)`:
- `MARGIN_BAL_LOGCHG5(d)  = ln((1+sum MB_i(d))/(1+sum MB_i(d-5)))`
- `MARGIN_BAL_LOGCHG20(d) = ln((1+sum MB_i(d))/(1+sum MB_i(d-20)))`
- `MARGIN_BAL_BREADTH_1(d) = (N[MB_i(d)-MB_i(prev)>0] - N[...<0]) / N_valid`

For finalized margin-short balance `MS(d)`, define the same three metrics with prefix `MSHORT_`.

Revision-safe rule:
- absent an archived original provisional snapshot, finalized D credit balance is not available to an open-context vector earlier than D+2 open.

Securities lending / borrowed-stock selling, when acquired, must be separate fields and may never be collapsed into margin-short or margin-financing metrics.

### F. Industry Synchronization / Diffusion — price-only core
No supply-chain graph is required.

For each stock i and date s, define leave-one-out electronics return:

`r_elec_minus_i(s) = mean_{j in U_s, j != i} r(j,s)`.

For fixed horizon h in `{20,60}`:
- `CORR_i,h(d) = PearsonCorr(r(i,s), r_elec_minus_i(s))` over the last h sessions if the 90% rolling-validity gate passes;
- `ELEC_SYNC20(d) = median_i CORR_i,20(d)`;
- `ELEC_SYNC60(d) = median_i CORR_i,60(d)`.

These measure price synchronization only. They do not identify causal lead-lag, supply-chain direction or information source.

### G. Attention / Crowding — delayed Clock C
Using official TWSE attention/disposition lists only:
- `ATTENTION_SHARE(d) = N[current electronics members on attention list] / N(U_d)`;
- `DISPOSITION_SHARE(d) = N[current electronics members on disposition list] / N(U_d)`;
- `ATTENTION_SHARE_MA5(d) = mean(last 5 ATTENTION_SHARE)`;
- `DISPOSITION_SHARE_MA5(d) = mean(last 5 DISPOSITION_SHARE)`.

These are market-activity/crowding observations only. They are not fear, FOMO, overconfidence or investor-intent measures.

## 7. Sparse / metadata-only dimensions

### H. Ownership / Participation Concentration
Not part of the continuous daily core because historical TDCC coverage is incomplete.

If an actual PIT-authorized weekly snapshot is available at the observation timestamp, it may be attached as a sparse sidecar. It is never daily forward-filled. No numeric TDCC field is required for S2 core reconstruction.

### I. Market-Design Context
Categorical effective-date metadata only. Minimum frozen field:
- `MATCHING_REGIME = CALL_OR_BATCH` before 2020-03-23;
- `MATCHING_REGIME = CONTINUOUS` on/after 2020-03-23.

Additional rule-version fields require separate authoritative effective-date evidence before addition. Market-design fields are context, never alpha signals.

### J. External / Derivatives Context
Deferred to a secondary sidecar acquisition stage. No external/derivatives field is required for the core historical observation matrix. This prevents the core from being blocked by heterogeneous day/night-session history and avoids promoting thinner literature evidence into a state-defining variable.

## 8. Row-level output schema
Every historical snapshot row must contain at least:

- `observation_timestamp`
- `market_event_date`
- all available frozen core metrics
- `core_price_effective_asof`
- `flow_event_date`, `flow_effective_asof`, `flow_age_sessions`
- `margin_event_date`, `margin_effective_asof`, `margin_age_sessions`
- `attention_event_date`, `attention_effective_asof`, `attention_age_sessions`
- `tdcc_snapshot_date`, `tdcc_effective_asof`, `tdcc_age_sessions` if present
- `matching_regime`
- per-family `coverage_ratio`
- per-family `reconstruction_class`
- per-family `missingness_reason`

## 9. Forbidden columns
The observation matrix must not contain:

- forward return of any horizon;
- future drawdown;
- future volatility;
- target label;
- hit/win/loss;
- alpha;
- P&L;
- buy/sell/hold action;
- stock rank;
- optimized cluster/state label;
- performance-selected feature or window.

## 10. Freeze rule
After this S2 freeze, formulas, horizons and missingness gates may change only for a documented **data/definition defect discovered without inspecting future outcomes**. Any such change creates a new schema version with supersedence notes. Predictive performance is never a valid reason to alter S2.

## 11. Authority consequence
S2 authorizes a deterministic **historical environment observation matrix builder** only.

It does not authorize state clustering/classification, thresholding, forward-return testing, Selection Core interaction tests, backtests, tuning or promotion.
