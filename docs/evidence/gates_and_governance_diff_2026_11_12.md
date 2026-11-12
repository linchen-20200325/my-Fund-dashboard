# 治理文件與安全差異整理（79／80／81／82 權威用語、BL-0532 正式模式殘餘掃描、G1～G13 狀態）

> **研究證據（唯讀整理）；非客戶裁示、非授權施工；單組作者，尚待非作者 QA。** 基準：main `d82a711d3bb7f4939952bdebae1441e99a8704f5`（#1225 merge；本機與 origin/main 同步）；整理日 2026-11-12（Asia/Taipei）。
> 授權來源：客戶 2026-11-12 本批授權單（任務 3 與同批裁示 (2)～(6)；**成稿時未另立 DEC；整合入庫時已由 `DEC-2026-11-12-02` 補登要點，repo 內仍無逐字存檔**，本檔所引「客戶本批裁示 (n)」均為總管轉述，不得當逐字稿）。`DEC-2026-11-12-01` 僅作優先序與「不授權」邊界引用。
> 本檔**不修改**任何程式、測試、workflow、`CLAUDE.md`、`PROJECT_RULES.md`、`docs/DECISIONS.md`、`docs/v2/**`；對 `HANDOFF`／`BACKLOG` 的修改建議另存（`old→new` 精確文字），**不在本檔內執行**。文中「推薦」一律是**總管讀法，可被客戶推翻**。
> 路徑一律寫「檔案::符號」，不寫行號。未寫 secret、NAS 位址、Sheet ID 值。缺值／無法判定一律寫 ⬜（UNAVAILABLE），不得讀成 0 或正常。
> 「單組 grep」＝全稱句限度：所有「0 命中／只有 N 處」皆為本組字面搜尋，**不含別名、動態組字**，**未經第二組驗證**。測試是否綠**只能由 CI 驗**（本機沒有 pytest 可用於本 repo 的依賴齊全環境；本組未跑任何 pytest）。

---

## 0. 結論先行

| # | 結論 | 狀態 |
|---|---|---|
| 1 | **用語不一致只有一處需要改**：`docs/HANDOFF.md` §0 第 4 點把 82 與 79／80／81 並列為「正式 SSOT／規格」。`PROJECT_RULES.md` 對 79／80／81／82 的措辭與各檔頭、相關 DEC **彼此一致**，不需改（也不在本批授權內）。建議的最小修改為 E1（單行替換，守衛相容性已模擬；整合者已於本 PR 套用，old→new 見本 PR diff）。 | 已查證（單組） |
| 2 | **BL-0532 在正式模式的可見殘餘＝1 組（共 3 個渲染點）＋1 項無法判定**：確認殘餘＝`ui_v2/mkt/market_section.py::_STATUS_TEXT` 的「資料未備」一列（市場趨勢區段不經 `symbols.apply`）；無法判定＝`ui_v2/mkt/chart.py::TEXT_EMPTY`（依 L2 契約推論正常資料不可達，未跑 AppTest）。其餘 `ui_v2` 命中（111 行）經渲染期改寫、僅示範模式、僅註解／docstring 或屬匯出檔。`ui_v3` 0 命中。 | 靜態追蹤＋純函式實算；**畫面層 NOT RUN** |
| 3 | **`TEXT_EMPTY` 暫維持原樣、不一次改寫 110 行**：本檔只登記，未改任何 `.py`。若客戶日後要動，最小批僅限第 2 節 (i) 類（1 組、改 1 個常數＋4 行測試斷言級別），不含 `TEXT_EMPTY`。 | 依客戶本批裁示 (2) |
| 4 | **G1～G13 分類**：(A) 已有明確裁示＝G2、G12；(C) 必須停止等待客戶＝其餘 11 個（其中 G6、G10、G11 另含有限的 (B) 唯讀研究）；(D) 可供下一批實施的候選＝**只有 2 項，且都不屬於 FX／D2／身份／金融公式／cutover**（D-1 HANDOFF 措辭修正；D-2 BL-0532 (i) 類最小批，仍須客戶開實作批）。 | 單組分類，可被客戶推翻 |
| 5 | **BL-0546 登記保留**（BACKLOG 該列存在、內容與證據檔 §1.8／§5 G13 相符，不動）。**BL-0545 仍是唯一全域 NEXT**；`BACKLOG` 該列狀態欄寫 `open`、`HANDOFF` 寫「暫不提供輸入」，兩處都**沒有「BLOCKED」一詞**（單組 grep）；客戶說 BLOCKED，故建議在文件補註（選配 E2／E4）。 | 已查證 |

---

## 1. 子任務 3a：79／80／81／82 權威用語核查

### 1.1 核查表

證據取法：各檔頭與結尾（逐字）、`DEC-2026-11-02-03`／`-05`／`-07`、`DEC-2026-11-03-01`、`DEC-2026-11-04-01`／`-02`、`DEC-2026-11-09-02`～`-04`、BACKLOG BL-0531／0533／0535／0536／0540／0542、`PROJECT_RULES.md` 0.4 與 13.x、`docs/HANDOFF.md`。

