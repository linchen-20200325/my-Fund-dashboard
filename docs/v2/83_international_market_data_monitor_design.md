# 83｜New UI2 國際市場資料監控 Sheet 與資料健康設計（2026-11-09）

> **現行閱讀入口／設計方向已由客戶要求入庫（DEC-2026-11-09-05）**。本文件為 **proposal／設計，不是正式 Schema、資料來源或 UI 施工授權**。本文件列出的新 Sheet 分頁名、欄位、資料健康判定、同步頻率與分母，現階段皆僅供**候選設計**。未實際建立 Sheet、未抓取 API、未修改 production。不得把候選寫成已驗證的抓取成功、已核准資料契約或可供投資決策。
>
> **領域限定**：基金儀表板的**國際市場、美股市場指標、美國／國際總經、利率、信用、美元與匯率**。使用者提供的「台股 AI 戰情室」HTML 是**UI 參考**，不是本 repo 的程式、資料 SSOT、金融規則或授權。**不移植股票選股、EPS×PE、Risk Cap、買賣判斷、台股資料層或其 Sheet 契約。**
>
> **權威優先順序**：`CLAUDE.md`／`PROJECT_RULES.md`／frozen `docs/v2/44_fund_ui_ssot.md`、`docs/v2/79_final_ui_contract_freeze.md` 與現行 `docs/DECISIONS.md` 優先；原既有 `docs/v2/50_settings_sheet_design.md` 的 `SETTINGS_SHEET_ID` 四分頁、`market_indicator`／`fetch_log` 合約不因本設計改動。本檔只說明**新獨立資料監控 Sheet 的候選**。

## 1. 正式方向 vs 尚待裁示

| 主題 | 狀態 | 具體邊界 |
|---|---|---|
| 國際資料集中盤點／每項資料是否抓得到 | **客戶要求的設計方向** | 規劃一個可追溯、集中查看的 Sheet；不能將「未抓」偽裝成「抓取失敗」或「0」。 |
| 參考台股 HTML 資料頁、第一屏狀態、來源清單／診斷 | **客戶要求借鏡方向** | 保留基金 New UI2 五頁 🌍／💼／🔍／🤖／⚙️；**不加第六頁**。 |
| 獨立監控 Sheet（方案 B） | **優先設計提案，實作待裁** | 不塞入現有 `SETTINGS_SHEET_ID`；不改 Active Sheet、`POLICY_SHEET_ID`、`NAV_SHEET_ID`、任何 OAuth／Secret。 |
| 四個候選分頁、欄位、刷新政策、來源寫入器 | **未核准 Schema／工程** | 需檢查與現行 44／50／49／79 的關係，分別取得正式決策。 |
| 資料健康、涵蓋率、門檻、Gate | **候選／不得衍生正式決策** | 無合法分母不得算百分比；FRED 月資料不能用每日是否有新觀測判斷失敗。 |
| 🌍 市場頁／⚙️ 設定頁之 UI | **只規劃資訊分工** | 🌍 呈現必要市場事實與限制；⚙️ 持有詳細來源健康與診斷；頁級 wireframe 另行核准。 |
| AI／Digest／OneBrain | **未授權** | 僅使用正式、可追溯資料做後續分析；分析結果不得寫回 canonical data。 |

## 2. 與既有系統的分界：避免讀錯

1. **現有系統設定 Sheet**：`docs/v2/50_settings_sheet_design.md` 原方案四張 `user_setting_log`、`market_indicator`、`fetch_log`、`fetch_log_open`，ID 使用 `SETTINGS_SHEET_ID`。這是既有設定／市場指標／粗粒度取數紀錄，**不是新國際資料全清單**；不得無授權改欄位或在這本上新增候選分頁。
2. **個人 Active Sheet** 只管個人持倉資料；新系統監控表不讀寫個人持倉原文、不收個人識別或秘密、不視為 Active Sheet。
3. **資料源／API 仍是資料源**。Google Sheet 是狀態 registry／觀測紀錄與使用者可見管理表，**不是自行生成市場價格的來源**；不取代 canonical `market_indicator`、FRED 序列、Yahoo 上游或正式發布日期。
4. **已存在程式**：`shared/fred_series.py` 提供多項 FRED 常數；`repositories/macro/{fred,yf}.py` 存在抓取路徑；`services/v2_tables/market_indicator.py` 有正式指標通道；`repositories/settings_sheet_repository.py` 有既有 Sheet 契約。**存在程式／常數 ≠ 新表已監控 ≠ 今日已抓取成功 ≠ 已獲准做基金計算。**
5. **FX Gate 明確維持關閉**：`FX_OBS_DATE_RULE_VERIFIED=False`；包括 USD/TWD 等已取得候選行情，不能因 Sheet 顯示「HTTP／抓取成功」而允許匯率轉換、資產總市值、基金幣別估算。各幣別方向／交易日／發布日需獨立證據。
6. **全球資料不等於新增一套宏觀判斷模型**：🌍 已核准的 TAIEX vs S&P 500 Primary 比較方向與正式 UI 約束繼續有效。本次清單聚焦美股／國際／總經／匯率，不重開主圖裁示，也不引入台股 EPS×PE。
7. **不要把資料來源健康等同市場風險或持倉健康**；`BL-0545` 真實 Active Sheet 覆蓋率 **NOT VERIFIED**，不得和本表的指標清單混作同一個分母。

