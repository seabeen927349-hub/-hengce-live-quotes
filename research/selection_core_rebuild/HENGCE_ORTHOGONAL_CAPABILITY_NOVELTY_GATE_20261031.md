# HENGCE Selection Core Rebuild — Orthogonal Information Family Capability + Novelty Gate

Date: 2026-10-31
Branch: `research/selection-core-rebuild-20261031`
Scope: Selection Core research only
Trading / production authority: `NONE`
Forward-return inspection for any new challenger in this gate: `NO`
Challenger preregistered: `NO`
Challenger status after this gate: `NOT_YET_DEFINED`

## Governance lock carried forward

This gate is performed before any new-candidate forward-return test.

Permanent prohibitions remain active:
- do not revive V6/V43 as the new core;
- do not rescue, re-window, re-normalize, or otherwise retune the killed cross-stock capital-share migration draft;
- do not repackage another Price / Volume-Liquidity transform as a new smart-money family;
- do not inject Escape v2.4.7 into Selection;
- do not inspect a new challenger’s forward returns before a separately versioned preregistration is persisted and re-read.

Frozen universe remains `TWSE_LISTED_ELECTRONICS_PIT_DAILY`.

## Evidence inventory performed in this gate

### 1. Canonical mother corpus

`HENGCE_2026_HIST_MOTHER.csv` was inspected directly.

Observed columns:
`Date, Ticker, Name, Volume, Turnover, Open, High, Low, Close, Margin_MarginBalance, ForeignNet, TrustNet, TotalNet`.

Consequence:
- the canonical mother contains Price, Volume/Liquidity, Margin and Institutional Flow;
- it does **not** contain quarterly OCF/CFO, receivables, inventory, gross margin, operating margin, total assets, total liabilities, capex/FCF, analyst consensus/revisions, customer-vendor relationship maps, or structured corporate-event timestamps;
- therefore use of an authorized augmentation source for the orthogonal families below is legal under the research-integrity lock.

### 2. Library research ledger / graveyard

The latest available research ledger family registry classifies:
- IF-07 Fundamental Quality = potentially low correlation; priority orthogonal family; data needed;
- IF-08 Expectation Revision = potentially low correlation; genuine expectation data required, no price proxy;
- IF-09 Industry/Supply-chain Lead-Lag = potentially low correlation; priority for Selection/Activation;
- IF-10 Corporate Events = potentially low correlation; candidate Activation family.

Existing graveyard controls remain binding:
- R-011 / R-012 kill broad industry / peer-average lead-lag as a substitute for a real firm relationship graph;
- R-013 kills simple revenue acceleration / second-derivative retuning;
- R-014 Earnings Quality is only a 2026 diagnostic and is `INCONCLUSIVE`; the attractive 10D mean was right-tail dependent and dominated by one name, so it has no promotion authority;
- R-017 kills turnover-shock / liquidity-impact style incremental engines after controls.

### 3. Fugle paid capability audit

`list_content_specs` on 2026-10-31 exposed accessible financial content families including:
- `FCNT000091` 最近N年損益表
- `FCNT000092` 最近N年現金流量表
- `FCNT000093` 最近N年資產負債表
- `FCNT000047/048/052/066` gross-profit / operating-profit / gross-margin / operating-margin history
- `FCNT000141` receivable turnover history
- `FCNT000143` inventory turnover history
- `FCNT000146` operating cash-flow history
- `FCNT000149` capex history

Retrieval probes performed through the connector:
- symbol `2330`, `FCNT000091`, params `{symbol_id: 2330, years: 4}` -> `{}`
- symbol `2330`, `FCNT000052`, params `{symbol_id: 2330}` -> `{}`
- symbol `2330`, `FCNT000001` basic profile, params `{symbol_id: 2330}` -> `{}`

Interpretation:
- the connector exposes the specifications but the content retrieval path is currently returning empty payloads even for basic data;
- this is `CONNECTOR_RETRIEVAL_BLOCKED`, **not** evidence that Fugle or the paid account lacks the underlying history;
- no returned coverage may be invented.

### 4. Official-source capability audit

Verified on 2026-10-31:
- TWSE OpenAPI documents listed-company financial-statement endpoints including comprehensive income and balance sheet tables;
- the live `上市公司綜合損益表(一般業)` payload includes `出表日期`, fiscal year, quarter, company code/name, revenue, cost, gross profit, operating expenses, operating profit and EPS;
- TWSE OpenAPI also documents `上市公司每日重大訊息`;
- MOPS exposes financial-report sections and both current and historical material-information search interfaces; current material-information listings visibly include company code/name, publication time and subject;
- Securities and Exchange Act Article 36 requires Q1/Q2/Q3 financial reports within 45 days after quarter-end and annual financial reports within three months after fiscal year-end.

Important limitations:
- `出表日期` in the live TWSE OpenAPI table is the table output date and is **not** sufficient proof of each company’s actual filing timestamp;
- a historical bulk quarterly-statement acquisition path with company-specific filing/availability timestamps has not yet been verified and persisted in HENGCE;
- a historical bulk material-event panel with stable taxonomy, deduplication and revision handling has not yet been persisted in HENGCE;
- therefore neither IF-07 nor IF-10 is data-capability PASS yet.

