# HENGCE Phase 14 — frozen February-anchor cross-year audit (RESEARCH ONLY)
Date: 2026-11-06. Branch: `research/phase14-fixed-feb15-cross-year-20261106`.

All original MOM20 Top5, daily close/turnover rules, ranks 6–10, 21-valid-close requirements, T+1-close entry to T+21-close exit, 0.2425%/0.5425% costs, and 22% holding-day jump threshold were frozen and unchanged. Official source TWSE historical `MI_INDEX` daily rows and exact-date `發行量加權股價報酬指數`. S5, Escape, RMS and original research governance unchanged; production main branch not changed.

| Signal | Rebuilt Top5 | New Top5 net % | New rank6–10 net % | Top5 minus peer pp | TAIEX total return % | Top5 minus TAIEX TR pp | New vs old Top5 |
|---|---|---:|---:|---:|---:|---:|---:|
|2018-02-21|2388,9958,2425,3557,2033|+14.05|-11.64|+25.69|+1.51|+12.54|+0.39pp|
|2019-02-15|3708,3016,6558,8215,3530|-0.76|+10.35|-11.11|+4.00|-4.77|-1.73pp|
|2020-02-17|1732,9919,1325,3515,3669|+8.41|INVALID|N/A|-20.86|+29.26|Old Top5 INVALID|
|2021-02-17|4576,1533,3138,6531,3034|+1.99|+6.25|-4.25|-2.03|+4.02|-7.57pp|
|2022-02-15|1529,2462,1760,6205,2497|INVALID|-4.24|N/A|-4.14|N/A|N/A|
|2023-02-15|2453,2482,2236,4763,3443|+18.64|INVALID|N/A|-0.66|+19.30|-14.13pp|
|2024-02-15|2465,6805,3017,2365,3376|+11.78|-3.67|+15.45|+7.00|+4.78|0.00pp|

**Quality failure is not a zero return and not an implicit substitution.** 2020 rank6–10 has missing 5269 close on 2020-02-21; old 2020 Top5 same issue. 2022 new Top5 has missing 1760 close 2022-02-22. 2023 new rank6–10 missing 6541 close 2023-03-02. No 6th-ranked substitutes, no alternate dates or shortened windows.

Four valid *Top5-vs-rank6–10* anchor pairs: 2018/2019/2021/2024, of which 2 were positive and 2 negative. Of six valid new Top5, five exceeded the market **price-and-dividend total-return index** in these particular 20-session windows, one did not; 2022 Top5 is invalid, not a loss nor a win. These are seven isolated date anchors across 2018–2024, NOT full-year backtests, NOT a formal seven-year alpha test, and too few to establish repeatable advantage. Cross-year earnings can be dominated by particular names or sector exposures. Because stock returns use *unadjusted raw closes excluding dividends* but the market uses *total-return index*, their payoffs are not yet on an equal equity-entitlement basis.

Original old Top5 and rank6–10 results for 2019–2024 reproduced from these official raw prices within normal rounding (with original invalid group still invalid); 2018 original same parity was already established in Phase13. Every eligible original-quote candidate is a four-digit security with `-DR` omitted; not a certified daily common-stock roster or adjusted for delisting, rights, splits, reverse splits, recovery, suspensions or execution slippage.

Data archived: 2018 Phase13 has 56 official trading days; Phase14 added 42 official-source days per year for 2019,2020,2021,2022,2023,2024: 252 new trading dates, 308 total archived calendar-date quotes across nonoverlapping historical periods. 2025 and 2026 were not used for model fitting, feedback, or optimization. 2018–2025 complete daily historical universe and corporate entitlements remain INCOMPLETE.

**Decision:** No repeatable selection alpha demonstrated. Do not promote. **NO_VALIDATED_SELECTION_EDGE / NO_MODEL_PROMOTION / NO_TRADING_AUTHORITY.**
