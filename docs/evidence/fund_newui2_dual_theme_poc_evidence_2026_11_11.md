# New UI2 ☀️／🌙 雙模式：隔離技術 PoC 證據（2026-11-11）

> **文件定位**：隔離 PoC 的施工與驗證證據，docs-only。**不是**正式雙模式 UI 施工授權，也不是新設計 SSOT。
> **授權依據**：`DEC-2026-11-11-02`（只授權 T1／T3／T4 的最小隔離 PoC；T2、T5、V1～V3 維持原狀）；邊界讀自 `docs/evidence/decisions/2026-11-11_new_ui2_dual_theme_t1_t5_ruling.md`「PoC 位置與守衛邊界」。
> **PoC 成功 ≠ 正式雙模式授權**：本文件的任何結果都不構成客戶已核准暗色色票、切換入口、偏好保存或上線。正式採用另需新的視覺與持久化 Decision Gate。
> **標記**：FACT＝本批實測／從 repo 讀到；INFERENCE＝推論；NOT RUN＝沒跑；NOT VERIFIED＝本批無法驗證。
> **自查聲明**：以下全部為**作者自查**（單組實作者），**非獨立 QA**；獨立 QA 與非作者重算對比度由總管另行安排。「全部通過」只代表作者自己的指令通過，不代表第二組驗過。

## 一、最終結構（FACT）

僅新增三處，沒有修改任何既有檔案：

| 位置 | 內容 |
|---|---|
| `poc/dual_theme_isolated/` | `app_poc.py`（PoC 專用入口，非 production；沒有 `pages/`）、`poc_page.py`（頁面）、`poc_palettes.py`（雙套色票 fixture）、`poc_theme_css.py`（palette → scoped CSS）、`poc_chart_svg.py`（行內 SVG 折線圖）、`poc_fixtures.py`（合成資料與狀態字樣）、`README.md` |
| `tests/poc_dual_theme/` | `test_poc_dual_theme_palettes.py`、`_apptest.py`、`_guard.py`、`_browser.py`（slow）、`_contrast.py`（slow）；輔助 `poc_dual_theme_contrast_lib.py`（自寫 WCAG 計算器）、`poc_dual_theme_browser_lib.py`（量測 JS 與配對導出）。無 `__init__.py`，檔名在整個 `tests/` 內唯一 |
| `docs/evidence/` | 本檔 |

- 手動執行：`streamlit run poc/dual_theme_isolated/app_poc.py`。
- 沒有 import 或唯讀 import `ui_v3`：PoC 把 light 值**複製成 fixture**，由測試（不是 PoC 程式）唯讀 import `ui_v3.design.tokens` 比對相等，防漂移（FACT：`test_light_palette_equals_approved_ui_v3_tokens_read_only` 通過）。
- 沒有 JS、沒有自訂 component、沒有新依賴、沒有網路、沒有寫檔、沒有 browser storage、沒有 query-param 持久化（FACT：由 `_guard.py` 的 AST 守衛與瀏覽器 storage 快照測試覆蓋）。
- 觸及禁止清單？**沒有**（FACT：見第十二節 `git diff --name-only` 結果）。

## 二、環境與版本（FACT）

| 項目 | 值 |
|---|---|
| Python | 3.13.18（scratchpad venv，`--system-site-packages`） |
| Streamlit | **1.59.2**（`requirements.txt` 為 `>=1.59.1,<1.60.0`；本機解析到 1.59.2；1.59.1 NOT RUN） |
| pytest／playwright | 9.2.0／1.65.0 |
| 瀏覽器 | Chromium（Chrome for Testing 153.0.8010.12，`/opt/pw-browsers/chromium-1243`，由 `UI_V2_CHROMIUM` 指定；沿用 `tests/ui_v2/_ui_v2_chromium.py` 的啟動與 server 方式） |
| 共用 config | PoC 以 repo 根為 cwd 啟動，所以吃到**未修改**的 `.streamlit/config.toml`（舊 light theme）；PoC 的兩個模式都是用自己的 CSS 覆蓋它 |

## 三、模式狀態如何運作（FACT）

