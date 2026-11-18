# 🔍 找一檔基金／依條件篩選｜離線 FAKE 隔離 Preview（非正式頁面、非正式資料）

- 授權依據：`DEC-2026-11-17-02`（要點轉述；客戶選定 `BL-0553` 方案 A 並以五點答覆；來源為對話提示語，repo 無逐字存檔，QA 無法核對，NOT VERIFIED）。
  只授權**本目錄與 `tests/poc_fund_search_preview/`** 的完全離線 FAKE Preview。UI 設計規格由 ChatGPT 規劃（「ChatGPT UI 設計方向 2026-11-17」），**不是客戶逐字裁示**。
- 補充授權：`DEC-2026-11-17-03`（G-1～G-6 限縮裁示與視覺對比要求；要點轉述，同樣 NOT VERIFIED；UI 設計文字由 ChatGPT 規劃，非客戶逐字裁示；範圍與限制見下方〈DEC-2026-11-17-03 適用範圍與視覺對比量測〉）。
- 這**不是** 🔍 頁面上線：`ui_v3/shell/registry.py`、`ui_v3/app_preview.py`、`ui_v3/pages/*`、導覽、frozen 44、正式公式／Schema／FX、Old UI、`ui_v2` 一律沒動；
  不接 Google Sheet／選股池、不讀 `user_setting`、不做 ISIN 解析、不發任何請求、不讀 secrets／環境變數、不寫檔或設定。**不得宣稱 🔍 頁面功能已完成。**
- 啟動：`streamlit run poc/fund_search_fixture_preview/app_fund_search_preview.py`（在 repo 根目錄執行）。

## 畫面（單欄、手機優先；一個入口上下排列）

頁頂固定一列「FAKE／測試資料（離線注入，未執行任何真實請求）」與 FAKE 代碼提示（屬 harness，不屬 renderer）。

**上區「找一檔基金」**：標題 → 單一輸入框「MoneyDJ 基金代碼或 ISIN」（不放範例碼）→ 常駐 ISIN 未啟用說明（無狀態符號，緊鄰輸入框）→「查詢」鈕
（`st.form`＋`form_submit_button`，Enter 與點擊等效）→ 結果卡 → 預設收合、不巢狀的單一 `<details>`「基本資料｜尚未取得｜來源與限制」。

| 輸入（去頭尾空白、轉大寫後比對） | 結果 |
|---|---|
| `FAKE-OK01` | 找到模擬項目：結果卡標「FAKE 模擬」，基金名稱為 FAKE 名稱，成立日／配息方式／經理費率一律 `⬜ 資料未備`（PendingWording，見下方「缺值字樣」；不補假金融數據） |
| `FAKE-LOW1` | 資料不足（規則表既有「資料不足」）：名稱等欄位全為 `⬜ 資料未備` |
| `FAKE-ERR1` | 查詢失敗：規則表既有 `⛔ 取數失敗`＋「無法顯示這檔基金」＋「這次取數失敗，不是對基金身份的判斷」；不畫任何資料列 |
| 空白、或不像代碼的字串 | `⬜ 無法判定（無法辨識格式）`——無法判定，**不是**「不存在」 |
| 像代碼但 fixture 沒有（例 `ABC123`） | `⬜ 無法判定（離線預覽沒有這個代碼的模擬資料）` |
| ISIN 形（2 字母＋9 英數＋1 數字） | **只**顯示「ISIN 目前未啟用」：不解析、不取數、不出結果卡、不回顯輸入 |

結果卡：「輸入代碼」顯示輸入**原值**；代碼型輸入（`FAKE-OK01`／`FAKE-LOW1`／`FAKE-ERR1`／`ABC123` 這類格式通過、非 ISIN 形者）另有一列「輸入類型：代碼型字串（原值未改寫）」（決策包〔已核〕句，只表示輸入形態，不暗示已解析為正式 MoneyDJ 身份；空白／不像代碼／ISIN 情境不加）（一律 HTML escape；輸入 `<script>` 不會執行也不會被當標籤）；「基金身份」固定 `◇ 尚未確認`（不因查詢成功改成已確認）；
「單檔查詢結果（唯讀；不會加入選股池或任何清單）」。畫面任何情境都不出現 NAV／報酬／績效／推薦／最佳／排名／「基金不存在」「查無基金」。

