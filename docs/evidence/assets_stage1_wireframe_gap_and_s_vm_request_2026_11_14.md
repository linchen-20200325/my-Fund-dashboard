# 💼 我的資產 Stage 1：線框缺口盤點與最小施工 Gate 申請（2026-11-14）

> **基準**：main `ede93f6fe9330deecd429c824422fcd975d7625b`（#1246 merge；其 push CI 作者撰寫時尚未完成，**以 GitHub 為準**）。docs-only。
> **性質**：**盤點與申請，不是授權**。不改 Old UI、`ui_v2`、`ui_v3` 任何檔、`registry.py`、frozen 44、Schema、FX、DG2、公式、資料來源；BL-0545 BLOCKED，不要求真實持倉；不新增來源／Agent／MCP／付費項目。
> **事實來源**：2026-11-14 一份唯讀盤點（subagent，單組，未跑 pytest；DEC-2026-11-04-01／-02／-03 DECISIONS 原文未逐字讀，其內容引自 82 §0.1／§9.8，屬二手）。總管（作者）另親自抽查四個承重點，見 §六。〔事〕＝讀碼可核；〔推〕＝作者推論；〔Gate〕＝需客戶裁示。檔案引用為「檔案::符號」，不寫行號。
> **品質狀態**：單組作者草稿，**尚待非作者獨立 QA**。

---

## 一、結論先講

1. 〔事〕**精修後 Stage 1 線框客戶尚未審**：客戶只在 2026-11-09 給方案 A 並附三項精修（`DEC-2026-11-09-04`）；停點仍是「客戶審核精修後的 Stage 1 線框」。文件中**沒有**任何宣稱客戶已審，也**沒有**已建的 💼 程式（`ui_v3/pages/` 只有 `mkt`／`chrome`／`chart_svg`；`ui_v3/viewmodels/` 無 💼 VM；`registry.py::IA_PAGES` 的 `ast` 為 `registered=False`、原因 `wireframe_not_approved`）。
2. 〔事〕**線框不是沒有，是只有文字版且有缺口**：82 §11.9.7（精修後 390px，三情境）、§11.9.8（1280px）、§11.9.9（入口流程）、§11.9.10（A50／A51 階層）、§11.9.11（三態＋區塊標記）、§11.11（驗收清單 J-1～J-18）。缺口見 §二。
3. 〔事〕**現有授權不足以做任何 💼 施工**：新 layout／renderer（`ui_v3/pages/ast.py`）、改 registry、新 VM／adapter、測試修改、資料接線皆未授權（DEC-2026-11-09-02／-03／-04 的「不授權」欄明列 Python／Streamlit 施工）。
4. 〔推〕**今天沒有零 Gate 的可見切片。** 可不經新 Gate 做的只有 docs-only 補線框缺口（客戶任務單即可，本稿即屬此類的盤點部分）。
5. 〔推〕**最小施工 Gate 是一張兩問的裁示卡**（§五），仿 🔍 的 `DEC-2026-11-14-04`；回覆「核准」前不動工。

---

## 二、線框缺口（P0：docs-only 可補，不需新 Gate）

| # | 缺口 | 現況（出處） | 補法 |
|---|---|---|---|
| G-A | A60「來源、略過、缺項證據」展開的內部版面與欄位未畫 | 82 §11.6、§11.7 只寫「預設收合、不含代碼／例外／路徑」 | 補 A60 內部版面（不新增狀態詞） |
| G-B | 390px 首屏元素**逐元素點數表**未做 | 首屏上限＝頁級 chip＋核心數字 ≤5（82 §0.1、§11.2；DEC-2026-11-03-11）；Missing 佔位仍計入為保守讀法，**待逐元素點數**；390px 與首屏高度皆設計值、未量測（82 §11.9.7、§11.10 限制 8、9） | 三情境各一張點數表；A10 入口與原因句不計 chip |
| G-C | 缺值三態有兩種讀法未分開 | ① 符號字樣 `◇ 資料未備`／`⬜ 無法判定`／`⛔ 取數失敗`；② 來源三情境（完整、部分缺漏、完全未取得：a 未選 Active、b 讀取失敗、c 完整但無列）（82 §11.7、§11.9.11；`shared/ui_semantics/rules.py`） | 補矩陣：符號 × (a)(b) × 各區塊；**不新增狀態詞、reason_code、映射**（DEC-2026-11-09-04 UI-1） |
| G-D | (a)(b) 標記後綴形式待裁；(b)「計算口徑未核准」放哪未定 | 82 §11.9.7：A10 原因句承載，A60 不得暗示已承載 | 列選項，客戶裁示（見 §五） |
| G-E | `AssetsLoadResult`／`AllocationEvidence` 欄位到各情境的對映未寫 | `holding.kind` 只存在中介型別 `HoldingOutcome`，不在 `AssetsLoadResult` 上；結果只有 `problems`、`holding_failure_code`、`evidence.holdings` 列數（82 §11.9.9 自標 NOT VERIFIED） | 補對映表；J-1 入口判定**不得升格為規則** |
| G-F | **市值基準時使用者看不到 A50**（與 82 §11.3「FX 無法驗證，原幣資料仍可查看」衝突） | 〔事〕`ui_v3/adapters/assets_source.py`：市值基準一律 `blocked`、不讀持倉、不呼叫生產者；`FX_OBS_DATE_RULE_VERIFIED = False` | 補處置選項；**不得為此開 FX 閘** |
| G-G | `AllocationEvidence.categories[*].value_twd` 存在，但 T1＝B 禁止顯示類別金額 | `DEC-2026-11-09-02` | VM 設計時不得帶出類別金額（寫進驗收條件） |

