# 衡策雙時間尺度大環境輸出規格 V1

2026-11-07｜定位：唯讀研究／監測介面（不改變原模型、選股、Escape 或交易授權）。

## 兩個固定結論

| 欄位 | 所需資料 | 可顯示的標籤 |
|---|---|---|
| `today_market_environment.label` 今日市場環境 | 台股開盤前經查驗的隔夜費半與 VIX 預報 | 強烈偏多／偏多／中性／偏空／強烈偏空 |
| `long_term_capital_environment.label` 長期資金環境 | 原衡策正式 EOD、法人相對淨流、產業承接與中長期確認證據 | 持續累積／資金輪動／資金撤退／恢復中／資料不足 |

任一軸資料未達正式門檻時，顯示 **資料不足**；「中性」不是沒有資料，而是市場方向分類中的中性。兩軸完全獨立，禁止換算為單一加權多空分數。

## 與原橋接的關係

`scripts/hengce_finmind_premarket_bridge.py` 現在在原輸出 JSON 增加 `two_time_scale_display`（原 `premarket_forecast`、`observed_breadth`、`macro_regime`、`escape_formal_state` 欄位保持不變）。投影邏輯為 `scripts/hengce_two_time_scale_environment_display.py`。只讀 FinMind 已有聚合資訊，不下載第二組 FinMind 資料。

- 當既有上游海外封包只有 `PIT_SCHEMA_VERIFIED_UPSTREAM`，代表只驗證了日期與結構，**不能**當作 Nasdaq / Cboe 來源行情已驗證；今日軸保持「資料不足」。
- 將來海外治理血管真正完成來源驗證時，可在 `VERIFIED_GOVERNED_OVERSEAS_SOX_VIX`、來源憑證／完整性欄位滿足規格後顯示五級標籤。**目前主排程沒有提供這個來源封包，因此不能宣稱今日軸已自動出結果。**
- 目前原 FinMind 聚合快照只可報告市場廣度與價格／流動性，**不是** 20／60／120 日資金累積證據。
- 長期資金軸不能直接由 `L0_NORMAL` 等 Escape 警戒級別推導「持續累積」，也不能因一天價格下跌直接判「資金撤退」。原 S5 分群也不是長期資金分類。
- 長期軸只有在一份**另行完成正式驗證**的 canonical 資金狀態憑證存在時，才允許用明確標籤；目前 bridge 的正常呼叫並沒有注入這份憑證，因此預設「資料不足」。程式對測試／未來外部封包的欄位檢查只是契約檢查，**不能替代原有血管對來源真偽、雜湊與市場日曆的實際稽核**。

## 狀態衝突（必須同時顯示）

今日「強烈偏多」 × 長期「資金撤退」：只代表隔夜美股利多可能造成開盤反彈，不能把長期撤資狀態重置。
今日「強烈偏空」 × 長期「持續累積」：只代表隔夜風險升高，不能直接推翻數十日至數月的累積狀態。
兩軸都不能產生買賣單或自動修改任何正式評等。

## 自動化與驗證

原 `HENGCE FinMind PreMarket Shadow Bridge` GitHub Action 已新增本模組與專屬測試。可執行：

```bash
python -m unittest discover -s tests/engineering -p 'test_hengce_finmind_premarket_bridge.py' -v
python -m unittest discover -s tests/engineering -p 'test_hengce_two_time_scale_environment_display.py' -v
```

介面必要欄位：兩個標籤、各自 status/source_scope、日期、來源憑證、資料不足理由與無交易權限旗標。欠缺來源要呈現欠缺，禁止自行補值。
