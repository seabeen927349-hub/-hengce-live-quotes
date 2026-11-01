# HENGCE Historical Factor Census — Bootstrap V1
Date: 2026-11-01
Status: ACTIVE RESEARCH / NOT TRADING AUTHORITY

Excluded from the current forensic build where prior instruction applies: 6415, 3042.

## Objective
Build an interpretable multi-factor state probability rather than an exact price target.

Each factor contributes:
1. direction contribution (bullish / bearish log-odds),
2. reliability weight based on historical depth, cross-year stability, incremental information and redundancy,
3. calibrated probability after aggregation.

The final percentage must be a calibrated historical probability / state estimate, not an arbitrary sum of indicator scores.

## Data actually opened / verified
### 2018-2026 TWSE listed electronics price-volume history
Nine annual canonical ZIPs are present and were opened.
Rows / sessions / unique tickers by year:
- 2018: 98,125 / 247 / 408
- 2019: 97,413 / 242 / 409
- 2020: 99,088 / 245 / 409
- 2021: 99,726 / 244 / 414
- 2022: 102,473 / 246 / 425
- 2023: 101,024 / 239 / 431
- 2024: 105,016 / 242 / 440
- 2025: 107,709 / 243 / 452
- 2026 through 2026-10-27: 88,901 / 195 / 463

Total: 899,475 daily price-volume rows across the nine annual files; 487 distinct tickers appear somewhere in the history.

Each annual ZIP also contains official corporate-action references. There are 3,174 corporate-action rows across 2018-2026. Mechanical discontinuities must be normalized or censored before factor learning.

### 2023-2025 institutional history
`TWSE_2023_2025_institutional.csv`: 724,677 rows.
Integrated mother: 735,618 rows.
Institutional exact Date×Ticker coverage:
- 2023: ~96.98%
- 2024: ~98.45%
- 2025: ~97.72%

### 2026 institutional + margin
Canonical 2026 daily institutional and margin files are available through 2026-10-30 / current canonical horizon.

### TDCC ownership
Useful but historically incomplete. Best-available research candidate contains 81 snapshots with years 2017, 2019, 2020, 2021 and 2026. Known bulk gaps include 2018 and 2022-2025. TDCC must therefore be an ownership overlay learned only where real snapshots exist; no synthetic weekly history.

### Fundamentals / events
Fugle-accessible specifications include multi-year revenue, EPS, margins, income statement, balance sheet, cash flow, capex, working-capital ratios, corporate events and insider-transfer data. These are separate lower-frequency factor families and will be timestamp-aligned to public availability.

## First price-only baseline — negative result retained
A first baseline used corporate-action-aware price/volume/transaction features such as recent returns, distance to highs/lows, volume and transaction shocks, close location, gap/range, volatility expansion, trade-size proxy, breadth and cross-sectional ranks.

Time split:
- train: 2018-2023
- calibration: 2024-2025
- true later test: 2026

Results:
- linear model, future 10-day raw positive return: test AUC ~0.510; Brier ~0.2523 vs constant baseline ~0.2503 (worse than baseline calibration).
- linear model, future 10-day cross-sectional outperformance: AUC ~0.520.
- nonlinear price-only model for cross-sectional outperformance: AUC ~0.531.
- nonlinear price-only classification of future top 30% vs bottom 30% cross-sectional outcomes: AUC ~0.548.

Interpretation:
Price / volume / transaction structure alone contains some extreme-ranking information but is far too weak to justify a high-confidence directional percentage. Do not retune this result away. The useful probability engine must add capital flow, ownership, leverage, fundamental/event and regime information.

## Factor families to census
1. Price path / location
2. Attention / turnover / transaction intensity
3. Intraday absorption / rejection geometry
4. Volatility / fragility / liquidity
5. Market and electronics breadth / regime
6. Institutional aggregate sponsorship and flow acceleration
7. Price-flow divergence / role rotation
8. Margin / leverage / short-covering state
9. TDCC concentration, dispersion, repair / failed repair
10. Fundamental acceleration / deterioration
11. Cash-flow / working-capital quality
12. Event / disclosure / corporate-action context
13. Cross-stock baton / opportunity relocation
14. Macro / SOX / DXY / market-relative state where historically available

## Weighting method
Do not assign subjective weights.
For each factor/family:
- learn direction from historical conditional outcomes;
- require out-of-time validation;
- measure stability across calendar years and regimes;
- measure incremental log-loss / Brier / ranking improvement after existing families;
- shrink short-history factors;
- discount redundant highly correlated factors;
- keep missing data as missing rather than fabricated neutral values.

A scorecard-style implementation is preferred for interpretability:
`base log-odds + sum(reliability_weight × factor_log_likelihood_contribution)`
then calibrated to a percentage using held-out years.

## Output target
For each requested stock/date, return at minimum:
- Bullish state probability
- Bearish state probability
- factor-family contributions in percentage points / log-odds
- evidence reliability / coverage
- strongest bullish evidence
- strongest bearish evidence
- missing/stale factors
- what next observation would most change the probability

The percentage is not a claim of exact future price. It is a continuously updated estimate of which historical state the current stock most resembles.
