# 🔍 找一檔基金／依條件篩選｜離線 FAKE 隔離 Preview（非正式頁面、非正式資料）

- 授權依據：`DEC-2026-11-17-02`（要點轉述；客戶選定 `BL-0553` 方案 A 並以五點答覆；來源為對話提示語，repo 無逐字存檔，QA 無法核對，NOT VERIFIED）。
  只授權**本目錄與 `tests/poc_fund_search_preview/`** 的完全離線 FAKE Preview。UI 設計規格由 ChatGPT 規劃（「ChatGPT UI 設計方向 2026-11-17」），**不是客戶逐字裁示**。
- 這**不是** 🔍 頁面上線：`ui_v3/shell/registry.py`、`ui_v3/app_preview.py`、`ui_v3/pages/*`、導覽、frozen 44、正式公式／Schema／FX、Old UI、`ui_v2` 一律沒動；
  不接 Google Sheet／選股池、不讀 `user_setting`、不做 ISIN 解析、不發任何請求、不讀 secrets／環境變數、不寫檔或設定。**不得宣稱 🔍 頁面功能已完成。**
- 啟動：`streamlit run poc/fund_search_fixture_preview/app_fund_search_preview.py`（在 repo 根目錄執行）。

## 畫面（單欄、手機優先；一個入口上下排列）

頁頂固定一列「FAKE／測試資料（離線注入，未執行任何真實請求）」與 FAKE 代碼提示（屬 harness，不屬 renderer）。

**上區「找一檔基金」**：標題 → 單一輸入框「MoneyDJ 基金代碼或 ISIN」（不放範例碼）→ 常駐 ISIN 未啟用說明（無狀態符號，緊鄰輸入框）→「查詢」鈕
（`st.form`＋`form_submit_button`，Enter 與點擊等效）→ 結果卡 → 預設收合、不巢狀的單一 `<details>`「基本資料｜尚未取得｜來源與限制」。

| 輸入（去頭尾空白、轉大寫後比對） | 結果 |
|---|---|
| `FAKE-OK01` | 找到模擬項目：結果卡標「FAKE 模擬」，基金名稱為 FAKE 名稱，成立日／配息方式／經理費率一律 `◇ 資料未備`（不補假金融數據） |
| `FAKE-LOW1` | 資料不足（規則表既有「資料不足」）：名稱等欄位全為 `◇ 資料未備` |
| `FAKE-ERR1` | 查詢失敗：規則表既有 `⛔ 取數失敗`＋「無法顯示這檔基金」＋「這次取數失敗，不是對基金身份的判斷」；不畫任何資料列 |
| 空白、或不像代碼的字串 | `⬜ 無法判定（無法辨識格式）`——無法判定，**不是**「不存在」 |
| 像代碼但 fixture 沒有（例 `ABC123`） | `⬜ 無法判定（離線預覽沒有這個代碼的模擬資料）` |
| ISIN 形（2 字母＋9 英數＋1 數字） | **只**顯示「ISIN 目前未啟用」：不解析、不取數、不出結果卡、不回顯輸入 |

結果卡：「輸入代碼」顯示輸入**原值**（一律 HTML escape；輸入 `<script>` 不會執行也不會被當標籤）；「基金身份」固定 `◇ 尚未確認`（不因查詢成功改成已確認）；
「單檔查詢結果（唯讀；不會加入選股池或任何清單）」。畫面任何情境都不出現 NAV／報酬／績效／推薦／最佳／排名／「基金不存在」「查無基金」。

**下區「依條件篩選」**（以分隔線與上區區隔，不增加頁內分頁；harness 的 selectbox 切換選股池情境）：

