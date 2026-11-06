# HENGCE Phase36 — Direct persistence-model experiment
2026-11-06. Status: REJECTED / RESEARCH ONLY / NO CAPITAL AUTHORITY.

Study based on Chen, Hsieh and Lee (2023), Pacific-Basin Finance Journal 78, 101943, DOI 10.1016/j.pacfin.2023.101943.
The original 24-page paper was provided privately and reviewed; its author strategy is monthly Taiwan common stocks, six-month ranking, persistent membership at t-1 and t, long winners/short losers, one-month skip, and six-/twelve-month holding. NOT the same as a 20-session long-only Top5 strategy.

Single frozen prototype: use original MOM20 Top5 435 trades over 87 fixed 2018–2025 holding periods. Keep an existing Top5 slot only if the stock is in the top 30 percent of previous six-month returns on both of the last two completed market month-ends; otherwise that slot remains cash. No replacement, no threshold tuning.

Mean net return per original period: original MOM20 Top5 +2.9691%; candidate +0.7941%. 2024–2025: original +0.3701%; candidate -1.0424%. Candidate-minus-original difference -2.1750 percentage points overall.
Candidate retained 158/435 slots, captured 4 of 15 trades with realized returns above +50 percent, missed 11. 15 periods entirely cash.
Matched-control excess including inactive zero-weight slots: original +2.3545 percentage points per period, candidate +0.8852 percentage points.
Ten thousand equal-period equal-exposure random selections within original Top5 averaged +0.9241% per period; candidate +0.7941%, 35.63 percentile of random selection. Exploratory, not clean out of sample.
Recheck excluding 2018 warm-up: baseline 2019–2025 +3.2301%, candidate +0.9829%. Model does not improve.

Independent full-archive cold replay reproduced all five output checksums. Private handoff: HENGCE_PHASE36_FULL_HANDOFF_20261106.zip; archive sha256 5626b59efb4eed1f72871ccd7bf1684d61c306c922007e10cf942a6baf5992da.
Inputs: original frozen mother, P27 435 paired costed returns, P28 87 periods; not independent new holdout. Historical mother month-end prices not fully verified as adjusted for corporate actions, and 2018–2025 universe not identical to the paper's nationwide TSE plus OTC sample.
Verdict: eliminate this candidate, do not tune to rescue. MOM20, S5, Escape, RMS, original mother and no-active-strategy production governance unchanged. This result does not disprove the author's long-short strategy.

Source/traceability and full code are in the private handoff, not committed to this public research summary. No licensed PDF copied into GitHub.
