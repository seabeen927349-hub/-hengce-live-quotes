# HENGCE V2.2-D → MAX5 → ATR → 每日持倉研究工作單

## 目的與授權界線

這個模組**只新增一個唯讀的操作風控工作單**，不新增任何市場資料血管，不重新訓練或更換已指定的 V2.2-D 選股核心，不啟動正式選股、不接券商、不執行任何委託。原 V2.2 繼續為 benchmark；S5、Escape、RMS 及 Q017 退役狀態完全不變。

程式：`scripts/hengce_v22d_max5_operations.py`。  
原有「衡策掃一次」：`reporting.v22d_max5_daily_account_worklist`。

### 模組現況（2026-11-11）

- V2.2-D **研究版本偏好已生效**。歷史研究最近一個決策日是 2026-11-05；**GitHub 還沒有可認證的當日 LightGBM 模型 checkpoint 與 point-in-time 預測收據**。
- GitHub 原始 EOD 已有 2026-11-11 三腿和母體驗證資料，但連續21交易日的正式 OHLC 原始日收據尚未齊備；ATR 不得用猜測回填。
- 因此「當日 V2.2-D Top5→即將開盤買進價」**尚不可解鎖**。程式會列示等待原因，不回退用舊 V2.2 名單冒充新訊號。
- 若帳戶實際持倉有完整的**券商實際入場日期／成交價、當時訊號日 ATR20**與後續可驗證的 OHLC，會逐日重算初始2ATR、+20%觸發4ATR只升不降風控、收盤是否已觸發下一有效開盤的人工退出檢查；未驗證的部位顯示 `BLOCKED_POSITION_EVIDENCE`。

## 交易時序

- 每日研究只看原 EOD 正式日收據；固定採台北 23:00 原 EOD 排程作為**最早**可用於今日工作單的時刻。在此以前只復查上一個有效交易日，避免回放偷看收盤後資料。實際資料若23:00後仍未發布，也不推算。
- 每日 V2.2-D 選股名單**不代表每天都買**；最多持有5檔，每一週最多新增1檔。所有已觸發退出的股票在券商成交與帳戶確認前仍占持倉名額。
- 初始風控價＝實際入場價－2×入場當日已知 ATR20；最高收盤上漲達20%後，移動風控價＝最高收盤價－4×當日 ATR20；只上調、不下降。
- 收盤觸發時僅產生 `REVIEW_EXIT_NEXT_VALID_OPEN` **人工研究待辦**。跳空、停牌可能使真正退出價偏離風控線。
- 買進只能在「真實當日 V2.2-D 已封存／模型與來源驗證通過、原EOD ATR可查、確實有帳戶空位、提供本週買賣紀錄」後，才出現**一個研究候選**。即便如此 `buy_signal=false`、`broker_execution=false`，不發委託。
- 實際買入和賣出價，只有券商成交後才知道；所有操作報告嚴禁把收盤價或初始風控線標成保證成交價。

## 本機執行（絕不把個人帳戶寫進 Repo）

建立私人的 `holdings.csv`（空持倉也必須保留表頭）：

```csv
ticker,entry_date,entry_fill,quantity,signal_atr20,peak_close,risk_floor,pending_exit,last_reviewed_session
```

現有持倉請從券商對帳單填入 **實際買進交易日、實際成交價、股數、當時買入訊號日已知ATR**。不知道某欄時留空，系統會擋下並指出缺口；**不要隨意補一個數值**。

另建立 `journal.csv`（本週及上期未平倉相關的實際交易）：

```csv
ticker,trade_date,side,status,quantity
```

`side` 僅允許 `BUY`、`SELL`；`status` 是 `FILLED`、`PENDING`、`CANCELED`。這只是使用者提供的紀錄，不等於已由券商驗證；缺少本週紀錄不可假定本週尚未買進。

```bash
python scripts/hengce_v22d_max5_operations.py \
  --asof '2026-11-11T23:55:00+08:00' \
  --holdings /secure/local/holdings.csv \
  --journal /secure/local/journal.csv \
  --output /secure/local/V22D_MAX5_worklist.json
```

