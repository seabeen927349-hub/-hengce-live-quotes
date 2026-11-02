# HENGCE Market Environment Observation — S1 PIT Requirement Closure

Date: 2026-11-02 (Asia/Taipei)  
Project: `research/market_state_observation_20261102`  
Authority reviewed at start: research branch `a03a445a1980265845596bc635128e97507c54d1`; main `8780ff04ce0ead8d294fd9eab6f1b0798b60ac1f`  
Canonical repair evidence additionally reconciled from Library: `04A_S2_V1_1_IMPLEMENTATION_REPAIR_AMENDMENT.md`, `08_2026_NUMERIC_PARSER_REPAIR_RECEIPT.md`, `OBSERVATION_MATRIX_MANIFEST_V2.json`  
Status: **S1 REQUIREMENTS CLOSED / PASS WITH NARROWING / 2026 OFFICIAL PRICE+TURNOVER REPAIRED / TRADES FAIL-CLOSED**

## 1. Purpose of this closure

This file does not alter the preregistered observation families and does not add a new measurement because it is convenient or potentially predictive. It closes the explicit PIT questions dimension by dimension:

1. Was the information genuinely observable at the relevant historical time?
2. What is the first-public timestamp or, if not preserved, the conservative safe-use time?
3. Can the historical version be reconstructed completely enough for the frozen quality gate?
4. Can the value revise later?
5. How must missingness be represented?
6. What look-ahead, survivorship, source-version or market-regime contamination remains possible?

No forward return, target label, backtest, threshold tuning, state-return mapping or predictive clustering was inspected or authorized.

## 2. Naming lock: user-facing aliases do not change the preregistration

The frozen preregistration does **not** merge price breadth with ownership participation. To avoid semantic drift:

- `Trend / Direction` maps to frozen **Market Path / Transition**.
- `Breadth` is the price-based breadth component of **Market Path / Transition**.
- `Participation` maps separately to frozen **Participation / Concentration Structure** (ownership/shareholder structure).
- `Flow / Microstructure` maps to frozen **Flow / Price Discovery Structure**, but S1 narrows the historical implementation to official daily investor-class flow where available; full historical aggressive/passive microstructure is not established.
- `External / Derivatives confirmation` remains frozen **External / Derivatives Context**, secondary only.

This mapping is nomenclature only. No family is added, deleted or promoted by this closure.

## 3. Canonical 2026 repair reconciliation

`07_2026_DATA_LINEAGE_REPAIR_DECISION.md` remains valid immutable audit history for the point at which the unlineaged candidate `HENGCE_2026_HIST_MOTHER.csv` was correctly rejected. It is superseded only on its operational conclusion that official 2026 OHLC/volume/turnover were unusable.

The later canonical audit located the official acquisition/audit package under `/HENGCE_CANONICAL/HIST_SOURCE_2018_2026_20261027/`, including `SOURCE_AND_AUDIT.zip` and `TWSE_ELECTRONICS_2026.zip`. The root defect was the V1 parser: comma-formatted official numeric strings were coerced to missing. S2 V1.1 normalizes thousands separators and separates turnover coverage from trade-count coverage. It changes no predictive formula, horizon, quality threshold or anti-leakage rule.

Canonical V2 repair facts:

- 2018–2025 common-field value changes: **0**;
- 2026 event rows: **194**;
- minimum 2026 price coverage: **0.993392070485**;
- minimum 2026 range coverage: **0.995594713656**;
- minimum 2026 turnover coverage: **1.0**;
- 2026 dates below the frozen 95% price gate: **0**;
- 2026 dates below the frozen 95% turnover gate: **0**;
- `ELEC_TRADES_RATIO20` non-null 2026 rows: **0 / 194**;
- `HENGCE_2026_HIST_MOTHER.csv` used in repair: **false**.

Therefore 2026 price-, breadth-, range-, turnover- and price-synchronization families may use the same official archive under the frozen clocks/gates. Trade-count-based liquidity remains `UNKNOWN` in 2026 where the source is genuinely absent.

## 4. Dimension-by-dimension PIT matrix

