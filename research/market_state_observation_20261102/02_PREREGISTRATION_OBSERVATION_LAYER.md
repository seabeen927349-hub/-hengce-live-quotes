# HENGCE Market Environment Observation Layer — Preregistration v0

Date: 2026-11-02 (Asia/Taipei)
Status: PREREGISTERED FOR S1 PIT/CAPABILITY AUDIT ONLY
Dependency: topic `LITERATURE_GATE.json` = PASS

## Research objective
Determine whether HENGCE can reconstruct, for any historical Taiwan trading date/time, a **contemporaneous market-environment vector** using only information genuinely available by that timestamp.

No target-return variable is part of this study.

## Universe and layers

Primary market context:
- Taiwan listed equities / TAIEX-level environment.

Mandatory target-universe overlay:
- Taiwan electronics sector, because the current Selection Core research universe is electronics-focused.

Observation layers:
1. market-wide;
2. electronics-sector;
3. cross-sectional participation/dispersion where data lineage permits;
4. microstructure/flow where data lineage permits;
5. leverage/short structure;
6. industry synchronization/diffusion;
7. market-design/rule context;
8. external/futures context as secondary metadata only.

## Preregistered dimension families

The following families are frozen as the **maximum initial observation set**. S1 may remove a family for data/PIT failure, but may not add a new family because it looks useful against future returns.

1. **Market Path / Transition**
   - contemporaneous market and electronics price-path information;
   - drawdown/transition uncertainty;
   - no ex-post turning-point label.

2. **Volatility / Downside Stress**
   - realized-volatility family;
   - downside/tail/jump family if reconstructable;
   - exact estimator/window deferred to a later preregistration after S1 availability audit.

3. **Liquidity / Market Quality**
   - spread/depth/turnover/price-impact families as available;
   - market and electronics/industry commonality must be retained where measurable.

4. **Flow / Price Discovery Structure**
   - order imbalance;
   - aggressive vs passive activity;
   - persistence/herding/price-discovery measures only when identity and timing are historically reconstructable.

5. **Leverage / Short Structure**
   - margin purchase, margin short and securities lending/borrowing treated separately;
   - scale relative to market capitalization/turnover where possible;
   - rule/maintenance context retained.

6. **Industry Synchronization / Diffusion**
   - market-factor-aware industry co-movement/dispersion;
   - no fixed permanent transmitter ordering;
   - supply-chain edges only when contemporaneously documented.

7. **Attention / Crowding Activation**
   - observable attention/activity/crowding proxies only;
   - no latent psychological label.

8. **Participation / Concentration Structure**
   - ownership/shareholder concentration and breadth only when historically versioned and first-public timing is known;
   - otherwise `UNKNOWN`.

9. **Market-Design Context**
   - continuous/call auction regime, price limits, tax/day-trading/short-sale rule context as historically versioned metadata.

10. **External / Derivatives Context**
   - global-market, FX, index-futures open-interest/price-discovery and implied-volatility inputs are secondary context only;
   - they may not define the core state unless a later literature/PIT gate explicitly promotes them.

## Output object

For each observation timestamp, output only a vector with per-dimension metadata:

- `dimension`;
- `measurement_family`;
- `value_or_state` (only after the measurement definition is frozen);
- `source`;
- `source_version`;
- `first_public_timestamp`;
- `observation_timestamp`;
- `latency`;
- `missingness`;
- `reconstruction_confidence`;
- `notes`.

Initial output must **not** contain:

- future return;
- future drawdown;
- forward hit rate;
- alpha;
- trade P&L;
- buy/sell action;
- stock rank;
- optimized state label.

## UNKNOWN rule
If a dimension cannot be reconstructed using information available at the observation timestamp, it must be recorded as `UNKNOWN`.

Forbidden:
- backfilling with later revised data;
- using later relationship maps;
- imputing a state from future observations;
- silently substituting a different modern dataset.

## S1 capability-audit pass questions
For every proposed measurement family:

1. Is a historical source available?
2. What is the exact first-public timestamp?
3. Was the value revised later?
4. Can the historical version be reconstructed?
5. What is the minimum recognition latency?
6. What is the missing-data behavior?
7. Does market-design change alter comparability?
8. For electronics, is the same measurement available consistently across the intended universe?

## Falsification / failure conditions
This observation-layer project fails or narrows if:

- a core dimension cannot be reconstructed PIT-cleanly;
- most dimensions require future-confirmed labels;
- historical data versions are unavailable;
- market-design breaks make a measurement non-comparable and no versioning solution exists;
- the observation vector cannot be reproduced deterministically from the same as-of data.

Failure is an acceptable result. No alternative dimension may be introduced because it happens to correlate with future returns.

## Next forbidden boundary
Completion of S1 does not authorize predictive testing. A separate preregistration is required before any attempt to determine whether an environment state conditions future stock returns or Selection Core performance.
