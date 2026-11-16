# 💼 我的資產 Stage 1 線框缺口最小補充（G-A～G-G）— 草稿

> **草稿，不具效力。補充 ≠ 新決策；不改 82 原文（僅新增 evidence）。** 不新增欄位、字樣、狀態詞、規則、入口判定；不開 FX 閘、不選方案。
> **授權**：客戶 2026-11-14 裁示（登記於 `DEC-2026-11-14-06`，同批落檔）：方案 A，核准精修後 Stage 1 線框為設計基準（A00／A10／A20、A50／A60、已核准缺值與展開方向）；G-A～G-G 保留；≠完整視覺驗收、≠Stage 3、≠production。
> **簡稱**：82＝`docs/v2/82_…proposal.md`；D01／D02＝`DEC-2026-11-04-01`／`-02`；D91～D94＝`DEC-2026-11-09-01`～`-04`；RULES＝`shared/ui_semantics/rules.py`；SRC＝`ui_v3/adapters/assets_source.py`；EV＝`services/v2_domain/allocation_evidence.py`；GAP＝`docs/evidence/assets_stage1_wireframe_gap_…_2026_11_14.md`。〔事〕可核對；〔推〕作者推論。
> **消歧**：82 以「(a)(b)」指兩件事——**來源子情境** S-a 未選 Active／S-b 讀取失敗／S-c 完整無列（§11.7）；**原因類別** R-a 資料缺漏或取數失敗／R-b 口徑未核准（§11.9.11、D94）。本稿分寫。

## G-A　A60「來源、略過、缺項證據」內部版面
- 預設收合；不含環境變數、例外、代碼、路徑、機密〔事〕82 §11.2、§11.7；PROJECT_RULES §13.5。
- 82 §11.6 A60 列所列來源為略過持倉列、略過分頁、金額欄解析錯誤、EV 的 `uncovered_*`〔事〕；82 未寫「僅限」，§11.7 情境三另有失敗分類人話，§11.9.11 R-a 例示含「缺淨值」〔事〕。依來源分組屬〔推〕。
- 被略過持倉不在 A50 表內、改由 A60 列出，不說成沒有持倉〔事〕82 §11.7、§11.9.7。
- R-a 證據可由 A60 按需查看；**不得暗示 A60 承載 R-b**〔事〕82 §11.9.7、§11.9.8。情境二 A00 有「一行指向」A60〔事〕82 §11.7；A60 內不得放 expander，由 J-12 全頁禁巢狀推得〔推〕。
**open**：欄位名與列內容、標題與指向句字樣、是否顯示件數、狀態詞（G-5）、排序——82 標〔待裁示〕，不補。略過字串可含試算表 ID／網址，上畫面前須另行處理〔事〕SRC (e)，處理 open。**PR #1248 ViewModel 暫行 `a60_field_set`** 只承載略過分頁／列件數、問題碼、R-a 原因，不含 `invest_twd_parse_errors`、`uncovered_*`（不得升格）。

## G-B　390px 首屏逐元素點數（設計值，未量測〔事〕82 §11.9.7、§11.10）
**預算**：頁級 chip＋核心數字 ≤5；保守讀法＝A00 容器 1＋四格 4＝5，不得再加 chip；A10 卡、SPEC、限制為文字非 chip〔事〕82 §0.1、§11.2、D01、D02 U3。入口為文字列、非 chip，**是否仍計入＝待 UI Review**〔事〕82 §11.9.9、J-2。元素依 82 §11.9.7：

| # | 元素 | 情境一 | 情境二 | 情境三（a/b/c） | 不計入版 | 計入版 |
|---|---|---|---|---|---|---|
| 1 | A00 單一狀態容器 | 有 | 有 | 有 | 1 | 1 |
| 2 | A10 `◇ 資料未備`＋原因句 | 1 句 | 兩短句（R-a、R-b） | 1 句（引用 A00） | 0 | 一：1；二：2（R-a、R-b 各 1）；三：1 |
| 3 | A10 SPEC 列、限制列 | 各 1 | 各 1 | 各 1 | 0 | 0（註 1） |
| 4 | A10「▸ 查看持倉明細」入口 | 有 | 有（有可用列才有） | **無** | 0 | 一、二：1；三：0 |
| 5 | A20 四格（`◇`＋極短標記） | 4 | 4 | 4（位置保留） | 4 | 4 |
| 6 | A30／A40 各一行 | 有 | 有 | §11.7 有、§11.9.7 未畫（註 2） | 0 | 0 |
| 7 | A50 收合列（三：狀態文字列）、A52、A60 | 有 | 有 | 有 | 0 | 0 |
| | **合計** | | | | **5／5／5** | **7／8／6** |

