# D3(a)｜資料狀態字彙「唯讀對照表」（草稿，單組作者；待獨立 QA）

> 基準 origin/main aabd5eb8；單組作者草稿，未經獨立 QA；不構成正式契約或裁示。

> 基準：`origin/main` = `aabd5eb8121793bae77491bf97d89a6a4145a38a`（讀取一律用 `git show origin/main:<path>`／`git grep origin/main`；未 checkout、未改程式、未 commit）。
> 性質：**只盤點既有字彙並對照**。不新增狀態、不提案天數／容差／過期規則、不改任何既有判定；凡無法一對一者列入「留給 D3(b)＋D7」，本檔不替客戶決定。

---

## 0. 結論先行

1. **已查到的詞彙族共 16 組**（A～P，定義見第 2 節；「組」是本檔為閱讀分的詞彙來源，不是官方分類），**逐列 97 列**。逐列對照判定：**可 37、否 27、不能判定 33**（計數方法見第 5 節 (d)，附重算指令）。
2. **已有一條「核准過的中樞」**：`shared/ui_semantics/rules.py` 的 `ENTRIES`（11 個規則鍵）＋三張既有程式對照（`STATUS_TO_KEY`、`FRESHNESS_TO_KEY`、`CHIP_KIND_TO_KEY`）＋ `BETA_LEVELS`。凡已查到「程式碼或核准文件明文指到這 11 鍵之一」者，本檔標「可」並附出處；**沒有明文的，不因字面相似就標可**。
3. **同字不同義（最需要 D3(b)／D7 看的）**：
   - `undetermined`：在 view model 的 `status` 欄對到規則鍵 `undetermined`（`⬜ 無法判定`），在 `freshness_state` 欄對到 `threshold_pending`（`⬜ 門檻待裁示`）——兩條不同的對照表。
   - `inconsistent`：Cell 狀態（`exp_profile`，多來源幣別不一致）與 ui_v2 市場比較設定（`mkt/logic.py::REASON_INCONSISTENT`，兩鍵一致性憑證對不上）是**兩件不同的事**。
   - `SRC_*`：`allocation_evidence`（來源涵蓋度狀態，5 個英文代碼）與 `fund_total_return`（「1Y 來源」顯示標籤，中文字串）**前綴相同、型別不同、用途不同**。
   - 「尚未設定」（`⛔`，來源或設定沒設，規則鍵 `not_configured`）與「未設定」（`⬜`，使用者參數留空，規則鍵 `user_param_unset`）：已核准文件明文分開，字面只差一個「尚」字。
4. **「不是最新／◷」沒有一條端到端的核准鏈**：規則表要求「只有正式門檻判為舊才用」，而 New UI2 的 `market_summary` 明文「門檻未裁示，不產生任何其他新鮮度狀態」；ui_v2 設定頁總表的 `◷ 不是最新` 則由「淨值取自預存序列」這類標示觸發（見 F4）。NAV 超過 10 日在 ui_v2 持股頁被併入「資料未備」，沒有獨立 stale 詞（與 `docs/v2/67` §5.3「淨值過期直接併進『資料未備』，沒有獨立 stale」一致）。這些**皆屬 D3(b)＋D7**，本檔只記事實。
5. **三軸分類**：本檔**沒有**提供「資料取得／新鮮度／一致性」三軸分組表。理由：本組查到的既有文件中，`DEC-2026-11-06-02` 的「三軸」指的是**「原字母評級／覆蓋完整／正式准入」**（那是健康維度，不是這三軸），且查到的其他文件沒有把這三個字當成一組已定義的分類（見第 4 節 (a)）。依客戶指示「不得自創分類」，故不提供。

---

## 1. 讀表說明

**欄位**：(1) 原始代碼與顯示文字；(2) 來源檔案與使用位置（路徑＋符號，不寫行號）；(3) 實際資料語意（逐句標〔F〕＝程式碼／docstring／文件逐字可驗，〔I〕＝本組推論）；(4) 已核准規則或尚待 Gate；(5) 可否一對一映射；(6) 無法對齊或衝突事項。

**第 (5) 欄判定定義（本檔自訂，只為讀表，不是新分類）**：
- **可**＝程式碼或已核准文件**明文**建立了對向，且兩邊定義一致，兩邊也沒有合併或分岔；附出處。
- **否**＝已查到語意不同、一對多／多對一，或對向詞不存在。
- **不能判定**＝沒有核准的對照依據，程式與文件證據也不足以斷言相同或相異。

**重要限制**：本檔**沒有跑任何測試**。凡寫「測試鎖」者，是轉述 docstring／註解的自述，不是本組驗證。

---

## 2. 對照表

### A 組｜呈現規則表（`shared/ui_semantics/rules.py`，`ENTRIES`；僅正式模式，BL-0532）

