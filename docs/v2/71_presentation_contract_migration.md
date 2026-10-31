# 71｜Presentation Contract Migration：影響盤點、衝突矩陣與分批計畫（第一階段）

> **性質**：盤點與計畫文件，**不是規格**。Presentation Contract 與 Visual Fidelity Gate 的正式條文只住在 `docs/v2/44_fund_ui_ssot.md` 第七節第三小節之十九（以下簡稱「44 之十九」）；本檔與它衝突時以 44 之十九為準。不另建第二套 UI 憲法（客戶第二十二節）。
> **出處**：客戶 2026-10-29 裁示（三則訊息），逐字存檔 `docs/evidence/decisions/2026-10-29_presentation_contract_migration.md`；決策登記 `docs/DECISIONS.md` `DEC-2026-10-29-05`（呈現與 Visual Fidelity）、`DEC-2026-10-29-06`（基金 IA、Decision Digest、One AI Brain、Durable Memory）；工作項 `docs/BACKLOG.md` BL-0525（母列）、BL-0526（AI 投資總結入口形式 Gate）、BL-0527（Decision Digest 缺口與守衛）、BL-0528（A 線 AI 牴觸登記）。基金 IA 的正式條文在 44 第七節第三小節之二十；Decision Digest 與 One AI Brain 的正式條文在 `docs/v2/67_ai_action_vocabulary.md` 第 5～7 節。
> **量測基準**：main `02615e417700e880796e2fe5251df97a3494183b`（`02615e41`，2026-10-29）。兩份調查盤點量在 `6b60b2b6`；兩者之間只有 #1104 的 7 檔（`docs/BACKLOG.md`、`docs/HANDOFF.md`、五個 `theme.py` 檔頭 docstring 劃線），不影響本檔任何一列（執行組以 `git diff --stat 6b60b2b6 02615e41` 實跑確認）。程式位置寫「檔案::符號」，行號標「約」，會漂移，引用前請現場重查。
> **來源組標記**：【碼】＝調查組 1（程式碼與測試）；【文】＝調查組 2（文件、規格、治理、IA）；【AI】＝調查組 3（AI 與 Decision Digest）；【執】＝本執行組抽查或補充。三份調查盤點是單組結果，本組只抽查了承重事實（第九節列出抽查了哪些），其餘照錄。
> **事實層級**：【事實】＝讀檔或 `git grep` 可重跑；【讀法】＝解讀，可被推翻；【未驗】＝沒有驗。
> **分類**（客戶第六節）：**A** 資訊語意 Contract（保留）；**B** Presentation-only（由新 Contract supersede）；**C** Mixed（拆開：A 留、B 遷）。另標 **IA**＝屬客戶第十二～十五節的 IA 方向，處置見第六節（客戶第三則已裁示，正式條文 44 之二十），不走呈現 precedence。
> **登記不構成動工授權**（`CLAUDE.md` §-1）。

---

## 0. 結論先講

1. 客戶點名的 `render_state.*`、`not_ready(..., where=...)`、三要素 helper 只住在舊線 `ui/`（A compatibility line）；B 線 `ui_v2/` 不 import 舊線，有自己一套形狀不同的等價物（`answers`、`detail_lines`、`caption_lines`、頁首狀態行、`quiet_*` 收起卡、「進階診斷」展開區）。【碼】【執抽查】
2. 舊線**客戶已裁示：不遷**（第三則 Gate 第 3 項方案 A，只遷 B 線；與 `PROJECT_RULES.md` 第 13 節第 11 條同向）。本檔照實登記舊線的 A／B／C 分類，不排工。
3. B 線全樹只有一個圖表呼叫點（🌍 頁的折線圖卡）；⚖️、💼、🔍、⚙️ 四頁目前沒有圖。新契約在那四頁不是「搬位置」而是「新增視覺元件」，依 `CLAUDE.md` §-1.5.4 屬草稿先行。【碼】【執抽查】
4. 衝突最直接的兩處：🌍 頁唯一的圖排在結論燈、三張文字卡與 ③ 之後；圖下常駐四到六行來源與限制小字。這兩處是 Batch C 的主工作。【碼】
5. 44 的呈現類條文已於本 PR 由 44 之十九 supersede（七行行尾加註、原文保留）；資料語意、Missing 符號、四狀態、嚴重度一字未改。子法 1 不動（判斷理由見第五節第三小節）。
6. 基金 IA（第十二～十五節）撞到的多是客戶自己的舊 DEC；客戶第三則已裁示 Gate 1、2、5，本 PR 已在 44 之二十落最小 IA amendment，並在 `DEC-2026-10-29-06` 逐筆寫明被 supersede 的範圍（第六節）。🤖 AI 投資總結的入口形式待單一最小 Gate（BL-0526）。 **【2026-10-29 狀態更新（`DEC-2026-10-29-07`）：客戶已裁示方案 C，BL-0526 closed；見第 6.6 節。舊句保留，不是漏刪。】**
7. Visual Fidelity Gate：客戶已裁示正式確認＝production-like Cloud screenshot、CI deterministic screenshot＝自動安全網；兩者工具鏈都還沒建（repo 內零張截圖、CI 沒有上傳截圖的步驟），列入 Batch A（第七節）。 **【2026-10-29 狀態更新：Batch A 已建 CI 安全網與 Cloud 擷取腳本，Cloud 正式確認受目前執行環境網路限制，見第 7.1 節。】**
8. Decision Digest 與 One AI Brain：repo 內原本沒有「Decision Digest」，也沒有 `build_ai_summary`；現有 AI 全在舊線、各頁自組文字快照自呼叫 LLM，沒有可直接重用成 One AI Brain 的函式。最小契約落在 67 第 5、6 節，缺口與守衛登記 BL-0527（第八節）。

---

## 1. Presentation contract inventory（A／B／C）

### 1.1 舊線 `ui/`（A compatibility line）helper —— 客戶已裁示：不遷（第三則 Gate 第 3 項方案 A）

| ID | 位置 | 作用 | 類 | 拆法（若日後遷移） | 來源 |
|---|---|---|---|---|---|
| P-01 | `ui/helpers/render_state.py::not_ready(message, *, where)` | ⬜ 灰色「未載入／未設定」；`where` 以「（請先到：…）」接在同一行常駐 | C | A：⬜ 標記、不吃 Exception（TypeError 防呆）、`message` 與 `where` 的內容要存在、`where` 字樣走 `story_nav.where_to_find()`。B：`where` 同一行常駐 | 【碼】（AST 計 90 呼叫／31 檔，`ui/views/**` 佔 42；B 線 0 —— 調查組數字，本組未重跑 AST） |
| P-02 | `ui/helpers/render_state.py::system_error` | 🔴／🟠 系統錯誤框＋可展開「技術細節」 | A | 技術細節本來就在展開區，與新契約同向；`hint` 長句常駐屬次要 B | 【碼】 |
| P-03 | `ui/helpers/render_state.py::business_alert` | 🫐 業務警訊卡 | C | A：與系統紅分離（顏色＋形狀雙訊號）；B：多行 body 全展開。新契約允許當下警示常駐，多數可不動 | 【碼】 |
| P-04 | `ui/helpers/render_state.py::safe_section`、`NOT_READY_MARK`、`NOT_APPLICABLE_MARK` | 區塊級例外隔離；⬜ 與 ➖ 語意標記 | A | — | 【碼】 |
| P-05 | `ui/helpers/ia/empty_state.py::empty_state(title, missing, *, where, footer)` | 舊線 IA 鐵則 04「空狀態三要素：標題／缺什麼／去哪補」 | C | A：三項都要有內容；B：三列全部外露 | 【碼】 |
| P-06 | `ui/helpers/ia/cards.py::state_card`、`render_cards` | 舊線卡片，灰態委派 `not_ready` | C | 同 P-01 | 【碼】 |
| P-07 | `ui/helpers/story_nav.py::where_to_find` | 「去哪補」字串的 SSOT | A | 只能改它被畫在哪，不能改它產出什麼 | 【碼】 |
| P-08 | 舊線 39 個圖表呼叫點 | 其中至少 4 個字面上在預設收合的展開區內 | B | 不遷，不動 | 【碼】（下界：只看同一函式內字面巢狀） |

⚠️ 客戶寫的「現在／為什麼／去哪補」字樣在 repo 內查不到：`git grep -nE "現在.{0,3}為什麼.{0,3}去哪補|現在／為什麼|現在/為什麼" 02615e41` 實跑無輸出（【執】2026-10-29）。本檔把它對應到舊線 `empty_state`（標題／缺什麼／去哪補）與 B 線的 `answers`、`detail_lines`、`render_settings_link`。【讀法】

### 1.2 B 線 `ui_v2/` 共用 helper

| ID | 位置 | 作用 | 類 | 拆法／處置 | 來源 |
|---|---|---|---|---|---|
| P-11 | `ui_v2/health_view.py::render_page_header` | 四頁頁首「主要原因＋另有＋資料截至日」文字狀態行＋「前往設定與診斷」 | C | A：主因、另有、as_of、同源錯誤只摘要一次。B：一行文字的形式 → 可改 status chips | 【碼】 |
| P-12 | `ui_v2/health_view.py::render_settings_link` | B 線的「去哪補」：頁面連結 | A | 已是一枚連結，相容 | 【碼】 |
| P-13 | `ui_v2/health_view.py::render_attention` | ③ 需要注意，預設展開 | C | A：項目與符號；B：段落位置 | 【碼】 |
| P-14 | `ui_v2/health_view.py::render_load_failure` | 整頁載入失敗：一句狀態＋導覽，原文進進階診斷 | A | 已符合「短句＋detail」，可作 placeholder 參考形 | 【碼】 |
| P-15 | `ui_v2/health.py::move_card_provenance` | 把核心卡的來源與新鮮度徽章移出卡面，改由設定頁總表明細承接（黃色新鮮度留 `◷`） | A | provenance 沒刪。⚠️ 與新契約的差異：新契約推薦卡內「▸ 來源」，現況是跨頁可追溯；44 之十九其二第 4 條允許兩處並存。市場趨勢圖卡沒有走這一支 | 【碼】 |
| P-16 | `ui_v2/health.py::dedupe_failures`、`relabel_unconfigured`、`drop_delay_badges` | 同源錯誤只講一次、「尚未設定」統一說法、中性延遲徽章不上卡 | A | 減字不刪資訊，可直接用 | 【碼】 |
| P-17 | `ui_v2/sections.py::quiet_cards`、`quiet_view`、`quiet_keep`、`quiet_detail_view`、`quiet_details` | 主值全讀不到的卡「安靜收起」成卡名＋一句原因 | A＋B | 新 Missing placeholder 的現成雛形；差異：收起卡仍畫 `quiet_keep` 留下的說明行 | 【碼】 |
| P-18 | `ui_v2/sections.py::relayer`（`RELAYER` 表） | 正式模式改層與 `_default_open` | B | 客戶 `DEC-2026-10-17-07` 裁示的版面；改它＝改已拍板的版面 → 草稿先行 | 【碼】 |
| P-19 | `ui_v2/sections.py::attention_items` 等 | ③ 內容組字，只讀已算結果 | A | — | 【碼】 |
| P-20 | `ui_v2/plain.py::LABEL_LAYER1..4`、`LABEL_ATTENTION`、`LABEL_DETAILS` | 正式模式四段段標 | B | 段序若改，段標與字面比對測試要同步 | 【碼】 |
| P-21 | `ui_v2/plain.py::ADVANCED_DIAG_TITLE`、`record_raw`、`raw_entries` | 原始錯誤訊息只進設定頁一枚預設收合的展開區 | A | 新契約「技術診斷」層的現成雛形 | 【碼】 |
| P-22 | `ui_v2/plain.py::plain_model`、`plain_text`、`section_text` | 一般畫面去工程化 | A | 新增的 detail 展開區內容同樣受此約束 | 【碼】 |
| P-23 | `ui_v2/symbols.py::apply`、`mark_missing`、`mark_attention` | ◆ 需要注意、◇ 資料未備、⬜ 無法判定／不適用 | A | 符號語意不在 precedence 內（44 之十九其五第 4 條） | 【碼】 |
| P-24 | `ui_v2/page_health.py` | 各頁資料狀態總表（`SET-8`）與明細 | A | provenance／freshness 的可追溯存放處 | 【碼】 |
| P-25 | `ui_v2/readonly.py::strip_write_controls` | 第一階段唯讀 | A（不在本 migration 範圍） | — | 【碼】 |
| P-26 | `ui_v2/active_gate.py::render_no_active` | 沒有 Active Sheet 的第三態「⬜ 尚未選定持倉資料來源」＋前往設定 | C（IA） | A：不是錯誤、不是空；導覽目的地屬 IA（第六節） | 【碼】 |
| P-27 | 各頁 `_badge_html`／`_badges_html`（mkt、hld、exp；set 為 `_badge`；alo 無） | 卡頭小徽章 | B | metadata chip 的雛形，但四份各自實作、無共用 | 【碼】 |

### 1.3 B 線頁面層

| ID | 位置 | 現況 | 類 | 拆法／處置 | 來源 |
|---|---|---|---|---|---|
| P-31 | `ui_v2/mkt/page.py::render`（段序） | 頁標 → 頁首狀態行 → ① `MKT-0` 燈 → ② 三欄核心卡 → ③ → 市場趨勢區段（五張圖）→ ④ → 頁尾 | B | 唯一的圖排在燈＋三張文字卡＋③ 之後；Batch C 主工作。⚠️ 390 首屏燈的測試見第四節 T1 | 【碼】 |
| P-32 | `ui_v2/mkt/page.py::_render_price_card` | 卡頭 → 期間切換 → 圖 → 期間漲跌一行 → `caption_lines` 逐行常駐 | C | A 留：資料日期、經過天數、來源、取得時間、缺值日不補值、FRED 觀測日≠公布日、單位、略過觀測、`⬜ 門檻待裁示`。B 遷：圖下常駐小字 → chips＋「▸ 來源／限制」 | 【碼】（調查組計五張卡合計約 23～28 行常駐小字） |
| P-33 | `ui_v2/mkt/market_section.py::_price_model` 與文案常數 | 純函式產出圖卡模型 | A | 模型只決定「有哪些資訊」；`model["freshness"]` 已是獨立欄位，可直接餵 chip | 【碼】 |
| P-34 | `ui_v2/mkt/market_section.py::missing_copy`＋`ui_v2/mkt/page.py::_missing_card_html` | 無正式來源的 domain 一卡一句 Missing | A＋B | 已近新 Missing 契約；符號見第二節 X-04 | 【碼】 |
| P-35 | `ui_v2/mkt/page.py::_render_card`、`_render_light` | 主值與狀態，加 `detail_lines`、`answers` 全部常駐 | C | A：主值、四狀態、`note_lines` 原因；B：`detail_lines`、`answers` 常駐 | 【碼】 |
| P-36 | `ui_v2/hld/page.py` 核心卡與 ③；`ui_v2/alo/page.py::_render_alo0..3`；`ui_v2/exp/page.py::_render_exp0..3` | 同 P-35：`answers`＋`detail_lines` 常駐；三頁 0 張圖 | C | 同 P-35；新增圖屬新增視覺元件（Batch D、E，草稿先行） | 【碼】 |
| P-37 | `ui_v2/set/page.py::_render_login`、`_render_picker`、`_render_page_health` | 登入、試算表選擇、各頁資料狀態總表都在設定頁、預設展開 | C（IA） | A：登入狀態、目前帳號、Active Sheet 語意；位置屬 IA（第六節） | 【碼】 |
| P-38 | 各頁 ④ 詳細資料展開區（`_default_open` 由 logic 給） | 層 3、層 4 預設收合 | A＋B（同向） | 可直接當 detail layer；不巢狀照守（44 之十九其六） | 【碼】 |

### 1.4 凍結 SSOT `docs/v2/44_fund_ui_ssot.md`

