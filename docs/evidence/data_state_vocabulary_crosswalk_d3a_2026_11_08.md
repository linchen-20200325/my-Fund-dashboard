# D3(a)｜資料狀態字彙「唯讀對照表」（回修第二輪版：依獨立 QA 兩輪意見修訂；單組作者）

> 基準 origin/main aabd5eb8；單組作者草稿，未經獨立 QA；不構成正式契約或裁示。
> 「可」欄計數為作者判定，不得當作已驗事實引用；G4／J1／A1（及連動的 B1、C1）已於第三輪覆核。

> 基準：`origin/main` = `aabd5eb8121793bae77491bf97d89a6a4145a38a`（讀取一律用 `git show origin/main:<path>`／`git grep origin/main`；未 checkout、未改程式、未 commit）。
> 性質：**只盤點既有字彙並對照**。不新增狀態、不提案天數／容差／過期規則、不改任何既有判定；凡無法一對一者列入「留給 D3(b)＋D7」，本檔不替客戶決定。

---

## 0. 結論先行

1. **已查到的詞彙族共 17 組**（A～Q，定義見第 2 節；「組」是本檔為閱讀分的詞彙來源，不是官方分類），**逐列 110 列**（含回修新增的 Q 組 7 列、P9～P13、N2b）。逐列對照判定（**嚴格讀法**：字面相同或程式有映射都不算語意一致，見第 1 節）：**可 12、否 44、不能判定 54**（計數方法見第 4 節 (d)，附重算指令）。原版（97 列）為 可 37／否 27／不能判定 33；第一輪回修版（110 列）為 可 23／否 40／不能判定 47；第二輪（110 列）為 可 17／否 40／不能判定 53；第三輪再下修 A1、B1、C1、G4（可→否）、J1（可→不能判定）。第二輪下修 A8、A10、B5、B8、F1（可→不能判定）、J2（否→不能判定）、D1（可→否）。
2. **已有一條「核准過的中樞」**：`shared/ui_semantics/rules.py` 的 `ENTRIES`（11 個規則鍵）＋三張既有程式對照（`STATUS_TO_KEY`、`FRESHNESS_TO_KEY`、`CHIP_KIND_TO_KEY`）＋ `BETA_LEVELS`。凡已查到「程式碼或核准文件明文指到這 11 鍵之一」者，本檔標「可」並附出處；**沒有明文的，不因字面相似就標可**。
3. **同字不同義（最需要 D3(b)／D7 看的）**：
   - `undetermined`：在 view model 的 `status` 欄對到規則鍵 `undetermined`（`⬜ 無法判定`），在 `freshness_state` 欄對到 `threshold_pending`（`⬜ 門檻待裁示`）——兩條不同的對照表。
   - `inconsistent`：Cell 狀態（`exp_profile`，多來源幣別不一致）與 ui_v2 市場比較設定（`mkt/logic.py::REASON_INCONSISTENT`，兩鍵一致性憑證對不上）是**兩件不同的事**。
   - `SRC_*`：`allocation_evidence`（來源涵蓋度狀態，5 個英文代碼）與 `fund_total_return`（「1Y 來源」顯示標籤，中文字串）**前綴相同、型別不同、用途不同**。
   - 「尚未設定」（`⛔`，來源或設定沒設，規則鍵 `not_configured`）與「未設定」（`⬜`，使用者參數留空，規則鍵 `user_param_unset`）：已核准文件明文分開；另有第三種用法（掛在 `⬜ 不適用：` 與 `⬜ 資料未備：` 底下的 `尚未設定…` 句型），見 A10 (6)。
4. **「不是最新／◷」沒有一條端到端的核准鏈，且已查到至少三種觸發來源**：規則表 A7 要求「只有正式門檻判為舊才用」；而 44 第七節第三小節之七其四明列 ◷ 的三個觸發——(1) 新鮮度徽章畫成黃的那一段、(2) `SET-1` 超過新鮮度上限的筆（上限是**使用者自設參數** `set_max_age_days`）、(3) 顯示最後一筆有效值時（Q 組）。New UI2 的 `market_summary` 則明文不產生 stale。NAV 超過 10 日在 ui_v2 持股頁被併入「資料未備」，沒有獨立 stale 詞（與 `docs/v2/67` §5.3 一致）。這些**皆屬 D3(b)＋D7**，本檔只記事實。
5. **三軸分類**：本檔**沒有**提供「資料取得／新鮮度／一致性」三軸分組表。理由：本組查到的既有文件中，`DEC-2026-11-06-02` 的「三軸」指的是**「原字母評級／覆蓋完整／正式准入」**（那是健康維度，不是這三軸），且查到的其他文件沒有把這三個字當成一組已定義的分類（見第 4 節 (a)）。依客戶指示「不得自創分類」，故不提供。

---

## 1. 讀表說明

**欄位**：(1) 原始代碼與顯示文字；(2) 來源檔案與使用位置（路徑＋符號，不寫行號）；(3) 實際資料語意（逐句標〔F〕＝程式碼／docstring／文件逐字可驗，〔I〕＝本組推論）；(4) 已核准規則或尚待 Gate；(5) 可否一對一映射；(6) 無法對齊或衝突事項。

**第 (5) 欄判定定義（本檔自訂，只為讀表，不是新分類）**：
- **可**＝程式碼或已核准文件**明文**建立了對向，且**兩邊定義一致**，兩邊也沒有合併或分岔；附出處。**嚴格讀法（回修版）**：程式碼有映射、或字面相同，**都不等於語意一致**；該列自己的 (3)(6) 欄若記載了多對一、成因較寬、對向未定或同字不同義，就不得標「可」。
- **一致套用的三條（回修第二輪明文化）**：(i) 該列 (6) 欄若記載「同字不同義」或「同名不同目標」，不得標可；(ii) 名稱不同的來源概念併入同一個畫面字樣，各來源列標否；(iii) 名稱相同、詞對詞的配對（例：E1／F3／G4 對 A3），只要 (6) 沒有 (i)(ii) 的記載才可標可。
- **A 組（規則表）各列的判定＝對其 (5) 欄所列各個對向的整體**：任一對向不成立，A 列就不是「可」；各配對的細節在對向那一列。
- **否**＝已查到語意不同、一對多／多對一（含「不同名稱的來源概念併入同一個畫面字樣」），或對向詞不存在（**對向為「不加任何字」者，例如 `ok`、`fresh`，視為對向詞不存在，標否**）。
- **不能判定**＝沒有核准的對照依據，程式與文件證據也不足以斷言相同或相異。

**重要限制**：本檔**沒有跑任何測試**。凡寫「測試鎖」者，是轉述 docstring／註解的自述，不是本組驗證。

---

## 2. 對照表

### A 組｜呈現規則表（`shared/ui_semantics/rules.py`，`ENTRIES`；僅正式模式，BL-0532）