| ID | (1) 代碼／顯示文字 | (2) 來源與使用位置 | (3) 資料語意 | (4) 核准／待 Gate | (5) 可否一對一 | (6) 無法對齊／衝突 |
|---|---|---|---|---|---|---|
| A1 | `ok`（無符號、無字樣） | `rules.py::ENTRIES["ok"]`；`STATUS_TO_KEY["ok"]` | 〔F〕刻意不寫字，note 稱「不是漏字」。〔F〕44 之七其二第 4 條：沒有異常時不寫「資料齊」「正常」 | 44 §5.1 ok 列；44 第七節第三小節之七其二第 4 條 | **可**：B1 `status=ok`、C1、J1 皆指向它（`STATUS_TO_KEY` 為程式碼對照） | 對向是「不加任何字」，不是一個詞 |
| A2 | `attention` ◆ `◆ 需要注意` | `rules.py::ENTRIES["attention"]`；`CHIP_KIND_TO_KEY["attention"]`；`BETA_LEVELS` 的 `attention` | 〔F〕「規則判出的注意事項；≠ 賣出訊號」；〔F〕只承接下層已判出的注意，本表不判定 | 79 §11；DEC-2026-10-17-03 第 (3) 題（rules.py source 欄） | **可**：B9、G3 | 〔I〕它是規則結果的呈現，不是資料取得／新鮮度／一致性；列入只為避免遺漏 |
| A3 | `missing` ◇ `◇ 資料未備` | `rules.py::ENTRIES["missing"]`；`MISSING_TEXT`；`STATUS_TO_KEY["missing"]` | 〔F〕「來源缺或資料尚未備齊；≠ 0、≠ 中性」（79 §11）。〔F〕只限正式模式，示範模式照舊 `⬜ 資料未備` | 79 §11；DEC-2026-11-02-01（四）；BL-0532；44 之七其四 | **可**：B2、C2、D1、E1、F3、G4 | 〔F〕ui_v2 `hld/logic.py`／`exp/logic.py` 的 `ND_TEXT` 字面是 `⬜ 資料未備`；`ui_v2/symbols.py` 以 `MISSING_OLD→MISSING_NEW` 在渲染時換成 ◇（docstring）。〔F〕79 §11 自己登記 `ui_v2/mkt/chart.py::TEXT_EMPTY` 等版面示意字樣「逐一判讀、不全域取代」。〔F〕此詞也承接「NAV 超過 10 日」與 Cell `inconsistent`（見 C2、J4），成因比定義寬 |
| A4 | `undetermined` ⬜ `⬜ 無法判定` | `rules.py::ENTRIES["undetermined"]`；`STATUS_TO_KEY["undetermined"]`；`BETA_LEVELS` | 〔F〕「證據或規則不足以判定（含不適用、未設定）；≠ 安全、≠ 續抱、≠ HOLD」 | 79 §11；67 §2.6；44 之七其四 | **可**：B5、G5 | 〔F〕79 §11 稱此詞「含」不適用、未設定，但 rules 表把 A4／A5／A11 列成三個鍵、同一個 ⬜ 符號；三者的包含關係在核准文件與規則表之間寫法不同，本檔不處理 |
| A5 | `not_applicable` ⬜ `⬜ 不適用` | `rules.py::ENTRIES["not_applicable"]` | 〔F〕「無法判定族的一種」；44 原字為 `⬜ 不適用：<原因>`，本列只收字首 | 44 第五節第一小節業務例外列；客戶 2026-10-16 裁示第 7 點（黃→灰） | **可**：C3、D3、E2 三處皆指向它 | 〔F〕三個來源名（業務例外／算不出來／徽章不適用）落到同一字樣——來源端多對一，不影響本列 |
| A6 | `fetch_failed` ⛔ `⛔ 取數失敗` | `rules.py::ENTRIES["fetch_failed"]`；`STATUS_TO_KEY["failed"]`；`CHIP_KIND_TO_KEY["failed"]`；`BETA_LEVELS` | 〔F〕「上游取數失敗；≠ 查無」（79 §11）；〔F〕note：「已執行取數或連線之後失敗的才是 fetch_failed；兩者不混用」 | 44 §5.5 系統錯誤列；79 §11；44 之七其四 | **可**：B3（僅 reason 非 not_configured 時）、B11、D4（見該列保留）、E3、F2、G1、J3 | 〔F〕一般畫面組合形式 `⛔ <中文資料類> 取數失敗`（`FETCH_FAILED_SCREEN_FORM`）與 `⛔ 此區塊暫時無法判定`（`FETCH_FAILED_SAME_SOURCE_TEXT`，屬系統錯誤族）是同一族的不同句型 |
| A7 | `stale` ◷ `◷ 不是最新` | `rules.py::ENTRIES["stale"]`；`FRESHNESS_TO_KEY["stale"]` | 〔F〕「只有正式門檻判為舊才用，門檻未裁示時見 threshold_pending」；44 的用法是「在原有文字前加 ◷」 | 79 §11；44 之七其四；門檻 **尚待 Gate**（67 §8.5「仍待」；BL-0531 後續項） | **不能判定**：詞對詞有（B4、B7 指向它），但**已查到的實際產生處**與規則表定義不同源，見 F4 | 〔F〕New UI2 `market_summary` 明文不產生 stale（見 N1）；〔F〕ui_v3 `market_page` 的 `domain_state` 只回 ok／missing／failed。→ 目前沒有查到 New UI2 路徑上真的送出 stale 的程式 |
| A8 | `threshold_pending` ⬜ `⬜ 門檻待裁示` | `rules.py::ENTRIES["threshold_pending"]`；`FRESHNESS_TO_KEY["undetermined"]` | 〔F〕80 §5：門檻未裁示時只顯示天數與此字樣。〔F〕note 自陳：tone＝灰是**推論**（無任何來源逐字寫它的顏色，「總管可推翻」） | 80 §5；44 之十九其四第 1 條；門檻 **尚待 Gate**（D3(b)） | **可**：B8、N1 | 〔F〕唯一的灰色 tone 推論；本檔不處理 |
| A9 | `neutral`（無符號無字樣） | `rules.py::ENTRIES["neutral"]`；`CHIP_KIND_TO_KEY["neutral"]` | 〔F〕中性 chip（資料日、延遲天數之類 metadata）；字樣由 view model 的 `label_key` 給 | 80 §5 status chips 列 | **否**：不是資料狀態，無對向詞 | 列入只為完整對應 `CHIP_KIND_TO_KEY` |
| A10 | `not_configured` ⛔ `⛔ 尚未設定` | `rules.py::ENTRIES["not_configured"]`；`REASON_NOT_CONFIGURED`；`NOT_CONFIGURED_FORM`；`NOT_CONFIGURED_RATES_SOURCE_TEXT`（`⛔ 利率資料來源尚未設定`） | 〔F〕成因是某個設定沒設、**沒有執行取數**；永遠不寫成取數失敗；`entry_for_status("failed", "not_configured")` 才分流到此列 | DEC-2026-10-19-05（44 之十二其二第 1 條）；DEC-2026-11-03-09（利率來源句） | **可**：F1（`KIND_UNCONFIGURED`）；B3 在 `reason_code=not_configured` 時指向它 | 〔F〕ui_v3 `market_page::domain_state` 靠比對字串 `未設定 FRED_API_KEY` 才判為 not_configured（`MISSING_FRED_API_KEY_TEXT`，docstring 稱測試鎖）——分流依據是原文字串而非獨立代碼 |
| A11 | `user_param_unset` ⬜ `⬜ 未設定` | `rules.py::ENTRIES["user_param_unset"]` | 〔F〕使用者自己的參數留空（G3†：系統不代填）；不是取數失敗、不是尚未設定的資料來源；**不計入資料狀態件數、不進 β 排序**（DEC-2026-10-20-01）。〔F〕note 自陳 tone＝灰是推論 | 44 SET-3；44 第四節第五小節 `user_setting`；DEC-2026-10-20-01 | **否**：與 A10／F1「尚未設定」字面相近但已核准文件明文分開，不可互映 | 〔F〕note 登記已知落差：ui_v2 資產配置／標的探索那幾格現行畫 ◇（BL-0382，未裁） |

### B 組｜New UI2 view model 的狀態鍵（`ui_v3/viewmodels/common.py`、`components.py`；對照表在 `rules.py`）

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| B1 | `status="ok"` | `ui_v3/viewmodels/common.py::STATUS_OK`；`STATUS_TO_KEY` | 〔F〕80 第 6 節共同欄位 `status` 五值之一 | 80 §6 | **可**：→ A1 | — |
| B2 | `status="missing"` | `common.py::STATUS_MISSING`；`ui_v3/adapters/market_page.py::domain_state`（`資料未備`→missing） | 〔F〕market_view 的「資料未備」在 adapter 轉成 missing，並帶 `reason_code`（無則用字串 `missing`） | 80 §6；`STATUS_TO_KEY` | **可**：→ A3 | 〔F〕adapter 的 reason fallback 是 `domain.get("reason_code") or STATUS_MISSING`，即「原因」欄可能就是 `missing` 本身 |
| B3 | `status="failed"` | `common.py::STATUS_FAILED`；`rules.py::entry_for_status` | 〔F〕`failed` 配 `reason_code=not_configured` → A10，其餘 → A6；`not_configured` 配在非 failed 的 status 上會 `ValueError` | 80 §6；44 之十二其二第 1 條 | **否**：一對二（依 `reason_code` 分流），是已核准設計，但不是一對一 | — |
| B4 | `status="stale"` | `common.py::STATUS_STALE`；`STATUS_TO_KEY["stale"]` | 〔F〕詞彙存在；〔F〕`market_page.py::_meta_status` 對 `ok／missing／failed` 以外的 meta 狀態一律降為 `undetermined` | 80 §6 | **可**：詞對詞 → A7（`STATUS_TO_KEY`） | 〔I〕adapter 路徑上沒有查到產生 `stale` 的程式；〔I〕`_meta_status` 的降級會讓任何真的 stale 的 meta 變成 undetermined——是否合理屬 D3(b)，本檔不判 |
| B5 | `status="undetermined"` | `common.py::STATUS_UNDETERMINED`；`STATUS_TO_KEY` | 〔F〕五值之一 | 80 §6 | **可**：→ A4 | 與 B8（freshness 欄的同名值）指向不同鍵，見 B8 |
| B6 | `freshness_state="fresh"` | `common.py::FRESH_FRESH`；`FRESHNESS_TO_KEY["fresh"]=None` | 〔F〕fresh 不加任何標記，也不寫「正常」 | 80 §5／§6 | **可**：→ 「不加標記」（`entry_for_freshness` 回 None） | 對向不是詞 |
| B7 | `freshness_state="stale"` | `common.py::FRESH_STALE`；`FRESHNESS_TO_KEY["stale"]` | 〔F〕common.py 註解自陳：「規格缺口：80 只點名 `undetermined`，未列舉其他值；取最小集合（fresh／stale／undetermined），待客戶裁示覆核」 | 80 §6（只點名 `undetermined`） | **可**：詞對詞 → A7；**但整組值域本身未經核准** | 〔F〕值域是執行組最小集合，不是核准字彙 |
| B8 | `freshness_state="undetermined"` | `common.py::FRESH_UNDETERMINED`；`FRESHNESS_TO_KEY["undetermined"]="threshold_pending"` | 〔F〕門檻未裁示＝undetermined | 80 §5／§6；門檻尚待 Gate | **可**：→ A8（不是 A4） | ⚠️ 與 B5 同名、不同目標；呈現層必須依欄位而非依字面對照 |
| B9 | chip kind `attention` | `components.py::CHIP_KINDS`；`CHIP_KIND_TO_KEY` | 〔F〕六個 kind 之一 | 80 §5 | **可**：→ A2 | — |
| B10 | chip kind `neutral` | 同上 | 〔F〕六個 kind 之一 | 80 §5 | **可**：→ A9 | — |
| B11 | chip kinds `missing／undetermined／failed／stale` | 同上；`CHIP_KIND_TO_KEY` | 〔F〕`failed`→`fetch_failed`（chip 層沒有 not_configured 分岔） | 80 §5 | **可**：分別 → A3／A4／A6／A7 | 〔F〕分岔只存在於 `status`（B3），chip 層沒有；兩層粒度不同 |

