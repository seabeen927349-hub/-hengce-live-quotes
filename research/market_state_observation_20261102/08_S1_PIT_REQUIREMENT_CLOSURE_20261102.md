# HENGCE Market Environment Observation — S1 PIT Requirement Closure

Date: 2026-11-02 (Asia/Taipei)  
Project: `research/market_state_observation_20261102`  
Authority reviewed at start: research branch `a03a445a1980265845596bc635128e97507c54d1`; main `8780ff04ce0ead8d294fd9eab6f1b0798b60ac1f`  
Inputs: `02_PREREGISTRATION_OBSERVATION_LAYER.md`, `03_S1_PIT_DATA_CAPABILITY_AUDIT.md`, `S1_CAPABILITY_AUDIT.json`, `05_S3_OBSERVATION_MATRIX_BUILD_RECEIPT.md`, `07_2026_DATA_LINEAGE_REPAIR_DECISION.md`  
Status: **S1 REQUIREMENTS CLOSED / PASS WITH NARROWING / 2026 CROSS-SECTION FAIL-CLOSED**

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

## 3. Dimension-by-dimension PIT matrix

| Requested dimension / frozen family | Genuinely observable then? | First-public / safe-use clock | Complete historical reconstruction? | Revision risk | UNKNOWN rule | Main contamination risks | S1 verdict |
|---|---|---|---|---|---|---|---|
| **Trend / Direction → Market Path / Transition** | Yes for official daily market/electronics OHLC/date-valued history, but the archive was acquired retrospectively and is not proof of original intraday capture. | Original historical first-seen timestamp is **not preserved**. Conservative use: after the official daily session is complete; for historical reconstruction use **next-session-open context** unless a contemporaneous receipt proves earlier availability. | **2018–2025 core: yes** under the frozen reconstruction path. **2026 electronics cross-section: not consistently**, because the frozen yearly archive is materially incomplete on affected dates. TAIEX-level fields remain usable where present. | Raw official daily values are not treated as revision-free merely because the retrospective endpoint returns one value; source-version metadata must be preserved. | If the date-correct universe or required price/reference coverage fails the frozen gate, affected cross-sectional fields are `UNKNOWN`. Never fill with later mother data lacking lineage. | Retrospective endpoint mistaken for first-seen data; hindsight bull/bear turning points; current membership substituted for historical membership; corporate-action reference errors; 2026 source-lineage substitution. | **FEASIBLE with 2026 narrowing**. |
| **Breadth → price breadth inside Market Path / Transition** | Yes when date-correct electronics member returns can be reconstructed. | Same Clock B rule as price path: historical first-public timestamp not preserved; next-session-open is the conservative historical anchor. | **2018–2025 yes** subject to the frozen 95% cross-sectional gate and corporate-action/reference availability. **2026 affected dates fail closed**. | Derived breadth revises if an upstream stock-day input/source version changes; therefore source version and coverage must be bound to the row. | Coverage `<95%` of the date-correct electronics universe => breadth is `UNKNOWN`, not recomputed on the surviving subset as if complete. | Survivorship from using today's electronics list; delisting/listing hindsight; ex-right/ex-dividend mechanical moves; lowering the coverage gate to retain difficult dates. | **FEASIBLE with explicit quality gate**. |
| **Participation → Participation / Concentration Structure** | Only on actual historically versioned ownership/shareholder snapshots whose publication timing is known. | Weekly Clock W. No daily forward-fill. Exact historical first-public timing must be attached to each authorized snapshot; otherwise unavailable. | **No continuous 2018–2026 reconstruction currently.** Material gaps remain, and current whole-history retrieval attempts are not sufficient authority. | Later ownership snapshots cannot be used to reconstruct earlier knowledge. Dataset rebucketing/version changes must be treated as source-version changes. | Missing week/history => `UNKNOWN`; never carry a later weekly concentration value backward or daily-forward-fill it as if newly observed each day. | Snapshot survivorship, shareholder bucket-definition changes, using later shareholder data as earlier knowledge, silently substituting commercial/current data. | **FAILS HISTORICAL PIT as continuous core; bounded/prospective only**. |
| **Volatility / Downside Stress** | Yes for daily past-only return/OHLC families; not established for full historical tick/minute jump structure. | Daily Clock B, same conservative next-session-open historical anchor when original first-seen timestamps are absent. | **2018–2025 daily families yes** from clean price history; 2026 cross-sectional/electronics-derived fields become `UNKNOWN` where source quality fails. Historical intraday replay is not assumed. | Derived values inherit upstream revisions/source corrections. | Any required rolling input or cross-section failing the frozen validity/coverage rule => `UNKNOWN`. No tail deletion/winsorization to force completeness. | Future-confirmed crash labels; volatility threshold tuned to outcomes; unarchived intraday data reconstructed from later aggregates; market-design comparability breaks. | **FEASIBLE daily; PARTIAL intraday**. |
| **Liquidity → Liquidity / Market Quality** | Yes for EOD volume/trading value/trade count and permitted derived activity/concentration families; no for historical full effective spread/depth/aggressive-passive impact under current authority. | Clock B. Original first-public timestamp of retrospective historical files is not preserved; use conservative next-session-open historical anchor. | **2018–2025 EOD narrowed family yes** where fields meet frozen quality gates. **2026 volume/value/trade fields materially fail on affected dates**, so those metrics are `UNKNOWN`. | Derived liquidity metrics inherit any upstream source correction. EOD last bid/ask cannot be treated as a frozen intraday spread history. | Missing required volume/value/trade inputs or cross-sectional coverage `<95%` => corresponding metric `UNKNOWN`. | Treating EOD bid/ask as historical quoted spread; substituting turnover proxies with changed denominators; silently repairing 2026 from unproven lineage; selection of a prettier liquidity proxy after outcomes. | **PARTIALLY FEASIBLE, EOD narrowed**. |
| **Flow / Microstructure → Flow / Price Discovery Structure** | Official daily T86 investor-class flow is observable after publication. Full aggressive/passive/order-splitting microstructure is **not** historically established by T86. | Clock C: current authority records T86 product at **18:00 excluding block trades / 20:00 including block trades**. A row may use the chosen product only after its product-specific publication clock. | Canonical validated HENGCE mother is clean for **2023–2025** only (not authority for a continuous 2018–2022 history). Longer official product existence does not equal locally reconstructed mother coverage. | A product/version correction is possible; publication product variant must be fixed. Investor classes remain separate. | Date/member match or frozen 95% flow coverage failure => flow metrics `UNKNOWN`; do not infer missing investor class from total. | Using T86 before publication; treating foreign/trust/dealer as one smart-money channel; aggressive/passive inference from daily net flow; block-trade product mismatch; identity/motive labels. | **PARTIALLY FEASIBLE; strong 2023–2025 post-close leg**. |
| **Leverage / Short → Leverage / Short Structure** | Yes in principle for official margin, margin-short, SBL/borrowed-stock products, but their clocks and revision semantics differ. | Revision-safe Clock D/C. Same-day margin/short balance can be adjusted; without preserved provisional snapshots, finalized D credit balance is usable only after the D+1 report publishes the corrected previous balance — conservatively **D+2 open or later**. SBL/other short products keep their own post-close product clocks. | **Not yet continuous enough for the frozen core.** Existing HENGCE margin population/backfill is incomplete; SBL and borrowed-stock selling must remain separate histories. | **Material revision risk** for same-day credit balances; this is the dimension where revision handling is mandatory, not optional. | If the correct vintage cannot be proven for the observation timestamp, field is `UNKNOWN`. Do not use today's corrected retrospective endpoint as if it were known at D+1 open. | Revision look-ahead; collapsing margin-short, borrowed stock and SBL; denominator drift; rule/maintenance changes; using later-corrected balance too early. | **PARTIALLY FEASIBLE / backfill required / revision-safe delay mandatory**. |
| **Attention / Crowding → Attention / Crowding Activation** | Yes for official TWSE attention/disposition incidence after publication; no latent fear/FOMO/overconfidence state is observable. | Clock C. Current authority records commercial attention/disposition file at **19:00**; historical query availability does not prove earlier intraday knowledge. | Official history exists, but the frozen observation matrix has **not yet ingested the continuous historical sidecar**, so current matrix fields remain `UNKNOWN`. | List corrections/source updates must be versioned; derived incidence inherits them. | Until official-history ingestion with release clock and date-correct membership is complete, metrics remain `UNKNOWN`. | Using next day's list earlier; using Google Trends without vintage/scaling audit; psychological labels; current-list survivorship. | **PARTIALLY FEASIBLE, after-close; ingestion pending**. |
| **Industry Synchronization / Diffusion** | Yes for price-based co-movement/dispersion using contemporaneous date-correct electronics returns. Complete historical customer/supplier graph is not established. | Price-based leg uses Clock B and next-session-open conservative historical anchor. Any future supply-chain sidecar would require its own contemporaneous-publication clock. | **2018–2025 price synchronization yes** subject to rolling/coverage gates; 2026 becomes `UNKNOWN` on dates where stock history fails the frozen gate. Complete supply-chain diffusion graph: **no**. | Derived correlation/synchronization inherits upstream source corrections and universe versioning. | Insufficient rolling observations or cross-sectional coverage failure => `UNKNOWN`; no hindsight edge fill. | Fixed upstream→downstream causal ordering; later-known supplier/customer relationships projected backward; current industry membership survivorship; common-factor exposure mistaken for causal lead-lag. | **FEASIBLE price synchronization; FAILS complete historical supply-chain PIT**. |
| **External / Derivatives confirmation → External / Derivatives Context** | Potentially yes for TAIFEX/market external series, but only with product/session-specific clocks and date attribution. It is secondary by preregistration. | No single blanket clock. Day/night session, trade date, OI/participant publication time and overseas-market timestamps must be explicit per field. Until separately audited, historical first-public time is **not blanket-proven**. | Public historical products exist, but the frozen core matrix deliberately defers this sidecar. Therefore it is **not required for core reconstruction** and remains incomplete under current project authority. | Contract specification, session definitions and disclosure staging can change; participant-data semantics are versioned. | If publication/session attribution or source vintage is unresolved, field is `UNKNOWN`; do not shift night-session information backward into the prior day. | Night-session look-ahead, timezone/day-boundary errors, contract-roll/version changes, later OI/participant disclosure used early, external series promoted to define Taiwan state despite secondary status. | **SECONDARY_CONTEXT_ONLY / PARTIALLY FEASIBLE**. |
| **Market-Design Context** | Yes as historically versioned rule metadata. | Effective-date clock; a rule is available no earlier than its effective/announced authority as defined in the rule record. | Core anchor available: continuous trading effective 2020-03-23. Additional rule fields require their own authority before use. | Rules can be amended; version history is the value. | Unverified rule/effective date => field `UNKNOWN` or omitted; never infer regime from later documents. | Comparing pre/post market mechanics as homogeneous; using modern rule definitions backward; treating rule metadata as alpha. | **FEASIBLE context metadata**. |