- 〔事〕「不計入」＝82 §11.2 算式，均為 5；「計入」均 >5〔推〕。**並列不選。**
- 註 1：82 稱 SPEC／限制為文字（§11.2）；若也計入，各情境再 +2〔推〕。註 2：A30／A40 是否在首屏取決於未量測高度〔事〕82 §11.9.7，不入算式；二者差異屬 T7〔事〕。
- 情境二依 82 §11.9.7 兩類原因分兩短句並列，忠實點數＝1＋2＋1＋4＝8（PR #1248 `first_screen_element_count` 亦 8）；「7」僅為兩短句合計一個的非 82 變體〔推〕。A20 格內標記視為附屬、不另計〔推〕。

## G-C　缺值矩陣（符號：`◇ 資料未備`／`⬜ 無法判定`／`⛔ 取數失敗`，RULES 已核准；文字句非已核准）
來源：82 §11.7、§11.9.7、§11.9.9、§11.9.11。「規」＝82／DEC 已規定；「開」＝未規定。

| 區塊 | 一 完整 | 二 部分缺漏 | 三 S-a 未選 Active | 三 S-b 讀取失敗 | 三 S-c 完整無列 |
|---|---|---|---|---|---|
| A00 | 規：描述性「已讀完」＋時點；符號開 | 規：略過件數為事實；符號開 | 規：`⬜`＋「尚未選定…」；句子非 RULES 字樣 | 規：`⛔ 取數失敗`＋人話分類；分類字樣開 | 規：證據成立才寫「沒有有效持倉列」，否則 `⬜ 無法判定`；判準開 |
| A10 | 規：`◇`＋R-b 候選句 | 規：`◇`＋R-a、R-b 兩短句 | 規：`◇`，原因引用 A00；無入口 | 同左 | `◇`規；R-a／R-b 歸類**開** |
| A20 | 規：四格 `◇`；R-b 為「候選示意」，判準開 | 規：逐格各標 R-a 或 R-b；**逐格判準開** | 規：四格 `◇`＋R-a | 同左 | 四格 `◇` 規；標記歸類開 |
| A30／A40 | 規：一行狀態、不顯示結果；符號字樣開 | 同左 | 規：原因引用 A00 | 同左 | 同左 |
| A50／A51 | 規：收合列標題帶狀態；字樣開 | 規：缺淨值欄 `◇`＋原因；幣別不一致 `⬜ 無法判定`（§11.3）；原因字樣開 | 規：一列狀態文字，不寫「持倉 0」 | 同左 | 同左；僅證據成立才寫「沒有有效持倉列」 |
| A60 | 規：預設收合；符號開 | 同左＋A00 一行指向 | 同左 | 規：失敗分類人話 | 同左 |

「規」為 82 線框設計候選；卡內文案仍〔待裁示〕（82 §11.9.11）。**S-c**：82 線框情境三整段標 (a)，但其原因句「來源未取得」不適用 S-c〔推〕（來源已讀完），故 R-a／R-b 歸類仍開；PR #1248 ViewModel 暫歸 (a)（`complete_no_rows_is_category_a`，暫行）〔事〕。**另 open**：設定讀取失敗或不可用（`PROBLEM_SETTINGS_*`）的呈現 82 未規定（見 G-E）。