- **EXP-0**：結論文案**一律取** `ui_v3.viewmodels.exp_counts.exp0_conclusion`（不重造）。零生效條件 → 「尚未設定條件」，不展示 N／M。
- **EXP-1「本次瀏覽暫時條件」**：三個 FAKE 條件勾選框（`FAKE 條件 1／2／3`），只在本次 `session_state` 生效，**不寫任何持久層**、不畫存檔鈕；重新載入或新瀏覽階段回到初始（零條件）。
- **EXP-2 結果清單**：一列一檔（卡片，不橫向捲動），固定順序＝`fund_code` 字面值升冪（不是名次）；欄位只用 44 `EXP-2` 規則欄既有欄名（基金代碼、基金名稱、幣別、最近淨值日、最近淨值、近 12 個月配息佔淨值比）；
  值皆 `FAKE 值` 或 `◇ 資料未備`；無法判定的列標規則表「⬜ 無法判定」。列數＝N＋M（`verify_exp2_row_count`）。**不做 EXP-4 排序**。
- **EXP-7 篩選軌跡**：逐條件（依畫面順序累計套用）顯示套用前檔數、符合、無法判定；末列＝EXP-0 的 N／M（`verify_exp7_last_row`）。
- 不實作 EXP-3／4／5／6、存檔、歸一化圖。

選股池情境（harness selectbox）：①有符合 ②無符合 ③只有無法判定 ④有符合也有無法判定 ⑤選股池來源失敗（EXP 區顯示 `⛔ 取數失敗`，不展示 N／M，不偽稱 0）。
「條件未設定」是 widget 的**初始狀態**，五個情境都適用（不另設情境）。各情境全勾條件的 (N, M)：(2,0)、(0,0)、(0,3)、(2,2)；子集合另有不同結果（例：情境④只勾條件 1 是 (4,1)）。

## 三態與組合規則（僅供畫面與計數演示，不得搬入 production）

每檔基金×每個條件的三態（符合／不符合／資料不足無法判定）由 `fund_search_fake_inputs.py` **明確提供**，預覽不從任何金融數值推導它。
多個條件的組合規則（任一不符合→不符合；否則任一資料不足→無法判定；否則→符合）**僅屬測試輸入的計數演示規則，不是金融公式、不是正式篩選判準，僅供畫面與計數演示，不得搬入 production。**
無法判定絕不算符合／不符合／0；缺值絕不轉 0（缺值格是規則表 `◇ 資料未備`）。

## 字樣：已核准取規則表，新字樣一律 PendingWording

- 已核准（取 `shared/ui_semantics/rules.py`，本目錄不複寫）：`◇ 資料未備`、`⬜ 無法判定`、`⛔ 取數失敗`、`資料不足`；EXP-0 與「尚未設定條件」「目前條件下沒有符合的基金」取 `exp_counts`。
- 其餘全是 `PendingWording`（出處標「ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行」），畫面帶 `data-pending-wording` 與虛線底線。
  **待定字清單**（客戶定字後才搬進規則表並自此刪除；其中 `isin_note` 是 ISIN 常駐說明，`DEC-2026-11-17-02` 明列「ISIN 常駐說明逐字句」待客戶確認；
  句子取自決策包 0.4-#4 與 Q2 方案 A 的擬字「ISIN：尚未啟用（目前沒有已核准的 ISIN 對照來源）」，核准狀態未確認，故仍標暫行）：

