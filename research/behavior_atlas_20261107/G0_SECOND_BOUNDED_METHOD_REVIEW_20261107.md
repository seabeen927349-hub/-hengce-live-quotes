# G0 — 第二輪（最後一輪）專題方法文獻完整核對

研究：HENGCE HUMAN BEHAVIOR ATLAS；日期：2026-11-07。  
**研究範圍只限於群體交易／持股結構的行為模式；不執行 G2/G3模型、特徵、報酬檢查。**  
主文獻庫 P1 15大領域2026-11-02暫時充分覆蓋；本輪針對 G0 尚缺的**時間序列行為模式、叢集穩定性、對抗性驗證及依存資料多重檢定**補四篇可讀完整HTML方法與結果、另外列出仍只有方法摘要的文章。研究總目標不變。

## 新增逐節核讀的四篇公開全文（FULL_HTML_READ，本輪新增，不冒充前輪全文）

| 原文及識別 | 學術方法與實驗 | 結果與強反證 | 衡策可遷移的限定用途 |
|---|---|---|---|
| Klassen, Tatusch & Conrad (2023), *Cluster-based stability evaluation in time series data sets*, Applied Intelligence 53:16606–16629, https://doi.org/10.1007/s10489-022-04231-7 | 閱讀 §2–§5 方法：CLOSE/FCSETS 區分個別序列群內同伴、分群跨時點組成穩定性、對異常行為 subsequence；比較KMeans、DBSCAN、FCM、evolutionary clustering，含3真實及1模擬資料、表圖與設定敏感性。| **時間穩定不等於統計顯著，更不等於有經濟預測力**；同一次群集拆分/合併與不同行為軌跡可造成分群不穩；作者在§5.2指出缺少可直接對比完全相同評估目的的定量基準；小樣本及不完整序列脆弱。| 可為群體「狀態轉移／成員關係隨時間變動」提供驗證方向，但不直接移植作者參數或宣稱真實投資者群體。 |
| Iglesias Vázquez & Zseby (2024), *Temporal silhouette: validation of stream clustering robust to concept drift*, Machine Learning 113:2067–2091, https://doi.org/10.1007/s10994-023-06462-2 | 閱讀§2–§7：Temporal Silhouette處理concept drift與 out-of-phase outliers；站在缺真實標籤的無監督分群出發，測試4經典資料集分群錯誤型態、超過200個模擬資料集、4個stream cluster方法與多種對照CVI，含參數敏感度和表圖。 | **靜態分群品質指標可把概念漂移誤判為正常**；反之過度追求即時穩定會忽視真正群體轉變。作者對資料生成/評估環境的實證不能直接外推台股。 | 行為圖譜需獨立報告時間漂移、過度/不足分群和錯時異常；不預設分群數一定為固定幾類。 |
| Holder, Middlehurst & Bagnall (2024), *A review and evaluation of elastic distance functions for time series clustering*, Knowledge and Information Systems 66:765–809, https://doi.org/10.1007/s10115-023-01952-0 | 閱讀§2–§7：九種彈性序列距離、KMeans vs KMedoids、UCR多資料基準、多比較及不同初始化/資料正規化/參數敏感度。| **DTW不一定優於簡單Euclidean**：作者的UCR群集基準下DTW+KMeans往往不優，KMedoids或MSM/TWE可改變排名；結論只適用其UCR單變量資料，不能直接當台股最佳方法。 | 研究必須保留簡單距離與簡單群聚作基準，不能以高複雜度方法為理由多試幾十種。 |
| Conrad, Tonello, Zonker & Siebert (2025), *Detection of dynamic communities in temporal networks with sparse data*, Applied Network Science 10:1, https://doi.org/10.1007/s41109-024-00687-3 | 閱讀methods/benchmark/實體案例/討論：比較缺節點、缺邊、缺時間解析度；多層網路的集群平滑或無平滑、逐層合併、穩定/非穩定環境；模擬真值及實際主題案例。| **聚合時間片可掩蓋真正快速變動**；相鄰層合併只能在較穩定群體時部分彌補稀疏；若關鍵節點整段缺失，無法靠平滑恢復。作者研究的是可觀測網路，不能把股票級法人與TDCC級距**擬成具名買賣雙方網路**。 | 對缺週、上市/上櫃混入、群體結構轉折應做資料完整性與多時間解析度敏感度；禁止「自動填補」創造虛構交易邊。 |