## G-D　(a)(b) 標記後綴形式與 R-b 放置位置（只列 82 已有選項，不選）
- **後綴形式**：①括號字母極短標記附於 A20 每格（`◇ 資料未備(b)`）〔事〕82 §11.9.7、§11.9.8「後綴形式待裁示」；②A10 以兩短句並列、不加字母〔事〕82 §11.9.7 情境二；③方案 A（各區塊完整重複原因）、B（A10 保留主因＋入口，A20 壓縮；「優先評估」，**未選定**，D94）；C（合併 A10／A20）違反 U3，不採〔事〕82 §11.9.11。
- **R-b 放置**：目前只由 A10 原因句承載，A60 不得暗示；待 T5／G-5〔事〕82 §11.9.7、§11.9.8。
- **open**：選哪一式；字母標記是否算「新增狀態詞／映射」（D94 UI-1 禁止）〔推〕。

## G-E　`AssetsLoadResult` 與 `evidence` 對映
`AssetsLoadResult`〔事〕SRC：`status`（`evaluated`／`blocked`）、`blocked_reason`、`evidence`、`problems`（`no_active_source`／`holding_read_failed`／`settings_read_failed`／`settings_value_unusable`）、`settings_status`、`holding_failure_code`、`schema_version`、`chart_claim`（恆 `withheld_pending_approval`）。`evidence`（EV）頂層〔事〕：`source`（`active_source`、`read_errors`、`skipped_tabs`、`omitted_rows`）、`holdings`、`categories`、`denominator`、`coverage`、`source_coverage` 等。

| 情境 | 可讀到的欄位（候選對映，**暫行，不得升格**〔事〕D94 UI-2；J-1） |
|---|---|
| 一 完整 | `evaluated`；`problems` 無 holding 類；`evidence.source_coverage`＝complete；`evidence.holdings` ≥1 列 |
| 二 部分缺漏 | `evaluated`；`evidence.source` 有略過分頁／列，或 holdings 內 `nav_state`／`is_unclassified` 等異常；≥1 列 |
| 三 S-a | `problems` 含 `no_active_source`；`evidence.source.active_source`＝`none`〔事〕SRC `holding_stage_inputs` |
| 三 S-b | `problems` 含 `holding_read_failed`；`holding_failure_code`（白名單 code）；`active_source`＝`selected` |
| 三 S-c | 無 holding 類 problems；`source_coverage`＝complete；holdings 0 列〔推〕（須排除 `holding_table_unreadable`） |

- **重點**：`holding.kind` 只在中介型別 `HoldingOutcome`，**不在 `AssetsLoadResult` 上**〔事〕SRC。82 §11.9.9 入口條件 1 引用它；VM 只能經 `problems`、`holding_failure_code`、`evidence.holdings` 列數推得〔推〕，NOT VERIFIED。
- 「可用持倉列」門檻客戶未定義〔事〕D93、D94；本表不定義。
- PR #1248 VM 暫行較嚴〔事〕：partial 只限 coverage=incomplete＋有略過證據＋有列；complete 需兩項略過證據皆已提供且為 0，否則降 undetermined；A00 的 not_selected 等不帶已核准符號（走暫時字樣）。不一致處以 VM 登記項為準，不得升格。
- **open**：settings 類 `problems` 的呈現；`settings_status` 不得當真相〔事〕SRC (d)。

## G-F　市值基準 blocked 與 82 §11.3 的方向差異
- 〔事〕市值基準一律回 `status=blocked`，**不讀持倉、不呼叫生產者**（SRC `load`／`evaluate`）。`FX_OBS_DATE_RULE_VERIFIED = False`（`market_indicator.py`）。
- 〔事〕82 §11.3：FX 閘關閉時「不換算不合計，但可查看有可靠證據的原始資料」；§11.7／§11.9.11 三態以持倉讀取定義，**無 blocked 對映**〔推：單組字面搜尋，未經第二組驗證〕。
- 〔推〕頁若只消費 `AssetsLoadResult`，市值基準下無持倉可展開，與 §11.3 方向不一致，易被讀成「沒有持倉」（D94 UI-1）。PR #1248 VM 暫行：blocked 時 A00 借 `⬜`、A10／A20 歸 R-b（`market_basis_blocked_symbol_and_category`，不得升格）〔事〕。
- **處置選項（〔推〕，不選）**：
  1. 維持降級＋明示原因（已核准符號＋說明句、無入口）。風險：有持倉卻看不到。
  2. adapter 在 blocked 時改讀持倉以保留入口。風險：需改 `assets_source.py`，超出 `DEC-2026-11-14-06` 授權的 5 個新增檔。
  3. 列為後續 Gate。風險：基準留一個無畫面情境。

