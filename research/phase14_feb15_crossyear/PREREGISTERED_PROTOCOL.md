# HENGCE Phase 14 — preregistered cross-year historical-pool check
Date 2026-11-06, created before fetching the phase14 years' daily exchange prices.

**Research-only. Zero model changes.** Keep the original MOM20 Top5 and Top6-10 ranking comparator, S5, Escape, RMS, baseline CSV, and governance. Never optimize parameters in 2025/2026.

## Selection of calendar anchors, not alpha tuning
For each calendar year 2018–2024, use the **first original Phase9 Q1 `signal_date` on or after February 15**, where corresponding daily exchange observations are recovered (do not shift the preselected signal when an observation is missing; mark FAIL). In this phase collect **2019-02-15 and 2022-02-15** as two deliberately separated independent calendar regimes, plus 2018-02-21 as preexisting reference only. These were picked before recovering new full-market daily prices; the collection is incomplete (2018, 2019, 2022 only), must not be labeled full cross-year proof. Preserve all remaining 2020–21 and 2023–24 as untested years; may eventually run all.

## Frozen model and trading rule
Source: TWSE MI_INDEX dated historical `response=json&type=ALLBUT0999`, one response per trading date, `stat=OK` and exact response date required. Four-digit quote candidate tickers, exclude -DR labels; independently certified PIT common-share roster and adjusted dividends still not completed. Need last 21 trading sessions with positive close, last 9 sessions each traded TWD >=2,000,000 and mean >=20,000,000. MOM20 = Close[T]/Close[T−20]−1, sort descending then ticker ascending. Compare rank 1–5 against rank 6–10, equal-weight. Buy next trading day's CLOSE, sell 21st trading day after signal's CLOSE (20 sessions of holding), no rebalance; buy cost 0.002425, sell cost 0.005425 applied multiplicatively to the equal-weight raw stock gross return. All days each held security must have positive close and adjacent raw close jump <=22%; otherwise entire group invalid, no backfilled name. Require every date complete or FAIL CLOSED.

## No data mining / declared evaluation
All selected years remain in result, even if worse than old universe. Report per-year old-vs-new Top5 overlap, fixed20-day net, new Top5 vs new 6–10, old parity if official price available, and concentration of outsized returns. No p-value, no signal significance from 2–3 anchors. Not sufficient to greenlight the strategy or change baseline. Full 2018–2025 PIT universe repair remains blocked until systematic coverage, delisting, corporate action, and tradability audit.

Governance: NO_VALIDATED_SELECTION_EDGE / NO_MODEL_PROMOTION / NO_TRADING_AUTHORITY.
