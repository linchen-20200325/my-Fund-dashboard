# 單檔基金查詢呈現元件｜離線 FAKE 隔離 Preview（非正式頁面、非正式資料）

- 授權依據：`DEC-2026-11-18-04`（要點轉述，來源待核，repo 無逐字存檔，QA 無法核對，**NOT VERIFIED**）。元件規格出自 ChatGPT 總管規劃，**不是客戶逐字裁示**。
  只授權**本目錄與 `tests/poc_fund_lookup_component_preview/`** 的純呈現元件與隔離 harness。
- 這**不是** 🔍 頁面上線：不掛 registry／`app_preview`／導覽（不掛 registry、不改任何既有檔）、不接 Google Sheet、不做 ISIN 解析、不發任何請求、不讀 secrets／環境變數、不寫檔或設定。
  **不得宣稱 🔍 頁面或路徑 B 已完成。**`DEC-2026-11-17-04` 對 `ui_v3/pages/exp.py` 及掛 🔍 頁的排除、`DEC-2026-11-14-08` 對 S2-T0 的暫緩全部維持。
- 啟動：`streamlit run poc/fund_lookup_component_preview/app_fund_lookup_component_preview.py`（在 repo 根目錄執行）。

## 元件與資料流

```
輸入 → harness: lookup_fund(FakeLoader, 輸入)（ui_v3/adapters/fund_lookup.py） → FundLookupView（ui_v3/viewmodels/fund_lookup.py） → renderer
```

- `fund_lookup_renderer.py`：**純呈現**。輸入是注入式 `FundLookupView`；`lookup_card_html(view, fake=...)`／`idle_html()`／`isin_note_html()` 是純函式（無 Streamlit 也能單測）；
  `render_form()`／`render_card()` 才 import streamlit（函式內）。不 import adapter、services、repositories、infra、requests、任何網路或檔案模組。
- `fund_lookup_wording.py`：字樣。已核准字樣（`⛔ 取數失敗`、`⬜ 無法判定`）一律經 `shared.ui_semantics.rules` API 取得（`status()`）；新字樣全是 `PendingWording`（出處 `DEC-2026-11-18-04（轉述，待核）`）。
- `fund_lookup_fake_inputs.py`：`FakeLoader`（L2 `build_profiles` 形狀的假取數函式）與 FAKE 示範代碼。**ViewModel 一律經 adapter 產生，不自行偽造繞過**；
  唯一例外是 `CONFLICT`：現行真實 L2 對這四欄**不可達**（L2 只對幣別用 inconsistent），故以 `conflict_view()` **直接建構** ViewModel 演示呈現語意，harness 的選單明示「直接建構、非 adapter 結果」。
- `app_fund_lookup_component_preview.py`：harness。頁頂 FAKE 標示；`session_state` 只存**經 adapter 淨化後的 ViewModel**（被安全攔截的輸入結構上沒有回顯），不存輸入原值（widget 自己的輸入框 key 除外，Streamlit 行為）。

## 畫面（單欄、手機優先；390 與 1280 兩種寬度驗收）

標題 → 單一輸入框「MoneyDJ 基金代碼或 ISIN」→ 常駐 ISIN 未啟用說明（無狀態符號，緊鄰輸入框）→「查詢」鈕（`st.form`，Enter 與點擊等效）→ 下方單欄結果卡。

**結果欄位只有五個，依序**：輸入代碼、基金名稱、配息方式、成立日期、經理費率。其餘一律不顯示（幣別、淨值、報酬、績效、取得時間、來源／供應者…）。測試以 `data-row` 白名單＋標籤白名單＋字樣掃描鎖定。

| 狀態 | 結果卡內容 | 備註 |
|---|---|---|
| `NOT_QUERIED` | 只有「尚未查詢」 | 沒有任何欄位列 |
| `RESULT` | 五欄；每欄 `VALUE`／`MISSING`／`CONFLICT` 各有獨立文案與 `data-field-status` | 經理費率恆為 `MISSING`（契約上目前無來源）；缺值不寫成 0、「無」、「不配息」 |
| `SOURCE_FAILED` | `⛔ 取數失敗`（規則表）＋「無法顯示這檔基金的欄位」＋原因句＋「這不是對基金身份的判斷」 | `role="alert"`；實線紅色邊框；只有輸入代碼，不畫任何欄位值 |
| `PAGE_UNMATCHED` | `⬜ 無法判定`（規則表）＋「頁面無法確認是這一檔」＋原因句＋「這不是對基金身份的判斷」 | 虛線邊框；不與取數失敗混用 |
| `BLOCKED` | 「輸入未通過檢查，未發出查詢」＋原因句 | `role="alert"`；虛線邊框；ISIN 形／網址形／控制字元的輸入**結構上不回顯** |

**沒有任何一個狀態說「基金不存在／查無」**——取數失敗、頁面無法確認、入口攔截都不是對基金存在與否的結論。卡首固定一個「FAKE 模擬」標籤，DOM 順序在任何狀態列與欄位列之前。

