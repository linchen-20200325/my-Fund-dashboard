# 🌍 市場頁視覺批 2（ui_v3 Preview-only）報告｜2026-11-20

> 來源：實作組回報（單組產出，未經獨立複驗）；本檔由總管依該回報**轉錄**（實作組的 Write 被拒、未寫成檔）。
> 轉錄處的取捨：只收 FACT 與其量測、R1 核證、Gate 差額；測試輸出照錄。
> 所有量測為本機 Chromium 對 CI fixture 的實測（Preview FAKE，DPR 1）。
> **NOT VERIFIED：Cloud `ui_v3` URL、部署 SHA、真機（iOS／Android／WebView）、系統字級放大、不同 CJK 字型、CI 四項 check、第二組獨立稽核。**
> 基準 main `b103e99c`；本批 commit `b35e7f95`（後續若有修正 commit，以 GitHub 為準）。

## 1. 改動（程式與測試共 4 檔）

| 檔案 | 內容 |
|---|---|
| `ui_v3/shell/nav.py` | `.uv3-statusbar`、`.uv3-footer`、`.uv3-cta-note`、`.uv3-nav-disabled .uv3-nav-soon` 的 `font-size:12px` → `{caption}`（`type.caption`＝13px）；`.uv3-statusbar` 行高 1.5 → 固定 18px（＝原 12px×1.5，使首屏露出量不變）。≤768px 頁首導覽規則未動 |
| `ui_v3/pages/mkt.py` | `status_row_html` 加 `uv3-status-row` 類；已取得列的來源與資料日各包 `<span class="uv3-unit">`；CSS 兩條 `.uv3-status-row{word-break:keep-all;overflow-wrap:anywhere;text-wrap:balance}`、`.uv3-unit{display:inline-block;max-width:100%}` |
| `tests/ui_v3/test_ui_v3_market_page_browser.py` | 新增 `aux_font_violations`、`top_nav_font_violations`、`status_row_violations`、量測測試與折行測試（2 情境×3 寬度）、2 個變異負控 |
| `tests/ui_v3/test_ui_v3_navigation_shell.py` | 靜態 CSS 守衛（含 5 個記憶體內負控）、頁首導覽未動守衛、狀態列標記守衛 |

證據：本資料夾 before／after 的 390／768／1280 各 fold／full／status 共 18 張 PNG（皆 <160KB）、`measure_before.json`、`measure_after.json`、`measure_candidates_not_applied.json` 與 `cand_svg_text_13_390_fold_NOT_APPLIED.png`（Gate 候選的注入量測，**未入程式**）。

### 需複判一點（總管與獨立 QA）
`mkt.py` 在來源／資料日外包 span 屬標記層改動：不增刪可見元件、不改順序與欄位、`innerText` 與改前逐字相同。實作組判為 §-1.5.4 兩步判定第 1 步的「同一版面內的內容呈現」，**此為實作組自己的判斷，未經第二組驗證**。退路：只保留 CSS（`.uv3-status-row` 一條）；日期實測仍未折斷，但只靠行寬碰巧，字樣或來源變長可能再折在連字號。

## 2. 量測（前→後；fixture；視窗 390×844／768×844／1280×800）

| 項目 | 390 | 768 | 1280 |
|---|---|---|---|
| 首屏主圖露出 px（normal） | 199.8→199.8 | 249.4→249.4 | 266.4→266.4 |
| 首屏主圖露出 px（tw_missing 降級） | 129.2→129.2 | 198.8→198.8 | 215.8→215.8 |
| Status Bar 字級／高／行數 | 12→13px／20→20／1（降級 40→40／2） | 12→13px／20→20／1 | 12→13px／20→20／1 |
| 頁尾字級／高 | 12→13px／38.4→41.6（2 行，在頁尾） | 19.2→20.8（1 行） | 19.2→20.8（1 行） |
| 側欄「開發中」標籤（≥769） | — | — | 12→13px；框 50×21.2→53×22.8；所在列高 48→48 |
| 側欄更新資料註記（≥769） | — | — | 12→13px；高 19.2→20.8 |
| 橫向溢出（含展開三個展開列後） | 0→0 | 0→0 | 0→0 |
| 頁首導覽整體框／各格 | 358×61／71.6×60，前後同 | 736×61／147.2×60，前後同 | 隱藏 |

