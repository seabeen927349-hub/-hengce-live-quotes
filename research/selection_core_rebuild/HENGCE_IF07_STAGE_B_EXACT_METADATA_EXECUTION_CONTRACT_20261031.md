# HENGCE IF-07 V0.1 — Stage B Exact-Metadata Execution Contract

Date frozen: 2026-10-31  
Branch: `research/selection-core-rebuild-20261031`  
Challenger: `IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1`  
Parent authority: existing V0.1 preregistration + implementation contract + pre-return erratum  
Stage A authority: `HENGCE_IF07_STAGE_A_V0_2_NO_RETURN_GATE_RESULT_20261031.md`  
Forward returns inspected: `NO`  
Trading / production authority: `NONE`

## 1. Purpose

This document freezes the handoff from Stage A accounting-only candidates to Stage B exact official electronic-report metadata.

It creates no new alpha rule and changes no preregistered threshold. Its sole purpose is to prevent identity drift, broad re-acquisition, timestamp substitution, and post-hoc sample rescue.

## 2. Stage A input identity lock

Stage B may accept only the exact Stage A V0.2 rows artifact produced by workflow run `41176211171` / job `124464189390`.

Frozen Stage A facts:
- total company-quarter rows: `3560`;
- accounting 6/6 pre-metadata candidates: `187`;
- unique candidate tickers: `128`;
- candidate period counts:
  - 2022Q4: `41`
  - 2023Q1: `23`
  - 2023Q2: `27`
  - 2023Q3: `23`
  - 2023Q4: `19`
  - 2024Q1: `17`
  - 2024Q2: `22`
  - 2024Q3: `15`

The existing Actions artifact containing the rows has artifact ID `13032993979` and ZIP digest:

`sha256:2366448ec259065df5e2a515a11bb9fbf0a5c40b806607f6ac1edce0385ee782`

This ZIP digest is **not** a substitute for a file-level hash of the contained Stage A rows JSON. The file-level SHA-256 must be calculated only after the exact existing rows file is lawfully available; it must never be invented.

No other source may be used to reconstruct or infer the 187 identities from counts.

## 3. Offline admission gate

Frozen script:

`if07_stage_b_candidate_manifest_gate_no_network.py`

The script performs no network access. It must verify before producing a Stage B request manifest:
- Stage A artifact identity is exact;
- explicit no-return boundary is intact;
- total rows = `3560`;
- candidates = `187`;
- unique candidate tickers = `128`;
- exact period distribution matches Stage A;
- no duplicate `(ticker, fiscal quarter)` rows;
- every admitted candidate has a complete accounting pair and all six booleans true;
- Stage A has not already attached upload timestamp, signal date, PIT membership, price, or market outcome;
- Stage A bulk-correction early-exclusion flags are false for admitted candidates;
- current and prior accounting payloads remain finite and structurally complete.

On any mismatch:

`FAIL_CANDIDATE_MANIFEST_ADMISSION`

and no t57 request may be made from that manifest.

## 4. Exact Stage B metadata authority

For each admitted candidate `(ticker, Y, Q)`, Stage B metadata authority remains only:

`https://doc.twse.com.tw/server-java/t57sb01`

Both `(Y,Q)` and `(Y-1,Q)` must satisfy the frozen implementation contract:
1. exactly one usable `IFRSs合併財報` row for that fiscal quarter;
2. parseable official `上傳日期`;
3. final `財務報告更(補)正` exactly equals Traditional-Chinese `無`.

Blank, missing, non-`無`, duplicate, ambiguous, rate-limited, or structurally unresolved metadata => fail closed for that candidate.

No broad all-market metadata index is authorized. The invalid historical 794-pair metadata artifact remains forbidden.

## 5. Timestamp semantics

Only the **current** `(Y,Q)` official `上傳日期` controls event availability and later signal-date mapping.

The prior `(Y-1,Q)` upload timestamp is required to be parseable as part of the original-filing metadata gate, but it has zero authority over the current event's signal time.

No substitute is legal:
- ZIP member timestamp;
- HTTP `Date` / `Last-Modified`;
- board approval date;
- quarter end;
- statutory filing deadline;
- inferred or median filing time.

## 6. Stage B output — still no returns

A legal exact-metadata output may contain only pre-outcome fields, including:
- ticker, fiscal year, quarter;
- Stage A input file SHA-256;
- current and prior t57 row identifiers / source provenance;
- current and prior exact upload timestamps;
- current and prior exact correction strings;
- exact-row-count / duplicate / ambiguity status;
- pass/fail and exclusion reason.

It must not contain:
- prices;
- forward returns;
- MAE/MFE;
- null returns;
- winner labels;
- post-signal outcomes.

## 7. Stage C boundary after metadata

Stage B metadata PASS does not itself authorize returns.

The next legal no-return transformations are:
1. map current upload timestamp to `signal_date` using the frozen Asia/Taipei 13:30 cutoff and canonical TWSE trading sessions;
2. enforce canonical daily TWSE electronics membership on the resolved signal date;
3. deduplicate to one Selection event per ticker/fiscal quarter;
4. persist and reread a count-only panel audit;
5. test preregistered Discovery count sufficiency, including the `>=20` distinct signal-date block requirement.

Only after those gates pass may Discovery returns be attached. Validation returns remain forbidden until Discovery itself passes.

## 8. Current user stop rule

The user has ordered: no further downloading / acquisition expansion now that the required historical data are known to be sufficient.

Therefore, as of this contract's creation:
- do not download Actions artifact `13032993979`;
- do not rerun Stage A;
- do not query t57;
- do not rebuild the candidate list from other sources;
- do not open forward returns.

The Stage B execution code may be prepared and audited offline, but Stage B data retrieval remains `NOT_STARTED` until the exact frozen candidate manifest becomes lawfully available under a later explicit instruction.

## 9. Governance state

`STAGE_A = PASS_NO_RETURN`

`STAGE_B_MANIFEST_ADMISSION_CODE = PREPARED_NOT_EXECUTED`

`STAGE_B_EXACT_METADATA_RETRIEVAL = NOT_STARTED`

`DATA_ACQUISITION_EXPANSION = CLOSED`

`FORWARD_RETURN_LOCK = CLOSED`
