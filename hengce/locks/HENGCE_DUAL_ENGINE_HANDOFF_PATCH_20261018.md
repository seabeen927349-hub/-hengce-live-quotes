# 衡策雙引擎換對話補丁 — 2026-10-18

用途：搭配既有 `衡策完整接續包_20261018_SCAN_HARDLOCK_SELFCONTAINED_5X` 使用。新對話若同時收到舊完整包與本補丁，**本補丁對雙引擎規則、Q017參數、E2規則與顯示契約具有較高優先權**。

## 一、衡策正式顯示為雙引擎

### Q017 — 研究資金 NT$2,000,000
- FROZEN_DO_NOT_MUTATE。
- TWSE listed electronics。
- SOX 1D <= 0。
- SOX 5D <= -2%。
- residual <= 4%。
- score = beta * (1 + 25 * max(-residual, 0))。
- beta observations 30–60。
- Top 3。
- research hold = 10 trading days。
- 舊文件若出現 SOX5D <= -3% 或 DXY gate，全部視為 stale prose，不得覆蓋本版。

### E2 — 研究資金 NT$3,000,000
- FROZEN_CHALLENGER_NOT_PRODUCTION。
- Parent universe = formal strong / D-Setup candidates。
- 同日相對排序三條：
  1. inst_ratio5 > same-date median。
  2. tight_ratio <= same-date median。
  3. dist20high <= same-date median。
- 至少 2/3 favorable 才進 E2 favorable。
- ROLLING_OVER = DEGRADED。
- SOX僅作環境與相對韌性層：SOX受壓而個股仍強可提高優先；SOX強勢不能放寬2-of-3；E2沒有硬SOX門檻。
- research hold = 5 trading days。
- 2026 same-sample reference only: N=95, mean5D +3.88%, median5D +2.30%, ex-top5 +2.82%, ex-top10 +2.12%。不得稱為OOS production return。

## 二、全域交易限制
- 現股。
- Long only。
- 不借券、不放空、不當沖、不融資、不槓桿。
- EOD signal，最早下一個TWSE交易日執行。
- research round-trip cost assumption = 0.6%。

## 三、「衡策掃一次」固定輸出契約
必須同時掃兩套，不得混榜：

### Q017區塊
- ON/OFF。
- Top1–Top3。
- Q017 score。
- SOX狀態。
- 持倉天數 / buy / hold / sell / pass。
- 200萬桶已用 / 可用。

### E2區塊
- ON / DEGRADED / OFF。
- MarketRegimeState。
- SOX環境：順風 / 中性 / 壓力。
- 每檔：inst_ratio5 ✓/✗、tight_ratio ✓/✗、dist20high ✓/✗、2/3或3/3、SOX韌性、BUY/WATCH/PASS。
- 300萬桶已用 / 可用。

### 總結
- 今日買什麼。
- 今日賣什麼。
- 今日續抱什麼。
- Q017與E2各自剩餘資金。

## 四、10X自檢結果
1. Q017 contamination — PASS。
2. Q017 parameter consistency — PASS；-2%為權威值。
3. Dual-engine independence — PASS。
4. Point-in-time causality — PASS。
5. Trading constraints — PASS。
6. E2 factor freeze — PASS；只准3個因子。
7. SOX role — PASS；overlay only。
8. Market regime — PASS；ROLLING_OVER DEGRADED。
9. Capital isolation — PASS；2m/3m分桶。
10. Handoff/scan anti-drift — PASS；「衡策掃一次」固定雙引擎。

## 五、防漂移硬鎖
- 不替本版E2增加第4、第5個個股因子。
- 不用2026結果回頭調SOX門檻。
- 不把E2包裝成Q017。
- 不允許舊handoff prose覆寫lock。
- 新研究必須另開新challenger名稱。

## 六、新對話啟動句
收到舊完整包 + 本補丁後：

> 先讀完整包，再以 HENGCE_DUAL_ENGINE_HANDOFF_PATCH_20261018 為雙引擎最高優先規則。確認 Q017=200萬、E2=300萬、交易限制與10X自檢均載入。之後我說「衡策掃一次」，固定同時掃Q017與E2，不得混榜，不得改規則。