| 文件 | 現行地位（依據與原文位置） | HANDOFF 現行寫法 | 一致？ | 建議用語 |
|---|---|---|---|---|
| **79** `final_ui_contract_freeze` | **New UI2 正式 input contract（正式 implementation input）**。檔頭首行標題「已裁示（`DEC-2026-11-02-07`）；New UI2 input contract（正式 implementation input）」；檔頭「2026-11-02 裁示狀態」：「自此本檔的語意規格是 New UI2 input contract」。`DEC-2026-11-02-03` 決策內容 (5)：「Final UI Contract 的語意規格作為 New UI2 的 input contract」。檔頭**位階**：不凌駕 `CLAUDE.md`、`PROJECT_RULES.md`、frozen 44、67、75 與正式 DEC。**全檔沒有任何一句宣告 79 是 frozen**；`PROJECT_RULES.md` 0.4 末的「上位與規格文件」清單（約 :71）與凍結 SSOT 只列 44，**不含 79**。 | §0 第 4 點：「該批正式 SSOT／規格（frozen 44、子法 1＋57、79／80／81／82）」——79 與 44 並列於同一括號，未區分 frozen 與 input contract | **否（有歧義）** | 「New UI2 正式 input contract（不等同 frozen 44）」 |
| **80** `new_ui2_architecture_proposal` | **正式 input contract；其中 architecture（第 1、2 節）、Reuse Matrix（第 3 節）、migration boundary（第 8 節）已凍結**，五頁 wireframe（第 7 節）為 implementation input，各頁最終呈現依 NG-5／UI-12 由 New UI2 各頁 wireframe 重新核准。依據：`DEC-2026-11-02-05` 決策內容「凍結」段；80 檔頭「2026-11-02 裁示狀態」；`DEC-2026-11-04-01` 影響範圍列「`docs/v2/80` 架構區（第 1、2、3、8 節）」；`PROJECT_RULES.md` 13.2「2026-11-02 指標」（約 :817）「architecture、Reuse Matrix、migration boundary 凍結（`docs/v2/80`）」。⚠️ **80 的標題行寫「已裁示並凍結」（全標題未限定範圍）**，與上列「只凍結三塊」並存；屬既有措辭，本批不改。 | 同上（與 79／81／82 並列） | **否（有歧義）** | 「New UI2 正式 input contract（不等同 frozen 44）；architecture／Reuse Matrix／migration boundary 依 `DEC-2026-11-02-05` 已凍結」 |
| **81** `new_ui2_wireframe_01_market` | **🌍 已裁示線框（`DEC-2026-11-03-01`：Q1 A、Q2-a／b／c A、Q3 A、Q4 A、Q5 B＋六項已核准方向）；「核准文字線框不是 production 渲染授權」**（81 檔頭「狀態」逐字）。後續字樣與公式另有 `DEC-2026-11-03-03`／`-04`／`-07`／`-09`／`-11` 等；`PROJECT_RULES.md` 0.4（約 :52）：「`docs/v2/81`（已裁示線框；字樣＝`shared/ui_semantics/rules.py::APPROVED_WORDING`）」。81 檔頭另有一句「自獨立稽核通過後才為 🌍 `ui_v3` 實作的 implementation input；獨立稽核本批尚未完成」——這是 **2026-11-03 當日**的句子，之後是否補完 **NOT VERIFIED**（本組未查；後續批已據此實作並合併，見 BL-0536 列）。 | 同上（並列於「正式 SSOT／規格」） | **部分**（未說錯，但未標範圍） | 「🌍 已核准線框（範圍以其檔頭與 `DEC-2026-11-03-01` 為準；非 production 渲染授權）」 |
| **82** `new_ui2_assets_ui_data_evidence_proposal` | **部分核准草案，不是現行規格**。82 檔頭「定位」：「ChatGPT 產品／資料契約初稿……**非已核准 wireframe、非公式或資料語意裁示、非程式實作授權**」。已核准僅限：§0.1 版面順序（`DEC-2026-11-04-01`：主圖在前、四項摘要在後、資料不足明確 Missing，**僅 UI 方向**）；U1～U5 UI 設計＋缺 FX 方案 A（`DEC-2026-11-04-02`，**僅 UI 設計**）；Stage 1 線框分階段審查與 T1＝B／N＝C／UI-1～3（`DEC-2026-11-09-02`～`-04`，**非最終線框、非 UI 施工授權**）。BL-0542 G-1～G-5、82 Q1～Q15 其餘仍待裁。`PROJECT_RULES.md` 0.4（約 :53）：「`docs/v2/82`＝U1～U5 UI 設計已核准（`DEC-2026-11-04-02`）、其餘仍待裁示的草案＋獨立稽核核實結果，不是現行規格（BL-0542）」。 | §0 第 4 點與 79／80／81 並列為「正式 SSOT／規格」（**這是唯一把草案升格的句子**）。§3 BL-0542 列與 §3A 的措辭則**正確**（「UI 設計部分核准，資料／配息／整頁接線 Gate 未全授權」）。 | **否（升格錯誤）** | 「部分核准草案、非現行規格（僅 `DEC-2026-11-04-01`／`-02`、`DEC-2026-11-09-02`～`-04` 所列 UI 設計／顯示方向已核准）」 |

### 1.2 其他位置的同型用語（只登記，本批不改）

| 位置 | 原文 | 與客戶本批裁示 (3) 的關係 | 處置 |
|---|---|---|---|
| `docs/DECISIONS.md` `DEC-2026-11-09-05`「既有契約繼續有效」列、`DEC-2026-11-09-06` ⑤ | 「frozen 44／79／80 不改行為與五頁 IA」 | 把 79 寫進 frozen 群；DECISIONS 為追加式、不改歷史 | 只登記；引用時以 79／80 檔頭＋`DEC-2026-11-02-05` 為準 |
| `docs/DECISIONS.md` `DEC-2026-11-04-02` 不授權事項列 | 「不改 frozen 44／79、五頁 IA」 | 同上 | 只登記 |
| `docs/v2/82` 檔頭、§5 稽核步驟處 | 「此檔不取代 frozen `44`、`79`、`80`、`73`、`74`」「與 frozen 44、79、73、74……逐項比對」 | 82 自己的措辭把 79 當 frozen | 只登記；`docs/BACKLOG.md` BL-0542 G-1 狀態 (d) **已預先登記此落差**（「82 第 5 節……稱 frozen，`PROJECT_RULES.md` 凍結清單約 :71 未列」） |
| `docs/v2/80` 標題行 | 「已裁示並凍結：`DEC-2026-11-02-05`」 | 全標題未限定凍結範圍 | 只登記 |
| `docs/evidence/ui_data_contract_audit_2026_11_12.md` §5 G2 | 「79／80 維持『正式 input contract，不等同 frozen』」 | 與客戶裁示 (3) 一致，但對 80 的「三塊已凍結」未提 | 本檔 1.1 補足 |
| `PROJECT_RULES.md` | 0.4 對 81、82 的措辭、13.2 對 80 三塊凍結的措辭、凍結 SSOT 清單只列 44 | **全部一致** | **不提議修改**（`PROJECT_RULES.md` 是否改，須另案；`CLAUDE.md` 依 BL-0538 不延伸授權，不碰） |

### 1.3 建議修改與守衛相容性