### C 組｜44 §5.1 卡片四態（`ok／資料未備／業務例外／系統錯誤`）

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| C1 | `ok` | `services/v2_tables/market_view.py::STATE_OK`；`ui_v2/{mkt,exp,hld}/logic.py::STATE_OK`；`ui_v2/alo/logic.py::STATE_OK`；`ui_v2/sections.py::STATE_OK`；`ui_v3/adapters/market_page.py::_STATE_OK` | 〔F〕四態「掛在主值上，不掛在整張卡；一個主值同時只處於一個狀態」（44 §5.1 更正註） | 44 §5.1 | **可**：→ A1 | 〔F〕`market_view.py` docstring：四態字面與 `ui_v2/mkt/logic.py::STATE_*` 逐字相同（測試比對，自述） |
| C2 | `資料未備` | 同上 `STATE_MISSING`；`ui_v2/page_health.py::KIND_MISSING` | 〔F〕market_view：沒有正式來源的 domain 交回此狀態＋reason_code；〔F〕`ui_v2/hld/live.py` 註解：NAV 超過 10 日（嚴格 `>`）→ 「視為資料未備」（客戶 2026-10-13 裁示）；〔F〕`ui_v2/exp/live.py::profile_cell_note`：Cell `not_ready` 與 `inconsistent` 都走 `STATE_MISSING` | 44 §5.1；客戶 2026-10-13 裁示（NAV 過期併入）；DEC-2026-11-02-01 | **可**：詞對詞 → A3 | ⚠️ 成因比 A3 定義（來源缺或尚未備齊）寬：同一個詞裝了「沒取到」「NAV 太舊」「來源衝突」三種成因；是否要分開屬 D3(b)＋D7 |
| C3 | `業務例外` | 同上 `STATE_BIZ`（market_view、sections） | 〔F〕主值 `⬜ 不適用`＋一句原因，灰 | 44 §5.1；客戶 2026-10-16 裁示第 7 點 | **可**：→ A5 | 〔F〕ui_v3 `domain_state`：遇 `業務例外` 直接 `ValueError`（「not produced for these domains」）——此詞在 New UI2 市場頁沒有產生者 |
| C4 | `系統錯誤` | 同上 `STATE_ERROR`；`ui_v2/health.py::_ERROR_STATE` | 〔F〕44 §5.5：「取數或計算本身失敗」；〔F〕market_view：缺 FRED 金鑰也給 `系統錯誤`＋`MISSING_FRED_API_KEY` 原文 | 44 §5.1／§5.5 | **否**：→ A6（取數失敗）或 A10（尚未設定）二擇一，且「計算失敗」不在 A6 定義內 | 〔F〕adapter 以原文字串分流（見 A10 (6)） |

### D 組｜44 §5.5 空狀態四種（`來源缺／部分缺／算不出來／系統錯誤`）

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| D1 | `來源缺` | `ui_v2/health.py::_MISSING_EMPTY_KINDS`；44 §5.5 | 〔F〕「這一塊依賴的來源一筆資料也沒有」；正式模式模板 `◇ 資料未備：<中文資料名> 尚無資料` | 44 §5.5；DEC-2026-10-17-03 | **可**：模板已落字 → A3 | — |
| D2 | `部分缺` | `ui_v2/health.py::_MISSING_EMPTY_KINDS`；`ui_v2/set/logic.py::STATUS_BADGE_LITERALS` | 〔F〕「來源只涵蓋區間的一部分；本塊照畫、缺的期間留白、標題掛徽章」；徽章色為黃 | 44 §5.5 | **否**：規則表沒有對應鍵（不是別名缺口，是尚無詞） | 〔F〕`ui_v2/health.py` 把它與 `來源缺` 一起歸入 `◇`（`_MISSING_EMPTY_KINDS`）；44 §5.5 徽章色為黃，A3 為灰——同一歸類下顏色不同 |
| D3 | `算不出來` | 44 §5.5 | 〔F〕「來源齊，但規則的前提不成立」；模板 `⬜ 不適用：<一句話原因>`，灰 | 44 §5.5 | **可**：→ A5 | 與 C3 同指向 A5 |
| D4 | `系統錯誤`（空狀態） | 44 §5.5 | 〔F〕「取數或計算本身失敗」；模板 `⛔ 取數失敗：<訊息原文>` | 44 §5.5 | **不能判定**：44 已落字為「取數失敗」，但定義含「計算本身失敗」，比 A6（上游取數失敗）寬；是否算語意衝突未見核准文件裁示 | 見 C4；本檔不判 |

### E 組｜44 §5.2 徽章「狀態」七字面（`ui_v2/set/logic.py::STATUS_BADGE_LITERALS`）

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| E1 | `資料未備`（灰） | `ui_v2/set/logic.py::STATUS_BADGE_LITERALS`、`_STATUS_BADGE_TONE` | 〔F〕七字面之一；〔F〕`ui_v2/symbols.py` 註解：徽章圖示換 ◇，文字不動 | 44 §5.2 | **可**：→ A3 | — |
| E2 | `不適用`（灰） | 同上 | 〔F〕客戶 2026-10-16 裁示第 7 點：黃→灰，glyph ⚠→⬜ | 44 §5.2 | **可**：→ A5 | — |
| E3 | `取數失敗`（紅） | 同上 | 〔F〕七字面之一 | 44 §5.2 | **可**：→ A6 | — |
| E4 | `推估`（黃） | 同上 | 〔I〕與 provenance 旗標 `is_estimated` 有關（67 §5.3 列出 `is_revised`、`is_estimated`）；本組未讀其產生處 | 44 §5.2 | **否**：規則表沒有對應鍵 | 不在 D3 的缺值／新鮮度／一致性範圍，列入只為完整 |
| E5 | `修正過`（黃） | 同上 | 〔I〕同 E4（`is_revised`） | 44 §5.2 | **否**：同上 | 同上 |
| E6 | `部分缺`（黃） | 同上 | 〔F〕與 D2 同詞 | 44 §5.2 | **否**：同 D2 | 同 D2 |
| E7 | `未定義`（黃） | 同上 | 〔F〕七字面之一；本組未讀其產生處 | 44 §5.2 | **不能判定**：詞面與 `allocation_evidence.NOT_DEFINED`（`not_defined`）相似，但未見任何文件明文對照，不推斷 | 同 K、P 組的內部代碼，不得因字面相似視為同義 |

