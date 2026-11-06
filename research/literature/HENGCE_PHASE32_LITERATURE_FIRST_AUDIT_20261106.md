# 衡策 HENGCE｜Phase32 Literature First Audit (2026-11-06)
Status: **LITERATURE_REVIEW_ONLY / NO NEW STRATEGY / NO OOS ALPHA VERIFIED**.
Governance upstream: [Literature First Constitution](../../governance/HENGCE_RESEARCH_LITERATURE_FIRST_CONSTITUTION_v1.md); [execution SOP](../../governance/HENGCE_LITERATURE_FIRST_EXECUTION_SOP_20261106.md).

## Read-first findings
1. Previous Phase31 exercise on Taiwan intraday/overnight momentum was NOT replication of Ho et al. (2023). Their paper forms 12-month intraday/overnight momentum portfolios with one-month future holding tests; Phase31 split the **already selected** MOM20 Top5 435 positions by 20-day components. Do not call these equivalent.
2. Bailey et al. (2017) CSCV requires synchronized returns matrix T×N for **actual tried strategy configurations**. This round inventoried 43 output files in the nested Phase25–31 handoffs. P25 6,000 monkey random control paths are not 6,000 searched models. P27 and P30 provide 87 fixed windows, P29 4 candidates × 33 windows, P31 forward ledger has 0 trades. No complete Phase1–31 strategy-trial ledger verified, hence **DO NOT COMPUTE OR CLAIM PBO**.
3. Published Taiwan momentum evidence is mixed: Hameed & Kusnadi (2002) broadly weak Asian-market momentum; Chen et al. (2023) propose persistence-based winner-minus-loser approach, but full paper's feasible point-in-time method is unverified. No new filter until original full text and gates are passed.
4. Harvey, Liu & Zhu (2016) warns t≈2 misleading after many trials; its reported t>3 factor-research hurdle is **not** an automatic HENGCE trading certification. McLean & Pontiff (2016) found 97 published cross-sectional predictor returns lower by 26% out-of-sample and 58% post-publication, **not** a Taiwan MOM20 forecast.

## Evidence sources and access depth
- Bailey et al., *The Probability of Backtest Overfitting*: https://doi.org/10.21314/jcf.2016.322 — PARTIAL (full text methods reviewed, not full table audit).
- Harvey et al., *... and the Cross-Section of Expected Returns*: https://doi.org/10.1093/rfs/hhv059 — PARTIAL.
- McLean & Pontiff, *Does Academic Research Destroy Stock Return Predictability?*: https://doi.org/10.1111/jofi.12365 — PARTIAL.
- Ho et al., *Momentum investing and a tale of intraday and overnight returns*: https://doi.org/10.1016/j.pacfin.2023.102151 — PARTIAL (publisher detailed introduction, not complete tables).
- Chen et al., *Revisiting the momentum effect in Taiwan: The role of persistency*: https://doi.org/10.1016/j.pacfin.2023.101943 — FOUND_ONLY.
- Hameed & Kusnadi, *Momentum Strategies: Evidence from Pacific Basin Stock Markets*: https://doi.org/10.1111/1475-6803.00025 — FOUND_ONLY.
- Daniel & Moskowitz, *Momentum Crashes*: https://doi.org/10.1016/j.jfineco.2015.12.002 — PARTIAL.

**No FULL_READ claimed.** Full Taiwan Stock Market Master Corpus + topic literature gate PASS not established here; status is BLOCKED for new modeling.

## Next proper work
- Obtain Chen et al. full text and examine precise persistence definition **before** building model. Compare their long-short, month-scale universe and trade timing to long-only HENGCE Top5.
- Recover actual full trial history and per-window synchronized outcomes from early rounds without fabricating old runs or treating random controls as selected models.
- Do not backfit on 2018–2025/2026. Continue existing prospective freeze only with valid first-seen immutable timestamp, original governed vessel, and eventual true unseen periods.
- Always keep MOM20, S5, Escape, RMS and production unchanged; no stock-selection or capital authority generated.

## Artifact provenance
Research performed against user-held full Phase31 handoff ZIP; verified SHA256: `36029d7593c457d2eaac8de4ac785c2e9e85addb8a3a2b58a0c2c8264683d609`.
Local archive contains read-first report, source ledger, per-file SHA inventory and read-only audit script. GitHub note is a trace, **not** a substitute for original ZIP or canonical master literature ledger.
