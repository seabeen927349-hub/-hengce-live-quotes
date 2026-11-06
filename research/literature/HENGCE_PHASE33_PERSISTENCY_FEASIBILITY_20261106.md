# 衡策 Phase33 — literature-first persistence method and mother capability audit
Date: 2026-11-06 (Asia/Taipei) | Status: **LITERATURE_REVIEW_ONLY / GATE BLOCKED / NO NEW ALPHA VERIFIED**
Upstream: `governance/HENGCE_RESEARCH_LITERATURE_FIRST_CONSTITUTION_v1.md`, `governance/HENGCE_LITERATURE_FIRST_EXECUTION_SOP_20261106.md`.
Full deliverable: `HENGCE_PHASE33_FULL_HANDOFF_20261106.zip` (conversation handoff; this GitHub record is not a copy of the binary or original mother).

## Professional evidence learned first
**Chen, Chou & Hsieh (2018), Persistency of the momentum effect**, European Financial Management 24(5):856–892, online first 2017-07-11, DOI https://doi.org/10.1111/eufm.12140 . NCCU author-accessible primary PDF: https://ah.lib.nccu.edu.tw/bitstream/140.119/113114/1/12140.pdf .
- The **US (1980–2013)** study ranks stocks into winner/loser deciles using past J=3/6/9/12-month returns. In its six-month example, stocks classified as winners at **both t-1 and t month-end** are observable *at t*, unlike a prediction made at t-1 that they will remain winners at t. Subsequent six-month long-short portfolio holding is preceded by a one-month skip; it is **not** HENGCE 20-session Top5 long-only.
- A reported 1.25% monthly persistent long-short return is **author's US historical research**, not costed Taiwanese 5-stock excess return. Do not manufacture a filter or claim direct replication.

**Chen, Hsieh & Lee (2023), Revisiting the momentum effect in Taiwan: The role of persistency**, DOI https://doi.org/10.1016/j.pacfin.2023.101943 . NCCU hub https://ah.lib.nccu.edu.tw/item?item_id=168915 . **Abstract only: NOT FULL_READ.** Paper reports persistent Taiwan long-short momentum in its own historical design; full formation, sample, execution/cost and robustness specifications **not verified**.
**Chen, Hsieh, Lee & Lin (2026) professional open-access review** https://link.springer.com/article/10.1007/s11156-026-01540-7 explains multiple momentum families and distinct historical persistence mechanisms; narrative review is not a 2023 replication.
**Tsung-Yu Chen et al. (2021), Momentum life cycle, revisited**, DOI https://doi.org/10.1016/j.jbankfin.2021.106119 is **counterevidence**: turnover-related lifecycle effects can be driven by already-known component effects and lose robustness to controls. Not direct refutation of the 2023 study.

## Completed independent governed-mother schema audit (no forward returns / no backtest)
- Read exact `HENGCE_PHASE32_FULL_HANDOFF_20261106.zip` original preserved in handoff; SHA256 `65f77f516a2e35851c660297c089a71e4c1e385da07b7e0f09ff39b61ffb51e9`; traversed 32 archive layers to original CSV. Dataset: **1,027,719 rows, 2,149 trade dates from 2018-01-02 through 2026-11-04, 13 columns**.
- `Turnover` is approximately `Volume × Close` (15,000 valid historical rows median ratio **1.000735**, p10 **0.990511**, p90 **1.012327**). Thus this column resembles **monetary trading value**, **not** the paper's turnover ratio `shares traded / shares outstanding`. Do not substitute it silently; original source data dictionary should confirm.
- The mother has no shares outstanding, true institution ownership percentage, market cap, analyst-forecast dispersion. `ForeignNet/TrustNet` are net trades **not** institutional ownership. These are **missing within the inspected mother only**, and are not a claim that other authorized vessels cannot supply them.
- Original historical raw Close is not a fully verified corporate-action-adjusted total return series. Phase21/22 identified capital reductions, stock denomination changes, cash-rights and a delisting. Phase31 identified a 2026-01-02 mother universe scope jump 452 -> 1,068 tickers. No silent pooling across the break.
- Repeated mother capability audit reproducible: `PHASE33_MOTHER_CAPABILITY_AUDIT.json` SHA256 `a5766201a942c9458bb6ffce631afeec3be360bcd5fffb73bec183dd0936c550` on two read-only runs.

## Go / No-Go
- Topic literature gate **BLOCKED**: Taiwan original article only abstract; Taiwan master corpus P1 saturation unverified; no topic gate PASS.
- **No new MOM20 feature/rule/model, no backtest, no tuning**. MOM20 Top5, S5, Escape, RMS, original mother and production governance untouched. Active strategy `NO_ACTIVE_SELECTION_STRATEGY`, zero capital authority.
- Next: retrieve and fully audit the 2023 original methodology and counterevidence, then inspect **existing governed** vessels for PIT price adjustments, shares outstanding and observable turnover. Only then consider preregistered replication; historical 2018–2026 remains previously inspected, not clean OOS.
- Deliverable's complete source-depth ledger, method/timing map, data audit script, manifest and original Phase32 handoff preserve provenance. This GitHub note does not certify the master literature gate or performance.