| ID | 位置 | 要點 | 類 | 處置 | 來源 |
|---|---|---|---|---|---|
| D-01 | 第一節第二小節禁顏色暗示方向；之十八其三系列色 | 顏色只映射資料狀態與新鮮度 | A | 不動 | 【文】 |
| D-02 | 第一節第二小節禁方向詞、禁排名為推薦、禁輸出 | 投資語意 | A | 不動 | 【文】 |
| D-03 | 第二節四層表與硬規則；之七其一四段 | 結構單位與預設展開 | C | 本 PR：「初次載入展開」加上核心圖（44 之十九其六第 4 條）；④ 必有證據來源照舊 | 【文】 |
| D-04 | 之十八其二（卡 ≤5、圖 ≤4、16 塊、第一屏密度；第 5 條核心圖是否展開由各頁定） | 密度與圖的預設狀態 | B | 本 PR：第 5 條 supersede（圖一律外露、位置讀法改寫） | 【文】 |
| D-05 | 之十八其三（第六類元件圖表：序列四狀態、缺段斷線、不畫零、無資料用空狀態模板、不畫目標價線） | 圖表元件語意 | C | A 全留；圖卡版面寫進 44 之十九其三 | 【文】 |
| D-06 | 之十八其四（期間切換，第一版統一預設 1Y） | 顯示控制 | B | 不動，與 chip「1Y +x%」相容 | 【文】 |
| D-07 | 第五節共通無障礙三條 | 語意硬規則 | A | 不動；chip 內狀態也要圖示＋文字 | 【文】 |
| D-08 | 第五節第一小節 `ok` 列（標題＋主值＋一行副標＋來源與新鮮度徽章；徽章已改由設定頁總表明細承接） | 卡片版面 | C | 本 PR：一般畫面改由 chips 與卡上「▸」承接（44 之十九其四第 4 條） | 【文】 |
| D-09 | 第五節第一小節非 `ok` 列 | 非 ok 主值的呈現 | C | 本 PR：`資料未備` 列改 placeholder 版型；符號與判定不改 | 【文】 |
| D-10 | 第五節第四小節（以層定 `default_open`；不巢狀；收合摘要寫缺什麼） | 展開規則 | C | 本 PR：卡級「▸」是該塊唯一一層（44 之十九其六）；摘要寫缺什麼照舊 | 【文】 |
| D-11 | 第五節第五小節四種空狀態與模板；之七其四符號對照 | Missing 呈現 | C | 本 PR：`來源缺` 列呈現版型改寫；四種、嚴重度、符號一字不改 | 【文】 |
| D-12 | 之七其二第 2 條去工程化 | 工程字樣下沉 | C | 相容，不動 | 【文】 |
| D-13 | 之七其二第 3 條同源錯誤一頁一次 | 錯誤去重 | C | 相容，不動 | 【文】 |
| D-14 | 之七其二第 4 條與之十四頁首資料狀態行 | 阻斷原因與資料截至日可見 | C | 相容；可改 chips，`main_reason` 單一來源不動（44 之十九其七第 3 條） | 【文】 |
| D-15 | 之七其五「導覽」類 | 只換頁、無副作用 | C | 相容；IA 改 Sheet selector 位置時要重述用途 | 【文】 |
| D-16 | 之十一頁尾一句 | 一句常駐 | B | 相容 | 【文】 |
| D-17 | 之十三找基金每列來源展開 | 來源下沉 | C | 相容 | 【文】 |
| D-18 | 之十五卡片安靜收起 | 收起規則 | C | 與新 Missing placeholder 幾乎同形，相容 | 【文】 |
| D-19 | `MKT-6`、`MKT-7`、`SET-1`、`SET-2`、`SET-6`、`SET-8` | provenance／freshness 承接處 | A | 不動 | 【文】 |
| D-20 | 之十八其七（不為湊張數補假資料、顯示 0、用佔位字樣假裝已有判斷） | 佔位禁令 | A | placeholder 只承載誠實 Missing（44 之十九其五第 3 條） | 【文】 |
| D-21 | 之十八其十第 3 條（情境指數六項同時顯示） | 必顯示資訊 | C | 六項任一不得預設收合；as-of 與來源可用 chip（44 之十九其二第 3 條列為主層例外） | 【文】 |
| D-22 | 第三節第零小節五頁總表、「一頁只回答自己那一句問題」 | 頁面職責 | A（IA） | 第六節 | 【文】 |
| D-23 | 之十七正式頁序頁名 | 頁序頁名 | B（IA） | 第六節 | 【文】 |
| D-24 | 第二節塊數上限、層 1 一枚結論燈 | 容器上限 | B（IA） | 合併頁會撞（第六節） | 【文】 |
| D-25 | 之十六其三（本檔沒有一處宣稱別頁有 Sheet 選擇器） | Sheet selector 位置 | C（IA） | 第六節 | 【文】 |
| D-26 | `EXP-2` 母體＝選股池；之三其六；之二其零「存了才算」 | 找基金母體與條件生效 | A（IA） | 第六節 | 【文】 |

### 1.5 子法 1 `docs/v2/CONSTITUTION.md`

| ID | 位置 | 要點 | 類 | 處置 | 來源 |
|---|---|---|---|---|---|
| K-01 | §2.2 V2 | 旗標 OFF 的畫面是 ⬜ 灰態三要素，不得空白 | C | 相容，不提案（第五節第三小節） | 【文】【執判斷】 |
| K-02 | §3.2、§6.6 M1 | 三態顏色嚴格分離 | A | 不動 | 【文】 |
| K-03 | §6.6 M2 | 灰態三要素（⬜ 標題／缺什麼／去哪補），資料不足一律走此形狀、不得留白 | C | 相容，不提案（第五節第三小節） | 【文】【執判斷】 |
| K-04 | §6.6 M3＋`EXCEPTIONS.md` `P-WHERECONTENT-1` | 去哪補內容的正確性 | A | 不動 | 【文】 |

### 1.6 B 線 UI/UX 規格與線框

| ID | 位置 | 要點 | 類 | 處置 | 來源 |
|---|---|---|---|---|---|
| U-01 | `docs/v2/58` U-02／U-03／U-06／U-10／U-11 | Answer first、Exception first、漸進揭露、四段、注意力預算 | B | 同向，不動 | 【文】 |
| U-02 | 58 U-08 | 一般畫面不出現工程識別碼 | C | 相容 | 【文】 |
| U-03 | 58 U-20～U-24、U-36 | 兩套符號、顏色非唯一訊號、缺值≠0、過期標示、無法判定是合法答案 | A | 不動 | 【文】 |
| U-04 | 58 U-30 | 四頁只顯示最小狀態 | C | 相容（可改 chips） | 【文】 |
| U-05 | 58 U-43 | 設定集中設定頁、其他頁輸入預設收合 | C（IA） | 與第十二節 B 衝突（第六節） | 【文】 |
| U-06 | 58 §9 圖表附文字結論 | 圖文 | B | 與「至多一句」相容 | 【文】 |
| U-07 | 58 §12 驗收表、第 13 節 (7) 截圖是驗收證據 | 驗收 | B（流程） | Visual Fidelity Gate 是它的加嚴 | 【文】 |
| U-08 | `docs/v2/59` 五頁 390px 純文字線框 | 無圖的文字首屏 | B | 第七節 precedence 明列 wireframe，直接由新 Contract 取代呈現 | 【文】 |
| U-09 | `docs/v2/61` 批次 3 線框第六版 | Data Health 收斂 | C | 相容；健康資訊搬遷不得遺失 | 【文】 |
| U-10 | `docs/v2/65` 設定頁線框（帳號卡、Sheet Picker 在設定頁） | 帳號與 Sheet 位置 | C（IA） | A 全留（Pending≠Active 等）；位置走第六節 | 【文】 |
| U-11 | `docs/v2/66` §0、§3 | 新鮮度與取得時間要能看到；門檻待裁示 | A | 「能看到」＝可取得，新契約不削弱 | 【文】 |
| U-12 | `docs/v2/64` §2 Information Ownership Matrix | 每項資訊一個完整主頁 | C（IA） | 計算擁有權不變；顯示頁隨 IA | 【文】 |
| U-13 | `docs/v2/52` B-15 固定說明欄三段常駐 | 長文字常駐 | B | 衝突；52 是儲備規格、非現行 | 【文】 |
| U-14 | `docs/v2/47` 舊市場線框草稿 | 舊線框 | B | 已被 59／藍圖取代 | 【文】 |
| U-15 | `docs/v2/55` 預覽驗收前置 | 驗收說明 | B（流程） | 未含視覺驗收 | 【文】 |
| U-16 | `docs/design/vnext_visual_blueprint.md` §2、§5、§6 | 圖表優先、密度 guardrail、不得為好看刪來源與依據 | C | 同向；新契約是它的具體化 | 【文】 |
| U-17 | 藍圖 §2 五大主頁、§3.2／§3.3 兩頁分立、§7 批 3／批 4 | 五頁 IA | B（IA） | 第六節 | 【文】 |
| U-18 | 藍圖 §3.5 設定頁大卡 A、B | 帳號與 Sheet 在設定頁 | C（IA） | 第六節 | 【文】 |
| U-19 | 藍圖 §7 每批驗收 | 驗收 | B（流程） | 加 production-like screenshot 與 Visual Fidelity audit | 【文】 |
| U-20 | `docs/design/D1_dual_sidebar_nav_phase1.md` §6.4／R-5（OAuth callback 只在 `/set`）、D-5 | 登入位置的技術約束 | C（IA） | callback／redirect_uri 不得動；登入卡位置走第六節 | 【文】 |

### 1.7 治理文件與客戶 DEC

| ID | 位置 | 要點 | 類 | 處置 | 來源 |
|---|---|---|---|---|---|
| G-01 | `PROJECT_RULES.md` 第 13 節第 2～5 條、13.2 第 3、4 條 | missing≠0、unavailable≠neutral、not evaluated≠safe、provenance 真實、顏色非唯一載體 | A | 不動 | 【文】 |
| G-02 | `PROJECT_RULES.md` 第 7 節 Definition of Done | 完成鏈沒有視覺驗收 | B（流程） | 本 PR：加 Visual Fidelity Gate 指標 | 【文】 |
| G-03 | `PROJECT_RULES.md` 13.2 第 1 條 | 五頁、不輕易增第六頁 | B（IA） | 第六節 | 【文】 |
| G-04 | `PROJECT_RULES.md` 13.2 第 8 條 | 帳號、Active Sheet、連線由設定頁管，其他頁不自管 | C（IA） | A 全留；位置走第六節 | 【文】 |
| G-05 | `CLAUDE.md` §-1.5.4 草稿先行 | 流程 | A（流程） | 不動；新元件（BL-0517 三卡、我的資產合併頁、側欄帳號控制）沒有核准線框，照舊草稿先行 | 【文】 |
| G-06 | `CLAUDE.md` v3 `02` | 未點擊載入灰色、系統真出錯紅色 | A | 不動 | 【文】 |
| G-07 | `CLAUDE.md` v3 `00` 固定 3 欄網格、Checkbox Gate | 預設版型 | B | 不衝突 | 【文】 |
| G-08 | `DEC-2026-10-19-04` 搬移不得先刪、尚未設定與取數失敗不合併、過期淨值與退回預存分開 | 資訊不得遺失 | A | 不動 | 【文】 |
| G-09 | `DEC-2026-10-18-02`（退回舊淨值畫 ⛔ 並寫舊資料日期）、58 U-23 | 舊值警示 | A | 主層可見（44 之十九其二第 3 條） | 【文】 |
| G-10 | `DEC-2026-10-19-05` (1)(5) | 找基金卡片來源層級、三個收合問題 | B | precedence 涵蓋；落實作時引 44 之十九 | 【文】 |
| G-11 | `DEC-2026-10-21-01`～`-05` | 3-C 搬遷、`main_reason` 單一、3-D 安靜收起、收合標題「標題　—　一句原因」 | C | 相容 | 【文】 |
| G-12 | `DEC-2026-10-17-03` 護欄 6 | ④ 內「操作」與「證據／來源」分開 | B | 相容 | 【文】 |
| G-13 | `DEC-2026-10-26-01` (4) | UI 要明示 ⬜ 資料未備、⬜ 資料未取得、⬜ 無法判定並與真 0 區分 | A | ⚠️ 與 44「◇ 資料未備」既有不一致，只登記（X-04） | 【文】 |
| G-14 | `DEC-2026-10-25-01` | 唯一擁有者、💼 不放第二個 Sheet 選擇器、搜尋只重用既有可追溯鏈 | C（IA） | A 全留；位置走第六節 | 【文】 |
| G-15 | `DEC-2026-10-25-02` CAP-GATE-02 | 設定頁是唯一 Sheet selection owner、其他頁不得有 selector | C（IA） | 第六節 | 【文】 |
| G-16 | `DEC-2026-10-25-04` (1)(2)(3) | 設定頁第一層只顯示狀態、其他頁不放 selector；J-4 Active＝持倉／保單；J-6 第一階段唯讀 | C（IA） | J-4、J-6 全留；位置走第六節 | 【文】 |
| G-17 | `DEC-2026-10-26-03` J-1、J-5、J-7、J-13 | 唯讀 scope、Active SSOT、OAuth 與 SA 不互相 fallback、未選 Active →「前往 ⚙️ 設定」 | C（IA） | scope、namespace、no-fallback 全留；J-13 導覽目的地走第六節 | 【文】 |
| G-18 | `DEC-2026-10-27-17` | 設定頁寫入邊界：第一階段 read-only | A | 「加入候選」＝寫入，受此拘束 | 【文】 |
| G-19 | `DEC-2026-10-27-11` | 手機五大主頁底部導航、主要目的地 ≤2 次互動、必須實測 390px | C（IA） | ≤2 次互動與 390 實測全留；頁數隨 IA | 【文】 |
| G-20 | `DEC-2026-10-27-31`、`-35` | 不以 placeholder 湊卡；情境指數六項 | A／C | 見 D-20、D-21 | 【文】 |

### 1.8 A 線文件（不是 B 線現行規格；不建議 migration）

| ID | 位置 | 要點 | 類 | 處置 | 來源 |
|---|---|---|---|---|---|
| L-01 | `docs/wireframes/ia-wireframe.html` 鐵則 04 | 空狀態三要素 | C | 客戶原件不得改寫；不遷（同 1.1） | 【文】 |
| L-02 | `docs/wireframes/fund-empty-state-wireframe.html` §03 | 三態顏色分離 | A | 不動 | 【文】 |
| L-03 | `docs/wireframes/` 其餘原件 | A 線舊五分頁 IA 與版面 | B | 原件不動 | 【文】 |
| L-04 | `docs/v2/20_ui_spec.md` | A 線空狀態三要素逐塊規格 | C | 歷史，不動 | 【文】 |
| L-05 | `docs/v2/01`～`04` 草稿包、`22`／`23`／`43`、`30`～`39`、`docs/evidence/branch_archive/pr840/*UI_SPEC*` | 歷史草稿與稽核 | B | 歷史，不續寫 | 【文】 |

---

## 2. Old contract vs new Visual SSOT 衝突矩陣

> 「新條」：P1＝第一節階層；P2＝第二節存在≠外露；P3＝第三節圖表契約；P4＝第四節 Missing；P9、P10＝第九、十節。「precedence」：**Y**＝屬第七節八類且對象是 helper／test／wireframe；**Y\***＝屬八類，但對象是 44、子法 1 或客戶 DEC，要走 amendment／supersede 記錄；**N**＝不屬八類。「本 PR」欄記本 PR 做了什麼。

