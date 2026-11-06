# HENGCE Phase35 — 2023 Taiwan momentum persistency, supplied-article method audit
Date 2026-11-06 | LITERATURE_REVIEW_ONLY | NO NEW ALPHA / NO BACKTEST / NO SIGNAL AUTHORITY

## Reading status and provenance
User supplied labelled pages 2–24 of Chen, Hsieh and Lee (2023), Pacific-Basin Finance Journal 78, 101943, DOI https://doi.org/10.1016/j.pacfin.2023.101943; substantive sections 2–7, Tables 1–13, Appendix A.1–A.4 and bibliography examined. Cover p1 absent; supplied as pasted text not original verified PDF; table transcription ambiguities remain. Status: TEXT_OF_PAGES_2_TO_24_REVIEWED / NOT FULL_PDF_VERIFIED / Taiwan Master Corpus gate NOT PASS.
Author interview https://nccubr.nccu.edu.tw/articles/30 confirms 6-month raw persistent long-short = 0.701% per month, 12-month raw = 0.380%. Do not confuse risk-adjusted alpha with raw realized return.

## Method and information timing
1982–2020 TEJ Taiwan listed and OTC common stocks. Monthly equal-weight cross-sectional winner/loser groups from prior 6-month performance (J=3,9,12 alternatives). At end of t, persistent winner is in winner group at BOTH t-1 and t, as observed at end t; persistent loser likewise. Long winners and short losers, one-month skip following formation, hold 6 or 12 months, no rebalance during a cohort's holding interval. This information cannot have been known at end t-1. Eq (1) duration through t+24 is retrospective dependent variable, not an ex-ante predictor. Three-group top 30% wording and top-third/decile references conflict; preserve that ambiguity instead of fabricating a threshold.

## Table 5 K=6 — monthly percent, historical not after execution costs
| Leg | Persistent | Standard JT seven-month |
|---|---:|---:|
| Long-only winner raw | +1.387 | +1.720 |
| Loser underlying raw | +0.686 | +1.544 |
| Long winner minus short loser RAW | +0.701 | +0.176 |
| W-L FF5 alpha | +0.756 | +0.185 |
Nonpersistent W-L K6 Table5B RAW −0.429, FF5 −0.436; K12 persistent W-L RAW +0.380. In Table8, persistent winner dummy DPW raw +0.031 insignificant, persistent loser DPL raw −0.496 significant, difference +0.527. This is evidence of a long-short spread with much of incremental power on the short side, NOT a proof that long-only top-five persistent winners beat conventional long-only winners. No long-only Taiwan Top5 out-of-sample or net-cost result is shown.

## Material contradictions to verify in PDF / with author, not fix by guessing
1. Section 3.2 says nonpersistent winner lost 1.05% but Table4 Panel A gives POSITIVE +1.050%; arithmetic +1.636 − +1.050 = +0.586 confirms table's positive sign.
2. Section 4.1 text states nonpersistent W-L six-month −0.786%; Table5B says RAW −0.429% and FF5 −0.436%. Contradiction unresolved.
3. Introduction approximately 46% winners and 52% losers exit; Table3 J6 group remains winners 54.52% / losers 51.11%, hence exit 45.48% / 48.89%. Distinct A2 duration-zero rates 45.72% / 51.36%; do not mix denominators.
4. 30%, top-third, top one-third decile, and top decile phrasing appear interchangeably; determine exact quantile bins, sample eligibility and tie handling before any replication.
5. Formation return endpoint t−7 to t−1 wording vs t−6 to t and overlapping cohort accounting need exact month-end conventions.
6. Zero-investment spread means long-short accounting, not zero capital or free shorting. Taiwan trading taxes, spread, commissions, price limits, short availability and slippage NOT established as deducted.
7. Taiwan paper sample includes TPEX and years 1982–2020. HENGCE governed mother 2018–2026 differs in coverage and has corporate-action/PIT and 2026 universe scope questions. Descriptive durability in this paper does not verify MOM20 Top5.
8. Original trader strategy persistence at t−1/t is prospective at t, but measured duration up to t+24 is ex-post; never use realized duration as entry signal.
9. Table11 has exceptions for non-momentum markets such as Brazil and Turkey; broad international robustness has limits.

## Decision
No new indicators, entry rule, ranking, score or performance test. Continue original governance: MOM20 Top5, S5, Escape, RMS and existing vessel unchanged, active trading authorization NONE. Next read p1 and PDF images, verify conflicts and complete multi-source counterevidence + master literature gate before preregistration.

## 2026-11-06 temporary ScienceDirect PDF link check
User supplied a signed ScienceDirect asset link for article S0927538X23000094; authorization query indicates 2026-11-06T12:32:35Z with expiry 300 s (= 20:37:35 Asia/Taipei). At 20:41 Asia/Taipei this was already expired; direct web PDF retrieval failed. Do **not** commit the signed query string or claim that the original PDF images were accessed. The user-supplied full article text (pages 2–24) remains available for method analysis; original PDF page 1, visible typesetting and inconsistent table labels/signs await verification from a newly downloaded PDF uploaded as a file.

## Fresh signed-link fetch attempt (2026-11-06)
The user supplied a second short-lived ScienceDirect signed PDF URL for S0927538X23000094 with X-Amz-Date 20261106T124235Z and 300-second validity (expires 20:47:35 Asia/Taipei). An immediate direct document opening returned an internal error, and an independent website content fetch returned `target_unreachable`; no PDF bytes were obtained locally. Signed URL credential/token omitted intentionally from public record. The user-supplied pages 2–24 text and table-based conclusions remain the substantive reviewed evidence, but original PDF visual verification is **NOT DONE**. Do not mark as FULL_PDF_READ based on this failed fetch; use a downloaded PDF file attachment instead.
