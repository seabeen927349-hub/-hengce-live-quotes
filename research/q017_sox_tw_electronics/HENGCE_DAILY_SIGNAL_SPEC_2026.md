# HENGCE 2026 SOX Electronics Daily Signal Spec

Research-only signal framework. Objective: maximize 2026 final capital under the tested SOX x Taiwan electronics setup. This is not an automated brokerage instruction.

## Entry model

Use only information available at decision time.

1. Latest completed U.S. SOX session before Taiwan market open:
   - SOX daily return <= -2.0%
   - SOX 5-session cumulative return <= -4.0%
2. Taiwan listed electronics universe only.
3. Compute each stock's rolling SOX beta from prior observations only (up to last 60 aligned observations; at least 30 required).
4. Rank by beta descending.
5. At Taiwan open, compute response residual:
   - expected_gap = beta * SOX_daily_return
   - actual_gap = Taiwan_open / prior_Taiwan_close - 1
   - residual = actual_gap - expected_gap
6. Candidate is the highest-beta stock with residual <= +4.0%.

## Daily state machine

### CASH
No active position and entry gate is not fully satisfied.
Output: CASH.

### SETUP
Pre-open SOX daily and SOX5 gates are satisfied, but Taiwan open/residual is not known yet.
Output: SETUP + provisional beta Top3 watchlist.

### ENTRY_CANDIDATE
After open, entry gate is fully satisfied and a valid Top1 candidate exists.
Output fields:
- ticker/name
- prior-60 SOX beta
- SOX daily return
- SOX5 cumulative return
- actual gap
- expected gap
- residual
- research status = ENTRY_CANDIDATE

### HOLD_D1 ... HOLD_D9
For an active research position before the tenth Taiwan trading session inclusive.
Output:
- ticker
- entry date/open
- current day count
- current mark-to-market return
- planned time exit date
- research status = HOLD

### EXIT_D10
The fixed 10-trading-day exit remains the highest-profit 2026 rule among the tested fixed and dynamic exits.
Exit reference used in research: close of the 10th Taiwan trading session, with 0.4% round-trip cost assumption.
Output: EXIT_D10.

### DATA_PENDING
Required SOX, Taiwan open, beta history, or price data are incomplete.
Never infer or fill missing values.

## Conflict rules

- If a new setup appears while an active research position is still inside D1-D10, do not replace the active position in the current best single-sleeve configuration.
- Re-evaluate for a new candidate only after the active position exits.
- Dynamic exits tested so far underperformed the fixed D10 exit; do not activate trailing-stop, momentum, SOX-recovery, or take-profit overrides unless a later 2026 capital test beats the D10 baseline.

## Current 2026 research benchmark

Best tested entry/exit family at time of writing:
- SOX daily <= -2.0%
- SOX5 <= -4.0%
- Top1 rolling SOX-beta electronics stock
- residual <= +4.0%
- single sleeve
- fixed D10 exit
- 0.4% round-trip cost

Historical 2026 research result: start NT$2,000,000 -> approximately NT$6,730,023 (+236.5%) over 9 non-overlapping events in the tested sample.

## Required daily output format

Keep it short:

STATE: CASH | SETUP | ENTRY_CANDIDATE | HOLD | EXIT_D10 | DATA_PENDING
STOCK: ticker name | NONE
SOX 1D: x.xx%
SOX 5D: x.xx%
BETA: x.xx | NA
GAP: x.xx% | NA
EXPECTED GAP: x.xx% | NA
RESIDUAL: x.xx% | NA
DAY: D0-D10 | NA
NOTE: one short factual reason