- **唯一權威**：一個受控 `st.session_state["poc_theme_mode"]`，它同時是切換用 `st.radio` 的 widget key（值 `light`／`dark`，預設 `light`）。`poc_page.current_mode()` 是唯一讀取點；未知值直接 `raise`（不退回預設，`test_unknown_mode_fails_loud`）。
- **時序**：腳本最前面讀模式 → 由 `poc_theme_css.build_css(palette)` 產生並以 `st.markdown(<style>, unsafe_allow_html=True)` 注入 → 其後才畫 radio。切換時 Streamlit 先把新值寫進 session_state 再重跑腳本，所以同一輪就是新色，**沒有二次 rerun**。
- **為什麼不用 `st.context.theme`**：它是唯讀、依 Streamlit 設定的 theme 推斷，不反映 scoped CSS。**本批實測**：注入 PoC 的 dark CSS（`.stApp` 底 `rgb(15, 22, 38)`）的同一頁，`st.context.theme.type` 仍回報 `light`（scratchpad 小程式實跑，非 repo 檔案）。這與 #1209 QA 的結論一致。PoC 程式碼完全沒有使用 `st.context`、`st.query_params`、`st.components`（AST 守衛）。
- **session-only 的實際行為**：同一 session 內切換多次、rerun、其他 widget 操作都保留；**瀏覽器重載＝新 session ⇒ 回到預設淺色**（FACT：`test_reload_returns_to_default_light_session_only`）；兩個 browser context 彼此獨立（`test_two_contexts_are_independent_sessions`）。這是 DEC T3 的預期行為，**不得**被讀成「記住使用者偏好」。
- **storage／cookie**：PoC 沒有寫任何 browser storage 或 cookie；切換前後 `localStorage`／`sessionStorage` 的鍵值與 cookie 名稱完全相同（FACT）。附帶觀察：**Streamlit 自己**會寫 `localStorage["stActiveTheme-/-v2"]` 與 `_streamlit_xsrf` cookie，與 PoC 無關、值不隨 PoC 切換改變。

## 四、截圖（FACT；影像不入 repo）

三寬度 × 兩模式，由 `test_screenshots_saved` 以 `POC_DUAL_THEME_SHOT_DIR` 寫出（單檔 145～185 KB，合計約 1 MB，超過 200 KB 上限，**依規定不 commit**）。作者本機路徑（scratchpad，非 repo、reviewer 無法由 PR 取得；需要時重跑該測試即可再產生）：

`/tmp/claude-0/-home-user-my-Fund-dashboard/efafe946-a13e-55b7-a7e0-682dd16e26e7/scratchpad/poc_shots/poc_dual_theme_{light,dark}_{390,768,1280}.png`

作者目視：兩模式的頁底、卡片、chip、原生 radio、expander、disabled、SVG 圖與側欄皆套色；暗色下頁首（Deploy／⋮／窄螢幕的側欄展開鈕）也變深。**目視不等於獨立 QA。**

## 五、三寬度實測結果（FACT；作者自查）

`test_poc_dual_theme_browser.py`（Playwright／Chromium），390／768／1280 × light／dark：

| 項目 | 結果 |
|---|---|
| 新 session 預設模式 | light（三寬度皆是） |
| computed style 與 palette 逐項吻合 | app 底、頁首底、標題字、卡片面／邊、次要文字、radio 選取圓點／未選圓環／標籤字、expander 邊／底／字（另有 expander 六態對比，見第六節）、button 底／邊、disabled button／radio 字、側欄底／字、SVG 兩條線與刻度字、六枚 chip 的字／底／邊、`color-scheme`；淺→深→淺後完全回到淺色（無殘留） |
| 頁級水平溢位 | 無（同時檢查 `documentElement`、`body`、`stMain`、`stAppViewContainer`；**`stMain` 是 Streamlit 的捲動容器，只查 document 會漏**——負控抓到後補上） |
| 圖寬 | `0 < svg 寬 ≤ 720`（三寬度、兩模式） |
| chip | 六枚皆有「符號＋中文字樣」（`◆ ◇ ⬜ ⛔ ◷ ●`），不靠顏色 |
| 缺資料 | 選「丙（資料未備示範）」不畫圖、只有 `◇ 資料未備`，文字內**沒有任何數字**；缺資料卡亦無數字 |
| 切換操作 | 滑鼠可切；鍵盤（focus 模式 radio 後 ArrowRight／ArrowLeft）可切（390 與 1280 驗證；768 鍵盤 NOT RUN） |
| rerun 保留 | 檢視＝甲、期間＝3M 在四次來回切換後皆保留 |