- **E1（必要，單行替換）**：`docs/HANDOFF.md` §0 第 4 點。新句把 44／子法 1＋57／79、80／81／82 分成四種地位。**行數不變**（81 行）。
- **E2（選配）**：§2 標題補「BLOCKED」註記。**E3（選配）**：§3A 證據檔段落補本檔索引。**E4／E5（選配，BACKLOG）**：BL-0545 加入快速索引 blocked 行；BL-0532 列尾加殘餘掃描指標。**成稿時另存為建議檔；整合者已於本 PR 套用 E1～E5，精確 old→new 見本 PR diff。**
- **守衛相容性（本組以純 Python 複刻 `tests/test_canonical_rule_consistency.py` 的判定，非跑 pytest）**：套用 E1＋E2＋E3 後的 HANDOFF 模擬結果：行數 81（上限 120）；未劃線「唯一下一接手點」恰 1 處且非並列編號；無 `PENDING`／`擬：`／`待客戶定字`；無 `~~`；無舊頁名行；§0 仍為 5 點。**真正的 pytest 結果 NOT RUN（待 CI）。**
- **不提議**：改 `PROJECT_RULES.md`、`CLAUDE.md`、`docs/v2/79`～`82`、`docs/DECISIONS.md`。

---

## 2. 子任務 3b：BL-0532 正式模式可見殘餘掃描（只掃描，不改）

### 2.1 範圍與方法

- **問題**：在**正式模式**（非示範模式）下，使用者實際可見的畫面文字裡，哪些路徑仍出現 `⬜ 資料未備`／`⬜ 資料未取得` 而非 `◇ 資料未備`？
- **「正式模式」的限度**：指 `ui_v2` 各頁 `render(load_live=…)` 的 live 分支（`ui_v2/app_*_live.py`）。**production 入口目前仍是 Old UI**（`app.py`，Streamlit Cloud 入口設定 repo 內查不到＝NOT VERIFIED）；`ui_v2` 正式模式只在 Preview 入口；`ui_v3` 是 New UI2。故本節的「可見」＝**在 Preview 的 live 分支**。
- **方法（四步）**：
  1. `git grep` 字面命中 `ui_v2`＝**111 行**（與 BL-0532 2026-11-02 登記的「111 行」同數；`ui_v3` 0 行；`shared`／`services` 各有說明文字或 Old UI 用字串，見 2.3）。
  2. 以 AST 把每一行分類為 **註解／docstring／程式字串**：`ui_v2` 111 行＝註解 43＋docstring 42＋程式字串 26。26 行程式字串再拆為：17 行「餵進頁面模型的顯示常數」、5 行 `ui_v2/alo/logic.py` 的 GAP 註記散文、1 行 `startswith` 比對（非顯示）、1 行 `ui_v2/sections.py::MKT6_EMPTY_LINE`（比對用常數）、**2 行不經模型的字串**（`chart.py::TEXT_EMPTY`、`market_section.py::_STATUS_TEXT`）。
  3. **追蹤渲染路徑**：各頁 `page.py` 正式分支的順序是 `build_live_model → mark_fetch_failures → plain.plain_model → symbols.apply → …（sections／health／readonly 後續步驟）`。`symbols.apply` **只改它收到的 `model` 那份 dict**、**只換字面「⬜ 資料未備」**（不含「⬜ 資料未取得」）、**不動 `_` 開頭鍵底下的字串**、**不動 tuple 內字串**。
  4. **實算（純函式，不啟動 App、不連網、不寫檔）**：(a) 以 `PYTHONDONTWRITEBYTECODE=1 python3 -I` 直接 import 無 streamlit 依賴的模組，餵 `market_section`／`overview` 的非 ok domain，列出模型字串；(b) 借用測試檔的 `_live_models()`（以 stub 取代 `pytest` 只為了能 import 測試檔）組出 **88 個正式模型**（`alo` 16、`exp` 4、`hld` 34、`mkt` 34）＋ `set` 的 17 個情境，各跑 `plain.plain_model → symbols.apply`（再跑 `sections.mark_mkt6_fetch_failed → health.dedupe_failures → health.relabel_unconfigured → readonly.strip_write_controls`），掃**含 `_` 鍵與 tuple 內部**的殘餘字面。
- **負控**：本組自訂隨機串搜尋同一範圍＝0 命中（字串未列出）。

### 2.2 結論（三類）

#### (i) 確認殘餘（可見且未統一）：1 組、3 個渲染點

| ID | 位置（檔案::符號） | 字串 | 是否經 `symbols` 改寫 | 正式模式可見性 | 依據 | 被測試鎖定？ |
|---|---|---|---|---|---|---|
| **R1a** | `ui_v2/mkt/market_section.py::_STATUS_TEXT[資料未備]` → `status_text()` → `ui_v2/mkt/overview.py::_status_card`（`primary_card`／`secondary_card`／`rates_card` 於 domain 非 ok 時） | `⬜ 資料未備`（卡片 chip）；`狀態：⬜ 資料未備`（卡片 detail 的「來源」組） | **否**：這些卡由 `notes["market_view"]` 在 `ui_v2/mkt/page.py::_render_primary`／`_render_secondary`／`_render_rates_card` 渲染時才組，**不在** `symbols.apply(model)` 的那份 `model` 裡；`presentation.missing_card_html`／`chips_html` 逐字輸出 `text` | **可見**（Primary／Secondary／利率與信用任一序列為「資料未備」時；是否發生取決於當次取數） | 純函式實算：`primary_card`／`secondary_card`／`rates_card` 對資料未備 domain 回傳字串含 `⬜ 資料未備` 與 `狀態：⬜ 資料未備`（本機實跑 3 筆） | **是**：`tests/ui_v2/test_mkt_overview_logic.py`（`狀態：⬜ 資料未備` 1 行） |
| **R1b** | 同上 `_STATUS_TEXT` → `conclusion_model()` → `ui_v2/mkt/page.py::_conclusion_html`（「▸ 各項資料狀態」展開區的「市場結論」列） | `⬜ 資料未備`（每個資料未備 domain 一列） | **否**（同上） | **可見（展開後恆見）**：L2 `services/v2_tables/market_view.py::_MISSING_DOMAINS` 固定 7 個 domain 恆為資料未備，只要 `market_view` 存在，展開區恆有 7 列 | 純函式實算 `conclusion_model` 回傳含 `⬜ 資料未備`；L2 `_MISSING_DOMAINS` 讀碼 | **是**：`tests/ui_v2/test_mkt_market_section_logic.py`（`status_text == "⬜ 資料未備"` 1 行；另 `message == "⬜ 資料未備：…"` 2 行，見註） |

