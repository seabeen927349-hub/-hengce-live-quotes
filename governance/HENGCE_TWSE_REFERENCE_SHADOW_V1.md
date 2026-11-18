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
