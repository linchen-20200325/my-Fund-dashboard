# UI-C｜💼 我的資產＋🔍 找基金：隔離 Preview 驗收與最小掛載差額（2026-11-20）

> 來源：實作組回報（單組執行 AI 產出，未經獨立複驗）；實作組的 Write 被工具拒絕，本檔由總管依該回報**轉錄**（取捨：保留結論、矩陣、缺陷、Gate、測試輸出；刪去逐項重複敘述）。
> 非授權、非裁示；登記不構成動工授權（`CLAUDE.md` §-1）。本檔只描述「隔離 FAKE Preview」在本機 Chromium 的實測，**不是 Cloud／真機驗收**。
> 基準：`origin/main` `b103e99c`；分支 `feat/ui-c-assets-search-acceptance`；實測 commit `adb760e2`（之後只新增本報告）。
> 標記：【FACT】本組實測或讀檔所見；【INFERENCE】推論；【NOT VERIFIED】未驗。

## 0. 結論

| # | 結論 | 類別 |
|---|---|---|
| 1 | 💼（11 個 FAKE 情境）與 🔍（找基金篩選預覽、單檔查詢元件）在 390／1280：無橫向溢出、最小字級 13px、摘要／輸入／按鈕／核取框觸控目標 ≥48px、Tab 順序＝視覺順序、焦點變化可見（唯一例外 Streamlit 自己的捲動容器，D3） | FACT |
| 2 | 缺值一律走缺值字樣，沒有任何一處把缺值顯示成 0；FAKE 資料無網址／試算表 ID／例外字串／內部鍵外洩；兩頁無 AI／OneBrain／Digest 字樣、無 ActionSlot；頁面對外請求 0 | FACT |
| 3 | 找到 1 個明確缺陷並已最小修正：💼 頁多 2 個看不見的 Tab 停駐點（Streamlit 自動標題錨點 16×16）；不改版面（幾何差 ≤0.3px）、不增刪元件、不改資料語意；已加單元＋瀏覽器測試與變異負控 | FACT |
| 4 | 另有 7 項只記錄不修的差額（D2–D8） | FACT |
| 5 | 距離正式掛載共 5 道 Gate（§5）；最大單一阻擋：修正版 S-AST-M1 Gate 與 FAKE 標記字樣未經客戶核准；其次 🔍 renderer 仍住 `poc/` 須先搬模組 | FACT／INFERENCE |
| 6 | 完成宣稱上限：本機 Chromium＋fixture。未驗 Cloud／真機／WebView／讀屏／768px／190% 字放大；未合併、本報告撰寫時未跑 exact-head CI | NOT VERIFIED |

## 1. 環境與方法

- 【FACT】Streamlit 1.59.2；Chrome for Testing 153（`UI_V2_CHROMIUM=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`）；playwright 1.65.2；DPR 1；視窗 390×844（`has_touch`）與 1280×800；locale zh-TW；本機無外網（頁面對外請求 0）。
- 起 4 個 Streamlit：`poc/assets_fixture_preview/app_assets_preview.py`（💼）、`poc/fund_search_fixture_preview/app_fund_search_preview.py`（🔍 篩選＋單檔）、`poc/fund_lookup_component_preview/app_fund_lookup_component_preview.py`（🔍 單檔元件）、`ui_v3/app_preview.py`（未掛載對照；唯讀）。
- 操作用真實點擊／鍵盤（selectbox 滑鼠或 ArrowDown＋Enter；核取框 Space；查詢 Enter 送 `st.form`；`<details>` Enter／Space）。
- 量測指令碼在實作組暫存區，**未入庫**；欄位定義見各 `measure_*.json`（`measure`＝溢出／字級／觸控；`focus_walk`＝逐次 Tab，聚焦與失焦局部截圖像素差）。
- 截圖：視窗拉高到內容全高再截；`*_fold.png` 第一屏；`*_open.png` 展開 A50／A60 後。PNG 單檔 <400KB。

## 2. 驗收矩陣（✅＝實測符合；—＝該頁無此控制項）