**下區「依條件篩選」**（以分隔線與上區區隔，不增加頁內分頁；harness 的 selectbox 切換選股池情境）：

- **EXP-0**：結論文案**一律取** `ui_v3.viewmodels.exp_counts.exp0_conclusion`（不重造）。零生效條件 → 「尚未設定條件」，不展示 N／M。
- **EXP-1「本次瀏覽暫時條件」**：三個 FAKE 條件勾選框（`FAKE 條件 1／2／3`），只在本次 `session_state` 生效，**不寫任何持久層**、不畫存檔鈕；重新載入或新瀏覽階段回到初始（零條件）。
- **EXP-2 結果清單**：一列一檔（卡片，不橫向捲動），固定順序＝`fund_code` 字面值升冪（不是名次）；欄位只用 44 `EXP-2` 規則欄既有欄名（基金代碼、基金名稱、幣別、最近淨值日、最近淨值、近 12 個月配息佔淨值比）；
  值皆 `FAKE 值` 或 `◇ 資料未備`；無法判定的列標規則表「⬜ 無法判定」。列數＝N＋M（`verify_exp2_row_count`）。**不做 EXP-4 排序**。
- **EXP-7 篩選軌跡**：逐條件（依畫面順序累計套用）顯示套用前檔數、符合、無法判定；末列＝EXP-0 的 N／M（`verify_exp7_last_row`）。
- 不實作 EXP-3／4／5／6、存檔、歸一化圖。

選股池情境（harness selectbox）：①有符合 ②無符合（有基金、全不符合） ③只有無法判定 ④有符合也有無法判定 ⑤選股池為空（0 檔；EXP-0 卡帶 `data-pool-size`，EXP-7 套用前檔數為 0） ⑥選股池來源失敗（EXP 區顯示 `⛔ 取數失敗`，不展示 N／M，不偽稱 0）。
「條件未設定」是 widget 的**初始狀態**，六個情境都適用（不另設情境）。各情境全勾條件的 (N, M)：(2,0)、(0,0)、(0,3)、(2,2)、空池 (0,0)；子集合另有不同結果（例：情境④只勾條件 1 是 (4,1)）。

## 三態與組合規則（僅供畫面與計數演示，不得搬入 production）

每檔基金×每個條件的三態（符合／不符合／資料不足無法判定）由 `fund_search_fake_inputs.py` **明確提供**，預覽不從任何金融數值推導它。
多個條件的組合規則（任一不符合→不符合；否則任一資料不足→無法判定；否則→符合）**僅屬測試輸入的計數演示規則，不是金融公式、不是正式篩選判準，僅供畫面與計數演示，不得搬入 production。**
無法判定絕不算符合／不符合／0；缺值絕不轉 0（缺值格是 PendingWording `⬜ 資料未備`，見下）。

## 字樣：已核准取規則表，新字樣一律 PendingWording

- 已核准（取 `shared/ui_semantics/rules.py`，本目錄不複寫）：`⬜ 無法判定`、`⛔ 取數失敗`、`資料不足`；EXP-0 與「尚未設定條件」「目前條件下沒有符合的基金」取 `exp_counts`。
- **缺值字樣（本批判定，`DEC-2026-11-17-02` (d) 待裁，非自動沿用正式模式 `◇`）**：規則表 `missing`（`◇ 資料未備`）依 `rules.py` 檔頭（:9–10）與 BL-0532 **只限正式模式**，檔頭並寫「示範模式仍是 `⬜ 資料未備`」，但規則表**沒有**示範模式缺值 entry；
  另 `DEC-2026-11-13-06` (6) 對 New UI2 寫 `◇ 資料未備`，兩者不一致。本預覽是 FAKE 示範性質，故**不取** `missing`，缺值格一律用 PendingWording `missing_demo`＝`⬜ 資料未備`（與 `⬜ 無法判定` 以不同字樣、不同函式、不同 DOM 標記 `data-kind="missing"` 分開）。
  『無法判定』與『資料缺值』分開呈現：整檔無法判定列沿用 44（:4287，客戶 2026-10-13 逐字）的結構『⬜ 無法判定（資料未備）』，缺值格只寫『⬜ 資料未備』。哪一種適用屬待 Gate（G-3）。
