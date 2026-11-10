# 衡策整張研究展示版｜2026-11-10

本分支僅提供 **研究展示轉接器**，並非新的正式選股器。正式主流程
`scripts/hengce_scan_once_router.py` 的 `reporting.top10=[]`、Q017退役、
`active_strategy_count=0`、S5 / Escape / RMS / 0元資金與無委託權限均不變。

## 如何運行（只讀）

```bash
python scripts/hengce_retail_wholelot_display.py \
 --asof 2026-11-09 \
 --ranking /path/to/verified_frozen_retail_ranking.json \
 --account /path/to/independent_research_account.json \
 --contract hengce/HENGCE_SCAN_ONCE_CONTRACT_LATEST.json \
 --out /tmp/retail_wholelot_shadow_board.json
```

`--ranking` 是**上游另行稽核、當日已可知、已凍結**的前十名，程式不會計算股票排名或挖掘新訊號。
目前倉庫內無與此規格相容的已認證前十名來源；若未提供，必須輸出 `DATA_BLOCKED`。
傳入的研究帳戶必須是**獨立的模擬帳戶**，不能拿歷史買進成交紀錄冒充當日真實持倉。

### 重要欄位

- `research_top10`：凍結順位、股號、名稱、來源日收盤價、一張估算成本、可試算張數、阻擋原因
- `position_reviews`：具當日持倉證據及行情資料時，檢查收盤跌破成本8%、最高收盤回落15%、連續3日跌破MA30且5日報酬為負
- `formal_can_buy=false`, `formal_can_sell=false`, `broker_order_execution=false`：任何輸入均不能解除
- 單張預算為 `ceil(1000 * 當日經核對收盤價 * 1.0025)`；不是明日真正委託限價，不聲稱買得到
- 資金配置為模擬上限：最多4檔，單檔上限模擬淨值30%，保留現金10%，不買零股；順序跟隨已凍結順位

### 必須補齊的真實資料

1. 事前凍結、且公告時間已驗證的 `HENGCE_VERIFIED_FROZEN_RETAIL_RANKING_V1` 清單（現階段不存在，不得假造）。
2. 持有股票的**當日**實際持股張數、成本、最高收盤、MA30和近5日報酬；缺值一律 `DATA_BLOCKED`。
3. 原有 S5、Escape、RMS 與個別股票交易適格證據；任何 `UNKNOWN` 均不得顯示為可買。
4. 在批准研究資料與完整文獻 Gate、前瞻驗證完成前，禁止升級正式策略。

## 驗收
```bash
python -m unittest discover -s tests/retail_wholelot -p 'test_*.py' -v
```

**所有內容只在獨立研究分支。未併入主線、未接自動掃描、未觸發交易。**
