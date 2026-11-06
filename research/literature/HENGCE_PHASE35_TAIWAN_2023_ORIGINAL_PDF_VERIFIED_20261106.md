# HENGCE Phase35 | 2023 Taiwan persistence — ORIGINAL PDF CHECKED (2026-11-06)

**Reading state: ORIGINAL 24-PAGE PDF ACQUIRED, READ AND VISUALLY CHECKED.**
**Topic readiness: METHOD REPLICATION NOT CLEARED / Taiwan Master Literature Gate NOT PASS / NO NEW MODEL, NO BACKTEST, NO SIGNAL OR CAPITAL AUTHORITY.**

## Provenance and exact source
User-uploaded original Elsevier article `main.pdf`, 24 pages, 692,908 bytes.
SHA256: `b281bcfc2bfb672c9273c215d6e6458d797f55621b72974d2bf21d852c208e92`.
Hong-Yi Chen, Chia-Hsun Hsieh, Cheng-Few Lee (2023), *Revisiting the momentum effect in Taiwan: The role of persistency*, Pacific-Basin Finance Journal 78, 101943. DOI: https://doi.org/10.1016/j.pacfin.2023.101943
Title page, methods, all Tables 1–13, Appendix Tables A.1–A.4, footnotes and bibliography were visually inspected in the ORIGINAL PDF. This supersedes earlier notes claiming the PDF was missing. The user-uploaded licensed PDF remains private; **DO NOT COMMIT ITS BYTES TO THIS PUBLIC REPO**.

## Exact method
- TEJ Taiwan TWSE and OTC common stocks, 1982–2020, equal-weighted monthly formation. Main J=6-month past return ranking; J=3/9/12 alternatives.
- Persistent winner at end t is classified winner in BOTH rankings at t-1 and t; loser analog. This is observable as of t, not as of t-1. The trading long-short position is determined at t; one-month skip before ensuing 6- or 12-month holding, no rebalance within a held cohort. PDF pp.8–9.
- **Important split:** Formula (1) realized duration through t+24 is retrospective research outcome, not permissible ex-ante stock-selection input. PDF pp.3–4.
- The main grouping is described as top/bottom 30% and as three groups; table notes also use 'one-third' or 'decile'. Table3 explicitly supplies both three-group and ten-decile panels. Precise binning/ties and rolling return endpoints **must be resolved before claiming exact replication**.
- Monthly statistical return factor adjustments do not deduct execution taxes, commissions, spread, borrow fees, slippage or limit price fill constraints.

## Major numbers verified directly against table images (per MONTH, 1982–2020)
TABLE 5 (PDF p.9, k=6):
- Persistent long winner raw: **+1.387%**; standard JT J=7 long winner raw: **+1.720%**.
- Persistent loser stock raw: **+0.686%**; JT loser raw: **+1.5442%**.
- Persistent W-L RAW: **+0.701%**; JT W-L RAW **+0.176%**.
- Persistent W-L FF5 ALPHA: **+0.756%**; JT W-L FF5 ALPHA **+0.185%**.
- Nonpersistent W-L RAW: **-0.429%** (Table5B).
Table8 (PDF p.14): separate persistent winner indicator DPW raw ≈ +0.031% *not significant*, persistent loser DPL ≈ -0.496% significant, spread DPW−DPL ≈+0.527%; authors explicitly attribute much of the isolated spread to persistent losers.
**Inference limit:** these are diversified Taiwan LONG-SHORT portfolio results, not independent proof that a concentrated long-only MOM20 Top5 persistent filter has net alpha. Note Table4 (p.8) persistent winner +1.636 vs nonpersistent winner +1.050 in first following month uses a DIFFERENT comparison from Table5's JT standard winner.

## Errors or ambiguous statements printed IN THE ORIGINAL PDF
1. Section3.2 (PDF p.6) says nonpersistent winner 'loss of 1.05%'; Table4 (p.8) shows **positive +1.050%**; 1.636−1.050=0.586 matches printed delta.
2. Section4.1 (p.9) prose calls six-month nonpersistent W-L RAW **-0.786%** but Table5B says RAW **-0.429%**, FF5 **-0.436%**.
3. Section4.1 (PDF p.8) calls **0.756%** 'raw'; Table5A (PDF p.9) shows **0.701% RAW** and **0.756% FF5 alpha**. Do not confuse risk-adjusted alpha with real earned return.
4. 'top 30%' vs 'top one-third' vs 'top decile' wording; do NOT invent the exact grouping rule, eligible universe, ties, or endpoints.
5. The two six-month rolling formation windows end at t-1 and t. They can be conceptually compatible; do not invent a lookahead error or fill dates without checking conventions.
Author clarification may be needed for exact replication; this is not a license to silently 'correct' the article.

## Review of ALL remaining parts of paper
- Table6 (p.11): multiple persistence lags; Table7 (p.12): long-short spreads for 1–4 known past persistence months; do not substitute future realized duration from Eq(1) as the current signal.
- Table9 (pp.14–15): authors find no significant longer-term reversal, not a demonstration of live profitability.
- Table10 (p.16): censored duration statistical mechanism associations with forecast dispersion, trading turnover / shares outstanding, institution ownership, residual volatility; NOT causal proof or necessary data for the BASIC winner-ranking strategy. 'Turnover' in Table3 means *membership turnover*, not share turnover ratio used in Table10.
- Table11–13 (pp.17–19): international extension and differences, with negative exceptions (Brazil/Turkey); not universal identical success.
- Appendix A.1 (pp.20–21): alternate value weight, ten groups, exclude OTC, exclude 2020; Appendix A.2–A.4 (pp.21–23): duration distribution, loser tests and mechanism variables.

## Decision and safe handoff
Original PDF read requirement is fulfilled; earlier 'missing full article' claims are obsolete. **Do not interpret full source reading as a passed overall topic literature gate.** Existing master-corpus saturation, source conflicts, exact implementation rules, PIT historical universe / corporate actions and genuine OOS readiness remain **BLOCKED**.
HENGCE original MOM20 Top5/S5/Escape/RMS, existing governed mother/blood vessels and no-active-selection-strategy remain unchanged.
Next: independently corroborate method ambiguities with authors/method appendices if available, review original Taiwan counterstudies, then check governed mother capability without inspecting future returns. Only after formal literature and preregistration gates may a bounded replication be attempted. Do not tune 2018–2026 outcomes or call this a model victory.