| # | 舊條文 | 新條 | 判定 | precedence | 本 PR | 來源 |
|---|---|---|---|---|---|---|
| X-01 | 44 之十八其二第 5 條（核心圖是否展開由各頁定） | P3、P9 | 衝突 | Y\* | supersede（44 之十九其三第 6 條） | 【文】 |
| X-02 | 44 第二節、之七其一（④ 預設收合；層 1／2 展開） | P1～P3 | 需拆分 | Y\* | 初次載入展開加核心圖；圖不得在 ④ | 【文】 |
| X-03 | 44 第五節第四小節（以層定 `default_open`；不巢狀；摘要寫缺什麼） | P2、P9 | 需拆分 | Y\* | 卡級「▸」讀法（44 之十九其六） | 【文】 |
| X-04 | 44 之七其四（`◇ 資料未備`、`⬜` 只給無法判定／不適用）vs 客戶範例「⬜ 資料未取得」；`DEC-2026-10-26-01` (4) 寫「⬜ 資料未備」 | P4、P10 | 版型相容；符號字面衝突 | 版型 Y\*；符號 N | 範例讀作版面示意、符號照 44 現行；既有不一致只登記（44 之十九其五第 4、5 條） | 【文】【執】 |
| X-05 | 44 第五節第一小節 `ok`（徽章已移設定頁總表） | P3 chips | 需拆分 | Y\* | chips 承接資料日、延遲、狀態；總表承接照舊 | 【文】 |
| X-06 | 44 每張非 ok 卡掛重新取數、副標原因句 | P10 | 相容（已被之七其二第 7 條收斂） | — | 無 | 【文】 |
| X-07 | 44 之十五安靜收起 | P10 | 相容 | — | 無 | 【文】 |
| X-08 | 44 之十四頁首主要原因行 | P2、P3 例外 | 相容 | Y\*（若改 chip 字面） | 無（44 之十九其七第 3 條寫明相容） | 【文】 |
| X-09 | 44 之十八其十第 3 條＋66 4.6＋`DEC-2026-10-27-35`（情境指數六項同時顯示） | P2、P3 | 需拆分 | N | 列為主層例外 | 【文】 |
| X-10 | 44 之十八其七＋`DEC-2026-10-27-31`（不以 placeholder 湊卡） | P10 圖表 placeholder | 需拆分 | N | placeholder 只承載誠實 Missing | 【文】 |
| X-11 | 44 之十八其三（無資料用空狀態模板、不畫空白座標軸） | P10 | 相容（用字對齊） | Y\* | 寫進 44 之十九其五第 3 條 | 【文】 |
| X-12 | 子法 1 §2.2 V2、§6.6 M2 | P2、P4、P10 | 需拆分（判定相容） | N | 不動（第五節第三小節） | 【文】【執】 |
| X-13 | `ia-wireframe.html` 鐵則 04、`20_ui_spec`（A 線） | P2、P10 | 需拆分 | Y（原件不得改寫） | 不遷 | 【文】 |
| X-14 | 58 U-30 | P3 chips | 相容 | Y\* | 無 | 【文】 |
| X-15 | 58 U-43 | 第十二節 B | 衝突 | N（IA） | 第六節 | 【文】 |
| X-16 | 58 §9 | P9 一句 | 相容 | — | 無 | 【文】 |
| X-17 | 59 五頁純文字線框 | P1、P3 | 衝突 | Y | 由新 Contract 取代呈現（DEC supersedes 欄） | 【文】 |
| X-18 | 52 B-15 固定說明欄常駐 | P2 | 衝突 | Y | 同上 | 【文】 |
| X-19 | 藍圖 §2、§5、§6 | P1～P3 | 相容（同向） | — | 檔頭加指標 | 【文】 |
| X-20 | `DEC-2026-10-19-05` (1) 找基金卡片層級來源 `⬜ 不適用` | P3 chips | 需拆分 | Y\* | 無（實作批處理） | 【文】 |
| X-21 | `DEC-2026-10-19-04`、`DEC-2026-10-18-02`、58 U-23 | P2 | 相容 | N（A） | 無 | 【文】 |
| X-22 | `DEC-2026-10-25-02`、`-25-04` (1)、`-26-01` (7)、13.2 第 8 條、J-13、65、藍圖 §3.5 | 第十二節 A、B | 衝突 | N（IA） | 第六節 | 【文】 |
| X-23 | `DEC-2026-10-24-02`、`-26-01` (1)(9)、`-27-02`、44 第三節第零小節與之十七、13.2 第 1 條、藍圖 §2 | 第十三、十四節 | 衝突 | N | 第六節 | 【文】 |
| X-24 | 44 `EXP-2` 母體＝選股池；之二其零「存了才算」；J-6 與 `PHASE1_HIDDEN_INPUT_CODES` 含 `EXP-1` | 第十五節 | 衝突 | N | 第六節 | 【文】 |
| X-25 | `ui_v2/mkt/page.py::render` 段序（圖在燈＋三卡＋③ 之後） | P1、P3 | 衝突 | Y | 無（Batch C） | 【碼】 |
| X-26 | `ui_v2/mkt/page.py::_render_price_card` 圖下常駐 `caption_lines` | P3 | 衝突 | Y | 無（Batch C） | 【碼】 |
| X-27 | 各頁核心卡 `answers`＋`detail_lines` 常駐 | P2 | 衝突 | Y | 無（Batch A／C～E） | 【碼】 |
| X-28 | 頁首狀態行「恰一行文字」的測試鎖 | P3 chips | 需拆分 | Y | 無（Batch A） | 【碼】 |
| X-29 | 「核心卡上沒有任何來源」的測試鎖 | P2、P9 卡內「▸ 來源」 | 需拆分（方向部分相反） | Y | 無（Batch A） | 【碼】 |
| X-30 | 390 首屏「結論燈在首屏」測試 | P1、P3 | 需拆分 | Y | 無；相容讀法寫進 44 之十九其七 | 【碼】【執】 |

---

## 3. Helper migration impact list

| 新契約需要 | 既有最接近的實作 | 能直接用嗎 | 缺什麼 | 批次 | 來源 |
|---|---|---|---|---|---|
| chart card（標題＋chips＋一句＋圖＋「▸」） | `ui_v2/mkt/page.py::_render_price_card`（`@st.fragment`）＋`ui_v2/mkt/chart.py::build_spec`（純函式） | 半成品 | chips 列、一句摘要欄、「▸」展開區；只存在於 mkt 頁，其他頁要用須抽到共用模組；fragment 內加展開區的重跑範圍【未驗】 | B | 【碼】 |
| metadata／status chip | 各頁 `_badge_html`／`_badges_html`／`_badge` | 形狀可用 | 四份各自實作；共用模組只能住在 `ui_v2/` 內（`tests/ui_v2/test_ui_v2_live_import_guard.py` 第 (5) 條禁 import 舊樹）；純函式模組不 import streamlit | B | 【碼】 |
| detail expander | 各頁 `_expander`、`_render_detail_quiet`；設定頁 `_render_advanced_diag` | 可用 | Streamlit 不允許巢狀展開區；④ 內已在展開區的塊不能再開（44 之十九其六第 2 條） | B | 【碼】 |
| Missing placeholder | `ui_v2/sections.py::quiet_view`／`quiet_cards`、`ui_v2/mkt/page.py::_missing_card_html`、`ui_v2/health_view.py::render_load_failure`、`ui_v2/active_gate.py::render_no_active` | 形狀最接近 | 收起卡仍畫 `quiet_keep` 說明行；圖表 placeholder 沒有實作 | B | 【碼】 |
| 去哪補（detail 內） | `ui_v2/health_view.py::render_settings_link` | 可用 | B 線只有「前往設定與診斷」一種去處，沒有更細的指路 | B（不擴需求） | 【碼】 |
| 首屏狀態 | `ui_v2/health_view.py::render_page_header`、各頁 `*-0` 燈 | 可改造 | 改 chips 要同步 T1、T2 | A／C | 【碼】 |
| 圖卡模型欄位 | `ui_v2/mkt/market_section.py::_price_model`（`freshness` 已是獨立欄位） | 可用 | 不必改模型；只改 page | C | 【碼】 |
| 舊線三要素 | `ui/helpers/render_state.py::not_ready`、`ui/helpers/ia/empty_state.py::empty_state` | 只服務舊線 | B 線不可共用（import 守衛）；舊線不遷 | —（客戶已裁示不遷） | 【碼】 |

> **2026-10-29 Batch A 更新**：chart card、chip、detail expander、Missing placeholder 四種形狀已建在 `ui_v2/presentation.py` 與 `ui_v2/presentation_view.py`（單元與畫面測試已有），尚未被任何頁面呼叫；套用到頁面屬 Batch C～F。

---

## 4. Test migration impact list

**關鍵技術事實（決定大部分測試要不要改）**：AppTest 的 `at.markdown`、`at.caption` 與 `tests/ui_v2/_plain_scan.py::screen_texts` 會把展開區（含預設收合的）裡的元素一起收；後者只跳過指名的標題。⇒ 「某字串在畫面上」的斷言，文字搬進展開區後仍會過；會紅的只有：精確比對展開區標題清單或數量、比對某張卡的 markdown 區塊內含某字、段序、瀏覽器量測首屏、以及把詳細內容改成條件渲染（不在畫面樹裡）。【碼】（AppTest 行為是調查組的認識，本組未實跑驗證）

| # | 檔案 | 現在鎖什麼 | 新測試契約改驗（44 之十九其八的六件事：①存在 ②未遺失 ③可展開取得 ④語意不變 ⑤provenance 可追溯 ⑥主畫面不必全部外露） | 批次 | 來源 |
|---|---|---|---|---|---|
| T1 | `tests/ui_v2/test_live_390_page.py::test_390寬_正式模式_渲染無例外_DataHealth燈在首屏` | 文字燈在 390 首屏 | ⑥＋結論燈（一行 chip）在首屏，且首屏看得到主圖或主數字（44 之十九其七第 2 條） | A（測試先改）／C | 【碼】【執抽查】 |
| T2 | `tests/ui_v2/test_health_page.py` 頁首狀態行系列（如 `test_每頁恰一行資料狀態行_不寫資料齊或正常_附資料截至日`） | 恰一行文字、固定字首 | ①②主因與 as_of 存在；④ ⛔／◇／◷ 語意不變；不鎖成單行文字 | A | 【碼】【執抽查】 |
| T3 | `tests/ui_v2/test_health_page.py::test_核心卡的來源與新鮮度徽章不在卡上_不再畫在第四段_在總表明細` | 卡內完全沒有來源 | ⑤可追溯（總表明細或卡內「▸」）；⑥主層沒有來源長字 | A | 【碼】【執抽查】 |
| T4 | `tests/ui_v2/test_hld_page.py`（`len(labels) == 5`、展開後數量不變）、`tests/ui_v2/test_exp_page.py`（`len(labels) == 4`） | 精確展開區數量 | ③每個 ④ 塊可展開取得；不巢狀照守；不鎖總數 | A | 【碼】【執抽查】 |
| T5 | `tests/ui_v2/test_alo_page.py`、`tests/ui_v2/test_set_page.py` 以塊代號前綴過濾的精確清單 | 精確清單 | 同 T4；新「▸」展開區標題規則先定 | A | 【碼】 |
| T6 | `tests/ui_v2/test_set_reshape_page.py`、`tests/ui_v2/test_sections_page.py` | 段序、展開區先後 | 段序被改時：③＋新段序；否則不動 | A／F | 【碼】 |
| T7 | `tests/ui_v2/test_set_login_page.py`、`tests/ui_v2/test_set_picker_page.py`、`tests/ui_v2/test_rulings_2026_10_18_page.py` | 登入卡、Sheet 卡、重新取數在設定頁展開區內 | 帳號與 Sheet 位置已裁示（44 之二十其三），隨 Batch F／D 重寫（不是本 Contract 的部分）；callback 查證結果可能影響登入卡測試 | D／F（不依 BL-0526） | 【碼】 |
| T8 | `tests/ui_v2/_plain_scan.py` | 市場腳本 `_MKT_NOTES` 沒有市場趨勢區段的資料 | **補射程**：讓去工程化守衛涵蓋市場趨勢區段與新 detail 容器 | A | 【碼】【執抽查】 |
| T9 | `tests/ui_v2/test_mkt_market_section_page.py` | 存在性 | ①②已符合；Batch C 搬 caption 時**新增**「主層不含長句」與「detail 內含它們」兩條 | C | 【碼】 |
| T10 | 新增 | — | 共用元件形狀測試：chip 3～5 枚、每圖至多一句、圖不在展開區、detail 預設收合、Missing 不寫 0 或中性 | B | 【碼】 |
| T11 | 舊線 `tests/test_ia_kit.py`、`tests/test_batch2_top_card_grid.py`、`tests/test_dual_track_plotly_id_collision.py`、`tests/test_wf0[1-5]_*`、`tests/test_ia_*` | where 要存在或常駐 | 不改（客戶已裁示舊線不遷） | — | 【碼】 |
| T12 | logic 層測試（`detail_lines`／`caption_lines`／`note_lines` 內容） | 模型內容 | 不必改，只要 migration 只動 page、不刪模型欄位 | — | 【碼】 |
| T13 | `tests/ui_v2/test_bl0345_dev_notes_page.py`、`tests/ui_v2/test_plain_page.py` | 收合展開區內文也不得有工程字樣 | 保留；新 detail 內的技術診斷要嘛進「進階診斷」，要嘛登記 `skip_expanders` 並附理由 | B／C | 【碼】 |

### 4.1 Batch A 測試遷移結果（2026-10-29）

| # | 結果 | 說明 |
|---|---|---|
| T1 | 順延 Batch C，現況已相容 | 它量的是結論燈元素在 390 首屏可見，沒有鎖「文字形式」，燈改 chip 後仍過；「首屏看得到主圖或主數字」的新斷言要等頁面套用（Batch C）才加，否則今天必然紅 |
| T2 | **已遷** | 狀態行不再鎖「恰一個文字元素」，改驗資料截至日存在且只講一次、不寫「資料齊」「正常」；◷／◇／⛔ 語意測試未動 |
| T3 | **已遷** | 「卡片 HTML 完全沒有來源」改為「預設可見層（剝掉 `<details>`）沒有來源長字」＋「總表明細或卡內展開區可追溯」 |
| T4 | **已遷（hld、exp）** | 展開區總數鎖死（五、四）改為各塊各一枚且預設收合，其餘展開區只准是「▸ 」開頭的 detail；不巢狀（展開後數量不變）的保護照舊 |
| T5 | 不必遷 | alo、set 以塊代號前綴過濾，新增的「▸」detail 不會讓它紅；它驗的是四塊是展開區且收合，與新契約同向 |
| T6 | 順延（段序被改時才動） | 本批不改段序 |
| T7 | 順延 Batch D／F | 帳號與 Sheet 位置隨對應批 |
| T8 | **已補射程** | 新增 `tests/ui_v2/test_plain_trend_page.py`（含正控）：市場趨勢區段納入去工程化掃描；情境腳本放在 `_plain_scan.MKT_TREND`，未放進 `SCRIPTS`，以免牽動逐情境參數化的既有測試 |
| T9 | 順延 Batch C | 隨圖卡搬 caption 時新增 |
| T10 | **已建（primitives 部分）** | 共用元件形狀測試：chip 3～5 枚、每圖至多一句、圖不在展開區、detail 預設收合、Missing 不寫 0 或中性、不巢狀時內容仍完整 |
| T11、T12 | 不改 | 舊線不遷；logic 層不動 |
| T13 | 順延 B／C | 新 detail 內的技術診斷歸屬隨頁面套用處理 |

修改處都在測試檔內以註解保留舊斷言與舊理由（劃線），不刪資訊、不改產品行為。

調查組未找到任何「圖表必須在展開區外／內」的測試（字面掃描，若有以 HTML 結構間接檢查者未涵蓋）。【碼】

---

## 5. Frozen SSOT amendment list

### 5.1 本 PR 已做

1. `docs/v2/44_fund_ui_ssot.md` 第七節第三小節之十九（呈現：資訊階層、Visual Budget 與三眼原則、各頁第一屏簡化、資訊存在與外露分離、圖表、chips、Missing 呈現、展開區、首屏、測試契約、Visual Fidelity Gate），七行行尾加註。
2. 44 第七節第三小節之二十（基金 IA：頁序與頁名、💼 我的資產結構與一枚結論燈、塊數 16、找基金第一階段、帳號與 Sheet 選擇的位置、舊線不遷），八行行尾加註。兩小節的行尾加註都不增刪行，表格列的加註寫在最後一格格尾。
3. 44 守衛基準值同批更新：`tests/ui_v2/test_alo_logic.py::test_44還是凍結的那一份`（md5）、`tests/ui_v2/test_exp_logic.py::test_44還是凍結的那一份`（md5＋行數）。理由：照 44 有限解凍程序（之十七、之十八前例），改 44 的同一批更新釘值，上一個值寫進註解。凍結不變量（塊標題、判準行、節判準、表判準、元件判準、紅線標記、隔離字表）改前改後同數，相關守衛不必動。`tests/test_doc_counters.py` 的受檢清單 `_MD_DOCS` 登記本檔（守衛要求新增的 `docs/v2/*.md` 逐一登記）。
4. `docs/v2/67_ai_action_vocabulary.md` 第 5～7 節（Decision Digest Contract、One AI Brain contract、揭露）；67 不是凍結檔，照一般文件增補，第 1～4 節原文一字未改。
5. `PROJECT_RULES.md`：第 7 節 Visual Fidelity Gate 指標、6.1.1 GitHub Durable Memory 指標、13.2 第 1、8 條行尾指標、0.5 快速索引兩行；`docs/design/vnext_visual_blueprint.md` 檔頭一行指標；`docs/DECISIONS.md` `DEC-2026-10-29-05`、`-06` 與九筆舊 DEC 的「部分 superseded by」標示。
6. `docs/v2/59`（五頁純文字線框）、`docs/v2/52`（B-15 固定說明欄常駐）、`docs/v2/58`（U-43 的帳號與 Sheet 位置）各在檔頭加一行 supersede 指標，原文一字未改。