| 檢查項 | 💼 我的資產（11 情境） | 🔍 篩選＋單檔 | 🔍 單檔元件 |
|---|---|---|---|
| 橫向溢出 | ✅ 390／1280 全情境、收合與展開皆 0 | ✅ 全查詢態＋6 情境皆 0 | ✅ 15 種輸入＋CONFLICT 皆 0 |
| 最小字級 | ✅ 13px | ✅ 13px | ✅ 13px |
| 觸控 ≥48px（renderer 自帶） | ✅ `<summary>` 358×48 | ✅ 輸入 356×48／1066×48；「查詢」54×48；`<summary>` 332×48；核取框標籤 94×48 | ✅ 輸入 356×48；「查詢」54×48 |
| 觸控 <48px | harness selectbox 輸入 324×38、`Open` 32×38；Streamlit 工具列 28px（D2） | 同左 | 同左 |
| Tab 順序 | ✅ selectbox → A50 → A60（＝視覺順序） | ✅ 輸入 → 查詢 → 摘要 → selectbox → 條件 | ✅ |
| 焦點可見 | ✅ 摘要為預設焦點環；selectbox 有像素變化 | ✅ | ✅ |
| radio 方向鍵 | — 三頁皆無 radio | — | — |
| 鍵盤操作 | ✅ selectbox 方向鍵＋Enter、摘要 Enter／Space | ✅ Enter 送出查詢、Space 勾核取框且結果隨之改變 | ✅ Enter 送出 |
| 缺值≠0 | ✅ A20 四格 11 情境皆 `◇ 資料未備`；A60 件數整數照顯示、`None` 一律 `◇ 資料未備` | ✅ 缺格 `⬜ 資料未備`；篩選計數 0 為 FAKE 池真實計數 | ✅ 缺欄「此欄尚無可顯示的值」 |
| FAKE 與真資料分隔 | 頁頂虛線框（harness）＋`FAKE` 前綴；**卡片本身無 FAKE 標記**（D5） | 頁頂框＋每卡「FAKE 模擬」標籤＋`FAKE 值` | 同左 |
| 敏感字串／工程詞 | ✅ 11 情境（含 ⑩ 假網址／ID／例外）未命中 | ✅ `<script>` 輸入已 escape | ✅ |
| AI／OneBrain 字樣、ActionSlot | ✅ 0 | ✅ 0 | ✅ 0 |
| 對外請求 | ✅ 0 | ✅ 0 | ✅ 0 |

## 3. 狀態矩陣

| 狀態 | 💼 | 🔍 | 證據 |
|---|---|---|---|
| FAKE | 頁頂 harness 框＋`FAKE 基金 n`；A10 基準 `成本` 為 FAKE 個人設定值（D4）；⑨ 50 列於 A50 容器內捲動、不截斷 | 頁頂框＋每卡「FAKE 模擬」；`FAKE-OK01`＝找到・配息型；篩選全勾＋6 池情境 | `screenshots/assets_*`、`fund_search_*`、`fund_lookup_*` |
| Missing | ③ 市值基準未開放（`⬜ 無法判定`／`◇ 資料未備`）；⑤⑦⑪ A60 `◇` | `FAKE-LOW1`（四欄 `⬜ 資料未備`）、`FAKE-OK02`、`undetermined_only`（計數 `無法判定 3`）、`FAKE-OK03` | 同上 |
| 取數失敗 | ⑥ A00／A10／A50 皆「⛔ 取數失敗」；失敗代碼不上畫面 | `FAKE-ERR1`／`FAIL1`／`COOL1`／`IOERR`（「⛔ 取數失敗」＋「這不是對基金身份的判斷」）；篩選 `source_failed` 三區皆「⛔ 取數失敗」、不顯示 N／M | 同上 |
| 未掛載 | 正式 Preview 入口：💼 導覽項「開發中」、`aria-disabled="true"`、無 `href`、不可聚焦；`/ast` → Streamlit 內建英文「Page not found」提示後落回 🌍，無任何 💼 區塊 | 同左（`/exp` 同） | `screenshots/unmounted_*`、`measure_unmounted.json` |

【FACT】🌍 頁在本機無外網，畫面為「0／5 項已取得（其中 3 項取數失敗）」，與 💼／🔍 驗收無關。

## 4. 缺陷與差額

