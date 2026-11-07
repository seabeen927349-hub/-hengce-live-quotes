# 衡策 FinMind 既有血管 × 台股開盤環境｜影子串接

**日期：2026-11-07。定位：只讀市場監測，無選股、下單或正式 Escape 狀態權限。**

## 真正接到哪一條血管？

已存在 `.github/workflows/hengce-escape-twse-full-market-finmind-shadow.yml`，使用 GitHub Actions Secret `FINMIND_TOKEN` 與 FinMind `taiwan_stock_tick_snapshot`，輸出下列**既有**聚合檔案：

- `escape_live/finmind_twse_common_context.json`
- `escape_live/finmind_twse_common_status.json`
- `escape_live/intraday_monitor.json`

新增的 `scripts/hengce_finmind_premarket_bridge.py` **只讀以上三個檔案**。不發出第二條 FinMind API 請求、不複製原始逐檔資料、不建立第二母體。新輸出為 `escape_live/finmind_premarket_bridge_shadow.json`。

## 兩種時間

- **盤前 08:40（台北時間）**：提供前一個已完成台灣交易日 FinMind 全市場漲跌家數與等權平均變動，清楚標示 `PREVIOUS_COMPLETED_TW_SESSION`。它不是當天開盤報價。
- **盤中 09:00–13:45**：待既有 FinMind shadow 更新完成，檢查來源日期是否為今天、最新來源時間是否在 20 分鐘內，再提供 `CURRENT_INTRADAY_OBSERVATION`。*僅能驗證最新來源時間*，不能證明每一檔股票都在 20 分鐘內刷新。

來源過期、缺值、覆蓋率不足或時間錯配一律**不發布新快照**。國定假日開休市未在此橋接中獨立校驗，因此不可藉由週一至週五排程宣稱市場當日一定開市。

## 費半和 VIX 的範圍

FinMind 台股 tick snapshot **不包含 SOX（費半）或 VIX**，不能把它們冒稱為 FinMind 即時數據。橋接器可接收上游獨立、具明確來源時戳的 `HENGCE-PREMARKET-V1` 封包，但必須另外完成海外資料來源驗證。若未提供該封包，就明確輸出 `NO_VERIFIED_OVERSEAS_PACKET`，不得發出假的五級預報。

外資股票買賣超也不等於外資淨匯出，更不能由 tick 快照推算出來。原有 20／40／60 日 Macro 與 Escape 四時鐘均不受本模組覆寫。

## 治理檢查

`metric_contract_sha256`、全上市普通股母體、來源日期、完整度、漲跌家數與原聚合檔案一致性必須通過；且原先狀態的正式決策權限全為 False。橋接結果永久保留 `trading_authority=NONE`。

```bash
python -m unittest discover -s tests/engineering -p 'test_hengce_finmind_premarket_bridge.py' -v
```

## 工作流程

新的 `.github/workflows/hengce-finmind-premarket-shadow-bridge.yml` 會在原 FinMind shadow 工作成功完成後觸發，也在台北時間每週一至五 08:40 執行，並支援手動執行。它只發布可稽核的聚合影子資料到原有 `escape_live/` 命名空間，不變更舊 workflow、EOD、正式選股或風險黑盒。

**生效條件：** 需先合併經檢查的 PR；PR 建立不等於正式日常運行。首次生產執行須用 GitHub Actions log 及產出的 JSON 憑證確認。