## 六、對比度（FACT；作者自寫計算器，非非作者重算）

- **方法**：`poc_dual_theme_contrast_lib.py`（WCAG 2.x 相對亮度、alpha 合成、大字判定）；已知值測試（黑白 21、#777 對白 4.478、alpha 合成）。配對**不寫死**：由瀏覽器 computed style 導出——每個可見文字節點的 `color`（SVG 用 `fill`）、各層祖先 `background-color` 與累計 `opacity` 逐層合成後計算。蒐集狀態：idle、expander 展開（hover）、**expander 展開（靜止：未 hover、未 focus）**、radio hover、radio 鍵盤 focus、button hover、主選單 popover 開啟、側欄（窄螢幕點原生展開鈕）。每個寬度×模式約 70 個文字節點。
- **文字（門檻：一般 4.5、大字 3）**

| 模式 | 最低（排除原生 popover） | 其他代表值 |
|---|---|---|
| light | **4.55**（disabled 字 `#6b7690` on 白） | 次要文字 6.9～7.4；紅 chip 7.67；黃 chip 7.10；主文 16.27；側欄 14.6；**expander 展開靜止 header 16.27** |
| dark | **5.59**（disabled 字 `#8d98b0` on `#172036`） | 次要文字 7.76～8.65；紅 chip 6.71；黃 chip 8.15；主文 13.71；側欄 16.06；**expander 展開靜止 header 13.71** |

- **非文字／邊界（門檻 3:1，緊鄰外側底色）**

| 元件 | light | dark |
|---|---|---|
| radio 未選圓環（功能性） | 3.38 | 5.84 |
| radio 選取圓點（功能性） | 5.85 | 5.95 |
| expander 邊框（功能性） | 3.16 | 3.45 |
| button 邊框（功能性） | 3.38 | 5.84 |
| 圖 甲 實線／乙 虛線／座標軸 | 5.85／16.27／7.35 | 5.95／13.71／7.76 |
| 鍵盤 focus 外框（radio、button） | 5.85 | 8.15 |
| 卡片邊框（裝飾；報告用） | 3.16 | 3.45 |
| chip 邊框 neutral／grey／red／yellow（報告用） | 3.38／3.38／5.44／3.64 | 5.84／5.84／7.07／8.78 |

- **發現（誠實揭露）**
  1. **原生主選單 popover 的小字（快速鍵 `R`／`C`、「Made with Streamlit」、版本字）在兩個模式都是 4.16:1（<4.5）**——這是 Streamlit 原生面板，PoC 未覆寫，不是 PoC 通過的項目；測試把它記錄為發現並設 4.0 底線防止更差。
  2. 卡片／expander 邊框在 light 只有 3.16:1（剛過 3），在 dark 3.45（研究示例 `#5a6c94` 對頁底 `#0f1626` 可用，但對卡面 `#172036` 僅約 3.09）。邊框是唯一的卡片輪廓線，餘裕很小；若客戶要求更清楚的卡片輪廓需另裁示。
  3. 研究文件警告「暗底下 red／yellow 邊接近或低於 3:1」——PoC 採**研究候選 `#ff8a7a`／`#e8b84a` 作 text 與 border**（實測 7.07／8.78）並自選暗底（見下表 PoC-only），所以此警告在本 PoC 的取值下未重現；這不代表研究示例原值被核准。
  4. 兩模式的原生 `disabled`（本 PoC 用 `disabled_text` ＋ 圓點淡化 ＋ `cursor:not-allowed`）都 ≥4.5；disabled 本來就免於 WCAG 對比要求，這裡是額外保持可讀。