### F 組｜設定與診斷頁「各頁資料狀態總表」四類（`ui_v2/page_health.py::KINDS`）

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| F1 | `尚未設定`（`KIND_UNCONFIGURED`，不加符號） | `ui_v2/page_health.py`；`ui_v2/health.py::LINE_NOT_CONFIGURED` | 〔F〕「鍵＝哪一個設定」；與取數失敗永遠分開數 | 44 之十三其七 | **可**：→ A10 | 見 A11 |
| F2 | `取數失敗`（⛔） | 同上 `KIND_FETCH` | 〔F〕鍵＝哪一類資料；含「改用預存淨值」句型（`TEXT_MAIN_RETREAT`） | 44 之十三其七；DEC-2026-10-18-02（BL-0375） | **可**：→ A6 | 〔F〕「取數失敗，改用 <日期> 的預存淨值」是**已取得替代值**的失敗，與 A6「上游取數失敗」並置 |
| F3 | `資料未備`（◇） | 同上 `KIND_MISSING` | 〔F〕鍵＝哪一類資料 | 同上 | **可**：→ A3 | — |
| F4 | `不是最新`（◷） | 同上 `KIND_STALE`；`TEXT_MAIN_STALE`＝`◷ 主要原因：部分只顯示最後有效資料` | 〔F〕「整頁只算一項」（`STALE_KEY="整頁"`）；〔F〕`health.py` docstring：`◷` 由呼叫端依該頁既有標示交進來，「目前只有持倉體檢有『淨值取自預存序列』這一種」；〔F〕該 docstring 同段另記 3-C 後狀態行退場、徽章改由總表明細承接 | 44 之七其四；44 之十三其七 | **不能判定**：與 A7 同符號同字樣，但**產生條件是「取自預存序列」，不是「正式門檻判舊」**；兩者是否為同一件事，文件未裁示 | 〔F〕A7 的定義與本列的產生條件不同；〔I〕若兩者要視為同一詞，等於預存序列＝不是最新，此為語意決定，屬 D3(b)，本檔不替客戶選 |

### G 組｜β 階梯七類（`ui_v2/status_class.py`；對照 `rules.py::BETA_LEVELS`）

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| G1 | `取數失敗`（E） | `status_class.py::ERROR`；`BETA_LEVELS` | 〔F〕頁級 presentation 分類，不改 domain block 原判定 | DEC-2026-10-30-04 | **可**：→ A6 | 頁級燈 production 上線以 BL-0411 修好為前提（`resolve_precedence` docstring） |
| G2 | `無持倉`（Z） | `status_class.py::NO_HOLDING` | 〔F〕尚未建立任何持倉 | DEC-2026-10-30-04 | **否**：規則表無字樣（`entry_key=None`，`PENDING_WORDING` 缺口） | 字樣隨 💼 wireframe Gate |
| G3 | `需要注意`（D，◆） | `status_class.py::ATTENTION` | 〔F〕同 A2 | 同上 | **可**：→ A2 | — |
| G4 | `資料未備`（M，◇） | `status_class.py::MISSING` | 〔F〕註「含 A6m／A5c／F-18／F-19」 | 同上 | **可**：→ A3 | — |
| G5 | `未設定或不適用`（U／X，⬜） | `status_class.py::UNSET` | 〔F〕β 把「未設定」與「不適用」併成一級 | 同上 | **可**：→ A4（`BETA_LEVELS` 的 `undetermined`） | 〔F〕但 A11（使用者參數留空）依 DEC-2026-10-20-01 **不進 β**；β 這一級裡的「未設定」與 A11 是否同一件事，本檔未查到文件明文，不推斷 |
| G6 | `只評估一部分`（N*，H7） | `status_class.py::PARTIAL` | 〔F〕無偏離但他卡不完整 | 同上 | **否**：規則表無字樣 | 同 G2 |
| G7 | `無偏離`（N） | `status_class.py::NORMAL` | 〔F〕完整評估且無偏離／帶內 | 同上 | **否**：規則表無字樣；對向本應是「正常」類，但 A1 刻意不寫字 | 〔I〕β 的 `無偏離／帶內` 與 A1「不寫『正常』」的關係，rules.py 未交代 |

### H 組｜原因代碼（reason_code；不是狀態，是狀態的成因）

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| H1 | `no_official_source` | `services/v2_tables/market_view.py::REASON_NO_OFFICIAL_SOURCE`（成交量、市場統計、NASDAQ、MSCI World／EM） | 〔F〕「目前沒有正式資料來源」；狀態為 `資料未備` | DEC-2026-10-27-43 等（market_view docstring） | **否**：是原因不是狀態，層級不同 | — |
| H2 | `eps_forecast_unavailable` | `market_view.py::REASON_EPS_UNAVAILABLE` | 〔F〕EPS 預估資料未取得；狀態為 `資料未備` | 同上 | **否**：同 H1 | — |
| H3 | `undeterminable` | `market_view.py::REASON_UNDETERMINABLE` | 〔F〕「無法判定（缺 EPS 預估與正式 trailing PE）」；狀態仍是 `資料未備`（經 `_missing` 輔助函式） | 同上 | **不能判定** | 〔F〕詞面是「無法判定」，掛的狀態卻是 `資料未備`（C2→A3），不是 A4；兩套詞並用於同一個 domain |
| H4 | `no_closed_observation` | `market_view.py::REASON_NO_OBSERVATION` | 〔F〕「來源有回，但沒有任何一筆通過收盤規則」；狀態 `資料未備` | 同上 | **不能判定**：→ ui_v3 adapter 的 `_NO_OBSERVATION="no_observation"` 是否同義，未見文件對照 | 不因字面相似推斷 |
| H5 | `source_pending_bl0518` | `market_view.py::REASON_SOURCE_PENDING` | 〔F〕註解：已於 2026-10-27 裁示，不再被任何 domain 使用，常數保留供舊引用 | DEC-2026-10-27-43 | **否**：已停用 | 保留常數，非現行字彙 |
| H6 | adapter 層 `not_configured`／`fetch_failed`／`no_observation` | `ui_v3/adapters/market_page.py::REASON_NOT_CONFIGURED`、`_NO_OBSERVATION`；`ui_v3/adapters/market_chart.py::REASON_FETCH_FAILED` | 〔F〕`domain_state` 把 `系統錯誤` 轉成 `failed`＋這兩個 reason 之一 | 80 §6（`reason_code` 只說「下層原因鍵」） | **不能判定**：與 `ui_v3/viewmodels/preview_wording.py` 的 `reason_missing／reason_fetch_failed／reason_not_configured` 字樣對應是暫擬（該檔自陳「執行組暫擬／沿用」） | 暫擬字樣非核准詞 |
| H7 | ui_v2 市場比較設定原因 `missing_baseline／missing_window／inconsistent` | `ui_v2/mkt/logic.py::REASON_MISSING_BASELINE／REASON_MISSING_WINDOW／REASON_INCONSISTENT` | 〔F〕「比較條件不完整的原因」；`inconsistent`＝兩鍵都在、一致性憑證對不上（`comparison_reason`，`pair_consistent is False`） | 客戶 2026-10-13 裁示 Q-07（docstring） | **否**：與 J4 同字不同義（見 J4） | 這是使用者設定一致性，不是資料來源衝突 |

