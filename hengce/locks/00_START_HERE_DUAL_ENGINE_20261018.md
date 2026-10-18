# 衡策雙引擎接續入口 — 2026-10-18

這份文件是新對話/新工作階段的第一入口。

## 目前衡策只有兩個正式顯示引擎

### Engine 1 — Q017（研究資金 200 萬）
- 完全凍結。
- 唯一權威參數：`HENGCE_DUAL_ENGINE_LOCK_20261018.json` 內的 Q017 區塊。
- SOX 1D <= 0；SOX 5D <= -2%；residual <= 4%。
- score = beta * (1 + 25 * max(-residual, 0))。
- Top 3；研究持有 10 日。
- 舊文件若出現 SOX 5D <= -3% 或 DXY gate，視為 stale prose，不得採用。

### Engine 2 — E2（研究資金 300 萬）
- Frozen challenger，非 production OOS。
- 母體：正式 strong / D-Setup candidates。
- 同一訊號日做相對排序，只看三項：
  1. inst_ratio5 高於同日中位數。
  2. tight_ratio <= 同日中位數。
  3. dist20high <= 同日中位數。
- 3 中至少 2 項才是 favorable。
- ROLLING_OVER = DEGRADED。
- SOX 只作環境/相對韌性層：費半受壓、個股仍抗跌可提高優先級；SOX 強勢不得放寬 2-of-3；E2 沒有硬性 SOX 門檻。
- 研究持有 5 個交易日。

## 使用者說「衡策掃一次」時
必須同時輸出兩套，禁止混榜：

1. Q017：ON/OFF、Top1-Top3、score、SOX 狀態、持倉/動作、200萬資金使用情況。
2. E2：ON/DEGRADED/OFF、市場 regime、SOX 壓力/韌性、候選的三項勾選、2/3 或 3/3、BUY/WATCH/PASS、300萬資金使用情況。
3. 總結：今天買什麼、賣什麼、續抱什麼，以及兩個研究桶剩餘資金。

## 全域交易限制
- 現股、多單。
- 不借券、不放空、不當沖、不融資、不槓桿。
- t 日收盤後訊號，最早 t+1 台股交易日執行。
- 回測成本預設 round trip 0.6%。

## E2 2026 研究參考（不得冒充 OOS）
- favorable N = 95。
- 5D mean = +3.88%。
- 5D median = +2.30%。
- 去掉前5大贏家 mean = +2.82%。
- 去掉前10大贏家 mean = +2.12%。

## 防漂移硬鎖
- 不再替 E2 新增第4、第5個個股因子。
- 不再調 SOX 門檻尋找最好看的 2026 數字。
- 不得把 E2 重新包裝成 Q017。
- 不得因舊 handoff prose 與 lock 衝突而覆寫 lock。
- 若要研究新變體，必須另開新 challenger 名稱，不能修改本版。

詳見：
- `HENGCE_DUAL_ENGINE_LOCK_20261018.json`
- `HENGCE_DUAL_ENGINE_SELF_CHECK_10X_20261018.md`