### 5.2 本 PR 沒做（逐項附理由）

| 項 | 為什麼沒做 | 什麼時候做 |
|---|---|---|
| 44 第三節第零小節與之十七其二表的第一欄字面、列序；`ui_v2/app_preview.py::PAGES` 與頁數頁序守衛 | 照之十七其三前例：程式端頁清單與守衛逐字鎖住，本 PR 不改程式；AI 入口形式未定，頁數還不能定 | BL-0526 裁示後的對齊批（BL-0525 Batch D 或殼層批） |
| 44 我的資產整頁「回答什麼」一句、合併頁塊組成與兩枚燈怎麼收 | 依 `DEC-2026-10-27-29`「等各頁內容 Batch 才定稿」；燈的畫法要線框 | Batch D（草稿先行） |
| 🤖 AI 投資總結的頁數、44 之十八其一的 AI 區性質 | 待單一最小 Gate | BL-0526 **→ 2026-10-29 已裁示方案 C（`DEC-2026-10-29-07`），BL-0526 closed；原文保留，不是漏刪。** |
| 44 之十四頁首資料狀態改 chip 的字面 | 相容（44 之十九其七第 3 條），字面不必改 | 實作批若要改字面再開一輪 |
| 子法 1 | 判斷相容（5.3） | 若客戶不採此讀法，走提案單 #9（先例 56→57：子法修改要客戶核准提案文字） |
| `docs/wireframes/` 原件 | 客戶原件不得改寫；A 線不遷 | — |
| `docs/v2/61`、`65`、`64` 檔頭指標 | Anti-Bloat（`PROJECT_RULES.md` 13.4 第 7 條）：precedence 與 supersede 由 DEC 與 44 之十九、之二十承接；`59`、`52`、`58` 三份因有條文被直接 supersede，已依 Supersession hygiene 第 (2) 條在檔頭加一行指標（5.1 第 6 條），其餘三份未加 | 實作批碰到該檔時順手加指標 |
| 三張圖卡（BL-0517）寫進 44 | 方案 A 先草稿 | 草稿經客戶拍板後另開一輪 |

### 5.3 子法 1 相容判斷（處置 3，執行組判斷，可被客戶推翻）

1. §2.2 V2「OFF 的畫面是 ⬜ 灰態三要素、不得空白」與 §6.6 M2「⬜ 標題／缺什麼／去哪補，資料不足一律走此形狀，不得留白」規定的是**三項資訊都在、畫面不得留白**。
2. 新 Missing 呈現（44 之十九其五第 2 條）：卡名＝標題；status chip＋一句短原因＝缺什麼（收合時看得見）；「▸ 詳細原因／來源狀態／去哪補」＝去哪補，**仍在同一張卡上**、一次點開即得。三要素都在，不留白。
3. 子法 1 自己在 §6.6 把 M2 的實作形狀寫成 `not_ready(message, *, where)`，那是 A 線 helper 的形狀；「走此形狀」讀作「交出這三項資訊」，不讀作「三項同層外露」——後者是呈現，正是客戶第二節取消的那一種要求。
4. 守住相容的條件（寫進 44 之十九其二第 4 條、其五第 6 條）：「去哪補」不得只移到別頁而本卡什麼指引都不留；「缺什麼」那一句不得藏進展開區。
5. 若總管或客戶讀作「三要素須同層外露」，本判斷即不成立：屆時**不改子法 1**，先擬提案單 #9 送客戶核准提案文字（先例 `docs/v2/56` → `docs/v2/57`）。

---

## 6. 基金 IA amendment list（**客戶第三則已裁示 Gate 1、2、3、5**；正式條文 44 之二十）

> 本節保留衝突分析作為紀錄；裁示後的落字與被 supersede 的舊 DEC 逐筆範圍見 44 之二十與 `DEC-2026-10-29-06`。仍待裁的只剩 🤖 AI 投資總結的入口形式（6.6，BL-0526）。 **【2026-10-29 更新：BL-0526 已裁示方案 C，不再待裁，見 6.6 與 `DEC-2026-10-29-07`；上句保留，不是漏刪。】**

### 6.1 「⚖️ 資產配置＋💼 我的持股 → 💼 我的資產」（Gate 1 方案 A）

| 面向 | 會撞到的條文 | 處置（44 之二十） |
|---|---|---|
| page count | `PROJECT_RULES.md` 13.2 第 1 條；`DEC-2026-10-26-01` (1)(9)；藍圖 §2「五大主頁（固定）」；`DEC-2026-10-27-11` 手機五大主頁 | 內容頁四頁（🌍、💼、🔍、⚙️）；AI 入口待 Gate，不寫涉及 AI 的頁數；(9) 不 supersede（本次是客戶親裁） |
| page name | 44 之十七其二、第三節第零小節第一欄；`DEC-2026-10-27-02` | 正式頁名「💼 我的資產」以之二十其一為準；兩處表格第一欄待對齊批 |
| 頁面職責 | 44 第三節第零小節 ⚖️「不談單檔績效好壞」；「一頁只回答自己那一句問題」；`DEC-2026-10-27-29`、`-30` | 兩列字面不改，讀作頁內兩個區段；整頁那一句隨 Batch D 定稿 |
| 容器上限 | 44 第二節（一頁最多 16 塊、層 1 一枚結論燈） | `ALO-*` 8 塊＋`HLD-*` 9 塊＝17 塊、兩枚燈（【文】以 `git show 02615e41:docs/v2/44_fund_ui_ssot.md | grep -c '^#### 塊 ALO-'` 得 8、`HLD-` 得 9，本組 2026-10-29 重跑相同）；只留一枚層 1 燈後總數計 16；**但逐層計不合規**：持倉層 1／2／3／4＝1／3／2／3、配置＝1／2／3／2（44 第三節第二、第四小節層表），合併去一燈後層 2＝5（合規）、**層 3＝5、層 4＝5，各超「層 3、層 4 各 3 塊」上限 2 塊**（【執】讀 `02615e41` 兩張層表）。處置：留給 Batch D 線框送客戶裁示（合併、切換、下沉或收合，符合 Visual Budget），**客戶裁示前不得宣稱合規**（44 之二十其二第 5 條；BL-0525 Batch D 前置 Gate）；燈的畫法同樣待 Batch D 線框 |
| 資訊擁有權 | `docs/v2/64` §2、`DEC-2026-10-25-01` | 頁面歸屬改；計算擁有權不變（canonical 鏈＝A；禁止配置區段自抓第二套資料，`PROJECT_RULES.md` 13.3） |
| routing | url_path `hld`／`alo`；`/set` 是 OAuth redirect 落點（`BL-0465`） | 合併頁 path 隨對齊批定；`/set` 不得動 |
| Data Health | 44 `SET-8` 總表列數 | 隨對齊批 |
| 藍圖與 BACKLOG | 藍圖 §3.2／§3.3、§7 批 3／批 4；BL-0486、BL-0487 | 合併為 Batch D（兩列列尾補記） |

### 6.2 Google 帳號控制位置

- 處置：桌機固定左側、手機進導覽抽屜或精簡控制（44 之二十其三第 1 條）；只改位置。
- 不撞：OAuth scope（J-1 唯讀四項）；唯讀。
- ⚠️【未驗】從非 `/set` 頁發起登入、登入後回原頁，是否要動 callback handler 或 state（13.2 首段禁改 callback；J-2 state／PKCE fail closed）。調查組未讀 `infra/oauth.py`、`ui_v2/set/source.py`。**實作批（Batch F）先查證；需要動 callback 時再開 Gate**，本 PR 不定案。

### 6.3 Sheet selector

- 處置：情境式，放在使用該 Sheet 的頁面（44 之二十其三第 2、3 條）；Active Sheet 的狀態語意全留。
- 被 supersede 的位置性字句（`DEC-2026-10-29-06` 逐筆）：`DEC-2026-10-25-02` CAP-GATE-02「唯一 owner」「其他頁不得有 selector」；`-25-04` (1)「其他頁不放 Sheet selector」；`-25-01` 唯一擁有者表的頁面歸屬；J-13 的「前往 ⚙️ 設定」；58 U-43 與 44 之十六其三隨之讀作歷史。
- ⚠️ 仍待另案：「候選清單 ▼」能不能讓使用者選，取決於 `docs/v2/62` CAP-GATE-05（候選池＝選股池還是觀察清單）與 J-4、J-7（選股池是部署來源）；「加入候選」＝寫入，受 J-6 第一階段唯讀拘束。

### 6.4 找基金（Gate 2 方案 A、Gate 5）

- 處置：第一階段唯讀＋只在本次瀏覽生效的暫時篩選；候選清單不是前提、可讀不寫；搜尋來源未核准 → `◇ 資料未備`，不得以候選池缺失冒充（44 之二十其四）。44 之二其零「存了才算」在第一階段改由暫時篩選生效。
- 現況（【文】【執抽查】）：B 線沒有搜尋鏈呼叫——`git grep -l -e search_funds -e tdcc_search_fund 02615e41 -- ui_v2 services/v2_tables` 實跑無輸出（【執】2026-10-29）；`ui_v2/readonly.py::PHASE1_HIDDEN_INPUT_CODES` 含 `EXP-1`、`EXP-4`、`EXP-5`。
- Data Source Decision Gate：登記在既有 BL-0397（CAP-GATE-06、-07 已在該列），不另開新列；不新增外部來源。

### 6.5 設定頁瘦身

- 處置：只留低頻全域功能（44 之十九其一之二第 4 條、之二十其三第 5 條）；隨 Batch F。

### 6.6 🤖 AI 投資總結的入口形式（**待單一最小 Gate**，BL-0526）

> **【2026-10-29 已裁示：方案 C（`DEC-2026-10-29-07`，客戶；逐字存檔 `docs/evidence/decisions/2026-10-29_batch_a_rulings.md`）。BL-0526 closed。】** 下方標題的「待單一最小 Gate」、Gate 草稿與方案表是裁示前的原文，保留作歷史（有意識的狀態更新，不是漏刪）。客戶採用的內容比草稿再收緊兩點：各頁入口至多一個 local AI summary 或一個「查看 AI 判斷」鏡像入口，且必須是同一份 Decision Digest 的 slice、與 🤖 結論一致、不另呼叫 prompt；🤖 頁只回答「現在怎麼看、主要原因、最大風險、是否需要行動」，不做成資料牆。啟用時點維持草稿推薦的綁定 Phase 7：Phase 7 實作 One AI Brain 時才加入頂層導覽，目標 5 項（🌍、💼、🔍、🤖、⚙️）。正式條文：`docs/v2/67_ai_action_vocabulary.md` 第 6.1 節；44 之二十其一第 2 條行尾加註。Batch A 不改 `ui_v2/app_preview.py::PAGES`、不改頁數頁序守衛、不實作 One AI Brain。

**Gate 題目（商業語言，草稿）**：「AI 投資總結」要放在哪裡，才能讓你在電腦和手機上都一眼找到，而且全站只有一份結論？

| 方案 | 內容 | 優點 | 缺點與風險 |
|---|---|---|---|
| A 獨立頂層頁 | 🤖 成為一個主頁（四頁內容頁＋🤖），各頁不放 AI 文字 | 手機底部導航與桌機左側都有固定入口；一頁一份輸出，跨頁一致最容易驗 | 要改 `DEC-2026-10-27-25`「殼層、不計塊」的性質；Brain 未做好前頁面會是空的 |
| B 維持殼層右欄 | 桌機右欄；手機在各頁收合 | 不改 IA、不改 `-25` | 手機沒有集中入口；右欄每頁重畫，看起來像每頁一套 AI；要改殼層守衛；不符客戶「集中入口」的手機那一半 |
| C 並存 | 🤖 頁是唯一整合輸出；各頁至多 1 個入口，只鏡像本頁那一句＋前往連結，不呼叫 AI、不另生文字 | 集中又就近；符合 44 之十八其二「至多 1 個 AI 摘要入口」字面；鏡像可用測試鎖住 | 要改的條文最多；入口若自己生文字就退化成每頁一套 AI |

**總管推薦：C**，分兩步：這次 Gate 只定形式；🤖 頁等 Phase 7 的 Digest 契約與前五項（非方向性）能產出後才掛進導覽，在那之前不放空頁。理由：手機只有頂層頁做得到集中入口；四頁內容頁＋🤖 仍是 5 個底部入口，不增加 390px 截斷風險；「一份輸出、入口只鏡像」比「右欄每頁重畫」容易驗；啟用綁 Phase 7，就不會在契約前寫 prompt（客戶第十五節）。（Gate 草稿出自調查組 3，推薦方案由總管定；本 PR 不改頁數守衛、不改 `PAGES`。）

---

## 7. Visual Fidelity Gate 的截圖工具鏈（客戶已裁示兩層；工具鏈待建）

**裁示（第三則 Gate 第 4 項）**：正式確認＝production-like Cloud screenshot；CI deterministic screenshot＝自動安全網，不取代正式確認（44 之十九其九第 7 條）。

| 工具 | 現況 | 限制 | 來源 |
|---|---|---|---|
| Chromium 與 Node playwright | 本機存在（`/opt/pw-browsers`、全域 `playwright@1.63.0`） | 可對任何可達 URL 截 desktop／390 | 【碼】 |
| Python streamlit | 系統 python 無；本 session 的暫存依賴目錄可 import，版本 1.66.1，高於 `requirements.txt` 上界 `<1.60.0` | 版本不符，不算 production-like；本組未嘗試起服務 | 【碼】【執】 |
| `tests/ui_v2/_ui_v2_chromium.py`、`tests/ui_v2/test_live_390_page.py` | 現成的起服務與 390 量測骨架（fixtures 資料、不打網路） | 只量 DOM、不截圖、不比對藍圖 | 【碼】 |
| CI slow lane（`.github/workflows/pr-check.yml` job `slow-tests`） | 有瀏覽器、有 streamlit | `continue-on-error: true`（紅了不擋 merge）；沒有上傳 artifact 的步驟（【執】讀 `02615e41` 該檔確認） | 【碼】【執抽查】 |
| 既有截圖 | repo 內零張 `.png`（`git ls-tree -r --name-only 02615e41` 篩 `.png` 為 0，【執】2026-10-29 重跑） | 沒有 baseline、沒有驗收截圖存放處 | 【碼】【執抽查】 |
| production-like 頁面 | B 線 Streamlit Cloud 預覽站（入口 `ui_v2/app_preview.py`） | URL 不在 repo；真資料要該 app 的 Secrets | 【碼】 |

**落地路徑（Batch A 第 3 項）**：(1) **正式確認**：總管或客戶提供 B 線預覽站 URL、放行該網域的網路存取，以 Node playwright＋Chromium 截桌機與 390；這是操作前提，不是新的產品 Gate。(2) **自動安全網**：CI 加一支 deterministic screenshot 步驟（固定測試資料）並上傳 artifact；slow lane 的 `continue-on-error` 是否要對這一支收緊，屬 CI 設定，由實作批判斷並寫進 PR。在正式確認做完之前，UI PR 寫「Visual Fidelity Gate 未執行」，不寫通過。

### 7.1 Batch A 落地現況（2026-10-29；`DEC-2026-10-29-07`）