> 註：`market_section._price_model` 在非 ok 時也組 `message="⬜ 資料未備：<原因>"`，但 `overview.primary_card`／`secondary_card` 對非 ok 走 `_status_card`、**不使用**該 `message`，故在目前正式渲染路徑不可見；它被 `tests/ui_v2/test_mkt_market_section_logic.py` 另 2 行鎖定。計入「R1 鎖定測試共 4 行／2 檔」。
> 兩邊並陳：`symbols.apply` 設計上只服務各頁「畫面模型」；BL-0516／BL-0525 之後新增的市場趨勢區段走另一條純函式管線，沒有再接上 `symbols`。**這是結構性遺漏，不是當初漏看**——`symbols` 檔頭射程寫的是「`plain.plain_model` 交出來的一般畫面模型」。

#### (ii) 確認非殘餘（已被改寫、或僅示範模式、或不是畫面文字）

| 類別 | 範圍（行／檔） | 依據 | 備註 |
|---|---|---|---|
| 餵進頁面模型的顯示常數（正式模式經 `symbols.apply` 改為 `◇ 資料未備`） | 17 行：`ui_v2/alo/logic.py`（`TEXT_NOT_READY`、`TEXT_FX_MISSING_ALO2`、`TEXT_FX_MISSING_ALO4`、`TEXT_NEVER_SET`、`NAV_NOT_READY_TEXT`、`NAV_NOT_READY_DATED_TEXT`、`:529` 組句）、`ui_v2/exp/live.py::NAV_NOT_READY_DATED_TEXT`、`ui_v2/exp/logic.py`（`ND_TEXT`、`TEXT_BLANK_VALUE`、組句）、`ui_v2/hld/logic.py`（`ND_TEXT`、`NAV_NOT_READY_TEXT`、組句）、`ui_v2/mkt/logic.py`（組句、`value_text`）、`ui_v2/page_health.py::OMITTED_ROW_TEXT` | 實算：88 個正式模型經 `plain.plain_model → symbols.apply`（含後續 sections／health／readonly 步驟）後，**非 `_` 鍵的殘餘字面＝0**；`set` 17 個情境殘餘＝0。既有守衛 `tests/ui_v2/test_symbols_logic.py::test_畫面上的方塊資料未備全數換成菱形_一處不多一處不少` 做同型檢查 | 模型覆蓋度限度見 2.4 |
| 示範模式 | `ui_v2/*/fixtures.py`、`ui_v2/app_preview.py` 的示範字串 | 44 第七節第三小節之七其四：**示範模式照舊 `⬜ 資料未備`**；`shared/ui_semantics/rules.py` 檔頭同；示範不經 `symbols`（`ui_v2/symbols.py` 檔頭） | 設計如此，不是殘餘 |
| 註解／docstring | `ui_v2` 85 行（註解 43＋docstring 42） | AST 分類 | 不顯示 |
| GAP 註記散文 | `ui_v2/alo/logic.py` 5 行（含 `ALO-GAP-部分缺的內外判讀` 等） | 屬開發註記；正式模式由 `ui_v2/alo/live.py::_drop_dev_notes`＋`LIVE_DEV_NOTE_EDITS` 依表處理，且 88 模型殘餘掃描＝0 | 未逐條驗證每則 GAP 在每個情境的去留，**以 0 殘餘為準** |
| 比對用常數 | `ui_v2/alo/logic.py`（`startswith("⬜ 資料未備")`）、`ui_v2/sections.py::MKT6_EMPTY_LINE`（供 `_is_mkt6_empty_line` 比對，兩種字首都認） | 讀碼 | 非顯示 |
| `_` 鍵內部字串 | 8 個字串，全在 `alo` 模型：`_gap_text`、`_missing_reasons`、`_reason`（程式內部，顯示用的副本在非 `_` 鍵已被改寫）、`_export_text`（見下列） | 實算殘餘掃描；讀碼 `ui_v2/alo/logic.py` | 內部欄位未見渲染器直接輸出（單組 grep） |
| 匯出檔內容（非畫面） | `ui_v2/alo/logic.py::_export_text`（`ALO-5` 試算結果 CSV，下載內容） | **BL-0372**（open）：總管 2026-10-17 裁定先不動匯出檔，「匯出檔要不要跟畫面同符號，另裁」 | 不是畫面文字；**不計入 (i)** |
| `ui_v3` | 0 行 | `git grep` 0 命中；`ui_v3/viewmodels/common.py` 以 `◇ 資料未備` 為準；`ui_v3` 不 import `ui_v2` | 無殘餘 |
| Old UI（`ui/**`）與 `services/**` | `ui/**` 13 行／9 檔；`services/**` 7 行／4 檔（`fund_total_return.py`、`health/dividend.py`、`health/grade.py`、`health/replacement.py`） | Old UI 為 read-only 邏輯參考（`DEC-2026-11-02-02`／`-03`）；`ui_v2`／`ui_v3`／`services/v2_tables`／`services/v2_domain` 不 import 這幾支（單組 grep） | **不在 NG-2（`ui_v2` maintenance-only）與 BL-0532 射程內**；不碰 |

#### (iii) 無法判定（需 AppTest／截圖／特製輸入）

| ID | 位置 | 字串 | 為什麼無法判定 | 被測試鎖定？ |
|---|---|---|---|---|
| **R2** | `ui_v2/mkt/chart.py::TEXT_EMPTY`（由 `market_section._price_model` 與 `overview.rates_card` 在「切片 status＝empty」時設為 `message`，`ui_v2/mkt/page.py::_render_primary` 以 `st.markdown` 輸出） | `⬜ 資料未取得，無法繪圖`（注意：**不是**「資料未備」字面，`symbols.apply` 即使收到也**不會**改） | **渲染路徑存在**；但進入條件＝「domain 是 ok、卻沒有任何有值的點」。L2 `services/v2_tables/market_view.py` 只在 `points` 非空時給 `STATE_OK`，`overview.rates_domain` 也要求 `_valued(points)` 非空才 ok ⇒ **依契約推論不可達**；是否在極端輸入（例：點存在但非有限數）出現＝**未驗**，需特製輸入或 AppTest | **是**：`tests/test_v2_domain_port.py` 的 `test_mkt_期間切片與延遲日數_與搬遷前逐案相同` 比對 `TEXT_EMPTY` 與搬遷前基準 commit 的 `ui_v2/mkt/chart.py` 逐字相等（取不到基準 commit 時 skip，改由摘要常數守住） |
| **R3** | 近鄰（**不含「⬜ 資料未備」字面**，不在 BL-0532 字面射程）：`ui_v2/mkt/market_section.py` 的 `TEXT_EPS_PE_MISSING`（`⬜ EPS 預估資料未取得，無法計算正式指數情境`）、`TEXT_INTL_MISSING`（`⬜ Missing／Data Gap：目前沒有正式資料來源`）、`TEXT_DATA_GAP`（`⬜ Data Gap：目前沒有已核准的資料來源`） | 同左 | 這些是「▸ 尚未取得」群組的**固定文案**，正式模式**恆可見**（7 個固定缺 domain）。是否算 BL-0532 殘餘取決於「`⬜` ＋『資料缺口』語意」是否納入統一——這是**字樣語意取捨**，屬 BL-0540 G-2 的鄰近題 | 是：`tests/ui_v2/test_mkt_market_section_logic.py`（`ms.TEXT_EPS_PE_MISSING` 等 3 處）、`test_mkt_market_section_page.py`（1 處） |