| Requested dimension / frozen family | Genuinely observable then? | First-public / safe-use clock | Historical reconstruction | Revision risk | UNKNOWN rule | Main contamination risks | S1 verdict |
|---|---|---|---|---|---|---|---|
| **Trend / Direction → Market Path / Transition** | Yes for official daily market/electronics OHLC/date-valued history, but retrospective archive acquisition is not proof of original intraday capture. | Original historical first-seen timestamp is **not preserved**. Historical research uses conservative **next-session-open context** unless a contemporaneous receipt proves earlier availability. | **2018–2026 price core eligible**, subject to frozen row gates. The 2026 official parser repair clears the 95% price gate on all audited 2026 dates. | Derived values inherit upstream source/version corrections. | Required price/reference coverage failure => affected metric `UNKNOWN`; no unlineaged substitute. | Retrospective endpoint mistaken for first-seen; hindsight bull/bear turning points; current membership substituted for historical membership; corporate-action reference errors; unauthorized source substitution. | **FEASIBLE under conservative Clock B**. |
| **Breadth → price breadth inside Market Path / Transition** | Yes when date-correct electronics member returns can be reconstructed. | Clock B; historical first-public timestamp not preserved; conservative next-session-open anchor. | **2018–2026 eligible** subject to the frozen 95% cross-sectional gate and corporate-action/reference availability. 2026 parser repair restores official price coverage above the gate. | Derived breadth inherits upstream corrections/source version. | Coverage `<95%` => breadth `UNKNOWN`; do not compute on an inadequately covered surviving subset. | Current-universe survivorship; listing/delisting hindsight; ex-right/ex-dividend mechanical moves; lowering the gate. | **FEASIBLE with explicit quality gate**. |
| **Participation → Participation / Concentration Structure** | Only on historically versioned ownership/shareholder snapshots whose publication timing is known. | Weekly Clock W. No daily forward-fill. Exact publication time must be attached to each authorized snapshot. | **No continuous 2018–2026 reconstruction currently.** | Later snapshots cannot reconstruct earlier knowledge; bucket/source versions matter. | Missing week/history => `UNKNOWN`; no backward fill or daily forward-fill. | Snapshot survivorship; bucket-definition changes; later ownership used as earlier knowledge; modern/commercial substitution. | **FAILS HISTORICAL PIT as continuous core; bounded/prospective only**. |
| **Volatility / Downside Stress** | Yes for daily past-only return/OHLC families; full historical tick/minute jump structure is not established. | Clock B; conservative next-session-open historical anchor when first-seen timestamps are absent. | **2018–2026 daily price/range families eligible** subject to rolling gates. 2026 minimum price/range coverage remains above 99%. Historical intraday replay is not assumed. | Derived values inherit upstream source corrections. | Rolling-validity or cross-sectional gate failure => `UNKNOWN`; no winsorization/tail deletion to force completeness. | Future-confirmed crash labels; outcome-tuned volatility threshold; synthetic intraday reconstruction; market-design comparability breaks. | **FEASIBLE daily; PARTIAL intraday**. |
| **Liquidity → Liquidity / Market Quality** | Yes for narrowed EOD volume/trading-value/turnover and, where present, trade-count families; no authority for full historical effective spread/depth/aggressive-passive impact. | Clock B; retrospective first-seen timestamp not preserved; conservative next-session-open anchor. | **2018–2026 turnover-based metrics eligible** under field-specific 95% gates. In 2026 turnover coverage is 100%. **Trade-count-based 2026 metrics remain UNKNOWN** because trade counts are genuinely unavailable. | Derived metrics inherit source corrections. EOD last bid/ask is not a full intraday spread history. | Each metric is gated by its own required field. Missing trades do not erase valid turnover metrics; trade metrics stay `UNKNOWN`. | EOD bid/ask promoted to spread; denominator drift; recoupling turnover/trades gates; unlineaged patch; outcome-selected proxy. | **PARTIALLY FEASIBLE, EOD narrowed; 2026 trades fail-closed**. |
| **Flow / Microstructure → Flow / Price Discovery Structure** | Official daily T86 investor-class flow is observable after publication. Full aggressive/passive/order-splitting microstructure is not historically established by T86. | Clock C: **18:00 excluding block trades / 20:00 including block trades** under current authority. | Canonical validated HENGCE T86 mother is clean for **2023–2025** only; longer product existence is not local historical coverage authority. | Product/version corrections possible; publication variant must be fixed. Investor classes remain separate. | Date/member match or frozen 95% flow coverage failure => `UNKNOWN`; never infer missing class from total. | Pre-publication use; smart-money motive; aggressive/passive inference from daily net flow; block-trade product mismatch; identity labels. | **PARTIALLY FEASIBLE; strong 2023–2025 post-close leg**. |
| **Leverage / Short → Leverage / Short Structure** | Yes in principle for official margin, margin-short, SBL and borrowed-stock products, but clocks/revision semantics differ. | Revision-safe Clock D/C. Without preserved provisional snapshots, finalized D credit balance is usable only after D+1 report exposes the corrected previous balance — conservatively **D+2 open or later**. | **Not yet continuous enough for the frozen core.** The parser repair does not authorize margin from the unlineaged candidate mother. | **Material revision risk** for same-day credit balances. | Correct historical vintage not proven at observation time => `UNKNOWN`. | Revision look-ahead; collapsing margin-short/SBL/borrowed stock; denominator/rule drift; using later-corrected balance too early. | **PARTIALLY FEASIBLE / backfill required / revision-safe delay mandatory**. |
| **Attention / Crowding → Attention / Crowding Activation** | Yes for official TWSE attention/disposition incidence after publication; latent fear/FOMO/overconfidence is not observable. | Clock C; commercial attention/disposition file **19:00** under current authority. | Official history exists, but continuous historical sidecar is not yet ingested into the frozen matrix. | List corrections/source updates must be versioned. | Until official-history ingestion and clock validation are complete, fields remain `UNKNOWN`. | Next-day list shifted earlier; Google Trends without vintage audit; psychological labels; current-list survivorship. | **PARTIALLY FEASIBLE, after-close; ingestion pending**. |
| **Industry Synchronization / Diffusion** | Yes for price-based co-movement/dispersion using contemporaneous date-correct electronics returns. Complete historical customer/supplier graph is not established. | Price leg uses Clock B; any future supply-chain sidecar requires its own publication clock. | **2018–2026 price synchronization eligible** subject to frozen rolling/coverage gates after the official parser repair. Complete supply-chain graph: **no**. | Derived synchronization inherits upstream source/universe corrections. | Insufficient rolling observations or coverage failure => `UNKNOWN`; no hindsight edge fill. | Fixed upstream→downstream causality; later-known supplier/customer edges projected backward; industry survivorship; common factor mistaken for causal lead-lag. | **FEASIBLE price synchronization; FAILS complete historical supply-chain PIT**. |
| **External / Derivatives confirmation → External / Derivatives Context** | Potentially yes for TAIFEX/external series, but only with product/session-specific clocks and date attribution. It remains secondary by preregistration. | No single blanket clock. Day/night session, trade date, OI/participant publication time and overseas timestamps must be explicit per field. | Public historical products exist, but the frozen core deliberately defers this sidecar. | Contract specification, session definitions and disclosure staging can change. | Unresolved publication/session/vintage attribution => `UNKNOWN`; never shift night-session information backward. | Night-session look-ahead; timezone/day-boundary errors; contract-roll/version drift; later OI/participant disclosure used early; secondary context promoted to core state. | **SECONDARY_CONTEXT_ONLY / PARTIALLY_FEASIBLE**. |
| **Market-Design Context** | Yes as historically versioned rule metadata. | Effective-date/authority clock per rule record. | Core anchor available: continuous trading effective 2020-03-23. Additional fields require their own authority. | Rule history is versioned. | Unverified effective date => `UNKNOWN` or omit. | Modern rules projected backward; pre/post mechanics treated homogeneous; rule metadata treated as alpha. | **FEASIBLE context metadata**. |