- **PoC-only 變體（本 PoC 另選，**不是**研究示例、不是核准值）**：`control_border`（dark `#8a9bc4`，原生控件邊界需 ≥3:1）、`hover_bg`、`focus_ring`、`disabled_text`、`sidebar_bg`（dark `#0a101f`）、dark 的 chip 背景（neutral／grey `#222d4a`、yellow `#2d2610`、red `#3a1c1f`）、dark 的 neutral／grey 邊 `#8a9bc4`；light 的 `hover_bg`／`focus_ring`／`disabled_text` 也是 PoC-only（ui_v3 沒有對應 token）。其餘 dark 值取自研究文件 §四 示例。
- **更正（2026-11-11 獨立 QA 發現，已修）**：初版**漏量「展開且滑鼠移開、未聚焦」的 expander header**——我的瀏覽器蒐集在展開當下滑鼠還停在 header 上（hover 底），且 hover／focus 只在收合狀態量過。實際上 Streamlit 原生對**展開中的 summary**給固定淺灰底 `rgb(242,244,247)`（不隨 palette），暗色下字 `rgb(230,237,243)` 對它只有約 **1.07:1**（390／768／1280 皆重現）；light 因字深而未被察覺。**修法**（`poc_theme_css.py`）：`details[open] > summary:not(:hover){background:transparent}`（透出 details 的 surface）＋ summary 鍵盤 focus 用 `hover_bg` 與 `focus_ring` 外框。**修後實測**：light 16.27、dark 13.71。新增 `test_expander_header_text_contrast_in_all_four_states`（關／開 × 靜止／hover／focus 共 6 個量測點 × 兩模式 × 三寬度，全部 ≥4.5）與負控 `test_mutation_without_open_summary_override_is_detected`；另在 scratchpad 副本內刪掉該覆寫行確認測試轉紅（dark 1.07，其餘五態 11.08～13.71）。上面「dark 最低 5.59」現在**涵蓋此狀態**（修後該狀態不是最低）。**教訓**：只在一個狀態下量測，等於沒量其他狀態；狀態矩陣要列出再逐格量。
- **QA 次要註記（照錄）**：側欄按鈕的邊框取自 ui_v3 核准的 `sidebar.border #34466e`，對側欄底只有 **1.85:1（light）／2.03:1（dark）**，<3:1。該邊框是**繼承自既有核准值的裝飾性邊框**（按鈕靠文字辨識），**不在 PoC 自己的邊界表內**，PoC 未覆寫；是否需要處理屬後續視覺裁示。卡片與 chip 邊框在上表標為「報告用」（裝飾性，內容靠符號＋字樣），不是 3:1 通過的功能性項目。
- **未涵蓋**：只量「實際渲染到的配對」；`⬜ ◷ ⛔` 等 emoji 字元本身的彩色字形不在文字對比度範圍；hover／focus 只量了上列狀態；不同 DPI／縮放／強制色彩模式 NOT RUN。

## 七、原生 widget 相容性發現

**可行（FACT，瀏覽器 computed style 實測）**

| 項目 | 結果 |
|---|---|
| 頁面／app 背景與文字 | `.stApp`／`body` 底與 `stMain` 全子孫 `color: inherit` 後單一來源；暗色可行 |
| 頁首（stHeader、Deploy、⋮、窄螢幕的側欄展開鈕） | 可用 `stHeader` 底＋`color: inherit` 重新著色；暗色下可讀（Deploy 文字 15.28:1；窄螢幕展開鈕只有目視） |
| 側欄（底、字、按鈕、邊） | 可行；兩模式側欄都是深色（light 沿用 ui_v3 核准的深側欄，dark 為更深的 PoC-only 值） |
| `st.radio`（選取／未選／標籤／hover／disabled） | 圓點用既有 ui_v3 同款選擇器 `label[data-testid="stRadioOption"] > div > div > div:first-child` 覆寫可行；hover 與鍵盤 focus 用 `[data-focus-visible="true"]`／`:hover` 自訂 |
| `st.expander`（邊、底、summary hover／鍵盤 focus、**展開靜止的 header 底**、字） | 可行，但**需要**覆寫展開中 summary 的原生固定淺灰底（見第六節更正）；關／開 × 靜止／hover／focus 六態皆已量測 |
| `st.button`（底、邊、hover、鍵盤 focus、disabled） | 可行；Streamlit 原生 focus 的 `box-shadow`（取自 config 舊主題的半透明藍）需覆寫為 `none` 才不與自訂外框打架 |
| 瀏覽器原生元件（捲軸、表單控件） | 設 `color-scheme`（computed 已驗證等於 palette 值）；捲軸實際外觀 **NOT VERIFIED**（headless 截圖未涵蓋） |

**不行／有限制（FACT）**

