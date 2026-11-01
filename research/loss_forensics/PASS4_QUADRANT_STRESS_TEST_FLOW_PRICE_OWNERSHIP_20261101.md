# HENGCE DYNAMIC STATE PROBABILITY ENGINE — Pass 4 Quadrant Stress Test
Date: 2026-11-01
Status: STRUCTURAL STRESS TEST / NO NUMERIC PROMOTION / NO TRADING AUTHORITY
Scope exclusions for interpretive examples: 6415, 3042.

## Purpose
Stress-test the proposed `FLOW_PRICE_RESPONSE` idea against ownership and leverage outcomes.

Key correction:
Flow-price response cannot be interpreted alone.
The economic unit is:

`VISIBLE FLOW x PRICE RESPONSE x OWNERSHIP RESPONSE x LEVERAGE QUALITY`

This file records cross-case mechanism checks only. The preregistered full-sample numeric test remains pending because the local compute runtime is returning ClientError.

## Quadrant 1 — visible selling + resilient/strong price + ownership repairs/strengthens
Interpretation candidate: real absorption / alternative sponsor with pricing power.

### 3189 examples
2026-06-26:
- price +10.08%
- margin -23.74%
- Big400 +3.409m
- Big1000 +4.411m
- foreign-identity -3.094m
- trust +10.870m
- total institutions +7.464m

2026-08-28:
- price +10.85%
- margin -1.85%
- Big400 +2.569m
- Big1000 +2.330m
- foreign-identity -1.266m
- trust +2.278m
- total institutions +1.794m

Foreign-identity selling did not imply weak control because large-holder ownership strengthened and another strong sponsor was present.

### 8021 examples
2026-06-12:
- price +13.97%
- Big400 +5.936m
- Mid +5.728m
- foreign-identity -3.400m
- trust +1.846m

2026-08-07:
- price +22.29%
- Big1000 +2.895m
- foreign-identity -3.382m
- trust +0.777m

Again, visible foreign-identity selling coexisted with ownership strengthening and repricing.

### 6782 fear-absorption example
2026-09-04:
- price -4.97%
- margin -14.32%
- foreign-identity -0.690m
- total institutions -0.778m
- Big400 +1.598m
- Big1000 +1.403m

Price was not strong on the day, but the relevant structural fact was that weak leverage was being removed while strong ownership increased despite negative visible institutional labels.

Conclusion:
`visible selling` is compatible with control strengthening when inventory moves into stronger ownership and leverage is being washed out.

## Quadrant 2 — visible selling + price still attractive/holds + ownership leaks / repair fails
Interpretation candidate: temporary price support / distribution efficiency, NOT absorption.

### 6213 first withdrawal cycle
2026-04-17:
- price +26.40%
- foreign-identity -15.70m
- Big400/Big1000 both down about 3.3m

2026-04-24:
- price still around 276
- Big400 -20.20m
- Big1000 -18.79m
- foreign-identity -7.05m

Later:
- attempted repairs remain small
- another ~14.6m Big1000 leaves by 2026-05-15
- price then falls materially

Conclusion:
Price resilience under selling does NOT prove absorption. If ownership is simultaneously leaking and no durable repair follows, the resilient price can instead be the liquidity window through which strong inventory exits.

This is a critical falsification of any rule like:
`selling + price holds -> bullish`.

## Quadrant 3 — visible buying + price rises + ownership builds/retains + leverage contained
Interpretation candidate: effective sponsorship / new control takeover.

### 6213 second-cycle takeover
2026-06-18:
- price +10.89%
- margin -12.44%
- Big400 +5.01m
- Big1000 +1.49m
- foreign +9.14m
- total institutions +10.37m

2026-06-26:
- price +23.75%
- margin -5.34%
- Big400 +28.00m
- Big1000 +29.10m
- foreign +24.58m
- total +27.46m

Ownership did not immediately reverse. This is consistent with sponsor flow that actually has pricing power and acquires durable inventory.

