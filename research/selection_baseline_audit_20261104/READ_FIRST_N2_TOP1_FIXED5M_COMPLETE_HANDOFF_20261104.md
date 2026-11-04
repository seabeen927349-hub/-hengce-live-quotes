# READ FIRST — 衡策 N2 Top1 每次固定500萬、不複利，2026-11-04 完整交接

**目的：讓新對話接手已完成研究，不能重新做一堆漂亮回測。** 本文件獨立於正式研究 HEAD，僅為交接，不改 main、Canonical 或交易系統。

## 研究權威

- Repository: `seabeen927349-hub/-hengce-live-quotes`
- 凍結研究分支: `research/n2-top1-fixed5m-no-compound-20261104`
- 已確認研究 HEAD: `edc6a713b6a640738773ba1957d8c95fa82e3b71`
- 規則凍結 commit: `b49f37ab6e463e37f84f4441cca69de9767ccede`
- 結論: `research/selection_baseline_audit_20261104/N2_TOP1_FIXED5M_NO_COMPOUND_RESULTS_20261104.md`
- 原始 N2/D1 TopK 研究: `research/n2-d1-top1-top3-top5-fixed1m-20261104`, SHA `ac0bee88c07abf48201a7e5d398e1d6642c2db27`
- 正式策略／交易權限: `NONE`.

## 經過驗算的研究結果，不等於實盤能力

- N2 是**過去5日相對弱勢排名**，不是「真正跌深」。TWSE 上市電子股 PIT 歷史電子股分類、近60交易日成交金額中位數與 >=50 資料 Top100；每次只選第1名。
- 84 個獨立歷史訊號窗口，2018–2026；每個窗口**重新給 NT$5,000,000**, 不複利、不使用前次盈虧、不買第二檔、不重疊。
- 次交易日開盤模擬買進，入場日算第20個TWSE交易日收盤賣出，只買1000股整張，未買足的錢閒置；來回成本40bps，壓力80bps。
- 84/84 以開盤價名目買得起整張，46勝38敗；平均投入97.92%。40bps後84次獨立損益**加總 +NT$19,883,039**，單次平均+NT$236,702.85（**不是單一500萬實盤帳戶的期末資產、也不是年化率**）；80bps後+NT$18,237,928。
- 最佳單筆 +NT$4,437,393.20，最差 -NT$1,684,980（-33.7% of 5m）；2024年9次僅2勝7敗、加總-NT$2,643,856.40。
- 同84次100萬Top1結果僅79次至少一張；同76次既有研究精確對帳PASS。原本93/93本地工程測試PASS，但不代表 alpha PASS。結論 `ALPHA_INCONCLUSIVE / TRADING_NO_GO`.

## 交接與原始數據位置

HENGCE Library:
`/HENGCE/Research Outputs/N2_TOP1_FIXED_5M_HANDOFF_20261104/`

- **完整版** `HENGCE_N2_TOP1_5M_COMPLETE_HANDOFF_20261104.zip` (31,612,829 bytes; SHA256 `301c56aaca3ad3251b4b3ffd0e23e34fea1d8aa30b126305aef031ae1d5bd961`) : 九個經驗 SHA 的 2018–2026 原始電子股年度來源封存、六份前期完整研究 ZIP、最新84筆 ledger、年度績效、源/碼/測試及逐檔 SHA manifest。
- **快速版** `HENGCE_N2_TOP1_5M_QUICK_HANDOFF_20261104.zip` (443,973 bytes; SHA256 `deac1ef1a73d997f262a638cabde04ae13b691312d4a2e86516ddffb62615733`) : 含交接與研究、不重複九個年度資料包。
- **閱讀入口** `00_READ_FIRST.md`；**給新對話的完整複製指令** `01_COPY_INTO_NEW_CHAT.txt`。
- 正版資料位置 `/HENGCE_CANONICAL/HIST_SOURCE_2018_2026_20261027/`，不得覆寫。

## 下一階段：一定先做這些

1. **獨立核驗回測與檔案**：用完整版 manifest SHA 對帳，重跑現有回測及93項測試；任何日期或股票不一致先停下來。
2. **除權息真實總報酬**：N2 Top1 的訊號前5日公司行為曝險9件、持有期4件。重建投資人實際可得現金、股數、權益與發布時序；應分成「不變原名單總報酬核對」與「新增 PIT-safe 調整後訊號研究」，不得悄悄重選原版。
3. **500萬元次日開盤成交能力**：須有09:00分鐘或逐筆成交量／撮合資料、漲跌停狀況、可成交張數及滑價，不能用整天成交額當開盤保證。缺資料判 `EXECUTION_DATA_BLOCKED`。
4. **虧損原因研究**：2024年的9筆（2勝7敗）、最差單筆等，分門別類檢查「接刀」與市場環境，避免針對舊結果調參優化勝率。
5. **真正前瞻**：所有新條件先版本化、事前凍結；從未來零資金不可重寫觀測開始，沒有合法未來績效不得升格。

禁止複利、禁止五次100萬元模擬、禁止 Top5 代替 Top1、禁止在已看過2018–26結果上尋優後自稱 OOS、禁止修改 main / Canonical / Q017 / Escape / frozen Selection、禁止給實盤買入授權。保留 `DATA_BLOCKED`、`INCONCLUSIVE` 作為合法結果。

**下一個 ChatGPT 對話可直接打開本文件與 Library 完整包後開始做事情，不用再問已經給過的設定。**