## G-G　不得帶出類別金額（寫入 S-VM 驗收條件）
- 〔事〕EV `CategoryEvidence.value_twd` 存在；T1＝B：不顯示類別小計與總合計，不新增占比或分母（D92；82 §11.8）。
- **驗收條件（VM 輸出含序列化後）**：不含 `categories[*].value_twd`、`denominator.value_twd`、`coverage.covered_value_twd`、`share_of_covered_pct` 及百分比、100%〔推：前三者視為「合計」、`share_*` 視為「占比」，客戶可推翻〕；測試以哨兵值斷言皆不出現。
- 指向：PR #1248 已含哨兵測試〔事〕——`tests/ui_v3/test_ui_v3_assets_page_adapter.py`（`categories[*].value_twd` 存取追蹤＋哨兵值）與 `tests/ui_v3/assets_page_support.py`（`SENTINEL_*`）；是否通過以 exact-head CI 為準，NOT VERIFIED。
- 同禁、併入 T6 open：`coverage.uncovered_holdings[*].own_value_twd`、`categories[*]` 內逐檔項（`excluded_valued_holdings` 現僅 (policy_id, fund_code)〔事〕EV）、逐檔 `value_twd`／`cost_twd` 可否帶出＝T6〔事〕82 §11.8。

## 本補充沒有解決的事（Remaining open）
A60 欄位／字樣（G-A）；入口、原因句計入與否，SPEC／限制若也計入再 +2（G-B）；全部畫面句子（T5／G-5）、S-c 歸類、A20 逐格判準（G-C）；後綴形式與 R-b 位置，字母標記是否算新增狀態詞（G-D）；「可用持倉列」門檻、設定類問題畫面（G-E）；市值基準 blocked 處置（G-F）；逐檔金額 T6；A30／A40 去留 T7。以上均不解除 G-1～G-5、T2～T10、D7、BL-0545；Stage 3 技術 Gate（展開／定位／rerun 是否重讀）未驗。

## 驗證狀態
單組、僅讀文件與原始碼（含 PR #1248 五檔）；**未量測像素、未跑測試**；客戶裁示為要點轉述；2026-11-14 裁示登記於 `DEC-2026-11-14-06`。點數為設計值；全稱句均〔推〕、未經第二組驗證。**待獨立 QA。**

---

## 2026-11-16 三張最小裁示卡（待客戶正式裁示）與第一個隔離式 Preview 施工授權包候選

> **狀態：三張卡全部【待客戶正式裁示】。** 下列 A／B／C 的「推薦」只是總管讀法，**可被客戶推翻**；不是已核准、不授權 renderer、不授權任何 `ui_v3/pages/`、registry、`app_preview` 或資料接線的施工。本小節不新增 DEC、不改 82 原文。表內〔事〕＝由文件／原始碼讀到，〔推〕＝本稿判讀（單組、未經第二組驗證）。符號名引自 `ui_v3/viewmodels/assets_page.py` 與 `ui_v3/adapters/assets_page.py`，不寫行號。

### 卡 1　390px 首屏元素名額口徑

| 項目 | 狀態 |
|---|---|
| frozen 44 首屏預算 ≤5、Missing 不隱藏也不當 0、A20 固定四格、兩類原因不得混同（UI-1）、不得新增 chip／狀態詞 | 【已核准】`DEC-2026-11-03-11`、`DEC-2026-11-09-04`（UI-1） |
| A10 入口、原因句、SPEC、限制是否計入名額 | 【待客戶正式裁示】 |
| 實際 390px 首屏驗收 | 【NOT VERIFIED】（renderer 完成前不可能量測） |

設計值（〔事〕由既有 G-B 矩陣與 `first_screen_element_count` 推算，**非量測**），情境依序為 一 完整／二 部分缺漏／三 未取得或無列：

