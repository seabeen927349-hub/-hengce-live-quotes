# HENGCE N2 Top1 — 2024 年虧損集群查核與失效機制探索
日期：2026-11-04
authority: RESEARCH_ONLY / POST_HOC_DESCRIPTIVE_FORENSICS / NO_NEW_FILTER / TRADING_NO_GO
source frozen branch: research/n2-top1-fixed5m-no-compound-20261104
source SHA: edc6a713b6a640738773ba1957d8c95fa82e3b71

## 第一件事：核對事實，不接受未驗證的「9 次都賠」

以訊號日所在年份分類，2024 年 **9 次進場、2 勝 7 敗、淨虧 NT$2,643,856.40**；每次獨立固定投入 NT$5,000,000、不複利、僅 Top1、次日開盤、持有含進場日在內20個TWSE交易日、來回成本40bps。2024-12-31訊號在2025-02-07才出場；2023-12-29訊號在2024年出場但不屬於2024訊號 cohort。

| Signal | Ticker | Exit | PnL (NT$) |
|---|---|---|---:|
| 2024-01-31 | 8210 | 2024-03-11 | -444,108.00 |
| 2024-03-29 | 2301 | 2024-04-30 | -117,992.00 |
| 2024-04-30 | 6139 | 2024-05-29 | -937,404.00 |
| 2024-05-31 | 2059 | 2024-07-01 | +241,520.00 |
| 2024-07-31 | 3443 | 2024-08-28 | -238,800.00 |
| 2024-08-30 | 6442 | 2024-09-30 | -499,872.00 |
| 2024-09-30 | 3661 | 2024-11-01 | +54,040.00 |
| 2024-11-29 | 6706 | 2024-12-27 | -630,036.00 |
| 2024-12-31 | 2408 | 2025-02-07 | -71,204.40 |

Derived from frozen original `n2_top1_fixed5m_20261104/all84_trades_fixed5m.csv`, source SHA256 `ca97f13879e7cf81b87093a114e429951383a7cc4e5055fb76e8b0b1d61bd1b6`, checked against yearly TWSE electronics prices. No stock, date, sale or cost substitutions.

## 真正的寶藏不是「9 筆全輸」，而是「大盤上升，選股卻嚴重落後」

- TAIEX calendar-2024 first-to-last price index change: **+29.02%** (context only, not strategy-investable return).
- In the 9 **entry-day CLOSE to H20 exit-day CLOSE** matched windows, TAIEX was up **7/9**, and selected individual stock's raw close/close return **underperformed TAIEX 8/9**; average stock minus market difference **-7.28 percentage points**.
- Both stock and TAIEX are compared with *same close-to-close geometry* for this diagnostic; it is not the original N2 next-open bought-price PnL and does not include dividends or costs.
- Other 75 N2 Top1 historical events: **44 wins / 31 losses**, average gross-window PnL net 40bp **+NT$300,358.61** per fresh NT$5m (versus 2024 average **-NT$293,761.82**), mean stock-minus-TAIEX same-close-window excess **+4.36 percentage points**.
- 2024 only **1/9** N2 signal-side preceding 5-day windows had a recorded corporate action; **0/9** held positions had recorded holding-period corporate action in frozen ledger. Signals/returns still need full economic PIT adjustment; it is incorrect to automatically blame 2024 losses on dividends.

## What was knowable at signal time — exploratory, not fitted filters

- 7/9 2024 signal dates had positive trailing 60-session TAIEX price return; 2025–26 also saw strong TAIEX prior60 trends in 15/18 N2 opportunities while producing positive annual PnL, so the crude rule `TAIEX 60d > 0 => abstain` is NOT justified.
- 2024 selected names had worse prior-60-session return than TAIEX **5/9**. Other 75 dates had that condition **36/75**; prior60 stock-vs-market negative alone does NOT separate bad-2024 from other years.
- Of 9 sample entries, approximately five picked names previously underperformed market on prior60; the other four demonstrate that even positive prior60 relative strength does not guarantee future reversal.
- No post-hoc threshold optimization, no new veto rule, no attribution to unobserved volume/orderflow.

## Statistical caveats

2024 was inspected **after** recognizing unusually poor performance in a 2018–2026 already-open historical sample. It is *not* a preregistered untouched segment. Any exploratory binomial or calendar-specific test is subject to the look-elsewhere problem; DO NOT claim validated external predictive power.

## Study recommendation, no model changes yet

The concrete failure hypothesis is **weak-stock trap in otherwise rising/constructive markets**: N2 short-term return rank sometimes catches individual stocks that continue to underperform, not mean-revert. Test in independent shadow research with signal-time information only: historical individual 20/60-day relative trend, broader electronics breadth and trend, vol & liquidity, previous fall persistence; before proposing any filter, first repair PIT corporate actions, legal stock class and execution. Keep unchanged N2 Top1 as reference; on historically exposed 2018–2026 do NOT select optimum risk thresholds then claim new OOS. Prospective, immutable zero-capital testing needed.

## Reproducibility package

`/HENGCE/Research Outputs/N2_TOP1_2024_LOSS_FORENSICS_20261104/`:
- `HENGCE_N2_TOP1_2024_LOSS_FORENSICS_20261104.zip`
- `2024_nine_trades_verified.csv`
- `all84_regime_descriptive_features.csv`
- `summary.json`, `run.py`, `READ_FIRST.md`, SHA manifest

No changes to main, original Canonical or frozen Selection/Q017/Escape. Trading authority NONE.
