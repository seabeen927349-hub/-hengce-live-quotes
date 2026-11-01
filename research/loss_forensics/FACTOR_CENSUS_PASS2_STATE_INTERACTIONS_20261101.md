# HENGCE DYNAMIC STATE PROBABILITY ENGINE — Factor Census Pass 2
Date: 2026-11-01
Status: ACTIVE RESEARCH / NO TRADING AUTHORITY
Scope note: 6415 and 3042 are excluded from current interpretive examples.

## Purpose
Move beyond one-variable evidence. This pass asks which interactions distinguish durable repair, temporary bridge control, true control takeover, and capital departure.

## 1. Evidence-status hierarchy
### Eligible for calibrated state work now
- CONTROL retention: expanding time-order OOS in 2026, AUC 0.694.
- HOOK / release states: expanding OOS return validation exists.

### Structural but not yet probability-calibrated
- bridge reload
- destination preload
- Big1000 -> Mid core loosening
- professional-flow mirror
- capital baton / marginal-control-capital relocation

### Uncalibrated / zero formal probability weight for now
- fundamental rapid-deterioration gates from TWSE_State_Transition_Matrix_v1_2.xlsx. The workbook explicitly states these gates were not sample-out validated.

## 2. CONTROL retention and HOOK remain the strongest validated state interactions
CONTROL target is next-snapshot strong-ownership retention, not stock return.

Expanding OOS 2026-06-26 through 2026-10-16:
- AUC 0.694
- confidence >=0.70 -> 84.56% next-snapshot retention
- confidence >=0.80 -> 88.79%
- confidence >=0.90 -> 93.51%

The dominant observable is Absorption Fraction = dBig400 shares / shares traded during the ownership interval, combined with existing concentration, relative dBig400 size, multi-snapshot accumulation, holder fragmentation and prior control behavior.

HOOK READY is defined from the CONTROL anchor:
- price above anchor
- TotalHolders above anchor
- margin balance above anchor
- turnover above anchor

The state therefore explicitly measures counterparty / weak-hand liquidity arriving after control was acquired.

### OOS action validation
SELL_WATCH_HOOK_READY:
- d5 N=163, mean -2.83%, median -2.05%, positive 33.7%
- d10 N=143, mean -4.20%, median -3.95%, positive 30.8%

MUST_SELL_RELEASE_STARTED = CONTROL FULL + HOOK READY + current dBig400 < 0:
- d5 N=49, mean -3.07%, median -3.41%, positive 32.65%
- d10 N=40, mean -5.91%, median -5.42%, positive 22.5%

BUY_CONTROL_CAPTURE = strong CONTROL capture + holders down + margin down + price still down:
- d5 N=552, mean +1.13%, median +0.51%, positive 55.1%
- d10 N=524, mean +0.82%, median +0.16%, positive 51.1%
- d20 N=462, mean +2.11%, median +0.38%, positive 51.7%

Interpretation: the validated architecture is much stronger on deterioration / exit-state recognition than exact entry timing.

## 3. New interaction: CONTROL PURITY / weak-hand contamination
A large ownership increase is not one economic state.

### Cleaner control acquisition
Observed structure:
- strong ownership rises materially
- margin falls or remains contained
- holder fragmentation does not surge
- ownership persists next snapshot

Examples excluding 6415/3042:
- 2408 on 2026-04-30: Big1000 +378.270m; price +4.61%; margin -5.81%; next snapshot Big400 adds again.
- 6213 on 2026-06-26: Big1000 +29.099m; price +23.75%; margin -5.34%; ownership remains largely intact.

### Contaminated / expensive control
Example:
- 4967 on 2026-04-24: Big1000 +10.341m; price +17.77%; margin +51.57%; next snapshot strong ownership reverses.

Current inference:
> `strong ownership up` must be conditioned on who is financing the price.

This does NOT establish that margin expansion causes failure. It establishes a candidate buyer-quality interaction:
`CONTROL_STRENGTH x WEAK_HAND_CONTAMINATION`.

No fixed threshold is authorized yet.

## 4. New interaction: REPAIR DURABILITY
The first strong-holder rebound must not be interpreted as repair automatically.

Three economically different states are visible:

### GENUINE_REPAIR
- prior outward transfer / wash
- strong holders absorb while price remains weak/ugly
- weak leverage does not become the dominant buyer
- inventory remains largely intact next snapshot

Examples: 2408, 2455, 3450 historical 2026 episodes.

### BRIDGE_RELOAD
- source recently loosened/lost control
- strong holders buy again
- price is already attractive or maintained
- another related name is simultaneously preloading
- source ownership reverses again quickly

Examples excluding 6415/3042:
- 4967 2026-04-24 -> next snapshot Big400 -5.416m while related destination was already preloading.
- 2337 2026-04-30 -> next snapshot Big400 -62.931m while 2344/2408 were receiving control capital.
- 8021 2026-01-23 -> next snapshot Big400 -5.463m while 2383 had begun accumulation.
- 3006 2026-09-11 -> next snapshot Big400 -12.165m while 8150 was receiving ownership.

### NEW_CONTROL_TAKEOVER
- strong ownership rises materially
- control does not immediately reverse
- next snapshot / next-next snapshot retains or adds control

Examples:
- 6213 2026-06-26: Big400 +28.003m / Big1000 +29.099m; next snapshots essentially retain control.
- 2408 2026-04-30: Big400 +375.845m / Big1000 +378.270m; next snapshot Big400 +58.231m.
- 2344 2026-05-08: Big400 +137.032m / Big1000 +141.393m; next snapshot Big400 +172.978m.

