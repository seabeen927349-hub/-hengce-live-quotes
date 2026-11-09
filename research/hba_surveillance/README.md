# 衡策 HENGCE｜每日大資金偵查研究模型 v1

**目的**：不是找必中公式，而是每天從既有正式原始血管辨識「疑似症狀 → 準備監控 → 行情確認（人工覆核）」與「撤退警戒」。個股不預設機構是同一帳戶；法人彙總僅作研究對手盤代理，TDCC 大額持股級距亦不能宣稱是真外資。

> **長期播種／施肥／收割的強制研究邊界（2026-11-09）**：本頁所列5日法人訊號、相鄰兩週TDCC與短期價量門檻，只能產生 \`SHORT_WINDOW_SURVEILLANCE_ONLY\` 的人工偵查提示。**不得直接命名或確認多年播種、施肥、分批收割、撤回、重試或跨股輪動。** 歷史階段必須另行使用多年逐日原始 gross 買／賣、完整價格路徑及全部當時可取得的集保週序列，依真實轉折事件判斷並保留失敗與反證。僅有多年買賣「總和」也不足以判斷階段。缺完整路徑稽核則設為 \`HISTORICAL_CYCLE_UNVERIFIED\`；原短期提示仍保留。詳細強制規則：[\`governance/HENGCE_LONGITUDINAL_CAPITAL_CYCLE_HARD_GATE_v1_20261109.md\`](../../governance/HENGCE_LONGITUDINAL_CAPITAL_CYCLE_HARD_GATE_v1_20261109.md)。

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

資料完整時產生 `latest.json` 和 `latest.md`，History 由獨立 sidecar GitHub Action 上傳 immutable 檔。每個平日台北時間 08:38、08:53 與 23:05 重跑，依最新已完成 EOD 與已發布海外資料更新；週末不假裝有新 EOD。

前 15 檔只作精簡文字展示；`latest.json` 的 `all_candidates` 保留原 HBA 所有通過既有短期偵查條件的逐股證據與反證（含撤退警戒），`integrated_latest.json` 也讀取此完整候選名單；`candidate_registry` 保留全部候選索引。沒有通過短期偵查條件的多年研究對象，仍須另以原有歷史母庫研究，不能因未入短期 HBA 就宣稱不存在。撤退警戒在文字摘要獨立展示最多 10 檔。當海外環境缺失或逆風時，decision_readiness 必須保留交叉審核，不得視為已取得交易許可。

新 sidecar 不更動 N2、Selection Core、Market State / Q017、Escape、Canonical 原母體或交易權限。GitHub Actions 延遲與外部來源異常時，輸出時間可能晚於 09:00，不能保證即時。

## 待補項目

Repo 目前只有約 18 個可查 EOD 日資料夾，缺少完整 20/60/120 日可用每日檔。故 v1 先以最近五到十日行為提示，不能假稱已完成中長期資金辨識。正式 SOX/VIX 封包截至 2026-11-08 亦未出現在預期的 main 路徑，預設環境未知。先讓每日機制運作並持續累積前瞻樣本，不把歷史重看當 OOS。
## 九年母體既有快取（非新血管）

- `research/hba_surveillance/data/HENGCE_LIFELONG_GROSS_SUMMARY.csv` 是**衡策原有** `HENGCE_FULL_MARKET_MOTHER_RESEARCH_2018_2026.csv.gz` 的逐股衍生摘要，僅供既有 `hengce_hba_context_bridge_v1.py` 讀取；**沒有新建下載器、獨立資料流或正式策略**。
- 原始母體 SHA-256：`b3275f8d58779fbec864a05066414d27e80cef8a68a76a08051f93808f1f8c93`。截止 2026-11-06，原始 2,111,682 筆，完整四類買賣腿的有效列 2,014,311 筆，97,371 筆缺失不補零；1,147 個股票代號。來源保留在既有 Canonical/Library 原母體，GitHub 只放 70KB 衍生摘要。
- 摘要 SHA-256：`63a499d67295d4c18d982ed2d6eb6961642eccdd1b694c7bde69ee03737bd84c`；每股買進與賣出均分開累計，淨額只是 `買進 − 賣出` 的驗算值；歷史個股首次上市與缺失紀錄不可假裝是九年完整資料。
- 這是**靜態 2026-11-06 截面**。之後新的正式 EOD 日應透過**既有 Canonical 母體增量流程**更新同一路徑；未更新時 `STALE_RESEARCH_SUMMARY`，不得假裝中長期完整。即使快取通過，也只代表 gross totals available，**不能以總和代替逐日歷史價格與完整集保週路徑，不能宣稱多年播種/收割階段或買進授權**。

## 原有日 EOD 的唯讀增量疊合

- HBA `hengce_hba_context_bridge_v1.py` 不再把 2026-11-06 的九年摘要視為之後每個交易日都固定不變；只有新的 `eod/YYYYMMDD` 在原三腿完整、原 Canonical Mother receipt 與逐腿 SHA 全部一致，且自基準日以來沒有未核驗交易日缺口時，才在**記憶體內**把原 T86 買進／賣出和價格有效列增量疊合到研究報告。
- 原始母體、原快取 CSV 和 Canonical 路徑完全不寫入，沒有任何新增來源或新母體。缺資料、日期跳躍、數值缺欄或原 receipt 失配均 fail closed，禁止用 0 當成買賣資料。休市若無獨立可核驗的交易日日曆，採保守策略不跳過未知平日。
- 增量只更新歷史 **gross** 累計與日期；不宣稱多年播種／施肥／收割階段。若正式 EOD 尚未完成，維持上一個有憑證日期，不把盤中 FinMind 當正式法人資料。