下次更新可以加上 `--previous-state /secure/local/V22D_MAX5_worklist.json`。若前期持股消失，須由使用者交易紀錄表列明 `SELL FILLED` 且股數足額；任何前期賣出待辦都不得自行清除。部分賣出／配股／換股等需人工重新核對，不可靜默解鎖。

## 不得混淆

- 帳戶持倉資料＝使用者自填；研究工作單＝驗證過的**市場 EOD** 加上未經券商驗證的**帳戶陳述**。
- 兩方 V2.2-D 輸出的是尚未公布的週末 TDCC 戶數**推估分數**，不是真正每天的戶數，也不是未來股價上漲機率。
- MAX5 單人限制與 ATR 風控規則是**操作研究版**，不是已證明優於原 V2.2 的完整實盤績效。
- 若缺已知 ATR20、官方21交易日 EOD、帳戶更新、PIT 模型或正式公告時間，明確顯示 `WAITING` / `BLOCKED`，絕不編造 Top5、買賣價或「沒有候選股」。


## 已有原血管的 781 檔 ATR20 讀取（可選，2026-11-11 歷史母體）

2026-11-12 新增唯讀適配器 `scripts/hengce_v22d_existing_canonical_atr.py`。它**不是第二條行情血管**，只讀原本已存在於衡策私人 Library 的兩份原始檔，先做完整 SHA256 與固定 781 檔 cohort 驗證；不另行下載行情、不改動集保母體。

- 原始檔一：`/HENGCE_CANONICAL/HENGCE_2026_HIST_MOTHER.csv`，SHA256 `67cc7454094a884c4769d0fa5172bdfba175fc7b95182714a40ced3c42d28d5f`。
- 原始檔二：`/HENGCE_CANONICAL/RESEARCH/BEHAVIOR_ATLAS_20261107/G1/RETAIL_HEADCOUNTS_V2/HENGCE_G1_TDCC_RETAIL_457_WEEK_MATCHED_PANEL_2018_2026.csv.gz`，SHA256 `71083d73a791b6bf25770139c65e8d29012a44e31c39f66479806bf5a562bc88`。
- 此 SHA 封存母體**只含至 2026-11-11**；11/12 以後任何新行情都必須重新取得已驗證、已封存的原血管資料，不可沿用舊數據產生新訊號。若日期超過封存日就直接阻擋，**不能把歷史 ATR 當作今日 ATR**。
- 實算 781 檔，718 檔資料可完整核對 21 個交易日 OHLC、63 檔缺少必要資料或不符合來源驗證。結果留在使用者私人 Library `/HENGCE/Research Outputs/HENGCE_V22D_ORIGINAL_781_ATR20_20261111.csv`，僅統計與 SHA 摘要寫在公開 Repo。

在電腦上**自行將上述兩份原檔安全下載至私有本機路徑**後，可選擇讓既有 `衡策掃一次` 讀取，例：

```bash
python scripts/hengce_scan_once_router.py \
  --now '2026-11-12T00:50:00+08:00' \
  --account-holdings /secure/holdings.csv \
  --account-journal /secure/trade_journal.csv \
  --previous-worklist /secure/previous_worklist.json \
  --original-canonical-2026 /secure/HENGCE_2026_HIST_MOTHER.csv \
  --original-tdcc-781 /secure/HENGCE_G1_TDCC_RETAIL_457_WEEK_MATCHED_PANEL_2018_2026.csv.gz
```

- `--previous-worklist` 在**首次**使用時可省略，其後延續已觸發的退出狀態；不可把上一期已觸發退出的工作單刻意省略來消除該待辦。
- 原 EOD 主血管與模型研究未更動。此操作需要真實的**入場日期、實際成交價、入場訊號當時 ATR**；以上任何一項不存在，風控價就保持 `BLOCKED`。
- 此接線先驗收歷史 ATR 與人工帳戶風控讀取；它不替代真正 V2.2-D 每日事前封存模型、TDCC 首見發表時戳、企業行動處理，或券商成交確認。依舊 `buy_signal/sell_signal=false`、`broker_execution=false`。
