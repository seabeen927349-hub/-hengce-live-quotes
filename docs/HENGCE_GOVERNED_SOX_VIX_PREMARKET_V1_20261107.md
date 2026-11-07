# HENGCE 外部官方指數盤前資料血管 V1 — SOX + VIX

日期：2026-11-07。使用者明確指示完成隔夜費半與 VIX 自動化。此為**新治理範圍的海外研究資料血管**，不將外部資料默默填入原台股 canonical 母體，不恢復已退役的 Q017，不變更選股、Escape、S5 或交易權限。

## 來源、格式及儲存

- Nasdaq：`https://indexes.nasdaq.com/Index/ExportHistory/SOX`，官方歷史 XLSX（需 `openpyxl`），取 SOX 日收盤。
- Cboe：`https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv`，官方 VIX 日收盤 CSV。
- 永遠只使用台灣開盤前已完成的美股交易日；兩來源**最新美股交易日必須相同**，且與台股目標日相差不超過 4 個日曆天。
- 每筆數據保存實際原始資料的 SHA256、來源網址、下載時間、比較收盤值及模型分級；不在公開 repo 散布 Nasdaq XLSX 或整份 VIX 歷史 CSV。來源並非數位簽章的付費行情，不可宣稱市場交易所對使用者的資料真實性背書。
- 產出 `overseas_premarket/latest.json` 和獨立雜湊命名的 `overseas_premarket/history/YYYYMMDD_<hash>.json` 研究影子收據；由衡策安全租約 `hengce_publish.py` 出版，禁止盲目 rebase。

## 模型

保留 2018–2024 訓練、2025–2026 回測的既有雙因子係數；不為 11/9 例子重訓：
```
gap_log_pct = 0.041642424724208524
             + 0.15095610356018835 * (100 * ln(SOX_latest / SOX_prior))
             - 0.0036574564504370257 * (100 * ln(VIX_latest / VIX_prior))
```
歷史分位門檻為 `[-0.19055541322518293, 0.0000503213262588, 0.12993431163319522, 0.32424484685128574]`。結果為五級「強烈偏空／偏空／中性／偏多／強烈偏多」及預期台股開盤跳空**對數百分比**。不代表 08:45 的實際可交易價格或當天收盤方向，也不代表持續累積/撤退等資金環境。

## 排程與鏈接

1. 新 `.github/workflows/hengce-overseas-sox-vix-premarket.yml`：台灣交易日週一至週五 08:10 與 08:30（第二次重試）擷取官方資料。GitHub schedule 可能延後；不保證分秒準時。PR 執行真實來源探測與離線時序回歸，手動 dispatch 可選 probe 或 run。
2. 既有 `HENGCE FinMind PreMarket Shadow Bridge` 仍保留 08:40 與 FinMind workflow_run 觸發，盤前讀取**日期完全符合**的 `overseas_premarket/latest.json`，重新核算模型係數、來源收據雜湊、源日期與值才可輸出 `VERIFIED_GOVERNED_OVERSEAS_SOX_VIX`。
3. 結果透過已合併的 `scripts/hengce_two_time_scale_environment_display.py` 顯示短線結論；長期資金環境仍只接受衡策 canonical 20／60／120 日正式證據，若無資料顯示「資料不足」。
4. ChatGPT 08:45 定時任務可以優先讀 GitHub `overseas_premarket/latest.json`；當檔案延後、缺漏、日期不符或來源不可核驗，必須回報「資料不足」，不可拿上週資料假裝今天資訊。
5. 因台股休市日前瞻行事曆仍需官方核驗，來源收據「週一到五」只表示日曆工作日，不能單靠此欄斷言台股開市。

## 驗證

```bash
python -m pip install 'openpyxl>=3.1,<4'
python -m unittest discover -s tests/engineering -p 'test_hengce_overseas_sox_vix_premarket.py' -v
python -m unittest discover -s tests/engineering -p 'test_hengce_finmind_premarket_bridge.py' -v
python scripts/hengce_overseas_sox_vix_premarket_v1.py --mode probe
```

**就緒判準**：官方原始資料下載 probe PASS、回歸測試 PASS、GitHub main 排程成功生成 `target_tw_date` 對應的 `overseas_premarket/latest.json`、同天 FinMind 聚合橋接成功，08:45 報告讀到一致時戳。單獨合併 PR 不構成「實際交易日已完成端到端驗證」。
