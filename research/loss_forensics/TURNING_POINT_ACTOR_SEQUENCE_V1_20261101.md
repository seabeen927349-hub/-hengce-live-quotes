# HENGCE LOSS FORENSICS — Turning-Point Actor Sequence V1
Date: 2026-11-01
Status: RETROSPECTIVE FORENSICS / NOT A TRADING RULE / NOT A MANIPULATION CLAIM
Universe: bound TWSE electronics 100-stock pilot

## Objective
Identify which observable capital roles change behavior first around major turns, which roles lag, and which subsequent ownership states distinguish a temporary shakeout from genuine control loss.

## Event sample
Using 12% ex-post zig-zag interior pivots in 2026 daily data:
- 499 interior peaks
- 488 interior troughs

The purpose is lifecycle reconstruction, not prospective alpha estimation.

## 1. Peak sequence: the visible market looks strongest immediately before failure
Median event-aligned state around peaks:

| Offset | 5d margin change | 5d short-balance change | volume / 20d median | trades / 20d median | total-institution flow / volume | close location |
|---|---:|---:|---:|---:|---:|---:|
| t-3 | +0.5% | -1.8% | 1.05x | 1.04x | +1.4% | 0.55 |
| t-2 | +1.5% | +2.4% | 1.10x | 1.09x | +3.2% | 0.65 |
| t-1 | +2.9% | +15.7% | 1.30x | 1.19x | +6.2% | 0.72 |
| t0 | +3.6% | +35.4% | 1.54x | 1.44x | +7.4% | 0.82 |
| t+1 | +2.0% | +15.3% | 1.29x | 1.45x | -9.3% | 0.15 |
| t+3 | -1.3% | -10.1% | 0.99x | 1.02x | -3.0% | 0.27 |
| t+5 | -4.4% | -35.0% | 0.87x | 0.90x | -1.7% | 0.34 |

Important: short-balance percentage changes are noisy when the base is small; normalized short-inventory creation is directionally consistent but economically much smaller than margin inventory. Therefore this is evidence that shorting participation intensifies around euphoric peaks, not proof that short sellers create the peak.

## 2. Fast capital turns before leveraged inventory
Peak-day sign sequence:
- 71.7% of peaks have positive total-institution intensity at t0.
- only 23.6% remain positive at t+1.
- 55.7% explicitly flip from positive t0 to negative t+1.
- among peaks with positive 3-day institutional flow and positive 5-day margin growth at t0, the median first negative institutional-flow day is t+2, while the median first negative margin-growth day is t+3.
- in 57.1% of the 177 events where both reversals are observable, institutional flow turns negative before margin does; 15.8% turn together; 27.1% have margin turn first.

Interpretation: visible professional/institutional flow generally reacts faster than leveraged retail inventory, but the ordering is probabilistic, not universal.

## 3. Institutional flip alone is NOT the structural death signal
For complete peak-to-next-trough legs:
- median subsequent decline when a t0-positive institutional flow flips negative at t+1: about -19.5%.
- without that fast flip: about -20.2%.

Therefore `institutional flow flipped` is a speed/asymmetry clue, not what determines how deep the subsequent damage becomes.

## 4. Ownership dispersion is much more important for decline depth
Using the TDCC snapshot 8-14 calendar days after peaks:
- 487 matched peak events
- median Big400 change -0.40pp
- median Big1000 change -0.44pp
- among 325 events with valid holder-count change, 63.7% show `Big400 down + total holders up`.

Complete peak-to-trough decline:
- ownership-dispersion events (`Big400 down + holders up`): median about -21.9%
- other peaks: median about -18.8%

This is retrospective, so not a tradable forecast; structurally, however, persistent outward inventory dispersion matters more than the one-day visible institutional sign flip.

## 5. A visible contradiction is common at the top
Among 325 peak events with valid post-peak holder data:
- 237 had positive total-institution flow on the peak day.
- of those, 65.4% later showed `Big400 down + holder count up` in the 8-14-day post-peak TDCC window.
- 155 events, 47.7% of the full valid sample, simultaneously had:
  1. positive visible institutional flow at the peak,
  2. later Big400 concentration decline,
  3. later shareholder-count expansion.
