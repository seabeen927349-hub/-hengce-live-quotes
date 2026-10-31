# HENGCE Selection Core — IF07 Earnings Quality Top100 V1.0 Preregistration

Date frozen: 2026-10-31 (Asia/Taipei)
Branch: `research/selection-core-rebuild-20261031`
ID: `IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_TOP100_V1_0`
State: `PREREGISTERED_NO_FORWARD_RETURN`
Production / trading authority: `NONE`

## 0. Governance

This is a separately versioned challenger. It does not mutate, rescue, reopen, or reinterpret
`IF07_EARNINGS_QUALITY_ZERO_RED_FLAG_V0_1`, whose controlling state remains
`EXECUTION_SPEC_BLOCKED`.

No forward return from the 187 Stage-A candidates has been inspected under either the old
V0.1 or this V1.0 before this preregistration.

The old 187-event Stage-A accounting candidate authority is reused only because:
- it was created before any IF07 forward return was opened;
- the economic accounting rule is unchanged;
- its parser cross-check had zero mismatches;
- re-acquiring accounting statements would add no economic information and would increase
  data-engineering degrees of freedom.

## 1. Economic hypothesis — unchanged ZERO_RED_FLAG

For current fiscal year Y and quarter Q versus prior-year same-quarter (Y-1,Q), require all six:

1. `D_CASH = CFO_YTD/Revenue_YTD - CFO_YTD_prev/Revenue_YTD_prev >= 0`
2. `AR_GAP = Revenue_YOY - AR_YOY >= 0`
3. `INV_GAP = COGS_YOY - Inventory_YOY >= 0`
4. `D_GM = GM - GM_prev >= 0`
5. `D_OM = OM - OM_prev >= 0`
6. `D_LEV = Liabilities/Assets - Liabilities_prev/Assets_prev <= 0`

No magnitude threshold, weights, percentile threshold, growth floor, price/volume confirmation,
institutional-flow filter, margin-financing filter, TDCC filter, broker filter, familiar-name whitelist,
or post-hoc exception is allowed.

## 2. Formal universe — dynamic Top100 TWSE electronics

An accounting event can enter this V1.0 research universe only after its official upload timestamp
has resolved a legal `signal_date`.

On that `signal_date`:

1. Base membership = `TWSE_LISTED_ELECTRONICS_PIT_DAILY`.
2. Compute each eligible ticker's median daily Turnover over the latest 60 TWSE trading sessions
   ending on `signal_date`.
3. Require at least 50 non-missing Turnover observations in that 60-session window.
4. Sort by median Turnover descending; tie-break by ticker ascending.
5. Retain exactly the first 100 names (or all names if fewer than 100 meet the history requirement).
6. The candidate event is in-scope iff its ticker belongs to this Top100 set.

The Top100 rule is applied only after metadata resolves signal dates. Missing metadata may never be
used to infer that a candidate is outside Top100.

## 3. PIT metadata law

Official source: TWSE electronic financial-report t57 index.
Availability time = official `上傳日期` timestamp.
Signal date = first TWSE trading day whose official close occurs strictly after availability time.
Earliest original consolidated filing only; later corrections/restatements have zero authority to
overwrite the original historical event.

If current or prior-year same-quarter original metadata is ambiguous, duplicated, corrected,
missing, or unparseable, the candidate is structurally ineligible — but only after transport itself
has completed successfully for that ticker.

## 4. Frozen transport contract — complete-or-block

The metadata-acquisition contract is data transport, not stock selection.

Candidate ticker authority:
- exact 128 unique tickers from the already-frozen 187-event Stage-A authority;
- deterministic ticker-ascending order;
- one blank-year t57 query per ticker per pass.

HTTP mechanics:
- Python `requests==2.32.5`;
- one `requests.Session`;
- User-Agent fixed in executor;
- connect timeout = 10 seconds;
- read timeout = 30 seconds;
- maximum passes = 4;
- within each pass, query every still-unresolved ticker exactly once in ticker-ascending order;
- fixed 4.0-second spacing after every request;
- fixed 180-second pause between passes when unresolved tickers remain;
- retryable/unresolved conditions: connect/read timeout, DNS/connection exception, HTTP 429,
  HTTP 5xx, or known TWSE block/rate-limit marker;
- HTTP 4xx other than 429 is terminal structural transport failure;
- no jitter, adaptive backoff, user-agent rotation, proxy rotation, concurrency, or guessed endpoint.

