# 衡策 V2.2D 原版模型：原血管的私人研究接線

## 本版實際連通範圍

1. 使用既有 SHA-pinned 2018–2026 EOD 歷史母體、G1 457 週 TDCC 小額持有人母體、既有 2026 正式三腿母體（**不建立新下載器**）。
2. 使用已還原的 **V2.2D 原版 LightGBM classifier/regressor**，檢查每一個模型與原始來源檔 SHA。
3. 鎖住 2018 年首次有效集保 400 張以上佔比 ≥50% 的 **781 檔固定母體**，重建原版 16 個特徵，只允許週一至週四日期。
4. 保留原版模型：預測週末小額戶數下降研究分數門檻 ≥0.50、20 日報酬 ≥5%、5 日報酬 ≥0%、20 日成交額中位數 ≥1,000 萬、波動有效；Top5 **按成交額中位數**排序。
5. 輸出 SHA 憑證與歷史研究 Top5。透過 `hengce_scan_once_router.py --v22d-private-report` 顯示，**不變更**正式選股／交易鎖定。
6. 私人權重、私人持倉／交易日誌與三份大型母體仍在私人 Library；不提交公有 GitHub。

## 執行（在持有原始私人 Library 資料的安全環境）

需由執行端先從**既有** Library 取得四份私有輸入，並確認它們確實來自原始血管，不將原始檔案、模型權重或未經驗證的數據寫入公開 GitHub。

```sh
python -m pip install pandas numpy lightgbm
python scripts/hengce_v22d_private_original_inference.py \
  --original-price-mother /secure/HENGCE_FULL_MARKET_MOTHER_RESEARCH_2018_2026.csv.gz \
  --original-tdcc-mother /secure/HENGCE_G1_TDCC_RETAIL_457_WEEK_MATCHED_PANEL_2018_2026.csv.gz \
  --original-2026-canonical /secure/HENGCE_2026_HIST_MOTHER.csv \
  --private-original-model /secure/HENGCE_V22D_ORIGINAL_REHYDRATED_MODEL_PROOF_20261111.zip \
  --decision-date 2026-11-11 \
  --out /secure/v22d_private_replay.json

python scripts/hengce_scan_once_router.py \
  --v22d-private-report /secure/v22d_private_replay.json \
  --display-only
```

**11/11 的獨立核對：**原始 781 檔，737 檔可運算、7 檔過門檻，歷史 Top5 為 1802、2886、2618、1476、2610。重算屬事後回放，不得宣稱為 11/11 當日已發布的訊號。

更換下一交易日的 2026 canonical 來源時，必須提供新的完整檔案 SHA：`--canonical-sha256 <verified-new-file-sha256>`。不能讓既有 11/11 母體冒充較晚日期；執行端還必須確認 GitHub 原有 EOD 的正式完整日收據。

## 尚未通過的正式上線門檻

- **模型權重在私人 Library，GitHub Actions 無權直接取用。**本 PR 僅接入可重複執行的私人環境推論與衡策掃描展示，CI 不下載、儲存或公開權重。自動化需要經授權的安全執行環境，不能用公有 Repo 保存原模型。
- 目前 TDCC 歷史首次發布時間未完整查證；14 天保守延遲是替代假設，不是完整 PIT 認證。因此即使私人執行端在當日跑出結果，仍保持 `RESEARCH_REPLAY_NOT_PIT_CERTIFIED`。
- `scripts/hengce_v22d_daily_reader.py` 的正式 `CURRENT_V22D_PIT_TOP5_VERIFIED` 不因上述研究資料被篡改或自動提升；正式買賣／MAX5 授權保持 0。
- 前瞻每日報告需另外核准由私人安全執行端提供**不可回填**的當時模型輸入時間、原 EOD 完整日來源與 TDCC 已知時間憑證，才能作為真實前瞻驗證。

這裡沒有新市場資料來源、重訓後替代模型、Q017 復活或自動下單。