- 其餘全是 `PendingWording`（出處標「ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行」），畫面帶 `data-pending-wording` 與虛線底線。
  **待定字清單**（客戶定字後才搬進規則表並自此刪除；其中 `isin_note` 是 ISIN 常駐說明，`DEC-2026-11-17-02` 明列「ISIN 常駐說明逐字句」待客戶確認；
  句子取自決策包 0.4-#4 與 Q2 方案 A 的擬字「ISIN：尚未啟用（目前沒有已核准的 ISIN 對照來源）」，核准狀態未確認，故仍標暫行）：

| key | 暫行字樣 | 實際出處（`wording.py` 的 `SOURCE`，全部同一句） | 來源性質（執行組讀法，未經第二組驗證；分類：客戶逐字／線框已列／決策包擬句／ChatGPT 新擬） |
|---|---|---|---|
| `page_title` | 找一檔基金 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 客戶逐字（IA 用語／裁示原句）；決策包 W1 |
| `input_label` | MoneyDJ 基金代碼或 ISIN | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 客戶逐字（IA 用語／裁示原句）；決策包 W-入口標示 |
| `isin_note` | ISIN：尚未啟用（目前沒有已核准的 ISIN 對照來源） | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 決策包擬句（Q2 方案 A；客戶原句為『尚未啟用／目前沒有已核准的 ISIN 對照來源』）；已採用 ChatGPT 設計，仍 Pending 定字（G-4） |
| `submit_label` | 查詢 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 決策包擬句（W2） |
| `isin_inactive_result` | ISIN 目前未啟用 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | ChatGPT 新擬／執行組暫擬 |
| `isin_inactive_detail` | 未用 ISIN 取數、未猜測任何代碼 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 決策包擬句（W5，78 S5 乙原句） |
| `fake_tag` | FAKE 模擬 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | ChatGPT 新擬／執行組暫擬 |
| `row_result` | 查詢結果 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | ChatGPT 新擬／執行組暫擬 |
| `result_found` | 找到模擬項目（FAKE） | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | ChatGPT 新擬／執行組暫擬 |
| `suffix_unrecognized` | （無法辨識格式） | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 決策包擬句（W4） |
| `suffix_no_fixture` | （離線預覽沒有這個代碼的模擬資料） | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | ChatGPT 新擬／執行組暫擬 |
| `fail_impact` | 無法顯示這檔基金 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 決策包擬句（W14 替代句） |
| `fail_not_identity` | 這次取數失敗，不是對基金身份的判斷 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | ChatGPT 設計句（取代 W14『這不代表基金不存在』，因禁用字樣）；已採用 ChatGPT 設計，仍 Pending 定字；W14 在線框層另見 `DEC-2026-11-13-06` (6)、`DEC-2026-11-14-02` (12)，句子替換仍是 Gate（G-2） |
| `missing_demo` | ⬜ 資料未備 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 規則表檔頭所述示範模式字樣（規則表無對應 entry）；已採用 ChatGPT 設計，仍 Pending 定字；`DEC-2026-11-17-02` (d) 待裁 |
| `row_input_type` | 輸入類型 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 決策包〔已核〕句（Q3／C13，逐字檔 `2026-11-01_batch_e_gate_rulings.md` 第三節）；已採用 ChatGPT 設計，仍 Pending 定字 |
| `input_type_code` | 代碼型字串（原值未改寫） | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 同上（客戶逐字句，決策包 `docs/evidence/exp_wireframe_decision_pack_2026_11_13.md` 0.4 #3）；已採用 ChatGPT 設計，仍 Pending 定字 |
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
| `col_matched` | 符合 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 線框核准稿已列（未核准）（L3『符合』）；`DEC-2026-11-14-04` (5) 已決；括號句另見 44 :4287（客戶 2026-10-13 逐字）；PendingWording 狀態不變 |
| `col_undetermined` | 無法判定 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 線框核准稿已列（未核准）（L3『無法判定』）；`DEC-2026-11-14-04` (5) 已決；括號句另見 44 :4287（客戶 2026-10-13 逐字）；PendingWording 狀態不變 |
| `col_code` | 基金代碼 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 44 EXP-2／EXP-7 規則欄既有欄名 |
| `col_name` | 基金名稱 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 44 EXP-2／EXP-7 規則欄既有欄名 |
| `col_ccy` | 幣別 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 44 EXP-2／EXP-7 規則欄既有欄名 |
| `col_nav_date` | 最近淨值日 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 44 EXP-2／EXP-7 規則欄既有欄名 |
| `col_nav` | 最近淨值 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 44 EXP-2／EXP-7 規則欄既有欄名 |
| `col_div` | 近 12 個月配息佔淨值比 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 44 EXP-2／EXP-7 規則欄既有欄名 |
| `col_cond` | 條件 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 44 EXP-2／EXP-7 規則欄既有欄名（『條件文字』改寫） |
| `col_before` | 套用前檔數 | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 44 EXP-2／EXP-7 規則欄既有欄名（『套用前檔數』） |
| `row_undetermined_suffix` | （資料未備） | ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行 | 線框核准稿已列（未核准）（L2『⬜ 無法判定（資料未備）』的括號）；`DEC-2026-11-14-04` (5) 已決；括號句另見 44 :4287（客戶 2026-10-13 逐字）；PendingWording 狀態不變 |
| `pool_empty_marker` | ○ 選股池目前是空的 | 執行組暫擬；DEC-2026-11-17-03 授權以符號或文字輔助標示空池，但未指定字句；待 ChatGPT／客戶確認定字（`SOURCE_DEC03`；精確相等，不是其他 key 的前綴出處） | 執行組暫擬（非 ChatGPT 設計、非客戶逐字；DEC-2026-11-17-03 只授權以符號或文字輔助標示空池、未指定字句，字句待 ChatGPT／客戶確認；符號＋短語，只陳述池是空的，不含失敗／缺失／來源字眼；PendingWording，未進規則表） |