| ID | (1) 代碼／顯示文字 | (2) 來源與使用位置 | (3) 資料語意 | (4) 核准／待 Gate | (5) 可否一對一 | (6) 無法對齊／衝突 |
|---|---|---|---|---|---|---|
| A1 | `ok`（無符號、無字樣） | `rules.py::ENTRIES["ok"]`；`STATUS_TO_KEY["ok"]` | 〔F〕刻意不寫字，note 稱「不是漏字」。〔F〕44 之七其二第 4 條：沒有異常時不寫「資料齊」「正常」 | 44 §5.1 ok 列；44 第七節第三小節之七其二第 4 條 | **否**：B1 `status=ok`、C1、J1 皆指向它（`STATUS_TO_KEY` 為程式碼對照） |對向是「不加任何字」，不是一個詞；〔回修三〕改為否：對向是「不加任何字」，依第 1 節視為對向詞不存在；B1、C1 與 A1 是同名 `ok` 在各層的重複，不是與另一個狀態詞的對照，一併改否；J1 見該列 |
| A2 | `attention` ◆ `◆ 需要注意` | `rules.py::ENTRIES["attention"]`；`CHIP_KIND_TO_KEY["attention"]`；`BETA_LEVELS` 的 `attention` | 〔F〕「規則判出的注意事項；≠ 賣出訊號」；〔F〕只承接下層已判出的注意，本表不判定 | 79 §11；DEC-2026-10-17-03 第 (3) 題（rules.py source 欄） | **可**：B9、G3 | 〔I〕它是規則結果的呈現，不是資料取得／新鮮度／一致性；列入只為避免遺漏 |
| A3 | `missing` ◇ `◇ 資料未備` | `rules.py::ENTRIES["missing"]`；`MISSING_TEXT`；`STATUS_TO_KEY["missing"]` | 〔F〕「來源缺或資料尚未備齊；≠ 0、≠ 中性」（79 §11）。〔F〕只限正式模式，示範模式照舊 `⬜ 資料未備` | 79 §11；DEC-2026-11-02-01（四）；BL-0532；44 之七其四 | **否**：B2、C2、D1、E1、F3、G4 | 〔F〕ui_v2 `hld/logic.py`／`exp/logic.py` 的 `ND_TEXT` 字面是 `⬜ 資料未備`；`ui_v2/symbols.py` 以 `MISSING_OLD→MISSING_NEW` 在渲染時換成 ◇（docstring）。〔F〕79 §11 自己登記 `ui_v2/mkt/chart.py::TEXT_EMPTY` 等版面示意字樣「逐一判讀、不全域取代」。〔F〕此詞也承接「NAV 超過 10 日」與 Cell `inconsistent`（見 C2、J4），成因比定義寬；〔回修〕改為否：B2／D1／E1／F3／G4 各自成立，但 C2、J2、J4 把「NAV 過期」「來源衝突」併進同一個詞，成因比 A3 定義寬（多對一） |
| A4 | `undetermined` ⬜ `⬜ 無法判定` | `rules.py::ENTRIES["undetermined"]`；`STATUS_TO_KEY["undetermined"]`；`BETA_LEVELS` | 〔F〕「證據或規則不足以判定（含不適用、未設定）；≠ 安全、≠ 續抱、≠ HOLD」 | 79 §11；67 §2.6；44 之七其四 | **不能判定**：B5、G5 | 〔F〕79 §11 稱此詞「含」不適用、未設定，但 rules 表把 A4／A5／A11 列成三個鍵、同一個 ⬜ 符號；三者的包含關係在核准文件與規則表之間寫法不同，本檔不處理；〔回修〕改為不能判定：B5 配對成立，但 79 §11「含」與 rules 表三鍵並列對包含關係的寫法不同，整體無法斷言一對一 |
| A5 | `not_applicable` ⬜ `⬜ 不適用` | `rules.py::ENTRIES["not_applicable"]` | 〔F〕「無法判定族的一種」；44 原字為 `⬜ 不適用：<原因>`，本列只收字首 | 44 第五節第一小節業務例外列；客戶 2026-10-16 裁示第 7 點（黃→灰） | **否**：C3、D3、E2 三處皆指向它 | 〔F〕三個來源名（業務例外／算不出來／徽章不適用）落到同一字樣——來源端多對一，不影響本列；〔回修〕改為否：C3「業務例外」、D3「算不出來」、E2「不適用」三個名稱不同的來源概念併入同一字樣（多對一）；且 79 §11 稱 A4 含此詞 |
| A6 | `fetch_failed` ⛔ `⛔ 取數失敗` | `rules.py::ENTRIES["fetch_failed"]`；`STATUS_TO_KEY["failed"]`；`CHIP_KIND_TO_KEY["failed"]`；`BETA_LEVELS` | 〔F〕「上游取數失敗；≠ 查無」（79 §11）；〔F〕note：「已執行取數或連線之後失敗的才是 fetch_failed；兩者不混用」 | 44 §5.5 系統錯誤列；79 §11；44 之七其四 | **否**：B3（僅 reason 非 not_configured 時）、B11、D4（見該列保留）、E3、F2、G1、J3 | 〔F〕一般畫面組合形式 `⛔ <中文資料類> 取數失敗`（`FETCH_FAILED_SCREEN_FORM`）與 `⛔ 此區塊暫時無法判定`（`FETCH_FAILED_SAME_SOURCE_TEXT`，屬系統錯誤族）是同一族的不同句型；〔回修〕改為否：E3、G1、J3 配對各自成立，但 B3（一對二分流）、C4／D4（定義含計算失敗）、F2（取數失敗但已改用預存值）使 A6 整體不是一對一 |
| A7 | `stale` ◷ `◷ 不是最新` | `rules.py::ENTRIES["stale"]`；`FRESHNESS_TO_KEY["stale"]` | 〔F〕「只有正式門檻判為舊才用，門檻未裁示時見 threshold_pending」；44 的用法是「在原有文字前加 ◷」 | 79 §11；44 之七其四；門檻 **尚待 Gate**（67 §8.5「仍待」；BL-0531 後續項） | **不能判定**：詞對詞有（B4、B7 指向它），但**已查到的實際產生處**與規則表定義不同源，見 F4 | 〔F〕New UI2 `market_summary` 明文不產生 stale（見 N1）；〔F〕ui_v3 `market_page` 的 `domain_state` 只回 ok／missing／failed。→ 目前沒有查到 New UI2 路徑上真的送出 stale 的程式 |
| A8 | `threshold_pending` ⬜ `⬜ 門檻待裁示` | `rules.py::ENTRIES["threshold_pending"]`；`FRESHNESS_TO_KEY["undetermined"]` | 〔F〕80 §5：門檻未裁示時只顯示天數與此字樣。〔F〕note 自陳：tone＝灰是**推論**（無任何來源逐字寫它的顏色，「總管可推翻」） | 80 §5；44 之十九其四第 1 條；門檻 **尚待 Gate**（D3(b)） | **不能判定**：B8、N1 | 〔F〕唯一的灰色 tone 推論；本檔不處理；〔回修二〕改為不能判定：(5) 欄所列對向 B8 已改為不能判定；N1 配對本身成立 |
| A9 | `neutral`（無符號無字樣） | `rules.py::ENTRIES["neutral"]`；`CHIP_KIND_TO_KEY["neutral"]` | 〔F〕中性 chip（資料日、延遲天數之類 metadata）；字樣由 view model 的 `label_key` 給 | 80 §5 status chips 列 | **可**：→ B10（chip `neutral`，80 §5 明文一對一） | 列入只為完整對應 `CHIP_KIND_TO_KEY`；〔F〕它不是資料狀態（不影響此配對） |
| A10 | `not_configured` ⛔ `⛔ 尚未設定` | `rules.py::ENTRIES["not_configured"]`；`REASON_NOT_CONFIGURED`；`NOT_CONFIGURED_FORM`；`NOT_CONFIGURED_RATES_SOURCE_TEXT`（`⛔ 利率資料來源尚未設定`） | 〔F〕成因是某個設定沒設、**沒有執行取數**；永遠不寫成取數失敗；`entry_for_status("failed", "not_configured")` 才分流到此列 | DEC-2026-10-19-05（44 之十二其二第 1 條）；DEC-2026-11-03-09（利率來源句） | **不能判定**：F1（`KIND_UNCONFIGURED`）；B3 在 `reason_code=not_configured` 時指向它 | 〔F〕「尚未設定」另有**第三種用法**：掛在 `⬜ 不適用：` 底下的使用者參數缺值句——`ui_v2/alo/logic.py::TEXT_NA_NO_TARGET`＝`⬜ 不適用：尚未設定目標`（另有 `TEXT_NO_TARGET`、`TEXT_NO_TOLERANCE`）、44 `SET-1` 空狀態 `⬜ 不適用：尚未設定上限`、44 `MKT-4` `⬜ 不適用：尚未設定觀察窗`、`ui_v2/exp/logic.py::TEXT_NO_CONDITION`（`尚未設定條件`）、`ui_v2/hld/logic.py::TEXT_NO_RULES`（`尚未設定門檻`）；它們屬 ⬜ 族、不是 ⛔ 的 A10，但字面都含「尚未設定」；〔F〕ui_v3 `market_page::domain_state` 靠比對字串 `未設定 FRED_API_KEY` 才判為 not_configured（`MISSING_FRED_API_KEY_TEXT`，docstring 稱測試鎖）——分流依據是原文字串而非獨立代碼；〔回修二〕改為不能判定：(5) 欄所列對向 B3 為否（一對二分流），且本欄記載「尚未設定」另有第三種同字用法；另 `ui_v2/alo/logic.py::TEXT_NEVER_SET`＝`⬜ 資料未備：尚未設定過`（已驗證存在）是又一種含「尚未設定」的句型，掛在 ⬜ 資料未備底下 |
| A11 | `user_param_unset` ⬜ `⬜ 未設定` | `rules.py::ENTRIES["user_param_unset"]` | 〔F〕使用者自己的參數留空（G3†：系統不代填）；不是取數失敗、不是尚未設定的資料來源；**不計入資料狀態件數、不進 β 排序**（DEC-2026-10-20-01）。〔F〕note 自陳 tone＝灰是推論 | 44 SET-3；44 第四節第五小節 `user_setting`；DEC-2026-10-20-01 | **否**：與 A10／F1「尚未設定」字面相近但已核准文件明文分開，不可互映 | 〔F〕note 登記已知落差：ui_v2 資產配置／標的探索那幾格現行畫 ◇（BL-0382，未裁）；〔F〕同一件事（使用者參數沒填）在 ui_v2 另有 `⬜ 不適用：尚未設定…` 句型（見 A10 (6)），與 A11 的 `⬜ 未設定` 是兩套字面 |