### I 組｜額外發現：L2 取數層的「暫不寫入」代碼

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| I1 | `fred_release_date`／`ndc_no_release_date`／`fx_obs_date_rule`（`PENDING_*`） | `services/v2_tables/market_indicator.py`；畫面文案 `ui_v2/mkt/live.py::REASON_TEXT` | 〔F〕`REASON_TEXT`：公布日尚未接上暫不寫入／來源不提供公布日／本指標規則未定暫不顯示 | 客戶 2026-09-26 裁示（fx 文案） | **不能判定**：不屬 rules 表任何鍵，也無核准對照 | 與 `FX_OBS_DATE_RULE_VERIFIED=False` 並存 |
| I2 | `WITHHELD_*`：`ccy_missing`／`ccy_conflict`／`ccy_not_source_reported`／`fetched_at_missing`／`fetched_at_in_future`／`input_conflict`；`div_outcome_undetermined`／`div_items_rejected`；`PENDING_DIV_*` | `services/v2_tables/nav_dividend.py` | 〔F〕行尾註解逐碼說明（例：`ccy_conflict`＝來源自報與持倉手填或手填之間意思不同；`input_conflict`＝同一檔給了互相矛盾的輸入）。〔I〕本組只讀常數定義處註解，**未讀各碼的完整使用路徑** | 無（內部碼） | **不能判定**：沒有核准對照 | 〔F〕含 `*_conflict` 兩碼，屬「一致性」字彙，**D3(b) 的 conflict 判定會碰到** |

### J 組｜Cell 狀態（`services/v2_tables/exp_profile.py`）

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| J1 | `ok` | `exp_profile.py::STATUS_OK`；`ui_v2/exp/live.py::profile_cell_note` | 〔F〕值照畫、掛來源標示；有失敗來源時標示寫出失敗來源 | `PARTIAL_FAILURE_POLICY="accept"`（規則 12，docstring） | **可**：→ A1 | — |
| J2 | `not_ready` → 畫面 `⬜ 資料未備：<原因>` | `exp_profile.py::STATUS_NOT_READY`；`ui_v2/exp/live.py::profile_cell_note` | 〔F〕docstring：「基本資料缺值保留並 ⬜資料未備」；〔F〕`profile_cell_note`：與 `inconsistent` 同走 `STATE_MISSING` | 客戶裁示（`exp_profile.py` 檔頭） | **可**：→ A3 | 〔F〕字面是 `⬜ 資料未備`（`logic.ND_TEXT`），正式字樣為 `◇ 資料未備`；本檔未查到此畫面是否經 `ui_v2/symbols.py` 換字，不推斷 |
| J3 | `fetch_failed` → `⛔ 取數失敗：<原因>` | `exp_profile.py::STATUS_FAILED`；`profile_cell_note` | 〔F〕L1 `failed`（取不到）才是此狀態；頁面回來但不符身分判準 → ⬜，不是 ⛔（docstring） | 客戶裁示（檔頭） | **可**：→ A6 | — |
| J4 | `inconsistent` → 畫面 `⬜ 資料未備：<原因>` | `exp_profile.py::STATUS_INCONSISTENT`；`profile_cell_note` | 〔F〕「多來源幣別不一致 → ⬜」；`reason` 為「各來源幣別不一致（…）」 | 客戶裁示（檔頭）；docstring「畫面以 ⬜ 呈現」 | **否**：被併入 J2 的同一畫面字樣，沒有獨立詞；語意（來源衝突）與 A3（來源缺）不同 | ⚠️ **D3(b) conflict 的既有實例**：已存在「不一致」狀態，但沒有獨立顯示詞，也沒有容差定義（幣別為字串比對，非數值） |

### K 組｜NAV_STATES（`services/v2_domain/allocation_evidence.py`；docstring 稱「internal technical code／CANDIDATE，不是核准字彙」）

> 〔F〕全模組宣告：「Every name in this module is an INTERNAL CANDIDATE, not approved vocabulary」。〔F〕本組在 ui_v2／ui_v3 底下未查到對 `nav_state` 的讀取（`git grep nav_state -- ui_v2 ui_v3` 無命中）。以下九列都**不是已核准字彙**，本檔不替它們配對。

| ID | (1) | (2) | (3) 〔F〕逐字取自 docstring／行註解 | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| K1 | `present` | `NAV_STATE_PRESENT` | 一般狀態碼 `present` | 無 | **不能判定** | 有列≠新鮮≠有效；本模組不碰新鮮度 |
| K2 | `not_required` | `NAV_STATE_NOT_REQUIRED` | 成本基準（不用 NAV） | 無 | **否**：無對向詞 | — |
| K3 | `not_evaluated` | `NAV_STATE_NOT_EVALUATED` | 基準未知／沒有東西被評估 | 無 | **不能判定** | 67 §5.4 與 79 §11 都出現「not evaluated」概念但無字彙對照 |
| K4 | `error` | `NAV_STATE_ERROR` | 追蹤本身 raise | 無 | **不能判定** | — |
| K5 | `not_assembled` | `NAV_STATE_NOT_ASSEMBLED` | 呼叫端宣告：NAV 端從未組裝／嘗試 | 無 | **否**：無對向詞 | 同名出現在 `NAV_INPUT_STATES`（呼叫端宣告）與 `NAV_STATES`（逐檔），兩層同字 |
| K6 | `failed` | `NAV_STATE_FAILED` | 「the NAV read / key failed」 | 無 | **不能判定** | 同 K 組說明 |
| K7 | `no_data` | `NAV_STATE_NO_DATA` | 已組裝、沒有失敗、沒有被移除、也沒有該檔的列 | 無 | **不能判定** | 〔F〕docstring 的 CONTRACT RISK：此判定靠呼叫端把 assembler 錯誤轉成 `source_state.errors["nav"]`，生產者無法驗證 |
| K8 | `obtained_rejected` | `NAV_STATE_OBTAINED_REJECTED` | 取到但被資料有效性要求拒絕（含在 `nav_not_ready`／assembler 的 `not_fresh`／`too_old`／`withheld`） | 無；10 日規則 **尚待 D7** | **不能判定** | 〔F〕把「過期被拒」與「其他有效性拒絕」同碼；與 ui_v2「過期＝資料未備」(C2) 的關係未見文件對照 |
| K9 | `cause_unknown` | `NAV_STATE_CAUSE_UNKNOWN` | 列缺而證據說不出為什麼 | 無 | **不能判定** | — |

### L 組｜`SRC_*`／`VAL_*`（`allocation_evidence.py`，候選字彙）

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| L1 | `SRC_COMPLETE`＝`complete` | `allocation_evidence.py`（`source_coverage`） | 〔F〕來源涵蓋度：沒有失敗、略過、未知的證據 | 無（候選） | **不能判定** | 〔F〕與 `VAL_COMPLETE` 字串相同（`complete`），不同欄位 |
| L2 | `SRC_INCOMPLETE`＝`incomplete` | 同上 | 〔F〕有跳過分頁／略過列、設定讀失敗或非持倉表讀錯 | 無 | **不能判定** | — |
| L3 | `SRC_UNKNOWN`＝`unknown` | 同上 | 〔F〕有略過證據但沒有持倉可聚合，或面向無效／未提供 | 無 | **不能判定** | — |
| L4 | `SRC_FAILED`＝`failed` | 同上 | 〔F〕`holding` 表讀取失敗 | 無 | **不能判定** | 與 A6 `fetch_failed` 字面相近，未見文件對照 |
| L5 | `SRC_NOT_SELECTED`＝`not_selected` | 同上 | 〔F〕沒有 Active 來源 | 無 | **否**：無對向詞 | — |
| L6 | `VAL_COMPLETE`＝`complete` | 同上（`valuation_completeness`） | 〔F〕沒有失敗也沒有缺口 | 無 | **不能判定** | — |
| L7 | `VAL_INCOMPLETE`＝`incomplete` | 同上 | 〔F〕有類別缺值，或沒有任何類別有值 | 無 | **不能判定** | — |
| L8 | `VAL_NOT_EVALUATED`＝`not_evaluated` | 同上 | 〔F〕有 soft code（例：`nav_not_assembled`） | 無 | **不能判定** | 與 K3 同字串 |
| L9 | `VAL_FAILED`＝`failed` | 同上 | 〔F〕硬性失敗（分母非正、非有限、持倉值非有限等） | 無 | **不能判定** | — |

