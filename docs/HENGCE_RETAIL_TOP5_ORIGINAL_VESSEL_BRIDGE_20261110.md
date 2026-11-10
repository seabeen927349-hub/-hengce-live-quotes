# 衡策 RETAIL Top5 V2.2 原血管資料接合（唯讀 / 研究資料層）

## 接合範圍
本接合不新設市場母體、不呼叫新資料供應商、不竄改任何 EOD／集保血管，也**不直接執行選股**。

| 模型輸入或輔助欄位 | 原始血管 | 接合方式 | 權限 |
|---|---|---|---|
| Date, Ticker, Close, Volume, Turnover | `eod/YYYYMMDD/price_[1-9].csv`，搭配同目錄 `status.json`、`receipts/price.json` | 精確對照原始檔 SHA、母體完成狀態；VolumeShares 為股、TurnoverTWD 為新臺幣 | 只轉換，不補價；缺21個完整交易日就阻擋 |
| SnapshotDate, Ticker, HolderLe10Lots, RetailPeopleValid | `ownership/tdcc/YYYYMMDD/tdcc_1_5_raw.csv`、`receipt.json`、`provenance/first_observed/{sha}.json` | 僅加總官方 1、2、3 級距之實際人數；驗證來源雜湊、首次觀測時間；僅取決策日之前可知、再延後14天的三期快照 | 非官方公告時間；PIT 證據缺漏不通過 |
| Fugle | 原 `live/status.json` + 原 live 報價血管（既存 `scripts/hengce_live_quote_transport.py`） | 只確認最新報價血管是否具時效，做後續限價／跳空人工核對 | 不替代收盤價、不進歷史動能訊號 |
| FinMind | 同一 `eod/YYYYMMDD/market_state_finmind_context.json` 與狀態 SHA | 僅附帶已驗證之全上市市場背景與其來源狀態 | 只有 aggregate，沒有可用的逐股 FinMind 日線，不拿來填缺價 |

## 執行方式

```bash
python scripts/hengce_retail_top5_vessel_bridge.py \
  --repo-root . --decision 2026-11-06 --output /tmp/retail_bridge_20261106
```

狀態檔 `bridge_status.json` 一律輸出；只有原血管 21 個以上可驗證日線交易日、決策當日 EOD、三期具首次觀測證據的連續 TDCC 快照皆完整時，才輸出 `daily.csv` 與 `weekly.csv`。若阻擋，程式以 exit 2 結束、**不產生可冒充選股輸入的 CSV**。所有輸出只可寫至**衡策 GitHub 倉庫根目錄之外**的明確新建路徑；即使指定原 EOD、TDCC 或研究目錄的子目錄也會拒絕，原血管內容完全不變。

`daily.csv` / `weekly.csv` 欄位形式與 V2.2 相容，但 V2.2 原版 `provenance.py` **只允許鎖定 2026-11-06 原附件位元組**，本橋不修改其 SHA、不啟動 model CLI、不繞開來源契約；須另經文獻 Gate、首次觀測驗證、外樣本測試及正式治理後才能建立新的受控資料基準並啟用模型。PR #64 仍維持 DRAFT。

## 2026-11-10 資料可用性
2026-11-10 倉庫當時 `eod` 可見約18個日期目錄，少於21個交易日需求；`ownership/tdcc` 僅有 10/22、10/30、11/06 三期原始快照，其中 `10/22` 缺本版要求的 first-observed 證據，`10/30` 舊 receipt 時點與更新規格首次觀測紀錄也不完全一致。Fugle `live/status.json` 指向 10/27 快照，非當期盤中報價。FinMind 只有研究輔助的 aggregated market-state context。**不能宣稱已可用既有血管直接產出最新 Top5 正式買點。**

## 權限
本程式屬於既有血管的 **資料整理與來源完整性稽核**，不計算價格強弱或任何選股訊號；沒有正式 selection、RMS、S5、Escape、資本、券商下單或 Q017 復活權限。所有規則都必須與 `governance/HENGCE_LITERATURE_GATE_CONTRACT_v1.json` 等正式治理相容。