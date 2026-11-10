# 衡策全合格股 Top 5 V2.2

依V2.1獨立驗收修正：全基礎合格候選與研究配對分離，固定取流動性前五名；假設整張資金規則改為最多5檔、每檔NAV18%、保留10%現金。不是沿用舊策略績效。

```bash
python -m pip install -r requirements.txt
python select_stocks.py --decision 2026-11-06 --output my_result_20261106
```

查看輸出report.md；all_qualified.csv是全部合格股，candidates.csv是Top5，research_pairs.csv僅供對照研究。內附sample_result可直接看。

詳細操作見 `README_V2_2_使用說明.md`，對應驗收修正見 `驗收修正對照表.md`。舊版本與獨立驗收原文在legacy/。

**RESEARCH_ONLY / NO_TRADING_AUTHORITY**：仍只接受固定歷史批次。官方來源、公告存證及正式風控未接，授權張數固定0；沒有實盤出場或回測績效宣稱。