| key | 暫行字樣 | 實際出處（`wording.py` 的 `SOURCE`，全部同一句） | 來源性質（執行組讀法，未經第二組驗證；分類：客戶逐字／線框已列／決策包擬句／ChatGPT 新擬） |
|---|---|---|---|
| `page_title` | 找一檔基金 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 客戶逐字（IA 用語／裁示原句）；決策包 W1 |
| `input_label` | MoneyDJ 基金代碼或 ISIN | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 客戶逐字（IA 用語／裁示原句）；決策包 W-入口標示 |
| `isin_note` | ISIN：尚未啟用（目前沒有已核准的 ISIN 對照來源） | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 決策包擬句（Q2 方案 A；客戶原句為『尚未啟用／目前沒有已核准的 ISIN 對照來源』） |
| `submit_label` | 查詢 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 決策包擬句（W2） |
| `isin_inactive_result` | ISIN 目前未啟用 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | ChatGPT 新擬／執行組暫擬 |
| `isin_inactive_detail` | 未用 ISIN 取數、未猜測任何代碼 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 決策包擬句（W5，78 S5 乙原句） |
| `fake_tag` | FAKE 模擬 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | ChatGPT 新擬／執行組暫擬 |
| `row_result` | 查詢結果 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | ChatGPT 新擬／執行組暫擬 |
| `result_found` | 找到模擬項目（FAKE） | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | ChatGPT 新擬／執行組暫擬 |
| `suffix_unrecognized` | （無法辨識格式） | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 決策包擬句（W4） |
| `suffix_no_fixture` | （離線預覽沒有這個代碼的模擬資料） | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | ChatGPT 新擬／執行組暫擬 |
| `fail_impact` | 無法顯示這檔基金 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 決策包擬句（W14 替代句） |
| `fail_not_identity` | 這次取數失敗，不是對基金身份的判斷 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | ChatGPT 新擬／執行組暫擬（取代 W14『這不代表基金不存在』，因禁用字樣） |
| `row_input_code` | 輸入代碼 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 決策包擬句（W7） |
| `row_identity` | 基金身份 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 線框核准稿已列（未核准）（U6） |
| `identity_unconfirmed` | ◇ 尚未確認 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 線框核准稿已列（未核准）（U6『◇ 尚未確認』） |
| `single_note` | 單檔查詢結果（唯讀；不會加入選股池或任何清單） | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 決策包擬句（W6 中性句） |
| `row_name` | 基金名稱 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 線框核准稿已列（未核准）（U7） |
| `row_inception` | 成立日 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 線框核准稿已列（未核准）（U7） |
| `row_dividend_mode` | 配息方式 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 線框核准稿已列（未核准）（U7） |
| `row_mgmt_fee` | 經理費率 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 線框核准稿已列（未核准）（U7） |
| `details_title` | 基本資料｜尚未取得｜來源與限制 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 線框核准稿已列（未核准）（U14／W17） |
| `row_source` | 來源 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 線框核准稿已列（未核准）（U7 位置） |
| `row_fallback` | 備援來源 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 線框核准稿已列（未核准）（U7 位置） |
| `row_asof` | 資料日 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 線框核准稿已列（未核准）（U7 位置） |
| `not_obtained_note` | 尚未取得：來源、備援來源、資料日的值尚未接線 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | ChatGPT 新擬／執行組暫擬 |
| `limits_note` | 本畫面為離線 FAKE 模擬，不是 MoneyDJ 或任何正式來源的資料；沒有發出任何請求 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | ChatGPT 新擬／執行組暫擬 |
| `section_exp_title` | 依條件篩選 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 決策包擬句（W15；79／80 線框已用） |
| `exp0_title` | 篩選結果 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | ChatGPT 新擬／執行組暫擬 |
| `exp1_title` | 本次瀏覽暫時條件 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 線框核准稿已列（未核准）（L5 之『暫時條件』語意） |
| `exp1_note` | 這些條件只在本次瀏覽生效，離開本頁後會清除 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 線框核准稿已列（未核准）（L8／W19 改寫：刪去『與欄位設定』） |
| `cond_label` | FAKE 條件 {n} | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | ChatGPT 新擬／執行組暫擬 |
| `exp2_title` | 結果清單 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 44 EXP-2／EXP-7 規則欄既有欄名（『候選清單卡』改寫為『結果清單』） |
| `exp7_title` | 篩選軌跡 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 44 EXP-2／EXP-7 規則欄既有欄名（『篩選軌跡』） |
| `exp_fail_impact` | 此區無法顯示篩選結果 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | ChatGPT 新擬／執行組暫擬 |
| `col_matched` | 符合 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 線框核准稿已列（未核准）（L3『符合』） |
| `col_undetermined` | 無法判定 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 線框核准稿已列（未核准）（L3『無法判定』） |
| `col_code` | 基金代碼 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 44 EXP-2／EXP-7 規則欄既有欄名 |
| `col_name` | 基金名稱 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 44 EXP-2／EXP-7 規則欄既有欄名 |
| `col_ccy` | 幣別 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 44 EXP-2／EXP-7 規則欄既有欄名 |
| `col_nav_date` | 最近淨值日 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 44 EXP-2／EXP-7 規則欄既有欄名 |
| `col_nav` | 最近淨值 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 44 EXP-2／EXP-7 規則欄既有欄名 |
| `col_div` | 近 12 個月配息佔淨值比 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 44 EXP-2／EXP-7 規則欄既有欄名 |
| `col_cond` | 條件 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 44 EXP-2／EXP-7 規則欄既有欄名（『條件文字』改寫） |
| `col_before` | 套用前檔數 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 44 EXP-2／EXP-7 規則欄既有欄名（『套用前檔數』） |
| `row_undetermined_suffix` | （資料未備） | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 線框核准稿已列（未核准）（L2『⬜ 無法判定（資料未備）』的括號） |