## 5. Anti-contamination closure

S1 is considered closed only under all of the following locks:

- no forward-return discovery;
- no backtest;
- no state-return mapping;
- no performance-selected feature/window;
- no threshold tuning;
- no lowering of 95%/90% quality gates;
- no replacement of UNKNOWN with a modern/revised dataset lacking historical-vintage authority;
- no use of current membership, current supplier/customer maps or current rule definitions as historical truth;
- no use of later-corrected margin values before their revision-safe effective time;
- `HENGCE_2026_HIST_MOTHER.csv` remains unauthorized for the 2026 repair despite numerical completeness.

## 6. S1 final decision

`S1_PIT_DATA_CAPABILITY = PASS_WITH_NARROWING`.

The pass is not a claim that every preregistered dimension is continuously available. It means a defensible multi-clock observation architecture exists, with several dimensions explicitly partial, delayed, sparse or `UNKNOWN`.

The canonical 2026 parser repair removes the false OHLC/volume/turnover blockage without weakening any preregistered quality rule. The remaining major capability gaps are genuine: 2026 trade counts, continuous ownership participation history, revision-safe leverage/short history, official attention-history ingestion, full historical microstructure, complete contemporaneous supply-chain graph, and field-level external/derivatives clock audit.

Predictive work remains unauthorized.