Engine implication:
- do not map `dBig400 > 0` directly to P(REPAIR).
- estimate `P(REPAIR_DURABLE)` separately from `P(BRIDGE_RELOAD)`.

## 5. Earlier FIRST_FRACTURE: CORE LOOSENING before Big400 exit
One useful early source-side structure is internal large-holder fragmentation:
- Big1000 falls
- Mid rises
- Big400 falls less than Big1000 or remains relatively stable
- later snapshot determines repair vs full leakage

6213 September example:
- 09/04 Big1000 -4.814m, Mid +0.369m, Big400 -4.444m
- 09/11 Big1000 -6.932m, Mid +4.128m, Big400 -2.804m
- 09/18 Big1000 -13.515m, Mid +2.198m, Big400 -11.317m, margin +7.77%

Interpretation:
`CORE_LOOSENING -> BIG400_LEAKAGE` can precede complete ownership loss.

This is currently structural/case-level evidence, not a calibrated probability feature.

## 6. Destination preload and overlapping baton migration
Observed baton behavior is often overlapping rather than sequential:
`destination preload -> source last reload/bridge -> source core loosening -> source departure -> destination reconcentration -> control proof`.

Destination preload can appear as:
- Mid accumulation
- Big400 growth while Big1000 is flat/down
- modest Big1000 accumulation
- visible professional/sponsor flow before weekly core reconcentration
- falling leverage while price remains quiet

This means the engine should not analyze a stock in isolation when estimating BRIDGE / DEPARTURE risk.

## 7. Professional-flow mirror: useful corroboration, not required evidence
Repeated source-out / destination-in visible flow exists in several strong Level-B baton candidates.

Examples:
- 3231 -> 3017: 9/10 days in one transition window and 7/10 in the next had source foreign-identity flow negative and destination positive.
- 3006 -> 8150 September: 6/9 days showed the same directional mirror.

But 8021 -> 2383 did not show the same clean foreign-identity mirror.

Therefore:
- professional-flow mirror can raise `P(BATON_DEPARTURE)` / `P(BATON_ARRIVAL)` when ownership migration agrees;
- absence of the mirror cannot veto the transition;
- visible institutional identity is execution evidence, not beneficial-owner identity.

## 8. Capital-relocation evidence and negative control
Strong repeated Level-B candidates include:
- 6213 -> 3189
- 3231 -> 3017
- 2337 -> 2344

Example 6213 -> 3189, September:
SOURCE 6213:
- Big1000 -13.515m
- Big400 -11.317m
- margin +7.77%
- foreign identity -7.788m
- total institutions -6.442m

DESTINATION 3189:
- Big1000 +13.954m
- Big400 +10.234m
- margin -5.11%
- foreign identity +18.233m
- total institutions +20.881m
- price +15.63%

This is economically consistent with marginal control capital moving from a weaker/leverage-financed source to a cleaner destination.

Negative control:
2408 -> 2337 ownership relays existed, but 2337 did not immediately deliver strong forward performance.
Therefore BATON_ARRIVAL is not automatically BUY.
Promotion requires destination CONTROL PROOF and buyer-quality evaluation.

## 9. Proposed state decomposition for the probability engine
Top-level probabilities remain:
- P(CONTINUATION)
- P(REPAIR)
- P(CONTROL_LOSS)
- P(SYSTEMIC_SHOCK)

Pass 2 adds latent sub-states that should be separately estimated before aggregation:
- P(CONTROL_PURE)
- P(REPAIR_DURABLE)
- P(BRIDGE_RELOAD)
- P(CORE_LOOSENING)
- P(BATON_DEPARTURE)
- P(DESTINATION_PRELOAD)
- P(BATON_ARRIVAL_PROVEN)

No numerical probabilities are assigned to the new latent states yet because cross-sectional time-order calibration has not been completed.

## 10. Fundamentals status
Fugle advertises historical revenue/cash-flow content specs, but direct calls in the current research session returned empty payloads for 6213. Retrieval-blocked must not be treated as data absence.

Library workbook `TWSE_State_Transition_Matrix_v1_2.xlsx` contains official-data fundamentals for a limited 2026 sample:
- May-Aug revenue
- 2025/2026 H1 EPS
- gross margin
- operating margin
- 42 observed stocks
- 240 fundamental rows

Its feature matrix includes Revenue_YoY, Revenue_YoY_Slope, Revenue_MoM, EPS_YoY, GrossMargin_Delta and OpMargin_Delta.

However the workbook explicitly states the fundamental rapid-deterioration gates have NOT completed out-of-sample validation. Therefore:
`FUNDAMENTAL_INFORMATION_WEIGHT = 0 for formal calibrated probability until validated`.
Fundamentals remain explanatory/context evidence and a future factor-census family.

## 11. Current strongest conclusion
The most useful interaction discovered so far is not price x volume. It is:

> `WHO HOLDS INVENTORY x WHO FUNDS THE PRICE x WHETHER CONTROL PERSISTS x WHERE MARGINAL CONTROL CAPITAL APPEARS NEXT`.

The next empirical task is to turn the structural bridge/baton observations into cross-sectional, time-ordered labels and test whether they improve Brier/log-loss/calibration beyond CONTROL+HOOK alone. If they do not, they must remain narrative diagnostics rather than probability inputs.
