# HENGCE V2.4-U｜統一研究決策系統（可執行、無下單授權）

**日期：2026-11-11。狀態：RESEARCH_ONLY_NO_ORDER，`authorized_lots=0`。**

本系統整合 V2.2-D 每日散戶方向分數（Entry）、V2.4-S 凍結的 2024 年訓練續強分類（Hold），以及固定價格風險線和研究性重新進場檢查。**統一由同一個 router 對每個代號輸出一個狀態**，不會同時對持有股發出新買進研究提示。不呼叫券商 API，不修改 `scripts/hengce_scan_once_router.py`、Q017、S5、Escape、RMS 或原正式選股治理。

## 實際可用功能

| 判斷狀態 | 觸發條件 | 研究輸出 |
|---|---|---|
| `ENTRY_REVIEW` | 買前20日漲幅≥5%、5日≥0、20日成交金額中位數≥1000萬元、日小額戶減少估計分數≥0.50 | 依成交金額排名候選（至多5）、訊號日 ATR，**不臆測下一日開盤** |
| `HOLD_REVIEW` | 已確認持股及完整入場價格/日期/ATR；收盤未觸及出場線 | 最新收盤價、已知初始/追蹤線、買後5/10/20/40日最新已完成續強檢查點 |
| `SELL_REVIEW` | 持股收盤觸及買價−2 ATR20；或最高收盤上漲至少20%後觸及最高收盤−4 ATR20 | 首次觸及日期、觸發原因；**需核對次日實際成交** |
| `REENTRY_REVIEW` | 已提供實際賣出成交日、至少隔5個交易日，收盤突破前60交易日最高收盤且站上30MA | 重新進場觀察；尚非通過三年獲利驗證的硬規則 |
| `HOLD_DATA_REQUIRED` | 持倉資料缺買入日期、實際價格、初始ATR等 | 明確要求補資料，**不偽造停損或賣價** |

> `SELL_REVIEW` 比其他新進場條件優先，已持有股票不重複加碼；最近已賣出的股票只依有確認成交紀錄的 `REENTRY_REVIEW` 處理。不會輸出同股票矛盾的建議。所有狀態都是研究判斷，不是下單委託。

## 研究基準與價格執行

1. 買入研究候選在**訊號日收盤**判斷，下一個有效交易日開盤價仍未知。實際入場基準以 `entry_price` 欄由人補入；停損線是該實際成交價減 `2 × initial_atr20`。
2. 收盤觸及出場線，只產生待核對訊號。下個有效開盤若跳空，成交價不等於停損價。實際買賣手續費/滑價與賣出交易稅須以成交回報核算。
3. 續強預測沿用凍結的 `frozen_continuation_model.json`；只在**5、10、20、40**交易日檢查點使用歷史模型，不把第21至39日假裝有新模型訓練分數。出場線仍每日更新。
4. 續強分類暫只供持有監測，不會直接觸發賣出：歷史「第10天轉弱即賣」與「第10天確認才買」未驗證能改善獲利。
5. 不設資金上限，也不設最長持有天數。**本版未加入資金配置／整張交易**；因此不能宣稱已經是一套有帳戶NAV、委託數量的正式交易系統。

## 執行

Python 3.11+，`pip install pandas numpy`；資料沿用衡策既有檔案，不需另建血管：

```bash
python -m unittest discover -s tests -v
python unified_decision.py \
  --prices /existing/HENGCE_FULL_MARKET_MOTHER_RESEARCH_2018_2026.csv.gz \
  --forecasts /existing/HENGCE_V22D_DAILY_RETAIL_TWO_PARTY_RESEARCH_SIGNALS_2024_2026.csv.gz \
  --asof 2026-11-06 \
  --positions samples/positions_empty.json \
  --exits samples/exits_empty.json \
  --out results/local_decisions.json
```

產生同名 `.json` 與 `.md`，拒絕覆寫結果。如果 EOD/預測中某日期缺資料，**拒絕沿用上一日訊號假裝今天有效**。如已有持倉，請自行提供完整且已核對的 JSON 欄位：

```json
[{"Ticker":"2412","entry_date":"YYYY-MM-DD","entry_price":100.0,"initial_atr20":3.0,"shares":1000,"entry_quality":0.8,"entry_retail_score":0.65}]
```

上述數值**純屬格式示範，不是2412真實買入價、實際ATR或任何人的交易**。缺入場日期／ATR可輸入但系統回報 `HOLD_DATA_REQUIRED`。重新進場檔格式：

```json
[{"Ticker":"2412","exit_fill_date":"YYYY-MM-DD"}]
```

只有**確認實際賣出成交**後，才可填 `exit_fill_date`。輸入成交資料不代表本系統可以下單。

## 兩種每日預測輸入

A. V2.2-D 歷史原研究訊號（CSV.gz）：`date,Ticker,unadjusted_score_week_end_le10_count_decline_1pct`。此資料缺獨立的逐筆模型 PredictionAt/公告時間，**僅供歷史展示**。

B. V2.3 工程型明確時間戳：`Ticker,PredictionAt,FeatureAvailableAt,ModelTrainedThrough,CalibrationAvailableAt,TargetSnapshot,Probability,ModelVersion`。時間戳必須帶時區，模型訓練截止不能晚於推估當下，未來週目標限1至7天，當日台北22:00前才可用於研究決策。仍需要真正可追溯的來源、集保公告時間和**完整候選池**驗收。

`--strict-provenance` 會要求 `--manifest`、吻合母體 SHA 及已獨立核實的可用時間和候選覆蓋；上述歷史原研究訊號**無法滿足這個條件，應當拒絕**。Manifest 不是數位簽章，自填文字不能算真正獨立驗證。

## 歷史試跑（不是今天即時名單）

使用資料截止 2026-11-06 的既有日價母體及 V2.2-D 歷史週末推估側車：當天原研究側車有737個候選代號；依新版買前條件，合格3檔：**2412、1476、2610**。當日成交額與收盤參考價格可於 `results/research_decision_2026-11-06.json` 查閱。這份試跑**不等於原版 V2.2 的官方 Top5**；策略條件不同，來源可用時戳沒有獨立確認。由於今天是2026-11-11，**這個輸出已經過期，不能作為今天買賣建議**。

## 已完成與未完成

- 已完成：結合每日候選、持倉、風險價格、買後續強、重新進場；同股票唯一狀態；基本資料/時間不一致時拒絕；歷史價格試跑；單元測試。
- **未完成**：新資料到 EOD/TDCC 現場管線的真正自動排程、真實股東數預測逐日首次可得時間認證、持倉與成交回報同步、除權息/停牌/盤中掛單成交能力、正式選股治理和三年完整新整合策略獨立回測。未宣稱正式上線或有交易許可。

本包 `README.md`、`unified_decision.py`、`frozen_continuation_model.json`、`tests` 與 `results` 均可審查；**原始百MB級日價母體未重新複製，繼續用衡策既有正本**。