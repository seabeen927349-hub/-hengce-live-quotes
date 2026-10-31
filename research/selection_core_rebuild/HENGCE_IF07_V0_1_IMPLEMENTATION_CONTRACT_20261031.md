# HENGCE IF-07 Earnings Quality ZERO-RED-FLAG V0.1 — Implementation Contract

Date frozen: 2026-10-31  
Branch: `research/selection-core-rebuild-20261031`  
Parent preregistration: `HENGCE_IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1_PREREG_20261031.md`  
Status: `FROZEN_BEFORE_PANEL_BUILD_AND_BEFORE_RETURNS`  
Forward-return data inspected for this challenger: `NO`  
Trading / production authority: `NONE`

## 0. Purpose and non-mutation rule

This document freezes data-engineering semantics that the preregistration left operationally implicit. It may not alter the six accounting conditions, thresholds, universe, horizons, nulls, Discovery/Validation split, or kill rules.

If a source ambiguity cannot be resolved under this contract, the affected company-quarter is excluded. The ambiguity must not be resolved after looking at returns.

## 1. Source authority

### Current quarter accounting values

Source must be the official MOPS direct iXBRL filing for the current company-quarter:

`https://mopsov.twse.com.tw/server-java/FileDownLoad?functionName=t164sb01&step=9&co_id={ticker}&year={western_year}&season={quarter}&report_id=C`

The electronic-report metadata row must identify the filing as `IFRSs合併財報`.

### Prior-year same-quarter accounting values

The prior-year values required by the preregistration must be sourced from the **separate original prior-year same-quarter filing**, not from the comparative columns embedded in the current-year filing.

Reason for the strict choice:
- a current filing can contain restated or reclassified prior-period comparatives;
- the preregistration requires the current report and prior-year same-quarter report both to be parseable;
- the revision law forbids later information from silently replacing historical source values.

Therefore:
- `(Y,Q)` signal values come from original `(Y,Q)` filing;
- comparator values come from original `(Y-1,Q)` filing;
- current-filing comparative columns are audit-only and have zero signal authority.

This rule is frozen before returns and cannot be relaxed for sample size.

## 2. Electronic-report metadata / original-filing gate

Metadata source:
`https://doc.twse.com.tw/server-java/t57sb01`

One blank-year query per ticker may be used to index all available IFRS consolidated-report rows.

For **both** `(Y,Q)` and `(Y-1,Q)`:
1. exactly one usable `IFRSs合併財報` row must be identifiable for that fiscal quarter;
2. the row must provide a parseable `上傳日期` timestamp;
3. the final `財務報告更(補)正` field must be **exactly the Traditional-Chinese string `無`**.

Fail closed if the correction field is:
- blank;
- missing;
- any string other than exact `無`;
- structurally ambiguous;
- associated with duplicate competing rows that cannot be resolved without judgment.

Known pre-return control evidence:
- 2330 2023 Q1-Q4 => exact `無`;
- known corrected case 2464 2024Q2 => blank correction field and is therefore excluded by this rule.

No later return result may change this gate.

## 3. Current report availability time

`upload_ts` = current `(Y,Q)` official electronic-report `上傳日期`, interpreted in `Asia/Taipei`.

Signal-time mapping remains exactly as preregistered:

`signal_date = first TWSE trading day whose regular market close timestamp occurs strictly after upload_ts`

Implementation:
- regular TWSE cash-market close cutoff = 13:30:00 Asia/Taipei;
- if `upload_ts < signal_date 13:30:00` on a canonical TWSE trading session, the filing can first be used at that session's after-close signal;
- if upload is at/after 13:30:00, or on a non-trading day, first eligible signal date is the next canonical TWSE trading session;
- exact equality to 13:30:00 is treated as **after cutoff** and rolls to the next trading session;
- if the trading-session calendar needed to resolve the timestamp is missing, exclude the event.

Entry remains the next TWSE open after `signal_date`; no return is attached during panel construction.

## 4. Formal PIT electronics membership

The 468-ticker file `IF07_ELECTRONICS_ACQUISITION_TICKER_UNION_2022_2026.json` is an acquisition superset only and has **zero** formal universe authority.

Formal event eligibility requires:
- the ticker must appear in the canonical `TWSE_ELECTRONICS_{year}.zip -> electronics_{year}.csv` on the resolved `signal_date`.

No annual static classification may substitute for signal-date membership.

If canonical electronics coverage does not extend to the resolved signal date, the event is `DATA_BLOCKED` / excluded rather than inferred.

## 5. Direct iXBRL parser contract

The official iXBRL response is parsed as HTML tables.

Required statement tables must expose the required accounting codes. The parser uses **accounting code as primary identity**, not company-specific label text.

Frozen required code map:
- `4000` => `Revenue_YTD`
- `5000` => `COGS_YTD`
- `6900` => `OperatingIncome_YTD`
- `AAAA` => `CFO_YTD`
- `1170` => `AR` (net accounts receivable)
- `130X` => `Inventory`
- `1XXX` => `Assets`
- `2XXX` => `Liabilities`

Optional audit-only code:
- `B02700` => acquisition of property, plant and equipment / capex proxy.

Rules:
- code matching is exact after harmless HTML/pandas normalization such as `4000.0 -> 4000`;
- no post-return company-specific alias map;
- if a required code is missing, duplicated with unresolved conflicting values, or nonnumeric => exclude the company-quarter;
- label text may be retained for provenance but may not override a conflicting code.

