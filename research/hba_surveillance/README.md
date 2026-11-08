# 衡策 HENGCE｜每日大資金偵查研究模型 v1

**目的**：不是找必中公式，而是每天從既有正式原始血管辨識「疑似症狀 → 準備監控 → 行情確認（人工覆核）」與「撤退警戒」。個股不預設機構是同一帳戶；法人彙總僅作研究對手盤代理，TDCC 大額持股級距亦不能宣稱是真外資。

## 輸入與資料治理

- 台股 `eod/YYYYMMDD/{price,institutional,margin}_*.csv`，只接受 status.json `formal_complete_day=true`、三腿同日與 `downstream_ready=true` 的觀測。
- TDCC `ownership/tdcc/YYYYMMDD/tdcc_ownership_4d.csv`，僅使用已首次觀測的週資料，禁止日級 forward fill。
- 大環境 `overseas_premarket/latest.json`，日期與 raw SHA/packet SHA 均驗證才顯示當日 SOX/VIX。缺少即顯示資料不足。
- 長期資金（20/60/120 天）獨立缺乏核准憑證時顯示「資料不足」，不拿淨買超假冒資金匯入。

## 事前先行的訊號判讀（不是機率公式）

- 法人：最近五個交易日淨買超占觀測成交量至少 1.2%，且五日至少三天淨買。
- 持股：可用的相鄰兩週 TDCC 400 張以上持股占比增加至少 0.25 個百分點。
- 價量：近五日收盤漲幅至少 3%，當日成交量相對前五日均值大於 1.2 倍。
- 融資：五日融資餘額減少至少 3%，同時法人五日仍為淨買。
- 三類以上證據，或「法人 + 持股」同時成立 → 準備監控；法人 + 價量 + 至少第三獨立證據，且當日漲幅≥2%、量比≥1.5 → 行情確認（人工覆核）。
- 法人五日淨賣逾 1.8% 且 TDCC 大額持股週降逾 0.5 個百分點 → 撤退警戒。

以上門檻為第一版**前瞻偵查操作定義**，不是 2018–2026 年回測優化或證明賺錢。只用以排序人工調查工作，不給機器下單授權。模型同時提供反證、異常來源缺口、日期與前次狀態變化。

## 使用方法

`python scripts/hengce_hba_daily_surveillance.py --root . --out research/hba_surveillance/latest.json`

資料完整時產生 `latest.json` 和 `latest.md`，History 由獨立 sidecar GitHub Action 上傳 immutable 檔。每個平日台北時間 08:38 與 08:53 重跑，依最新已完成 EOD 與已發布海外資料更新；週末不假裝有新 EOD。

新 sidecar 不更動 N2、Selection Core、Market State / Q017、Escape、Canonical 原母體或交易權限。GitHub Actions 延遲與外部來源異常時，輸出時間可能晚於 09:00，不能保證即時。

## 待補項目

Repo 目前只有約 18 個可查 EOD 日資料夾，缺少完整 20/60/120 日可用每日檔。故 v1 先以最近五到十日行為提示，不能假稱已完成中長期資金辨識。正式 SOX/VIX 封包截至 2026-11-08 亦未出現在預期的 main 路徑，預設環境未知。先讓每日機制運作並持續累積前瞻樣本，不把歷史重看當 OOS。