| 口徑 | 一／二／三 |
|---|---|
| 不計入（入口、原因句、SPEC、限制皆為文字） | 5／5／5 |
| 計入入口與原因句 | 7／8／6 |
| 再計入 SPEC 與限制（各 +2） | 9／10／8 |

| 方案 | 內容 | 風險／張力 |
|---|---|---|
| A | 明文裁定入口、原因句、SPEC、限制為文字、不計名額，並設密度上限（入口 ≤1 行、原因句 ≤2 短句且兩類不混、SPEC ≤1 行、限制 ≤1 行）；Preview 同時回報三種口徑 | 需客戶接受「文字不計名額」；密度上限數值為本稿提議【候選】 |
| B | 全部計入，超出者折疊 | 與 UI-1（兩類原因不得混同、Missing 不隱藏）有張力；`DEC-2026-11-03-11` 的先例只限 🌍〔推〕 |
| C | 不裁，只報告兩種點數 | 無法形成驗收條件 |

**推薦 A（總管讀法，可被客戶推翻）。** 附註：(1) VM 的 `POLICY_A10_TEXT_INCLUDED` 只計入 A10 入口與原因句，**不含 SPEC／限制**，不得稱為最保守口徑；(2) 不得為了湊數刪必要的風險說明。

### 卡 2　空持倉語意

| 項目 | 狀態 |
|---|---|
| 四類必須分開：來源未取得、取數失敗、來源完整但零有效列、已有資料但計算契約未核准 | 【分開本身已核准】`DEC-2026-11-09-04`（UI-1） |
| 來源完整零有效列歸原因類別 (a)／(b)／其他；「可用持倉列」門檻 | 【待客戶正式裁示】（客戶尚未定義門檻，見 `DEC-2026-11-09-04` 與本檔 G-D） |
| 下列 VM／adapter 現行判準 | 【候選·暫行·不得升格】，留待下一個契約 Decision Gate |

**消歧**：「原因類別 (a)」（`CATEGORY_SOURCE_DATA`，資料缺漏或取數失敗）≠「來源情境三 (a)」（`SRC_NOT_SELECTED`，未選 Active）。兩者不得混用。

**現行暫行判準（〔事〕讀 `ui_v3/adapters/assets_page.py::_resolve`、`_causes_for` 與 `ui_v3/viewmodels/assets_page.py` 的 `SRC_*` 常數）**：
- 問題碼 no_active → `SRC_NOT_SELECTED`；holding_read_failed → `SRC_READ_FAILED`（優先於矛盾的 coverage）。
- 來源涵蓋為 complete：兩項略過證據（略過分頁、略過列）**皆已提供且件數為 0** 且有列 → `SRC_COMPLETE`；同條件但無列 → `SRC_COMPLETE_NO_ROWS`（暫歸原因類別 (a)、原因引用 A00）。
- 來源涵蓋為 complete 但任一略過證據未提供或件數 >0 → 降為 `SRC_UNDETERMINED`；有列時原因含類別 (b)，無列時只有類別 (a)。
- 來源涵蓋為 incomplete 且有列且有略過證據 → `SRC_PARTIAL`；未知值或 incomplete 無略過證據 → `SRC_UNDETERMINED`。
- 進入 NO_ROWS 狀態（未選、失敗、完整無列、未讀）一律清空列；市值基準 blocked → `SRC_NOT_READ`，列為空。
- 入口 `provisional_holding_entry_available`：額外排除未選／失敗／blocked；`SRC_UNDETERMINED` 但有列仍出現入口。

**反例／邊界（〔推〕，單組閱讀，未實跑）**：

