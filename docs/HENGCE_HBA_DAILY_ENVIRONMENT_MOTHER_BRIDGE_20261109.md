# 衡策每日血管整合修正 V1（研究唯讀）

日期：2026-11-09。本次改動修復既有 HBA 每日監控、原始三腿 EOD、多年法人交易累計與 Escape / S5 環境監測之間的接線。它不是新選股策略，也不改交易授權。

## 修正原因

- 原 HBA 每日監控只直接讀取 eod/YYYYMMDD，而 GitHub 內僅有近期 EOD；既有2018–2026多年母庫的原始買賣交易量未進入這份日報。
- 2026-11-05與2026-11-06已存在正式EOD下的 FinMind 市場廣度影子；原先個股報告沒有串接前後兩日環境。
- escape_live/twse_common_status.json最後記錄2026-11-03之全上市Fugle snapshot HTTP 403。舊403不等於11/06正式EOD故障，亦不等於個股即時報價不可使用。
- 正式S5分類、Escape V2狀態機、海外SOX/VIX及長期資金環境現有治理規範必須保留；缺憑證時不能自行創造分類或恐慌指數。

## 本次改動

1. 新增 scripts/hengce_hba_context_bridge_v1.py，接在原HBA掃描結果之後，不改原掃描器選股公式及排名。
2. 檢查eod/YYYYMMDD/status.json的同日價格、法人、融資三腿完整性，接入原EOD日期對應市場廣度，保留上一個實際有效觀察日比較。
3. 可選讀取已完成的多年法人原始買、賣總量逐股摘要，避免每日重掃九年母庫；路徑約定 research/hba_surveillance/data/HENGCE_LIFELONG_GROSS_SUMMARY.csv。
   欄位：ticker,first_date,last_date,valid_stock_days,gross_buy_shares,gross_sell_shares,net_shares。逐股檢核買減賣與淨額一致、最後觀測日不超過報告EOD日。原始股票不以事後結果篩選。
4. 多年摘要未接入則 EOD_READY_LONG_TERM_MISSING，不以近幾日淨額冒充多年研究；不產生交易授權。
5. 原 HBA GitHub Actions 新增唯讀整合步驟、輸出JSON/Markdown、SHA歷史紀錄；收盤對帳時段調至台北23:35及23:55，以避開之前11/06的23:18 EOD完成延遲。
6. 新增5項單元測試：跨日廣度、舊403、完整交易量、缺母體、未來資料與不完整EOD的fail-closed規則。

## 2026-11-06 本地整合驗證

- 原完整歷史摘要涵蓋2018-01-02至2026-11-06、1,147檔；其中624檔累計淨變動不到累計買賣總股數1%。描述性統計，不是成功收割證明。
- 11/05 FinMind TWSE普通股環境：有效1,085檔，下跌857檔。
- 11/06 FinMind TWSE普通股環境：有效1,085檔，下跌953檔。
- 下跌比例由78.99%增至87.83%，增加8.85個百分點。
- Fugle全市場批次狀態僅是11/03的403歷史記錄；11/06原始EOD三腿為COMPLETE。
- 影子環境資料經夜間正式EOD附掛，不能拿11/06夜間才可用的資料倒回11/06開盤前做決策。

## 尚未完成，必須明確揭露

- GitHub main目前沒有上述多年累計摘要的正式掛載或按日增量更新。此PR提供介面，但不宣稱GitHub排程已讀到九年。後續須透過既有Canonical母庫的來源稽核與增量發布流程接上；不可新建平行血管。
- S5正式分類需要九項凍結特徵；Escape L0至L6必須由原狀態機提供憑證。此PR只標示NOT_PROVIDED，不能把市場下跌家數直接推算正式級別。
- 11/05恐慌指數的確切名稱、數值、比較期間必須從原衡策環境監測來源確認，不能自行編造。
- Fugle全上市批次403須核對帳戶方案、端點權限與API金鑰；個股成功與批次403並不矛盾。無權限時不能靠修改程式保證成功，不得擅自恢復全市場輪詢。
- 所有研究輸出只做觀測與人工覆核，不具備實盤交易、部位調整與模型升格授權。

## 操作指令

    python -m unittest discover -s tests/hba_surveillance -p 'test_*.py' -v
    python scripts/hengce_hba_context_bridge_v1.py --root . --hba-input research/hba_surveillance/latest.json --mother-summary research/hba_surveillance/data/HENGCE_LIFELONG_GROSS_SUMMARY.csv --out research/hba_surveillance/integrated_latest.json

若多年摘要尚未掛載，省略 --mother-summary，報告會正確標示長期資料未接入。