## 與規格不一致或需設計者裁示的點

1. **W14 的「這不代表基金不存在」與禁用字樣衝突**：決策包 W14 擬在取數失敗處加「這不代表基金不存在」，但任務規格禁止畫面出現「基金不存在」。本預覽改寫為「這次取數失敗，不是對基金身份的判斷」（暫行）。
2. **`shared` 白名單**：任務規格禁止 import `shared`，但已核准字樣只住 `shared/ui_semantics/rules.py`；本預覽只 import `shared.ui_semantics`（與 `ui_v3` 守衛既有的白名單相同），守衛鎖定 `shared` 其餘一律禁止。
3. **「條件未設定」不是獨立情境**：它是 EXP-1 勾選框的初始狀態，五個選股池情境都適用。
4. **EXP-7 套用順序**：勾選框沒有「使用者新增的順序」，本預覽依畫面順序（條件 1→2→3）累計套用。
5. **EXP-2 缺值格**：44 原文缺值格寫 `⬜`，本預覽依 `BL-0532`／`DEC-2026-11-02-01` 的正式模式缺值字樣寫 `◇ 資料未備`；無法判定列另標「⬜ 無法判定」。
6. **harness selectbox**：Streamlit 預設高度約 40px，未達 48px 觸控下限；renderer 內的輸入框、查詢鈕、條件勾選、details 摘要列都量到 ≥48px。
7. **隱藏 Streamlit 內建的「Press Enter to submit form」提示**：它會蓋住長輸入；Enter 仍照常提交（瀏覽器守衛驗證）。

8. **EXP-7 欄位與空狀態與 44 §EXP-7 不同**：本預覽 EXP-7 每列四格（條件／套用前檔數／符合／無法判定），44 §EXP-7 規則欄為三欄（條件文字／套用前檔數／套用後檔數）；
   無條件時 44 要求「`來源缺`＋『尚未設定條件』」，本預覽只顯示「尚未設定條件」。是否 amendment 屬設計者／客戶裁示，本預覽不改。