FAKE 示範代碼（harness 頁頂也會列出）：`FAKE-OK01`（配息型、有成立日期）、`FAKE-OK02`（累積型、成立日期缺值）、`FAKE-OK03`（配息方式與成立日期缺值）、
`FAKE-FAIL1`／`FAKE-COOL1`／`FAKE-IOERR`（取數失敗三種原因）、`FAKE-PAGE1`／`FAKE-PAGE2`／`FAKE-PAGE3`／`FAKE-NAME1`（頁面無法確認四種原因）、`FAKE-REJ1`（取數鍵被拒）。
其他合法格式的代碼（例 `ABC123`）＝「找不到對應頁面」，**不推論基金存在與否**；空白、ISIN 形、網址形、控制字元等會在入口被攔截（不呼叫取數函式）。

## 互動、無障礙與 Design Token

- 鍵盤：Tab 順序＝輸入框 → 查詢鈕；Shift+Tab 回到輸入框；Enter 與點擊等效；結果卡內沒有任何可聚焦元素。焦點環以 `color.primary` token 的 2px 外框實作，並以 computed style 實測對比。
- 觸控目標：輸入框與查詢鈕高、寬皆 ≥48px（沿既有 fund_search／nas_diag 規格；任務要求 ≥44px）。harness 自己的 selectbox 約 40px，**屬 harness 不屬元件**，測試據實另量。
- 語意：結果卡 `role="region"` 並以 `aria-labelledby` 指向卡內狀態列；狀態列與可操作原因句同在一個 live region 容器（`role="status"`，失敗與攔截為 `role="alert"`）；五欄以 `<dl>／<dt>／<dd>` 呈現。狀態一律有文字，**不只靠顏色**（另有邊框線型差異）。
- 對比：卡內與 ISIN 說明全部文字、表單控制項（輸入框標籤、輸入文字、查詢鈕文字）對其有效底色 ≥4.5:1；卡片、輸入框、查詢鈕邊框對外層底色 ≥3:1，皆以瀏覽器 computed style 實測（不寫死色碼、不引用 token 表的數字）。Streamlit 預設的輸入框邊框實測僅約 1.06:1，故元件 CSS 以 `color.card.border` token 覆寫輸入框與查詢鈕邊框。
- Design Token：色與尺寸一律經 `ui_v3.design.theme`（`theme.v`／`theme.m`），沒有字面色碼（守衛鎖定）；卡片、tone、間距沿 💼🌍⚙️ 既有元件同一組 token。

## 驗收範圍（已跑）與 NOT VERIFIED

已跑（本機，`tests/poc_fund_lookup_component_preview/`）：單元（renderer 純函式）、AppTest、**真正 Chromium（Playwright）390／1280**（無橫向溢出、觸控目標、鍵盤、焦點環、對比、各狀態文字與語意、無外部請求）、AST／字樣／隔離守衛、
**對 production renderer 與 wording 的記憶體內突變測試**（每個突變至少一個檢查失敗；崩潰型例外不算被殺）。Chromium 路徑由環境變數 `UI_V2_CHROMIUM` 指定（見 `tests/ui_v2/_ui_v2_chromium.py`）；**CI（`CI=true`）依賴缺失一律 fail，不 skip**。

**NOT VERIFIED（未驗）**：Streamlit Cloud 實機、真機（真實手機／平板）、**螢幕閱讀器**（NVDA／VoiceOver／TalkBack 實際朗讀 `role="alert"`／`role="status"` 與 `<dl>` 結構）、
Chromium 以外的瀏覽器（Safari／Firefox）、Streamlit 升級後 `data-testid` 是否仍相容（瀏覽器守衛會轉紅，不會靜默）、與真實 L1／L2 的端到端行為（本元件不接）。
`aria-describedby` 無法由 Streamlit 原生 `text_input` 設定，故 ISIN 說明與輸入框只靠相鄰關係，**未做程式化關聯**。
`<dt>`／`<dd>` 以 `display:inline` 排成同一行，**螢幕閱讀器是否仍把它們當定義清單朗讀未驗**（CSS 改 display 在部分瀏覽器／閱讀器會丟掉 list 語意）。

## 待定字清單（全部 `PendingWording`，客戶／設計者定字後才搬進規則表）

出處一律 `DEC-2026-11-18-04（轉述，待核）`；畫面上帶 `data-pending-wording` 與虛線底線。

