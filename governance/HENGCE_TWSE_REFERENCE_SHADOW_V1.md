# HENGCE 官方市場參考資料影子橋接 V1

以已核驗的 TWSE 交易日曆、Mother 出版收據與原 EOD 股價腿確定交易日和股號母體。
不另抓個股日行情。一次手動擷取對下列公開端點各最多發出一次請求，
同一證據目錄及交易日已取得的收據直接重用。

- TAIEX https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST
- 暫停及恢復 https://openapi.twse.com.tw/v1/exchangeReport/TWTAWU
- 終止上市 https://openapi.twse.com.tw/v1/company/suspendListingCsvAndHtml
- 除權息 https://www.twse.com.tw/rwd/zh/exRight/TWT49U

```sh
python scripts/hengce_hba_twse_reference_shadow.py --market-date 2026-11-17 \
  --evidence-dir /tmp/hengce-reference --capture > /tmp/hengce-reference-report.json
python scripts/hengce_hba_twse_reference_shadow.py --market-date 2026-11-17 \
  --evidence-dir /tmp/hengce-reference --asof '2026-11-18T17:00:00+08:00'
```

每個收據保存完整 URL、原始位元組、SHA-256、本證據目錄首次收件時刻及指定交易日。
只接受精確白名單上的 HTTPS 端點，拒絕重新導向。收件時刻由擷取程式在讀完回應後
記錄。官方資料若無可信公告時刻便保留 null。歷史回讀只能用於回放；
早於首次收件的截止時刻無法使用該報表。首次有效收據原子建立。
修訂資料應另存於新證據目錄，可用原始 SHA 判斷是否變動。
本機收據為未簽名的影子證據，沒有不可覆寫的正式發布時間或證交所簽章。
相同資料及相同截止時刻會產生相同的離線報告。

TAIEX 必須有唯一指定日與一致的 OHLC。停復牌事件須與當日交易時段交疊，
下市按生效日判讀，與同日成交證據衝突時保留未知。日成交有值只能證明
觀測到日內交易，暫停清單沒有該股不能證明開盤可交易，零量也不能證明停牌。
TWT49U 已列事件可回溯類型和適用日，報表缺列不能證明無事件。公司行動的
完整覆蓋、可靠調整口徑與可核驗的公告時間未取得時標為 UNVERIFIED。
各股的個別狀態、證據與來源阻擋原因保留於報告。

GitHub Actions 只做 PR 離線驗證，無下載排程、雲端寫入或 OIDC。
影子輸出使用獨立 schema，不能傳給 PR-2 當正式資料。正式接入前須另案驗證
歷史交易狀態是否完整、除權息以外的公司行動事件涵蓋、官方公告時間、首次收件
持久證明與調整計算。正式採集器如採用 Ed25519，簽章代表衡策審核的採集器。
信任清單、政策 SHA、持久封存及自動結算都各自需要審查與批准。

## 11/17 原始來源驗收與影子狀態

`tests/hba_surveillance/fixtures/twse_reference_20261117_excerpt.json` 保存四個已收件
官方回應的裁切版，逐筆保留實際欄位名稱和格式。fixture 的 original_sha256 只對應完整
原始回應，裁切版僅用於解析回歸，不能充當來源憑證。TWT49U 查詢參數使用
startDate/endDate，回應使用 strDate/endDate，資料列使用民國年月日。未採用欄位的
N/A 值保留原樣，亦不構成公告或首次收件時間。

全日停牌須有明確的正式時段起訖覆蓋，且無同日成交衝突。若時段內已恢復，
標為 HALT_RESUMED_DURING_SESSION，另列是否已知開盤停牌。缺恢復時刻不判定
全日停牌。盤中停復紀錄亦不自動證明可開盤交易。

## PR-3 原始位元組驗收紀錄

四個原始擷取收據原樣保存於
`tests/hba_surveillance/fixtures/twse_reference_original/2026-11-17/`。檔案內
`receipt.raw_base64` 解碼後即為完整 HTTP 回應本文。本次沿用原擷取檔，
未再次連線或替換首見時間。驗收樣本未簽名，留存僅供影子回放與 CI 複驗。
所有時間為 2026-11-18 台北時間，官方公告時間均無已核驗值。

| 檔名 | 首次收件 | 原始回應 SHA-256 | 收據檔 SHA-256 |
| --- | --- | --- | --- |
| taiex.json | 16:55:28.375192 | f673a3c5f3c7c5c2702cda29ecd4b3782aa9af93aca15534ab48a4774691ab20 | 103d9e246ebaf2cc655a00732e5cce2c8756be27879bf9e4d29ee34fdb20a278 |
| halts.json | 16:54:25.140252 | 14ee8e4457fbc9e9c69635cc576a3341dec33159138721ddaf98ec0da7327f3d | 344a528f1ef739a2b70663935d75cfe52113d7563841eb77e42f25e04db5e527 |
| delistings.json | 16:54:27.218761 | b5e2c7a94e40503482d9d74e8be9c0e7ed9df58fd14805b90d63e7c3f47bcd50 | c712e340e458c70f52349a9a8207723bcb6dc7a3751c5ee01c8e0e591714990b |
| corporate_actions.json | 16:54:28.573313 | ead8f4676fc848b851dfc867377c932c43d9a8360726439dd9e4a07248f8f31a | c2485648475cffc190a2199f1e64ca85d9fdbd9af5b6417cb97a5fbf01e8a74f |

從 repo 根目錄執行離線讀回。程式驗證原始本文與完整收據 SHA，
並使用原價量腿決定母體。CI 另外核對裁切 fixture 的 original_sha256。

```sh
python scripts/hengce_hba_twse_reference_shadow.py --market-date 2026-11-17 \
  --evidence-dir tests/hba_surveillance/fixtures/twse_reference_original \
  --asof '2026-11-18T16:55:28.377673+08:00' > /tmp/hengce-reference-report.json
sha256sum /tmp/hengce-reference-report.json
```

此次全量報告 SHA-256 為 f95b5cf730cc8e2b1f62ac3cc3380bbd36eee4ddb90229c2a7330cf177221703。
四個來源檔的原始回應均通過影子核驗。TAIEX 1/1 日，開 40546.64、收 40092.11。
停復牌回應有 2314 的 11/10 至 11/11 區間，11/17 無交疊。終止上市清單可核對
2867 的 2026-09-01 生效日。TWT49U 有 25 筆明列事件，皆在原 1,091 檔之外。
11/17 母體內各有 0 筆明列停復牌、下市及公司行動事件，個股交易狀態 1,091 檔、
公司行動 1,091 檔仍為 UNVERIFIED。原 EOD 另記錄 1,089 檔曾有日內成交，
未據此認定開盤可交易。以 11/17 23:59 回放時，四個回應全數超出收件截止而遭拒絕。
