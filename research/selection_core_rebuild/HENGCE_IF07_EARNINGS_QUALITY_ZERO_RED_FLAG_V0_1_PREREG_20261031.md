# HENGCE Selection Core Rebuild — IF-07 Earnings Quality ZERO-RED-FLAG Challenger V0.1 Preregistration

Date frozen: 2026-10-31
Branch: `research/selection-core-rebuild-20261031`
Status at creation: `PREREGISTERED_NOT_YET_RETURN_TESTED`
Trading / production authority: `NONE`
Forward returns inspected for this challenger before this file was persisted: `NO`
Parent rescue / retuning: `FORBIDDEN`

## 0. Governance purpose

This document freezes one challenger **before** any forward-return calculation.

It does not claim alpha. It defines a falsifiable test.

If this challenger fails, it is killed as V0.1. No threshold/window/feature rescue is permitted in place. Any future hypothesis must receive a new version and a new preregistration before looking at its forward returns.

V6/V43 remain frozen references only. Cross-stock capital-share migration remains killed. Escape v2.4.7 has zero Selection authority.

## 1. Challenger identity

ID:
`IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1`

Information family:
`IF-07 FUNDAMENTAL QUALITY`

Core hypothesis:
> A newly filed quarterly report that shows no deterioration across cash conversion, receivables discipline, inventory discipline, gross margin, operating margin, and leverage identifies a higher-quality earnings state that contains Selection information beyond simple equal-weight, momentum, reversal, and random nulls.

The hypothesis is accounting-quality based. It does not use price, turnover, margin financing, institutional flow, TDCC, broker flow, Escape, or familiar-stock identity to construct the challenger signal.

## 2. Formal universe

Base universe:
`TWSE_LISTED_ELECTRONICS_PIT_DAILY`

A company-event is eligible only if all are true at signal time:
1. the company is TWSE-listed and classified as electronics on that PIT date;
2. TPEx/OTC is excluded;
3. an original quarterly **consolidated** financial report has a verified official TWSE electronic-report `上傳日期` timestamp;
4. the current report and prior-year same-quarter report can both be parsed for every required field below;
5. required denominators are positive and finite;
6. the stock has sufficient price history to construct frozen null N1/N2 and a valid next-open entry under the baseline contract.

Missing required accounting data => event excluded, fail closed.
No imputation.
No synthetic history.
No backfilling from later corrected statements.

## 3. PIT availability and revision law

Official source timestamp:
`upload_ts = TWSE electronic financial-report 上傳日期`

Signal date:
`signal_date = first TWSE trading day whose official market close timestamp occurs strictly after upload_ts`

Consequences:
- if a report is uploaded before that day's market close, it may be used at that day's after-close signal;
- if uploaded after market close, on a weekend, or on a holiday, it first becomes usable at the next TWSE trading day's after-close signal;
- entry is the next TWSE open after `signal_date`.

Quarter-end date is never an availability date.
Statutory deadline is never substituted when an actual upload timestamp exists.

Revision handling:
- use the earliest original filing for a company-quarter;
- later corrections/restatements must not overwrite the historical signal values;
- corrected filings may be stored for audit but have zero authority to mutate the original event.

## 4. Accounting field contract

For current fiscal year `Y` and quarter `Q`, use the cumulative/current values reported in the consolidated financial statements for the fiscal period through Q, plus quarter-end balance-sheet stocks.

Required fields:
- `Revenue_YTD`
- `COGS_YTD`
- `OperatingIncome_YTD`
- `CFO_YTD` = net cash flow from operating activities
- `AR` = net accounts receivable at quarter end
- `Inventory` = inventory at quarter end
- `Assets` = total assets
- `Liabilities` = total liabilities

Required prior-year same-quarter fields:
- identical eight fields from `(Y-1, Q)`.

Frozen MOPS concept aliases may normalize harmless presentation variants such as:
- `營業收入` / `營業收入合計`
- `營業成本` / `營業成本合計`

The economic concept must not change. Company-specific bespoke aliases created after seeing returns are forbidden.

## 5. Derived variables

All calculations use current report vs prior-year same-quarter report.

### 5.1 Cash conversion

`cash_conversion = CFO_YTD / Revenue_YTD`

`cash_conversion_prev = CFO_YTD_prev / Revenue_YTD_prev`

`D_CASH = cash_conversion - cash_conversion_prev`

Pass condition:
`D_CASH >= 0`

