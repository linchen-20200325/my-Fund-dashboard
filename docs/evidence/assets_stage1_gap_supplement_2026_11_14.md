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
