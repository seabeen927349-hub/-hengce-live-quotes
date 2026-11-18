# HENGCE HBA 研究封存與觀察結果 V1

## 封存與生效時間

研究時間沿用 PR-1 manifest 的證據截止時間。封存包含當時的 manifest 與各分片原始位元組、來源時間、SHA、版本、研究條件及模型入選驗證狀態。快照 ID 由模式、市場日、形成時間和研究版本決定，逐股事件 ID 另綁定股票代號。相同事件再次寫入時逐位元比較。同一 ID 的不同內容視為衝突。

本機工具僅接受 `HISTORICAL_REPLAY`，用於既有資料與 GitHub PR 驗收。沒有事前回執的歷史卡不得轉列真實前瞻。正式 `PROSPECTIVE` 以 S3 物件版本的 LastModified 為發布時間，並驗證來源時點、物件 SHA 和版本的保留鎖。匯入或延遲歸檔仍由當次實際存入時間起算。

## 正式儲存部署

使用獨立 S3 bucket，開啟版本化與 Object Lock，預設 `COMPLIANCE` 保留至少 365 日。無保留鎖、版本 ID 或可靠讀回時不發出可用回執。Archive job 使用既有 HBA 觸發，未設定 `HENGCE_RESEARCH_ARCHIVE_ENABLED=true` 就不執行。須由維護者設定 `hengce-research-archive` GitHub environment，只允許受保護的主分支工作流程，並設定 `HENGCE_RESEARCH_ARCHIVE_ROLE_ARN`、`HENGCE_RESEARCH_ARCHIVE_REGION`、`HENGCE_RESEARCH_ARCHIVE_OWNER`、`HENGCE_RESEARCH_ARCHIVE_BUCKET`。

OIDC 身分只允許該 repository 和環境。封存與結算角色只允許對指定的
`hengce/hba-research/v1/PROSPECTIVE/` 前綴建立新物件和讀取版本、保留資料。
Bucket policy 須對該前綴所有寫入者強制 `If-None-Match: *`，禁止刪除、
新增刪除標記、直接修改 retention、無條件上傳及繞過保留。基準與交易狀態
發布者使用不同身分及 `hengce/hba-research/v1/references/` 前綴。
應以實際 bucket 測試同鍵複寫與刪除被拒絕，再啟用。
依 key 與 version ID 可重建完整封存，不須讀取原 Actions artifact。
授權、儲存實際保留年限、成本及升級由維護者核准。

## 結算契約

`scripts/hengce_hba_research_outcomes.py` 對指定快照和 `--ticker` 或
`--all` 計算。真實前瞻用 `--bucket`、`--owner`、`--key`、
`--version-id` 和當前時間；設定 `--reference-key` 與 `--reference-version`
選擇另外發布的鎖定參考資料。回放只用 `--replay`，可指定
`--historical-asof` 及以 SHA 指定的本機參考檔。正式尚無已核驗參考物件時
回報資料不足。後續結果另存至 `PROSPECTIVE/outcomes/`，內容定址，重試同一
結果會讀回原版本。新結果以完整快照 SHA、參考資料 SHA、每個交易日來源 SHA
及結果版本追蹤。

鎖定參考 JSON 結構如下。

```text
policy: {version: HENGCE_HBA_RESEARCH_OUTCOMES_V1, benchmark: TAIEX,
         min_volume_shares: 正整數, cost_bps: {buy_fee, sell_fee, sell_tax, slippage_per_side}}
sessions[YYYY-MM-DD].benchmark: {status, effective_date, available_at, sha256, source, open, close}
sessions[YYYY-MM-DD].stocks[代號]: {status, effective_date, available_at, sha256, source,
                                 trading_status, corporate_action}
```

只有正式價格腿與 Mother 收據的位元組和日期均核驗，且參考資料已發布，才使用該日。
首個開盤必須嚴格晚於發布時間，開盤日為第 1 日。使用開盤到第 5、10、20 個
正式交易日的收盤，最大回撤取起始開盤及每日收盤路徑。超額報酬使用同窗 TAIEX
開收盤價差。同步提供扣除預先指定費、稅與滑價的示意長部位報酬。價格區間失效
由觀察窗內第一個超出既有上下界的正式收盤認定。開盤價及日量只能用於描述及
流動性篩檢，無法確認實際成交。停牌、下市、低量、除權息或調整未核驗時拒算，
直到另有已審查的調整口徑。本版本僅接受官方行事曆覆蓋之交易日，跨年度須取得
新年度官方日曆與驗證。

本結果是描述性價格觀察，沒有方向標籤、買進指令、策略勝率或選股權限。任何
日後模型比較需以同時點與固定母體另立實驗。