| 項 | 落地 | 驗過的是什麼 |
|---|---|---|
| Cloud Preview URL | 登記在 `tests/visual_fidelity/vf_config.py::CLOUD_PREVIEW_URL`（程式可讀的單一位置；公開網址，不含 credential）。守衛：同檔單元測試釘住「只在這一處」 | 單元測試（本機與 CI） |
| 兩層標示 | `config.CI_FIXTURE_LABEL`＝「CI fixture screenshot ≠ production-like Cloud screenshot」；CI 截圖檔名前綴 `ci-fixture`、artifact 名 `ci-fixture-screenshots-NOT-production-cloud`、報告第一行都帶標示；Cloud 截圖前綴 `cloud-preview`，兩層不混用 | 單元測試與 workflow 解析測試 |
| A. CI deterministic screenshot | `tests/visual_fidelity/test_ci_fixture_screenshots.py`（Playwright／Chromium、固定 fixtures、不打外部網路、desktop 1280x800 與 390x844、每畫面截兩次比對決定性、基本 layout 檢查 V1～V8）＋ `.github/workflows/pr-check.yml` 新 job `visual-fidelity-safety-net`（`actions/upload-artifact@v4`）。**非阻擋**（`continue-on-error: true`）：hard 檢查（例外、程式碼區塊外露、水平溢出）會轉紅，契約缺口（圖在首屏、chips 數）只寫進報告，因為今天的頁面尚未套用呈現契約，那是 Batch C～F 的工作；新建的 primitives 展示頁則全部檢查都是 hard | 本機以 Python playwright 與本機 Chromium 實跑過六個情境的截圖與檢查；CI job 本身待 PR 的 CI 結果 |
| B. Streamlit Cloud screenshot | `tests/visual_fidelity/cloud_capture.py`（參數化 URL、desktop 與 390px；預設不在 CI 跑，只在手動 `workflow_dispatch` 時嘗試）。只有明確的網路層錯誤（`net::ERR_*`）才輸出並寫入「production-like Cloud capture blocked by current environment network policy」、exit 0；`Timeout`／`403` 輸出「無法判定（not determinable）」、exit 3；休眠頁或找不到 app 容器輸出「未擷取」、exit 4；擷取成功前會檢查頁面確實是 app 內容（Community Cloud 的 app 在 iframe 內，逐框架找） | 本機實跑：目前執行環境連不到該網域（`curl` 回 000；playwright 回 `net::ERR_TUNNEL_CONNECTION_FAILED`），腳本走到 blocked 分支。**尚未取得任何 production-like 截圖** |

**Cloud 正式確認的狀態**：production-like Cloud capture blocked by current environment network policy（2026-10-29）。依客戶裁示不停批、不重複向客戶要 URL；環境放行後執行 `python tests/visual_fidelity/cloud_capture.py --out <目錄>`（或手動觸發 workflow）補正式 Cloud confirmation。在補上之前，UI PR 寫「Visual Fidelity Gate 未執行」，不寫通過；Batch A 本身不改任何可見畫面，Visual audit 註記「無可見變更」。

**沒做的**：像素 baseline 比對（repo 內沒有基準 PNG，第一張要在有人確認「這就是對的畫面」之後才能存；那個確認就是 Cloud screenshot）；VFG 12 項中需要人判斷的項（三眼原則、圖文比例、資訊密度）。

---

## 8. Decision Digest 與 One AI Brain 的盤點（正式條文在 67 第 5～7 節）

### 8.1 落點的選擇

正式條文放在 `docs/v2/67_ai_action_vocabulary.md`：它是 One AI Brain 的現行正式規格（`DEC-2026-10-27-18` 落點，客戶裁示的語意邊界 SSOT）；Decision Digest 是 Brain 的輸入層，同一份才不會有兩套 AI 規格。`docs/v2/54` 自述 Non-production、schema「Phase 7 再定」，不當正式落點；本檔只放盤點與計畫。（執行組判斷，可推翻）

### 8.2 既有 AI 實作（客戶第十六節 Stop Gate；【AI】，單組讀碼，靜態可達性未跑 app）

| # | 位置 | 現況 | 初判 |
|---|---|---|---|
| 1 | `services/ai_prompts.py::build_structured_summary_prompt`＋`ui/helpers/ai_summary.py::render_ai_summary_widget` | 吃 UI 組好的文字快照、每 Tab 各自呼叫 AI；沒有逐項 provenance、freshness 只有選填說明 | replace（等於 UI scrape、各頁各一套 AI） |
| 2 | `services/ai_service.py::analyze_portfolio_mk_advisor`＋`services/ai_prompts.py::build_mk_advisor_prompt` | prompt 要 AI 列「該減碼」標的、給配置比例、「提高現金比例至 25%+」（【執】以 `git grep -n "25%" 02615e41 -- services/ai_prompts.py` 實跑命中那一句） | replace，不可 reuse；與 `DEC-2026-10-27-14`、`-22`、`-40` 牴觸；A 線靜態可達 → 只登記（BL-0528） |
| 3 | `ui/tab3_portfolio.py::_render_tab3_ai_summary` | 投資邏輯在 UI 組裝；權重「invest_twd 缺則 0、全缺等權」 | replace |
| 4 | `ui/views/page_01_macro.py::_detail_ai`／`_ai_snapshot` | 缺值寫「—」不寫 0、完整率不足不生成（原則可參考）；餵舊綜合健康度單一總分 | replace |
| 5 | `ui/helpers/fund_grp_health/ai.py`、`ui/tab1_macro_ai.py`、`ui/helpers/io/freshness.py::_render_data_health_ai` | 各自組快照呼叫 AI；後者是資料健康、不屬投資判斷；`ui/tab1_macro_ai.py` 沒找到 production caller | replace／登記即可 |
| 6 | `mcp_server/tools_macro.py::build_macro_snapshot` | 給外部 AI 的 dict 含 `composite_score`、`verdict.action`、`action_light`（【執】`git grep -n "action_light\|verdict" 02615e41 -- mcp_server/tools_macro.py` 命中） | 不可當 Digest 原料；只登記（BL-0528） |
| 7 | `infra/llm.py::call_llm`、`services/ai_service.py::gemini_generate` | 多 provider、多金鑰輪替的傳輸層 | reuse 候選（只當傳輸層） |
| 8 | B 線 `ui_v2/**`、`services/v2_tables/**` | 沒有任何 AI 呼叫（【執】抽查只見金鑰名遮蔽清單） | — |

`build_ai_summary` 在 repo 內不存在（`git grep -n "build_ai_summary" 02615e41` 實跑無輸出，【執】2026-10-29），「Decision Digest」一詞也查不到（`git grep -n -i "decision digest" 02615e41 -- '*.md'` 實跑無輸出，【執】）。

### 8.3 Digest 素材與缺口

逐項對照與缺口見 67 第 5.3、5.6 節（不在此重抄）；登記 BL-0527。守衛缺口：「AI 不讀畫面（不是 UI scrape）」「AI 輸出不回寫 canonical 表」兩類，repo 內沒找到專門的條文或測試（【AI】，「沒找到」只代表那幾條字串查不到），列入 BL-0527，Phase 7 實作批之前補。

### 8.4 整合順序的差異

`DEC-2026-10-27-18` 有「Missing／freshness」段，客戶第三則第八節列的順序沒有；67 第 6 節第 2 點保留該段（-18 是正式裁示，客戶同節說維持正式方向）。

---

## 9. Implementation 分期與 Batch（客戶第二則第二十節、第三則第十五節；每批 ≤3 個實際工作項，`PROJECT_RULES.md` 13.4 第 5 條）

| Phase／批 | 工作項（≤3） | 前置 | 驗收（第二則第二十一節八項＋Visual audit 九問） |
|---|---|---|---|
| **Phase 1**（本 PR） | Presentation Contract／VFG（44 之十九）；IA amendment（44 之二十）；Decision Digest／One AI Brain 最小契約（67 第 5～7 節） | — | 1 組獨立稽核（治理與 SSOT 等級）；CI |
| **Phase 2＝Batch A** helper／tests migration | (1) T1～T6、T8 依新測試契約改寫（不刪資訊、不改產品行為）；(2) 頁首狀態行與核心卡的 page 層呈現責任拆分點（只動 page，不動模型）；(3) 截圖工具鏈落地（第七節兩層） | 預覽站 URL 與網路放行（只擋 (3) 的正式確認） | targeted tests、regression、CI、1 組獨立稽核；本批不改畫面時 Visual audit 註記「無可見變更」 |
| **Phase 3＝Batch B** 共用元件 | (1) chart card；(2) metadata／status chip；(3) detail 展開區＋Missing placeholder（含圖表 placeholder） | 無（44 之十九已定）；符號照 44 現行 | 同上＋T10＋desktop／390 截圖 |
| **Phase 4＝Batch C** 🌍 reference implementation | (1) 段序改為圖表優先、Primary 1＋Secondary ≤3（X-25、T1）；(2) 圖卡改 chips＋「▸」（X-26、T9）；(3) 核心卡 `answers`／`detail_lines` 下沉（X-27） | 無；BL-0517 三張新圖卡不在本批（方案 A 草稿另批）〔2026-10-30：草稿已寫成，`docs/v2/72_mkt_wireframe_batch_c.md`，~~待客戶拍板；拍板前不開實作~~ → **同日客戶核准 D1～D7（`DEC-2026-10-30-01`），Batch C 實作批已做，見下方「Batch C 實際做了什麼」**；狀態更新，不是漏刪〕 | 八項全做＋Visual audit 九問 |
| **Phase 5＝Batch D** 💼 我的資產 | (1) 合併頁 IA（含一枚結論燈的畫法、層 3／層 4 各超 2 塊的處置〔線框送客戶裁示〕、頁序頁名對齊批）；(2) 情境式持倉資料來源選擇；(3) portfolio visuals（Primary 1＋Secondary ≤3） | 線框草稿先行（新元件與合併頁）；**層 3／層 4 超限的客戶裁示**；BL-0526 若影響頁數，對齊批等它 | 八項全做 |
| **Phase 6＝Batch E** 🔍 找基金 | (1) 候選清單解耦；(2) 暫時篩選（只在本次瀏覽生效）；(3) search／filter／compare 呈現 | BL-0397 Data Source Decision Gate（未核准前搜尋區 `◇ 資料未備`）；CAP-GATE-05 | 八項全做 |
| **Batch F** ⚙️ 設定＋帳號位置 | (1) 設定頁瘦身；(2) Google 帳號左側固定與手機控制；(3) desktop／mobile 互動 | callback 查證（6.2，可能再 Gate） | 八項全做 |
| **Phase 7** One AI Brain／Decision Digest／AI 投資總結 | 依 67 第 5、6 節；先補 BL-0527 缺口與守衛 | ~~BL-0526 入口形式~~（→ 已裁示方案 C，`DEC-2026-10-29-07`；Phase 7 才加入導覽）；BL-0495 Risk Cap；BL-0496 減碼 trigger；`AI-1`、`AI-3` | Digest 契約定義前不寫 prompt 或 LLM glue |

**Batch A 實際做了什麼（2026-10-29；`DEC-2026-10-29-07`；上表 Phase 2 列是計畫，保留）**：
1. **測試契約遷移**：T2、T3、T4（hld、exp）已依新測試契約改寫（詳見 4.1）；T8 以新增情境補射程。
2. **共用 presentation primitives**（原列在 Batch B，客戶 2026-10-29 要求 Batch A 先建）：`ui_v2/presentation.py`（純函式：chip、至多 5 枚 chips、圖卡模型、一句摘要、detail 四組、Missing 模型）與 `ui_v2/presentation_view.py`（Streamlit 畫法）；單元與畫面測試 `tests/ui_v2/test_presentation_logic.py`、`test_presentation_page.py`（T10 的兩半）。**尚未被任何頁面呼叫**（守衛釘住；頁面套用是 Batch C～F），所以不改任何畫面。
3. **截圖工具鏈**：見第 7.1 節。
本批實際工作項為上列三項，未超過每批 3 項；頁首狀態行與核心卡的 page 層拆分（原 Phase 2 第 (2) 點）依客戶「不重寫五頁」順延到 Batch C。**下一個唯一接手點**見 `docs/HANDOFF.md`。

**Batch C 實際做了什麼（2026-10-30；`DEC-2026-10-30-01`；上表 Phase 4 列是計畫，保留）**：
1. **🌍 頁視覺層級**（`ui_v2/mkt/overview.py` 純函式模型＋`ui_v2/mkt/page.py` 畫法）：status chip（一行，既有字樣）→ 一句主判讀（不放頁級日期）→ Primary（五序列切換、一組期間切換、圖 300px）→ Secondary（風險 VIX／國際 S&P 500／利率與信用，各為迷你折線＋3 枚 chips；「利率與信用」內部切換期限利差／信用利差／政策利率）→ 依據卡 `MKT-1`～`MKT-3`（位置後移）→ ③ → 「▸ 尚未取得」群組（EPS×PE 排最前）→ 「▸ 各項資料狀態」→ ④ 詳細資料。X-25（段序）、X-26（圖下常駐小字）、X-27（核心卡 `answers`／`detail_lines`）中，X-25、X-26 已處理；X-27 的 `answers`／`detail_lines` 仍在依據卡內，**未下沉**（見 HANDOFF，後續批次再議）。
2. **Primitives 最小擴充**：`chart_card_model` 的摘要句可省略（`summary=None`；給了字串仍須是一句）、`presentation_view.inject_css` 公開。
3. **測試與 Visual Fidelity**：T1、T9 遷移（舊斷言劃線保留理由）；T6＝`tests/ui_v2/test_sections_page.py` 新增 🌍 有 Data View 的新段序測試（舊四段順序測試對無 Data View 情境照舊成立）；T13＝`test_bl0345_dev_notes_page.py`、`test_plain_trend_page.py` 把新 detail／尚未取得／次要圖展開區與每個 Primary 序列、利率與信用子序列切換後的畫面納入開發註記與工程字樣掃描（皆讀過原測試內容後遷移，無需 skip_expanders）；`tests/visual_fidelity` 對 🌍 頁 V4～V8 升為 hard 並新增 M1～M6（視覺順序、Secondary ≤3、無頁級日期、Secondary 不高於 Primary、手機緊湊列、無圖表牆）。**CI fixture screenshot ≠ production-like Cloud screenshot**；Cloud capture 仍受環境網路政策阻擋，**Visual Fidelity Gate 的正式確認尚未執行**。