**以上四篇全文核讀以出版社HTML原文的完整方法段、結果/圖表討論與結論為依據；未在本輪對其PDF做額外圖像重讀，圖表詳細數值不拿來作HENGCE參數或效應主張。**

## 重要的反方向、方法局限文獻（PARTIAL／摘要＋可查方法，未冒充FULL_READ）

| 來源 | 已確定可用的負面約束 | 本輪深度 |
|---|---|---|
| Ando & Bai (2017), *Clustering Huge Number of Financial Time Series: A Panel Data Approach With High-Dimensional Predictors and Factor Structures*, JASA 112:1182–1198, https://doi.org/10.1080/01621459.2016.1195743 | 橫斷面共依賴、因子與異質性會使金融時間序列同動；單純相似度不能自動解讀心理。 | PARTIAL: 摘要／研究模型範圍；全文受供應商限制 |
| Peña & Tsay (2023), *A testing approach to clustering scalar time series*, Journal of Time Series Analysis, https://doi.org/10.1111/jtsa.12706 | 不應先假設「一定有多個自然分群」；作者用AR sieve bootstrap先測群集是否存在；對非線性／橫斷面相關序列的適用性有限。 | PARTIAL: 出版社公開方法／結論段；未完整審核原表 |
| Smeekes & Westerlund (2018), *Robust block bootstrap panel predictability tests*, Journal of Applied Econometrics, https://doi.org/10.1080/07474938.2018.1536102 | panel依賴、預測者持續性、斜率異質性要求非i.i.d.推論；簡單每日樣本當獨立會過度自信。 | PARTIAL: 出版社方法／摘要；未完整審核原表 |
| Sullivan, Timmermann & White (1999), *Data-Snooping, Technical Trading Rule Performance, and the Bootstrap*, J Finance 54:1647–1691, https://doi.org/10.1111/0022-1082.00163 | 多個可能方法反覆測試需要校正資料探勘；不能只報最好一個。 | PARTIAL: 出版社論文摘要／方法概要與固定配額要求；未重讀所有表格 |

## 研究方法上最重要的四個約束（只提出預註冊要求，**不創建特徵或模型**）

1. **零模式原假說必須可存在**：G3允許最後報告「無可重複群體規律」，不可強迫分群器一定輸出漂亮群。
2. **時間狀態必須獨立驗證**：時間平滑／群體穩定可能把真正轉折抹掉，頻率是週TDCC與日法人不一致；不能靠補值虛構共同時點。
3. **因子與制度假象必須列競爭解釋**：共同市場/產業/宏觀下跌及機構風控能造成同步，不代表投資者互相模仿。
4. **探索配方硬上限維持6**：G4以嚴格跨年、事件獨立、非i.i.d.與多重比較反證；本輪文獻不授權實作新方法，只有 G2 預註冊才決定配方、樣本、基準和驗收門檻。

## 專項文獻審核結果

- 第2輪查核已完成：既有台股5大行為金融核心文獻及主Master Ledger反例維持原FULL_READ/PARTIAL狀態，不逆向改寫；新增 **4 篇完整可讀出版社HTML 方法／實驗／結論**，另記4篇部分可核對的競爭性方法。
- 正面：台灣確有投資人行為異質與群體同動的學術支撐，但動機及交易者實際身分不能由公開聚合四腿直接辨認。
- 反面：局部股權集中度未呈普遍報酬優勢、群聚可能虛構、復用歷史/不合理離散化易出現資料探勘；這些反例明確列出。
- **方法文獻足以支援一個以可觀察聚合行為、因子競爭解釋與嚴格反證為核心的受限描述性研究**；不得聲稱已證實可交易預測力。
- 本輪沒有查任何新候選規律或未來報酬；與「研究者自選六個配方」分開，正式配方與G2事前凍結仍尚未開始。
- G0可判決 **PASS_LITERATURE_ONLY**（待由LITERATURE_GATE.json及CI同步登記；只授權G2預註冊的文獻先決條件，G1尚阻擋）。

**繼續研究的具體順序**：G1歷史上市普通股證據／TDCC週初見時點的限制與候選股分離 → G1描述性可用Gate → G2唯一預註冊 → G3六個上限配方。