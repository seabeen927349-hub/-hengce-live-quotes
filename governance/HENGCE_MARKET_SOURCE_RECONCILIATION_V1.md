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