**Batch D 實際做了什麼（2026-10-30；`DEC-2026-10-30-02`；上表 Phase 5 列與下方裁示指標是計畫與前置，保留）**：
1. **💼 我的資產頁**（`ui_v2/asset/`：`overview.py` 純函式模型、`page.py` 畫法、`theme.py` 沿用 alo 色票；預覽入口 `app_preview.py::page_ast`，`url_path` `ast`）。由上而下：頁頂「持倉資料來源」一列（D-8；已登入重用設定頁既有 picker〔`set_source.picker_live`＋`set/live.py::picker_view`，widget key 與動作白名單不動〕，未登入／無 Active 沿用 `active_gate` 既有字樣「⬜ 尚未選定持倉資料來源」與「前往 ⚙️ 設定」；**OAuth 一個檔都沒動**）→ 頁名與提問句（D-9 沿用）→ 主要原因／另有，其後兩側各一列資料日（「資產配置　資料截至 ‹日期›」「持股明細　資料截至 ‹日期›」；字樣取 `page_health` 單頁頁首同一組；沒有日期寫「—」，不補、不借另一側的、不合成一個頁級日期；稽核回修，見下）→ summary strip（總資產／總損益／報酬／配息，一個容器、四格，一律 `◇ 資料未備`，手機 2×2；為什麼／來源／限制／去哪補在其下 `▸`；D-5A 沒有任何彙總計算）→ 一句主判讀（C2：「持有 ‹n› 檔基金；目前最大配置差距在 ‹類別›。」〔⚠️ 後續更正，見下〈SF-2 還原第一輪的嚴格主判讀〉（`ae8c32a0`）：任何類別沒評估到時，這個模板不用，一律改寫「配置差距無法判定」，不再點名類別；N-4 審查修訂，有意識的補註，不是漏刪〕；`n` 取 `sections.hld_holding_count`〔`HLD-2` 實際列出的不重複基金檔數，與門檻、燈色無關；稽核回修前取 `hld_count_values`〕，類別取 `ALO-0` 已算出的 `_leaders`〔並列全列〕；任何一值取不到照實「持有檔數無法判定」「配置差距無法判定」；各類別皆在容許帶內時照 `ALO-0` 既有字，但 `ALO-2` 有任何一列沒評估到差距〔`_diff` 為 None：目標比重留空、持倉類別沒有目標、基準值缺〕時一律寫「配置差距無法判定」）→ Primary〔資產配置 現況 vs 目標：`ALO-0` 一行、單頁頁面頂端那一行灰字（`top_lines`，例「目標合計 90%」）、chips〔容許帶、比重基準、資料日；字取 `ALO-1`／`ALO-4` 卡上既有行〕、每類兩條水平條、`▸ 各類別全表‧來源‧限制`＝`ALO-2` 全表、`ALO-3` 入口條照舊〕→ Secondary ×2（基金占比＝`ALO-6`、各檔區間報酬＝`HLD-2`；全列、卡內固定高度垂直捲動、列序沿既有規則、標籤含幣別、不合計）→ ③ 需要注意（`ALO-2` 帶外類別＋`HLD-1`）→ 持股明細（`HLD-0` 一行＋`HLD-2`／`HLD-3`）→ ④ 層 3＝3 個容器（「我的條件」＝`HLD-4`＋`ALO-1`＋`ALO-4`、`HLD-5` 單檔展開、`ALO-5` 匯出）、層 4＝2 個容器（「持股明細」＝`HLD-6`＋`HLD-7`＋`HLD-8`、「配置明細」＝`ALO-6`＋`ALO-7`）；多塊容器內各塊以小標題分組、**沒有任何巢狀展開區** → `▸ 尚未取得`（九項，點名在標題列）→ 頁尾（兩區「不負責什麼」都保留，只去完全相同的句子與指向本頁自己的半句「，單檔績效請到我的持股」）。
2. **為了共用而抽出（單頁 `render` 行為不變）**：`alo/page.py`、`hld/page.py` 各抽 `prepare_live`（載入→組模型→資料狀態收集→收起／收合判定，原樣搬、順序與副作用不變）、`LiveFailed`、`record_live_error`；層 3／層 4 的 `_render_*` 多一個 `flat=False` 參數（預設＝原展開區）；`active_gate` 抽 `record_no_active`／`render_no_active_status`；`presentation_view.flat_block`（小標題段落）；`sections.hld_count_values`（`hld_counts` 改由它組字串）、`sections.hld_holding_count`（稽核回修再從 `hld_count_values` 抽出）；`ALO-0` block 多一個 `_leaders` 鍵（`conclusion_light` 本來就算出，只是原本沒放進 block）。
3. **導覽**：`app_preview.PAGES` 由五項改四項（🌍、💼 我的資產、🔍、⚙️；44 之二十其一的正式頁序）；`page_alo`／`page_hld` 刪除；單頁入口 `app_alo*.py`、`app_hld*.py`（示範與 live）保留不動；設定頁總表的「前往該頁」`hld`／`alo` 兩列都指向合併頁。
**D-3 暫行狀態（D-3 Formula Gate 落盤前）**：**沒有任何 page-level combined light、合讀規則、排序或聚合**；`HLD-0` 與 `ALO-0` 各自維持既有燈、字樣、判定一字不改，`ALO-0` 放在 Primary 區開頭、`HLD-0` 放在持股明細區開頭。一句主判讀不是燈（只是兩個既有值的描述）。Gate 落盤並經客戶裁示後，才能把兩枚燈合成頁燈。
**測試遷移**：T4（精確展開區數量）與 3a／4a 容器衝突 → 單頁測試不受影響（單頁 `render` 沒改），合併頁新測試改驗「容器內各塊有小標題、block ID 全保留、不巢狀」（`tests/ui_v2/test_ast_page.py`、`test_ast_overview_logic.py`）；T7（帳號與 Sheet 位置）：本批只做頁頂 selector，登入卡與設定頁 picker 仍在設定頁、沒動；T6／預覽入口：`test_preview_entry.py`（頁序改讀 44 之二十其一、`alo`／`hld` 注入改由 `page_ast` 的 `alo_live`／`hld_live` 比對、`_on_page` slug）、`test_shell_logic.py`、`test_shell_page.py`（五項→四項；底部導覽寬度改用未進位寬度加總，4×97.5px 舊寫法 round 後多 2px 誤紅）、`test_ui_v2_live_import_guard.py`（白名單只多 `ui_v2.asset.page`）、`test_preview_page.py`／`test_p15_load_failure_page.py`（預覽的 `alo`、`hld` slug 對到合併頁 `ast`，斷言內容不放寬；合併頁的 `alo_live`／`hld_live` 與兩個 live 入口同物件另驗）、`test_readonly_write_surface_guard.py`（`strip_write_controls` 隨 `prepare_live` 移位，順序性質拆兩半驗，合併頁另驗兩側 `prepare_live` 先於任何畫塊）、`test_presentation_logic.py`（primitives 使用者清單簽名多合併頁與 `flat_block` 的兩個單頁檔）；`tests/visual_fidelity`：`ast` 情境 desktop／390px 截圖，V1～V7 與新增 A1～A6 全部 hard（順序 selector < summary < 主判讀 < Primary < Secondary、Secondary 恰兩張、summary 一容器四格、無巢狀展開區、手機 summary 緊湊、清單固定高度捲動）。**CI fixture screenshot ≠ production-like Cloud screenshot**；Cloud capture 仍受環境網路政策阻擋，**Visual Fidelity Gate 的正式確認尚未執行**。
**稽核回修（2026-10-30；獨立稽核指出、本組逐項對碼後修掉；`DEC-2026-10-30-02` 的「合併只改呈現、不丟 block ID／source／as_of／missing／reason／provenance」）**：
- **頁級資料日**：合併頁原本只畫主要原因／另有，單頁頁首的「資料截至 ‹日期›」只剩收合的層 4 裡有，配置側只剩 Primary chip 的短寫法「資料日 09-23」。現在兩側各一列（`overview.data_date_line`、`page.py::_render_header_state`）；載入失敗的那一側寫「資料截至 —」並在該列下畫完整的一句狀態。
- **目標合計**：單頁 `alo/page.py::render` 畫的 `top_lines` 合併頁原本沒讀；現在畫在 Primary 內（`ALO-0` 一行之後、圖之前）。
- **容器標題帶出狀態**：多塊容器收合時標題原本只列塊名，設定讀不到時單頁標題是「目標輸入卡　—　⛔ 取數失敗」而合併頁看不出來。現在有狀態的塊寫成「標題　—　狀態」（單頁展開區標題同一個字面：`ALO-1` 讀 `sections.alo1_summary`、收合區比照的塊讀它那一行原因、其餘讀 `summary_text`）；判斷「有沒有狀態」讀塊上既有的佔位、紅灰色調或標題句本身的狀態字樣（`overview.STATE_MARKERS`），正常的塊容器標題照舊只列塊名。這是字樣判斷，不是新判定。
- **主判讀的 n**：原本取 `hld_count_values`，門檻未設、燈紅、n＝0 時回 None，於是持股卡明明列著 3 檔也寫「持有檔數無法判定」。現在取 `hld_holding_count`（`HLD-2` 實際列出的檔數）；沒有任何一檔被列出才寫無法判定，不寫 0。
- **失敗優先於尚未設定**：一側載入失敗、另一側沒有 Active 時，原本整頁走「尚未選定」並對兩側都記「尚未設定」，把失敗那一側的記錄覆寫掉。現在只要有一側失敗就不走整頁「尚未選定」，失敗那一側的記錄與錯誤句照留，沒有 Active 的那一側只記它自己；~~兩側都沒有 Active 才是整頁「尚未選定」（原行為）。~~ → 第二輪更正（有意識的更正，不是漏刪）：上句不實。沒有任何一側失敗時，**只要一側沒有 Active 就是整頁「尚未選定」**（`_render` 的 `whole_page_no_active`，parent `aba1ee1a` 的行為）；舊句把這個條件寫成「兩側都」，與程式不符。見下方第二輪 S3。
- **C2 主判讀不複述 `ALO-0` 的「皆在容許帶內」（F-13／`docs/v2/74` A6m 的洩漏路徑）**：`ALO-0` 在目標比重留空、持倉類別沒有目標（例：未分類）時仍寫「各類別皆在容許帶內」，主判讀原本照抄，等於把 missing 讀成正常。這是本次稽核找到、本批修掉的：`ALO-2` 有任何一列沒評估到，主判讀的配置段一律寫「配置差距無法判定」，也不點名「最大配置差距在 X」（最大值取自不完整的類別集合）。`ALO-0` 本身一字沒改，`docs/v2/74` F-13 仍待客戶另裁。 → ⚠️ 文件回修補註（2026-10-30，有意識的更正，不是漏刪）：其中「持倉類別沒有目標（例：未分類）」這一半，`docs/v2/74` v6 另立 **F-19**（有值但沒有目標的類別算不算 A6m）送客戶裁示，推薦算 A6m，與本條現行程式一致；客戶若裁定不算，`overview.has_unevaluated_category` 要改回（排除有值、沒有目標的列）。 → ~~⚠️ 第二輪更正（S5，總管讀法，待客戶確認；有意識的更正，不是漏刪）：本條「一律寫配置差距無法判定、也不點名最大配置差距在 X」範圍說過頭了，現在只擋「`ALO-0` 寫各類別皆在容許帶內」那一句；`ALO-0` 已點名類別（A7）時主判讀照 parent 點名。見下方第二輪 S5。~~（文件回修劃線，有意識的更正，不是漏刪：這句在 `4dec17e0` 為真，`ae8c32a0` 還原後不再成立，現行以下一句第三輪更正為準） → ⚠️ 第三輪更正（SF-2，有意識的更正，不是漏刪）：第二輪 S5 已還原，本條原先的嚴格行為恢復——`ALO-2` 有任何一列沒評估到，主判讀的配置段一律「配置差距無法判定」，不論 `ALO-0` 寫皆在帶內或已點名類別，見下方第三輪 SF-2。
- **小項**：`hld_count_values` 的 `ValueError` 原本在 `_prepare` 之外，一拋兩側一起炸；~~現在 `_prepare` 接住 `prepare_live`（含 `sections.hld_counts`）拋的 `ValueError`，只有持股這一側改畫狀態、原文照記進進階診斷與 log；~~ → 第二輪更正（S2，有意識的更正，不是漏刪）：接得太寬，現在只接 `LiveFailed` 與 `sections.HoldingCountsInconsistent`（`hld_counts` 計數不成立專用的 `ValueError` 子類別），只有持股這一側改畫狀態、原文照記進進階診斷與 log；其他 `ValueError` 照舊浮出（見第二輪 S2）；收合區比照的小標題原本沒帶 `data-block`（`ALO-6`／`ALO-7` 收合時 block ID 少兩個），現在帶；規則順序改成與單頁一致（`HLD-4`／`ALO-1` 先於收合區比照）；`overview._nonblank` 拿掉，空白行交給 `P.detail_model` 當場 `ValueError`；`return_rows` 缺「區間報酬率」那一格的檔改為列出、寫 `◇ 資料未備`，不再靜默丟列；`prepare_live` 兩份 docstring 的路徑改成 `ui_v2/asset/page.py`、`alo/page.py::prepare_live` 的死變數拿掉；`test_readonly_write_surface_guard.py` 的 `prepare_live` 順序守衛補上「在正式模式分支」的檢查（註解與守衛一致）；`plain.PLAIN_FOOTERS` 的 `mkt`／`exp` 兩句與 `PREVIEW_NOTE` 的「我的持股」「資產配置」改指向「我的資產」；一側載入失敗時完整的一句狀態只在頁首畫一次，各區段改畫既有短句「⛔ 取數失敗」（沒有 Active 的一側畫「⬜ 尚未選定持倉資料來源」），失敗的是哪幾塊由容器標題列點名。
**稽核回修第二輪（2026-10-30；對 `9d0da7d2` 的獨立稽核，本組逐項對碼、實測後修掉）**：
- **B1（阻擋）主判讀把「部分讀到的持倉」寫成完整**：`ui_v2/hld/live.py` 在部分分頁被略過（`holding_tables["skipped_tabs"]`）時照交持倉並放一筆 `errors["holding"]`；`HLD-2` 照列讀到的幾檔，`sections.hld_holding_count` 就數出 n，主判讀寫「持有 2 檔基金」，同一畫面的頁首／持股區卻是紅的「持倉取數失敗」。現在 `hld/page.py::prepare_live` 的回傳多一個 `holding_error`（原樣讀既有旗標 `dataset["errors"]["holding"]`，HLD 自己的判定、`HLD-2` 的列一個都沒動），`asset/page.py::_prepare` 用 `overview.hero_holding_count(n, holding_error)`：持倉來源有錯時 n 一律為 None → 「持有檔數無法判定」（D-10：資料不足照實說）。只是門檻未設（沒有 `errors["holding"]`）仍照 `HLD-2` 列出的檔數寫。測試：`holdfail_nothr` 的兩處舊斷言（`test_ast_page.py`、`test_ast_overview_logic.py`）反向並留刪除線註解；稽核探針（3 檔掉 1 檔 ＋ `errors["holding"]`）寫成 `test_稽核探針_…`。
- **S1 容器標題漏掉的狀態**：「未設定」「⬜」「未指派 N 檔」「門檻 0 列」原本不在 `STATE_MARKERS`，所以單頁標題「目標輸入卡　—　⬜ 未設定；容許帶：⬜ 未設定」在合併頁只剩「目標輸入卡」（`first`、`notarget`、`notol`），`ALO-4`「未指派 1 檔」（`unbkt`）、`HLD-4`「門檻 0 列」（`nothr`）同。現在先看塊上既有的旗標（`overview.STATE_LIST_FLAGS`：`unset_lines`、`unassigned_lines`、`bucket_unset_lines`、`mismatch_lines`，各自是 `ALO-1`／`ALO-4` 塊上本來就有的未到位串列），再看字樣（`STATE_MARKERS` 補「未設定」〔含原有的「尚未設定」〕、`⬜`、「門檻 0 列」）。`HLD-4` 的「門檻 0 列」塊上沒有旗標（`threshold_rows` 會放一列空白輸入列，數量不等於門檻數），只能靠字樣。測試：`tests/ui_v2/test_ast_page.py` 對 ALO 16 個、HLD 17 個 fixture 情境 × 8 個多塊容器內的塊逐一掃描（`F.SWEEP_SCRIPT`），金標準 `STATE_GOLDEN` 是手寫的（不由 `STATE_MARKERS` 推導），正向（單頁標題帶狀態 → 合併頁一定帶、且與單頁同一句）與反向（正常的塊不得多出狀態）都驗；五個稽核點名的案例另驗整句容器標題。
- **S2 `_prepare` 接太寬**：原本接 `prepare_live` 拋的所有 `ValueError` 並畫成取數失敗，但 `prepare_live` 在 try 之外的東西（檔頭註明「是本檔的 bug，不得畫成取數失敗」）出的 `ValueError` 也會被吞成取數失敗。現在 `sections.hld_count_values` 的計數不成立改拋專用的 `sections.HoldingCountsInconsistent`（`ValueError` 的子類別；單頁畫面不變，但有兩處記錄面的差異，見下方第三輪 N-a），`_prepare` 只接 `LiveFailed` 與它；其他例外照舊往上浮出，由 `render` 的 `_record_collect_failure` 記一筆再拋（同單頁 `guard_page`）。`hld/page.py::record_live_error` 補上 `_log.warning`（體例同 `alo/page.py`）；`_prepare` docstring 改正。
- **S3 整頁「尚未選定」只記一側**：一側沒有 Active、另一側載入成功時，整頁畫成「尚未選定」，但總表只記沒有 Active 的那一側，另一側還留著「載入成功」的記錄。現在整頁畫成「尚未選定」（沒有任何一側失敗、至少一側沒有 Active）時兩格都記尚未設定（parent `aba1ee1a` 的行為）；有一側失敗的混合情形維持第一輪的行為（失敗那側記失敗、沒有 Active 的那側只記自己）。上方「失敗優先於尚未設定」bullet 的「兩側都沒有 Active 才是整頁尚未選定」是錯的，已在該處劃線更正。
- **S4 沒有 Active 被畫成紅色警示**：混合情形（一側失敗、一側沒有 Active）下，沒有 Active 那一側的區段短句與頁首完整句原本與失敗用同一個紅色 `ast-err`（`role="alert"`），J-13 的三種狀態（有資料／沒有 Active／系統出錯）被畫成兩種。現在 `page.py::_state_div` 對 `no_active` 畫灰色 `ast-status`（`role="status"`，同 `active_gate.render_no_active_status` 的灰與角色）；失敗那一側與純失敗的畫面不變。
- ~~**S5 主判讀的 `incomplete` 蓋掉 A7 點名**：`has_unevaluated_category` 為真時，原本連 `ALO-0` 已點名類別的黃燈情形（A7）也寫「配置差距無法判定」（例：`unbkt`），而下方 `ALO-0` 寫「衛星 與目標差 30.0 個百分點」，主判讀否定了同一畫面上一條已算出的規則結果。**總管讀法，待客戶確認**：`incomplete` 只擋「`ALO-0` 寫各類別皆在容許帶內」那一句（改寫「配置差距無法判定」）；`ALO-0` 點名類別時主判讀照 parent 點名。⚠️ A7 的「N 個百分點」與 `_leaders` 可能建立在不完整的分母上（`docs/v2/74` 的 A7 列 v5 補：A6m 條件 (2) 缺值類別被排出分母），這是 `ALO-0` 的既有缺陷（F-13），本頁不改它、也不複述得比它更多；客戶若認為 A7 在 `incomplete` 時也該無法判定，改回只需把 `hero_sentence` 的 `incomplete` 判斷提到 `leaders` 之前。~~ → 第三輪更正（SF-2，有意識的更正，不是漏刪）：S5 已還原，見下方第三輪 SF-2。
- **N1**：`has_unevaluated_category` docstring 與 `hero_sentence` 註明 A6m 條件 (3)（持倉來源有略過的 ALO 分頁）沒有涵蓋，記在本檔與 `docs/v2/74`。
- **本輪沒新增任何客戶看得到的字樣**：主判讀用的「持有檔數無法判定」「配置差距無法判定」、容器標題裡的狀態句都是既有字面（單頁標題同一句）；新增的只有 CSS class `ast-status`、一個例外類別名與一則 log。
- **已知還沒涵蓋（第二輪，不是漏做）**：(a) `STATE_MARKERS` 仍是字樣判斷，`HLD-4` 的「門檻 0 列」沒有旗標可讀；單頁標題若日後出現不在字表、塊上又沒有旗標的狀態字樣，容器標題會比單頁短（不會多編狀態），`test_S1_*` 的金標準會在新增 fixture 情境時逼人重看一遍，但新字樣本身仍需人看。(b) 單塊容器（`ALO-5`、`HLD-5`）本來就整句畫在自己的展開區標題上，不經容器標題，不在 S1 的範圍；其「目前沒有可匯出的列」是否算狀態沒有裁。(c) `HLD-8` 在 `full` 等情境因塊本身是灰色調（「有值取不到或不適用」）而在「持股明細」容器標題帶出，是第一輪既有行為，本輪沒動。(d) A6m 條件 (3) 與 F-18（BL-0411）仍沒擋（見下方「沒做或沒驗」(4)）。~~(e) `holding_error` 只讀 `errors["holding"]`；`fund_errors`（逐檔淨值／配息取數失敗）不算持倉來源有錯，沿用 `HLD-2` 列出的檔數（本組沒有另外驗證該情形下 `HLD-2` 是否列全部持倉）。~~ → 第三輪更正（SF-1，有意識的更正，不是漏刪）：`fund_errors` 的疑慮已由稽核探針驗證為無害（FACT）：`logic.all_metrics` 不論逐檔取數是否失敗，每一列持倉都產生一組 `HLD-2`，所以 `fund_errors` 不會讓 `HLD-2` 少列；本項不再是未驗事項。真正的缺口在別處，見下方第三輪 SF-1。
**稽核回修第三輪（2026-10-30；對 `4dec17e0` 的獨立稽核，本組逐項對碼、實測後修掉；只動 `ui_v2/asset/`、`tests/ui_v2/` 與本檔）**：
- **SF-2 還原第一輪的嚴格主判讀（取代第二輪 S5）**：`has_unevaluated_category(ALO-2)` 為真（`incomplete`）時，`overview.hero_sentence` 一律寫「配置差距無法判定」，不論 `ALO-0` 寫「各類別皆在容許帶內」或已點名 A7 類別，涵蓋 `partial`、`unbkt`、`nobucket` 與目標留空的 `inband`（`blank_target`）。理由：「目前最大配置差距在 X」是對整個類別集合的最大值宣稱；有類別 `_diff=None`（例：`partial` 的債券有目標但值缺）時，該類別的差距未知、可能才是最大，在不完整的集合上宣稱最大值，等於把 Missing 推成已知（客戶裁示 D-10：不把 Missing 推論成正常；資料不足照實「無法判定」）。`ALO-0` 本身一字未動，仍在 Primary 寫它自己的「X 與目標差 N 個百分點」；`ALO-0` 從不說「最大」，兩者不矛盾。客戶若要放寬為「有 A7 領先者就點名」，是 `hero_sentence` 的一行改動（把 `incomplete` 判斷搬到只包「皆在帶內」那個分支）。第二輪 S5 的「總管讀法、待客戶確認」字樣隨之移除，改由上述理由承擔。測試：S5 舊斷言加刪除線並註明原因，改斷言 `partial`／`unbkt`／`nobucket`／`blank_target` 皆為「持有 3 檔基金；配置差距無法判定。」；還原改動後這幾條測試轉紅，恢復後轉綠（突變驗證）。
- **N-c**：`ast-status` 原本沒有 CSS 規則，只有行內灰色；現在補上與 `ast-err` 相同的字級與邊距（`.85rem`、`.3rem 0`、`overflow-wrap: anywhere`），顏色仍是行內灰色。
- **N-a 單頁記錄面的差異（補第二輪 S2「單頁行為不變」的限定）**：單頁 HLD 在計數不成立時，頁面健康記錄的 `collect_error` 現在是「HoldingCountsInconsistent」，原本是「ValueError」；這只進 log 與記錄、沒有畫在畫面上（`page_health.py`）。另外單頁 `hld/page.py::record_live_error` 新增一則 `_log.warning`。畫面字樣不變。
- **SF-1 「持有 N 檔」的已知缺口（FACT／INFERENCE 分開寫；產品語意，待客戶裁示）**：(FACT，稽核探針) `fund_errors` 無害——`logic.all_metrics` 不論逐檔取數是否失敗，每列持倉都產生一組 `HLD-2`。(FACT，依 F-18／BL-0411) 被丟進 `skipped_holdings` 的列（例：保單分頁缺 `_持倉補充`）根本不會進 HLD，所以主判讀的「持有 N 檔」只數被接受的列，也沒有任何錯誤旗標可讀（`holding_error` 只讀 `errors["holding"]`）；`HLD-2` 與主判讀因此都可能少算而不自知。(INFERENCE) 修法需要把略過原因帶到畫面，屬產品語意（Stop Gate），本組沒有動，等客戶裁示（BL-0411、`docs/v2/74` F-18）。（→ 2026-10-30 客戶已裁、已修，狀態更新，不是漏刪：見下方「D-3 阻擋項修正批」。）
- **本輪沒新增任何客戶看得到的字樣**：「配置差距無法判定」「目前最大配置差距在」皆為既有字面。
**沒做或沒驗（不是漏做）**：(1) D-3 page-level 結論燈（暫停）；(2) D-8 的 OAuth callback 回原頁的 read-only 技術查證（本批沒做、沒改 OAuth；現況：未登入時 selector 列寫「尚未選定」並連到設定頁，登入仍在設定頁）；(3) 新擬字樣待客戶確認：summary `▸` 內四句、`▸ 各類別全表‧來源‧限制`、`持有檔數無法判定`／`配置差距無法判定`、`區間未設`、`N 檔有值`、`N 檔無基準值`、`原幣，不合計`（沿 `HLD-2` 既有「不合計」語意）、`▸ 尚未取得` 內各項一句原因、層 4 容器名「持股明細」與第 8 區標題「持股明細」同名（客戶產品結構與 D-11 兩處都用這個詞，未自行改名）、頁級資料日列的側名沿用「資產配置」「持股明細」兩個既有詞、`mkt`／`exp` 頁尾與預覽說明改指向的「我的資產」；(4) `docs/v2/74` A6m 的第三種情形（~~持倉來源有未讀分頁~~ → 持倉來源有**略過的**分頁；正式模式下 `unread` 一律為假，略過的是標頭格式有誤的分頁；2026-10-30 文件回修更正，有意識的更正，不是漏刪）沒接：`prepare_live` 的回傳不帶 `notes["skipped"]`，主判讀只擋 (1)(2)（→ 2026-10-30 已修，狀態更新，不是漏刪：見下方「D-3 阻擋項修正批」）；(5) `PREVIEW_NOTE` 的「五頁」字樣（導覽已改四項）沒動，`tests/ui_v2/test_preview_entry.py` 把「五頁皆讀真資料」釘為必含字樣，改它屬字樣變更，待客戶確認；(6) 沒有看過 production Cloud 的真實畫面與真資料；(7)（2026-10-30 文件回修補登）設定頁「各頁資料狀態總表」每列的「前往該頁」連結仍用舊頁名：`page_health.TEXT_GOTO`「前往{page}」配 `page_health.PAGE_NAMES`，畫成「前往💼 我的持股」「前往⚖️ 資產配置」，兩枚都指向 💼 我的資產（`app_preview._page_links`）；改它屬頁名字樣變更，本批沒動，登記於 BACKLOG BL-0525 列尾（與 BL-0483 併讀）。

