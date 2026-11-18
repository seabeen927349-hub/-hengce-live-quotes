# HENGCE FinMind 記憶體內逐股同時點候選驗證 V1

## 已確認的根本限制

既有 Escape 盤中 FinMind runner 單次取得全上市普通股 `taiwan_stock_tick_snapshot`，
在 `collect()` 的 `raw_rows` / `snapshot_map` 中有逐股資料，但**只發布聚合資訊**。
本 PR 在相同程序的記憶體內，將已存在的逐股 FinMind 資料與**原本就為過期代號取得的**
TWSE MIS `mis_matches` 進行有限的候選對帳，**不新增任何 FinMind、MIS 或 Fugle 請求**。

現行 MIS 是「FinMind 過期股」才會呼叫，而且只查那些代號；對正常新鮮的 FinMind
代號，沒有第二來源。即使剛好有同時點價格吻合，也只記
`MATCHED_TRADE_TIME_PRICE_CANDIDATE`，**不升格為已核驗全市場第二來源**。

## 資料規則

- FinMind 收件時點在 `await client.query_endpoint(...)` 完成後記錄，不使用工作開始時間冒充收件。
- 使用 FinMind 已有 `date` 和 `close`；MIS 已有 `d`、`t`、`z`。
- 日期須同交易日；FinMind 與 MIS 距離現有 runner 完成時間各不得超過 90 秒，時間戳差不超過 1 秒。
- **注意**：兩個來源的時間欄位與價格欄位尚未證明完全相同交易語意，所以一致／差異都只屬「候選」，非正式衝突判定。
- 不能只以 MIS 現有日期、FinMind 日期或日內有成交，推論股票已在開盤可交易。
- 缺第二來源、時間不一致、價格不可比、非本日資料均以分類原因碼呈現，不填零、不補造。
- 僅在 runner 記憶體使用兩組逐股資料，不保存股號、逐股價量、原始 MIS 或逐股比價結果。
- 公開輸出只含全母群分母、各原因數量、接收時間與候選數；`fully_independently_verified_count = 0`。
- 保留 FinMind 原市場數據指標、Mother、TWSE EOD、Fugle、V2.2D、交易授權與正式結算原有治理。

## 驗收

本 PR 新增純函式 `scripts/hengce_finmind_inmemory_same_tick_audit.py`，
並接進**既有** `scripts/hengce_escape_finmind_twse_common_shadow.py`，
讓 `context` 與 `status` 多出 `inmemory_cross_source_audit`（彙總而非行情）。
現有 GitHub workflow 增加離線測試，不新增排程或正式發布器。

驗證：

```sh
python -m unittest discover -s tests/engineering -p 'test_hengce_finmind_inmemory_same_tick_audit.py' -v
python -m unittest discover -s tests/engineering -p 'test_hengce_finmind_intraday_freshness_gate.py' -v
```

本輪在 2026-11-18 台股收盤後開發，**未聲稱已完成當日真實全市場跨來源同時點驗證**。
只有 PR 通過且合併、下一個正常盤中 runner 產生真實聚合輸出後，才能報告實際
`reason_counts`。而且在**不增加第二來源覆蓋**的前提下，已驗證全市場比例仍為零；
若目標要求全市場逐股跨來源同時點校驗，仍需要明確界定來源授權、取得可比第二來源、
時間差容忍度與新採集請求負擔，須獨立批准，不能把 FinMind 1,084/1,088
市場觀測直接當成跨來源驗證。
