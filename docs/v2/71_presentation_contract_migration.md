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
6. 基金 IA（第十二～十五節）撞到的多是客戶自己的舊 DEC；客戶第三則已裁示 Gate 1、2、5，本 PR 已在 44 之二十落最小 IA amendment，並在 `DEC-2026-10-29-06` 逐筆寫明被 supersede 的範圍（第六節）。🤖 AI 投資總結的入口形式待單一最小 Gate（BL-0526）。
7. Visual Fidelity Gate：客戶已裁示正式確認＝production-like Cloud screenshot、CI deterministic screenshot＝自動安全網；兩者工具鏈都還沒建（repo 內零張截圖、CI 沒有上傳截圖的步驟），列入 Batch A（第七節）。
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
| 🤖 AI 投資總結的頁數、44 之十八其一的 AI 區性質 | 待單一最小 Gate | BL-0526 |
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

> 本節保留衝突分析作為紀錄；裁示後的落字與被 supersede 的舊 DEC 逐筆範圍見 44 之二十與 `DEC-2026-10-29-06`。仍待裁的只剩 🤖 AI 投資總結的入口形式（6.6，BL-0526）。

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
| **Phase 4＝Batch C** 🌍 reference implementation | (1) 段序改為圖表優先、Primary 1＋Secondary ≤3（X-25、T1）；(2) 圖卡改 chips＋「▸」（X-26、T9）；(3) 核心卡 `answers`／`detail_lines` 下沉（X-27） | 無；BL-0517 三張新圖卡不在本批（方案 A 草稿另批） | 八項全做＋Visual audit 九問 |
| **Phase 5＝Batch D** 💼 我的資產 | (1) 合併頁 IA（含一枚結論燈的畫法、層 3／層 4 各超 2 塊的處置〔線框送客戶裁示〕、頁序頁名對齊批）；(2) 情境式持倉資料來源選擇；(3) portfolio visuals（Primary 1＋Secondary ≤3） | 線框草稿先行（新元件與合併頁）；**層 3／層 4 超限的客戶裁示**；BL-0526 若影響頁數，對齊批等它 | 八項全做 |
| **Phase 6＝Batch E** 🔍 找基金 | (1) 候選清單解耦；(2) 暫時篩選（只在本次瀏覽生效）；(3) search／filter／compare 呈現 | BL-0397 Data Source Decision Gate（未核准前搜尋區 `◇ 資料未備`）；CAP-GATE-05 | 八項全做 |
| **Batch F** ⚙️ 設定＋帳號位置 | (1) 設定頁瘦身；(2) Google 帳號左側固定與手機控制；(3) desktop／mobile 互動 | callback 查證（6.2，可能再 Gate） | 八項全做 |
| **Phase 7** One AI Brain／Decision Digest／AI 投資總結 | 依 67 第 5、6 節；先補 BL-0527 缺口與守衛 | BL-0526 入口形式；BL-0495 Risk Cap；BL-0496 減碼 trigger；`AI-1`、`AI-3` | Digest 契約定義前不寫 prompt 或 LLM glue |

依 repo dependency 可微調順序；每批完成前走 Visual Fidelity Gate，CI 全綠不等於完成。進入 Batch B 以後的機械式 UI 實作，依客戶第二十四節與第三則末段走 Model／Effort Change Gate（建議 Sonnet 5.5／Medium）。

---

## 10. 本檔沒有查證的部分（誠實揭露）

1. **本組抽查過的承重事實**（`02615e41` 實跑）：B 線不 import 舊線、舊線不 import B 線；B 線唯一圖表呼叫點；T1、T2、T3、T4 的測試名稱與斷言形狀；`_plain_scan.py` 市場腳本的資料；slow lane `continue-on-error: true`；`PHASE1_HIDDEN_INPUT_CODES`；B 線無搜尋鏈呼叫；44 `ALO-*`／`HLD-*` 塊數；「現在／為什麼／去哪補」字樣零命中；零張截圖；市場區段 Data Gap 文案用 ⬜；`build_ai_summary` 與「Decision Digest」零命中；`rule_version` 零命中；A 線 prompt 的「25%+」與 `mcp_server` 的 `action_light`；B 線無 AI 呼叫。
2. **照錄未重跑**：調查組的 AST 呼叫點計數（P-01 等）、舊線圖表巢狀計數、測試面的其餘逐條判定、文件面 44 之外各檔的逐段判讀、AI 盤點的 production 可達性與欄位（讀建構函式得出，未跑回傳值）。三份調查盤點皆單組產出。
3. **單組判斷、未經第二組驗證**（`CLAUDE.md` §-2 規則 6）：各表的 A／B／C 分類、衝突矩陣判定、第五節第三小節子法 1 相容判斷、第六節對各 DEC 的 supersede 範圍、第八節落點選擇、第九節分批。屬治理規則等級，合併前要有至少 1 組真正獨立稽核（`PROJECT_RULES.md` 第 8 節）。
4. 盤點母體是三組選定的檔案與 DEC，不是窮舉：44 其餘各塊的空狀態欄未逐塊讀；`docs/DECISIONS.md` 第五節歷史索引、交接本、`docs/evidence/**` 未逐條讀；`docs/v2/59`／`61`／`65` 只讀檔頭與命中處。
5. 版面結論（「第一屏看不到圖」）是讀程式碼得出的結構，沒有截圖驗證實際首屏。