## 與規格不一致或需設計者裁示的點（最後一次更新：2026-11-17 收斂批）

狀態標記：**已採用 ChatGPT 設計，仍 Pending 定字**＝本批依 ChatGPT UI 設計方向落實，非客戶逐字裁示、字樣仍待客戶定；**待 Gate**＝預覽不自行選，維持現狀。

1. **W14 的「這不代表基金不存在」與禁用字樣衝突**：決策包 W14 原句含禁用字樣「基金不存在」；本預覽採 ChatGPT 設計句「這次取數失敗，不是對基金身份的判斷」（`fail_not_identity`；已採用 ChatGPT 設計，仍 Pending 定字）。
   W14 在線框層已被採用（`DEC-2026-11-13-06` (6)、`DEC-2026-11-14-02` (12)），與 ChatGPT 規格「禁『基金不存在』字串」並存；句子替換仍是 Gate（G-2）。
2. **`shared.ui_semantics` import**（本批對 (i) 的明確結論）：
   - 現況事實：`DEC-2026-11-17-02` 只明列可 import `exp_counts` 與 `preview_wording`，**未提** `shared.ui_semantics`；`ui_v3` 守衛白名單（`tests/ui_v3/ui_v3_guard_lib.py`）只放行 `viewmodels/`、`pages/` 兩層 import `shared.ui_semantics`，`poc/` 不在其掃描與放行範圍；
     姊妹隔離預覽（`poc/dual_theme_isolated`、`poc/assets_fixture_preview`）都**沒有** import `shared`（前者檔頭明寫「PoC 不 import 它」）。
   - 但被授權 import 的 `ui_v3.viewmodels.preview_wording` 與 `exp_counts` 的依賴鏈本身就 import `shared.ui_semantics.rules`（`preview_wording.py` 開頭），本預覽直接 import 的是同一個已核准字樣來源。
   - 結論：**沒有明文授權、也沒有明文禁止**；本批不追認、不擴大，維持現狀（本目錄守衛鎖定 `shared` 只開 `shared.ui_semantics`），最小 Gate 為 G-1（請客戶/設計者一句話裁示 poc 可否直接 import `shared.ui_semantics`，或改為只經 `preview_wording`）。