### B 組｜New UI2 view model 的狀態鍵（`ui_v3/viewmodels/common.py`、`components.py`；對照表在 `rules.py`）

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| B1 | `status="ok"` | `ui_v3/viewmodels/common.py::STATUS_OK`；`STATUS_TO_KEY` | 〔F〕80 第 6 節共同欄位 `status` 五值之一 | 80 §6 | **否**：→ A1 | 〔回修三〕改為否：對向 A1 是「不加字」的規則鍵，不是一個詞（同 A1） |
| B2 | `status="missing"` | `common.py::STATUS_MISSING`；`ui_v3/adapters/market_page.py::domain_state`（`資料未備`→missing） | 〔F〕market_view 的「資料未備」在 adapter 轉成 missing，並帶 `reason_code`（無則用字串 `missing`） | 80 §6；`STATUS_TO_KEY` | **可**：→ A3 | 〔F〕adapter 的 reason fallback 是 `domain.get("reason_code") or STATUS_MISSING`，即「原因」欄可能就是 `missing` 本身 |
| B3 | `status="failed"` | `common.py::STATUS_FAILED`；`rules.py::entry_for_status` | 〔F〕`failed` 配 `reason_code=not_configured` → A10，其餘 → A6；`not_configured` 配在非 failed 的 status 上會 `ValueError` | 80 §6；44 之十二其二第 1 條 | **否**：一對二（依 `reason_code` 分流），是已核准設計，但不是一對一 | — |
| B4 | `status="stale"` | `common.py::STATUS_STALE`；`STATUS_TO_KEY["stale"]` | 〔F〕詞彙存在；〔F〕`market_page.py::_meta_status` 對 `ok／missing／failed` 以外的 meta 狀態一律降為 `undetermined` | 80 §6 | **不能判定**：詞對詞 → A7（`STATUS_TO_KEY`） | 〔I〕adapter 路徑上沒有查到產生 `stale` 的程式；〔I〕`_meta_status` 的降級會讓任何真的 stale 的 meta 變成 undetermined——是否合理屬 D3(b)，本檔不判；〔回修〕改為不能判定：對向 A7 本身不能判定，且 adapter 路徑沒有查到產生者 |
| B5 | `status="undetermined"` | `common.py::STATUS_UNDETERMINED`；`STATUS_TO_KEY` | 〔F〕五值之一 | 80 §6 | **不能判定**：→ A4 | 與 B8（freshness 欄的同名值）指向不同鍵，見 B8；〔回修二〕改為不能判定：依第 1 節 (i)，(6) 已記載同名不同目標；且對向 A4 為不能判定 |
| B6 | `freshness_state="fresh"` | `common.py::FRESH_FRESH`；`FRESHNESS_TO_KEY["fresh"]=None` | 〔F〕fresh 不加任何標記，也不寫「正常」 | 80 §5／§6 | **不能判定**：→ 「不加標記」（`entry_for_freshness` 回 None） | 對向不是詞；〔回修〕改為不能判定：`fresh` 屬 common.py 自陳「待客戶裁示覆核」的最小集合，核准依據只到 80 點名的 `undetermined` |
| B7 | `freshness_state="stale"` | `common.py::FRESH_STALE`；`FRESHNESS_TO_KEY["stale"]` | 〔F〕common.py 註解自陳：「規格缺口：80 只點名 `undetermined`，未列舉其他值；取最小集合（fresh／stale／undetermined），待客戶裁示覆核」 | 80 §6（只點名 `undetermined`） | **不能判定**：詞對詞 → A7；**但整組值域本身未經核准** | 〔F〕值域是執行組最小集合，不是核准字彙；〔回修〕改為不能判定：對向 A7 不能判定，且值域未經核准 |
| B8 | `freshness_state="undetermined"` | `common.py::FRESH_UNDETERMINED`；`FRESHNESS_TO_KEY["undetermined"]="threshold_pending"` | 〔F〕門檻未裁示＝undetermined | 80 §5／§6；門檻尚待 Gate | **不能判定**：→ A8（不是 A4） | ⚠️ 與 B5 同名、不同目標；呈現層必須依欄位而非依字面對照；〔回修二〕改為不能判定：依第 1 節 (i)，(6) 已記載同名不同目標（status 欄的 `undetermined`→A4，freshness 欄的→A8）；原版標可與規則不一致 |
| B9 | chip kind `attention` | `components.py::CHIP_KINDS`；`CHIP_KIND_TO_KEY` | 〔F〕六個 kind 之一 | 80 §5 | **可**：→ A2 | — |
| B10 | chip kind `neutral` | 同上 | 〔F〕六個 kind 之一 | 80 §5 | **可**：→ A9 | — |
| B11 | chip kinds `missing／undetermined／failed／stale` | 同上；`CHIP_KIND_TO_KEY` | 〔F〕`failed`→`fetch_failed`（chip 層沒有 not_configured 分岔） | 80 §5 | **不能判定**：分別 → A3／A4／A6／A7 | 〔F〕分岔只存在於 `status`（B3），chip 層沒有；兩層粒度不同；〔回修〕改為不能判定：四個 kind 中 `stale` 的對向 A7 不能判定；整列不得標可 |

