# HENGCE Market State — Topic Evidence Map

Date: 2026-11-02 (Asia/Taipei)
Status: literature evidence map complete for the **observation-layer scope**; no predictive state rule authorized.
Canonical source: `/HENGCE_CANONICAL/RESEARCH/TAIWAN_STOCK_MARKET/HENGCE_TAIWAN_STOCK_MARKET_MASTER_LITERATURE_LEDGER_v1.xlsx`
Master P1 authority: `HENGCE_TAIWAN_STOCK_MASTER_P1_CLOSURE_AUTHORITY_20261102.json`

## Topic question
Which dimensions of the Taiwan equity market can be defended as distinct, contemporaneously observable components of the current market environment, and which interpretations must be rejected before PIT/data validation?

## Evidence subset
Canonical subset: 41 studies/entries relevant to state observation.

- FULL_READ: 25
- PARTIAL: 7
- FOUND_ONLY: 9

The subset spans regime/macro, volatility/tail risk, microstructure/order flow, liquidity, leverage/short selling, institutional flow, behavioral attention/herding, ownership/concentration, industry spillovers and market-design changes.

Key canonical IDs:

- Regime/transition: TW-MKT-077, 078, 129, 130, 131, 132, 133, 134, 125
- Volatility/tail: TW-MKT-091, 092, 093, 094, 095
- Microstructure/flow: TW-MKT-043, 044, 051; BF-TW-021, 022, 003, 004, 008
- Liquidity: TW-MKT-068, 069, 073, 059, 135
- Leverage/short: TW-MKT-081, 082, 083, 084, 085, 087, 138
- Industry synchronization/diffusion: TW-MKT-050, 096, 097, 121
- Ownership/concentration: TW-MKT-071, 142, 143

## Bounded conclusions

| Dimension | What the literature supports | What is allowed at observation stage | What is explicitly not allowed |
|---|---|---|---|
| **Market path / transition** | Taiwan market and sector states can diverge; no single macro predictor works across market, industry and horizon; ex-post bear dating has recognition latency. | Observe contemporaneous market/sector price path, drawdown/transition evidence and uncertainty. | Copy ex-post bull/bear labels, use future-confirmed turning points, or freeze one macro switch. |
| **Volatility / downside stress** | Strategy sensitivity to high volatility/rebound/tail stress is heterogeneous; electronics crash-risk evidence includes direct null results. | Observe realized/downside/tail stress as a conditioning dimension. | Treat high volatility as universally bearish or directly as a stock-selection signal. |
| **Liquidity / market quality** | Liquidity is multidimensional; market and industry commonality are material; electronics may show strong commonality; proxies can be contaminated by overnight returns and market structure. | Observe spread/depth/turnover/price-impact families, with market/industry context. | Use one liquidity proxy or cutoff as universal state truth. |
| **Flow / price discovery** | Aggregate net flow hides participant and order-style heterogeneity; aggressiveness, liquidity provision, herding and price discovery differ by investor type and horizon. | Observe order imbalance/aggressiveness/passive provision/persistence where data are PIT-available. | Equate foreign/institutional buying with smart money or infer motive from flow alone. |
| **Leverage / short structure** | Margin, retail shorting and institutional SBL can have different or opposite meanings; raw margin balance is misleading without scale and market structure. | Observe margin, short and SBL separately and scale them appropriately. | Collapse them into one leverage score or interpret rising margin as crash evidence. |
| **Industry synchronization / diffusion** | Industry spillovers are regime-dependent; common factors explain much raw co-movement; transmitter/receiver roles can reverse; physical supply-chain direction is not price-discovery direction. | Observe common-factor-aware industry synchronization, dispersion and diffusion. | Freeze a permanent leader industry or upstream->downstream causal ordering. |
| **Attention / crowd activation** | Retail attention and herding are linked and state-dependent; institutional herding can also be state-dependent; simple sentiment proxies are weak/unstable. | Observe attention/crowding proxies as behavioral activation context. | Name latent fear/FOMO/overconfidence or infer excess-return direction from attention alone. |
| **Ownership / participation concentration** | Ownership/liquidity relations are nonlinear; concentration-return evidence includes null and cost/trend-sensitive results. | Observe concentration/participation structure only when historically versioned and PIT-clean. | Assume more large-holder ownership is automatically bullish or informed. |
| **Market-design context** | Taiwan rule changes materially affect volatility, liquidity, participation and price discovery. | Carry historically versioned rule regime as context metadata. | Compare observations across regimes as if market mechanics were unchanged. |
| **External transmission / derivatives** | Existing Taiwan/international evidence supports cross-market and futures/spot information transmission, but the topic-specific full-text Taiwan evidence is thinner than for the core dimensions. | Keep S&P/FX/futures OI/implied-volatility variables as secondary confirmation/context pending PIT and source audit. | Let TVIX, futures OI, US market moves or any one external input define the Taiwan market state. |

## Strongest architectural implication

The literature does **not** justify a single market-state label or score.

The clean observation object should initially be a **state vector**:

`MarketPath × VolatilityStress × LiquidityQuality × FlowStructure × LeverageStructure × IndustrySynchronization × AttentionCrowding × ParticipationConcentration × RuleContext × ExternalContext`

Each component must carry:

- value/measurement family;
- data source;
- first-public timestamp;
- observation timestamp;
- missing/unknown status;
- historical reconstruction confidence;
- source/regime version.

## Explicitly rejected constructs

The following are banned from the initial observation layer:

- `Fear State`
- `FOMO State`
- `Overconfidence State`
- `Smart Money Accumulation / Distribution`
- `Bull / Bear` defined using future-confirmed turning points
- `High Volatility = Risk Off`
- `High Margin = Crash Imminent`
- `Foreign Buy = Informed`
- `Upstream Leads Downstream`
- any single composite score whose weights are chosen without preregistration and PIT validation

## Saturation assessment

For the narrow question **"what dimensions may legitimately describe the current Taiwan market environment?"**, further literature search is unlikely to change the initial architecture materially. The major scientific conflicts are already represented: state dependence vs OOS instability, supportive vs null crash-risk evidence, informative vs noisy institutional flow, conditional vs unstable momentum, systematic vs idiosyncratic liquidity, and bidirectional/reversing industry spillovers.

Remaining uncertainty is primarily downstream:

1. exact PIT availability and release timestamps;
2. historical rule/version reconstruction;
3. current order-book and investor-class data capability;
4. definitions of realized volatility/downside/jump measures;
5. missingness/UNKNOWN handling;
6. whether external derivatives/cross-market variables materially add information after contemporaneous Taiwan variables.

Those are S1/S3 capability and preregistration questions, not reasons to keep the topic literature gate open indefinitely.