| 項目 | 結果 |
|---|---|
| 主選單 popover（portal，不在 `stMain` 內） | **深色模式下仍維持原生淺色面板（深字，可讀）**。本批嘗試過只用 CSS 重新著色：面板與文字可以變深，但內部「Auto rerun」開關的軌道是半透明深色，在深底上幾乎看不見（截圖目視），分隔線也消失；要修需靠無 `data-testid` 的脆弱選擇器。**PoC 選擇不覆寫**並把它列為殘留淺色項。 |
| 其他 portal 類元件（`st.dialog`、`st.toast`、popover、selectbox 下拉、tooltip） | **NOT RUN**（PoC 頁沒有使用，無法聲稱可著色） |
| 選擇器耐久 | 覆寫依賴 Streamlit 的 `data-testid` 與 emotion DOM 結構（`> div > div > div:first-child`）；升級 Streamlit 若改 DOM，瀏覽器測試會轉紅，不會靜默退回舊色（INFERENCE：以 ui_v3 既有做法與本 PoC 的負控為依據）。大量使用 `!important`。 |
| 頁首／工具列文字 | 只有 `stHeader` 內元素被改；Streamlit 其他 chrome（如部署在 Cloud 時的額外工具列、狀態 widget）**NOT VERIFIED** |

## 八、session／rerun 行為（FACT）

AppTest（15 條）與瀏覽器（共用同一組判定）互相印證：預設淺色；淺→深→淺；12 次連續切換一致；切換不重置其他 radio；新 `AppTest` 實例（＝新 session）回到淺色而舊實例維持深色；直接寫 `session_state` 的鍵即可決定模式（確認沒有第二個狀態來源）；所有期間與檢視組合在暗色下渲染無例外。

## 九、變異驗證（FACT；在 scratchpad 的 repo 副本內暫時破壞後確認轉紅、再還原確認回綠）

| # | 破壞 | 轉紅的測試 |
|---|---|---|
| M1 | 拿掉頁底（`.stApp`）規則 | `test_default_is_light_then_dark_then_light_computed_styles[1280]`（瀏覽器） |
| M2 | `DEFAULT_MODE` 改 `dark` | `test_default_is_light_on_new_session` |
| M3 | 在 `ui/` 新增 `import poc_page` | `test_no_production_path_references_the_poc` |
| M4 | dark `text2` 改成低對比 `#3a4666` | `test_palette_static_contrast[dark]` |
| M5 | SVG 寫死 `stroke="#ff0000"` | `test_svg_has_no_hardcoded_colors_and_has_axis_labels_and_legend` |
| M6 | 把 PoC dark 值加進 `ui_v3/design/tokens.py`（副本內） | `test_dark_values_are_fixtures_not_in_ui_v3_tokens` |
| M7 | PoC 內出現 `<script>localStorage…` 字串 | `test_poc_sources_have_no_forbidden_mechanisms` |
| M8 | 拿掉原生 radio 圓點覆寫 | `test_default_is_light_then_dark_then_light_computed_styles[1280]` |

還原後同批 38 條單元／守衛測試回綠。另有**記憶體內負控**（在測試內現編，不改任何檔）：對已載入頁面注入「亮底留在暗色」「頁首留淺」「原生 radio 圓點錯色」「橫向溢位」「圖過寬」「淺灰字」「卡片邊框與底同色」，斷言同一組判定函式真的會報；隔離守衛也對「production 引用」與 11 種禁用機制寫了負控。**M4 的瀏覽器對比度版本、M5～M8 於其他寬度／模式 NOT RUN**（每項只跑了一個最短路徑）。

## 十、隔離守衛（FACT）

`test_poc_dual_theme_guard.py`：(1) 正式路徑（根目錄 `*.py`、`ui`／`ui_v2`／`ui_v3`／`services`／`repositories`／`shared`／`infra`／`scripts`／`mcp_server`／`models`、`.streamlit`／`.github`／`.devcontainer`）沒有任何引用 PoC；(2) PoC 原始碼 AST：import 白名單（stdlib 子集＋streamlit＋`poc_*`）、無 `open`／寫入／`exec`／`st.context`／`query_params`／components／JS 字串——**沒有任何寫入面，因此不可能寫到 `ui_v3/**`**；(3) 無 `pages/`、無 `__init__.py`、PoC 目錄只含 `.py`／`.md`、測試檔名全域唯一；(4) `ui_v3/design/tokens.py` 不含 PoC 暗色獨有值、`.streamlit/config.toml` 沒有 dark 區段。**限制**：靜態引用偵測以字串／AST 為準，字串拼接繞法不在涵蓋內（同 ui_v3 既有守衛的揭露）。