**D-3 阻擋項修正批（2026-10-30；客戶裁示 `DEC-2026-10-30-04`；代碼 commit `dc670882`；只修阻擋項，P3 page-level 合併燈仍未實作）**：
- **已修**：上方「沒做或沒驗」(4)（A6m 條件 (3)：持倉來源有略過的分頁）與第三輪 SF-1（「持有 N 檔」只數被接受的列、BL-0411）。兩頁資料承載層把 L2 `skipped_holdings`（與配置側的 `skipped_tabs`）原樣交進 dataset（`ui_v2/hld/live.py::assemble_live_load`、`ui_v2/alo/source.py::load_live` 經 `ui_v2/alo/live.py::skipped_for_dataset`；經遮蔽、只轉交），`ALO-2`／`HLD-2` 記下略過紀錄，兩枚燈與 `sections.hld_holding_count` 讀它：`ALO-0` 不寫「各類別皆在容許帶內」、`HLD-0` 不寫「無偏離項」，燈下逐列寫出略過的持倉與 L2 原因；單頁三個計數那一行不畫，合併頁主判讀寫「持有檔數無法判定」。另修 F-13／F-19（有類別沒評估到 → `ALO-0` 改既有「配置差距無法判定」）、F-14（74 A5c 燈沒有字 → 同一句）、F-2（74 H7 → `HLD-0` 照舊「無偏離項」並帶上 `HLD-2`／`HLD-3` 卡上既有的未評估字樣）。逐項見 `docs/v2/74` 第 5 節各列末。
- **合併頁主判讀**：`overview.allocation_incomplete`（`has_unevaluated_category` 或 `ALO-0` 的 `_incomplete`）取代只看 `has_unevaluated_category`；`TEXT_UNDECIDABLE_GAP` 的定義搬到 `ui_v2/alo/logic.py`（字面不變）。
- **新擬字樣（待客戶確認字樣）**：略過的持倉列那一行「◇ 資料未備：<分頁> 第 <列> 列（<基金代號>） 未列入：<L2 原因>」（由既有字「◇ 資料未備」「第 N 列」〔`HLD-5` 的「DIRECT 第 3 列」〕「未列入」組成）；`HLD-0` 的 H7 附行「<卡名>：<卡上既有主值字樣>」（同紅燈那一行「<卡名>：取數失敗。」的體例，例「配息與本金卡：◇ 資料未備」）。「配置差距無法判定」是既有字面，本批只是讓 `ALO-0` 也用它。
- **44 衝突（44 待依 DEC-2026-10-30-04 增修〔44 凍結，未改〕）**：(a) 44 `ALO-0` 規則欄「最大差距在使用者設定的容許帶內 → 燈為灰，文案『各類別皆在容許帶內』」——有類別沒評估到時改寫「配置差距無法判定」；(b) 44 `HLD-0` 規則欄「三塊皆 `ok` 且偏離筆數為零 → … 文案『無偏離項』」與空狀態欄「持倉表為空 → 『尚未建立任何持倉』」——有持倉列被略過時改既有「◇ 資料未備」；(c) 44 `ALO-0` 空狀態欄「尚未建立任何持倉」——持倉列全數被略過時改「配置差距無法判定」；(d) 44 之八其一 (a-2) 的三個計數那一行——有持倉列被略過時不畫（j 的定義未改）。
- **沒做或沒驗（不是漏做）**：(i) P3 page-level 合併燈與八種組合矩陣（下一批，換模型之後）；(ii) F-17（配置側不把略過的分頁浮成錯誤）照舊：配置側只因此改寫「配置差距無法判定」，略過的分頁本身在配置側仍沒有字樣（持股側照舊是取數失敗），部分分頁被略過、其餘分頁沒有持倉列時配置燈仍說「尚未建立任何持倉」；(iii) `HLD-1`（③）在零偏離時照舊寫「無偏離項」「目前這一組門檻下，沒有任何一檔超出。」（已評估子集合的結果），沒有加略過字樣；(iv) 合併頁 Secondary「基金占比」的「N 檔」chip 照舊數 `ALO-6` 列出的檔；(v) H7 的計數行 j 照舊是 `HLD-1` 沒有進入偏離評估的檔數（44 之八其一 (a-2) 第 1 條定義；H7 時為 0 不是誤報），本批沒改；(vi) 逐檔取數失敗而塊仍為 `ok` 的情形（H6，不是 H7）不在 F-2 附行的射程；(vii) 沒有看過 production Cloud 的真實畫面與真資料。實作組單組，獨立稽核待下一步。（→ 2026-10-31 第二輪：(ii)(iii)(iv)(vi) 已修，狀態更新，不是漏刪；見下一段。）