## 4. 2026 supersedence/narrowing rule

The S1 statement that official yearly electronics archives exist through 2026 is **not** authority to treat every 2026 cross-sectional field as usable. Subsequent deterministic build and descriptive audit found material 2026 missingness in OHLC/volume/trading-value/trade-count fields. The frozen 95% gate therefore controls operational availability.

Effective interpretation from this closure forward:

- `2018–2025`: core EOD market/electronics path, breadth, daily volatility, narrowed liquidity and price synchronization are historically reconstructable subject to row-level gates.
- `2026 TAIEX-level`: usable where the official session series is present.
- `2026 electronics cross-section`: affected fields are `UNKNOWN` unless a new, source-lineage-authorized repair version is created.
- `HENGCE_2026_HIST_MOTHER.csv`: repair candidate only. Numerical completeness does not establish PIT/source lineage.

This narrows operational capability; it does **not** relax any data-quality gate and does not invalidate the frozen schema for clean dates.

## 5. Anti-contamination closure

S1 is considered closed only under all of the following locks:

- no forward-return discovery;
- no backtest;
- no state-return mapping;
- no performance-selected feature/window;
- no threshold tuning;
- no lowering of 95%/90% quality gates to rescue dates;
- no replacement of UNKNOWN with a modern/revised dataset lacking historical-vintage authority;
- no use of current membership, current supplier/customer maps or current rule definitions as historical truth;
- no use of later-corrected margin values before their revision-safe effective time.

## 6. S1 final decision

`S1_PIT_DATA_CAPABILITY = PASS_WITH_NARROWING`.

The pass is **not** a claim that every preregistered dimension is continuously available. It means a defensible multi-clock observation architecture exists, with several dimensions explicitly partial, delayed, sparse or UNKNOWN.

The project remains unauthorized for predictive work. Existing S2/S3/S4 artifacts remain non-predictive historical work; the current active defect is source-lineage reconciliation for 2026 electronics data plus pending attention and leverage/short ingestion.