## 3. 三方案比較（不應誤作執行授權）

| 路線 | 正確性／風險 | 速度／成本 | 建議 |
|---|---|---|---|
| A：擴充既有 `SETTINGS_SHEET_ID` | 觸及 frozen 44／50 四表、讀寫相容與權限 | 起步表面快，回歸風險高 | 不建議 |
| **B：獨立的國際市場資料監控 Sheet；重用已核准 L1／L2** | 職責隔離、易追溯、避免動舊契約 | 分段成本較低 | **首選設計候選** |
| C：由 Sheet 直接驅動所有來源、來源優先序與採用規則 | 易讓未驗證表格覆蓋 GitHub 決策與 Gate | 短期便利，治理風險高 | 不建議 |

推薦選 **B 的混合式治理**：*指標 ID、來源語意、正式採用與 Gate 在 GitHub 的版本化契約；Sheet 顯示清單與真實狀態，不能人工把 Gate 改成「已核准」*。方案 B 仍須另案批准 Schema／服務帳戶／寫入行為。

## 4. 四個候選分頁（**名稱與欄位均未正式核准**）

### 4.1 `catalog_status` — 一指標／來源一列的最新狀態

候選欄位：`indicator_key`、`display_name`、`region`、`topic`、`provider`、`provider_series_id`、`frequency`、`unit`、`quote_direction`（匯率）、`source_contract_ref`、`obs_date`、`release_date`、`fetched_at`、`last_success_at`、`fetch_state`、`validation_state`、`eligibility_state`、`gate_ref`、`reason`、`updated_at`。

**設計要求**：一次抓取失敗不得抹掉上一個成功觀測；`last_success_at` 不等於最新資料日；若日期／來源未取得則留空並保留原因，不補 0 或今天；觀測頻率分日／週／月／季，不以每日是否變更判斷 stale。

### 4.2 `fetch_events` — 只追加嘗試紀錄

候選欄位：`event_id`、`indicator_key`、`provider`、`started_at`、`finished_at`、`attempt_state`、`returned_rows`、`error_code`、`sanitized_message`、`retry_or_cooldown`、`provenance_ref`。

**設計要求**：未嘗試／正在抓／成功但空／HTTP 失敗／解析失敗／來源不可用分清楚；遇到既有 L1 只返回空表而沒有成功證明時，不得當成成功；原始 HTTP 回應、token、cookie、使用者 Sheet ID 與 traceback 不入表。若與現有 `fetch_log` 重疊，施工前需定義 lineage、去重及成本。

### 4.3 `coverage_summary` — 各主題範圍與缺口

僅從合法 `catalog_status` 狀態投影。四類候選群組：美股、全球市場、總經／利率／信用、外匯／美元。

**嚴禁**無正式母集合／適用條件即算完成率、成功率或百分比；「本次監控清單有幾項」不等於「全球資料真實涵蓋率」；`unavailable`、`missing`、`not evaluated`、`withheld by gate` 必須區分。

### 4.4 `data_gaps` — 缺口與後續決策

候選欄位：`gap_key`、`indicator_key`、`gap_type`、`evidence`、`blocker`、`owner`、`next_action`、`decision_ref`、`verification_status`。

列出**缺正式來源、缺發布日證據、頻率與時區未驗、來源衝突、FX 閘門、未授權 Schema、現存 L1 缺清楚錯誤結果**。不得以推論把缺口變成已修復；不要把待驗項寫成「資料不重要」。