### 2.3 數字總表（`d82a711d`，單組 `git grep` 與 AST，可重跑）

| 範圍 | 行數 | 備註 |
|---|---|---|
| `ui_v2` 字面命中 | **111** | 註解 43／docstring 42／程式字串 26 |
| 　程式字串 26 的去向 | 17 模型顯示常數＋5 GAP 散文＋1 比對＋1 比對用常數＋**2 不經模型（R1／R2）** | 見 2.1 第 2 步 |
| `ui_v3` | 0 | |
| `ui/**`（Old UI） | 13 行／9 檔 | read-only，不計 |
| `services/**` | 7 行／4 檔 | Old UI 路徑，不計 |
| 測試中含字面 | 169 行／37 檔（`tests/ui_v2` 136 行／27 檔） | 與證據檔 §3.4 的「37 檔／169 行」相符 |
| 鎖定 R1 的測試行 | **4 行／2 檔** | `test_mkt_market_section_logic.py` 3＋`test_mkt_overview_logic.py` 1 |

### 2.4 未驗與限度（不得讀成「ui_v2 已掃乾淨」）

1. **NOT RUN**：任何 Streamlit／AppTest／截圖。R1 的「可見」是由 `page.py` 讀碼＋純函式實算得到，不是畫面證據。
2. 88 個正式模型是**測試 fixtures 組出的**，不是真實 Sheet／真實取數；`exp` 只有 4 個、`set` 是以 `SF.scenario` 的 17 個情境直接跑 `build_page_model`（非 live 分支）。未涵蓋的分支以「殘餘＝0」之外的**靜態判讀**為準。
3. 全稱句限度：「`symbols` 只改 `model`」「`_` 鍵內字串未見渲染器輸出」「`ui_v3` 0 命中」皆為單組字面搜尋，不含別名、動態組字、`getattr`；`hld/page.py` 確有渲染 `_fields`（私有鍵）的先例（已由 `_missing_fields` 機制處理），故「`_` 鍵＝不可見」**不能一概而論**，本檔只對上列 4 個鍵做了讀碼。
4. 只搜 `⬜ 資料未備`／`⬜ 資料未取得` 兩個字面；「⬜ ＋其他資料缺口語意」見 R3，不含「⬜ 無法判定」「⬜ 不適用」「⬜ 未設定」（那是 44 明定留給無法判定族的 `⬜`，**不是殘餘**）。

### 2.5 客戶裁示重申與下一步邊界

- **客戶本批裁示 (2)**：α 不全面啟動；BL-0532 僅做殘餘影響掃描；**`TEXT_EMPTY` 暫維持原樣**；**不得一次改寫舊 UI 110 行字樣及大量測試**。本檔**沒有改任何 `.py`**，`TEXT_EMPTY` 一字未動。
- **若客戶之後要動（仍須先開 BL-0532 實作批；BACKLOG BL-0532 列：「客戶開實作批」）**：最小批僅限 (i) 類——R1 一個常數（`_STATUS_TEXT[資料未備]`），以及 4 行測試斷言級別的同步；**不含 R2（`TEXT_EMPTY`）、R3、匯出檔、Old UI**。實作方式（改常數、或在市場趨勢區段渲染前套 `symbols`）屬技術細節，總管拍板。需注意：`TEXT_EMPTY` 另受 `tests/test_v2_domain_port.py` 搬遷前逐字比對鎖定，貿然改字會使該測試紅。
- **證據檔 §3.4 Q2 的補充（不改其結論）**：證據檔 Q2 方案 C 理由寫「BL-0540 G-2 未裁，會預先替客戶答題」。事實面補充：`shared/ui_semantics/rules.py::APPROVED_WORDING["chart_empty"]`＝「此圖目前沒有可畫的資料」**已由客戶 2026-11-03 核准**（`DEC-2026-11-03-07`），BL-0540 G-2 現只剩「`資料不足`／`chart_empty` 與 `◇ 資料未備` 是新增還是取代」未確認。`ui_v2` 的 `TEXT_EMPTY` 是否改用該正式字樣，仍屬客戶裁示；**本檔不推薦，也不預先替客戶答題**。

---

## 3. 子任務 3c：G1～G13 現行狀態

Gate 定義：`docs/evidence/ui_data_contract_audit_2026_11_12.md` §5（逐字讀過）。歸類：**(A)** 已有明確裁示；**(B)** 可繼續唯讀研究；**(C)** 必須停止等待客戶；**(D)** 可供下一批實施的候選。涉及 FX 開閘、D2 欄位核准、身份（DG2／ISIN）、金融公式／門檻、正式 cutover 的 Gate **只歸 (C)／(B)，不歸 (D)**。「推薦」＝總管讀法，可被客戶推翻。引用的 DEC／BL 均已實際 `grep` 確認存在。

### 3.1 總表