### 5.2 Receivables discipline

`REV_YOY = Revenue_YTD / Revenue_YTD_prev - 1`

`AR_YOY = AR / AR_prev - 1`

`AR_GAP = REV_YOY - AR_YOY`

Pass condition:
`AR_GAP >= 0`

Economic meaning: receivables do not grow faster than recognized revenue.

### 5.3 Inventory discipline

`COGS_YOY = COGS_YTD / COGS_YTD_prev - 1`

`INV_YOY = Inventory / Inventory_prev - 1`

`INV_GAP = COGS_YOY - INV_YOY`

Pass condition:
`INV_GAP >= 0`

Economic meaning: inventory does not grow faster than cost-of-goods activity.

### 5.4 Gross-margin non-deterioration

`GM = (Revenue_YTD - COGS_YTD) / Revenue_YTD`

`GM_prev = (Revenue_YTD_prev - COGS_YTD_prev) / Revenue_YTD_prev`

`D_GM = GM - GM_prev`

Pass condition:
`D_GM >= 0`

### 5.5 Operating-margin non-deterioration

`OM = OperatingIncome_YTD / Revenue_YTD`

`OM_prev = OperatingIncome_YTD_prev / Revenue_YTD_prev`

`D_OM = OM - OM_prev`

Pass condition:
`D_OM >= 0`

### 5.6 Leverage non-deterioration

`LEV = Liabilities / Assets`

`LEV_prev = Liabilities_prev / Assets_prev`

`D_LEV = LEV - LEV_prev`

Pass condition:
`D_LEV <= 0`

## 6. Exact challenger signal

A company-event is selected if and only if **all six** conditions pass:

`D_CASH >= 0`
`AR_GAP >= 0`
`INV_GAP >= 0`
`D_GM >= 0`
`D_OM >= 0`
`D_LEV <= 0`

This is the `ZERO_RED_FLAG` rule.

There are:
- no optimized magnitudes;
- no score weights;
- no top-percentile threshold;
- no growth-rate floor;
- no familiar-name whitelist;
- no rescue exception.

If 0 names pass on a signal date, that date is not a challenger event date.
If multiple names pass on the same signal date, select all of them.

`k_d = number of selected names on signal date d`.

No maximum `k` is imposed at the event-test stage.

## 7. Signal de-duplication and overlap

- maximum one Selection event per ticker per fiscal quarter;
- multiple original-file rows for the same company-quarter must collapse to the earliest verified original upload;
- later corrections do not generate a new V0.1 event;
- different tickers on the same signal date remain separate selected events but form one date block;
- a ticker may generate a new event in a later fiscal quarter even if a long-horizon observation from the prior quarter overlaps in calendar time.

Statistical inference must use signal-date blocks so a mass filing date is not treated as dozens of independent market observations.

Portfolio proof later must forbid pyramiding: an already-held ticker cannot receive additional notional from a new signal until the existing position exits under the tested horizon.

## 8. Return geometry — frozen before opening returns

Execution follows the frozen null contract:
- signal: after close on `signal_date`;
- entry: next TWSE open;
- round-trip cost: 40 bps total;
- horizons: 5 / 10 / 20 / 40 / 60 TWSE sessions.

Frozen exit convention:
- for horizon `H`, exit at the official close of the H-th TWSE trading session counting the entry session as session 1;
- net return subtracts the full 40 bp round-trip cost.

Primary research horizon:
`20 sessions`

Secondary horizons:
`5, 10, 40, 60 sessions`

Secondary horizons cannot rescue failure at the 20-session primary horizon.

## 9. Frozen nulls

Use the existing frozen baseline contract without modification:
- N0 = equal-weight eligible cross-section;
- N1 = prior-20-session momentum TopK;
- N2 = prior-5-session reversal BottomK;
- N3 = matched random, seed 20261031, 10,000 draws.

Pairing requirements:
- same signal date;
- same formal PIT eligible universe;
- same `k_d` where a k-name null is required;
- same next-open entry;
- same exit horizon;
- same 40 bp cost;
- same fail-closed missing-price treatment.

## 10. Discovery / validation split

By `signal_date`:

Discovery:
`2023-01-01 through 2024-12-31`

Validation:
`2025-01-01 through 2026-10-31`

Horizon-specific maturity rule:
only events whose frozen exit date is observable by the research data cutoff may enter that horizon's statistics.