| # | 情境 | 影響 |
|---|---|---|
| 1 | 略過證據 >0 且 coverage=complete、且無列 | 降為 `SRC_UNDETERMINED`，不會被寫成「沒有有效持倉列」；使用者看不到「完整讀完但真的是零列」，與 82 §11.7 情境三 (c) 的可達性有落差 |
| 2 | 略過證據未提供（status 非 provided）卻 coverage=complete | 同上降級；真實來源若永遠不提供略過證據，`SRC_COMPLETE`／`SRC_COMPLETE_NO_ROWS` 永遠無法出現 |
| 3 | 設定讀取失敗（settings 類 problems） | `_resolve` 不看 `settings_status`（本檔 G-D open）；若 coverage 仍為 complete，來源狀態不反映設定失敗，呈現方式未定 |
| 4 | 行只含金額欄位 | `FORBIDDEN_ROW_FIELDS`（`value_twd`、`cost_twd`、`cost_orig_ccy`、`share_of_covered_pct`、`weight_ratio`）擋下；若 `row_fields` 全是禁用欄位會 `ValueError`，列「有」但可顯示欄位為零，「可用持倉列」是否成立未定 |
| 5 | 市值基準 blocked | `rows` 恆空、`SRC_NOT_READ`，與「有持倉但看不到」無法區分（見卡 3） |
| 6 | 有 no_active／holding_read_failed 問題碼 | 提前回傳，**略過持倉列形狀驗證**（`early_return_skips_row_and_coverage_validation`，已知落差） |

| 方案 | 內容 |
|---|---|
| A | Preview 沿用暫歸原因類別 (a)，並標「暫行」 |
| B | 不歸類，只顯示 A00 |
| C | 歸原因類別 (b) |

**推薦 A，僅限 Preview（總管讀法，可被客戶推翻）。** A50 入口判定維持【候選】（`DEC-2026-11-09-04` UI-2）；無可用列時**不顯示**導向空內容的入口。

### 卡 3　FX blocked 下的原幣呈現

〔事〕載入端在市值基準下一律 blocked、**不讀持倉**；`FX_OBS_DATE_RULE_VERIFIED = False`；現行 VM／adapter 結構無法承載原幣事實（本檔 G-F 未決）。82 §11.3 的原幣事實**有證據來源，尚待實跑及獨立 QA**，目前不是「已驗證的原幣事實」。

| 方案 | 內容 | 風險 |
|---|---|---|
| A | 兩組完全分離的 fake fixture。成本基準 fixture：`ccy`、`units_shares`，標「假資料／使用者填寫（模擬）」，不換算、不合計、不給配置百分比。真實 blocked：維持 blocked、不讀持倉、不顯示原幣 | fixture 不代表真實資料路徑；仍屬【待客戶正式裁示】 |
| B | 擴 adapter／VM，使 blocked 也讀持倉 | 需改 #1248 已合併檔，須新授權，且涉淨值門檻 |
| C | 列後續 Gate | 本基準留一個無畫面情境 |

**推薦 A（總管讀法，可被客戶推翻）。**

### 第一個隔離式 Preview 施工授權包候選

> **本節不構成授權。** 以下是供客戶「一次核准」的候選清單，核准前一切為【Pending】。**前置：卡 1 的名額口徑須先裁。**

| 項目 | 狀態 |
|---|---|
| 新增 `ui_v3/pages/assets.py`（唯一 renderer） | 【候選】 |
| `ui_v3/shell/registry.py` 的 ast 頁由未啟用改啟用 | 【候選】 |
| 最小 `app_preview` 接線 | 【候選】 |
| fixture 位置與 fake 標示方式 | 【候選】 |
| 場景切換器是否屬新增正式 UI 元件 | 【Pending】找不到依據，需客戶判定 |
| 範圍僅 A00、A10、A20；A30–A60 不做 | 【候選】 |
| A10 入口無合法目標時，不得做可點擊的空內容假入口 | 【候選】 |
| 字樣只用 `shared/ui_semantics/rules.py` 已核准鍵與 `ASSETS_PENDING_WORDING`（顯示為「暫行」） | 【候選】 |
| 不碰 services／公式／FX／真實資料 | 【候選】 |
| 驗收：390×844、768、1280 視覺與操作；AppTest／Playwright；獨立 QA；exact-head CI。fixture 通過不等同 Cloud／真機 | 【候選】驗收條件 |

四個最低測試情境【候選】：(1) TWD＋USD 持倉；(2) 來源成功但零有效持倉列；(3) FX Gate blocked；(4) NAV／配息／1Y 含息局部 Missing。

**驗證狀態**：單組、僅讀文件與原始碼；未量測像素、未跑測試；全稱句均〔推〕。
