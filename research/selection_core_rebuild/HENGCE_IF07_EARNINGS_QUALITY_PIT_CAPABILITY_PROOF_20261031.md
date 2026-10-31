# HENGCE IF-07 Earnings Quality — PIT Source Capability Proof

Date: 2026-10-31
Branch: `research/selection-core-rebuild-20261031`
Scope: data capability only
Forward-return inspection for a new challenger: `NO`
Challenger defined in this document: `NO`
Trading / production authority: `NONE`

## Purpose

Prove or falsify whether IF-07 Fundamental Quality can be reconstructed point-in-time for TWSE-listed electronics before defining a Selection challenger.

This document does **not** test predictive returns.

## 1. Canonical mother limitation

Direct inspection of `HENGCE_2026_HIST_MOTHER.csv` showed only:

`Date, Ticker, Name, Volume, Turnover, Open, High, Low, Close, Margin_MarginBalance, ForeignNet, TrustNet, TotalNet`.

Therefore the mother corpus does not itself contain the quarterly accounting variables required for IF-07.

## 2. Fugle capability and current connector state

On 2026-10-31, Fugle `list_content_specs` exposed accessible source families including:
- FCNT000091 最近N年損益表
- FCNT000092 最近N年現金流量表
- FCNT000093 最近N年資產負債表
- FCNT000052 最近5年毛利率
- FCNT000066 最近5年營業利益率
- FCNT000141 最近5年應收款項週轉率與週轉天數
- FCNT000143 最近5年存貨週轉率與週轉天數
- FCNT000146 最近5年營運現金流與每股營運現金流
- FCNT000149 最近5年資本支出與每股資本支出

However `get_content` probes returned empty `{}` payloads for 2330 on FCNT000091, FCNT000052 and even FCNT000001 basic data.

Verdict for connector path:
`FUGLE_CONTENT_RETRIEVAL = DATA_BLOCKED`

This does not imply provider-level absence.

## 3. Official TWSE/MOPS company-specific PIT timestamp proof

The TWSE electronic financial-report document index (`doc.twse.com.tw/server-java/t57sb01`) exposes a field named `上傳日期` with date and time to the second.

Verified samples:

| Ticker | Company | Report period | Chinese consolidated report file | `上傳日期` |
|---|---|---|---|---|
| 2330 | 台積電 | 2023 Q1 | `202301_2330_AI1.pdf` | `112/05/12 13:51:34` = 2023-05-12 13:51:34 |
| 2454 | 聯發科 | 2024 Q2 | `202402_2454_AI1.pdf` | `113/08/13 17:27:52` = 2024-08-13 17:27:52 |
| 3037 | 欣興 | 2025 Q3 | `202503_3037_AI1.pdf` | `114/10/30 18:45:28` = 2025-10-30 18:45:28 |
| 2303 | 聯電 | 2026 Q2 | `202602_2303_AI1.pdf` | `115/07/29 17:18:33` = 2026-07-29 17:18:33 |

The 2303 2026Q2 PDF was opened directly and confirmed to contain:
- consolidated balance sheet;
- consolidated statement of comprehensive income;
- consolidated statement of cash flows.

It also displayed a board approval/release date of 2026-07-29.

### Reliability correction

One intermediate browser-agent run incorrectly asserted that 2026Q2 had not yet occurred. That statement was rejected immediately because the research date is 2026-10-31. A separate direct re-query found the actual 2303 2026Q2 report and upload timestamp above.

The rejected erroneous statement has zero evidentiary weight and is not used anywhere in the capability verdict.

## 4. Machine-readable accounting-field proof

MOPS XBRL-viewer pages expose financial statements as DOM-readable HTML tables. No price or forward-return data were used.

### 2330 台積電 — 2023 Q1

Verified page-level fields and values (NT$ thousand):
- `營業收入合計` = 508,632,973
- `營業成本合計` = 222,132,581
- `營業毛利（毛損）淨額` = 286,500,392
- `營業利益（損失）` = 231,238,157
- `應收帳款淨額` = 147,715,125
- `存貨` = 216,067,981
- `資產總計` = 5,045,844,348
- `負債總計` = 1,952,946,750
- `營業活動之淨現金流入（流出）` = 385,244,745
- `取得不動產、廠房及設備` = -302,498,628

All ten were confirmed as DOM-readable HTML table text.

### 2454 聯發科 — 2024 Q2

Verified page-level fields and values (NT$ thousand):
- `營業收入` = 127,271,121
- `營業成本` = 65,134,699
- `營業毛利（毛損）淨額` = 62,136,422
- `營業利益（損失）` = 24,956,016
- `應收帳款淨額` = 45,889,387
- `存貨` = 53,578,351
- `資產總計` = 681,374,287
- `負債總計` = 290,750,665
- `營業活動之淨現金流入（流出）` = 75,144,111
- `取得不動產、廠房及設備` = -6,961,649

All ten were confirmed as DOM-readable HTML table text.

### Parser portability implication

2330 and 2454 use the same economically relevant labels for the ten required accounting concepts, with only harmless presentation variation such as `營業收入` vs `營業收入合計`.

A fail-closed parser can therefore use a frozen alias map rather than company-specific rules.

## 5. PIT law for future panel construction

For any company-quarter, accounting information is not usable before the official TWSE electronic-report `上傳日期` timestamp.

Permanent rule:
`availability_time = official_upload_timestamp`

Forbidden substitutions:
- quarter end date;
- earnings period end;
- inferred publication date;
- statutory deadline, if the actual upload timestamp is available.

If an official upload timestamp cannot be obtained, that company-quarter is missing and must fail closed.

## 6. Capability verdict

### IF-07 novelty
`PASS`

### IF-07 source/data capability
`PASS`

Basis:
1. company-specific PIT timestamps are directly available and verified across 2023-2026 samples;
2. complete financial-report PDFs exist;
3. key accounting fields are machine-readable from MOPS HTML tables;
4. the same ten-field concept map worked on two distinct major electronics issuers;
5. no forward return was inspected to reach this verdict.

### Important boundary

`DATA_CAPABILITY_PASS != ALPHA_PASS`

No Selection challenger has been tested.
No predictive claim has been made.
No production authority exists.

## 7. Next legal step

Because IF-07 is both novel and data-capable, the next legal step under the frozen governance is:

`WRITE_ONE_SEPARATELY_VERSIONED_IF07_CHALLENGER_PREREGISTRATION -> PERSIST -> RE_READ -> ONLY_THEN_ALLOW_FORWARD_RETURN_TESTING`

The preregistration must define, before any forward-return calculation:
- exact accounting transforms;
- signal-date schedule and PIT cutoff;
- missing-data policy;
- cross-sectional ranking and selected count k;
- tie-breaking;
- overlap rules;
- discovery/validation split;
- N0/N1/N2/N3 comparison contract;
- kill criteria and no-rescue rule.
