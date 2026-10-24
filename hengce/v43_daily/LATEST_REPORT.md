# 衡策 V43 每日獨立篩選報告

- 報告時間（台北）：`2026-10-24T12:50:52.379856+08:00`
- 資料日期：`2026-10-22`
- Engine：`HENGCE_V43_DAILY`
- Frozen model：`V43_EXPANDING_REGIME_ICIR`
- 狀態：`PASS`
- 權限：`SCREENING_ONLY_NO_ORDER_AUTHORITY`

## 今日市場狀態

- Regime：**WEAK**
- Breadth20：`0.41772152`
- V43 exposure：`0.62136642`
- Risk multiplier：`1.0`
- Predicted daily sigma：`0.01784037`

## 今日 Top 3

| 排名 | 股票 | 名稱 | V43 score | 組合權重 | 有效曝險權重 |
|---:|---:|---|---:|---:|---:|
| 1 | **3044** | 健鼎 | 0.77742947 | 0.42649421 | 0.26500918 |
| 2 | **2355** | 敬鵬 | 0.76878371 | 0.27228671 | 0.16918982 |
| 3 | **6438** | 迅得 | 0.76043905 | 0.30121907 | 0.18716742 |

## Frozen schedule / prospective validation

- Schedule 狀態：`FROZEN_BASKET_ACTIVE_OR_AWAITING_COMPLETION`
- Pending candidate：`{"signal_date": "2026-09-24", "reason": "INSUFFICIENT_FUTURE_SESSIONS", "sessions_available_after_signal": 17, "sessions_required_after_signal": 21}`
- 今日是否為 frozen schedule signal：`False`
- 完整 post-lock baskets：`0`
- Prospective 狀態：`WAITING_FOR_POST_LOCK_DATA`

## 完整性

- Historical parity：`True`
- Rebuilt events SHA-256：`ed5b0c4caff523525ecafb303e04dc82bc07d7d2fe706733edf4ce0180ecfd6e`
- Canonical observer commit：`959f96831fdea65f32bed65ca11011d67328f695`

> 這是衡策獨立 V43 篩選引擎的每日研究報告，不是 Q017 輸出，不是券商委託，不建立下單權限。每日 watchlist 不會被當成新的 H20 prospective basket；prospective 證據仍只依 frozen non-overlap schedule 計算。