## 6. Period-column selection

### Balance-sheet stocks

For `AR`, `Inventory`, `Assets`, `Liabilities` use the quarter-end column corresponding exactly to `(Y,Q)` in the original filing.

For the prior comparator use the quarter-end column corresponding to `(Y-1,Q)` in the separate original prior-year filing.

### Flow / income values

For `Revenue_YTD`, `COGS_YTD`, `OperatingIncome_YTD`, `CFO_YTD` use the **year-to-date cumulative period from January 1 through the current quarter end** in the filing.

Thus:
- Q1 => Jan 1 through Mar 31;
- Q2 => Jan 1 through Jun 30;
- Q3 => Jan 1 through Sep 30;
- Q4 => full fiscal year Jan 1 through Dec 31.

If the statement shows both single-quarter and YTD columns, the parser must select YTD.

If the YTD period cannot be identified unambiguously from the table header, exclude the event.

## 7. Numeric parsing

Frozen numeric rules:
- commas and ordinary whitespace removed;
- parenthesized numeric value => negative;
- explicit leading minus => negative;
- `--`, empty string, textual N/A, infinity, or unparsable content => missing;
- no zero-imputation;
- all denominators required by preregistration must be strictly positive and finite.

Currency units are taken as reported; because every derived V0.1 condition is a ratio or same-unit growth comparison, no post-hoc unit rescaling is permitted except deterministic normalization of a whole statement when its header explicitly states the unit.

## 8. Exact derived-variable implementation

No change from preregistration:

`cash_conversion = CFO_YTD / Revenue_YTD`

`D_CASH = cash_conversion - cash_conversion_prev`

`REV_YOY = Revenue_YTD / Revenue_YTD_prev - 1`

`AR_YOY = AR / AR_prev - 1`

`AR_GAP = REV_YOY - AR_YOY`

`COGS_YOY = COGS_YTD / COGS_YTD_prev - 1`

`INV_YOY = Inventory / Inventory_prev - 1`

`INV_GAP = COGS_YOY - INV_YOY`

`GM = (Revenue_YTD - COGS_YTD) / Revenue_YTD`

`D_GM = GM - GM_prev`

`OM = OperatingIncome_YTD / Revenue_YTD`

`D_OM = OM - OM_prev`

`LEV = Liabilities / Assets`

`D_LEV = LEV - LEV_prev`

Selection iff all six are true:
- `D_CASH >= 0`
- `AR_GAP >= 0`
- `INV_GAP >= 0`
- `D_GM >= 0`
- `D_OM >= 0`
- `D_LEV <= 0`

No tolerances.
No rounding before comparisons beyond normal floating-point calculation.
No condition may be removed after seeing outcomes.

## 9. Panel date range

Accounting acquisition must include enough lag history for all legal signal events.

Minimum filing periods required:
- prior input begins: `2022 Q1`;
- legal challenger current filings begin: `2023 Q1`;
- legal challenger current filings end at the latest quarter whose upload timestamp can resolve to a `signal_date <= 2026-10-31` and whose canonical PIT electronics membership is available.

Because the canonical 2026 electronics archive currently ends on 2026-10-27, any resolved event after that date is unavailable for PIT membership under the current corpus and must be excluded / reported as coverage-blocked until the canonical archive is extended.

## 10. Panel contents — strict no-return boundary

The accounting event panel may contain:
- ticker / company name;
- fiscal year / quarter;
- current upload timestamp;
- resolved signal date;
- current and prior filing identifiers / hashes;
- correction-gate status;
- exact raw accounting values;
- derived accounting variables;
- six condition booleans;
- final V0.1 selected boolean;
- canonical PIT electronics membership boolean;
- missing/exclusion reason;
- parser/source provenance.

It must **not** contain:
- future close/open prices;
- forward returns;
- MAE/MFE;
- null returns;
- winner labels;
- any post-signal market outcome.

## 11. Audit before opening Discovery returns

Before any Discovery return is attached, persist a panel audit reporting at minimum:
- acquisition ticker count;
- report-row count by year/quarter;
- exact-`無` correction-gate pass/fail counts;
- iXBRL download success/fail counts;
- required-code completeness by code;
- current+prior complete-pair count;
- resolved signal-date count;
- PIT electronics membership pass/fail count;
- selected event count by year/quarter and signal month;
- exclusion-reason counts;
- duplicate/ambiguity counts;
- source hashes / script commit.

No performance metric is permitted in this audit.

If the panel cannot meet the preregistration's Discovery sample sufficiency **as a count-only fact**, the legal state becomes `INCONCLUSIVE` without opening returns.

## 12. No-rescue engineering rule

Engineering bug fixes are allowed only when they restore this frozen contract and are separately versioned/logged.

They may not:
- change accounting concepts;
- change thresholds;
- substitute current-filing comparative prior values for prior original filing values;
- accept corrected/ambiguous reports to increase N;
- broaden the formal universe;
- alter signal timestamps based on outcomes;
- use returns to decide parser aliases.

## 13. Next legal command

`BUILD_IF07_V0_1_PIT_ACCOUNTING_PANEL_NO_RETURNS -> PERSIST PANEL AUDIT -> RE_READ AUDIT -> ONLY IF COUNT/INTEGRITY GATES PASS, OPEN DISCOVERY RETURNS`