| Gate | 問題（一句話） | 歸類 | 依據（位置） | 下一個合法動作 | 推薦（A／B／C 簡表） | 禁止事項 |
|---|---|---|---|---|---|---|
| **G1** BL-0545 | 使用者何時提供合法輸入（本人 session 或匿名清單）？ | **C** | BACKLOG BL-0545 列（狀態欄 `open`，內文「使用者目前選擇暫不提供真實輸入」）；HANDOFF §2；`DEC-2026-11-07-03`（Phase 1 探針已核准、live 模式 NOT IMPLEMENTED）；客戶本批裁示 (5)「繼續 BLOCKED」 | 無（等外部輸入）。文件可選補註 BLOCKED（E2／E4） | A 維持 BLOCKED（推薦）／B 使用者自願給匿名清單，再以既有探針跑／C 實作 live 模式（未授權） | 請求憑證、執行 live、虛構覆蓋率、改 Grade／准入／UI |
| **G2** 79／80 地位＋HANDOFF 標 82 | 兩份輸入契約是否列入凍結清單；HANDOFF 是否改標 82 | **A**（＋(D) D-1） | 客戶本批裁示 (3)（成稿時未另立 DEC，現補登於 `DEC-2026-11-12-02`）；79／80 檔頭＋`DEC-2026-11-02-03`／`-05`／`-07`；BL-0542 G1 狀態 (d)（已登記 79 frozen 落差）；本檔 §1 | 套用 E1（docs-only）＝候選 D-1 | A 79／80 維持「正式 input contract，不等同 frozen」並改 HANDOFF（推薦，已裁）／B 把 79 納入凍結清單（須客戶＋走凍結程序）／C 不處理 | 自動把 79／80 升格 frozen；改 82 或 DEC 歷史；改 `PROJECT_RULES.md`／`CLAUDE.md` |
| **G3** BL-0540 G-2／G-3／G-5 | 資料不足與資料未備並存或取代；健康度集中 ⚙️ 如何承接；AI 六項對映 | **C**（(B)：crosswalk 獨立複驗） | BACKLOG BL-0540 列（「待客戶裁示三子項」）；`DEC-2026-11-03-07`（`insufficient`／`chart_empty` 字樣已核准，僅「新增或取代」未確認）、`-08`；`docs/evidence/data_state_vocabulary_crosswalk_d3a_2026_11_08.md` | 可選：對 crosswalk 做獨立複驗（純文件）。決定本身等客戶 | A G-2 並存、G-3 由各頁 wireframe 承接（不解凍 44）、G-5 先不改 67（證據檔推薦）／B G-2 取代／C 先不裁 | 取代或刪除 `◇ 資料未備` 規則表列；改 frozen 44 或 67 |
| **G4** 🌍 綜合判定／新鮮度／VIX 門檻 | 要不要有正式判定規則與「何時算舊」 | **C** | 證據檔 §3.2 缺口 D7（**註：此 D7 是缺口編號，不是 `DEC-2026-10-30-01` 的 D7 段序**）；BACKLOG BL-0369（open，`Q-05` 未定）、BL-0536 列 H4（freshness 門檻）；`DEC-2026-11-03-01` Q5 B（未裁前不自創新舊判定） | 無。可唯讀蒐集既有證據（來源發布頻率）供客戶裁示用，不新增門檻 | A 先不裁，維持 ⬜ 門檻待裁示（推薦）／B 逐源以發布頻率論證後裁／C 沿用舊樹 22／30（不推薦） | 自訂門檻值、沿用舊樹 22／30 當預設、寫「新／舊／正常／過期」判定 |
| **G5** cutover（BL-0535）與深色模式正式施工 | 何時把正式入口切到 `ui_v3`；深色是否施工 | **C** | `DEC-2026-11-02-06`（cutover 規則）；BACKLOG BL-0535（open；cutover 後守衛在切換前不可能存在）；`DEC-2026-11-11-03`（不授權任何 UI／Runtime 施工；G7 Cloud／真機待正式 dark 實作＋非作者 QA 後另行授權） | 無 | A 💼／🔍／⚙️ wireframe 與資料契約過關前不 cutover（推薦）／B 先做 🌍 單頁 cutover 評估／C 先動深色 | 動 Streamlit Cloud 入口設定、改 `app.py`、刪 Old UI／`ui_v2`、新增正式 dark token、偏好保存 |
| **G6** 💼 BL-0542 G-3／G-4／G-5、NAV 10 日規則 | 摘要四格、配息推估、狀態詞對映 | **C**（(A)：T1＝B、N＝C、Stage 1 三項裁示；(B)：第一切片規劃） | BACKLOG BL-0542 列；`DEC-2026-11-04-01`／`-02`／`-03`；`DEC-2026-11-09-02`～`-04` ④ 未核准清單（含 NAV 10 日／D7）；G1-① Golden Baseline 已有 `tests/test_alo_core_golden.py` | 可做：唯讀規劃第一切片 B0（資料契約＋fixture＋缺值 ViewModel）的文件。**B0 本身未獲授權**（BL-0542 稱「稽核建議，待客戶核准」） | A 走 82 第一切片 B0、G-4 暫不開（證據檔推薦）／B 先裁 G-3／C 先接線 | 動 `_build_alo2` 分母、改 `nav_metrics`、任何公式／推估值、新增狀態詞；G1-②／③ 搬遷 |
| **G7** 💼 Stage 1 線框審批 | 客戶審精修後的 Stage 1 線框 | **C** | `DEC-2026-11-09-03`／`-04`（停點＝客戶審核精修後線框；非最終線框、非 UI 施工授權）；HANDOFF §3 BL-0542 列「待客戶」 | 無（等審） | A 照現行停點，不跳 Stage 3（推薦）／B 併審 Stage 2／C 先施工 | 進 Stage 3、資料接線、金融計算、新狀態詞／`reason_code` |
| **G8** 🔍 BL-0530 ISIN、🔍 wireframe（BL-0536-G3）、D2 首批逐列核可 | ISIN 要不要啟用；D2 的 17 列是否核可 | **C** | BACKLOG BL-0530（research-only，`DEC-2026-11-01-02`）；`PROJECT_RULES.md` 0.4（🔍 尚無 wireframe）；`DEC-2026-11-11-04`（D2-G1＝B 修正版、核准欄位＝0）；`docs/evidence/d2_contract_candidates_returns_identity_holdings_2026_11_08.md` 末節「Required 逐列待審表」＝身份 3＋NAV 6＋績效 8＝**17 列，皆待審**（本組數列確認） | 無（逐列核可是客戶審核，不是施工）。🔍 線框草稿是否產出須先有客戶指示 | A 先逐列審 D2 Required 17 列；ISIN 維持「尚未啟用」（推薦）／B 先出 🔍 線框／C 先啟用 ISIN | 啟用 ISIN mapping、DG2 production、把任何 D2 欄位當核准、名稱搜尋補 ISIN、AI 猜 |
| **G9** 🤖 Phase 7 前置 | Digest schema、Risk Cap、BL-0528 何時處理 | **C** | BACKLOG BL-0527（open）、BL-0495／0496（待客戶裁示）、BL-0528（待客戶裁示）；`DEC-2026-11-11-04` D2-G2＝A（D2 與 Digest 分離） | 無 | A 維持 Phase 7 前不啟用，BL-0528 另案（推薦）／B 先定 Digest schema／C 先接 Claude API | OneBrain／Digest 施工、Risk Cap 數值、改 A 線 prompt、Phase 7 |
| **G10** ⚙️ wireframe（BL-0536-G4）、Rule ID 格式、BL-0534 | Registry 殼、通知偏好版面；`pay_date` amendment | **C**（(B)：BL-0534 amendment 文字起草） | `PROJECT_RULES.md` 0.4（⚙️ 尚無 wireframe）；BACKLOG BL-0534（open，amendment 文字未起草、起草後送客戶核准）、BL-0531 UI-10；`DEC-2026-11-02-07`（44 `pay_date` 另開正式 amendment） | 起草 BL-0534 amendment **文字**（不改 frozen 44）是否在現行授權內＝**NOT VERIFIED**，宜先請總管確認；⚙️ 線框草稿須客戶指示 | A Registry 殼先只列名稱與出處、`pay_date` 先起草文字（證據檔推薦）／B 先出 ⚙️ 線框／C 直接 amend 44 | 直接改 frozen 44、新增 Rule Registry 程式、改 OAuth scope／callback |
| **G11** FX 閘門 D8；Actions→Cache 讀取路線 | FX 閘門何時可開；快取何時能當主來源 | **C**（(A)：FX 維持關閉；(B)：僅離線唯讀） | `DEC-2026-11-08-02`（D8 維持關閉、不以相同方法立即重跑）、`-08-01`（遠端分支全保留）、`DEC-2026-11-10-04`（研究與架構方向，**不准許切換 production**）、`-10-05`（純離線驗證）；`FX_OBS_DATE_RULE_VERIFIED` 仍為 `False`（證據檔 §1.1，單組讀碼） | FX：**無**（含不得重跑探測、不得觸發 workflow）。快取：僅限 `DEC-2026-11-10-05` 範圍的純離線唯讀分析；不得連網、不得改 workflow | A FX 維持關閉；快取最窄版 α 僅為研究推薦、未裁（證據檔推薦）／B 開 FX 補跑／C 快取當主來源 | FX 開閘、改 `FX_OBS_DATE_RULE_VERIFIED`、重跑探測、改 `data_cache`／workflow、清 Actions Run、刪遠端分支 |
| **G12** `CLAUDE.md` §2.1 TDCC「境內」標籤、§3.1 pandera 自相矛盾 | 是否登記為憲法勘誤待另案 | **A**（不得改；僅登記） | BACKLOG BL-0538 列＋HANDOFF §3 GATE (a)：「BL-0538 不延伸授權修改 `CLAUDE.md`」；BACKLOG 檔尾 2026-11-12 索引列已登記此兩項為文件勘誤待確認；本組複核：`repositories/fund/sources.py` 的 TDCC 說明寫「TDCC OpenAPI 境外基金 metadata」，`CLAUDE.md` 寫「TDCC(境內)主」；`requirements.txt` 有 `pandera>=0.20,<1.0`，`CLAUDE.md` §3.1 首句仍寫「無 pandera」（該處已自帶 2026-09-01 反遮蔽註記） | 無。已登記，不另開 BL | A 僅登記、不改（已裁，推薦）／B 另案修憲法／C 順手修 | 修改 `CLAUDE.md` 任何字；以「勘誤」名義夾帶 |
| **G13** BL-0546 | Old UI `composite_score`／`decision_matrix` 缺值語意（補 0／持有）是否沿用 legacy | **C** | BACKLOG BL-0546 列（存在，待客戶裁示，登記不構成動工授權）；與 BL-0428／BL-0440／BL-0445 相鄰；客戶本批裁示 (4)（保留登記、未核准修改舊 UI） | 無；**保留 BL-0546 登記不動** | A 不動 Old UI，與 BL-0428／0440 一併裁（推薦）／B 要求 Old UI 改 ⬜／C 沿用 | 改 Old UI 的 `composite_score`／`decision_matrix`；New UI 沿用此語意；新增公式／門檻 |

