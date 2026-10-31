# HENGCE IF-07 — Q2/Q3/Q4 Period-Column Semantics Proof

Date: 2026-10-31  
Branch: `research/selection-core-rebuild-20261031`  
Forward returns inspected: `NO`

## Purpose

Prevent a parser error in which single-quarter income-statement values are mistaken for the YTD values required by the frozen IF-07 implementation contract.

## Q2 control — 2454, 2024 Q2

Official filing: `tifrs-fr1-m1-ci-cr-2454-2024Q2.html`.

Balance sheet columns:
- 2024-06-30
- 2023-12-31
- 2023-06-30

Comprehensive-income columns include both:
- single quarter: `2024/4/1 To 6/30`, `2023/4/1 To 6/30`;
- YTD: `2024/1/1 To 6/30`, `2023/1/1 To 6/30`.

Example code `4000` Revenue:
- single-quarter 2024 Q2 = 127,271,121;
- YTD 2024 H1 = 260,729,268.

Cash-flow columns are YTD:
- `2024/1/1 To 6/30`
- `2023/1/1 To 6/30`.

## Q3 control — 3037, 2025 Q3

Official filing: `tifrs-fr1-m1-ci-cr-3037-2025Q3.html`.

Comprehensive-income columns include both:
- single quarter: `2025/7/1 To 9/30`, `2024/7/1 To 9/30`;
- YTD: `2025/1/1 To 9/30`, `2024/1/1 To 9/30`.

Example code `4000` Revenue:
- single-quarter 2025 Q3 = 33,994,419;
- YTD 2025 nine months = 96,549,996.

Cash-flow columns are YTD:
- `2025/1/1 To 9/30`
- `2024/1/1 To 9/30`.

## Q4 control — 2330, 2023 Q4

Official filing: `tifrs-fr1-m1-ci-cr-2330-2023Q4.html`.

Comprehensive-income and cash-flow columns are full-year:
- `2023/1/1 To 12/31`
- `2022/1/1 To 12/31`.

## Frozen parser consequence

The parser must identify the YTD column by the explicit date interval beginning on January 1 of the filing fiscal year and ending on the quarter-end date.

It must **not** select a numeric column by ordinal position alone.

For balance-sheet stocks, select the exact current quarter-end date in the separate original filing.

Failure to identify an unambiguous period header => exclude the company-quarter.

Action provenance: GitHub Actions run `41173162667`, artifact ID `13031786680`.