### `各項資料狀態` 逐列（展開後；每列 16px、行高 24.8px）

| 寬度／情境 | 列行數 前→後 | 日期被折斷 前→後 | 「資料日」被折斷 前→後 | 展開內容高 前→後 |
|---|---|---|---|---|
| 390／normal | 2×5→2×5 | VIX 列→無 | 台股列→無 | 289→289 |
| 390／tw_missing | 1,2,2,2,2→同 | VIX 列→無 | 無→無 | 267.1→267.1 |
| 768、1280 | 1×5→1×5 | 無→無 | 無→無 | 165→165（tw_missing 167.9→167.9） |

- 三個展開列的摘要（觸控目標）在三寬度皆 38px 高，前後相同，低於站內 48px（候選 A，被 Gate 擋下）。
- 殘留瑕疵：390 兩行時第二行開頭可能出現「｜」（分隔符是字樣模板本身，CSS 無法黏到上一行行尾）；改前同樣有。總管目視 `after_390_status.png`／`before_390_status.png` 確認：改後無字中折斷（「資／料日」「2026-11-／02」已消除），行首「｜」仍在多列出現。
- 做法取捨（390 實測）：只加 `text-wrap:balance` 無效（否決）；純 CSS（keep-all＋balance，不包 span）日期這次剛好沒折斷但取決於行寬（備案）；來源與日期設 `nowrap` 版面最乾淨但來源名稱比整行寬會橫向溢出（否決）；狀態列字級 16→13px 3 列變一行但更小（否決）。**採用** `inline-block` 單位＋keep-all＋balance＋`overflow-wrap:anywhere` 兜底。

## 3. R1 逐項核證（`git grep` font-size／12px 後逐項判讀）

| # | 位置 | 屬主導覽？ | 前→後 | 判定 |
|---|---|---|---|---|
| 1 | `nav.py::shell_css` `.uv3-statusbar`（含 PREVIEW 標籤） | 否 | 12→13px；行高 1.5→18px | 改（維持 1.5 倍行高會讓首屏退步 1.5px／降級 3px） |
| 2 | `.uv3-footer` | 否 | 12→13px | 改（在頁尾） |
| 3 | `.uv3-cta-note`（側欄註記） | 否（≥769） | 12→13px | 改 |
| 4 | `.uv3-nav-disabled .uv3-nav-soon`（側欄「開發中」標籤） | **邊界案例**：在側欄導覽列內，但是列內標籤 | 12→13px | 改，所在列高仍 48px。若認為側欄導覽列內任何字都算導覽，請單行還原此處 |
| 5 | ≤768 `a[stPageLink]`、其 `<p>`、`.uv3-tn-disabled`（頁首五格 3 處 12px） | 是 | 12→12px | 不改（各格 71.6×60／147.2×60、整體 61px 皆未動） |
| 6 | ≤768 `.uv3-tn-soon`（10px） | 是 | 10→10px | 不改，候選 B |
| 7 | `chart_svg.py` SVG text 11／12 user units | 否 | 390 渲染 10.88／11.87px | 不改（要改版面常數，非純 CSS），候選 C |
| 8 | `tokens.py`／`theme.py` | — | `type.caption`＝13px | 無 12px 字級 |
| 9 | `mkt.py`／`assets.py`／`nas_diag.py` 的 `.uv3-label`／`.uv3-note` | 否 | 本來就 `{caption}` | 無差額 |

## 4. 被 Gate 擋下的差額（fixture 注入 CSS 實測，未入程式）

| 編號 | 候選 | 精確差額 | 擋下原因 |
|---|---|---|---|
| A | 三個展開列摘要 38→48px | 摘要 38→48（×3）；首屏不變；頁面長 +30px；無橫向溢出 | 控制項尺寸變更；`DEC-2026-11-11-02` V2 明文限制本批不可改；是否比照單選 pill 48px 需客戶定 |
| B | 頁首五格字級 12→13px、`開發中` 10→12px | 各格仍 60px 高、框 61px、寬不變；首屏不變 | 屬導覽，本批明令不動；真機／系統字級／CJK 字型 NOT VERIFIED |
| C | 圖內 SVG 刻度／標籤 11→13.1 user units | 390 渲染 10.88→約 12.95px；左側刻度字最左 26.3→21.7px（圖框左緣 17）；首屏不變。僅目視首屏截圖，未逐一檢查整張圖標籤碰撞 | 要改 `chart_svg.py` 版面常數，非純 CSS |
| D | 狀態列改「標籤／來源／資料日」堆疊（消除行首「｜」） | 列高約 49.6→約 54（**未實測，推算**） | 改欄位呈現結構，屬 §-1.5.4 版面異動，須線框先行 |