### C 組｜44 §5.1 卡片四態（`ok／資料未備／業務例外／系統錯誤`）

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| C1 | `ok` | `services/v2_tables/market_view.py::STATE_OK`；`ui_v2/{mkt,exp,hld}/logic.py::STATE_OK`；`ui_v2/alo/logic.py::STATE_OK`；`ui_v2/sections.py::STATE_OK`；`ui_v3/adapters/market_page.py::_STATE_OK` | 〔F〕四態「掛在主值上，不掛在整張卡；一個主值同時只處於一個狀態」（44 §5.1 更正註） | 44 §5.1 | **否**：→ A1 |〔F〕`market_view.py` docstring：四態字面與 `ui_v2/mkt/logic.py::STATE_*` 逐字相同（測試比對，自述）；〔回修三〕改為否：同 B1 |
| C2 | `資料未備` | 同上 `STATE_MISSING`；`ui_v2/page_health.py::KIND_MISSING` | 〔F〕market_view：沒有正式來源的 domain 交回此狀態＋reason_code；〔F〕`ui_v2/hld/live.py` 註解：NAV 超過 10 日（嚴格 `>`）→ 「視為資料未備」（客戶 2026-10-13 裁示）；〔F〕`ui_v2/exp/live.py::profile_cell_note`：Cell `not_ready` 與 `inconsistent` 都走 `STATE_MISSING` | 44 §5.1；客戶 2026-10-13 裁示（NAV 過期併入）；DEC-2026-11-02-01 | **否**：詞對詞 → A3 | ⚠️ 成因比 A3 定義（來源缺或尚未備齊）寬：同一個詞裝了「沒取到」「NAV 太舊」「來源衝突」三種成因；是否要分開屬 D3(b)＋D7；〔回修〕改為否：成因比 A3 定義寬（多對一） |
| C3 | `業務例外` | 同上 `STATE_BIZ`（market_view、sections） | 〔F〕主值 `⬜ 不適用`＋一句原因，灰 | 44 §5.1；客戶 2026-10-16 裁示第 7 點 | **否**：→ A5 | 〔F〕ui_v3 `domain_state`：遇 `業務例外` 直接 `ValueError`（「not produced for these domains」）——此詞在 New UI2 市場頁沒有產生者；〔回修〕改為否：與 D3、E2 不同名稱併入 A5 同一字樣 |
| C4 | `系統錯誤` | 同上 `STATE_ERROR`；`ui_v2/health.py::_ERROR_STATE` | 〔F〕44 §5.5：「取數或計算本身失敗」；〔F〕market_view：缺 FRED 金鑰也給 `系統錯誤`＋`MISSING_FRED_API_KEY` 原文 | 44 §5.1／§5.5 | **否**：→ A6（取數失敗）或 A10（尚未設定）二擇一，且「計算失敗」不在 A6 定義內 | 〔F〕adapter 以原文字串分流（見 A10 (6)） |

### D 組｜44 §5.5 空狀態四種（`來源缺／部分缺／算不出來／系統錯誤`）

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| D1 | `來源缺` | `ui_v2/health.py::_MISSING_EMPTY_KINDS`；44 §5.5 | 〔F〕「這一塊依賴的來源一筆資料也沒有」；正式模式模板 `◇ 資料未備：<中文資料名> 尚無資料` | 44 §5.5；DEC-2026-10-17-03 | **否**：模板已落字 → A3 | —；〔回修二〕改為否：`來源缺` 與 `部分缺` 在 `ui_v2/health.py::_MISSING_EMPTY_KINDS` 併入同一個 ◇ 字樣（不同名稱併入同一字樣），標準同 A5／C3／D3／E2；同名詞對詞的 E1／F3／G4 保留可 |
| D2 | `部分缺` | `ui_v2/health.py::_MISSING_EMPTY_KINDS`；`ui_v2/set/logic.py::STATUS_BADGE_LITERALS` | 〔F〕「來源只涵蓋區間的一部分；本塊照畫、缺的期間留白、標題掛徽章」；徽章色為黃 | 44 §5.5 | **否**：規則表沒有對應鍵（不是別名缺口，是尚無詞） | 〔F〕`ui_v2/health.py` 把它與 `來源缺` 一起歸入 `◇`（`_MISSING_EMPTY_KINDS`）；44 §5.5 徽章色為黃，A3 為灰——同一歸類下顏色不同 |
| D3 | `算不出來` | 44 §5.5 | 〔F〕「來源齊，但規則的前提不成立」；模板 `⬜ 不適用：<一句話原因>`，灰 | 44 §5.5 | **否**：→ A5 | 與 C3 同指向 A5；〔回修〕改為否：同 C3 |
| D4 | `系統錯誤`（空狀態） | 44 §5.5 | 〔F〕「取數或計算本身失敗」；模板 `⛔ 取數失敗：<訊息原文>` | 44 §5.5 | **不能判定**：44 已落字為「取數失敗」，但定義含「計算本身失敗」，比 A6（上游取數失敗）寬；是否算語意衝突未見核准文件裁示 | 見 C4；本檔不判 |

### E 組｜44 §5.2 徽章「狀態」七字面（`ui_v2/set/logic.py::STATUS_BADGE_LITERALS`）

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| E1 | `資料未備`（灰） | `ui_v2/set/logic.py::STATUS_BADGE_LITERALS`、`_STATUS_BADGE_TONE` | 〔F〕七字面之一；〔F〕`ui_v2/symbols.py` 註解：徽章圖示換 ◇，文字不動 | 44 §5.2 | **可**：→ A3 | — |
| E2 | `不適用`（灰） | 同上 | 〔F〕客戶 2026-10-16 裁示第 7 點：黃→灰，glyph ⚠→⬜ | 44 §5.2 | **否**：→ A5 | —；〔回修〕改為否：同 C3；字面與 A5 相同，但來源端併入三個名稱 |
| E3 | `取數失敗`（紅） | 同上 | 〔F〕七字面之一 | 44 §5.2 | **可**：→ A6 | — |
| E4 | `推估`（黃） | 同上 | 〔I〕與 provenance 旗標 `is_estimated` 有關（67 §5.3 列出 `is_revised`、`is_estimated`）；本組未讀其產生處 | 44 §5.2 | **否**：規則表沒有對應鍵 | 不在 D3 的缺值／新鮮度／一致性範圍，列入只為完整 |
| E5 | `修正過`（黃） | 同上 | 〔I〕同 E4（`is_revised`） | 44 §5.2 | **否**：同上 | 同上 |
| E6 | `部分缺`（黃） | 同上 | 〔F〕與 D2 同詞 | 44 §5.2 | **否**：同 D2 | 同 D2 |
| E7 | `未定義`（黃） | 同上 | 〔F〕七字面之一；〔F〕**現存產生處**：`ui_v2/mkt/logic.py::_freshness_badge` 在 `rows` 為空、或 `freshness_badge_text(delay)` 回 None（即 delay ≤ 0）時回傳 `_status_badge("未定義")`；〔F〕`freshness_badge_text` docstring 自陳：「`即時`／`當日` 兩級的判定門檻 `44` 沒有定（`47` Q-05）。本檔不自行發明門檻——delay <= 0 時回 None，由呼叫端掛一枚 `未定義` 狀態徽章」 | 44 §5.2 | **不能判定**：詞面與 `allocation_evidence.NOT_DEFINED`（`not_defined`）相似，但未見任何文件明文對照，不推斷 | 同 K、P 組的內部代碼，不得因字面相似視為同義；與 A3「資料未備」亦有「未備／未定義」同義風險，未見文件對照，不推斷（交叉引用：A11、P12 的 `unset`）；〔F〕同為「新鮮度不判」的情形，`ui_v2/hld/live.py` 對 N＝0 輸出 `當日`（`FRESHNESS_TODAY_TEXT if days == 0`），而 mkt 頁對 delay ≤ 0 輸出 `未定義` 徽章——**兩頁行為不同**（見 N2、N2b）；〔F〕`未定義` 在此承擔「新鮮度門檻未定」，與 New UI2 的 `⬜ 門檻待裁示`（A8）情境相近，但未見文件對照，不推斷 |