## Family-by-family gate

### IF-07 — Fundamental Quality / Earnings Quality

Novelty verdict: `PASS`

Reason:
- OCF conversion, receivable quality, inventory quality, margin structure and balance-sheet quality are not algebraic transforms of Price, Volume/Liquidity, Margin financing balance, or simple institutional flow;
- this family is explicitly preserved by the research ledger as a priority orthogonal family after R-013/R-014.

Data-capability verdict: `INCONCLUSIVE`

Why not PASS yet:
- required fields have credible source families in Fugle and official financial-report infrastructure;
- however a reproducible 2023-2026 company-quarter panel with a verified `filing_date` or defensible `availability_date` has not yet been persisted and re-read;
- Fugle connector retrieval is currently blocked;
- current official OpenAPI snapshots alone do not establish historical company-specific availability time.

Legal next action for IF-07:
1. identify and verify an official historical quarterly-statement acquisition path for 2023-2026;
2. retain company-quarter, report period, source provenance and revision/version handling;
3. acquire actual filing/announcement timestamp where possible;
4. if actual filing timestamp cannot be acquired, do **not** silently substitute quarter-end. A conservative statutory-deadline availability convention may only be used if separately frozen in the preregistration before any forward-return test;
5. verify fields required by the frozen R-014 acquisition contract: OCF/CFO, CFO/revenue, receivables and growth, inventory and growth, gross margin, operating margin, assets, liabilities, capex/FCF where available.

Status consequence: no challenger yet.

### IF-08 — Genuine Expectation Revision

Novelty verdict: `PASS`

Reason:
- true analyst consensus / estimate revisions are a distinct information source from realized price/volume/fundamentals.

Data-capability verdict: `DATA_BLOCKED`

Evidence:
- canonical mother has no consensus/revision fields;
- current HENGCE Library inventory contains no verified PIT analyst-consensus history;
- current Fugle accessible content-spec inventory does not expose a genuine analyst-consensus / historical revision series suitable for this test.

Permanent rule:
- price momentum, target-price summaries without revision history, or realized EPS/revenue must not be substituted and called “expectation revision.”

### IF-09 — Firm-level Supply-chain / Customer-Vendor Lead-Lag

Novelty verdict: `PASS`

Reason:
- true relationship-level information transmission can be orthogonal to the killed broad-industry peer-average constructions.

Data-capability verdict: `DATA_BLOCKED`

Evidence:
- canonical mother contains no firm relationship graph;
- no defensible PIT customer-vendor relationship map was found in the current HENGCE Library capability inventory;
- Fugle content-spec inventory does not expose such a relationship graph.

Permanent rule:
- industry classification, value-chain labels, or broad peer averages do not satisfy this requirement and cannot revive R-011/R-012 under a new name.

### IF-10 — Structured Corporate Events

Novelty verdict: `PASS`

Reason:
- timestamped corporate actions / material events are discrete causal information and are not a transform of the existing Price / Volume / Flow families.

Data-capability verdict: `INCONCLUSIVE`

Positive evidence:
- TWSE OpenAPI documents listed-company daily material-information data;
- MOPS visibly exposes historical material-information search and publication time in current material-information listings.

Remaining blocker:
- a reproducible 2023-2026 historical bulk event panel with stable event taxonomy, exact event-time handling, deduplication and revision handling has not yet been persisted and re-read inside HENGCE.

Legal next action:
- acquire and freeze the raw event panel first;
- define event taxonomy without looking at subsequent returns;
- only then may a separately versioned structured-event challenger be preregistered.

## Overall decision

`ORTHOGONAL_INFORMATION_FAMILY_GATE = PASS_WITH_DATA_ACQUISITION_BLOCKERS`

This is **not** a challenger PASS.

Current Selection Core state remains:
- phase: `BASELINE_NULL_LOCKED_CHALLENGER_NOT_YET_DEFINED`
- challenger: `NOT_YET_DEFINED`
- trading authority: `NONE`
- production promotion: `NO`
- new-candidate forward return inspected: `NO`

Priority after this gate:
1. IF-07 Earnings Quality — highest priority because novelty passes and credible source families exist, but historical PIT availability must be proven first;
2. IF-10 Structured Corporate Events — second acquisition lane because timestamped official event infrastructure exists, but historical bulk persistence/taxonomy is not yet locked;
3. IF-08 Expectation Revision — remain `DATA_BLOCKED` until a genuine consensus/revision source exists;
4. IF-09 firm-network Lead-Lag — remain `DATA_BLOCKED` until a defensible firm-level relationship map exists.

## Next legal step

`ACQUIRE_AND_FREEZE_PIT_INPUT_PANEL_BEFORE_CHALLENGER_PREREGISTRATION`

Specifically:
- first verify and acquire IF-07 historical quarterly statements plus a defensible availability-time panel;
- if the required PIT timing cannot be made reproducible, record `DATA_BLOCKED` or `INCONCLUSIVE` and do not manufacture a challenger;
- only after one orthogonal family is both novel and data-capable may a challenger definition be written;
- persist and re-read that preregistration before any 5/10/20/40/60-session forward-return calculation or any null comparison.
