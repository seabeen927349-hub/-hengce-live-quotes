# HENGCE Market Environment Observation — S1 PIT / Data Capability Audit

Date: 2026-11-02 (Asia/Taipei)
Project: `research/market_state_observation_20261102`
Authority input: topic `LITERATURE_GATE.json = PASS` + `02_PREREGISTRATION_OBSERVATION_LAYER.md`
Status: **S1 BOUNDED PASS WITH NARROWING**

## 1. What S1 is deciding
S1 does not decide whether a market state predicts returns. It decides whether each preregistered observation family can be reconstructed without future information, silent revision substitution, or hindsight relationship maps.

Status classes: `FEASIBLE`, `PARTIALLY_FEASIBLE`, `FAILS_HISTORICAL_PIT`, `PROSPECTIVE_ONLY`, `SECONDARY_CONTEXT_ONLY`.

## 2. Key result: Market State must be multi-clock
Taiwan public data are released on materially different clocks.

### Clock A — Intraday prospective
Realtime price/volume/orderbook may be used only when live transport is actually healthy. No historical intraday replay is assumed. The current whole-market Fugle snapshot is fail-closed (`HTTP 403`, `snapshot_authorized=false`).

### Clock B — Official EOD / next-safe-use
Raw daily OHLC, volume, trading value, trade count and market/electronics cross-section are historically available. The 2018–2026 source archive was retrospectively downloaded and does not preserve original first-seen/publication timestamps, so historical research must not claim original 13:30 capture. Use a conservative EOD/next-session-safe clock unless a contemporaneous receipt proves earlier availability.

### Clock C — Post-close official files
- T86 institutional: TWSE product 18:00 excluding block trades / 20:00 including block trades.
- Attention/disposition: after-close analysis; commercial file 19:00.
- Securities-lending balance: 20:30.
- Available short-sale quota: 22:30.

### Clock D — Revision-safe delayed credit state
TWSE states the same-day margin/short balance is published after contributing institutions finish processing, but next-day adjustments can still change it. The pre-open announced balance is therefore contemporaneous but provisional. TWSE says the following report's `previous balance` contains the final correct balance after next-day adjustments. A retrospective historical endpoint can expose that corrected value without preserving the originally announced provisional version. Therefore, absent a contemporaneous provisional snapshot archive, D's finalized balance may be used only after the D+1 report has been published — conservatively **D+2 open or later**. D+1-open use of a later-corrected D value is forbidden.

### Clock W — Weekly ownership
TDCC is weekly, no daily forward-fill. Continuous full-market history is missing for material years, so ownership concentration is not a continuous historical core leg.

## 3. Dimension verdicts

### 3.1 Market Path / Transition — `FEASIBLE`
Allowed: raw market/electronics price path, date-correct electronics breadth, cross-sectional dispersion, past-only drawdown/path descriptors. Canonical yearly TWSE electronics archives cover 2018–2026. Retrospective historical downloads are not first-public-time proof. No ex-post bull/bear labels.

### 3.2 Volatility / Downside Stress — `FEASIBLE` daily, `PARTIALLY_FEASIBLE` intraday
Allowed: daily realized volatility, downside daily-return families, OHLC range families and cross-sectional stress. Unarchived historical tick/minute jump measures and volatility-based risk-off labels are not allowed.

### 3.3 Liquidity / Market Quality — `PARTIALLY_FEASIBLE`
Allowed: daily volume, trading value, trade count, PIT-denominator turnover-like families and cross-sectional liquidity commonality. EOD bid/ask-type fields do not establish full historical quoted spread/depth. Historical effective spread, realized spread and aggressive/passive price-impact families are not established across the full sample.

### 3.4 Flow / Price Discovery Structure — `PARTIALLY_FEASIBLE`
Official T86 investor-class daily flow is usable only after publication. Current canonical validated HENGCE T86 mother covers 2023–2025 with matched coverage about 96.98%, 98.45% and 97.72%, no failed T86 dates and no SHA mismatches. Foreign, trust and dealer primitives remain separate. T86 does not authorize aggressive/passive flow, intraday order splitting or smart-money motive labels. TWSE commercial T86 history starts 2004-09-09, but longer history is not assumed present in the canonical mother.