---

## 三、已核准條款（只列與 390px 首屏／Evidence 展開／缺值三態直接相關者；二手，以 DECISIONS／82 為準）

| 類別 | 條款摘要 | 出處 |
|---|---|---|
| 第一屏 | 主圖在前、四項摘要在後；資料不足明確顯示 Missing，不填假數據 | DEC-2026-11-04-01；82 §0.1 |
| 第一屏 | U3：A00 單一正式狀態容器、A10 簡潔 SPEC、A20 四格保留，不得加 chip 突破 5 | DEC-2026-11-04-02；82 §9.7、§9.8 |
| 第一屏／三態 | U2：主圖僅在分母、目標、基準合法且完整時才畫，否則顯示資料狀態卡；缺 FX 採方案 A（不顯示看似完整的 100%） | 同上 |
| 第一屏／三態 | T1＝B：不顯示類別淨投資金額小計與總合計；N＝C：不顯示新定義的涵蓋 N／M | DEC-2026-11-09-02 |
| 第一屏／三態 | S1-1＝B：A10 原位，缺口徑時為精簡降級卡；無可查看持倉時隱藏入口或顯示合法來源狀態 | DEC-2026-11-09-03 |
| Evidence | U4：A50／A51 完整持倉與逐檔 NAV／配息可展開；A60 診斷預設收合、不出現環境變數／例外／代碼／路徑 | 82 §9.7、§11.2；PROJECT_RULES §13.5 |
| Evidence | S1-2：手機 A50 預設收合、桌面有可靠證據時預設展開；「展開／定位／rerun 是否重讀 Active Sheet」未驗，列為 Stage 3 技術 Gate | DEC-2026-11-09-03 |
| Evidence | 禁巢狀 expander、禁 Top N；A51 桌面「非巢狀列內詳情」為優先設計候選，不批准特定元件 | DEC-2026-10-30-02；DEC-2026-11-09-04 UI-3 |
| 三態 | UI-1：A10／A20 區分「原始資料缺漏／取數失敗」與「口徑未核准故不提供結果」，只能用已核准字樣 | DEC-2026-11-09-04 |
| 三態 | 已核准狀態字樣僅 `◇ 資料未備`、`⬜ 無法判定`、`⛔ 取數失敗`、`⛔ 尚未設定`、`⬜ 未設定` | `shared/ui_semantics/rules.py` |
| 全部 | 使用者面一律稱「淨投資金額」，不稱成本、市值、總資產、本金 | DEC-2026-11-09-01 |

---

## 四、可重用的 `ui_v3` 契約與 fixture（含限制）

| 項目 | 事實 |
|---|---|
| 載入端 | `ui_v3/adapters/assets_source.py::load(state, secret_values, *, reads=None, producer=None)` → `AssetsLoadResult`；`chart_claim` 建構時強制為 `withheld_pending_approval` |
| 生產者 | `services/v2_domain/allocation_evidence.py::build_allocation_evidence(...)` → `AllocationEvidence`（欄位名皆為**內部候選，非核准詞彙**） |
| 既有 fixture | **不夠驅動 💼**：`ui_v3/fixtures/scenarios.py` 的 11 個情境全是通用元件 VM，無 💼 專屬形狀；且 `test_ui_v3_fixtures_are_fake_guard` 禁止非測試檔 import fixtures，Preview 結構上看不到 fake 資料 |
| 最接近可用 | `tests/ui_v3/assets_source_support.py`（測試端建構器，真形狀 `build_alo_tables`；🌍 `market_stubs.py` 的同款做法） |
| 情境覆蓋 | 正常／部分 skipped／user_setting 未設或失敗：support 可組；無 Active／全表失敗：可用替身組但無現成情境包；零持倉／NAV 缺或延遲／FX 不可用／配息日期未確認／身份衝突：**沒有現成情境包** |
| 缺口 | 無 💼 頁級 VM、無 evidence→VM 映射、無 💼 字樣表（A00 來源狀態字樣、入口文案、原因句屬 T5／G-5 待裁） |

