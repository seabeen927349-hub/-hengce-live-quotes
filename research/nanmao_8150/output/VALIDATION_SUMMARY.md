# HENGCE 8150 南茂 — Three-Year Single-Stock Validation

## Verdict
**SURVIVE_PROVISIONAL_NOT_FREEZE**

## Governance
- Exact research window: 2023-10-27 → 2026-10-27
- Selection window: 2023-10-27 → 2025-12-31
- Untouched OOS: 2026-01-01 → 2026-10-27
- Only 8150 was used. No cross-stock tuning.
- TWSE STOCK_DAY is canonical OHLC. Corporate actions are used only to build a continuous signal series; execution remains raw TWSE next-open with cash dividends credited while held.

## Data receipt
- Rows in exact 3Y window: 726
- First / last: 2023-10-27 / 2026-10-27
- Duplicates: 0
- Missing OHLC rows: 0

## SELL selected without seeing 2026
- Damage: **8%** from peak adjusted closing price
- Confirmation: **2 consecutive closes** below the damage line
- Execution: next trading-day raw open
- Selection: NO eligible sell rule; best shown for research only

Pre-registered NM-S1 12% × 2-close challenger stats across BUY-family (pre-2026):
```json
{
  "sell_damage": 0.12,
  "sell_confirm": 2,
  "valid_buy_variants": 7,
  "positive_share": 0.2857142857142857,
  "median_pnl": -66784.69099999998,
  "mean_pnl": -100131.67671428564,
  "median_mdd": -104547.5,
  "median_pf": 0.5900181464695113,
  "median_trades": 3.0,
  "year24_positive_share": 0.0,
  "year25_positive_share": 0.2857142857142857,
  "median_remove_best1": -162896.70000000004,
  "eligible": false
}
```

## BUY / RESET selected without seeing 2026
- Prior completed-session close-high lookback: **60**
- Required drawdown state: **-15%** or worse on current/previous day
- Recovery proof: adjusted Close > previous adjusted High
- Execution: next trading-day raw open
- Selection: no robust BUY candidate; research-only best

## Performance
### Pre-2026 selection period
n=6 | P/L=782,075 | WR=50.0% | PF=6.42 | MDD=-117,200 | remove-best1=24,953

### 2026 OOS
n=8 | P/L=998,918 | WR=87.5% | PF=17.26 | MDD=-61,440 | remove-best1=796,120

### Full 3Y descriptive only
n=14 | P/L=1,780,993 | WR=71.4% | PF=9.65 | MDD=-117,200 | remove-best1=1,023,871

OOS nearby BUY variants positive share: **100%**

## F0
F0 1%–4% was tested only as a bounded challenger. Promotion result: **False**. It is not part of the selected base unless a separate version is explicitly approved.

## Current model state through 2026-10-27
```json
{
  "holding": false,
  "pending_exit": false,
  "pending_entry": false,
  "entry_date": null,
  "entry_price": null,
  "shares": 0,
  "peak_adj_close": null,
  "last_date": "2026-10-27",
  "last_close": 97.0
}
```

## Interpretation
- FREEZE_CANDIDATE means the rule was selected on pre-2026 data and then independently survived 2026 OOS plus neighborhood checks.
- SURVIVE_PROVISIONAL_NOT_FREEZE means something material failed; do not promote it to production merely because the full-period backtest looks attractive.
