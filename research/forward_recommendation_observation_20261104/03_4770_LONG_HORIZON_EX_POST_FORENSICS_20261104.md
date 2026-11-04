# HENGCE 4770 上品｜2026-11-04 中長期資金、價格與獲利循環解剖

**地位：DESCRIPTIVE_EX_POST_RESEARCH_ONLY / NO_TRADING_AUTHORITY / NO_FEATURE_PROMOTION**  
**2026-11-04 臺灣時間盤中調查**。對話已看到 11/04 反彈，以下檢驗都是 **事後解剖**，不是沒看過結果的 OOS、不是正式模型成功證據。不得以此案例直接新增 threshold 或事後調整選股順位。**不可在公開 Repo 留存 Fugle/FinMind 授權盤中個股報價或原始分點交易資料。**

## 研究問題
2026-11-03 的非正式「搶反彈候選」為何含 4770，該標的長期價格、股東分布、法人、融資與公司基本面，是否有與普通跌深股不同的跡象？

### 11/03 當時可見資訊與來源限制
- 上一段對話曾敘述：11/03 先以五檔清單選出 4770（非初始第一），後經較廣泛壓力盤勢觀察列第一，候選與 5876/4764 等不同小組有重疊。另描述 20 交易日價格 +0.36%、當日成交額相對近期中位數 1.38x、收盤位階 52.8%、總法人 +93,746 股、融資 -127 張。**目前沒有可稽核、日期凍結的全上市正式 runner / 規則雜湊 / 研究選股排序包，故此為事前口頭理由重建，非已驗證 alpha。**
- 衡策 main `eod/20261103/status.json` = COMPLETE, all three legs complete.
- `eod/20261103/price_4.csv`: 11/03 上品 Open 283.00 High 284.50 Low 266.50 Close 276.00, VolumeShares 1,334,011, TurnoverTWD 366,283,956; previous 11/02 Close 288.50. Daily close location = (276-266.5)/(284.5-266.5) = 52.78%, decline -4.33%.
- `institutional_4.csv`: 11/03 ForeignNet +163,404 shares; TrustNet 0; DealerNet -69,658; TotalNet +93,746 shares. Legal category != beneficial owner; don't assume foreign = independent capital.
- `margin_4.csv`: 11/03 margin balance 1599 -> 1472 **-127 lots**.
- `broker_hhi.csv`: 11/03 Gross HHI 0.03034785. Pair with the 1,092 stocks in TWSE price original vessel gives 1,090 valid same-date HHI, 4770 ~21st percentile, valid-matched median ~0.04316. Not evidence of extraordinary single-broker control (no liquidity-matched control).

## Price and relative strength over longer windows, grounded public pages (as-of 11/03)
Public Goodinfo `https://goodinfo.tw/tw/ShowK_Chart.asp?CHT_CAT=YEAR&STOCK_ID=4770`:
- Nov03 Close 276; 3 months (Aug05) approx 212 -> 276 = +30.2%; 6 months (May06) 232.5 -> 276 = +18.7%; 1 year approx 248 -> 276 = +11.3%; 2 years 335 -> 276 = -17.6%; 3 years 314 -> 276 = -12.1%. Window-endpoint/adjustment differences with other vendors are expected; don't mix time definitions.
- Aug25 2026 52-week low **202**; Oct22 52-week high **316**, **+56.4%** from Aug low; Nov03 **276** = **-12.66%** from 316. Oct21 price closed limit-up **313.5**, foreign net bought +1,024 lots (not repeated daily).
- `https://toalpha.tw/stock/4770`: as-of 11/03 relative index: 1mo stock +0.4%, index -10.4%; 3mo +30.2% vs -0.1%; 6mo +23.5% vs +4.1%; 1yr +13.6% vs index +54%. **Vendor window definitions differ** from Goodinfo. Safe inference: stock outperformed broadly over 3–6 months, underperformed over a year. One year is not a permanent long-term uptrend.
- `https://info.ifa.ai/tw-stock/4770/technical-chart`: 11/03 5D avg ~292.5, 20D ~282, 60D ~247.5, 120D ~236, 240D ~232. Near-term 11/03 close fell below 20D but remained above 60D/longer. Do not treat any static moving average or price level as formal HENGCE trading rule. MACD bearish divergence signal mentioned 10/21; trend may still fail.

## Longer-term capital and holder structure (end-dated before 11/04)
- `https://www.wantgoo.com/stock/4770/major-investors/concentration`: foreign share around 6.55% Aug28 -> 9.74% Oct30 (+3.19 percentage points); 400+ lots holder share 63.35% Aug28 -> 70.09% Oct30 (+6.74 pp). These two buckets can overlap.
- `https://www.agdstock.club/EquityDistribution/4770-%E4%B8%8A%E5%93%81`: 1000+ lot holder bucket 59.56% Jul24 -> 61.43% Oct30 (+1.87pp), while small-holder composition shifted. 1000+ holders include strategic/insider and are not all trades/marginal price setters; group changes cannot identify actual individuals.
- `https://signova.tw/stock/4770`: 20 sessions total institutions net **+1,636 lots** (foreign +1,548; trusts +205; dealers -117), 60 sessions total net **+4,230 lots**, descriptive only. 11/03 foreign net purchased +163 lots and was consecutive net buyer for 5 days totaling +548 lots `https://goodinfo.tw/tw/ShowBuySaleChart.asp?CHT_CAT=DATE&PRICE_ADJ=F&STOCK_ID=4770`.
- Margin: Aug25 around 1035 lots when price 202; Oct22 around 1908 lots near price 316; Nov03 1472 lots. **Recent margin deleveraging** Oct22 -> Nov03 about -436 lots (-22.9%), yet level remains +437 lots (+42.2%) above Aug25. So "all leverage fully cleaned" is false.
- Brokerage `https://tweb.money-link.com.tw/TWStock/StockChips.aspx?SymId=4770&TWMId=Chips_STK08`: 5-day total brokerage groups net bought include UBS +266, Fubon +207, SinoPac +175; Goldman net sold ~293; **20-day** brokerage-group leaders include Goldman +301, JPMorgan +292, KGI +224, UBS +184, Fubon +181, Merrill +175; 20-day sellers Yuanta -583. One-day reports by branch ID e.g. Nomura +76 and KGI Taipei +74 are a separate **branch-vs-group** denominator. Goldman appears positive on 20d, negative on 5d, and reportedly positive on 11/03 day: **no persistent single-direction single-entity inference**. Distinct clients/accounts within same venue can trade both sides.
- 11/03 short balance for margin shares 7 lots is tiny relative to 1,334 traded; margin-short-cover alone is unlikely to explain most of the trade, though securities lending and other shorts were not reconstructed.