### F 組｜設定與診斷頁「各頁資料狀態總表」四類（`ui_v2/page_health.py::KINDS`）

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| F1 | `尚未設定`（`KIND_UNCONFIGURED`，不加符號） | `ui_v2/page_health.py`；`ui_v2/health.py::LINE_NOT_CONFIGURED` | 〔F〕「鍵＝哪一個設定」；與取數失敗永遠分開數 | 44 之十三其七 | **不能判定**：→ A10 | 見 A11；〔回修二〕改為不能判定：`尚未設定` 一詞另有第三種用法（`⬜ 不適用：尚未設定…`、`⬜ 資料未備：尚未設定過`，見 A10 (6)）；F1 指向的 A10 本身為不能判定；並見 A11 |
| F2 | `取數失敗`（⛔） | 同上 `KIND_FETCH` | 〔F〕鍵＝哪一類資料；含「改用預存淨值」句型（`TEXT_MAIN_RETREAT`） | 44 之十三其七；DEC-2026-10-18-02（BL-0375） | **不能判定**：→ A6 | 〔F〕「取數失敗，改用 <日期> 的預存淨值」是**已取得替代值**的失敗，與 A6「上游取數失敗」並置；〔回修〕改為不能判定：「取數失敗，改用預存淨值」是否仍屬 A6，文件未裁示 |
| F3 | `資料未備`（◇） | 同上 `KIND_MISSING` | 〔F〕鍵＝哪一類資料 | 同上 | **可**：→ A3 | — |
| F4 | `不是最新`（◷） | 同上 `KIND_STALE`；`TEXT_MAIN_STALE`＝`◷ 主要原因：部分只顯示最後有效資料` | 〔F〕「整頁只算一項」（`STALE_KEY="整頁"`）；〔F〕`health.py` docstring：`◷` 由呼叫端依該頁既有標示交進來，「目前只有持倉體檢有『淨值取自預存序列』這一種」（該段寫於 3-C 之前，狀態行已退場）；〔F〕**44 第七節第三小節之七其四明列 ◷ 的三個觸發**：(1) 新鮮度徽章畫成黃的那一段、(2) `SET-1` 超過新鮮度上限的筆、(3) 顯示最後一筆有效值時（見 Q 組）；〔F〕總表 `KIND_STALE` 實際由哪一個觸發填入，本組未逐處追 | 44 之七其四；44 之十三其七 | **不能判定**：與 A7 同符號同字樣，但 44 之七其四有三種觸發，其中 (2) 的上限是**使用者自設參數**、(3) 是**預存序列**，都不是規則表 A7 所稱的「正式門檻」；它們與 A7 是否為同一件事，文件未裁示 | 〔F〕A7 的定義（正式門檻）與已查到的三種觸發（徽章日數黃段、使用者自設上限、顯示最後有效值）不同；〔I〕要把它們視為同一詞是語意決定，屬 D3(b)，本檔不替客戶選 |

### G 組｜β 階梯七類（`ui_v2/status_class.py`；對照 `rules.py::BETA_LEVELS`）

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| G1 | `取數失敗`（E） | `status_class.py::ERROR`；`BETA_LEVELS` | 〔F〕頁級 presentation 分類，不改 domain block 原判定 | DEC-2026-10-30-04 | **可**：→ A6 | 頁級燈 production 上線以 BL-0411 修好為前提（`resolve_precedence` docstring） |
| G2 | `無持倉`（Z） | `status_class.py::NO_HOLDING` | 〔F〕尚未建立任何持倉 | DEC-2026-10-30-04 | **否**：規則表無字樣（`entry_key=None`，`PENDING_WORDING` 缺口） | 字樣隨 💼 wireframe Gate |
| G3 | `需要注意`（D，◆） | `status_class.py::ATTENTION` | 〔F〕同 A2 | 同上 | **可**：→ A2 | — |
| G4 | `資料未備`（M，◇） | `status_class.py::MISSING` | 〔F〕註「含 A6m／A5c／F-18／F-19」 | 同上 | **否**：→ A3 | 〔回修三〕改為否：doc 74 第一節落地方式寫「A6m、A5c、F-18、F-19 在 logic 內歸資料未備」——四個不同名稱併入同一 β 類，依第 1 節 (ii) 標否；這四碼的個別語意本組未讀（F-18／F-19 為 74 的阻擋項編號、A6m／A5c 為 logic 分支編號，〔I〕尚未逐一對照）。理由不依賴對它們性質的判斷：是否算「來源概念」本組不裁 |
| G5 | `未設定或不適用`（U／X，⬜） | `status_class.py::UNSET` | 〔F〕β 把「未設定」與「不適用」併成一級 | 同上 | **不能判定**：→ A4（`BETA_LEVELS` 的 `undetermined`） | 〔F〕但 A11（使用者參數留空）依 DEC-2026-10-20-01 **不進 β**；β 這一級裡的「未設定」與 A11 是否同一件事，本檔未查到文件明文，不推斷；〔回修〕改為不能判定：β 的「未設定或不適用」與 A11 的關係未見文件明文，且 A4 本身不能判定 |
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
| I2 | `WITHHELD_*`：`ccy_missing`／`ccy_conflict`／`ccy_not_source_reported`／`fetched_at_missing`／`fetched_at_in_future`／`input_conflict`；`div_outcome_undetermined`／`div_items_rejected`／`div_ccy_differs`；`PENDING_DIV_*` | `services/v2_tables/nav_dividend.py` | 〔F〕行尾註解逐碼說明（例：`ccy_conflict`＝來源自報與持倉手填或手填之間意思不同；`input_conflict`＝同一檔給了互相矛盾的輸入）。〔I〕本組只讀常數定義處註解，**未讀各碼的完整使用路徑** | 無（內部碼） | **不能判定**：沒有核准對照 | 〔F〕含 `*_conflict` 兩碼與 `div_ccy_differs`（幣別相異），屬「一致性」字彙，**D3(b) 的 conflict 判定會碰到** |

