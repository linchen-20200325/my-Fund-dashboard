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

| key | 暫行字樣 |
|---|---|
| `page_title` | 找一檔基金 |
| `input_label` | MoneyDJ 基金代碼或 ISIN |
| `isin_note` | ISIN：尚未啟用（目前沒有已核准的 ISIN 對照來源） |
| `submit_label` | 查詢 |
| `isin_inactive_result` | ISIN 目前未啟用 |
| `isin_inactive_detail` | 未用 ISIN 取數、未猜測任何代碼 |
| `fake_tag` | FAKE 模擬 |
| `row_result` | 查詢結果 |
| `result_found` | 找到模擬項目（FAKE） |
| `suffix_unrecognized` | （無法辨識格式） |
| `suffix_no_fixture` | （離線預覽沒有這個代碼的模擬資料） |
| `fail_impact` | 無法顯示這檔基金 |
| `fail_not_identity` | 這次取數失敗，不是對基金身份的判斷 |
| `row_input_code` | 輸入代碼 |
| `row_identity` | 基金身份 |
| `identity_unconfirmed` | ◇ 尚未確認 |
| `single_note` | 單檔查詢結果（唯讀；不會加入選股池或任何清單） |
| `row_name` | 基金名稱 |
| `row_inception` | 成立日 |
| `row_dividend_mode` | 配息方式 |
| `row_mgmt_fee` | 經理費率 |
| `details_title` | 基本資料｜尚未取得｜來源與限制 |
| `row_source` | 來源 |
| `row_fallback` | 備援來源 |
| `row_asof` | 資料日 |
| `not_obtained_note` | 尚未取得：來源、備援來源、資料日的值尚未接線 |
| `limits_note` | 本畫面為離線 FAKE 模擬，不是 MoneyDJ 或任何正式來源的資料；沒有發出任何請求 |
| `section_exp_title` | 依條件篩選 |
| `exp0_title` | 篩選結果 |
| `exp1_title` | 本次瀏覽暫時條件 |
| `exp1_note` | 這些條件只在本次瀏覽生效，離開本頁後會清除 |
| `cond_label` | FAKE 條件 {n} |
| `exp2_title` | 結果清單 |
| `exp7_title` | 篩選軌跡 |
| `exp_fail_impact` | 此區無法顯示篩選結果 |
| `col_matched` | 符合 |
| `col_undetermined` | 無法判定 |
| `col_code` | 基金代碼 |
| `col_name` | 基金名稱 |
| `col_ccy` | 幣別 |
| `col_nav_date` | 最近淨值日 |
| `col_nav` | 最近淨值 |
| `col_div` | 近 12 個月配息佔淨值比 |
| `col_cond` | 條件 |
| `col_before` | 套用前檔數 |
| `row_undetermined_suffix` | （資料未備） |

## 與規格不一致或需設計者裁示的點

1. **W14 的「這不代表基金不存在」與禁用字樣衝突**：決策包 W14 擬在取數失敗處加「這不代表基金不存在」，但任務規格禁止畫面出現「基金不存在」。本預覽改寫為「這次取數失敗，不是對基金身份的判斷」（暫行）。
2. **`shared` 白名單**：任務規格禁止 import `shared`，但已核准字樣只住 `shared/ui_semantics/rules.py`；本預覽只 import `shared.ui_semantics`（與 `ui_v3` 守衛既有的白名單相同），守衛鎖定 `shared` 其餘一律禁止。
3. **「條件未設定」不是獨立情境**：它是 EXP-1 勾選框的初始狀態，五個選股池情境都適用。
4. **EXP-7 套用順序**：勾選框沒有「使用者新增的順序」，本預覽依畫面順序（條件 1→2→3）累計套用。
5. **EXP-2 缺值格**：44 原文缺值格寫 `⬜`，本預覽依 `BL-0532`／`DEC-2026-11-02-01` 的正式模式缺值字樣寫 `◇ 資料未備`；無法判定列另標「⬜ 無法判定」。
6. **harness selectbox**：Streamlit 預設高度約 40px，未達 48px 觸控下限；renderer 內的輸入框、查詢鈕、條件勾選、details 摘要列都量到 ≥48px。
7. **隱藏 Streamlit 內建的「Press Enter to submit form」提示**：它會蓋住長輸入；Enter 仍照常提交（瀏覽器守衛驗證）。

## NOT VERIFIED

- Streamlit Cloud 與真機（觸控、軟鍵盤、Safari）：未驗；瀏覽器守衛只在本機 headless Chromium（390×844、768、1280）跑。瀏覽器守衛屬 slow lane（CI slow lane 標 `continue-on-error`，紅了不擋 merge；fast lane 的 AST／renderer／AppTest 守衛才擋）。
- 正式資料接線、production 掛載（registry／`app_preview`／導覽）、🔍 頁面上線：本批全都沒做，也沒授權。
- `S2-T0`（`DEC-2026-11-14-08`）維持暫緩：本預覽不是 S2-T0，也不解除它。
- 斷網測試只攔 `socket.socket.connect` 與 `socket.create_connection`；讀憑證測試只攔 `os.environ.get`；措辭為「在上述攔截範圍內未偵測到」，不是「已證明不連網／不讀憑證」。瀏覽器的 request 事件只涵蓋 HTTP 請求（不含 WebSocket 本身；Streamlit 自己的 WebSocket 連本機）。
- 單組作者實作與自驗，未經非作者 QA；自驗不是 QA。
- FAKE 多欄展示的欄位集合、新字樣定稿、ISIN 常駐說明逐字句、Cloud／真機驗收：`DEC-2026-11-17-02` 列為待客戶確認。