### 3.5 Leverage / Short Structure — `PARTIALLY_FEASIBLE`
TWSE margin history exists from 2001, but the existing HENGCE import documents incomplete margin population beyond early 2023 and same-day balances can be revised. Absent a preserved original provisional snapshot, use D's finalized balance only after the D+1 report has published its final `previous balance`; for an open-context vector this means D+2 open or later. SBL/lending is separate: official lending-balance product starts 2017-08-07 and is generated at 20:30; available-short-sale quota at 22:30. Borrowing is not equal to short selling.

### 3.6 Industry Synchronization / Diffusion — `FEASIBLE` price sync; `FAILS_HISTORICAL_PIT` complete supply-chain graph
Allowed: electronics/subindustry co-movement, dispersion and past-only common-factor-aware synchronization. Complete historical customer/supplier graph, hindsight edge fill and fixed upstream→downstream direction remain forbidden.

### 3.7 Attention / Crowding Activation — `PARTIALLY_FEASIBLE`, after-close only
Allowed: official TWSE attention/disposition-stock incidence and concentration. TWSE historical attention query is available from 2001; commercial daily file is generated at 19:00 and starts 2006-04-01. Google Trends is excluded until a vintage/scaling audit. No fear/FOMO/overconfidence labels.

### 3.8 Participation / Concentration Structure — `FAILS_HISTORICAL_PIT` continuous core; `PARTIALLY_FEASIBLE` bounded/prospective
TDCC is weekly and no daily forward-fill is allowed. Material full-market bulk gaps remain for 2018 and 2022–2025; Fugle long-history TDCC attempt returned HTTP 403. Allowed: 2026 canonical weekly sidecar, explicitly-authorized bounded research components and prospective weekly collection. Missing history stays UNKNOWN.

### 3.9 Market-Design Context — `FEASIBLE`
Use historically versioned rule metadata. Anchor: TWSE intraday continuous trading effective 2020-03-23. Market-design context controls comparability; it is not an alpha signal.

### 3.10 External / Derivatives Context — `SECONDARY_CONTEXT_ONLY`, `PARTIALLY_FEASIBLE`
TAIFEX provides daily futures/options history, VIX and historical transaction-data products. Participant data start 2008-04-07 and have staged disclosure semantics; older detailed history may require paid acquisition. Day/night-session and trade-date attribution must be explicit. VIX/OI/put-call/overseas moves cannot define Taiwan state alone.

## 4. Fugle decision
Canonical binding says Fugle is an intraday realtime augmentation layer and does not replace historical mother. The deployed whole-TWSE snapshot returned HTTP 403 on 2026-11-02 with `snapshot_authorized=false`, `healthy_transport=false` and `FAIL_CLOSED`.

Historical S1 authority from Fugle is none beyond separately audited returned historical content. Whole-market live Market State authority is currently unavailable from this snapshot transport. Realtime fields are prospective only when an actual call succeeds and timestamp/status are preserved.

## 5. Final S1 architecture after narrowing
Core historical EOD-capable:
1. Market Path / Transition
2. Daily Volatility / Downside Stress
3. EOD Liquidity / Market Quality (narrowed)
4. Price-based Industry Synchronization / Dispersion
5. Market-Design Context

Delayed/post-close:
6. Institutional Flow — strong 2023–2025 canonical coverage, publish-clock constrained
7. Leverage / Short — revision-safe delayed representation; finalized D margin may require D+2-open use absent provisional snapshots; backfill required for clean continuous mother
8. Attention / Crowding — official after-close data

Low-frequency/incomplete historical:
9. Participation / Ownership Concentration — weekly, incomplete, not continuous core

Secondary:
10. External / Derivatives Context

## 6. Observation clock rule
Every dimension must carry `event_date`, publication/safe-use clock, preserved `first_seen_timestamp` where available, `effective_asof_timestamp`, `age_at_observation`, `revision_status`, `source_version`, `reconstruction_class`, and `missingness/UNKNOWN`. If a field's effective-as-of time is later than the observation timestamp it is unavailable, not imputed.

## 7. S1 conclusion
`S1_PIT_DATA_CAPABILITY = PASS_WITH_NARROWING`.

HENGCE has enough defensible capability to build a historical contemporaneous environment observation vector if it is multi-clock and preserves unknowns. This does not establish stable states, combination weights, thresholds, return predictability or selection value.

## 8. Next clean step
Proceed to **S2 Observation Schema Freeze / Measurement Definition**: exact past-only formulas and clock semantics only. No forward returns, predictive clustering, state labels chosen from future outcomes, optimization or substitution of unavailable historical fields.