### M 組｜`fund_total_return.SRC_*`（「1Y 來源」顯示標籤；與 L 組同前綴、不同物）

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| M1 | `SRC_SELF_RESTORED`＝`自算（還原含息淨值）`；`SRC_UNAVAILABLE_PREFIX`＝`⬜ 資料未備／無法判定`；`SRC_NONE`＝`—` | `services/fund_total_return.py`；`resolve_1y_total_return` | 〔F〕2026-10-23 裁示 1B 後只產出前兩種：有值，或無值＋白話原因；`status` 為 `ok`／`unavailable`，`reason` 為 `no_series`／`no_restored_value`／`window_short`（docstring） | 客戶 2026-10-23 裁示 1B（docstring） | **否**：是「值的來源標籤」，不是資料狀態；其中 `SRC_UNAVAILABLE_PREFIX` 字面是 `⬜ 資料未備／無法判定`，同時含 A3 與 A4 兩個詞 | ⚠️ 舊版（Old UI 路徑）字面把「資料未備」與「無法判定」並成一句，與 New UI2 規則表把兩者分成 ◇／⬜ 兩個符號不同 |
| M2 | 相容保留：`SRC_OFFICIAL`、`SRC_PERF_UNLABELED`、`SRC_SELF_TOTAL`、`SRC_SELF_NAV_ONLY`、`SRC_SELF_ANNUALIZED`、`SRC_TOO_SHORT`、`SRC_IMPLAUSIBLE_SUFFIX` | 同上 | 〔F〕註解均寫「相容保留」，且對應口徑已退役（短窗累積、外推年化等） | 同上 | **否**：已退役口徑標籤 | 常數仍在，辨識函式保留；非現行產出 |

### N 組｜門檻待裁示家族

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| N1 | `FRESHNESS_THRESHOLD_PENDING`＝`"threshold_pending"` | `services/v2_domain/market_summary.py` | 〔F〕「門檻未裁示，本模組只給事實……不判新、舊、正常、過期」；〔F〕各序列給 `elapsed_days` 與此唯一狀態；〔F〕「門檻裁示前本模組不產生任何其他新鮮度狀態」；〔F〕值刻意等於規則表鍵 `threshold_pending`（一致性由測試鎖，docstring 自述） | BL-0536-H4、BL-0369；DEC-2026-11-03-01 Q5 B | **可**：→ A8 | 〔F〕經過天數為負（觀測日晚於取得日）照實回報，不改 0 也不改 None；如何呈現留給呈現層——此為既有的「不一致」邊角，**D3(b) 可能碰到** |
| N2 | 新鮮度徽章 `當日`／`延遲 {n} 日` | `ui_v2/hld/live.py::FRESHNESS_TODAY_TEXT`、`FRESHNESS_DELAY_TEXT` | 〔F〕N＝0 與 N≥1 的字面（44 §5.2 新鮮度字面） | 44 §5.2 | **否**：是新鮮度事實的顯示，不是狀態詞；規則表無對應鍵 | 與 A8（只顯示天數與 `⬜ 門檻待裁示`）並存於兩代 UI |
| N3 | `NAV_NOT_READY_DAYS = 10`；超過 → `⬜ 資料未備` | `ui_v2/thresholds.py`；`ui_v2/hld/live.py::NAV_FRESH_DAYS_YELLOW`（別名）；`ui_v2/alo/live.py::assemble_nav` | 〔F〕唯一字面值在 `ui_v2/thresholds.py`；〔F〕持股頁嚴格 `>`；〔F〕與舊介面 `MJ_FRESH_DAYS_*`（2／7）是不同兩套（`thresholds.py` 註解） | 客戶 2026-10-13 裁示（持股）；**跨頁語意尚待 D7**（evidence 文件 D7 (a)～(e)） | **否**：這是一個「數值門檻」，不是詞；其結果被併入 A3 | 本檔不處理數值 |

### O 組｜New UI2 畫面實際使用的狀態相關字樣（`rules.py::APPROVED_WORDING` 與 `ui_v3/viewmodels/preview_wording.py`）

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| O1 | `資料不足`（`insufficient`） | `rules.py::APPROVED_WORDING["insufficient"]` | 〔F〕純文字正式字樣（沒有符號）；〔F〕market 圖表 period／normalization 狀態 `insufficient` 的字樣出處未逐一追（本組未查） | DEC-2026-11-03-07 | **不能判定**：與 A3 `◇ 資料未備`、A4 `⬜ 無法判定` 的邊界未見文件對照 | 三個詞（資料不足／資料未備／無法判定）並存 |
| O2 | `原因未明`／`來源資料無法使用`／`沒有觀測值` | `APPROVED_WORDING["reason_unknown／reason_no_source／reason_no_observation"]` | 〔F〕單序列退回句 `目前僅顯示可用序列；另一序列{原因}，暫不進行比較。` 的原因片段 | DEC-2026-11-03-07 | **否**：是原因片語，不是狀態 | — |
| O3 | `此圖目前沒有可畫的資料` | `APPROVED_WORDING["chart_empty"]` | 〔F〕整張圖無資料的正式字樣 | DEC-2026-11-03-07（客戶 2026-11-03 裁示） | **不能判定**：與 A3 的關係未見文件對照；79 §11 登記 `TEXT_EMPTY`＝「⬜ 資料未取得，無法繪圖」是另一個舊字樣 | 舊字樣 `⬜ 資料未取得` 為 79 §11 登記的版面示意字樣 |
| O4 | Shell 資料狀態：`部分資料未取得（{ok}／{total} 項已取得）`、`其中 {n} 項取數失敗`、`{ok}／{total} 項已取得` | `APPROVED_WORDING["shell_status_*"]`；`ui_v3/viewmodels/shell.py::LEVELS`（`ok／partial／none`） | 〔F〕三個層級加計數，不推估；〔F〕分母＝本次檢查涵蓋的已登錄項目（五條主要序列） | DEC-2026-11-03-11 | **否**：層級（齊全／部分／全缺）是聚合摘要，不是逐項狀態詞 | 其中「取數失敗」與 A6 同詞但在計數句裡；`partial` 與 D2／E6／G6 的「部分」是不同層級 |
| O5 | 暫擬字樣：`缺資料`、`取數失敗`、`尚未設定`、`共同有效觀測日不足`、`有效點數不足` | `ui_v3/viewmodels/preview_wording.py`（`reason_missing／reason_fetch_failed／reason_not_configured／reason_few_common／reason_few_points`） | 〔F〕該檔自陳：「執行組暫擬／沿用」，status 恆為 `pending`；其中 `reason_missing` 自陳註明「取數失敗≠缺資料」 | **尚待 Gate**（`APPROVED_WORDING` Gate） | **否**：暫擬字樣不是核准詞；`缺資料` 與正式的 `資料未備` 並存 | 暫擬字樣非核准，不得當正式字彙 |