## 十一、全 repo 測試（FACT／見結果）

**PoC 自己的測試（FACT）**：`pytest tests/poc_dual_theme -m "slow or not slow"`（含瀏覽器與對比度）→ **115 passed**（約 253 秒；分項：palettes 18、AppTest 15、guard 20、browser 42、contrast 20）。預設 fast lane（`-m "not slow"`）只跑到其中不標 slow 的 53 條（palettes＋AppTest＋guard）；瀏覽器與對比度兩檔標 `slow`，由 CI slow lane 跑（該 lane 有 chromium）。

**全 repo `pytest -q -m "not slow"`（FACT；作者在本機 venv 實跑，含 `tests/ui_v3` 與全部會 glob 全 repo `.py` 的掃描型測試，如 `test_name_heuristics_removed`、`test_retired_exception_ids`、`test_st_cache_failure_not_cached`、`test_ia_switch_advisor_moved_to_portfolio`、`test_constitution_file_refs`）：**

- 本分支（含 PoC）：**9 failed, 19782 passed, 45 skipped, 1299 deselected, 8 xfailed**（約 18 分鐘；expander 修正後重跑，失敗清單與修正前逐條相同）。
- 9 個失敗為：`tests/test_alo_core_golden.py` 3 條（`test_整份矩陣_工作樹與黃金檔逐位元組相同`、`test_逐情境相同[alo2_family-cost:near_tied_leaders_within_1e9]`、`test_額外對照_從git歷史的基準原始碼重算_等於黃金檔`）、`tests/test_alo_core_golden_mutations.py` 1 條（`test_對照組_未突變的載入器重現黃金檔`）、`tests/ui_v2/test_hld_logic.py` 2 條、`tests/ui_v2/test_hld_read_failure_logic.py` 2 條、`tests/ui_v2/test_rulings_2026_10_18b_logic.py` 1 條。
- **對照乾淨 `origin/main`（`55e48d03`）**：在**同一環境**用 `git worktree` 取乾淨 main 重跑上述 5 個檔案 → **同樣 9 failed、557 passed**，失敗清單與本分支逐條相同（FACT）。因此這 9 條是環境因素造成、**與本 PoC 無關**（成因 NOT VERIFIED；不是本批要查的）。另用 `git archive` 取得的無 `.git` 乾淨副本跑完整 `-m "not slow"` 得 14 failed——多出的 6 條（`test_dg2_parsing_defects` 1、`test_doc_counters` 1、`test_public_repo_name_redaction` 2、`test_xview_characterization` 2）在「有 `.git` 的真 repo」都通過，屬無 git 環境的人為差異，不是比較基準。
- 本分支**沒有任何新增失敗**；`tests/ui_v3`（含 `test_ui_v3_import_guard`、`test_ui_v3_preview_not_formal_guard`、token／導覽／市場頁相關）全數通過（FACT：失敗清單中無 `tests/ui_v3`）。
- **未跑**：`-m slow` 的全 repo 其他 slow 測試（只跑了本 PoC 的兩個 slow 檔）；CI 的四條 check 結果見 PR 頁（本檔寫成時尚未產生；**不得**在其完成前視為通過）。

## 十二、範圍確認（FACT）

`git diff --stat origin/main`（提交前以 `55e48d03` 為基準）：**15 個檔案、2029 行新增、0 行刪除**，全部落在 `poc/dual_theme_isolated/`（7 檔）、`tests/poc_dual_theme/`（7 檔）與本檔；沒有任何既有檔案被修改。

`git diff --name-only origin/main -- ui_v3 .streamlit ui ui_v2 app.py services repositories shared infra scripts .github docs/DECISIONS.md docs/BACKLOG.md docs/HANDOFF.md PROJECT_RULES.md CLAUDE.md` → **空**（FACT：禁止修改的路徑皆未變）。沒有修改 `STATUS_TONES`、任何公式或資料契約。

## 十三、尚未驗證（NOT VERIFIED／NOT RUN）