---

## 五、AI 總管推薦與一則請示

**AI 總管推薦（先講）：兩問都選 A（見下表），且 S-VM 之後不順勢自動進渲染切片。** 以上為作者推論，客戶可選任一，亦可逐項調整。

**P0（不需新 Gate，本批可做）**：補 §二 G-A～G-G 為一份 docs-only 線框補件。若客戶同意由總管接手，會另開一個 docs-only PR；**此項不是施工**。

**一張裁示卡，兩個問題**：

| # | 問題 | 說明 |
|---|---|---|
| Q1 | 是否核准「精修後 Stage 1 線框」（限 A00／A10／A20、A50／A60 展開、三態）為線框基準 | T6 欄位集合、G-1～G-5 **不升格**；390／1280 像素、首屏高度仍為設計值未量測 |
| Q2 | 是否授權 **S-VM 切片**：僅新增檔，無頁、無 registry、無 Streamlit、無資料接線 | 見下表 |

| 方案 | 內容 | 優點 | 缺點 | 風險 |
|---|---|---|---|---|
| A　Q1＋Q2 皆核准 | 線框成基準；施工 S-VM（純新增檔） | 最安全的第一刀；可自動驗；零執行期影響 | 使用者仍看不到 💼 頁；之後渲染切片需第二次授權 | 低；被誤讀為「💼 完成」須在驗收句防範 |
| B　只核准 Q1 | 先確立線框基準，不施工 | 把審核與施工分開 | 沒有可驗的程式進度 | 低 |
| C　皆暫緩 | 先裁 D2 與市值基準處置 | 不產生薄切片 | 💼 長期停在文件 | 低，但進度慢 |

**S-VM 預計新增檔（純新增，〔推〕未驗）**：`ui_v3/viewmodels/assets_page.py`、`ui_v3/adapters/assets_page.py`（`AssetsLoadResult`→VM 純函式，無 I/O、無 streamlit、不 import L2）、`tests/ui_v3/assets_page_support.py`、`tests/ui_v3/test_ui_v3_assets_page_viewmodel.py`、`tests/ui_v3/test_ui_v3_assets_page_adapter.py`。**不修改** `registry.py`、`app_preview.py`、`pages/`、`rules.py`、`assets_source.py`、`allocation_evidence.py`、任何既有守衛。

**S-VM 驗收條件（可自動驗）**：順序 A00→A10→A20→A30→A40→A50→A52→A60 且 A20 恆 4 格；首屏元素點數 ≤5；不得出現百分比、100%、金額合計、類別小計；Missing 永遠是 `None`＋原因、不轉 0；三情境各一且 (a)(b) 兩類原因不混；入口只在「有可用列」時存在，a／b 不出現入口、也不寫「持倉 0」；只用已核准字樣，其餘走暫時字樣表加 `data-pending-wording` 標記；市值基準照 `blocked` 降級、不偽造數字。

**不在 S-VM 內、需第二次授權**：`pages/ast.py`＋registry＋對應守衛測試改動＋AppTest＋Playwright 實測；390px 實機首屏、Evidence 展開、定位、焦點（部分屬 Stage 3）。**以 VM 切片宣稱「390px 通過」是不對的。**

**回滾**：純新增檔，`git revert` 單一 PR；registry 與 Preview 入口不動，執行期零影響。

---

## 六、驗證狀態與限制

- **作者親自抽查（2026-11-14，讀碼）**：`registry.py::IA_PAGES` 的 `ast` 為 `registered=False`／`wireframe_not_approved`；`assets_source.py` 市值基準一律 `blocked` 且不呼叫生產者；`FX_OBS_DATE_RULE_VERIFIED = False`；`ui_v3/pages` 與 `ui_v3/viewmodels` 無 💼 檔。其餘條款與缺口為盤點組單組讀碼，**未經第二組驗證**。
- 未跑任何 pytest；「測試現況為綠」NOT VERIFIED。
- 相依：BL-0545 BLOCKED（S-VM 只能是 fixture，每個畫面不得宣稱「真實資料」，N＝C 不得用 n／m／j）；D2 Pending（A51 的 NAV／幣別／取得時間欄位屬 T6，S-VM 不得固化欄位集合）；Formula Gate（A20 四格全 Missing，A30／A40 只有單行狀態，不出現「過期／正常」）。
- 本稿不構成任何動工授權；BL-0545、Q5、R-NAV-2／5、EXP-6 等其他 Gate 不因本稿解鎖。
