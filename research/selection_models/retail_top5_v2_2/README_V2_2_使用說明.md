# V2.2操作與策略規格

## 一鍵選股

Python 3.11以上：

```bash
python -m pip install -r requirements.txt
python select_stocks.py --decision 2026-11-06 --output my_result_20261106
```

輸出資料夾必須不存在，避免覆寫。原資料為2026-11-06截止批次，指定11/13會拒絕，不產生空殼名單冒充成功。

|檔案|內容|
|---|---|
|all_qualified.csv|全部通過基礎條件的股票，排序及Top5旗標|
|candidates.csv|上表前5名，少於5檔就如實輸出|
|research_pairs.csv|成功配對對照股的研究子集，**不是入選門檻**|
|selection.json|三種結果、策略參數、來源／程式SHA及核對範圍|
|report.md|中文完整排名與資料、資金假設說明|

以原附件11/06資料為例，全合格7檔：6446、2412、1476、2610、2254、4720、6782；Top5為前五檔。研究配對仍為2254、6782，其中6782雖能配對，排名第7仍不入Top5。

## 新策略版本：all_qualified_top5_v1

V2.2是候選池及資金規則均改變的新研究版本，無法沿用V2.1或其他Top5歷史報酬。

- 主模型僅週五決策、集保延遲14日；20交易日漲幅至少5%、5日報酬非負。
- 20日成交額中位數至少1,000萬元，完整20日波動度可計算且大於0。
- 10張以下持有人數兩個觀察間隔下降至少1%，每段相隔5至10日；缺週不跨週補算。
- 合格股以20日成交額中位數降冪、股票代號升冪排序。配對成敗不影響排序或資格。
- 全部合格股都保留；Top5嚴格取前5檔。21日延遲封存是分開的敏感度情境，不與14日合併。

`strategy.py`列出參數，封存亦寫入並於重算時核對。這些是本版明定的工程假設，未經績效調參或驗證。

## 五檔整張資金情境

最多5個持倉，每個新入選標的成本上限NAV18%，保留10%現金。18%來自90%可投入資金除以5檔，是本版採用的等額預算，並非已驗證最優配置。

每張1000股，買進成本估0.25%。各檔張數向下取整。買不起一張、已持有或未通過情境檢查則零張；**不遞補第6、7名，不把某檔沒用完的預算分給其他檔**。這會使實際買進少於5檔、現金高於10%，是規格的一部分。

已有持倉時提供held_tickers及position_market_values；兩者須對應，現金加市值須符合NAV（差額容許0.01元），任一既有持倉超過18%則停止新增情境試算。這是情境輸入檢查，未與真實帳戶核對。

```json
{"nav":1000000,"cash":850000,"held_tickers":["1101"],"position_market_values":{"1101":150000},"as_of":"2026-11-06"}
```

## 封存與排名

```bash
python freeze.py price_seed_through_20261106.csv.gz chip_seed_through_20261106.csv.gz 2026-11-06 my_rehearsal.json --rehearsal
python rank_whole_lot.py --freeze my_rehearsal.json --prices prices_example.csv --account account_example.json --risk risk_example.csv --output my_rank.csv
```

附帶rehearsal_verified_20261106.json為本版可重算演練檔，schema為retail_forward_v2_2。排名會重新核對來源、母體與七個程式SHA，重算14／21日的完整候選、Top5與研究配對，並核對策略參數。舊schema、篡改名單或假雜湊拒絕。

要執行**假設**資金試算，在排名命令加`--simulate`。prices輸入欄位ticker,reference_price,as_of；risk為ticker,rms,s5,escape,account_eligible,tradable,as_of；account含nav,cash,held_tickers,as_of。日期需對應決策日。risk全PASS僅是情境假設，不是正式證據；附帶範例仍為PENDING，故即使加--simulate也會是0張。

|輸出欄位|意義|
|---|---|
|authorized_lots、lots_for_manual_review|永遠0|
|gate_all_pass|永遠False，沒有正式證據鏈|
|input_gate_all_pass|不可信CSV是否全PASS，不能當核准|
|simulation_lots|只在--simulate、情境條件齊備時顯示假設張數|
|reference_control|有研究配對才填；空白不阻擋入選或資金情境|

目前沒有正式母體、公告存證、風控憑證、帳戶來源及報價時效核實，不支援正式模式：不加--rehearsal的freeze、prospective封存、select --mode official均拒絕。不提供例外開關，不自動下單。

## 固定資料基準與錯誤回報

來源固定為原附件的30個日價日期與10個集保快照。reference/bundled_contract.json含逐日／逐週清單、來源SHA和批次標籤；基準自身SHA亦固定在程式中。所有公開CLI都核對該基準。這防止原批次被縮減、增刪或換值，但不是獨立官方母體證明。

--daily、--weekly可指向原資料相同位元組副本；--contract僅接受相同基準副本。新來源、重新壓縮或重新儲存都需新的受控獨立基準；正式管線尚未取得，不能解除限制。SHA與重算不是簽章或不可改寫存證。

損壞gzip、CSV解析失敗、空檔、編碼錯誤會轉為DATA_INPUT_ERROR，含batch、daily/chips標籤、實際輸入SHA及原因；CLI非零退出，不產生選股目錄，也不以Traceback當作一般資料錯誤訊息。錯誤不會放寬驗證。

screen()是舊研究配對純計算函式；eligible_stocks()是全部基礎合格股純計算函式。兩者不驗證來源。正式公開CLI則使用來源核對入口；不能把直接呼叫純計算函式視作官方核驗。

## 驗證與未完成事項

```bash
python -m unittest discover -s tests -v
```

53項測試：原36項更新，新增17項Top5及異常輸入測試。包括7檔與前5檔獨立期望值、配對分離、未來資料不影響歷史訊號、五檔18%與10%現金、買不起不遞補、已有5檔不加第6檔、策略／封存篡改、損壞gzip及CSV標準化。

目前只有短期歷史輸入，沒有多年走勢外驗證、企業行動調整、證券身分核對、歷史公告首見時間、交易日曆、逐日帳務／成交滑價回測、動態出場或賣出引擎。未自行杜撰賣出規則或沿用舊績效。既有RMS/S5/Escape亦未接，授權仍為0。

legacy/保存先前版本說明、封存和使用者本次提供的獨立驗收原文／腳本／實際log，僅作證據，不是本版操作指令。