- **Streamlit Cloud**、**WebView**、**真機**（iOS Safari／Android Chrome）、其他瀏覽器（Firefox／WebKit）、螢幕閱讀器、強制色彩模式、觸控裝置上的 hover：全部 NOT RUN／NOT VERIFIED（T5：G7 驗收未授權）。
- 任何形式的偏好**持久化**：NOT RUN（T3 未核准）。
- 真實資料、真實 `ui_v3` 頁面（`mkt.py`、`chart_svg.py`、`shell/nav.py`）上的暗色：NOT RUN——PoC 是**模仿**元件組合的合成頁，行內 SVG 是簡化版，**不代表**實際 `ui_v3` 頁面套上暗色後就沒有版面或對比問題（INFERENCE：實際頁面還有導覽殼、更多 chip 組合、Secondary 卡、真實序列，需要再驗）。
- Streamlit 1.59.1（只在 1.59.2 驗證）、其他 minor 版本：NOT RUN。
- 捲軸實際深色外觀、`st.dialog`／selectbox／tooltip 等 portal 元件：NOT VERIFIED。
- 同一頁在兩模式下的效能（CSS 注入成本、切換延遲）：NOT RUN；INFERENCE：每次 rerun 多注入約 4 KB 的 `<style>`，影響應很小。

## 十四、殘留風險（INFERENCE，除非另標）

1. **DOM 耦合**：覆寫原生 radio 圓點等用的是結構選擇器，Streamlit 小版本升級就可能失效；目前只有 PoC 自己的瀏覽器測試會報（若未來正式採用，應把同款測試放進 `ui_v3` 守衛）。
2. **主選單 popover 在暗色下仍是淺色面板**：視覺上是「一塊亮面板」；且其小字 4.16:1 是原生值、兩模式相同。
3. **邊框餘裕小**：卡片輪廓線 light 3.16／dark 3.45，僅略高於 3:1。
4. **`!important` 與 transition**：Streamlit 原生元件有 CSS transition，切換後立刻量 computed style 會量到過渡中的值（測試已改為輪詢到穩定）；使用者可能看到極短的顏色過渡（NOT VERIFIED 主觀感受）。
5. **session-only 的預期落差**：重載回淺色；若使用者習慣深色會每次重選——這正是 T3 待後續裁示的需求，不是本 PoC 能解的。
6. **`color-scheme` 的副作用**：瀏覽器原生元件會跟著變，但本 PoC 沒有涵蓋所有原生元件。

## 十五、仍待客戶裁示的問題（本 PoC 不代為決定）

1. **暗色正式色票**：是否核准某一組暗色值？含上列 PoC-only 變體（`control_border`、hover、focus ring、disabled、側欄、chip 底）。研究示例對 red／yellow 不可直接沿用，是否接受 PoC 的 `#ff8a7a`／`#e8b84a` 方向？（T4 後續；需附非作者重算的對比與畫面證據。）
2. **偏好保存範圍**：維持 session-only，或要求重載／跨裝置記住？若要記住，需要裁示是否接受 browser storage／custom component／JS（本 PoC 刻意不碰）或會員設定。（T3 後續。）
3. **切換入口位置與時機**：⚙️ 設定頁線框與實作核准後才放（T2 維持等待）；PoC 的切換控件只是技術驗證用，不是入口提案。
4. **原生 popover 殘留淺色**是否可接受，或要求更深度的客製（需要脆弱選擇器甚至 JS）。
5. **淺色與深色主內容的關係**：現行 `DEC-2026-10-27-09` 是「淺色主內容＋深色側欄」；暗色模式下「主內容也深色」是否為客戶要的方向，需要明確確認。
6. **`neutral`／`grey` 共色**（V3）、**12px→13px 小字**（V2）、**共用 `.streamlit/config.toml`**（V1）：本 PoC 全部沿用現況，未動。
7. **G7 真機／Cloud／WebView 驗收**（T5）：何時授權。

## 十六、停手條件檢查

本批沒有觸發任何停手條件：不需要 JS／自訂 component、沒有新增依賴、沒有修改禁止檔案、沒有任何持久化。**唯一的異動**：開工時 `git merge origin/main` 在 docs 索引三檔衝突，已先停手回報，由總管以「從 origin/main 重建分支」處置（沒有強推、沒有 reset）。