### 3.2 與證據檔不一致或需補充之處

| Gate | 證據檔寫法 | 本組查證結果 |
|---|---|---|
| G1 | 「維持唯一全域 NEXT」 | 一致。補充：BACKLOG／HANDOFF 都沒有「BLOCKED」一詞（單組 grep），客戶說 BLOCKED，建議文件補註（E2／E4，選配） |
| G2 | 「79／80 維持『正式 input contract，不等同 frozen』」 | 一致，但**對 80 偏簡**：80 的 architecture／Reuse Matrix／migration boundary 依 `DEC-2026-11-02-05` 已凍結（本檔 §1.1） |
| G3 | BL-0540 G-2／G-3／G-5 | 一致。補充：`insufficient`／`chart_empty` 字樣**已核准**（`DEC-2026-11-03-07`），G-2 只剩「新增或取代」 |
| G4 | 「D7」 | 證據檔此處 D7＝§3.2 缺口編號；與 `DEC-2026-10-30-01` D7（段序）同名不同物，易混 |
| G6 | 只列 G-3／G-4／G-5、NAV 10 日 | 一致但未提 BL-0542 的 **G-1（PORT／分母，G1-② ／③ 未授權）與 G-2（Preview 守衛）** 仍待裁；本表已在「禁止」欄補上 |
| G8 | 「D2 首批逐列核可」 | 一致；本組數得「17 列」（3＋6＋8） |
| G11 | 「快取最窄版 α（僅 DGS10／DGS2、僅取數失敗回退）為研究推薦，尚未授權」 | `DEC-2026-11-10-04` ② 明寫「專案 AI……推薦（方案 α 最窄版）**未經客戶裁示**」，一致 |
| G12 | 「CLAUDE.md §2.1 TDCC 境內標籤／§3.1 pandera 自相矛盾」 | 兩項事實均複核屬實（見 G12 列）。補充：§3.1 那句在 `CLAUDE.md` 內**已有 2026-09-01 就地註記**自承矛盾，並寫「已登記回報總管另派」 |
| G13 | BL-0546 | 一致（列存在、內容相符） |

### 3.3 可供下一批實施的候選（(D) 類；僅 2 項）