| # | 內容（FACT） | 處置 |
|---|---|---|
| D1 | 💼 頁有 2 個 `a[aria-label="Link to heading"]`（H1 與 A10 `<h4>`；16×16、平時透明、卻是 Tab 停駐點）。`nas_diag` 與 🔍 兩預覽早已避開 | **已修**（`ui_v3/pages/assets.py`）：`st.title(..., anchor=False)`；A10 標題由 `<h4>` 改 `<div class="uv3-card-title" role="heading" aria-level="4">`，樣式對齊原 h4。前後 11 情境×2 寬度：錨點 2→0、可見文字逐字相同、幾何差 ≤0.3px（A10 高 179.5→179.2px） |
| D2 | harness selectbox 輸入 38px、`Open` 32×38（<48）；Streamlit 工具列 28px | 只記錄：非 renderer 一部分；工具列為 Streamlit 預設 |
| D3 | Streamlit 主捲動容器 `section`（stMain）本身是 Tab 停駐點，聚焦無可見變化 | 只記錄：框架行為，需動 Shell／全域，超出授權 |
| D4 | 💼 11 情境中 10 個在 A10 顯示「基準 成本」（FAKE 個人設定值）。`DEC-2026-11-19-09` 條件 (1)：掛載版不得顯示假持股／假金額／個人設定值（含假「成本」）；該 DEC「改用情境 ③」為作者推薦、非客戶核准 | 只記錄：屬 Gate 決定（G2） |
| D5 | FAKE 標示不一致：🔍 每卡有標籤；💼 只有頁頂 harness 框（非 sticky），卡片與 A50 列無 FAKE 標記，A00 寫「來源已讀完」 | 只記錄：屬 G1 |
| D6 | 缺值字樣三套並存：💼 `◇ 資料未備`；🔍 篩選 `⬜ 資料未備`；🔍 單檔元件「此欄尚無可顯示的值」 | 只記錄：`DEC-2026-11-18-01` R2／`-04` (E5) 待客戶裁（G1） |
| D7 | harness 虛線框上緣在 390／1280 被 Streamlit 頁首蓋住約 6px（【INFERENCE】內容 `padding-top:3.4rem`＝54.4px，頁首 60px；`ui_next_batch_gap` 列 4 另記「stHeader 60→40 未做」） | 只記錄：影響只在 harness 框 |
| D8 | 未掛載頁直接網址顯示 Streamlit 內建英文「Page not found」後落回 🌍 | 只記錄：框架預設，掛載 Gate 時一併決定 |

## 5. 距離正式掛載的最小 Gate（≤5 項、依賴順序；不替客戶裁決）

| 順序 | Gate | 目前狀態 | 阻擋原因 | 出處 | 最小解除動作 | 誰能裁示 |
|---|---|---|---|---|---|---|
| G1 | 字樣與 FAKE 標記裁示（缺值 ◇／⬜／無符號；頁頂橫幅；導覽 FAKE 辨識） | 全是 PendingWording；導覽層 FAKE 辨識 S-b／S-c 未選 | 缺值字樣不一致（D6）；FAKE 標記只在 harness（D5） | `DEC-2026-11-19-01` S-a(2)(6)；`-09` 區分欄 2(1)；`DEC-2026-11-18-01` R2；`c_assets_s_ast_m1_gate_v2` §g 第 3 項 | 客戶逐項核定字樣 | 客戶 |
| G2 | 💼 掛載：S-AST-M1 修正版 Gate | 方向已核准（轉述〔待核〕）；修正版未核准；`registered=False` | 情境選擇、S-a(7) 例外形狀（8 條守衛）、Shell 新增結構、Status Bar／頁尾落差；五格加標記後 374／375／390／768 版面從未實測 | `DEC-2026-11-19-01`（P1）；`-09`；v2 卡 §c／§e／§g；`docs/v2/82`；BL-0561 列 14 | 客戶核准 v2 卡 §g 第 1–5 點，再開掛載 PR 並過獨立 QA | 客戶 |
| G3 | 🔍 掛載：先搬模組、後掛載（兩 PR） | renderer 住 `poc/`；`DEC-2026-11-19-04` 裁 G-A（目前不搬、不改守衛） | 守衛禁止 `ui_v3` 引用 `poc/`，須改 `ALLOWED_PREFIX`（G-B 需客戶明文） | `DEC-2026-11-19-04`；`-01` P1；BL-0554 | G2 之後提最小可回滾方案並核准 G-B | 客戶 |
| G4 | 兩頁 OneBrain 預留位置（線框，不渲染） | 80 §7.1／81／82／78 皆無該位置；ActionSlot 頁面未引用 | 可見元件屬 B 類；任何可見字樣＝新 PendingWording | `ui_next_batch_gap` §2b；BL-0561 R3（只含 🌍）；`CLAUDE.md` §-1.5.4 | 先出線框草稿；不得用 ActionSlot 冒充 AI | 客戶（草稿審批） |
| G5 | 真實資料接線（Gate-D 等） | 全是離線 FAKE | 與 G1–G4 互相獨立；G1–G4 通過後仍只是 FAKE 頁 | `DEC-2026-11-19-02／-05／-06`；BL-0555／0551／0545／0542 | 客戶裁 Gate-D 待決與 A 線 Gate | 客戶 |