9. **結果卡未回顯輸入類型**：決策包〔已核〕句「輸入類型：代碼型字串（原值未改寫）」沒有出現在結果卡；ISIN 情境不回顯輸入、也沒有基金身份列（只出「ISIN 目前未啟用」說明）。是否補回顯屬設計者裁示。
10. **成立日／配息方式／經理費率放在結果卡本體**：決策包 Q6 方案 B 是放收合區，Q6 仍待客戶；本預覽依線框核准稿 U7 放卡內，值一律 `◇ 資料未備`。
11. **EXP-2 缺值字樣適用性**：本預覽用 `◇ 資料未備`（44 原文 `⬜`）；`shared/ui_semantics/rules.py` 該表檔頭自述「只限正式模式，示範模式仍是 `⬜ 資料未備`」，本預覽屬 FAKE 預覽而非正式模式，哪一種適用待裁示。
12. **ISIN 形判定為啟發式**：預覽用「2 字母＋9 英數＋1 數字」判斷輸入像不像 ISIN，只表示輸入形態、不是正式 resolver 或格式契約，可能與某些真實代碼撞型（撞型者會被擋在「ISIN 目前未啟用」）。
13. **輸入正規化**：比對前做 `raw.strip().upper()`；未做 Unicode 正規化（全形英數、零寬字元、RTL 控制字元都不會被折疊，一律落入「無法辨識格式」）；畫面顯示的輸入仍是原值（escape 後）。
14. **空白送出**：顯示「無法判定（無法辨識格式）」，輸入代碼列寫缺值字樣；是否改成不送出或另有提示屬設計者裁示。
15. **缺「空選股池」情境**：目前五個情境不含「選股池為空（0 檔）」；N=0、M=0 只由「無符合」情境（有基金但全不符合）表達。
16. **`result_found`「找到模擬項目（FAKE）」可能被讀成基金存在**：它只表示 fixture 命中，結果卡同時標「FAKE 模擬」且基金身份固定「◇ 尚未確認」；措辭是否需要再收斂屬設計者裁示。
17. **`identity_unconfirmed`（`◇ 尚未確認`）是否改取規則表**：已查 `shared/ui_semantics/rules.py`，**沒有**對應「尚未確認」的 entry（`◇` 符號只出現在 `missing`＝`◇ 資料未備`）。故維持 PendingWording；
    改用 `◇ 資料未備` 或新增規則表 entry，由設計者決定，本預覽不自行改。

## 測試的變異對象（避免誤讀）

- **對判定函式（checker）變異者**（`fund_search_support.py`／`fund_search_browser_lib.py` 的 `*_violations`，含瀏覽器 DOM 注入）：只證明「檢查函式抓得到這種壞頁面」，**不證明 production renderer 不會產生該錯誤**。
- **真正對 production 程式變異者**（monkeypatch 後重跑 production renderer／view model；皆在 `tests/poc_fund_search_preview/test_fund_search_logic_and_renderer.py`）：
  `test_mutation_without_escape_turns_red`（`R.safe` 換成不 escape）、`test_mutation_removing_any_safe_branch_turns_the_special_char_guard_red`（`R.safe` 逐分支拿掉：`$`、反斜線、換行）、
  `test_mutation_renderer_with_wrong_n_raises_through_exp_counts`（餵錯 N 的 view 給 production renderer，由 `exp_counts` 驗證擋下）。

## NOT VERIFIED

- Streamlit Cloud 與真機（觸控、軟鍵盤、Safari）：未驗；瀏覽器守衛只在本機 headless Chromium（390×844、768、1280）跑。瀏覽器守衛屬 slow lane（CI slow lane 標 `continue-on-error`，紅了不擋 merge；fast lane 的 AST／renderer／AppTest 守衛才擋）。
- 正式資料接線、production 掛載（registry／`app_preview`／導覽）、🔍 頁面上線：本批全都沒做，也沒授權。
- `S2-T0`（`DEC-2026-11-14-08`）維持暫緩：本預覽不是 S2-T0，也不解除它。
- 斷網測試只攔 `socket.socket.connect` 與 `socket.create_connection`；讀憑證測試只攔 `os.environ.get`；措辭為「在上述攔截範圍內未偵測到」，不是「已證明不連網／不讀憑證」。瀏覽器的 request 事件只涵蓋 HTTP 請求（不含 WebSocket 本身；Streamlit 自己的 WebSocket 連本機）。
- 單組作者實作與自驗，未經非作者 QA；自驗不是 QA。
- FAKE 多欄展示的欄位集合、新字樣定稿、ISIN 常駐說明逐字句、Cloud／真機驗收：`DEC-2026-11-17-02` 列為待客戶確認。