3. **「條件未設定」不是獨立情境**：它是 EXP-1 勾選框的初始狀態，六個選股池情境都適用。
4. **EXP-7 套用順序**：勾選框沒有「使用者新增的順序」，本預覽依畫面順序（條件 1→2→3）累計套用（`DEC-2026-11-17-02` (e) 待裁；G-5）。順序只影響中間列，不影響最後一列 N／M（測試鎖定）。
5. **缺值字樣**：見上方「缺值字樣」。44 原文缺值格 `⬜`、`rules.py` 檔頭示範模式 `⬜ 資料未備`、`DEC-2026-11-13-06` (6) 對 New UI2 `◇ 資料未備` 三者不一致；本批採示範模式字樣、標 PendingWording，`DEC-2026-11-17-02` (d) 待裁（G-3）。
6. **harness selectbox**：Streamlit 預設高度約 40px，未達 48px 觸控下限；renderer 內的輸入框、查詢鈕、條件勾選、details 摘要列都量到 ≥48px。
7. **隱藏 Streamlit 內建的「Press Enter to submit form」提示**：它會蓋住長輸入；Enter 仍照常提交（瀏覽器守衛驗證）。
8. **EXP-7 欄位與空狀態**：見下方「EXP-7 規則對照」（差異／衝突，待設計者／客戶；G-6）。
9. **輸入類型列**：已補（`row_input_type`／`input_type_code`，決策包〔已核〕逐字句；僅代碼型輸入；已採用 ChatGPT 設計，仍 Pending 定字）。
10. **成立日／配息方式／經理費率放在結果卡本體**：依核准稿 U7 與 `DEC-2026-11-14-02` (9) Q6＝6a（決策卡 6a 已取代決策包 Q6 方案 B 的收合區設計）放卡內，值一律 `⬜ 資料未備`；`DEC-2026-11-17-02` (g) 仍列待確認；來源／備援／資料日保留在預設收合區。
11. **EXP-2 缺值字樣適用性**：同第 5 點（適用模式差異見下表；待裁）。
12. **ISIN 形判定為啟發式**：預覽用「2 字母＋9 英數＋1 數字」判斷輸入像不像 ISIN，只表示輸入形態、不是正式 resolver 或格式契約，可能與某些真實代碼撞型（撞型者會被擋在「ISIN 目前未啟用」）。
13. **輸入正規化**：比對前做 `raw.strip().upper()`；未做 Unicode 正規化（全形英數、零寬字元、RTL 控制字元都不會被折疊，一律落入「無法辨識格式」）；畫面顯示的輸入仍是原值（escape 後）。
14. **空白送出**：顯示「無法判定（無法辨識格式）」，輸入代碼列寫缺值字樣；是否改成不送出或另有提示屬設計者裁示。
15. **空選股池**：已補 `empty_pool` 情境（0 檔）。N＝0、M＝0 的結論文案仍取 `exp_counts`（與「有基金但零符合」相同句子）；`DEC-2026-11-17-03` 之後，空池另有非顏色輔助標記 `pool_empty_marker`（「○ 選股池目前是空的」，PendingWording，EXP-0／EXP-2／EXP-7 三卡各一列，見下方量測章節）；畫面上其餘區別：EXP-0 卡 `data-pool-size`（0 vs 4）與 EXP-7 首列套用前檔數 0。標記字樣為執行組暫擬、定字待 ChatGPT／客戶確認（見第 18 點）。
16. **`result_found`「找到模擬項目（FAKE）」可能被讀成基金存在**：它只表示 fixture 命中，結果卡同時標「FAKE 模擬」且基金身份固定「◇ 尚未確認」；措辭是否需要再收斂屬設計者裁示。
17. **`identity_unconfirmed`（`◇ 尚未確認`）**：規則表**沒有**對應 entry（`◇` 只出現在 `missing`），維持 PendingWording；不因 fixture 命中而變成已確認。改用規則表字樣或新增 entry 由設計者決定。
18. **`pool_empty_marker` 定字待確認**：「○ 選股池目前是空的」是執行組暫擬，不是 ChatGPT 設計給的句子、也不是客戶逐字；`DEC-2026-11-17-03` 只授權以符號或文字輔助標示空池、**未指定字句**。字句與符號（`○`）待 ChatGPT／客戶確認定字，定字前維持 PendingWording、不進規則表。

### EXP-7 規則對照（只列差異／衝突，不宣稱已解決；不改 frozen 44、不升格正式 EXP-7 契約）