## Fundamental cycle 2022–2026 (not one-day catalyst)
- `https://goodinfo.tw/tw/StockDetail.asp?STOCK_ID=4770` 2022 revenue ~61.4bn? **NOTE UNITS:** site shows **61.4 億元**, annual EPS 22.54, gross margin 45.1%; 2023 revenue 56.9 億, EPS 21.22, gross 46.4%; 2024 revenue 64.6 億, EPS 21.68, gross 40.7%; 2025 revenue 47.3 億, EPS 10.20, gross 33.0%. This is a material 2025 profit/margin collapse; company is cyclical, not monotonically growing.
- Official published 2026 first-half financial statements reported `https://www.moneydj.com/KMDJ/news/newsviewer.aspx?a=bfaccbbe-b04d-4dac-8fcc-91d23dcd85ce`: revenue NT$2,363,145k; gross NT$834,650k (35.3%); operating profit NT$510,074k; attributable net income NT$450,511k, EPS **5.63** versus comparable 2025 H1 EPS 5.35 (about +5.2%). **Do not compare first-half EPS 5.63 as if full-year.**
- Published monthly revenue `https://tw.stock.yahoo.com/quote/4770/revenue`: 2026 Sept NT$579.281m (+69.02% YoY), but Jan-Sep cumulative NT$3,960.979m (+7.77% YoY); Aug YoY -29.50%. Sales by month are lumpy; one strong month insufficient as earnings proof.
- Existing disclosed order backlog about NT$7.5bn (75億元) vs early year 38億元 and planned tank truck monthly capacity 80 -> 140 -> 170 in 2027 Q1 `https://money.udn.com/money/story/5710/9766611` (Sept21). Revenue recognition, capex, capacity utilization, profit margin and timing remain forward execution risks. The company-specific positive demand narrative was publicly known BEFORE Nov04; not proof of a Nov04 surprise catalyst.
- 2025 EPS10.20, Nov03 Close276 -> mechanical trailing *2025-only* multiple ~27.1x. A better TTM may differ; do not call 27x literal audited TTM. Historical 2025 profit depressed and forward estimates are uncertain; cheapness is **not** established.

## Comparing controls and preserving counterexamples
- The same 11/03 institutional-net-buy plus margin-deleveraging pattern was also present in 4764 雙鍵 (total institutions +666,308 shares, margin -608 lots, compared with 4770 +93,746 shares/-127 lots). They diverged intraday on Nov04; therefore those two features ALONE are not a predictor.
- 11/03 close location: 4770 52.8%; 4764 (close 135.5, low130.5, high143) ~40.0%, price action differs, but a post-outcome contrast CANNOT authorize a new threshold or retrospective alpha discovery.
- No matching exchange risk factor controls, no timestamped formal model, no pre-outcome source corpus or untouched test confirmed. This is a single retrospective case and a contemporaneous loser; not an unbiased estimate of predictive power.
- Research line `research/cross_section_opportunity_20261103/CURRENT_STATE_CROSS_SECTION_OPPORTUNITY_20261103.json`: STOP_NO_FEATURE_MINING / research only. Preserved. The frozen observation cohort `01_FROZEN_FIRST_PROSPECTIVE_COHORT_20261104.json` deliberately starts at next market open because Nov04 paths were already seen. Never backdate entry to Nov03 close or Nov04 low and never score intraday-high sale.

## Working inference, explicitly not proven
**Plausible convergence:** 2025 profit slump -> 2026 expansion backlog + 3–6 month stock relative strength -> foreign and 400+lot holder share increase -> Oct21 stock volume/foreign spike -> rapid ~12–13% pullback to Nov03 close, some continuing net institutional purchases and 23% margin reduction from Oct22 -> Nov04 rebound. However a plain relief rebound, broad sector beta, seller exhaustion, execution-venue rotation and fresh retail demand also fit; specific main buyer ID and durable future rise cannot be inferred. The 400+ ownership pattern is stronger descriptive long-horizon evidence than a single day's broker tally, but still not alpha proof.

## Pending (do not invent)
1. After official Nov04 EOD: OHLC final, T86 total, margin, official BSR if lawful/access, exact-branch ID reconciliation.
2. Daily/weekly returns versus index and actual executed next-open/next-close after costs. Prospective H5/H20 only once future observations actually complete.
3. Examine if same patterns occur in *pre-declared*, as-yet-unobserved non-winning stocks; require literature first, frozen definitions and matched prospective cohort; otherwise **no new model rule**.
