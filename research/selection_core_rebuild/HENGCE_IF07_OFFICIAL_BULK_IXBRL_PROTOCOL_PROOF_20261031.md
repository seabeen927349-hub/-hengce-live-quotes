# HENGCE IF-07 — Official MOPS Bulk iXBRL Protocol Proof

Date: 2026-10-31  
Branch: `research/selection-core-rebuild-20261031`  
Scope: source/acquisition engineering only  
Forward returns inspected: `NO`  
Trading / production authority: `NONE`

## 1. Official page and protocol

Official MOPS page:
`https://mopsov.twse.com.tw/mops/web/t203sb02`

The page source was fetched and inspected on GitHub Actions run `41172860771`. The actual HTML contains explicit quarterly download buttons. Example for 2023 Q1:

`window.open('/server-java/FileDownLoad?step=9&functionName=show_file2&fileName=tifrs-2023Q1.zip&filePath=/ifrs/2023/','new1');`

Therefore the official bulk-download endpoint pattern is:

`https://mopsov.twse.com.tw/server-java/FileDownLoad?step=9&functionName=show_file2&fileName=tifrs-{YYYY}Q{Q}.zip&filePath=/ifrs/{YYYY}/`

The page directly exposed fixed quarterly packages for 2022, 2023, 2024, 2025 and 2026, among earlier years.

## 2. Direct bulk ZIP verification

GitHub Actions run `41173046902` directly downloaded the official 2023 Q1 package using the protocol above.

Observed response:
- HTTP status: `200`
- content type: `application/x-zip-compressed; charset=iso-8859-1`
- content disposition: `attachment; filename="tifrs-2023Q1.zip"`
- bytes: `74,465,121`
- SHA-256: `ed0cd5a9e75d522b2e4213d0b22cf66ba1494375055c3288dc88fc8ea3888d70`
- ZIP magic: `true`
- member count: `1,860`
- HTML/iXBRL member count: `1,860`
- XML/XBRL member count: `0`

Verified members include:
- `tifrs-fr1-m1-ci-cr-2330-2023Q1.html`
- `tifrs-fr1-m1-ci-cr-2454-2023Q1.html`

The archive therefore contains many companies, not a single-company response.

## 3. Acquisition consequence

The IF-07 accounting acquisition does not require thousands of direct single-company downloads.

For the currently preregistered 2023-2026 research interval plus the required prior-year comparator history, the minimum quarterly source range is:

`2022 Q1 through 2026 Q3`

This is 19 quarterly bulk packages.

Reasons:
- 2022 is needed as prior-year same-quarter input for 2023 challenger events;
- 2025 Q4 is needed for 2025 Q4 challenger events whose filing/signal occurs in 2026;
- 2026 Q1-Q3 can contain current 2026 challenger inputs;
- 2026 Q4 cannot have a valid filing/signal by 2026-10-31.

## 4. Governance boundary

Bulk archives supply accounting filing bytes only. They do **not** replace:
- official electronic-report `上傳日期` metadata;
- exact `財務報告更(補)正 == 無` gate;
- signal-date canonical `TWSE_LISTED_ELECTRONICS_PIT_DAILY` membership;
- the frozen separate-original-prior-filing comparator rule.

A file from a bulk ZIP is usable only if the corresponding company-quarter survives those independent gates.

## 5. Verdict

`OFFICIAL_BULK_IXBRL_ACQUISITION = PASS`

This is an acquisition-capability result only. It contains no return evidence and grants no Selection or production authority.