### 2408 takeover
2026-04-30:
- price +4.61%
- margin -5.81%
- Big400 +375.85m
- Big1000 +378.27m
- foreign +6.93m
- total +11.41m

2026-05-08:
- price +27.15%
- margin -6.48%
- Big400 +58.23m
- Big1000 +55.63m
- foreign +69.61m
- total +100.43m

Conclusion:
Visible buying is only high-quality when it is accompanied by durable strong-holder acquisition and weak leverage is not the marginal financing source.

## Quadrant 4 — visible buying + price weak/collapsing + ownership leaks
Interpretation candidate: visible buying has little/no pricing power; buying vehicle is not the controller.

### 6213 direct contradictions
2026-07-17:
- price -17.14%
- Big400 -5.200m
- Big1000 -6.727m
- margin -15.47%
- foreign-identity +2.712m
- total institutions +3.006m

2026-09-04:
- price -11.17%
- Big400 -4.444m
- Big1000 -4.814m
- foreign-identity +0.673m

Conclusion:
Positive visible institutional flow can coexist with genuine control withdrawal and falling price. The buying category did not possess pricing power.

## Repair Velocity cross-check
### Fast repair / false distribution
2408 2026-05-22 -> 2026-05-29:
- Big400 -72.49m -> +45.01m
- Big1000 -73.56m -> +43.81m
- margin on repair week -2.83%

2408 2026-09-18 -> 2026-09-24:
- Big400 -31.540m -> +34.597m
- Big1000 -35.495m -> +34.395m

8021 2026-06-18 -> 2026-06-26:
- Big400 -8.34m -> +1.86m
- Big1000 -5.00m -> +3.43m
- institutions positive
- margin remained lower

### Failed repair
6213 first withdrawal cycle:
- ownership continues leaking across snapshots
- no credible replacement sponsor
- weak money increasingly needed to carry price
- later price breaks

Structural conclusion:
The first fracture magnitude is less informative than whether strong ownership returns quickly, whether it stays, and who finances the repair.

## Pass-4 mechanism update
The proposed latent state should not be `FLOW_PRICE_RESPONSE` alone.
It should be decomposed into four interacting questions:

1. `FLOW_SIGN_AND_SIZE`
   - what visible professional flow occurred?

2. `PRICE_RESPONSE_RESIDUAL`
   - did price respond more/less strongly than expected given market/sector/volatility/liquidity conditions?

3. `OWNERSHIP_CONFIRMATION`
   - did Big400/Big1000/Mid show absorption, leakage, reconcentration or failed repair?

4. `LEVERAGE_QUALITY`
   - was margin/weak-hand participation being removed, contained, or becoming the marginal buyer?

Candidate state interpretations:
- `ABSORPTION_CONFIRMED` = sell pressure + resilient relative price + ownership strengthening/repair + leverage contained/falling
- `DISTRIBUTION_WITH_PRICE_SUPPORT` = sell pressure + resilient price + ownership leakage + weak-hand financing / failed repair
- `SPONSORSHIP_EFFECTIVE` = buy pressure + positive residual price response + durable ownership accumulation + leverage contained
- `SPONSORSHIP_INEFFECTIVE` = buy pressure + weak/negative residual price response + ownership leakage/no control proof

No numerical probability weights are authorized yet.

## Main falsification achieved
The stress test rejects both simplistic rules:

`selling + price holds = bullish`

and

`buying + price rises = bullish`.

Ownership destination and leverage quality determine whether the price response represents absorption, distribution, or irrelevant visible flow.

## Next required numeric test
When compute runtime is available:
1. fit expected stock return conditional on market return, electronics/industry return, volatility, liquidity and normalized professional flow using only earlier data;
2. calculate out-of-time residual price response;
3. combine residual response with contemporaneously available ownership and leverage state;
4. test whether the four-state interaction improves held-out Brier/log-loss/calibration for REPAIR vs CONTROL_LOSS beyond CONTROL+HOOK;
5. if not, formal probability weight remains zero.