## 5. 三層狀態，不得合併成一盞綠燈

| 層 | 問題 | 可能結果（概念字，不是 UI 核准字樣） |
|---|---|---|
| **Fetch** | 是否真的呼叫且回傳？ | attempted／not attempted／ok／empty／failed／interrupted |
| **Validation** | obs/release/as_of、單位、身份、幣別方向與版本可追溯且正確？ | verified／incomplete／conflicted／not evaluated |
| **Eligibility** | 受哪一正式規則准入做圖或基金計算／AI evidence？ | permitted for specific use／withheld／requires decision |

**三層不可互推**：`fetch_state=ok` 不代表 `eligibility=permitted`；資料不符合准入不等於 API 失敗。這些英文狀態僅用於研究草稿，**不是新增正式狀態詞或理由碼**。UI 必須遵守 `shared/ui_semantics/rules.py` 與 79 的核准字彙，缺字彙先走 G-5 等適用 Gate。

## 6. 候選監控清單：先對照現有來源，不猜現時可用

| 主題 | 候選指標 | 現有線索／限制 |
|---|---|---|
| 美國股市與波動 | S&P 500 (`^GSPC`)、VIX (`^VIX`) | 現有 Yahoo 路徑；無證據不標當日抓取成功 |
| 全球股市 | NASDAQ、MSCI World、MSCI EM；未來可擴歐日股市 | 部分正式 source 尚缺；列 `data_gaps`，不可直接開新 provider |
| 美債利率 | FRED `DGS2`、`DGS10`、`T10Y2Y` | 區分債殖利率單位與公布／觀測日 |
| 美國總經 | FRED `CPIAUCSL`、`UNRATE`、`PAYEMS`、`FEDFUNDS`、`CFNAI` | 公布節奏不同且可能修正，未取首次發布日不能猜 |
| 信用與流動性 | FRED `BAMLH0A0HYM2`、`WALCL`、`M2SL`、`RRPONTSYD` | 各自頻率與滯後需正式契約 |
| 美元／匯率 | `USDTWD=X`、FRED `DEXJPUS`、`DEXUSEU`、`DTWEXBGS` | USD/TWD Gate 關閉；`DTWEXBGS` **不是 ICE DXY**；幣別方向不可錯置 |

**新增指標及資料來源先做合法來源、授權、成本與可得性盤點**；這份表只是提議，不改原 FRED 常數或正式監控範圍。

## 7. UI 借鏡（只借版面與資訊階層）

台股 HTML 有「市場第一屏、主要風險區、主圖／核心指標、資料頁的來源清單／資格／診斷、連線狀態、下一步」等**視覺／操作模式**；對基金 New UI2 的映射：

- **🌍 市場與趨勢**：首屏先看美股、國際、總經、利率、美元／匯率的**資料狀態與既有合法指標**，缺市場 aggregation rule 時不可自造多空、Risk Cap 或買賣結論；已核准 Primary 比較圖及其 Gate 仍有效；事件發布時間軸屬未來設計候選，未查正式公布時刻前不顯示確定時間。
- **⚙️ 設定 → 資料健康度**：完整 catalog、Fetch／Validation／Eligibility 三層狀態、最後成功、資料日、缺口原因、連線診斷；**只能在既有五頁之一內設計，不增第六頁**。
- **💼 我的資產**：只保留與持倉相關的必要來源限制與查看依據，完整技術明細放 ⚙️；不把宏觀來源監控狀態套用在 Active Sheet 覆蓋率。
- **🔍 找基金**：可以借「候選／單檔查詢」互動概念，**不得借股票成長動能／價值錯殺的資料公式或排名**。
- **🤖 AI 投資總結**：Phase 7 前不開啟；AI 與資料層完全分離。任何未合格／缺資料資訊不可改寫 canonical 表。

### 重要補充：時間與財務語意

`obs_date`（觀測日期）、`release_date`（發布）、`fetched_at`（取得）、`last_success_at`（最近成功抓取）是**四個不同欄位與時間概念**。美股交易日與台北日界、FRED 月／週資料與 FX 前收的交易日需分別驗證；不准以「本日抓取成功」取代「最新有效觀測」。

## 8. 下階段設計 Gate／驗收（本次沒有授權執行）