| 規則來源 | 內容 | 適用模式 | 與本預覽的差異／衝突 |
|---|---|---|---|
| frozen 44 §3.3 塊 EXP-7（`docs/v2/44_fund_ui_ssot.md` :1196 起） | 三欄：條件文字／套用前檔數／套用後檔數；條件依使用者新增的順序套用並逐列記錄；末列套用後檔數＝EXP-0 的 N；無條件→`來源缺`＋「尚未設定條件」；某條件因數值未填未生效→兩檔數相等並列尾寫 `未生效` | 44 原文與示範模式（44 :4294 自注示範模式照舊用「套用後檔數」） | **差異**：本預覽四格不是三欄、沒有「套用後檔數」欄；無條件只寫「尚未設定條件」不寫「來源缺」；未實作「未生效」。**待設計者／客戶** |
| 44 §7.3.2 其三（2026-10-13 標的探索客戶裁示；:4291–4292） | 每一條條件寫套用前、符合、無法判定三個數（累計口徑），末列符合數＝EXP-0 的 N；:4292 自注「四欄欄名與累計口徑」決策者為 AI 總管（非客戶原話） | 正式模式（AI 總管落地） | **差異**：本預覽四格（條件＋三數）與其欄名/累計口徑相近，但來源不同——44 :4292 自注非客戶原話；**待設計者／客戶** |
| `DEC-2026-11-14-04` (5) | EXP-7 最後一列符合數＝N、無法判定數＝M；驗收須覆蓋多條條件與缺值；(4) 條件未設定顯示「尚未設定條件」、不展示 N／M | New UI2 🔍 線框層（已決項） | 一致（末列＝N／M 由 `exp_counts.verify_exp7_last_row` 驗；多條件/缺值有測試）；Amendment 範圍未含 EXP-0 N 口徑，見下一列 |
| EXP-0 的 N 口徑：44 規則欄「N 為 EXP-2 列數」vs 後續「N＝符合檔數」 | 44 內部兩種說法；`DEC-2026-11-14-02` (1)／`-04` (3)(5) 採 N＝明確符合、M＝無法判定 | New UI2（DEC 有效） | **衝突（44 內部）**：本預覽依 DEC 採 N＝符合檔數、EXP-2 列數＝N＋M；44 Amendment 範圍未含此句；**待設計者／客戶（G-7）** |
| 執行組／ChatGPT UI 設計方向（見提示語；repo 無逐字存檔，NOT VERIFIED）；`DEC-2026-11-17-02` (e) 待裁 | FAKE 預覽的 EXP-7 四格「條件、套用前、符合、無法判定」（**四格本身不是 DEC 條文**：DEC 五項答覆 (3) 只講零生效條件→EXP-2／EXP-7 不產生結果列，(4) 只講 M 由 fixture 三態產生；DEC 把「預覽四格 vs 44 三欄」列為 (e) 待客戶確認）；不升格正式契約 | 僅本 FAKE Preview（非示範模式亦非正式模式） | 本預覽照做；與 44 三欄／「來源缺」的差異屬 **差異**，歸類（示範 vs 正式 vs FAKE Preview）客戶未明確裁示；44 :2414–2421 自身也登記相關張力待客戶裁決 |
| 條件順序 | 44＝使用者新增順序；本預覽＝畫面勾選序（條件 1→2→3） | — | **差異**：`DEC-2026-11-17-02` (e) 待裁，只影響中間列、不影響末列 N／M（G-5） |

測試鎖定：`test_exp7_columns_are_the_fake_preview_four_and_zero_conditions_say_only_the_no_condition_text`（欄位集合與零條件文案；註解標「FAKE 專屬，非 44 三欄」）。

### 需 Gate、本預覽不得自行動的清單

G-1 poc 直接 import `shared.ui_semantics` 的追認；G-2 W14 句子替換（含線框層採用）；G-3 缺值字樣（`⬜`／`◇`）與適用模式；G-4 ISIN 常駐說明逐字句；G-5 條件套用順序；G-6 零條件歸類／EXP-7 Amendment（三欄 vs 四格、「來源缺」）；G-7 EXP-0 N 口徑。

### 啟發式與守衛限制（揭露，不改行為與文案）