### P 組｜額外發現：其他現存的狀態／原因字彙（本組在盤點中順帶讀到；只列字面，不展開）

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| P1 | 歸一化／期間狀態：`ok`／`empty`／`insufficient`／`no_common_base`／`too_few_common_days`／`too_few_points`／`both_missing`；序列層 `missing`／`withheld`；模式 `pair／single／fallback／none` | `services/v2_domain/periods.py`、`services/v2_domain/normalization.py` | 〔F〕中性英文碼；〔F〕「共同有值日不足 2 天」是定義不是門檻 | 80／DEC-2026-11-02-07（UI-13） | **不能判定** | `missing` 在此指「整條序列沒有有效值」，與 B2 `status=missing` 同字不同層（`status` 是 domain 狀態，此為序列結果） |
| P2 | 圖表可比性：`comparable`／`not_comparable`／`not_evaluated`／`undetermined` | `allocation_evidence.py`（`CHART_*`） | 〔F〕CANDIDATE；〔F〕`undetermined`＝「無阻擋事實、但有判斷待決閘」 | 無（候選）；Adapter 恆輸出 `withheld_pending_approval` | **不能判定** | 第三個 `undetermined`（B5、B8、P2 三處同字） |
| P3 | L1 declared_profile 狀態：`ok`／`not_listed`／`failed`／`unrecognized_page`／`not_found`／`code_unmapped` | `repositories/fund/declared_profile.py::STATUS_*` | 〔F〕行註解：`unrecognized_page`＝頁面回來但不符身分判準；`not_found`＝所有嘗試的網址皆 404；`code_unmapped`＝清單成功、代碼 0 命中 | 無 | **不能判定** | 這些被 `exp_profile` 轉成 Cell 四態（J）；轉換為 L2 內部規則，本組未逐條對照 |
| P4 | 偏離略過類別：`missing／missing_other／error／na／not_ready` | `services/v2_domain/deviation.py::SKIP_KINDS` | 〔F〕五類；取數失敗優先（`SKIP_KINDS_YIELDING_TO_ERROR`） | 總管 2026-10-02 J1 裁定（註解） | **不能判定** | `not_ready` 與 Cell `not_ready`（J2）同字，來源層級不同 |
| P5 | 缺值原因碼：`nav_absent／nav_stale／nav_stale_undated／fx_absent` | `services/v2_domain/holdings.py::REASON_*` | 〔F〕「在過期名單」＝`nav_stale` | 無 | **不能判定** | 〔F〕這是**已存在**的「淨值過期」專屬原因碼，但狀態仍落在資料未備（C2）——與 67 §5.3 的「沒有獨立 stale」描述並存，D7 須知 |
| P6 | 行動詞呈現型態 `⬜ 無法判定（資料未備／證據不足）` | `rules.py::ACTION_UNDETERMINED_FORM`；67 §2.6、§8.2 | 〔F〕行動詞「無法判定」的呈現；括號內是「缺什麼」的兩種原因，**不是新行動詞** | 67 §2.6、§8.2；44 之四其三 | **不能判定**：括號內「資料未備」是否等同 A3，文件未明文 | 與 A4 字樣的差別是括號補語 |
| P7 | 舊介面「`stale`」旗標（資料品質）與 provenance `cache_fallback`／`stale` | `shared/data_quality.py`（`stale` 以 `MJ_FRESH_DAYS_YELLOW` 判）；`services/v2_tables/nav_dividend.py`（`provenance.cache_fallback`、`provenance.stale`） | 〔F〕`ui_v2/thresholds.py` 註解：舊介面 `MJ_FRESH_DAYS_GREEN／YELLOW`（2／7）管舊 UI 與 L2 的 `stale`，與新常數是不同兩套；〔F〕`nav_dividend`：`stale = quality.get("stale")` 僅在退回預存序列時才有值 | 無 | **不能判定** | 67 §5.3 列為「三套說法」的一部分（nav provenance、設定頁「不是最新」、市場指標延遲天數）；本組未重新量測「三套」是否恰好為三 |
| P8 | `COMPARISON_*`／ui_v2 市場比較條件狀態：`complete／unset／incomplete_setting／read_failed` | `ui_v2/mkt/logic.py::comparison_reason`（docstring） | 〔F〕使用者「比較設定」兩鍵的狀態 | 客戶 2026-10-13 裁示 Q-07 | **否**：使用者設定狀態，不是資料狀態（同 A11 的性質） | 與 H7 同一個機制 |

---

## 3. 對 67 §5.3「狀態字彙至少三套」與四態的對應（逐字取自 67 §5.3 缺口欄）

67 §5.3 表中與狀態直接相關的兩列，其「repo 既有承載」欄原文列的項目，在本表的位置如下（**本檔不重新斷言「恰好幾套」**，67 自己也寫「至少」）：

| 67 §5.3 原列項目 | 在本表 |
|---|---|
| 44 第五節第一小節四狀態 | C 組（C1～C4）；§5.5 空狀態四種為 D 組（67 沒有點名它，本檔另列） |
| Cell 的 `not_ready`／`fetch_failed`／`inconsistent` | J 組（J1～J4） |
| 設定頁總表四類 | F 組（F1～F4） |
| `market_view` 的 `reason_code` | H 組（H1～H5） |
| nav 的 `provenance.stale`、`cache_fallback` | P7；`nav_dividend` 的 `PENDING_*`／`WITHHELD_*` 見 I2 |
| 市場指標的延遲天數 | N1、N2 |

---

## 4. 附件

### (a) 三軸（資料取得／新鮮度／一致性）分類

**本檔不提供。** 查證：
- `docs/DECISIONS.md` 的 `DEC-2026-11-06-02`（基金健康維度）寫的是「原字母評級 ≠ 覆蓋完整 ≠ 正式准入」；`docs/evidence/onebrain_decision_gate_route_and_risk_check_2026_11_08.md` 的「資料健康／Freshness」一列引用它並稱「三軸分開」，但 `DEC-2026-11-06-02` 本文的三項與「取得／新鮮度／一致性」不是同一組。
- 其餘查到的「三軸」字樣（`STATE.md` 的 indicator taxonomy、`docs/v2/10_db_inventory.md` 的「誰讀它／狀態」等）屬其他主題。
- 本組沒有在既有文件中查到「資料取得／新鮮度／一致性」被定義成一組分類。
- 依客戶指示，不自創分類；若客戶要此三軸，須先由 D3(b)＋D7 之外的裁示定義。

### (b) 無法對齊清單（逐項，僅陳述事實）

1. **A7／F4／B4／B7**：`◷ 不是最新`——規則表定義（正式門檻判舊）、New UI2 實況（不產生）、ui_v2 實況（預存序列標示）三者不同源。
2. **C2／J2／J4／P5／K8**：`資料未備` 同時承接「沒取到」「NAV 超過 10 日」「來源衝突（幣別不一致）」；`nav_stale`、`obtained_rejected` 是已存在的過期專屬碼，但沒有獨立顯示詞。
3. **J4**：已存在「不一致」狀態，沒有獨立顯示詞，沒有數值容差定義（幣別為字串比對）。
4. **B5／B8／P2**：`undetermined` 三處同字，指向不同規則鍵或候選語意。
5. **inconsistent**：J4（來源幣別）與 H7（使用者設定兩鍵憑證）同字不同義。
6. **SRC_\***：L1～L5（涵蓋度狀態）與 M 組（來源標籤）同前綴不同物。
7. **A10／A11／F1／G5**：「尚未設定」與「未設定」；A11 不進 β，但 G5 的「未設定或不適用」一級與 A11 的關係未見文件明文。
8. **C4／D4**：系統錯誤的定義含「計算失敗」，與 A6「上游取數失敗」不同寬。
9. **A3 vs `ND_TEXT`**：正式 `◇ 資料未備` 與程式常數 `⬜ 資料未備` 並存；經 `ui_v2/symbols.py` 在渲染時換字（docstring 自述，本組未實跑畫面）。
10. **O1／O3／O5**：`資料不足`、`此圖目前沒有可畫的資料`、`缺資料`（暫擬）與 `資料未備`、`無法判定` 之間的邊界未見文件對照。
11. **D2／E6／G6／O4**：「部分」一詞出現在四個不同層級（空狀態、徽章、β、Shell 聚合）。
12. **A8／A11 的 tone＝灰**：`rules.py` note 自陳為推論。
13. **K、L 兩組**：整組為 INTERNAL CANDIDATE，沒有任何核准對照。