### J 組｜Cell 狀態（`services/v2_tables/exp_profile.py`）

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| J1 | `ok` | `exp_profile.py::STATUS_OK`；`ui_v2/exp/live.py::profile_cell_note` | 〔F〕值照畫、掛來源標示；有失敗來源時標示寫出失敗來源 | `PARTIAL_FAILURE_POLICY="accept"`（規則 12，docstring） | **不能判定**：→ A1 | 〔回修三〕改為不能判定：J1 的 `ok` 同時涵蓋完全成功與「部分來源失敗但接受」（`PARTIAL_FAILURE_POLICY="accept"`，標示寫出失敗來源），成因寬度與 A1「沒有異常」不同，且 A1 已為否；本組未判定兩者是否同義 |
| J2 | `not_ready` → 畫面 `⬜ 資料未備：<原因>` | `exp_profile.py::STATUS_NOT_READY`；`ui_v2/exp/live.py::profile_cell_note` | 〔F〕docstring：「基本資料缺值保留並 ⬜資料未備」；〔F〕`profile_cell_note`：與 `inconsistent` 同走 `STATE_MISSING` | 客戶裁示（`exp_profile.py` 檔頭） | **不能判定**：→ A3 | 〔F〕字面是 `⬜ 資料未備`（`logic.ND_TEXT`），正式字樣為 `◇ 資料未備`；本檔未查到此畫面是否經 `ui_v2/symbols.py` 換字，不推斷；〔回修〕改為否：與 J4 併入同一畫面字樣，且 ⬜／◇ 字面未實跑確認；〔回修二〕改為不能判定：理由為 ⬜／◇ 字面未實跑確認（屬未驗，不得標否）；另與 J4 併入同一畫面字樣，見 J4 |
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
| N2 | 新鮮度徽章 `當日`／`延遲 {n} 日` | `ui_v2/hld/live.py::FRESHNESS_TODAY_TEXT`、`FRESHNESS_DELAY_TEXT` | 〔F〕N＝0 與 N≥1 的字面（44 §5.2 新鮮度字面）；〔F〕`hld/live.py` 對 N＝0 輸出 `當日`（`days == 0`）；〔F〕mkt 頁 `freshness_badge_text` 對 delay ≥ 1 回 `延遲 N 日`、delay ≤ 0 回 None 並改掛 `未定義` 徽章（E7） | 44 §5.2 | **否**：是新鮮度事實的顯示，不是狀態詞；規則表無對應鍵 | 與 A8（只顯示天數與 `⬜ 門檻待裁示`）並存於兩代 UI；〔F〕兩頁對 N＝0 的處理不同（hld：`當日`；mkt：`未定義` 徽章） |
| N2b | 新鮮度徽章 `即時`（44 §5.2 `新鮮度` 列 `即時`／`當日`／`延遲 N 日` 的第一個值） | 44 §5.2 | 〔F〕44 列出；〔F〕`ui_v2/mkt/logic.py::freshness_badge_text` docstring：`即時`／`當日` 兩級的判定門檻 44 沒有定（47 Q-05），程式不自行發明門檻；〔F〕本組以 `git grep -n -E "\"即時\"" origin/main -- 'ui_v2/*.py' 'ui_v2/**/*.py'` 查字串字面，無命中（只代表字面未出現，不代表邏輯不存在） | 44 §5.2 | **不能判定** | `即時` 與 `當日` 的邊界門檻 44 未定；hld 頁輸出 `當日`、mkt 頁輸出 `未定義` 徽章，兩頁行為不同（見 N2、E7） |
| N3 | `NAV_NOT_READY_DAYS = 10`；超過 → `⬜ 資料未備` | `ui_v2/thresholds.py`；`ui_v2/hld/live.py::NAV_FRESH_DAYS_YELLOW`（別名）；`ui_v2/alo/live.py::assemble_nav` | 〔F〕唯一字面值在 `ui_v2/thresholds.py`；〔F〕持股頁嚴格 `>`；〔F〕與舊介面 `MJ_FRESH_DAYS_*`（2／7）是不同兩套（`thresholds.py` 註解） | 客戶 2026-10-13 裁示（持股）；**跨頁語意尚待 D7**（evidence 文件 D7 (a)～(e)） | **否**：這是一個「數值門檻」，不是詞；其結果被併入 A3 | 本檔不處理數值 |

### O 組｜New UI2 畫面實際使用的狀態相關字樣（`rules.py::APPROVED_WORDING` 與 `ui_v3/viewmodels/preview_wording.py`）

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| O1 | `資料不足`（`insufficient`） | `rules.py::APPROVED_WORDING["insufficient"]` | 〔F〕純文字正式字樣（沒有符號）；〔F〕market 圖表 period／normalization 狀態 `insufficient` 的字樣出處未逐一追（本組未查） | DEC-2026-11-03-07 | **不能判定**：與 A3 `◇ 資料未備`、A4 `⬜ 無法判定` 的邊界未見文件對照 | 三個詞（資料不足／資料未備／無法判定）並存 |
| O2 | `原因未明`／`來源資料無法使用`／`沒有觀測值` | `APPROVED_WORDING["reason_unknown／reason_no_source／reason_no_observation"]` | 〔F〕單序列退回句 `目前僅顯示可用序列；另一序列{原因}，暫不進行比較。` 的原因片段 | DEC-2026-11-03-07 | **否**：是原因片語，不是狀態 | — |
| O3 | `此圖目前沒有可畫的資料` | `APPROVED_WORDING["chart_empty"]` | 〔F〕整張圖無資料的正式字樣 | DEC-2026-11-03-07（客戶 2026-11-03 裁示） | **不能判定**：與 A3 的關係未見文件對照；79 §11 登記 `TEXT_EMPTY`＝「⬜ 資料未取得，無法繪圖」是另一個舊字樣 | 舊字樣 `⬜ 資料未取得` 為 79 §11 登記的版面示意字樣 |
| O4 | Shell 資料狀態：`部分資料未取得（{ok}／{total} 項已取得）`、`其中 {n} 項取數失敗`、`{ok}／{total} 項已取得` | `APPROVED_WORDING["shell_status_*"]`；`ui_v3/viewmodels/shell.py::LEVELS`（`ok／partial／none`） | 〔F〕三個層級加計數，不推估；〔F〕分母＝本次檢查涵蓋的已登錄項目（五條主要序列） | DEC-2026-11-03-11 | **否**：層級（齊全／部分／全缺）是聚合摘要，不是逐項狀態詞 | 其中「取數失敗」與 A6 同詞但在計數句裡；`partial` 與 D2／E6／G6 的「部分」是不同層級 |
| O5 | 暫擬字樣：`缺資料`、`取數失敗`、`尚未設定`、`共同有效觀測日不足`、`有效點數不足`、`沒有共同有效觀測日` | `ui_v3/viewmodels/preview_wording.py`（`reason_missing／reason_fetch_failed／reason_not_configured／reason_few_common／reason_few_points`；另有 `reason_no_common`＝`沒有共同有效觀測日`，對應 `no_common_base`） | 〔F〕該檔自陳：「執行組暫擬／沿用」，status 恆為 `pending`；其中 `reason_missing` 自陳註明「取數失敗≠缺資料」 | **尚待 Gate**（`APPROVED_WORDING` Gate） | **否**：暫擬字樣不是核准詞；`缺資料` 與正式的 `資料未備` 並存 | 暫擬字樣非核准，不得當正式字彙 |

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
| P8 | `COMPARISON_*`／ui_v2 市場比較條件狀態：`complete／unset／incomplete_setting／read_failed`（`unset`、`read_failed` 與 allocation_evidence 的設定狀態同字，見 P12） | `ui_v2/mkt/logic.py::comparison_reason`（docstring） | 〔F〕使用者「比較設定」兩鍵的狀態 | 客戶 2026-10-13 裁示 Q-07 | **否**：使用者設定狀態，不是資料狀態（同 A11 的性質） | 與 H7 同一個機制 |
| P9 | 資產配置頁無持倉句 `尚未建立任何持倉` | `ui_v2/sections.py::HLD_TEXT_NO_HOLDING` | 〔F〕字面常數；β 的 `無持倉`（G2）是否即此句，本組未追 | DEC-2026-10-30-04（β 一級） | **不能判定** | 與 G2、規則表 `PENDING_WORDING` 缺口的關係未見文件對照 |
| P10 | `dividend_calendar` 的 `REASON_STALE`＝`stale`（同組另有 `anchor_weak`／`too_few`／`no_anchor_day`） | `services/dividend_calendar.py`（註解：§14.2 unpredictable 四類成因；`stale`＝疑停配／資料過舊） | 〔F〕這是配息行事曆「不可預測」的成因碼，不是資料新鮮度狀態；屬 services 舊路徑 | 無 | **否**：同字（stale）不同義，不得與 A7／B4／B7 對照 | 第二個 `stale` 字面 |
| P11 | `exp_universe` 狀態 `ok`／`pool_not_cloud`／`failed`；`exp_nav` 的 `KIND_SUCCESS＝success`／`KIND_FAILURE＝failure`；`personal_session` 原因 `no_active`／`deploy_config` | `services/v2_tables/exp_universe.py::STATUS_*`；`services/v2_tables/exp_nav.py::KIND_*`；`services/v2_tables/personal_session.py::REASON_*` | 〔F〕`pool_not_cloud`＝選股池未設定雲端來源（`TEXT_NOT_CLOUD`、`TEXT_NO_SHEET_ID`）；〔F〕`exp_nav` KIND 是記憶體的成功／失敗，決定 TTL；〔F〕`no_active`＝已登入但沒有 Active（或屬別的帳號），`deploy_config`＝讀不到部署端登入設定 | 無（內部碼） | **不能判定** | `pool_not_cloud` 成因是設定沒設，概念上近 A10，但未見文件對照；`failed` 與 A6、L4、P3 同字 |
| P12 | allocation_evidence 的設定／facet 狀態 `set`／`unset`／`empty`／`read_failed`／`invalid`、`provided`；分母判定 `DEN_COMPLETE／DEN_INCOMPLETE／DEN_NONE／DEN_NON_POSITIVE／DEN_NON_FINITE`；類別來源 `unproven_zero` 等 | `services/v2_domain/allocation_evidence.py` | 〔F〕整模組為 INTERNAL CANDIDATE；〔F〕`unproven_zero` 行註解：目標類別無持倉的 0.0，而來源涵蓋度不完整 | 無（候選） | **否**：`unset`、`read_failed` 與 P8（ui_v2 `COMPARISON_UNSET`／`COMPARISON_READ_FAILED`）同字不同層（L2 設定值狀態 vs L3 市場比較設定狀態），不得互映 | `read_failed` 與 L4 `failed` 相近，未見對照 |
| P13 | 取數冷卻字彙：冷卻句 `來源冷卻中：<來源>，約剩 N 秒`；冷卻 kind `unreachable`／`server_error`／`blocked`／`rate_limited`／`not_found`／`proxy_auth` | `ui_v2/mkt/live.py::cooldown_reason`；`infra/source_backoff.py`（`record_failure(key, kind)`）；`shared/backoff_policy.py`（`BACKOFF_COOLDOWN_SEC` 的鍵、`NO_COOLDOWN_KINDS`） | 〔F〕kind 是失敗分類，決定是否退避；`not_found`、`proxy_auth` 屬不退避類；本檔不記秒數 | 無 | **不能判定** | 冷卻是取數層機制，其與 A6 的對應（冷卻中算不算取數失敗）未見文件對照；`not_found` 與 P3 同字不同層 |