候選 D 文字線框（未實作，供審）：

```
現況（改後，390）                      候選 D
台股：取得 ｜ 來源 Yahoo Finance        台股：取得
(^TWII)                                  來源 Yahoo Finance (^TWII)
｜ 資料日 2026-11-02                     資料日 2026-11-02
```

實作組推薦：維持本批現況（不做 D）；A 與 B 等客戶決定 48px／導覽字級規則時併批。**此為建議，非裁示。**

## 5. 守衛與變異負控

- 真 Chromium：`aux_font_violations`（Status Bar 與頁尾三寬度、側欄標籤與註記 ≥769 字級＝`type.caption`；Status Bar 高度 ≤ 行數×20px）；`top_nav_font_violations`（≤768 頁首格字級不得縮）；`status_row_violations`（日期與「資料日」不在字中折行、每列 ≤2 行、無橫向溢出）；首屏不退步沿用 `firstscreen_violations`，`_FOLD_BASELINE`（194／244／261）未放寬也未收緊（新量測與批 1 逐位相同）。
- 變異負控（測試內現編，未寫入任何文件）：輔助字退回 12px、Status Bar 行高放大、側欄標籤與註記退回 12px、頁首導覽字縮成 11px 各被報；拿掉 keep-all 與單位後折斷被報；單位撐寬後橫向溢出被報。
- 靜態（無瀏覽器）：含 5 個記憶體內負控，另鎖頁首導覽 12px×3、圖示 20px、`開發中` 10px、最小高 60px、觸控下限 48px 不變，以及狀態列標記字樣逐字等於查表結果。
- 實作過程曾自造一次紅燈（`test_mkt_page_has_no_hardcoded_cjk_screen_wording` 掃到 CSS 字串內的中文註解），已搬到 docstring。

## 6. 測試輸出（原文，行尾空白已去）

環境：scratchpad venv（streamlit 1.59.2）、`UI_V2_CHROMIUM=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`、`-p no:cacheprovider`。

`pytest tests/ui_v3 -q -p no:cacheprovider`（2026-11-20T10:59:27Z→11:05:17Z）：

```
3109 passed, 769 warnings in 348.07s (0:05:48)
exit 0
```

`pytest tests/test_canonical_rule_consistency.py tests/test_doc_counters.py tests/test_constitution_file_refs.py -q -p no:cacheprovider`：

```
113 passed in 92.41s (0:01:32)
```

pre-commit 本機未安裝，實作組以 `git diff --cached --check` 與檔尾換行、檔案大小手動核對；CI 為裁判。

## 7. NOT VERIFIED／INFERENCE

- Cloud URL、部署 SHA、真機、系統字級放大、CJK 字型差異、CI 四項 check、第二組獨立稽核。
- `text-wrap:balance` 需 Chromium 114+／Safari 17.5+／Firefox 121+；不支援者退回 keep-all＋單位（推論日期與「資料日」仍不折斷，兩行不一定平均）。
- 新守衛在 CI 字型下是否穩定（Status Bar 高度判定留 0.6px 容差，行數由高度÷行高推得）。
- 候選 D 的列高約 54px 為推算。
- 已目視的截圖：`after_390_fold`、`after_1280_fold`、`after_390_status`、`before_390_status`、`cand_svg_text_13_390_fold_NOT_APPLIED`；其餘未逐張目視。
- 量測腳本（`measure.py`、`cand.py`）在實作組 scratchpad，未入庫；守衛已把關鍵量測寫進測試。
- 未動禁區：圖表系列色 token、雙線語意、公式、資料來源、權限、`stHeader` 40px、`docs/v2/44`、`ui_v2`、`registry.py`、`app_preview.py`、`.streamlit/config.toml`、`.github/`、導覽高度與觸控尺寸。
