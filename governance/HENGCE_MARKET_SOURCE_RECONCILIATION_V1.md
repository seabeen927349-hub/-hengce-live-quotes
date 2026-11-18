# HENGCE 市場來源差異影子報告 V1

以 HBA 研究卡的已核驗股價腿作母體，讀回卡片分片並確認代號集合、
股價腿 SHA、Mother SHA 與升格時點相符。輸出綁定 manifest SHA、各卡
canonical JSON SHA、各來源檔 SHA 及既有 schema/contract。仍屬影子用途。
本工具沒有網路請求、排程或正式掃描接線。

| 來源 | 既有可用欄位與作業 | 保存及缺口 |
| --- | --- | --- |
| FinMind | 既有 Escape 盤中排程約每五分鐘採集全上市普通股 `taiwan_stock_tick_snapshot`，含逐股最新價、時間與量額欄位。已保存 context/status/monitor 只含產業及市場彙總、時間、完整率及合約 SHA。 EOD 另有既有衍生彙總。 | 逐股原始快照只用於既有 runner 記憶體。11/17 市場彙總為 1,084 / 1,088，逐股可比數維持 0。歷史 `TaiwanStockPrice`、`TaiwanStockPriceAdj` 與 `TaiwanStockDividend` 為既有個股研究契約列出的資料集，這次沒有在本母體核驗逐股內容、公告證據或現有方案再發布權。 |
| Fugle | 既有逐股 quote transport 可接最新成交價、成交時刻、OHLC、量、最佳買賣價與量；11/17 私人留存的收盤觀測有 OHLC、漲跌、張數及成交時間。 | 3 檔有私人收盤觀測。市場全量快照、歷史 K 線與公司行動的現有授權與可讀回內容未由本次逐股樣本證明。報告只留比較狀態、差異欄位名稱與 SHA，原報價和報價量維持原保存範圍。 |
| TWSE | 沿用正式 EOD 三腿、交易日曆、Mother 收據與 PR-3 TAIEX、停復牌、終止上市、除權息證據。 | 仍須有受信來源的開盤交易狀態及完整公司行動覆蓋。證據缺席保持 UNVERIFIED。 |

## 使用與判讀

```sh
python scripts/hengce_hba_market_source_reconcile.py \
  --cards /path/to/verified-hba-artifact \
  --twse-evidence tests/hba_surveillance/fixtures/twse_reference_original \
  --fugle /private/path/realtime_quote_observations_latest.json \
  --fugle-sha SHA256_FROM_PINNED_PRIVATE_ARTIFACT > /tmp/reconcile.json
```

Fugle 可省略。讀入私人觀測時記錄本次實際讀取時間，晚於 --asof 時拒用。
原始收件時間缺失時留空，收盤時間不冒充收件時間。FinMind 將既有 generated_at 視為工作開始時間，另核對市場來源時點和本次完成讀取時間；
讀取晚於資訊截止時拒用，原收件時點留空。舊日回讀標記為
HISTORICAL_REPLAY。若比較的兩側開高低收與收盤語意有效，數值一致為
VERIFIED_SHADOW，有差異為 CONFLICT。張數、股數及盤後零股等口徑未建立
同口徑收據前不比較量。逐股有成交不確立開盤可交易。未有已核驗除權息、
股本與公司行動資料時保留未知。

11/17 正式 HBA artifact 14416705399 加上既有私人 Fugle 封存的實測結果：
原 EOD 正式有效收盤 1,089 檔、缺 2 檔；Fugle 同日收盤 OHLC 比對 3 檔、
缺比較資料 1,088 檔、觀測到的衝突 0。FinMind 彙總 1,084 / 1,088 是其監測
口徑，對 1,091 母體的逐股可比列為 0，逐股均 UNVERIFIED。開盤交易狀態與
公司行動均為 1,091 檔 UNVERIFIED。各資料集仍依原供應商條款處理，不增加
API 額度、儲存範圍或授權。此工具不改變正式 EOD、V2.2D、選股、結算或 AWS。

## PR-4 最後實證驗收

[可公開驗收收據](../tests/hba_surveillance/fixtures/market_source_20261117_acceptance_receipt.json)
取自 2026-11-18 18:18:38 台北時間的實際回放。完整報告
`hengce-pr4-20261117-final-acceptance.json` 保留於工作區
`/workspace/shared/downloads/`，SHA-256 為
`a99b08163145bc6346155a85054817b3f9670ec6507514248397b7d9b3eab666`。
在 repo 中保存可公開收據，用於回查該報告與原輸入；報價仍只保存在既有私人股價檔。
收據列出 HBA ZIP、manifest、正式價量腿證據及 FinMind 三份原彙總 SHA。
使用上方 CLI 可重算同日比較。新執行帶有實際新讀取時刻，因此新報告雜湊會變動。

Fugle 原檔可由有權限者在私人 `twse--backfill-test` 的
`74d758cd1fc51da04381bd68c085a4be63bb15f7` 提交讀取
`hengce/private_v22d_autoscan/reports/realtime_quote_observations_latest.json`。
Git blob 為 `ddba5ec2598b8534606cd16e67bfc7b011c499c2`。三筆
2610、6782、9933 的同日收盤 OHLC 皆一致，僅有市場時刻 11/17 13:30，
原始供應商首次收件時間缺失。11/18 18:18:38.897893 為本次實際讀取時刻。
這三筆來自原留存觀測而非合成測試。其他 1,088 檔缺可比 Fugle 觀測。

實際 FinMind 產物核對了 1,088 操作範圍、1,084 有效觀測及 0 檔逐股跨來源
對帳。程式碼驗證既有 runner 在彙總前仍有 raw_rows 與逐股時間，可做
同次執行來源交集的記憶體內對帳；現有 TWSE MIS 僅按部分回補代號讀取，
用途為交易狀態，未持有全市場的第二份同時點、同口徑行情。本輪未執行
實際全市場逐股對帳或新增請求。未來僅在條款確認允許時保存比對筆數、
差異分布、原因碼與來源 SHA。工作開始時間與實際收件時間應分開記錄。