---

### Q 組｜既有新鮮度字彙（回修新增；原版漏盤：SET-1 比較欄與 ◷ 的使用者自設上限路徑）

> 〔F〕這一組顯示：本 repo 已有一條以「使用者自設上限」判斷「外／◷」的新鮮度路徑，與規則表 A7（正式門檻）、N3（NAV 10 日常數）是三個不同來源的判斷。本檔只記事實，不比較孰是孰非，也不記任何數值。

| ID | (1) | (2) | (3) | (4) | (5) | (6) |
|---|---|---|---|---|---|---|
| Q1 | `SET-1` 比較欄 `內` | `ui_v2/set/logic.py::TEXT_IN`；44 `SET-1` | 〔F〕一列一類資料（淨值、配息、市場指標），比較「距今日數」與使用者上限，結果為「內」或「外」；「內」不加 `✓`、不寫「資料齊」「正常」（之八其二 (b-2)） | 44 `SET-1`；`DEC-2026-10-17-07` | **否**：沒有對向詞（A1 刻意不寫字） | 與 Q7 的資產配置 `內` 同字不同義 |
| Q2 | `SET-1` 比較欄 `外` → 畫面 `◷ 外` | `ui_v2/set/logic.py::TEXT_OUT`；`ui_v2/sections.py::SET_TEXT_OUT`、`mark_set1_rows`、`_set_is_out` | 〔F〕`mark_set1_rows` docstring：「超過新鮮度上限的筆，文字前加 ◷；顏色照舊」（44 之七其四）；〔F〕上限由使用者輸入（G3†，鍵 `set_max_age_days`） | 44 之七其四；`DEC-2026-10-17-07` (b-2) | **不能判定**：符號與 A7 相同，但判斷依據是使用者自設參數，不是規則表要求的「正式門檻」；兩者是否同一件事文件未裁示 | 屬 D3(b) 的門檻語意；本檔不提案 |
| Q3 | `SET-0` 黃燈 `◷ N 類資料超過你設的上限`；`③` 注意行 `{kind}：距今 {days} 日，超過你設的上限` | `ui_v2/sections.py::SET_OVERDUE_TEXT`、`SET_ATTENTION_TEXT`、`set_attention`、`set_conclusion` | 〔F〕N＝`SET-1` 逾期類數（一列一類）；〔F〕`set_attention` 只讀 `SET-1` 已算出的結果，不另判；〔F〕注意行前綴 ◷、tone 黃 | 44 之八其二 (b-2) 第 3 條 | **不能判定**：同 Q2 | 字面用「超過你設的上限」，與 A7「不是最新」字樣不同 |
| Q4 | 使用者參數 `set_max_age_days`（一般畫面換字為「新鮮度上限日數」） | `ui_v2/plain.py`（鍵名對照）；`ui_v2/set/logic.py::MAX_AGE_KEY`；`ui_v2/set/spec.py`（歸屬 `SET-1`） | 〔F〕使用者參數，整數；留空時 `SET-1` 比較欄為 `⬜ 不適用：尚未設定上限` | 44 `SET-1`、`SET-3` | **否**：是參數不是狀態；本檔不記其值或預設 | 留空屬「使用者參數沒填」，卻用 `⬜ 不適用：尚未設定上限` 句型，見 A10 (6) |
| Q5 | 44 之七其四明列的 ◷ 三個觸發：(1) 新鮮度徽章畫成黃的那一段、(2) `SET-1` 超過新鮮度上限的筆、(3) 顯示最後一筆有效值時 | `docs/v2/44_fund_ui_ssot.md` 第七節第三小節之七其四（「不是最新」列） | 〔F〕三者並列，文字前加 `◷`、顏色照舊 | 44 之七其四；`DEC-2026-10-17-03` | **不能判定**：三個觸發的判斷依據不同（徽章日數、使用者上限、預存序列），與 A7 的關係未見文件對照 | F4、Q2、Q3 各對應其中之一；〔F〕(1)：44 §5.2 `新鮮度` 列只寫「中性至黃，只映射日數」，**未給黃色日數門檻**；〔F〕現行 ui_v2 **未找到**產生黃色新鮮度徽章的程式：`mkt/logic.py::_freshness_badge` 恆回「中性」tone、`hld/live.py` 的過期徽章用灰 `NOT_READY_TONE`；`ui_v2/health.py::_STALE_TONE`（`黃`）只是讀取端的判讀（`_is_stale_badge`），不是產生處；**(1) 的產生處標「未驗」（此為 grep 與讀檔結果，非窮舉；`alo`／`exp` 頁未逐檔確認）** |
| Q6 | 新鮮度徽章 `當日`／`延遲 {n} 日`（及 44 §5.2 的 `即時`） | `ui_v2/hld/live.py::FRESHNESS_TODAY_TEXT`、`FRESHNESS_DELAY_TEXT`；44 §5.2 | 〔F〕N＝0 與 N≥1 的字面；`即時` 見 N2b | 44 §5.2 | **否**：新鮮度事實的顯示，不是狀態詞 | 與 N2 同一組詞，為完整另列 |
| Q7 | 資產配置 `內`／`外`（容許帶） | `ui_v2/alo/logic.py::TEXT_IN`、`TEXT_OUT`；`ui_v2/sections.py::ALO_TEXT_OUT` | 〔F〕配置占比相對目標的容許帶內／帶外（ALO-0），與資料新鮮度無關 | 44 `ALO-0` | **否**：同字（內／外）不同義，不得與 Q1／Q2 對照 | 同字不同義 |

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
7. **A10／A11／F1／G5／Q4**（另含 `alo/logic.py::TEXT_NEVER_SET`＝`⬜ 資料未備：尚未設定過`）：「尚未設定」有三種用法——⛔ 尚未設定（A10，來源或設定沒設、沒執行取數）、⬜ 未設定（A11，使用者參數留空）、掛在 `⬜ 不適用：` 底下的 `尚未設定目標／上限／觀察窗／條件／門檻`（`alo/logic.py::TEXT_NA_NO_TARGET`、`TEXT_NO_TARGET`、`TEXT_NO_TOLERANCE`、44 `SET-1`／`MKT-4` 空狀態、`exp/logic.py::TEXT_NO_CONDITION`、`hld/logic.py::TEXT_NO_RULES`）；A11 不進 β，但 G5 的「未設定或不適用」一級與 A11 的關係未見文件明文。
8. **C4／D4**：系統錯誤的定義含「計算失敗」，與 A6「上游取數失敗」不同寬。
9. **A3 vs `ND_TEXT`**：正式 `◇ 資料未備` 與程式常數 `⬜ 資料未備` 並存；經 `ui_v2/symbols.py` 在渲染時換字（docstring 自述，本組未實跑畫面）。
10. **O1／O3／O5**：`資料不足`、`此圖目前沒有可畫的資料`、`缺資料`（暫擬）與 `資料未備`、`無法判定` 之間的邊界未見文件對照。
11. **D2／E6／G6／O4**：「部分」一詞出現在四個不同層級（空狀態、徽章、β、Shell 聚合）。
12. **A8／A11 的 tone＝灰**：`rules.py` note 自陳為推論。
13. **K、L、P12 三組**：整組為 INTERNAL CANDIDATE，沒有任何核准對照。
14. **Q2／Q3／Q5／F4／A7**：同一個 ◷ 已查到三種觸發（使用者自設上限、徽章日數黃段、顯示最後有效值），與規則表「正式門檻」不同源。
15. **同字不同義（回修新增）**：`內／外`（Q1／Q2 vs Q7）、`stale`（A7／B4／B7 vs P10）、`unset／read_failed`（P8 vs P12）、`not_found`（P3 vs P13）、`failed`（A6／L4／P3／P11）。

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

