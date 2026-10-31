# HENGCE Repricing State — Execution Clarification Addendum V0.1.1

Date frozen: 2026-10-31
Status: `NO_FORWARD_IMPLEMENTATION_DETAIL_FROZEN`
Parent clarification: `HENGCE_REPRICING_STATE_EXECUTION_CLARIFICATION_V0_1_20261031.md`
Authority: `RESEARCH_ONLY`
Forward returns: `SEALED`

## 1. Trading-session continuity

All frozen lookbacks expressed in sessions are implemented on the canonical TWSE trading-session calendar, not as a count of whatever non-missing stock observations happen to be available.

For V0.1:

- trailing-20 SA means the 20 consecutive TWSE sessions ending at t;
- `g1` requires both t and the immediately preceding TWSE session;
- `g5` requires five consecutive valid `g1` observations ending at t;
- `g20` requires twenty consecutive valid `g1` observations ending at t, therefore 21 consecutive valid margin-balance observations;
- a missing stock-level margin, T86, price, or volume leg inside a required path breaks that path;
- the implementation may not skip a missing session and reach farther backward to manufacture the requested count;
- TAIEX `R63` / `RV63` use the canonical consecutive TAIEX/TWSE session sequence required by the preregistration.

This is the fail-closed reading of the frozen common-cohort rule and does not alter any lookback length.

## 2. No synthetic zero and no carry

A genuine reported numeric zero remains a valid observation. A missing record is not a zero and is not forward-filled, backward-filled, interpolated, or carried.

## 3. Novelty panel row semantics

The legacy-factor reconstruction OLS uses one row per valid matched `(signal_date, ticker)` observation, exactly as implied by the frozen preregistration's held-out-year row partition. Calendar year is determined by `signal_date`.

No date weighting, ticker weighting, duplicate expansion, interaction, spline, regularization, feature selection, or transformation is introduced.

## 4. No outcome access

This addendum is frozen before any Repricing State forward-return computation. It authorizes only contemporaneous/raw historical features and frozen legacy-reference reconstruction for the label-free novelty audit.