Critical fail-closed rule:
**If any of the 128 candidate tickers remains transport-unresolved after pass 4, the entire V1.0
Stage B is `DATA_BLOCKED`; no candidate is dropped, no Top100 filtering is performed for return
authority, and no forward return may be opened.**

Thus network luck cannot determine the tested sample.

## 5. No-return Stage-B gate

Only if all 128 tickers are transport-resolved:
1. parse exact original current/prior metadata;
2. resolve signal dates;
3. enforce PIT electronics membership;
4. build signal-date dynamic Top100 membership;
5. retain only ZERO_RED_FLAG events inside Top100;
6. report counts only, with no returns attached.

Discovery count sufficiency remains unchanged from V0.1:
- >= 80 selected company-events;
- >= 40 unique tickers;
- >= 20 distinct signal dates.

If below any minimum: `INCONCLUSIVE_COUNT_INSUFFICIENT_DO_NOT_OPEN_RETURNS`.

## 6. Return geometry — frozen but unopened

Only if the no-return Stage-B gate passes:
- signal after close on signal_date;
- entry next TWSE open;
- round-trip cost 40 bps;
- primary horizon = 20 trading sessions;
- exit at close of the 20th trading session counting entry session as session 1;
- secondary horizons 5/10/40/60 cannot rescue primary-horizon failure.

Discovery: signal dates 2023-01-01 through 2024-12-31.
Validation: 2025-01-01 through 2026-10-31.
Validation remains sealed unless Discovery passes.

## 7. Frozen nulls

For each signal date, use the same dynamic Top100 eligible universe and same k_d:
- N0 = equal-weight eligible Top100 cross-section;
- N1 = prior-20-session return TopK;
- N2 = prior-5-session return BottomK;
- N3 = matched random without replacement.

N3 mechanics:
- NumPy `Generator(PCG64(20261031))`;
- signal dates processed ascending;
- eligible tickers sorted ascending before sampling;
- 10,000 draws;
- global generator instantiated once and consumed sequentially;
- no reseeding by date;
- if k_d exceeds eligible count, fail closed.

## 8. Bootstrap mechanics

Validation date-block excess vs N1 uses:
- NumPy `Generator(PCG64(20261031))`;
- 10,000 bootstrap replicates;
- resampling unit = signal-date block;
- sample exactly B blocks with replacement where B = observed distinct signal-date blocks;
- statistic = equal-weight mean of block-level challenger-minus-N1 excess;
- 95% percentile CI = empirical 2.5th and 97.5th percentiles;
- interpolation = NumPy default linear quantile method;
- missing/invalid block => fail closed before bootstrap;
- bootstrap generator is separate from the N3 generator but uses the same fixed seed.

## 9. Discovery gate

At the primary 20-session horizon Discovery passes only if all are true:
1. count sufficiency passes;
2. challenger net mean return > 0;
3. challenger net median return > 0;
4. challenger mean after removing best 5 events > 0;
5. date-block mean excess vs N0 > 0;
6. date-block mean excess vs N1 > 0;
7. no single ticker contributes >20% of total positive PnL.

Any failure => `FAIL`; Validation stays sealed.

## 10. Validation gate

Only after Discovery PASS, Validation passes only if all are true:
1. count sufficiency >=80 events, >=40 tickers, >=20 dates;
2. net mean >0;
3. net median >0;
4. remove-best-5 mean >0;
5. date-block excess vs N0 >0;
6. date-block excess vs N1 >0;
7. bootstrap 95% CI lower bound vs N1 >0;
8. challenger mean >95th percentile of N3 matched-random distribution;
9. no single ticker >20% of total positive PnL.

Passing = `RESEARCH_VALIDATION_PASS` only, never Production.

## 11. No-rescue law

Forbidden after any data/return opening:
- changing any of the six accounting signs;
- changing Top100 to another N;
- changing 60-session turnover window or 50-observation minimum;
- switching primary horizon;
- changing transport passes/timeouts/spacing/pause;
- excluding unresolved transport failures and continuing;
- changing N3 PRNG/seed/draw count;
- changing bootstrap unit/seed/replicate count/CI;
- adding M1/M3, flow, margin, TDCC, industry, or familiar-stock filters.

Any genuine new mechanism requires a new challenger ID and preregistration before affected returns.

## 12. Immediate next legal command

`RUN_V1_0_METADATA_ONLY_COMPLETE_OR_BLOCK_STAGE_B`

No forward return is authorized by this preregistration alone.