【INFERENCE】G1→G2 是硬依賴；G3 可與 G2 並行但客戶 `-09` 選了 💼 先；G4 阻擋「兩頁放進 OneBrain 位置」、不阻擋 FAKE 頁掛載；G5 不阻擋 FAKE 掛載。

## 6. OneBrain

【FACT】兩頁（及單檔元件）的 DOM 與可見文字沒有 OneBrain／Digest／ActionSlot／AI 分析／AI 解釋字樣（`measure_leak_onebrain_network.json`）；`ui_v3/pages`、`poc/` 內沒有 `ActionSlot` 引用。位置只在線框／說明層（G4）；本批無渲染、無 FAKE 分析、無 Digest。

## 7. 本批程式變更與變異負控

- 檔案：`ui_v3/pages/assets.py`（D1）；測試：`tests/ui_v3/test_ui_v3_assets_page_renderer.py`（新增單元測試）、`tests/poc_assets_preview/assets_preview_browser_lib.py`（量測加 `headingAnchors`＋判定）、`tests/poc_assets_preview/test_assets_preview_browser.py`（瀏覽器級測試）。未動 registry／`app_preview`／正式頁面／`shared/ui_semantics/rules.py`。
- 變異負控（暫改後立即還原，還原後 `cmp` 確認與修正版逐位元組相同）：A10 標題改回 `h4` → 單元測試轉紅；拿掉 `anchor=False` → 單元測試與瀏覽器級 `test_no_streamlit_heading_anchor_tab_stops[390-multi_currency]` 轉紅。
- ⚠️【FACT】`docs/evidence/c_assets_s_ast_m1_gate_v2_2026_11_19.md` §d 把 `ui_v3/pages/assets.py` 列為「一字不動」。該 v2 卡為執行組草稿、未核准；本批動了該檔，**日後掛載 PR 的白名單說明需同步**。

## 8. 測試輸出（實作組回報原文，於 commit `adb760e2`）

```
tests/ui_v3/test_ui_v3_assets_page_renderer.py    348 passed in 0.96s
tests/poc_assets_preview（含 Chromium 瀏覽器級）  367 passed in 494.17s (0:08:14)
tests/ui_v3（含 slow 瀏覽器級守衛）               3104 passed, 766 warnings in 294.20s (0:04:54)
三支治理守衛（canonical／doc_counters／constitution_file_refs）
                                                  113 passed in 86.75s   （寫入證據檔前）
                                                  113 passed in 90.11s   （證據檔入庫後複跑）
變異 A（A10 標題改回 h4）:     1 failed, 330 passed
變異 B（拿掉 anchor=False）:   1 failed, 342 passed
瀏覽器級（拿掉 anchor=False）: 1 failed, 247 deselected
還原後: 348 passed in 0.96s
```

## 9. NOT VERIFIED

- Streamlit Cloud 實機／真實手機／WebView／讀屏；iOS Safari、Firefox、其他 Chromium 版本。
- 768px、374／375px、190% 文字放大（本批只量 390／1280）；色彩對比。
- 💼 掛進導覽後的版面（registry 禁改，五格加 FAKE／示範標記的實際版面從未實測）。
- 觸控為 `has_touch` 模擬；焦點可見性只證明「有變化」，不證明「對比足夠」。
- exact-head CI、非作者獨立稽核、合併：本報告撰寫時皆未發生。
- 缺陷清單只涵蓋本組實測範圍；「兩頁以外沒有其他同類問題」不宣稱。DEC／BACKLOG 引用取自讀檔，客戶方向多為〔待核〕轉述。

## 10. 產出檔

`report.md`（本檔）；`measure_assets.json`（修正後）、`measure_assets_before_fix.json`（修正前，同一指令碼）、`measure_search.json`、`measure_lookup.json`、`measure_unmounted.json`、`measure_leak_onebrain_network.json`；`screenshots/`（70 張 PNG：💼、🔍、未掛載；`measure_assets_before_fix.json` 內截圖檔名與修正後同名，截圖已用修正後程式覆蓋，兩者可見畫面逐字相同、幾何差 ≤0.3px）。