- **輸入形態判斷是啟發式**：`_CODE_SHAPE = [A-Z0-9-]{3,24}`（`fund_search_logic.py`）只看字元集與長度，`---`、`123` 這類輸入也會被判為 `no_fixture` 並顯示「輸入類型：代碼型字串（原值未改寫）」。該列只表示輸入形態，不表示真的是基金代碼；測試 `test_code_shape_is_a_heuristic_*` 明示此現況。是否收緊屬設計者裁示。
- **空池與零符合**：文案取 `exp_counts`，兩者的結論句相同。區分方式（`DEC-2026-11-17-03` 之後）：選股池為空（`data-pool-size="0"`）時 EXP-0／EXP-2／EXP-7 三張結果卡＝虛線框＋灰底＋**非顏色標記列「○ 選股池目前是空的」**（`pool_empty_marker`）；有基金但零符合維持實線白底、無標記。EXP-7 首列「套用前檔數」（0 vs 4）仍在。零條件時沒有軌跡，無從得知池大小，故不標記（測試鎖定）；來源失敗不標記（空池≠失敗）。
- **視覺對比與無障礙**：已於 `DEC-2026-11-17-03` 要求下改為**實測**，結果見下方〈DEC-2026-11-17-03 適用範圍與視覺對比量測〉（舊敘述「虛線邊框對 grey 底手算約 2.8:1，手算、未用工具實測」已被取代：實測確為 2.81:1，已修正為 6.10:1）。螢幕閱讀器讀不到 `data-*` 屬性，但空池與整檔無法判定現在各有可讀的符號＋文字（空池「○ 選股池目前是空的」；無法判定「⬜ 無法判定（資料未備）」），不再只靠虛線／灰底。仍未做的：螢幕閱讀器實機朗讀未驗（NOT VERIFIED）。
- **整檔無法判定的列**：EXP-2 內 `data-row-state="undetermined"` 的卡改為虛線框（純視覺；既有「⬜ 無法判定（資料未備）」字樣不動）。條件勾選區的垂直間距略收緊（`stCheckbox` 負 margin，觸控目標仍 ≥48px，由既有瀏覽器守衛鎖定）。
- **G-1 現況核對**：`preview_wording` 的公開函式（`text`／`is_approved`／`span`…）只取 `rules.APPROVED_WORDING` 的純文字鍵，取不到 `rules.ENTRIES`（`preview_wording.rules` 屬模組層 import，技術上可取得，但那不是它的公開介面）；本預覽用到的 `undetermined`／`fetch_failed` 是 `rules.ENTRIES`（含符號與色調），故 poc 仍須直接 import `shared.ui_semantics`；白名單維持不變（未擴大、也無法收緊），G-1 仍待裁。
- **session_state 寫入守衛是 AST 靜態掃描**：追得到下標／增量／`|=`／方法呼叫與簡單別名，**追不到**解構賦值、海象運算子、函式參數傳遞、`getattr` 等間接寫法。
- **origin 判斷**以 `urllib.parse.urlsplit` 解析；與瀏覽器 WHATWG 的反斜線等形可能不一致。Playwright 的 `request.url` 已是正規化後的 URL，風險低，但未逐形驗證。

## DEC-2026-11-17-03 適用範圍與視覺對比量測

**適用範圍**：`DEC-2026-11-17-03`（要點轉述，NOT VERIFIED；UI 設計文字由 ChatGPT 規劃，非客戶逐字裁示）的 G-1～G-6 定稿方向與視覺對比要求，**只適用本離線 FAKE Preview**（`poc/fund_search_fixture_preview/` 與 `tests/poc_fund_search_preview/`）。
- 不自動變更正式共用字樣、其他模式或正式條件順序契約；G-3 的 `⬜`／`◇` 並存僅限模式區分，不改規則表檔頭「只限正式模式」之規定；G-7 正式改文不在本預覽範圍。
- **PendingWording 身分不變**：本目錄所有新字樣（含本批新增的 `pool_empty_marker`）仍是 PendingWording，客戶定字前不進規則表、不自動升格。
- 本批**只**處理視覺對比要求（空選股池與整檔「無法判定」的虛線邊框 ≥3:1，並有符號或文字輔助）與 G-5「EXP-7 手機可換行、不強制四欄」的測試鎖定；未改 registry／`app_preview`／導覽／`rules.py`／frozen 44／公式／Schema／FX／ISIN。

