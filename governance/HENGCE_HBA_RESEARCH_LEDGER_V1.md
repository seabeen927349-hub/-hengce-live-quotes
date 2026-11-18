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

本機歷史回放參考 JSON 結構如下。正式模式使用下方帶簽章的來源格式。

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


## 正式來源驗證

正式模式不接受回放用的平面 `sessions`、狀態字串或 SHA 格式作為充分證明。
`HENGCE_TWSE_OFFICIAL_REFERENCE_V1` 需含 `policy`、`raw_objects[sha256]`（原始檔 bytes
以 Base64 封存），及 `official_sessions[交易日]`。每天必須有 `taiex`、
`trading_status`、`corporate_actions` 三個獨立封包。每個封包包含 `receipt`、
`claims`、`signature`。收據綁定 schema、TWSE publisher、dataset、有效日、完整 HTTPS
來源 URL、公告時間、首次實際取得時間、原始檔 SHA、解析後 claims SHA 及 key ID。
摘要與簽名以程式的 canonical JSON 為準。claims 分別是 {open,close}、逐股交易狀態、
逐股公司行動判斷。資料缺席維持未知。保留所有原始檔，供稽核重新解析。

獨立且經審查的來源採集者要擷取官方原始回應，記錄公告及實際收件時刻，依核准
解析規格產生 claims，再以 Ed25519 簽收據。驗證端重算原始檔與 claims SHA，
核對 repo 審查過的公鑰、有效期間、確切官方端點及簽章；時間須滿足
交易日收盤 ≤ 公告 ≤ 收件 ≤ 鎖定物件發布 ≤ 結算截止。
公鑰是對官方來源擷取過程的信任根，並非 TWSE 本身簽署。
正式模式只接受已核准 policy SHA。信任清單目前為空；新增採集器、公鑰、
端點及解析合規驗收須獨立審查。未通過時回報 UNVERIFIED／阻擋，保留 PENDING。
本機回放中的數值資料不能進入正式分支。

## 定期結算閉環（部署規格）

沿用既有 HBA 主線排程成功後的結算步驟，不另增排程；待核准部署才啟用。
每次固定一次結算截止時間，由不可變 receipts 前綴依版本列出待處理快照，
以官方交易日曆判定已逾期的 5／10／20 日視窗。參考採集者先依原始檔與首見收據
發布鎖定版本。結算以該引用和原 EOD 收據運行 `--all`，只讀完整且已正式
升格的原價檔。以處理預算及持久 cursor 分批續跑；同一快照、參考版本和結算
結果可冪等重試，缺漏或晚到保留待重查，之後有資料時追加新版本。
每個視窗須獨立取得完整來源才能發布 SETTLED_DESCRIPTIVE。未到期維持
PENDING，報告只描述證據後續價格路徑，不統計勝率。

## 雲端啟用前的驗收與成本

此 PR 不部署 bucket、OIDC 或長期保留。需由擁有者先確認區域、保留期、預估容量與
AWS 報價。按月列出物件容量與版本保留（GB-month）、PUT/GET/LIST 次數、下載流量及
可能的 KMS/審計費用。以目前正式卡約 251 KB 壓縮 ZIP 為參考，實際 S3 定價應以
未壓縮的封存 JSON、原始參考證據和結算物件的位元組統計。
驗收需用實際角色測正確 repo/environment 可 assume、其他身分失敗；檢驗版本化、
COMPLIANCE 保留和同鍵條件建立；實測無條件寫入、刪除、縮短保留皆被拒絕；
獨立讀取角色須按 key/version 於 Actions 過期後重新核對原件。
保留到期前即使管理人員也不能移除鎖定物件，依法刪除與誤寫成本須先評估。


## 正式排程硬停用

`archive-research` 固定使用 `if: ${{ false }}`。即使 Actions 變數為 `true`，也不會執行 AWS 或 Object Lock 步驟。重新啟用須以獨立 PR 提出並經明確人工批准。