| key | 暫行字樣 |
|---|---|
| `page_title` | 找一檔基金 |
| `input_label` | MoneyDJ 基金代碼或 ISIN |
| `isin_note` | ISIN：尚未啟用（目前沒有已核准的 ISIN 對照來源） |
| `submit_label` | 查詢 |
| `not_queried` | 尚未查詢 |
| `fake_tag` | FAKE 模擬 |
| `single_note` | 單檔查詢結果（唯讀；不會加入選股池或任何清單） |
| `not_identity` | 這不是對基金身份的判斷 |
| `row_input_code` | 輸入代碼 |
| `row_name` | 基金名稱 |
| `row_dividend_mode` | 配息方式 |
| `row_inception` | 成立日期 |
| `row_mgmt_fee` | 經理費率 |
| `div_mode_distributing` | 配息型 |
| `div_mode_accumulating` | 累積型 |
| `field_missing` | 此欄尚無可顯示的值 |
| `field_conflict` | 此欄的來源值不一致，未選用任何一個 |
| `state_result` | 查詢結果（模擬資料） |
| `failed_impact` | 無法顯示這檔基金的欄位 |
| `failed_source_failed` | 來源回報取數失敗 |
| `failed_source_cooling` | 來源剛失敗，暫時冷卻中，請稍後再查 |
| `failed_loader_io_error` | 取數連線失敗 |
| `unmatched_impact` | 頁面無法確認是這一檔，不顯示任何欄位 |
| `unmatched_unrecognized_page` | 頁面格式無法辨識 |
| `unmatched_no_page` | 找不到對應頁面 |
| `unmatched_source_not_listed` | 來源沒有列出這一檔 |
| `unmatched_name_unconfirmed` | 頁面上的基金名稱無法確認 |
| `blocked_impact` | 輸入未通過檢查，未發出查詢 |
| `blocked_blank` | 請先輸入基金代碼 |
| `blocked_control_or_non_ascii` | 輸入含不可顯示或非英數的字元 |
| `blocked_url_shape` | 請輸入基金代碼，不要貼網址 |
| `blocked_isin_shape` | ISIN 目前未啟用 |
| `blocked_isin_detail` | 未用 ISIN 取數、未猜測任何代碼 |
| `blocked_code_format` | 代碼格式不符 |
| `blocked_key_rejected` | 這個代碼無法用於查詢 |

## 待客戶／設計者確認（沿 `DEC-2026-11-18-04` 待確認欄；中性列出，不預寫結論）

1. 客戶是否本人要求「平行作業完成 UI + OneBrain」、該方向是否涵蓋本元件；元件放在 `poc/` 隔離目錄、日後是否核准移入 `ui_v3/pages/`（需客戶 Decision Gate）。
2. 元件完成後是否核准任何掛載或正式接線 Gate。本元件**不掛載、不接真實資料**。
3. 缺值符號的取捨（`◇` 或 `⬜`）與「資料未備」用字：`DEC-2026-11-18-01` R2、`EXP-2` 欄位、收合區標題等 fund_search 預覽的待裁示點**不因本元件解決**。
   本元件的缺值字樣刻意**不帶符號**（`field_missing`），以免替客戶決定 ◇／⬜；若客戶定案為某符號，只需改字樣檔一處。
4. `CONFLICT` 與 `MISSING` 的區分需 L2 結構化旗標（現行 L2 對這四欄不可達 CONFLICT；`MISSING` 同時涵蓋「來源沒提供」與「同標籤出現不同值」）。
5. ISIN 常駐說明逐字句、各狀態說明句（含「這不是對基金身份的判斷」、各原因句）的定字。
6. 身分揭露：真實 L2 `resolve_full_keys` 可能經別名表把輸入映為不同的 full_key，`RESULT` 欄位屬於 full_key、不保證等於輸入代碼；adapter 看不到 full_key（Decision Gate，未裁）。
7. Q6：`INPUT_ECHO_MAX`＝64 與 ISIN 形判斷前先移除所有非英數字元的取捨（ISIN 形多一字元的變體與含 `-` 後綴者放行並回顯；裸主機名不視為網址形）。

## 保守處理與已知落差

- **隱藏 Streamlit 的 `InputInstructions`**（「Press Enter to submit form」與字數計數）：因為它會蓋住長輸入；代價是視覺上少了「按 Enter 可送出」的提示與字數提示（Enter 仍可送出，已測）。是否保留提示屬設計取捨，待設計者確認。

- 缺值字樣不使用規則表 `missing`（`◇ 資料未備`，只限正式模式），也不沿用 fund_search 的 `⬜ 資料未備`，避免複製規則表符號；詳見上方第 3 點。
- 已核准狀態列只取規則表既有的 `fetch_failed`（⛔）與 `undetermined`（⬜）；新增的說明句全是 PendingWording，不新增規則表項目。
- 沒有「來源與限制」收合區（與 fund_search 預覽不同）：本元件規格只要求輸入、按鈕、ISIN 說明與結果卡；限制說明併入結果卡的說明句。
- `session_state` 以 ViewModel 為單位；Streamlit 輸入框 widget 自己的 key 會保存使用者輸入原值，無法由本元件避免。

## 已登記、本輪不做（待辦，不構成動工授權）

- 頁面層 CSS（`block-container`、`h1`、`app_css`）與元件 CSS 混在 `CSS` 內，日後應拆 `component_css`／`page_css`（設計債）。
- `id="fl-status"` 為固定 id，同頁若出現多張卡會重複；目前一頁只有一張卡。
- CONFLICT 演示模式下送出查詢，畫面不變（harness 只顯示直接建構的 ViewModel）。
- 少數字面尺寸（48px 觸控下限、2px 焦點環、1px 邊框）寫在 CSS 內，應向 token 提案（本輪不改 `ui_v3/design`）。
