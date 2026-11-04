# HENGCE exploratory IF-MOM60-SKIP5 — pre-test contract (2026-11-04)

Branch: `research/independent-skip5-momentum-prereg-20261104`, parent commit `c4a2cbb80f89d97adc0f73cad2086ab7fde533ee`.
Status: `EXPLORATORY_HISTORIC_ONLY`; `NO_TRADING_AUTHORITY`.
Date of pre-registration: 2026-11-04, before computing results under this contract.

## Single hypothesis; do not optimize
The cross-sectional momentum/underreaction hypothesis predicts the highest **prior 60-to-5 trading-session raw close momentum**, \(close[t-5]/close[t-60]-1\), among the exact frozen PIT-archived electronics turnover Top100 may outperform, after realistic costs, a random one-stock selection and simple 20-session price momentum. Recent 5 days are excluded to reduce short-run reversal effects. **This is an economic hypothesis, not evidence of an advantage.**

## Frozen selection and trading contract
- Original frozen 84 N2 dates and next-session entry/20th trading-session closing exit; exact Top100: 60-session median turnover rank, at least 50 observed daily amounts, historical electronics archive. No alternate dates, replacements, stock changes to N2, or optimization.
- New candidate only: eligible ticker with highest `close[t-5]/close[t-60]-1`; price must be positive and observed at both dates. Tie ticker ascending. If any date insufficient or no eligible ticker, `DATA_BLOCKED` on that event; never replace by another window.
- One stock Top1 and exactly independent NT$5,000,000 for each event, whole lots of 1000 shares, idle remainder; next session open simulated entry and 20th session close simulated exit. No compounding, no position overlap, no substitute stock for unpriced exit.
- **Reserve the full 0.4% roundtrip cost from purchase cash**: `lots=floor(5m/(entry_open*1000*(1+0.004)))`, PnL `shares*(exit_close-entry_open)-0.004*invested`. For 0.8% stress recompute lots using 0.008; same for *all* comparators. A price or amount failure is blocked, not a zero outcome.
- Fair fixed-name re-budgeting for original N2, simple 20-session momentum Top1, and rolling equal-weight of the Top100 (equal-weight is descriptive and not one-stock executable comparator); exact same date universe, fees and lot approach for all Top1.
- Random Top1 baseline analytic equal-weight conditional expectation over all eligible prices, separately count blocked candidates; not interpret as formal significance. Optional deterministic fixed random simulation, one random stock per event, no resampling by result. Compare a fixed TAIEX matching-window index-price proxy if already verified; avoid conflating with tradeable ETF.
- Diagnostics: yearly PnL, 2024 and 2026, percent beats simple momentum and frozen N2, best-win-removal contribution, long-term risks, corporate action contamination, volume feasibility. Assess drawdown, fees and turnover; do not call calendar-total compounded return.
- No performance gate automatically confers strategy approval. Failed or blocked data is permitted and must be recorded.
- Historical 2018–2026 has repeatedly been seen and is **NOT** prospective OOS. Even if historical winner, no alpha claim, strategy remains research-only. New real forward evidence must be frozen before observation.

## Kill criteria (non-negotiable)
No promotion if PIT or total-return audit fails, actual NT$5m open-fill data unavailable, or new forward evidence missing. If candidate cannot beat relevant controls without relying on an extreme win or lacks stable cross-regime evidence, record `HISTORIC_NO_ADVANTAGE`; stop optimizing this hypothesis. This is one preselected parameter, not a grid search.
