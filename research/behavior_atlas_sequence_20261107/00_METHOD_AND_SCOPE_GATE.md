# HENGCE 原研究續篇：群體行為先後順序研究的文獻與範圍門檻
建立：2026-11-07（Asia/Taipei）

**接續原研究主題，不是改為「大資金 vs 小額持股者」：** 比較TDCC持股結構、三大法人交易淨額與融資餘額的先後相位差及跨年代穩定性。**不是**前案A1再調參；原案 `DESCRIPTIVE_ONLY` 完全保留，五個未執行配方仍為NOT_EXECUTED。本文件為新的有界、公開回顧式探索提案，不能作為乾淨新OOS。

## 原文獻及負面方法要求
- 繼承原案 `research/behavior_atlas_20261107/LITERATURE_GATE.json` 的 `PASS`，其專項範圍包括群體資金先後、機構異質性、同時性及時間序列驗證；文獻節目與方法審查是於新案方法凍結前已完成。
- Shyu & Sun（2010）台股機構群聚：聚合機構淨流量不能識別同一人的行為與真正模仿。舊Ledger記錄已閱讀。
- White (2000), *A Reality Check for Data Snooping*, Econometrica，DOI 10.1111/1468-0262.00152；Sullivan/Timmermann/White (1999), *Data-Snooping, Technical Trading Rule Performance, and the Bootstrap*, Journal of Finance DOI 10.1111/0022-1082.00163：反覆挑最好看的時段與方法會增加假發現。新案必須凍結數量與失敗結案規則。
- `Testing for Granger causality in heterogeneous panels with cross-sectional dependence`, Empirical Economics (2024), DOI 10.1007/s00181-024-02589-w：異質股票對共同市場因子的反應可造成表面領先；其方法章公開可核對，但本文不宣稱在本案實作該完整panel VAR模型。
- `Detection of multiple change-points in high-dimensional panel data with cross-sectional and temporal dependence`（2024）DOI 10.1007/s00362-023-01484-3：股票面板在時間與橫斷面有依賴時不能按逐股週獨立推論。僅核對摘要及研究適用限制；**不是 FULL_READ**。
- A1之前已知 **0.35** 左右同期相關可由TDCC大戶與外資同一資金的持股/買賣部分重合解釋；本研究**不再測同期關聯是否顯著**，並禁止將先後相關當成心理因果。

## 本研究可觀測與不可觀測
可觀測：四腿股票週 TDCC Big400/Big1000持股比例及人數、TWSE法人淨流量、融資餘額；資料版本已核對。
不可觀測：戶名身分、跨級距同戶拆分、每個法人的真實對手、委託單、心理動機、歷史週 TDCC首次公開時間。因而只准稱「回顧性時間先後**關聯**」，**不准**稱事前策略或領先因果。

## 文獻使用狀態與Gate
**PASS_FOR_BOUNDED_RETROSPECTIVE_LEAD_LAG_DESCRIPTION_ONLY**：上述方法只允許在事先凍結後建立六個以4／12／24週為尺度的描述檢查；不授權 G5/PIT、股價報酬回測、新因子或正式交易。若使用任何超出原文獻／本次方法的模型，需新案，而非本案變體。
