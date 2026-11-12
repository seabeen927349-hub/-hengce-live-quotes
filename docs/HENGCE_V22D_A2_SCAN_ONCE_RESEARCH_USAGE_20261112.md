# 衡策 V2.2D-A2：「衡策掃一次」研究接線

## 目的

沿用原始 781 檔研究母體與原版 V2.2D LightGBM；A2 是唯讀研究側欄，不重排 Top5，
不改 MAX5、2ATR/4ATR、S5、Escape、RMS 或已退役 Q017，也不建立新行情下載器。
掃描的原有正式 `rows`、`buy_signal`、`sell_signal` 及 `broker_order_execution` 永遠不由 A2 解鎖。

## 日常使用

在持有原始私人 HENGCE Library 檔案的安全主機上，使用既有每日原血管入口：

```sh
python scripts/hengce_v22d_private_daily_runner.py \
  --repo-root . \
  --original-price-mother /private/HENGCE_FULL_MARKET_MOTHER_RESEARCH_2018_2026.csv.gz \
  --original-tdcc-mother /private/HENGCE_G1_TDCC_RETAIL_457_WEEK_MATCHED_PANEL_2018_2026.csv.gz \
  --original-2026-canonical /private/HENGCE_2026_HIST_MOTHER.csv \
  --private-original-model /private/HENGCE_V22D_ORIGINAL_REHYDRATED_MODEL_PROOF_20261111.zip \
  --private-work-dir /private/hengce_v22d_output
```

程式先驗證現有每日三腿 EOD 收據、續接原版私人母體、用原版 checkpoint 重跑 V2.2D；
接著在 `hengce_scan_once_YYYYMMDD.json` 的 `reporting.v22d_a2_shadow_observation` 自動附上 A2。
既有主掃描仍為 `NO_ACTIVE_SELECTION_STRATEGY`，這是研究觀察，不是正式選股或下單。

如果已經有依原版模型驗證過的私人 replay JSON，可直接執行：

```sh
python scripts/hengce_scan_once_router.py \
  --v22d-private-report /private/v22d_private_replay_YYYYMMDD.json \
  --a2-canonical-2026 /private/same_verified_canonical_from_replay.csv \
  --a2-tdcc-781 /private/HENGCE_G1_TDCC_RETAIL_457_WEEK_MATCHED_PANEL_2018_2026.csv.gz \
  --display-only
```

## A2 會顯示的欄位

- 原始 V2.2D Top5 順序及分數（不修改）。
- 已知集保資料相對前三週的小額戶數變化；沒有資料就標示缺口。
- 20 日個股報酬相對 781 檔母體中位數、5 日/20 日波動收斂。
- 5 日對 20 日量比、距 20 日最高收盤價回撤。
- 過去已知交易日的「上漲→回落→再上漲」價格型態線索。
- 追價風險、資料期日、SHA 驗證狀態及明確的缺口。

價格型態不能證明刻意洗盤、操縱或未來會漲；原模型分數不是股價上漲機率。
14 日集保保守延遲仍不等於真實首次公告時戳的 PIT 證明。

## 不可省略的限制

GitHub 公開 Actions 無法直接讀取私人 ChatGPT Library 與私有模型權重。
這個接線沒有啟動排程，也沒有公開私人原始檔或模型。若執行端無法讀取完整私有原檔，
A2 必須顯示 `A2_WAITING_FOR_PRIVATE_CANONICAL_AND_TDCC` 或 `A2_SOURCE_BLOCKED`，不能編造結果。
目前原版私人重播僅提供 Top5，因此 A2 只描述這五檔，沒有宣稱重排所有候選股。
正式績效改善仍需另外以 2026 年與多年度樣本外資料驗證。

## 研究檢驗

`python -m unittest tests.engineering.test_hengce_v22d_private_original_runtime`

原版 V2.2D、完整使用者持倉、ATR 及正式選股權限皆維持獨立。