**量測方法**（`tests/poc_fund_search_preview/test_fund_search_contrast_browser.py` ＋ `fund_search_browser_lib.py` 的 `CONTRAST_JS`／`contrast_ratio`）：真 Chromium（headless shell）於 390×844、768×844、1280×800，在瀏覽器內取 computed style——邊框四邊的 style／寬／色、元素自身的有效底色（逐層疊 alpha）、外層（父元素）有效底色、區塊內每段可見文字的 computed color 與有效底色；以 WCAG 2.x 相對亮度公式 `(L1+0.05)/(L2+0.05)` 即時計算，**斷言裡不寫死任何色值**（改 token 後守衛仍成立）。
- 邊框（非文字）：四邊皆須為虛線、不透明、有寬度，且**對外層背景與對元素自身背景皆 ≥3:1**。
- 文字：空池三卡與整檔無法判定列內每一段可見文字，對其有效底色 **≥4.5:1**，且累計 opacity＝1。
- 變異驗證：把邊框色退回舊值（`color.card.border`）判定必須報紅；把文字改淺判定必須報紅；拿掉標記判定必須報紅（此項呼叫與正式斷言共用的 `marker_violations`，三張卡都須轉紅；非 `not all(...)` 的恆真寫法）。公式本身另以已知值（黑白 21:1、#777 對白 4.48）單測。

**修正**：實測空池卡的虛線邊框（`color.card.border` #7f8ca6）對自身灰底（`color.tone.grey` #e6eaf3）只有 **2.81:1**（< 3:1）；改用**既有** token `color.text.secondary`（#4a5670）作空池卡邊框色（未新增任何全域色票）。整檔無法判定列的虛線邊框（#7f8ca6）落在白底卡面上，實測 3.38:1，**已達標、未更動**。

**量測結果**（量測日 2026-11-17；環境：Chromium headless shell 153.0.8010.12，Linux，Streamlit 1.59.2；三個寬度的數值完全相同）：

| 情境（全勾條件 1～3） | 元素 | 邊框色 | 對自身背景 | 對外層背景 | 修正前（自身／外層） | 文字最低對比（段數） |
|---|---|---|---|---|---|---|
| `empty_pool` | EXP-0 卡 | #4a5670（虛線 1px） | 6.10 | 6.86 | 2.81／3.16 | 6.10（7） |
| `empty_pool` | EXP-2 卡 | #4a5670（虛線 1px） | 6.10 | 6.86 | 2.81／3.16 | 13.50（3） |
| `empty_pool` | EXP-7 卡 | #4a5670（虛線 1px） | 6.10 | 6.86 | 2.81／3.16 | 6.10（26） |
| `mixed`（2 列無法判定） | EXP-2 無法判定列 | #7f8ca6（虛線 1px） | 3.38 | 3.38 | 未更動 | 7.35 |
| `undetermined_only`（3 列） | EXP-2 無法判定列 | #7f8ca6（虛線 1px） | 3.38 | 3.38 | 未更動 | 7.35 |

390／768／1280 三個寬度逐一量測，上表每格三個寬度的比值相同（元素背景不隨寬度改變）。

**符號或文字輔助（不單靠顏色、灰底或虛線）**：空池三卡各一列「○ 選股池目前是空的」（PendingWording `pool_empty_marker`，出處「執行組暫擬；DEC-2026-11-17-03 授權以符號或文字輔助標示空池，但未指定字句；待 ChatGPT／客戶確認定字」）；整檔無法判定列沿用規則表既有「⬜ 無法判定」＋「（資料未備）」（符號＋字樣已存在，守衛鎖定每一列都帶）。空池標記不含失敗／缺失／來源字眼（空池≠取數失敗≠來源缺失）。

**G-5**：EXP-7 每條件一列四格（條件、套用前檔數、符合、無法判定），格線為 `auto-fit`＋`minmax(min(100%,150px),1fr)`，不寫死四欄；測試鎖定：390 寬每條件的四格至少分成兩橫列（已換行；不鎖定恰好幾列）、768／1280 寬每條件的四格 top 相同（同一橫列並排），三個寬度皆無溢出。

**限制**：只量本機 headless Chromium 的 computed style，**不是**像素取樣、不涵蓋抗鋸齒後的實際渲染顏色；虛線 1px 的視覺可辨性、螢幕閱讀器、Cloud／真機均未驗（NOT VERIFIED）。

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
