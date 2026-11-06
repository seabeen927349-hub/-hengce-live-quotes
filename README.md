# -hengce-live-quotes

## 衡策個股分析預設規格（2026-11-05）

當使用者說 **「分析某股」或「衡策分析 5289」**，應直接依據 [FinMind 長期個股研究標準](docs/HENGCE_SINGLE_STOCK_FINMIND_ANALYSIS_STANDARD_v1_20261105.md) 執行：優先核對衡策原有血管與 Canonical 母體，再以 FinMind 長期個股價量、營收、損益、資產負債、現金流、法人籌碼、融資融券、估值、基準指數完成完整分析。契約：[預設個股分析設定](hengce/HENGCE_SINGLE_STOCK_ANALYSIS_DEFAULT_LATEST.json)。

注意：`5289` 是 TPEx 上櫃股，若目前 TWSE-only Canonical 無其正式覆蓋，應標示無母體覆蓋，不能虛稱已入母體。FinMind 外部唯讀研究資料不得擅自升格為 Canonical。**Q017 已退役，沒有正式交易策略權限；個股研究 ≠ 選股或下單授權。**


## 衡策研究必讀：先讀專業研究，再做模型（2026-11-06）

**所有新研究與跨對話接手，第一步必讀**：[文獻優先執行規範](governance/HENGCE_LITERATURE_FIRST_EXECUTION_SOP_20261106.md)，並遵守[文獻優先研究憲章](governance/HENGCE_RESEARCH_LITERATURE_FIRST_CONSTITUTION_v1.md)與[強制 Gate 合約](governance/HENGCE_LITERATURE_GATE_CONTRACT_v1.json)。

研究流程：先接手既有母體/歷次失敗紀錄 → 搜尋並研讀專業原始文獻（支持＋反證＋無效結果）→ 說明學習與適用性 → Gate PASS 後事前註冊 → 才可依正式治理測試。**不懂先查專業資料，不靠猜測亂造公式，不把修資料當超額報酬；每輪交接必附文獻來源、閱讀狀態、反證與待學事項。**

沒有取得全文或通過文獻門檻：研究維持 LITERATURE_REVIEW_ONLY，不得私自回測新模型。這條規則持續適用所有未來對話、研究分支與模型；不改變正式交易授權。
