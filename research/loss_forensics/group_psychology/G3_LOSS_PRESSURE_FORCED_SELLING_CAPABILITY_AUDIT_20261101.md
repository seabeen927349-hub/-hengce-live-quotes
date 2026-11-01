# HENGCE Group Psychology — G3 Loss-Pressure / Forced-Selling Capability Audit

Date: 2026-11-01
Status: **PARTIAL_CAPABILITY_REDUCE_SCOPE / FULL_G3_NOT_AUTHORIZED_FOR_PREREG**
Formal weight: **0**
Trading / production authority: **NONE**

## 0. Governance
This audit follows the group-psychology handoff and the participation-diffusion novelty rejection. No new-family forward return or drawdown was inspected.

The handoff explicitly requires the participation layer to show incremental structure before building the transaction-cost / unrealized-P&L pressure proxy. The first participation-diffusion fallback failed its residual-novelty gate. Therefore this audit does **not** construct or backfit a holder cost basis, dense transaction-price mass, break-even zone, or trapped-holder estimate.

## 1. Canonical daily capability
Canonical mother `HENGCE_2026_HIST_MOTHER.csv` contains daily price, volume, traded value/turnover and `Margin_MarginBalance`.

Observed margin capability in the local canonical mother:
- margin non-null rows: 207,075
- date span: 2026-01-02 through 2026-10-30
- margin-covered tickers: 1,065
- 198 trading dates with margin data
- daily mother-row margin coverage approximately 96.5% to 97.3%

Thus 2026 leverage/margin and liquidity inputs are broadly available.

Fugle capability advertises adjusted/restated historical price, margin data, broker data and broker Gini. In this execution, `FCNT000154` adjusted-history and `FCNT000117` broker-Gini requests returned empty objects through the connector. This is treated as a connector/runtime availability gap, not evidence that the underlying paid product lacks those data.

## 2. Full G3 capability verdict
The handoff G3 mechanism requires jointly:
- price below a dense recent transaction-price mass;
- high holder breadth;
- leverage/margin pressure;
- accelerating selling/turnover.

Two required semantic layers are not currently authorized:
1. holder participation did not pass incremental-novelty as a new primitive using the available aggregate `<400` fallback;
2. the transaction-cost / inventory-pressure proxy is governance-gated behind a successful participation layer.

Therefore the **full G3 loss-pressure / forced-selling family is not authorized for preregistration in the current state**.

Verdict: `PARTIAL_CAPABILITY_REDUCE_SCOPE`.

## 3. Narrow observable input audit: deleveraging synchrony
A narrower descriptive state was audited only to determine whether the raw inputs are measurable. It is **not** asserted to be holder psychology and is not the full G3 family.

Natural time semantics used without outcome inspection:
- one trading week = 5 same-ticker sessions;
- prior trading month liquidity reference = preceding 20 same-ticker sessions.

Contemporaneous components:
- `RET5 = log(Close_t / Close_t-5)`;
- `DMARGIN5 = log(MarginBalance_t / MarginBalance_t-5)` when both balances are positive;
- `TURN_ACCEL = log(mean(Turnover_t-4..t) / mean(Turnover_t-24..t-5))` when inputs are positive.

Sign-only synchronization state:
`DELEVERAGING_SYNCHRONY = 1[RET5 < 0 AND DMARGIN5 < 0 AND TURN_ACCEL > 0]`.

This uses natural zero / no-acceleration boundaries and does not search percentiles or fitted cutoffs.

Input-only prevalence on 2026 mother:
- eligible rows: 173,125
- eligible tickers: 1,022
- eligible dates: 174 (2026-02-05 through 2026-10-30)
- synchronized rows: 12,842
- prevalence: 7.42%
- early-half prevalence: 8.36%
- late-half prevalence: 6.53%
- largest single-date share of all synchronized rows: about 1.93%
- largest single-ticker share: about 0.34%

The components are related but not identical in the input distribution:
- Pearson `RET5` vs `DMARGIN5`: about 0.169
- Pearson `RET5` vs `TURN_ACCEL`: about 0.335
- Pearson `DMARGIN5` vs `TURN_ACCEL`: about 0.193

## 4. Novelty boundary
`DELEVERAGING_SYNCHRONY` adds **no new raw information source**. It is a deterministic nonlinear conjunction of ordinary price, margin and turnover variables that the required BASE already contains.

It may represent a nonlinear state geometry beyond an additive linear baseline, but that is a model-form question, not a new crowd-information primitive. It must not be sold as evidence of shared holder psychology or forced liquidation without additional validated participation / cost-pressure structure.

Additionally, the local mother price field is not proven here to be corporate-action-adjusted. The Fugle adjusted-price call returned empty in this run. Therefore a clean price-loss state cannot yet be certified against ex-rights/ex-dividend discontinuities for a full-universe historical test.

## 5. Frozen decision
- Full G3: **NOT AUTHORIZED FOR PREREGISTRATION** under current handoff sequence.
- Narrow deleveraging-synchrony state: **INPUT-MEASURABLE BUT NOT A NEW INFORMATION PRIMITIVE**.
- No forward outcome unseal.
- No threshold, window, or interaction rescue after outcome inspection.
- Formal weight remains 0.

A future separate nonlinear-state study could preregister the sign conjunction explicitly if corporate-action-adjusted price provenance is restored, but it must be labelled as nonlinear geometry of existing baseline inputs, not as a newly observed crowd-psychology variable.