### Sequential opening rule

1. Build and audit the accounting event panel with no returns attached.
2. Open **Discovery returns only**.
3. Apply the frozen Discovery gate below.
4. If Discovery fails, set challenger = `FAIL` and do **not** open Validation returns.
5. Only if Discovery passes may Validation returns be opened.

This rule prevents validation data from influencing rescue decisions.

## 11. Minimum sample sufficiency

At the primary 20-session horizon:

Discovery must have at least:
- 80 selected company-events;
- 40 unique tickers;
- 20 distinct signal dates.

Validation must have at least:
- 80 selected company-events;
- 40 unique tickers;
- 20 distinct signal dates.

If performance gates are otherwise satisfied but sample sufficiency is not met, legal state = `INCONCLUSIVE`, not PASS.

For the final latest-3M promotion gate, there must be at least:
- 10 matured primary-horizon trades;
- 5 distinct signal dates.

Below that => promotion cannot pass.

## 12. Discovery gate

At the 20-session primary horizon, Discovery passes only if all are true:
1. sample sufficiency is met;
2. challenger net mean return > 0;
3. challenger net median return > 0;
4. challenger mean after removing the best 5 events > 0;
5. date-block mean excess vs N0 > 0;
6. date-block mean excess vs N1 > 0;
7. challenger result is not dependent on one ticker contributing more than 20% of total positive PnL.

Failure of any item => `FAIL` and validation remains unopened.

## 13. Validation gate

If and only if Discovery passes, Validation at the 20-session primary horizon passes only if all are true:
1. sample sufficiency is met;
2. challenger net mean return > 0;
3. challenger net median return > 0;
4. challenger mean after removing the best 5 events > 0;
5. date-block mean excess vs N0 > 0;
6. date-block mean excess vs N1 > 0;
7. bootstrap 95% CI for date-block excess vs N1 has lower bound > 0;
8. challenger mean lies above the 95th percentile of the N3 matched-random empirical distribution;
9. no single ticker contributes more than 20% of total positive PnL.

Failure of any item => `FAIL`.

Passing this gate yields only:
`RESEARCH_VALIDATION_PASS`

It does **not** grant production authority.

## 14. Mandatory reporting

For every opened horizon report:
- event count;
- unique tickers;
- signal-date count;
- signals per month;
- mean;
- median;
- win rate;
- remove-best 1 / 3 / 5;
- MAE;
- MFE;
- date-block excess vs N0;
- date-block excess vs N1;
- N2 comparison;
- N3 empirical percentile;
- bootstrap CI;
- year-by-year;
- regime splits;
- industry subgroups within electronics;
- concentration of positive and negative PnL by ticker.

No metric may be suppressed because it is unfavorable.

## 15. Final promotion gates — explicitly outside the initial research pass

Even a `RESEARCH_VALIDATION_PASS` cannot become Selection Core until all existing HENGCE hard laws are separately satisfied:
- latest 3 months total PnL > 0;
- strong-market latest-3M loss = KILL;
- sufficient actual trade count/frequency/capital efficiency;
- finite-capital portfolio accounting;
- contemporaneous TAIEX outperformance;
- cross-cycle evidence extending beyond the 2023-2026 initial panel toward the required long-cycle standard (~2018-2026) if PIT data can be acquired;
- bear/weak-market behavior;
- no lifecycle duplication artifact;
- no production promotion from event means alone.

If earlier PIT accounting data cannot be acquired for cross-cycle proof, final promotion remains `DATA_BLOCKED` even if 2023-2026 research validation passes.

## 16. Forbidden rescue paths

If V0.1 fails, do not:
- change `>= 0` to a tuned tolerance;
- drop the weakest of the six conditions after seeing returns;
- replace YoY with QoQ because it looks better;
- change receivable/inventory denominators after seeing winners;
- add price/volume/institutional-flow confirmation to rescue it;
- condition on familiar winners;
- change primary horizon away from 20 sessions;
- choose the best secondary horizon as the new headline;
- alter k after outcomes;
- reopen Validation after Discovery failure.

Any genuinely new mechanism requires a new challenger ID and new preregistration before its returns are inspected.

## 17. Frozen next command

After persistence and re-read of this file:

`BUILD_IF07_PIT_ACCOUNTING_EVENT_PANEL_WITHOUT_RETURNS`

Only after that panel passes schema/coverage/provenance audit may Discovery forward returns be attached.