**D-3 阻擋項修正批〈第二輪〉（2026-10-31；依獨立稽核 B1／B2／S1～S6；客戶裁示 `DEC-2026-10-30-04`；代碼 commit 見 `git log`；只修阻擋項，P3 page-level 合併燈仍未實作）**：
- **B1（F-18、F-17）**：~~配置側只因略過的分頁改寫「配置差距無法判定」、分頁本身沒有字樣，持倉為空時仍說「尚未建立任何持倉」~~ → `ui_v2/alo/live.py::skipped_for_dataset` 連同 L2 原因（經遮蔽）轉交 `skipped_tabs`；`ui_v2/alo/logic.py::conclusion_light` 燈下第一行寫「⛔ 取數失敗：<分頁>：<原因>」（`skipped_tab_message`，逐字同 `ui_v2/hld/live.py::assemble_live_load` 組 `errors["holding"]` 那一句；正式模式經 `plain` 畫成「⛔ <分頁> 取數失敗」，與持股側同字），`_build_alo0` 記資料類「持倉」；`_conclusion_light` 持倉為空時 ~~只看 `omitted`~~ 也看 `source_incomplete` →「配置差距無法判定」。`ALO-0` 照舊沒有紅燈。
- **B2（F-18）**：`ui_v2/hld/logic.py::_present_omitted_rows`：持倉列全數被略過（持倉表本身讀得到）時，`HLD-1`／`HLD-2`／`HLD-3`／`HLD-5`／`HLD-8` 的 ~~「尚未建立任何持倉」~~（摘要、說明行）改既有「◇ 資料未備」與略過的列各一行；`conclusion_light` 拿掉紅燈那一支的 ~~「（另：尚未建立任何持倉。…）」~~ 補述（`HLD0_NO_HOLDING_ASIDE`）。各塊 `_state`、主值、按鈕不動。`ALO` 各卡本來就沒有這一句（實跑確認）。
- **S1（F-18）**：同一函式：有持倉、`HLD-1` 零偏離而有略過的列時，~~「無偏離項」＋「目前這一組門檻下，沒有任何一檔超出。」~~ 改既有「◇ 資料未備」佔位（同「零列而有檔資料未備」那一支的寫法）與略過的列各一行；`_state`、`_rows` 不動；`HLD-1` 與佔位記資料類「持倉」。單頁與合併頁 ③ 同一塊。
- **S2（F-18）**：合併頁「基金占比」：`ui_v2/asset/overview.py::share_omitted_lines`／`share_chips`／`share_detail`、`ui_v2/asset/page.py::_secondary_share`：有略過的列時 ~~「N 檔」~~ chip 改既有「◇ 資料未備」（`presentation.missing_chip`），`ALO-6` 表尾（類別內與總體佔比合計）之後接略過的列各一行；表尾字不改。
- **S3（F-2）**：`ui_v2/hld/logic.py::_conclusion_light`：~~三塊皆 ok 就回「無偏離項」＋「沒有任何一檔超出」~~ → 74 H6 的一種（`HLD-2`／`HLD-3` 有逐檔取數失敗或缺值、塊照舊 ok）走 H7 那一支：照舊「無偏離項」、灰、`_state`＝ok，帶原因並記 `_partial`；`_partial_reason_lines` 改看每一個非 ok 主值（不論塊態），`系統錯誤` 也收；`_tag_hld_blocks` 把 `HLD-2`／`HLD-3` 的取數失敗資料類照抄到 `HLD-0`（頁首照舊「⛔ 主要原因：配息取數失敗」，不落到「資料取數失敗」）。`_state` 不改（INFERENCE，理由見 74 F-2 列末）。
- **S4（F-2）**：`_partial_reason_text`：附行帶卡上既有的原因 —— 資料未備接資料類（「◇ 資料未備：配息」）、取數失敗用逐檔那一句、業務例外照印；沒記原因只寫狀態字（不猜）；不計數。
- **S5（F-14）**：判定 A1 正式模式燈句為空不屬「有狀態但沒有文字」（燈上「⛔ 狀態：取數失敗」、頁首有同一句原因；`trim_light_echo` 是去重），**登記豁免、未改程式**（總管讀法，可被客戶推翻；理由見 74 F-14 列末）。
- **S6**：`tests/ui_v2/test_d3_blockers_round2_logic.py` 的 S6 三條：原因字含假祕密，拿掉 `ui_v2/hld/live.py::_omitted_rows_for_dataset` 或 `ui_v2/alo/live.py::skipped_for_dataset` 的 `mask()` 即轉紅（突變實跑）。
- **改動或新增的客戶可見字串**：新增「⛔ 取數失敗：<分頁>：<原因>」在 `ALO-0` 燈下（既有持股側同一句）；`ALO-0` 持倉為空而有略過分頁時「配置差距無法判定」（既有）；`HLD-1`／`HLD-2`／`HLD-3`／`HLD-5`／`HLD-8` 有略過列時的「◇ 資料未備」與略過列那一行（皆既有；該行字樣仍待客戶確認）；合併頁「基金占比」chip「◇ 資料未備」（既有）；F-2 附行「<卡名>：◇ 資料未備：<資料類>」「<卡名>：⛔ <代碼> 取數失敗」（由既有字組成，待客戶確認字樣）。頁首新出現的「⛔ 主要原因：持倉取數失敗」（配置側略過分頁）與「◇ 主要原因：持倉資料未備」（持股側零偏離而有略過列）是既有頁首機制讀到新畫出的 ⛔／◇。
- **44 衝突（44 待依 DEC-2026-10-30-04 增修〔44 凍結，未改〕）**：(e) 44 `ALO-0` 空狀態欄「尚未建立任何持倉」——有保單分頁被略過時改「配置差距無法判定」；(f) 44 `HLD-1`／`HLD-2`／`HLD-3`／`HLD-5`／`HLD-8` 空狀態的「尚未建立任何持倉」、`HLD-1` 零列「無偏離項」（程式登記草稿 ⛔ H-06）——有持倉列被略過時不成立；(g) 44 `HLD-0` 規則欄「三塊皆 `ok` 且偏離筆數為零 →『無偏離項』」——逐檔未評估（H6）時另帶原因、不寫「沒有任何一檔超出」。
- **沒做或沒驗（不是漏做）**：(i) P3 page-level 合併燈與八種組合矩陣（換模型之後）；(ii) `ALO-4`「分組定義」摘要的「未指派 0 檔」、`ALO-6` 單頁表尾的佔比合計在有略過列時照舊（未被稽核點名；單頁 `ALO-0` 燈下已逐列寫出），合併頁「各檔區間報酬」的「N 檔有值」照舊（→ 2026-10-31 第三輪：`ALO-4`、`ALO-6` 兩項已修，狀態更新，不是漏刪；「N 檔有值」照舊）；(iii) `HLD-1` 有偏離列時照舊列出（N 為下限由 `HLD-0` 那幾行承擔）；(iv) 頁首新出現的兩種主要原因是否要排序調整，未改（既有排序規則）；(v) 沒有看過 production Cloud 的真實畫面與真資料。實作組單組，獨立稽核待下一步。

**D-3 阻擋項修正批〈第三輪〉（2026-10-31；依獨立稽核 B-NEW-1／should-fix 1／should-fix 3／`_strip_dev_lines` 附註；客戶裁示 `DEC-2026-10-30-04` F-18；前一輪代碼 `b4267262`；本輪代碼 commit 見 `git log`；只修阻擋項，P3 page-level 合併燈仍未實作）**：
- **B-NEW-1（回歸，阻擋）**：(FACT，探針重現) 有 DIRECT 列、保單分頁上的持倉列又全數被略過時，第二輪的 `ui_v2/hld/logic.py::_present_omitted_rows` 已把 `HLD-5` 那一句「尚未建立任何持倉，沒有可以展開的檔。」換成略過的列，`ui_v2/hld/live.py::_apply_direct`（持倉全空、N＞0、非讀取失敗那一支）卻照舊要求那一句在、不在就 `ValueError` → 單頁 `💼 我的持股` 與合併頁持股側畫成「⛔ 資料 取數失敗：本頁暫時無法判定」（造假，且蓋掉略過的列）。修法：`_apply_direct` 加 `omitted`（`page_health.omitted_rows(dataset)` 非空，與 `logic` 同一個來源）一支：摘要＝`logic` 給的「⬜ 資料未備：持倉」接 `DIRECT_SUMMARY_SUFFIX`（「⬜ 資料未備：持倉 · DIRECT N 筆未列入」，兩段皆既有字樣）；說明區不動（略過的列照留）；卡尾照加 DIRECT 黃字與逐筆位置；不跑 `_replace_exits`（出口已由 `logic` 換掉，再換會把略過的列改寫成 DIRECT 那一句）。**摘要的選擇**：不用 `DIRECT_SUMMARY_ONLY`「DIRECT N 筆未列入」——它會讀成「沒寫進來的只有 DIRECT」，蓋掉略過的列（總管讀法，可被客戶推翻）。原本的不變式照舊守沒有略過的列的情形；有略過的列時改守反方向（那一句還在或摘要不是 `OMITTED_SUMMARY` → raise）。有持倉＋DIRECT＋略過的列那一支本來就不 raise，已補測試。
- **should-fix 1（F-18）**：`ui_v2/alo/logic.py::_build_alo6`：有略過的列時 ~~摘要「N 檔」~~ 改既有「⬜ 資料未備」（正式模式 ◇；「；被排除 N 檔」照接），表尾各合計之後接略過的列各一行（`page_health.omitted_row_lines`）；列、分母、合計數字不動；持倉全數被略過那一支表尾同樣寫出略過的列；資料類記「持倉」。`_build_alo4`：~~「未指派 N 檔」~~ 改「未指派 ⬜ 資料未備」（略過的列沒進來，不算成未指派；已知未指派的檔照舊逐檔列在 `unassigned_lines`），資料類記「持倉」。單頁與合併頁「配置明細」讀同一塊；合併頁「基金占比」的 `ui_v2/asset/overview.py::share_detail` 拿掉 `omitted_lines` 參數、照舊只讀 `ALO-6` 表尾（不重複）；件數 chip 照舊。
- **should-fix 3**：`_present_omitted_rows` 的摘要 ~~`ND_TEXT`~~ 改 `logic.OMITTED_SUMMARY`＝「⬜ 資料未備：持倉」（`page_health.DATA_CLASSES["holding"]`；既有字型「◇ 資料未備：‹資料類›」）：「單檔展開」「最大回撤與本金類配息佔比」兩個展開區標題恢復「◇ 資料未備：持倉」。
- **附註（`_strip_dev_lines`；FACT，探針重現）**：F-2 附行「<卡名>：⛔ 取數失敗：<代碼>：<上游原文>」的上游原文不在行首，原文含殘留檢查那一小段（例「規格沒有寫」）時整頁 raise。`ui_v2/hld/live.py::_is_upstream_error_line` 另認「以 `HLD-2`／`HLD-3` 卡名開頭、行內有 `fetch_failed_text` 前綴」的行為資料行（卡名取自 `logic.BLOCK_TITLES`）；範本行殘留照舊 raise。
- **改動的客戶可見字串**：(1) DIRECT＋持倉全數被略過：~~「⛔ 資料 取數失敗：本頁暫時無法判定」~~ → 照常畫頁，「單檔展開　—　◇ 資料未備：持倉 · DIRECT N 筆未列入」、DIRECT 黃字與位置、略過的列；(2) 持倉全數被略過：「單檔展開」「最大回撤與本金類配息佔比」標題 ~~「◇ 資料未備」~~ →「◇ 資料未備：持倉」（`HLD-1`／`HLD-2`／`HLD-3` 摘要同字，層 2 不畫摘要）；(3) 有略過的列：「歸屬明細　—　~~N 檔~~ ◇ 資料未備」、「分組定義　—　…未指派 ~~N 檔~~ ◇ 資料未備」，兩者帶進合併頁「我的條件」「配置明細」容器標題（既有容器標題規則 `ui_v2/asset/overview.py::block_state`／`container_title`：塊摘要帶 `STATE_MARKERS` 字樣時接在塊名後）；`ALO-6` 表尾「總體佔比合計」之後多出略過的列（單頁與「配置明細」；「基金占比」照舊一次）；持倉全數被略過時 `ALO-6` 表尾同樣多出略過的列；(4) 單頁 `⚖️ 資產配置` 與合併頁頁首新出現「◇ 主要原因：持倉資料未備」（既有頁首機制讀到 `ALO-4`／`ALO-6` 新記的 ◇）。上列字樣由既有字組成（「⬜／◇ 資料未備」「：持倉」「 · DIRECT N 筆未列入」「未指派」、略過列那一行），本輪沒有新增 Missing 字彙（實作組單組逐條對照 `ui_v2/hld/logic.py`、`ui_v2/hld/live.py`、`ui_v2/page_health.py` 既有常數，未經第二組驗證）。
- **第三輪補（總管派工；F-18；同 should-fix 1 的處理）**：`ui_v2/hld/logic.py::_present_omitted_rows`：有持倉而有略過的列時，`HLD-5`、`HLD-8` 摘要開頭的 ~~「N 檔」~~ 改既有字型 `OMITTED_SUMMARY`（「⬜ 資料未備：持倉」，正式模式 ◇），其餘字照留（`_COUNT_HEAD`；示範模式字尾「（示意）」標的是件數，隨件數拿掉）；兩塊說明區最後各接略過的列；資料類記「持倉」；列、主值、`_state`、按鈕不動。可見字串：「單檔展開　—　~~N 檔~~ ◇ 資料未備：持倉 · 同時最多展開一檔」（有 DIRECT 時再接「 · DIRECT N 筆未列入」）、「最大回撤與本金類配息佔比　—　~~N 檔~~ ◇ 資料未備：持倉 · 兩個值皆出數／有值取不到或不適用」；兩塊說明區多出略過的列；合併頁「持股明細」容器標題依既有規則一併帶出。44 無新衝突（INFERENCE：兩塊摘要字面不在 44 內）。
- **44 衝突**：本輪沒有新增（INFERENCE，單組對讀 44 `ALO-4`／`ALO-6` 規則欄與判準：表尾兩個合計照印、數字照舊為 1；兩塊摘要與 `HLD-5` DIRECT 摘要的字面不在 44 內）。第一、二輪已登記的 (a)～(g) 照舊「44 待依 DEC-2026-10-30-04 增修（44 凍結，未改）」。
- **沒做或沒驗（不是漏做）**：(i) P3 與八種組合矩陣；(ii) ~~**發現、未修**：有持倉列被略過時，`HLD-5`「單檔展開」摘要「N 檔 · 同時最多展開一檔」與 `HLD-8` 摘要「N 檔 · …」仍以被接受的列計數（同 should-fix 1 的形狀；不在本輪稽核點名範圍，登記於 `docs/HANDOFF.md` (8) ⑦，待總管決定）~~（→ 已修，見下一條「第三輪補」；狀態更新，不是漏刪）；(iii) H6 在 P3 的排位、`OMITTED_ROW_TEXT` 字樣待客戶確認（`docs/HANDOFF.md` (8) ⑤⑥）；(iv) 沒有看過 production Cloud 的真實畫面與真資料。實作組單組，獨立稽核待下一步。

**Batch D 裁示指標（2026-10-30；`DEC-2026-10-30-02`；上表 Phase 5 列是計畫，保留）**：客戶已對 `docs/v2/73_assets_wireframe_batch_d.md` 的 D-1～D-12 正式裁示（逐字 `docs/evidence/decisions/2026-10-30_batch_d_d1_d12_rulings.md`）：層 3／層 4 的「塊」按 presentation container 計（R-C；正式定義「Domain Block Identity ≠ Presentation Container Count」，block ID 不刪、Decision Digest 不減），整頁 S1（3a＋4a）；Primary 為資產配置現況 vs 目標；第一屏保留總資產／總損益／報酬／配息四項 compact summary slots（缺資料誠實 Missing），本批不准入新彙總公式；持倉資料來源 selector 頁頂獨立一列（OAuth 不得順手改）；**D-3 page-level 結論燈暫停，待最小 Formula Gate，Gate 落盤前不得實作**。本檔其餘處的「層 3／層 4 超限處置待客戶裁示」讀作已裁結（上表 Phase 5 列的前置條件已滿足；T7 帳號與 Sheet 位置仍隨 Batch D／F 實作）。Batch D 實作批的狀態見 `docs/HANDOFF.md` 與 `docs/BACKLOG.md` BL-0525。

依 repo dependency 可微調順序；每批完成前走 Visual Fidelity Gate，CI 全綠不等於完成。進入 Batch B 以後的機械式 UI 實作，依客戶第二十四節與第三則末段走 Model／Effort Change Gate（建議 Sonnet 5.5／Medium）。

---

## 10. 本檔沒有查證的部分（誠實揭露）

1. **本組抽查過的承重事實**（`02615e41` 實跑）：B 線不 import 舊線、舊線不 import B 線；B 線唯一圖表呼叫點；T1、T2、T3、T4 的測試名稱與斷言形狀；`_plain_scan.py` 市場腳本的資料；slow lane `continue-on-error: true`；`PHASE1_HIDDEN_INPUT_CODES`；B 線無搜尋鏈呼叫；44 `ALO-*`／`HLD-*` 塊數；「現在／為什麼／去哪補」字樣零命中；零張截圖；市場區段 Data Gap 文案用 ⬜；`build_ai_summary` 與「Decision Digest」零命中；`rule_version` 零命中；A 線 prompt 的「25%+」與 `mcp_server` 的 `action_light`；B 線無 AI 呼叫。
2. **照錄未重跑**：調查組的 AST 呼叫點計數（P-01 等）、舊線圖表巢狀計數、測試面的其餘逐條判定、文件面 44 之外各檔的逐段判讀、AI 盤點的 production 可達性與欄位（讀建構函式得出，未跑回傳值）。三份調查盤點皆單組產出。
3. **單組判斷、未經第二組驗證**（`CLAUDE.md` §-2 規則 6）：各表的 A／B／C 分類、衝突矩陣判定、第五節第三小節子法 1 相容判斷、第六節對各 DEC 的 supersede 範圍、第八節落點選擇、第九節分批。屬治理規則等級，合併前要有至少 1 組真正獨立稽核（`PROJECT_RULES.md` 第 8 節）。
4. 盤點母體是三組選定的檔案與 DEC，不是窮舉：44 其餘各塊的空狀態欄未逐塊讀；`docs/DECISIONS.md` 第五節歷史索引、交接本、`docs/evidence/**` 未逐條讀；`docs/v2/59`／`61`／`65` 只讀檔頭與命中處。
5. 版面結論（「第一屏看不到圖」）是讀程式碼得出的結構，沒有截圖驗證實際首屏。