1. 唯讀逐項對照 source coverage：每項現有 L1／L2、合法 `indicator_key`、上游 series、取得資料是否帶錯誤／observed/released、正式 Gate；列出已存在、缺口、待授權，不執行網路抓取。
2. 新獨立 Sheet 權限與 ID 命名、分頁／欄位 Schema、append-only、去重／衝突、冷卻／重試、配額、讀寫責任、遮蔽／保留政策及測試矩陣，**均須另裁**。遵循 `50` 的 secret 不入 Git、no fallback、RAW 原則，但**不擅自修改其已凍結的現行四表**。
3. 資料層只記真實取數／驗證／正式准入，AI 只讀合格 Evidence；永遠不得透過 Sheet 人工覆蓋 canonical source 或開閘。
4. 🌍／⚙️ 各自畫 **390px＋1280px 視覺稿** 與來源不可用的三種情境，需客戶另行審核；不能拿股票 HTML 當基金正式 UI。
5. 新監控 Sheet 即使建立成功，也不等於各來源取數成功、Cloud 已驗或金融計算已獲准。不得直接接正式排程／寫入／OAuth。

**本文件與歷史互斥規則**：讀 `docs/v2/50` 時，仍須照既有四表契約執行；不能用其「本本試算表不放其他分頁」去否定**另一個未來候選獨立 Sheet**，也不能用本文件主張在 `SETTINGS_SHEET_ID` 新增 `catalog_status` 等四頁。讀 `docs/v2/80` 時，五頁 IA／資料邊界與原 market Primary 契約不變；本文件新增的是**資料治理設計候選**，非覆寫 80。

## 9. REUSE 8 項補證後的文件檢查點（2026-11-09；研究索引，非正式契約）

> 本節承接客戶 `DEC-2026-11-09-06` 的 G1＝A-mod、G2＝A、G3＝A-mod，以及已合併的 `docs/evidence/reuse8_offline_evidence_2026_11_09.md`。僅把**既有證據的適用範圍與待驗缺口**導引到設計入口；詳細列數、原始探測、推論、研究分類以兩份 evidence 為準，這裡不維護第二份數據清單。下列資料**不是**最新即時行情或正式准入證明。

| 候選／既有來源 | 已有的離線證據（限縮解讀） | 進一步判斷前仍需的證據或 Gate |
|---|---|---|
| A1 S&P 500（`^GSPC`）、A11 TAIEX（`^TWII`） | 舊快照與共用資料路徑、fixture；不能證明日 K 的交易所時區時間戳 | 真實來源日 K 時區／切日證據；與正式 Primary 圖日期契約核對 |
| A3 VIX（`^VIX`） | 既有探測含時區與部分原始時間戳；歷史快照可離線比對 | 交易日差異、同日快照與探測值差異的原因；不得視為已驗證的資料修正 |
| D1 USD/TWD（`USDTWD=X`） | 舊探測有時間戳與切日差異；不同 run 不得混算 | `FX_OBS_DATE_RULE_VERIFIED=False` 仍封鎖准入；需額外證據和正式裁示，不能由讀檔開閘 |
| C1／C2：FRED `DGS10`、`DGS2` | 離線 cron 快照存在；**非**共用 L1 在 Cloud 可用的證據 | 共用 L1 真實連線、觀測／發布日語意與資料資格均待驗 |
| C6：FRED `FEDFUNDS` | 共用程式及替身測試；現有 cron 快照清單不含該 series | 真實來源結果、vintage／發布日證據、正式准入均待驗 |
| C7：FRED `BAMLH0A0HYM2` | 離線快照可見，含月底週末日期列；原因未證 | 頻率／日期粒度、歷史長度、共用 L1 與 vintage 真實行為待驗 |

**跨來源待查線索（非錯誤定論）**：VIX 快照比 SPX 多兩個日期、VIX 一日快照與舊探測值不一致、TWII 快照有一筆週日列。原值、日期及抽樣交叉驗證詳見 `reuse8_offline_evidence_2026_11_09.md` §3、§7，不能以相同供應者的兩份歷史資料稱為獨立交叉驗證。

**實作與裁示邊界**：`INDICATOR_SPECS`、`market_view.DOMAIN_ORDER` 與 REUSE 8 項未完成一對一正式對齊；本節不建立正式母集合、Eligibility、涵蓋率分母或新 `indicator_key`。下個補證路線可比較「只沿用既有文件」「離線重驗」「另行授權的受控上游取數」，但本節不核准上游探測、程式／工作流程、Sheet／writer、FX Gate、金融計算或 AI 分析。未來任何探測與正式來源契約須另過 Decision Gate。