- 125 events, 38.5% of the valid sample, additionally showed the peak-day institutional flow flipping negative the next day.

Interpretation: `法人仍在買` is frequently compatible with real ownership dispersion. The public institution label is not a control label.

## 6. Rising short inventory in a strong uptrend is a useful disagreement marker, not a controller fingerprint
Among high-attention uptrend days (`20d return >= 15%`, volume >= 20d median), days in the highest quintile of 5-day short-inventory creation were followed by a 12% major peak within five sessions 36.7% of the time, compared with 27.5% in the lowest quintile. Within fixed prior-return bands the high-short group also generally shows more near-term peaks, especially for >40% 20-day gains.

Caveat: this is not threshold-preregistered alpha research and should not be promoted as a rule. It says that the final euphoric phase often contains informed disagreement: leveraged longs are still adding while short-side inventory is also increasing.

## 7. The trough is the mirror, but less symmetric
Around troughs:
- t0: median daily return about -4.4%, 5d margin change about -4.1%, institutional flow about -4.4% of volume, CLV ~0.15.
- t+1: price rebounds about +4.8%, institutional flow turns positive on median, but 5d margin change remains about -2.6%.
- t+5: price is roughly +13.9% from trough, and margin growth has only then recovered to positive territory.

Negative-to-positive institutional sign reversal from t0 to t+1 occurs in about 35.8% of troughs, while negative-to-positive margin reversal occurs in only about 8.5%.

The 8-14-day TDCC window then tends to show Big400/Big1000 rebuilding and holder-count contraction.

## 8. Theme/capital baton is a second mechanism of retail lateness
Existing HENGCE stock-to-stock control research documents repeated source-release / destination-concentration paths:
- 6213 -> 3189
- 3231 -> 3017
- 2337 -> 2344
- other weaker Level-B edges

The important retail implication is not `buy the destination`. It is that strong capital can leave an old winner while the old narrative remains attractive and redeploy into a related name before the old stock visibly collapses. A retail investor who selects using lagging attention can therefore buy the old story exactly while sophisticated inventory is migrating to the next story.

## 9. Public narrative can peak close to inventory transitions without implying manipulation
Concrete 2026 examples from public news:
- 6415 received analyst target/EPS optimism on 2026-06-10 and a further positive target-price story on 2026-06-13, immediately before the 06-12 fear reload -> 06-18/22 euphoric markup/handoff cycle.
- 6213 received FactSet/analyst upgrades on 2026-06-25/26, the same period in which HENGCE observed a massive new-control concentration and subsequent July financing shift.

This does NOT show reports were deceptive or coordinated. It demonstrates the attention channel: legitimate positive information can make a stock maximally visible and liquid at the same time that earlier holders have the best opportunity to transfer inventory.

Taiwan academic evidence independently shows that foreign institutions and domestic mutual funds react aggressively to analyst recommendations/target prices while individual investors often become de facto liquidity providers around analyst-report releases.

## Current forensic interpretation
The strongest evidence currently supports a multi-actor mechanism rather than a single puppet master:

`fundamental/story catalyst -> fast/informed/professional capital trades aggressively -> price/volume/attention amplify -> leveraged/confirmation-seeking retail increases exposure -> some sophisticated short/inventory disagreement appears -> price pivot -> fast visible flow reverses -> retail leverage lags -> ownership either repairs or disperses -> failed repair produces the deeper loss cycle -> capital may rotate to the next related name`.

The actors who profit from the process do not need to manufacture the entire story. They only need to recognize when attention has created abundant counterparties and when fear has created urgent sellers.

## Data ceiling
Fugle connector currently advertises accessible broker-main, 240-day single-broker, and broker-Gini content specs, but direct calls for 6415 and 2330 return empty payloads. Library search also found no historical broker-branch transaction dataset beyond prior governance notes. Therefore no broker/beneficial-owner identity claim is supported yet.