| ID | 內容 | 層級 | 為什麼可進 (D) | 仍須的前置 |
|---|---|---|---|---|
| **D-1** | `docs/HANDOFF.md` §0 第 4 點措辭修正（E1，單行；選配 E2／E3） | 文件 | 客戶本批裁示 (3) 已明確規定 79／80／81／82 的稱法；不改任何語意、不新增裁示 | 無額外 Gate；一般 docs-only PR 流程（非作者 QA、CI） |
| **D-2** | BL-0532 (i) 類最小批：僅 R1（`_STATUS_TEXT[資料未備]` 一個常數）＋ 4 行測試斷言同步＋可選的防回流守衛 | 字樣／守衛 | `DEC-2026-11-02-01` 甲(四)＋`DEC-2026-11-02-05` NG-2 附題已裁示統一也套用 `ui_v2` 且視為正確性修正；BL-0532 列稱「屬機械式」 | **須客戶先開 BL-0532 實作批**（BACKLOG BL-0532 列：「需等客戶開實作批」）；客戶本批裁示 (2) 已限縮為 (i) 類、`TEXT_EMPTY` 不動、不一次改 110 行 |

**未列入 (D)（刻意）**：證據檔 U2(b)(c)（`ui_v2/shell.py` docstring「五項」、`fetch_fund_multi_source` docstring 順序）——是否在 NG-2「只修安全／正確性」範圍**無明文**，建議併客戶一句話確認，確認前不列；U3（🔍 線框草稿）——須客戶指示且有 D2／ISIN 越界風險；任何涉及 FX、D2、身份、金融公式、cutover 的項目。

### 3.4 與本批客戶裁示對應的「下一個合法工作點」

| 客戶本批裁示 | 對應的下一個合法工作點 | 備註 |
|---|---|---|
| (1) γ 優先（Gate 清單整理） | 本檔 §3 ＋ E1～E5 的 docs-only PR（由整合者彙整） | 不產生新裁示；推薦欄為總管讀法 |
| (1) β 限縮 | 🔍 線框草稿**不開始**（須客戶指示；見 G8／3.3 未列入項） | 若客戶要，另派 |
| (2) α 不全面啟動；BL-0532 只掃描；`TEXT_EMPTY` 維持 | 本檔 §2（已完成）；後續僅在客戶開實作批後做 D-2 | 不改 110 行；不動 R2／R3 |
| (3) 79／80 不升格；82 部分核准草案；81 依範圍 | D-1（E1） | |
| (4) 保留 BL-0546 | 不動 | |
| (5) BL-0545 BLOCKED | 不動；可選 E2／E4 補註 | |
| (6) B2／B3、CLAUDE.md 大幅整理、Digest、OneBrain、Phase 7、FX 開閘、Actions 清理繼續暫停 | 無動作 | 本檔未碰 |

### 3.5 BL-0545 仍為唯一全域 NEXT 的相容性說明

本檔的所有「下一個合法動作」都是 **文件整理或客戶決策前置**，**不是新的全域 NEXT**：D-1 屬 docs-only 小批；D-2 需客戶開實作批後才成立；其餘 Gate 皆等客戶。因此 `HANDOFF` §2「唯一 NEXT：BL-0545」、§0 的「唯一下一接手點」恰一處未劃線，**維持不變**，與 `tests/test_canonical_rule_consistency.py` 的「單一 live next point」守衛相容（E1～E3 已模擬）。`DEC-2026-11-12-01`／HANDOFF §3A 已寫明「本文不是新全域 NEXT」。

---

## 4. 限度與未驗清單

1. **未跑任何 pytest／AppTest／Streamlit／截圖**；所有測試是否綠＝NOT VERIFIED（CI 才能驗）。本機 `python3` 無 streamlit、無 pytest；本組僅以 `python3 -I`＋`PYTHONDONTWRITEBYTECODE=1` import 純 Python 模組做小段實算（`ui_v2/symbols`、`ui_v2/plain`、`ui_v2/mkt/{market_section,overview,chart}`、`ui_v2/{alo,hld,exp,mkt,set}/{logic,live,fixtures}` 等），並以 stub 取代 `pytest` 只為了 import 測試檔的 fixtures 組裝函式；**未寫入 repo、`git status` 乾淨**。
2. 全稱句皆單組字面搜尋（見檔頭）；「`ui_v2` 殘餘＝R1 一組」依賴 88＋17 個 fixtures 模型的覆蓋度。
3. 79／80／81／82 的地位判讀、(A)～(D) 分類、推薦欄，皆為**單組作者讀法，可被客戶推翻**；`DEC-2026-11-02-03`／`-05`／`-07` 等多為「要點轉述」，本組見不到客戶對話本身。
4. 81 檔頭「獨立稽核本批尚未完成」是否後續補完＝**NOT VERIFIED**。
5. 客戶本批裁示 (1)～(6) 為總管轉述，**repo 內無逐字存檔**（成稿時未另立 DEC；整合入庫時已補登 `DEC-2026-11-12-02`，仍為要點轉述）。
6. 本檔未涵蓋：`docs/v2/44` 全文、`ui_v2/**` 全部渲染器逐行讀碼、`.claude/worktrees/` 下的鏡像目錄（未追蹤，`git grep` 不含）。

---

## 附錄 A　可重跑的指令（repo 根目錄）

```
# 字面命中（行數）
git grep -n "⬜ 資料未備\|⬜ 資料未取得" -- ui_v2 | wc -l          # 111
git grep -n "⬜ 資料未備\|⬜ 資料未取得" -- ui_v3 | wc -l          # 0
git grep -n "⬜ 資料未備\|⬜ 資料未取得" -- ui | wc -l             # 13（Old UI）
git grep -c "⬜ 資料未備\|⬜ 資料未取得" -- tests                  # 37 檔／169 行
# R1 的鎖定測試
git grep -n "⬜ 資料未備" -- tests/ui_v2/test_mkt_market_section_logic.py tests/ui_v2/test_mkt_overview_logic.py
# R2 的鎖定測試
git grep -n "TEXT_EMPTY" -- tests
```

分類（AST，把 111 行分為註解／docstring／程式字串）與模型殘餘掃描（借用 `tests/ui_v2/test_plain_logic.py::_live_models` 與 `ui_v2/set/fixtures`）的做法見 2.1 第 2、4 步；腳本為一次性、未入庫，整合者如需附錄可向本組索取。
