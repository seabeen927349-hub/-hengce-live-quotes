# HENGCE Selection N2/D1 × Top1/Top3/Top5 — Fixed NT$1m, noncompound independent audit

Date: 2026-11-04; verdict: **RESEARCH_PRICE_ONLY / ALPHA_INCONCLUSIVE / TRADING_NO_GO**.

## Reproducibility and non-mutation
- New branch starts from independent deep-vs-weak study SHA `b1d63a01e936f5f4d69ca2e62841f5e7f2f60f54`.
- New K variant and 1m/K allocation preregistered **before the new return computations**, commit `bbd46ae05859af518f8e3423251b0bc0bb5abc5d`, file `N2_D1_TOPK_FIXED_1M_PREREG_20261104.md`.
- Historical sample: exact 76 common valid monthly windows, **2019–2026**; same frozen underlying 84 dates with eight 2018 windows excluded due missing complete 250 prior trading sessions required by D1. Signals, ranks, stocks, entry and exit dates identical to earlier research. K5 152/152 windows independently recalculated with **exact prior PnL parity**.
- Every window is **new independent** NT$1,000,000; no compounding, no carrying forward profit or loss. Per name budget = 1m/K, 1000-share boardlots, unused cash idle. Buy next TWSE open, exit fixed H20 close, no overlapping windows, total 40bps cost on invested amount, 80bps stress. Sums below are 76 separate one-million-window PnLs, **not** any real continuously funded portfolio terminal account.
- Raw historical price, corporate actions and price revisions not yet independently adjusted/certified. No broker-order or capital authority.

## Six-arm same-date matched results: sum of fixed 1m PnLs (TWD), raw price-only

| Strategy | Top1 | Top3 | Top5 |
| --- | ---: | ---: | ---: |
| N2 5d-weak-return-rank | **+3,217,226.80** | +1,225,751.80 | +904,600.68 |
| D1 250d deep + 60d underperformance | +1,117,470.80 | +656,698.96 | +482,629.36 |

At 80bps cost:
- N2 K1 +2,960,553.60; K3 +1,027,453.60; K5 +743,761.36.
- D1 K1 +875,681.60; K3 +498,227.92; K5 +384,728.72.

## Capital deployment, sample and risk

| Family | K | Average invested percent of each 1m | Purchased positions | Positive / negative / zero events | 2024 summed PnL | Sum after removing top five profitable events |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| N2 | 1 | 84.43% | 71 | 40/31/5 | **-468,299.60** | +674,892.80 |
| N2 | 3 | 65.23% | 177 | 44/30/2 | -108,495.20 | +90,533.80 |
| N2 | 5 | 52.91% | 251 | 40/35/1 | -28,817.20 | +56,323.48 |
| D1 | 1 | 79.54% | 66 | 32/34/10 | +92,829.60 | **-752,262.80** |
| D1 | 3 | 52.13% | 143 | 33/32/11 | +151,700.60 | -206,301.44 |
| D1 | 5 | 32.20% | 150 | 34/28/14 | +95,535.20 | -55,906.44 |

- Relative to the **actual invested principal summed over events**, raw-price-only PnL ratios (not annualized) are N2 K1 **+5.01%**, K3 +2.47%, K5 +2.25%; D1 K1 +1.85%, K3 +1.66%, K5 **+1.97%**. D1 K1's higher unnormalized total is not evidence of greater selection skill than D1 K5, since K1 deployed far more capital.
- N2 Top1 best single event signal **2025-12-31**, ticker **2313**, next open 93.9, exit H20 close 178, 10×1000 shares, **+837,244** net 40bps. Worst single event signal 2022-03-31 **-278,004**. One best event is about **26%** of its entire 76-window summed profit. N2 Top1 **2024 -468,299.60** despite positive overall.
- D1 Top1 best event +533,660, 47.8% of total; removing best three event wins makes aggregate **-224,882.80**.
- Risk is concentrated in single stock exposure; no portfolio stop strategy specified, no claim that drawdown is bounded by observed event lows.

## Paired N2 date evidence, not pristine OOS

- N2 K1 vs N2 K5: +NT$2,312,626.12 difference in same 76 windows; 10,000-year-block-bootstrap descriptive 95% CI of **mean per window difference** [+NT$3,628.53, +NT$52,873.40]. This does not establish external forward alpha due retrospective K comparisons and tested designs.
- N2 K1 vs N2 K3: +NT$1,991,475; mean CI [+NT$3,095.39,+NT$46,599.25].
- N2 K1 vs D1 K1: +NT$2,099,756; mean CI **[-NT$5,850.32,+NT$58,750.93]**, crosses zero: superiority between families **not statistically established**.
- All six K books priced for 76 windows with no purchased-name missing-exit blocker in this sample.

## Tests, verifiability and package
- `73/73 pytest` passed; includes source file SHA, all 84/76 gates, rank prefix, no rerank, dated parity with all 152 original K5 results, 40/80bp cost, independently reconstructed 1m/K lots, invested plus idle exactly 1m per event, no future exit fabrication, annual arithmetic, corporate-action exposures, paired date integrity.
- Frozen parent inputs and source are bundled in Library ZIP `/HENGCE/Research Outputs/SELECTION_N2_D1_TOPK_FIXED1M_20261104/HENGCE_N2_D1_Top1_Top3_Top5_Fixed1M_NoCompound_20261104.zip`. File SHA256 `0e3535d8b5877b1ab9c1d620edde84badde4213449780d2741f29b47ccf5813c`.
- Bundle contains code, tests, full JSON, all 456 strategy-event records, ticker-level records, annual table, 152 original top5 parity receipt, frozen inputs, human README and per-file SHA manifest. Exact test evidence in `pytest.log`.

## Independent verdict
1. **Research priority:** N2-K1 (not formal deployment), N2-K3 and K5 as concentration controls. D1 K1, K3, K5 retained as separate deep-pullback hypotheses, not merged or retuned.
2. **Key blockers:** PIT corporate action true-total-return & cash/share/rights accounting; current-vs-historical security status certification; next-open executability, price source revisions, proper market-index same-geometry benchmark; untouched forward OOS; risk limits for single-name sleeve.
3. No changing model rule or choosing new thresholds based on this historical winner. **Trading authority NONE**; keep honest status ALPHA_INCONCLUSIVE.
