# HENGCE Dynamic State Engine — Factor Census Pass 1
Date: 2026-11-01
Status: RESEARCH / NO TRADING AUTHORITY

## Purpose
Prioritize evidence families by what they have actually demonstrated, not by intuition. No family weight is frozen here.

## 1. OWNERSHIP / SPONSORSHIP — strongest current state evidence
Existing strict time-order CONTROL validation (2026-06-26 through 2026-10-16):
- target: next-TDCC-snapshot retention of ownership control, not future return
- OOS AUC: 0.694
- CONTROL confidence >=0.70 -> next-snapshot retention 84.56%
- >=0.80 -> 88.79%
- >=0.90 -> 93.51%

Dominant observable in that research:
- Absorption Fraction = delta Big400 shares / shares traded during ownership interval
Supporting variables:
- existing Big400 concentration
- current increase relative to stock's own PIT history
- two-snapshot accumulation
- holder-fragmentation contraction
- prior control behavior

Exit-state evidence:
`CONTROL FULL + HOOK READY`
- 5d mean -2.83%, median -2.05%, positive-return rate 33.7%
- 10d mean -4.20%, median -3.95%, positive-return rate 30.8%
- 40d mean -6.63%, median -5.68%

`CONTROL FULL + HOOK READY + dBig400 < 0`
- OOS n=52
- 5d mean -3.07%, median -3.41%
- 10d mean -5.91%, median -5.42%, positive-return rate 22.5%
- 40d median -7.52%

Interpretation for new engine:
- ownership family has real evidence for CONTROL retention and for late-stage release/handoff states;
- do NOT reinterpret the CONTROL AUC as stock-return AUC;
- this family should primarily model P(REPAIR) / P(CONTROL_LOSS), then allow state probabilities to influence return/risk interpretation.

## 2. MARKET / RELATIVE-STRESS — strong evidence in a specific state
Frozen Q017 historical evidence (kept as a separate old model, not inherited):
- 2025 OOS AUC 0.7200675
- target: Top1 stock reaches signal close +5% within future 5 sessions
- Top1 hit rate ~68.22%
- base rate ~25.64%

Q017 conditions combine:
- negative individual residual relative to PIT electronics median
- electronics market weakness
- prior U.S. SOX weakness

Interpretation for new engine:
- this is evidence that MARKET_REGIME x RELATIVE_PRICE interaction can identify a repair/rebound opportunity state;
- it is NOT evidence for generic daily up/down prediction;
- use it as a candidate transition family for SYSTEMIC_SHOCK -> REPAIR rather than copying Q017 formula or thresholds.

## 3. PRICE / LIQUIDITY — broad coverage but weak standalone probability evidence
2018-2026 TWSE electronics history is available with annual corporate-action files.
Preliminary new-engine baseline using only price/liquidity/cross-sectional variables has weak OOT discrimination (~0.51-0.55 AUC depending on target/model).

Interpretation:
- retain price/liquidity as state-description, timing and interaction evidence;
- do not assign high standalone directional weight;
- high volume, high transaction count, strong close, rising margin/shorts can occur at both genuine continuation and true peaks.

## 4. PROFESSIONAL CAPITAL — fast state-update evidence, weak standalone terminal classifier
Current loss-forensics results show visible institutional flow often reverses faster than leverage after major turns.
However peak-day positive -> next-day negative flow flip does not materially separate deeper vs shallower complete declines by itself.

Interpretation:
- use professional capital as FIRST_FRACTURE / REPAIR_IN_PROGRESS evidence;
- do not equate foreign/trust/dealer labels with beneficial-owner identity;
- weight should depend on price response and ownership context.

## 5. LEVERAGE / WEAK HANDS — buyer-quality and capitulation evidence
Current findings:
- leverage tends to expand later in rallies and contract later in declines;
- HOOK research treats TotalHolders + margin + turnover expansion above control anchor as distribution capacity;
- late negative margin change is not equivalent to forced margin calls.

Interpretation:
- leverage should mostly modify buyer-quality and urgency probabilities;
- likely higher weight in ATTENTION_EXPANSION, HOOK_READY, FAILED_REPAIR and capitulation states than at initial accumulation.

## 6. CAPITAL RELOCATION — repeated structural evidence, not yet calibrated cross-sectionally
Repeated Level-B baton candidates exist (e.g. 6213->3189, 3231->3017, 2337->2344), but same-beneficial-owner identity is unproven.

Interpretation:
- candidate modifier for P(CONTROL_LOSS) in source and P(REPAIR/CONTROL_BUILD) in destination;
- needs all-universe event construction and calibration before numeric weight.

## 7. FUNDAMENTALS / EVENTS — open, not yet censused
Available sources include revenue, EPS, margins, statements, cash flow, inventory/receivables/payables, announcements and corporate actions.

Priority questions:
- Does positive fundamental acceleration matter only when ownership is building/retaining?
- Does deterioration increase CONTROL_LOSS probability only after sponsorship weakens?
- Are event surprises primarily attention/liquidity triggers, or independent state information?

No weight until tested.

## Provisional family priority
This is research priority, NOT model weight:
1. OWNERSHIP_SPONSORSHIP
2. MARKET_REGIME x RELATIVE_STATE
3. PROFESSIONAL_CAPITAL x PRICE_RESPONSE
4. LEVERAGE_WEAK_HANDS x OWNERSHIP
5. PRICE_LIQUIDITY as timing/context
6. CAPITAL_RELOCATION
7. FUNDAMENTAL_INFORMATION pending census

## Design consequence
Do not train one monolithic model first.
Build family-specific transition estimators:
- Ownership -> P(control retention / repair / failed repair)
- Market-relative -> P(systemic shock / rebound repair)
- Professional flow -> P(first fracture / early repair)
- Leverage -> P(hook / weak-buyer takeover / capitulation)
Then combine calibrated family posteriors in a state-transition layer.

This avoids asking a variable to predict an outcome it was never shown to predict.