13. 使用者自設上限（`set_max_age_days`）驅動的「外／◷」與「正式門檻」驅動的「不是最新」，是否為同一個詞、同一條規則，或並存。
14. ◷ 三種觸發（徽章日數黃段、使用者上限、顯示最後有效值）是否都保留 ◷。
15. `⬜ 不適用：尚未設定…` 句型與 `⬜ 未設定`、`⛔ 尚未設定` 三者是否維持分開。

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
- **回修輪補查（2026-11-08，origin/main 同為 aabd5eb8）**：以 `git grep` 核對 `SET_TEXT_OUT`／`ALO_TEXT_OUT`／`mark_set1_rows`／`set_attention`／`TEXT_IN`／`TEXT_OUT`／`set_max_age_days`／`HLD_TEXT_NO_HOLDING`／`REASON_STALE`／`STATUS_NOT_CLOUD`／`KIND_SUCCESS`／`COMPARISON_*`／`DEN_*`／`UNPROVEN_ZERO`／`WITHHELD_DIV_CCY_DIFFERS`／`reason_no_common` 等符號都存在，並讀 `ui_v2/sections.py` 的 SET-1 段、44 `SET-1` 塊與之七其四表列；`即時` 字面在 ui_v2 程式碼中無命中。
- **回修後仍未涵蓋**：`ui_v2/set/` 的 `SET-1` 計算本體（距今日數怎麼算）、`infra/source_backoff` 與 `shared/backoff_policy` 的完整行為（只讀 kind 名稱）、`allocation_evidence` 各 facet 狀態的完整判定、`exp_universe`／`exp_nav` 的畫面對照、`dividend_calendar` 其餘字彙。
- **未讀**：各 `WITHHELD_*`／`PENDING_*` 的完整使用路徑（只讀常數處註解）；`ui_v2/symbols.py` 的完整渲染邏輯與畫面實跑；`ui_v3/pages/*` 的畫面組裝；`ui_v2/set/` 各徽章的產生處；`repositories/v2_source_status`（冷卻）的狀態用詞。
- **未執行任何測試或畫面**；所有「測試鎖」皆為 docstring 自述。
- **未查證**：67 §5.3「至少三套」與 AUD R6「至少 5 套」中「套」的點算方式（兩者原文即未逐一點算）。本檔分了 17 組，**這是本組為閱讀所分，不等於官方「套數」**，不得引用為任何一方的點算結果。

**計數方法（第 0 節數字）**：在第 2 節各表中，以第 (5) 欄開頭粗體詞統計（**須在 `docs/evidence/` 目錄下執行**，檔名為相對路徑）：

```
awk -F'|' '/^\| [A-Q][0-9]+b? \|/{ if ($7 ~ /^ *\*\*可/) k++; else if ($7 ~ /^ *\*\*否/) n++; else if ($7 ~ /^ *\*\*不能判定/) u++; t++ } END{print "rows="t" 可="k" 否="n" 不能判定="u}' data_state_vocabulary_crosswalk_d3a_2026_11_08.md
```

### (e) 單組揭露（§-2 規則 6）

- 本版為**回修第二輪版**：獨立 QA 已完成兩輪，本組逐項以 `git grep origin/main` 重驗後修訂（第二輪新增驗證：`TEXT_NEVER_SET`、`freshness_badge_text`、`_freshness_badge`、`hld/live.py` 對 N＝0 的處理、`health.py::_STALE_TONE` 均已讀原始碼）；第二輪修訂**尚未經第三輪 QA**。本檔由**單一作者組**產出；所有〔I〕推論只是待驗事項，不得作為後續動作的前提。
- 第 (5) 欄的「可／否／不能判定」是本組依第 1 節自訂定義作的判斷；**「可」僅在查到明文出處且兩邊定義一致時才標**，「否」「不能判定」是保守判斷，非客戶裁示。
- 第 0 節「110 列、可 12／否 44／不能判定 54」為本組以上列 awk 指令計得；獨立 QA 請重跑並核對，數字若有出入以重跑結果為準。
- 本檔沒有新增任何狀態、字樣、數值或門檻；凡本檔出現的字樣皆為既有代碼或文件的轉錄，並已標明其核准狀態（核准／暫擬／內部候選／已停用）。
