# HENGCE IF-07 — Fast iXBRL Context Parser Proof

Date: 2026-10-31  
Branch: `research/selection-core-rebuild-20261031`  
Forward returns inspected: `NO`  
Trading / production authority: `NONE`

## Purpose

Prove a faster parser for the already-frozen IF-07 accounting fields before running the no-return Stage A accounting upper-bound build.

The parser does not infer columns by ordinal position. It reads:
- the frozen MOPS account code in the filing table row;
- inline-XBRL `ix:nonFraction` facts;
- the referenced XBRL context period;
- non-segmented consolidated facts only;
- explicit Jan-1-to-quarter-end YTD contexts for flows;
- exact quarter-end instant contexts for balance-sheet stocks.

Frozen account codes remain unchanged:
- `4000` Revenue_YTD
- `5000` COGS_YTD
- `6900` OperatingIncome_YTD
- `AAAA` CFO_YTD
- `1170` AR
- `130X` Inventory
- `1XXX` Assets
- `2XXX` Liabilities

## Control-oracle correction

The first probe correctly parsed 2454 2024Q2 YTD values but was initially marked FAIL because the control oracle mistakenly contained Apr-Jun single-quarter income-statement values.

This was rejected because the already-frozen `HENGCE_IF07_PERIOD_COLUMN_SEMANTICS_PROOF_20261031.md` explicitly establishes:
- 2454 2024Q2 Revenue single-quarter = 127,271,121;
- 2454 2024 H1 Revenue YTD = 260,729,268;
- IF-07 V0.1 requires the YTD value.

The oracle was corrected before any IF-07 forward-return inspection. Parser logic and model rules were not changed.

## Exact control results

GitHub Actions run: `41175338312`  
Job: `124461606842`

### 2330 — 2023Q1
All 8 exact checks PASS:
- Revenue_YTD 508,632,973
- COGS_YTD 222,132,581
- OperatingIncome_YTD 231,238,157
- CFO_YTD 385,244,745
- AR 147,715,125
- Inventory 216,067,981
- Assets 5,045,844,348
- Liabilities 1,952,946,750

### 2454 — 2024Q2
All 8 exact checks PASS:
- Revenue_YTD 260,729,268
- COGS_YTD 128,692,316
- OperatingIncome_YTD 57,135,880
- CFO_YTD 75,144,111
- AR 45,889,387
- Inventory 53,578,351
- Assets 681,374,287
- Liabilities 290,750,665

For 2454 the parser selected `From20240101To20240630` for all flow fields and `AsOf20240630` for balance-sheet fields.

## Verdict

`FAST_IXBRL_CONTEXT_PARSER = PASS`

Boundary:
- this is parser engineering evidence only;
- it creates no alpha claim;
- Stage A must still fail closed on ambiguous/missing facts;
- a slower independent table parser is retained as fallback for fast-parser failures so parser coverage cannot silently manufacture a low candidate count.
