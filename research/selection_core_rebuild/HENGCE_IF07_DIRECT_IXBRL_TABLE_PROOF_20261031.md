# HENGCE IF-07 — Direct Official iXBRL Table Proof

Date: 2026-10-31  
Branch: `research/selection-core-rebuild-20261031`  
Scope: data engineering / PIT accounting source proof only  
Forward-return data inspected: `NO`  
Trading / production authority: `NONE`

## Why this proof exists

The prior official-source capability probes established that GitHub Actions can reach MOPS aggregate financial tables and TWSE electronic-report metadata. This proof establishes a stricter source path: direct company-quarter official iXBRL filing bytes can be downloaded and parsed into the exact accounting concepts required by preregistered challenger `IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1`.

No price or forward-return data were requested or used.

## Official direct-download endpoint

Verified official endpoint pattern:

`https://mopsov.twse.com.tw/server-java/FileDownLoad?functionName=t164sb01&step=9&co_id={ticker}&year={western_year}&season={quarter}&report_id=C`

Control request:
- ticker: `2330`
- fiscal period: `2023 Q1`
- HTTP status: `200`
- content-disposition filename: `tifrs-fr1-m1-ci-cr-2330-2023Q1.html`
- response size: `767,246` bytes
- response type observed: Inline XBRL HTML
- SHA-256 observed in the original-filing probe: `61e474d63c807784549e6c82e697db8df04fc37f3a790953c19cf836a3c29ca5`

## Direct HTML-table parsing proof

The downloaded official iXBRL HTML was parsed with `pandas.read_html` on a GitHub Actions runner. It produced 35 tables.

Core statements were directly identifiable:
- table 0: Balance Sheet, 93 rows;
- table 1: Statement of Comprehensive Income, 61 rows;
- table 2: Statement of Cash Flows, 81 rows.

The following preregistration-required concepts were found directly in those tables with stable accounting codes and values.

| Concept | Accounting code | 2023Q1 current value | 2022Q1 comparative shown in filing |
|---|---:|---:|---:|
| Revenue | `4000` | 508,632,973 | 491,075,873 |
| COGS | `5000` | 222,132,581 | 217,872,707 |
| Gross profit net | `5950` | 286,500,392 | 273,203,166 |
| Operating income | `6900` | 231,238,157 | 223,790,118 |
| Accounts receivable, net | `1170` | 147,715,125 | 212,846,891 |
| Inventory | `130X` | 216,067,981 | 200,118,682 |
| Total assets | `1XXX` | 5,045,844,348 | 3,992,676,667 |
| Total liabilities | `2XXX` | 1,952,946,750 | 1,671,207,913 |
| Net cash from operating activities | `AAAA` | 385,244,745 | 372,169,688 |
| Acquisition of PP&E | `B02700` | -302,498,628 | -262,134,719 |

All values above came from the official downloaded iXBRL tables. The filing itself also supplies prior-year same-quarter comparative columns.

## Important implementation boundary

This proof does **not** decide which source will supply the prior-year same-quarter inputs in the production research panel.

The preregistration explicitly requires that the current report and the prior-year same-quarter report both be parseable, and it forbids later corrections/restatements from silently overwriting historical signal values. Therefore the implementation contract must freeze the comparator source before any returns are opened.

Until that contract is frozen, current-filing comparative columns may be used only as an audit cross-check, not silently substituted as the signal's prior-year source.

## Electronic-report metadata efficiency proof

The same probe confirmed that querying the TWSE electronic-book index with `year` left blank returns many years for one ticker in a single response.

For 2330 the blank-year query returned 54 IFRS consolidated-report rows, spanning multiple years. This means upload timestamps and the `財務報告更(補)正` field can be indexed with one metadata request per ticker rather than one request per ticker-year.

## Original-filing correction gate already established

Separate probe evidence showed:
- 2330 2023 Q1-Q4 rows have the final correction field exactly `無`;
- known correction case 2464 2024Q2 has a blank final correction field, while adjacent quarters show `無`.

Frozen conservative acquisition rule for subsequent implementation contract:
- only an electronic-report row whose correction field is **exactly** `無` may be used;
- blank, non-`無`, malformed, missing, or ambiguous correction status => fail closed / exclude;
- no forward return may be used to relax this rule.

## Workflow provenance

The direct iXBRL table probe executed in GitHub Actions run `41172549256`.

The data-probe steps themselves succeeded. The overall workflow was marked failure only because the final receipt-persistence `git push` was rejected as non-fast-forward after the branch advanced concurrently. This Git race has no bearing on the source/data proof.

Artifact containing the generated receipts was uploaded successfully in that run as artifact ID `13031965972`.

## Verdict

`DIRECT_OFFICIAL_IXBRL_PARSE_CAPABILITY = PASS`

This is a data-capability result only.

It is not:
- an alpha result;
- a Discovery result;
- a Validation result;
- a Selection Core promotion.

Next legal step remains: freeze the exact implementation contract and build the PIT accounting panel with **no returns attached**.