### (c) 留給 D3(b)＋D7 的問題清單（**只列問題，不給答案**）

1. 是否要有獨立的 stale 詞？若有，它與 `資料未備`、`不是最新`、`門檻待裁示` 的關係是什麼？（新字樣另受 `APPROVED_WORDING` Gate）
2. `不是最新（◷）` 的觸發條件是「正式門檻」還是「預存序列／cache fallback」？兩者是否為同一件事？
3. 各來源的 `stale_after`、`expected_lag`、`frequency` 逐來源值；PIT 取哪一欄（`CLAUDE.md` §2.3）；月度 `[STALE: XXd]` 標籤是否沿用。
4. NAV 10 日規則：(a)「今天」是否台灣日期；(b) 跨頁適用範圍；(c) 未來日期 NAV 語意；(d) `>` 或 `>=`；(e) 若搬遷的中立擁有者。（D7 原五項）
5. 「不一致」如何判定：何謂同 as-of 的不一致；數值來源有無容差；字串型欄位（如幣別）是否適用同一套；不一致時顯示什麼，被捨棄的來源與差異是否保留。
6. `業務例外`、`來源衝突`、`無法判定` 是否應各自獨立顯示，還是繼續併入同一個符號。
7. `資料未備` 的成因（沒取到、過期、衝突）是否需要在呈現層分開標示。
8. 經過天數為負（觀測日晚於取得日）如何呈現。
9. `⛔ 取數失敗：改用預存淨值` 是否仍算「取數失敗」，或應有另一個狀態。
10. `undetermined` 在 `status` 與 `freshness_state` 兩個欄位的雙重角色是否保持。
11. `未設定` 與 `尚未設定` 的邊界，以及 β 的 `未設定或不適用` 是否包含使用者參數。
12. `SRC_*`／`VAL_*`／`NAV_STATES` 這組候選碼是否要升格為核准字彙，或維持內部碼；其與規則表鍵是否要有對照表。

### (d) 本檔查證範圍、指令、未涵蓋範圍

**基準**：`origin/main` = `aabd5eb8121793bae77491bf97d89a6a4145a38a`；`git fetch` 後以 `git rev-parse origin/main` 確認同值。

**主要指令（可重跑；repo 根目錄）**：

```
git grep -n -E "NAV_STATES|\bSRC_[A-Z_]+ *=|\bVAL_[A-Z_]+ *=|threshold_pending|not_ready|fetch_failed|inconsistent" origin/main -- '*.py'
git grep -n -E "^(STATUS|STATE|KIND|FRESH|REASON|MISS|NOT_|SRC|VAL|LEVEL|CLASS)[A-Z_]* *=|^[A-Z_]*(STATUSES|STATES|KINDS) *=" origin/main -- 'ui_v2/*.py' 'ui_v2/**/*.py' 'ui_v3/**/*.py' 'services/v2_domain/*.py' 'services/v2_tables/*.py' 'repositories/fund/declared_profile.py'
git grep -n -E "^PENDING_[A-Z_]+ *=|^WITHHELD_[A-Z_]+ *=" origin/main -- '*.py'
git grep -n -E "三軸|三個軸|資料取得.{0,6}新鮮度" origin/main -- '*.md'
git show origin/main:<path>   # 逐檔讀取：rules.py、ui_v2/health.py、ui_v2/page_health.py、ui_v2/status_class.py、
                              # services/v2_tables/market_view.py、exp_profile.py、nav_dividend.py（常數段）、
                              # services/v2_domain/allocation_evidence.py、market_summary.py、normalization.py、periods.py、
                              # holdings.py（常數段）、deviation.py、services/fund_total_return.py、
                              # ui_v3/viewmodels/{common,components,shell,preview_wording}.py、ui_v3/adapters/market_page.py、
                              # ui_v2/exp/live.py、ui_v2/mkt/logic.py、docs/v2/44、67、79
```

**未涵蓋（分類敘述，不是窮舉）**：
- **未逐檔回查所有 `git grep` 命中**：第一條指令的命中包含大量註解與測試；本組只讀了常數定義處與上列檔案，**未保證沒有其他位置定義了同名或同義的狀態字串**。`git grep` 的字表只涵蓋 `NAV_STATES`／`SRC_*`／`VAL_*`／`threshold_pending`／`not_ready`／`fetch_failed`／`inconsistent` 與常見 `STATUS_`／`STATE_`／`KIND_` 前綴；不用這些名字的狀態字串不在範圍內。
- **Old UI（`ui/`、`services/` 舊路徑）**：只讀到 `services/fund_total_return.py`、`shared/data_quality.py` 的引用處；其他舊 UI 的狀態用詞（含 `is_stale`、`is_proxy`、`is_imputed` 等旗標）**未盤點**。
- **`docs/v2/75`、`docs/v2/80`、`docs/v2/79` 的其餘章節**：只讀 79 §11、80 的狀態相關列，其餘按需未讀；`docs/v2/44` 只讀 §5.1、§5.2（透過程式註解間接）、§5.5。
- **未讀**：各 `WITHHELD_*`／`PENDING_*` 的完整使用路徑（只讀常數處註解）；`ui_v2/symbols.py` 的完整渲染邏輯與畫面實跑；`ui_v3/pages/*` 的畫面組裝；`ui_v2/set/` 各徽章的產生處；`repositories/v2_source_status`（冷卻）的狀態用詞。
- **未執行任何測試或畫面**；所有「測試鎖」皆為 docstring 自述。
- **未查證**：67 §5.3「至少三套」與 AUD R6「至少 5 套」中「套」的點算方式（兩者原文即未逐一點算）。本檔分了 16 組，**這是本組為閱讀所分，不等於官方「套數」**，不得引用為任何一方的點算結果。

**計數方法（第 0 節數字）**：在第 2 節各表中，以第 (5) 欄開頭粗體詞統計：

```
awk -F'|' '/^\| [A-P][0-9]+ \|/{ if ($7 ~ /^ *\*\*可/) k++; else if ($7 ~ /^ *\*\*否/) n++; else if ($7 ~ /^ *\*\*不能判定/) u++; t++ } END{print "rows="t" 可="k" 否="n" 不能判定="u}' C_d3a_crosswalk.md
```

### (e) 單組揭露（§-2 規則 6）

- 本檔由**單一作者組**產出，**沒有第二組獨立複驗**；所有〔I〕推論只是待驗事項，不得作為後續動作的前提。
- 第 (5) 欄的「可／否／不能判定」是本組依第 1 節自訂定義作的判斷；**「可」僅在查到明文出處時才標**，「否」「不能判定」是保守判斷，非客戶裁示。
- 第 0 節「97 列、可 37／否 27／不能判定 33」為本組以上列 awk 指令計得；獨立 QA 請重跑並核對，數字若有出入以重跑結果為準。
- 本檔沒有新增任何狀態、字樣、數值或門檻；凡本檔出現的字樣皆為既有代碼或文件的轉錄，並已標明其核准狀態（核准／暫擬／內部候選／已停用）。
