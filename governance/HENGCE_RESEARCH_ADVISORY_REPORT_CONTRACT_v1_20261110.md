# HENGCE 恒定研究建議報告契約 v1.0｜2026-11-10

## 目的與觸發

使用者說「衡策掃一次」時，不可只回報 EOD 血管是否正常、原 HBA 警報檔數或「沒有正式買點」。必須在資料許可時，從**既有 HENGCE 原血管**讀取 `research/hba_surveillance/decision_latest.json`／`decision_latest.md`，提出可檢驗的人工研究建議，說明「看哪幾檔、為什麼、風險在哪裡、什麼變化會推翻判斷」，並區分最近正式 EOD 與當日盤中報價。

本契約是**研究報告展示契約**，不是正式選股策略、評分權重、交易訊號或下單指令。既有 `hengce/HENGCE_SCAN_ONCE_CONTRACT_LATEST.json` 的 `NO_ACTIVE_SELECTION_STRATEGY`、0 套策略、停用 Q017、0 下單授權持續有效。

## 既有流程：無平行血管

唯一輸出路徑屬於原有 `.github/workflows/hengce-hba-daily-surveillance.yml`，步驟為：

1. `scripts/hengce_hba_daily_surveillance.py` 用原始三腿 EOD 與 TDCC 產生舊版 HBA 完整警報（舊公式保留、不加權變更）。
2. `scripts/hengce_hba_context_bridge_v1.py` 併入散戶（TDCC 1–3 級距，<=10張）與其他所有持有人**實際股數**、相同 TDCC 參考週收盤價及歷史買賣總量；不得用 400 張級距、持有人數或法人單日淨額代替。
3. `scripts/hengce_hba_decision_report.py` 依當下可核對的資料形成「研究觀察／等待價格確認／風險警戒」及其理由、反證與下次檢驗，輸出 `decision_latest.json`、`decision_latest.md` 及 `decision_history/YYYYMMDD_SHA.json`。
4. `scripts/hengce_scan_once_router.py` 對使用者呈現只讀 `reporting.research_advisory`，不得改動 `status=NO_ACTIVE_SELECTION_STRATEGY`、`rows=[]`、`reporting.top10=[]`、`buy_signal=false` 或 `broker_order_execution=false`。

完整上市可比較股票形成一份**非交易排行**的逐股研究紀錄，原 HBA 307 檔（檔數會變）只作獨立的短期警示，不得拿它冒充全市場。人工覆核案例同時保留短期強勢觀察及撤退警戒，避免顯示上限掩蓋反證。

## 報告固定要回答

每次報告在資料可用時，應回答：

- 哪些股票目前值得**優先人工追蹤**？依據哪些實際價籌觀察，而不是僅依法人買超？
- 哪些股票顯示散戶實股增加／減少、其他持有人實股增加／減少？散戶人數是否與實股方向相反？
- 哪些股票因融資增加、快速大漲、價格回檔、資料不足等因素要提高風險警戒？
- 下次實際 EOD 或公開 TDCC 出現哪種反向變化時，須更新或撤回原判斷？參考價格**不是經回測驗證的停損線**。
- 每項資料截至何日、首次公開可用時間為何、是正式 EOD、集保週資料還是即時盤中觀察？尚缺什麼證據？

當正式選股器尚未通過外樣本和前瞻驗證時，不得宣稱上述分類已證明有獲利選股能力，也不得因散戶追價直接禁買、或因其他持有人增持就直接買入。原 2018–2025 的 781 檔長期循環母體與全上市比較研究須各自保留，不得互換、只取特定成功案例、任意設定試探固定週期。

## 資料時點與失敗關閉

- 只讀原有 EOD／TDCC 與憑證。缺失、逾時、SHA不符、股本變動過大、週資料不連續或狀態不同步時輸出 **BLOCKED/UNKNOWN**；不能補造「中性」或使用未來可得資料。
- 已發生的同週股價與持股模式 ≠ 事前可知的多週「播種／施肥／收割」；完整多年階段仍受 `governance/HENGCE_LONGITUDINAL_CAPITAL_CYCLE_HARD_GATE_v1_20261109.json` 控制。
- SOX/VIX、S5、Escape 或 RMS 沒有各自正式憑證時，報告維持資料不足，不使用本研究生成替代級別。
- 並非即時盤中血管：HBA 決策報告的 `latest_eod_close` 必須清楚標示**正式 EOD 日期**；查當天盤中價須另讀既有合規的個股報價，不得假稱 EOD 為現價。
- 固定報告不得自行新增資料來源、第二母體、策略族、選股排名、成交量硬篩選、買賣閘門或下單授權。

## 驗收

每次變更需通過 `tests/hba_surveillance`，包含完整逐股覆蓋、同週價籌配對、上市原始股價完整性、資料缺失關閉、交易停用、報告大小、來源雜湊、時效、原 HBA 全量與實際 2026-11-09 凍結樣本回放。主分支執行時，必須確認 JSON／中文 Markdown／不可變歷史檔**實際發布成功**；光是 Pull Request 測試成功不代表已部署。若發布失敗，需明示未完成。

## 變更權限

正式策略、S5、Escape、RMS、原 HBA 凍結短期條件、Q017 退役、下單及資本權限均不因本契約而改變。研究分類若要升格為正式選股或交易指令，需另有完整前瞻與交易級成本驗證及明確授權。
